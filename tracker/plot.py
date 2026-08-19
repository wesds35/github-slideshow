#!/usr/bin/env python3
"""Render tracker/chart.png: all recorded days plus 7-day projections.

Small multiples, one panel per metric (scales differ too much to share an
axis). History = solid marks; projection = dashed posterior-mean line with
a shaded 90% band from the same posteriors the report uses. Sleep shows
its full history; the other panels start when their tracking started.
"""

from __future__ import annotations

import csv
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))
from bayes import model
from track import DATA, _b, _f, load

OUT = Path(__file__).parent / "chart.png"

# Reference palette (light mode)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SERIES = "#2a78d6"

HORIZON = 7
MC = 20_000
RNG = np.random.default_rng(7)


def _series(rows, col, binary=False):
    out = []
    for day, row in rows.items():
        v = _b(row, col) if binary else _f(row, col)
        if v is not None:
            out.append((date.fromisoformat(day), float(v)))
    return sorted(out)


def _nig_from(points, as_of, window):
    vals = [v for d, v in points if (as_of - d).days < window]
    return model.fit_nig(vals) if len(vals) >= 3 else None


def _nig_daily_band(post, level=0.90):
    lo, hi = post.predictive_ci(level)
    return max(lo, 0.0), post.m, max(hi, 0.0)


def _style(ax, title, subtitle):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold",
                 color=INK, pad=10)
    ax.text(0, 1.015, subtitle, transform=ax.transAxes, fontsize=8,
            color=INK2, va="bottom")


def _projection(ax, days, lo, mean, hi):
    ax.fill_between(days, lo, hi, color=SERIES, alpha=0.14, linewidth=0)
    ax.plot(days, mean, color=SERIES, linewidth=2, linestyle=(0, (4, 3)))


def _today_marker(ax, as_of):
    ax.axvline(as_of + timedelta(hours=12), color=BASELINE,
               linewidth=1, linestyle=(0, (2, 2)))


def main() -> None:
    rows = load()
    if not rows:
        raise SystemExit("no data")
    as_of = max(date.fromisoformat(d) for d in rows)
    proj_days = [as_of + timedelta(days=i) for i in range(1, HORIZON + 1)]
    habit_start = min((date.fromisoformat(d) for d, r in rows.items()
                       if _f(r, "nicotine_mg") is not None), default=as_of)
    zoom_lo = habit_start - timedelta(days=1)
    zoom_hi = proj_days[-1] + timedelta(days=1)

    fig, axes = plt.subplots(6, 1, figsize=(9, 14), dpi=170)
    fig.patch.set_facecolor(SURFACE)

    # --- Sleep: full history -------------------------------------------
    ax = axes[0]
    pts = _series(rows, "sleep_hours")
    ds, vs = zip(*pts)
    ax.plot(ds, vs, color=SERIES, linewidth=1.6)
    post = _nig_from(pts, as_of, 30)
    if post:
        lo, m, hi = _nig_daily_band(post)
        _projection(ax, proj_days, [lo] * HORIZON, [m] * HORIZON, [hi] * HORIZON)
    _style(ax, "Sleep (hours)",
           "full history · dashed = projected typical night, band = 90% single-night range")
    _today_marker(ax, as_of)
    ax.set_ylim(bottom=0)

    # --- Nicotine ------------------------------------------------------
    ax = axes[1]
    pts = _series(rows, "nicotine_mg")
    events = [(d, int(v > 0)) for d, v in pts]
    ax.scatter(*zip(*pts), color=SERIES, s=34, zorder=3)
    ax.plot(*zip(*pts), color=SERIES, linewidth=1.2, alpha=0.5)
    if len(events) >= 3:
        freq = model.discounted_beta(events, as_of)
        dose = model.fit_nig([v for _, v in pts if v > 0])
        if dose:
            p = freq.sample(MC)
            mu, s2 = model._nig_draws(dose, MC)
            daily = RNG.binomial(1, p) * np.maximum(
                RNG.normal(mu, np.sqrt(s2)), 0)
            _projection(ax, proj_days,
                        [float(np.quantile(daily, 0.05))] * HORIZON,
                        [float(daily.mean())] * HORIZON,
                        [float(np.quantile(daily, 0.95))] * HORIZON)
    _style(ax, "Nicotine (mg/day)",
           "dots = logged days · dashed = expected daily mg (use-rate x dose), 90% band")
    _today_marker(ax, as_of)
    ax.set_xlim(zoom_lo, zoom_hi)
    ax.set_ylim(bottom=0)

    # --- Porn ----------------------------------------------------------
    ax = axes[2]
    pts = _series(rows, "porn", binary=True)
    ax.scatter(*zip(*pts), color=SERIES, s=34, zorder=3)
    if len(pts) >= 3:
        beta = model.discounted_beta([(d, int(v)) for d, v in pts], as_of)
        blo, bhi = beta.ci(0.90)
        _projection(ax, proj_days, [blo] * HORIZON,
                    [beta.mean] * HORIZON, [bhi] * HORIZON)
    _style(ax, "Porn (yes / no)",
           "dots = logged days · dashed = probability of a use day, 90% band")
    _today_marker(ax, as_of)
    ax.set_xlim(zoom_lo, zoom_hi)
    ax.set_ylim(-0.08, 1.08)
    ax.set_yticks([0, 1], ["no", "yes"])

    # --- Reading, Expenses, Income ------------------------------------
    panels = [
        ("Reading (minutes/day)", "reading_minutes", 30, axes[3]),
        ("Expenses ($/day)", "expenses", 60, axes[4]),
        ("Income ($/day)", "income", 60, axes[5]),
    ]
    for title, col, window, ax in panels:
        pts = _series(rows, col)
        if pts:
            ax.scatter(*zip(*pts), color=SERIES, s=34, zorder=3)
            ax.plot(*zip(*pts), color=SERIES, linewidth=1.2, alpha=0.5)
        post = _nig_from(pts, as_of, window)
        if post:
            lo, m, hi = _nig_daily_band(post)
            _projection(ax, proj_days, [lo] * HORIZON,
                        [max(m, 0)] * HORIZON, [hi] * HORIZON)
        _style(ax, title,
               "dots = logged days · dashed = projected typical day, 90% band")
        _today_marker(ax, as_of)
        ax.set_xlim(zoom_lo, zoom_hi)
        ax.set_ylim(bottom=0)

    for ax in axes:
        loc = mdates.AutoDateLocator(minticks=4, maxticks=9)
        ax.xaxis.set_major_locator(loc)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))

    fig.suptitle("Daily tracker — history and 7-day projections",
                 x=0.065, y=0.995, ha="left", va="top",
                 fontsize=14, fontweight="bold", color=INK)
    fig.text(0.065, 0.978,
             f"through {as_of.isoformat()} · vertical dotted line = today · "
             "bands widen or shrink as the models learn",
             fontsize=9, color=INK2, va="top")
    fig.tight_layout(rect=(0.01, 0.005, 0.99, 0.958), h_pad=2.2)
    fig.savefig(OUT, facecolor=SURFACE)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
