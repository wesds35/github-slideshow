#!/usr/bin/env python3
"""Daily tracker: Bayesian estimates over sleep, nicotine, porn, reading,
expenses and income.

Data lives in tracker/data/daily.csv, one row per date. Automated sources
(Oura, bank) and manual logs upsert into the same row, so partial data is
fine and everything is re-runnable.

Commands:
  log             record today's (or --date's) manual fields
  fetch           pull sleep from Oura and money flow from the bank
  report          rebuild tracker/report.md from the data
  claim-simplefin one-time exchange of a SimpleFIN setup token
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from bayes import model

DATA = Path(__file__).parent / "data" / "daily.csv"
REPORT = Path(__file__).parent / "report.md"

FIELDS = ["date", "sleep_hours", "sleep_score", "nicotine_mg", "porn",
          "reading_minutes", "expenses", "income", "notes"]

# Habits reported as use/no-use: (label, column). A numeric column counts
# as "use" when its value is > 0, so nicotine frequency comes from mg.
BINARY = [("Nicotine", "nicotine_mg"), ("Porn", "porn")]

CONTINUOUS = {
    # column -> (label, unit, higher_is_better, nonzero_only)
    "sleep_hours": ("Sleep", "h", True, False),
    "nicotine_mg": ("Nicotine dose (use days)", "mg", False, True),
    "reading_minutes": ("Reading", "min", True, False),
    "expenses": ("Expenses", "$", False, False),
    "income": ("Income", "$", True, False),
}


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------

def load() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if DATA.exists():
        with DATA.open(newline="") as f:
            for row in csv.DictReader(f):
                if row.get("date"):
                    rows[row["date"]] = row
    return rows


def save(rows: dict[str, dict]) -> None:
    DATA.parent.mkdir(parents=True, exist_ok=True)
    with DATA.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for day in sorted(rows):
            w.writerow({k: rows[day].get(k, "") for k in FIELDS})


def upsert(rows: dict[str, dict], day: str, values: dict) -> None:
    row = rows.setdefault(day, {"date": day})
    for k, v in values.items():
        if v is not None and v != "":
            row[k] = v


def _f(row: dict, key: str) -> float | None:
    v = row.get(key, "")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _b(row: dict, key: str) -> int | None:
    v = _f(row, key)
    return None if v is None else int(v > 0)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def cmd_log(args) -> None:
    rows = load()
    day = args.date or date.today().isoformat()
    datetime.strptime(day, "%Y-%m-%d")  # validate

    def yn(v):
        if v is None:
            return None
        return 1 if str(v).strip().lower() in ("1", "y", "yes", "true") else 0

    upsert(rows, day, {
        "nicotine_mg": args.nicotine,
        "porn": yn(args.porn),
        "reading_minutes": args.reading,
        "sleep_hours": args.sleep,
        "expenses": args.expenses,
        "income": args.income,
        "notes": args.notes,
    })
    save(rows)
    print(f"Logged {day}: {rows[day]}")


def cmd_fetch(args) -> None:
    rows = load()
    end = date.today()
    start = end - timedelta(days=args.days)
    fetched_something = False

    import os
    if os.environ.get("OURA_TOKEN"):
        from connectors import oura
        sleep = oura.fetch_sleep(start, end)
        for day, vals in sleep.items():
            upsert(rows, day, vals)
        print(f"Oura: updated {len(sleep)} day(s)")
        fetched_something = True
    else:
        print("Oura: skipped (OURA_TOKEN not set)")

    if os.environ.get("SIMPLEFIN_ACCESS_URL") or os.environ.get("PLAID_ACCESS_TOKEN"):
        from connectors import bank
        money = bank.fetch_money(start, end)
        for day, vals in money.items():
            upsert(rows, day, vals)
        print(f"Bank: updated {len(money)} day(s)")
        fetched_something = True
    else:
        print("Bank: skipped (SIMPLEFIN_ACCESS_URL / PLAID_* not set)")

    if fetched_something:
        save(rows)


def cmd_claim_simplefin(args) -> None:
    from connectors import bank
    url = bank.claim_simplefin_token(args.setup_token)
    print("Access URL (store as SIMPLEFIN_ACCESS_URL secret, shown once):")
    print(url)


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def _trend_line(p: float | None) -> str:
    if p is None:
        return "not enough data for a trend yet"
    if p >= 0.9:
        return f"**improving** (P = {_pct(p)})"
    if p >= 0.7:
        return f"probably improving (P = {_pct(p)})"
    if p > 0.3:
        return f"flat (P(improving) = {_pct(p)})"
    if p > 0.1:
        return f"probably slipping (P(improving) = {_pct(p)})"
    return f"**slipping** (P(improving) = {_pct(p)})"


def cmd_report(args) -> None:
    rows = load()
    if not rows:
        print("No data yet — run `track.py log` or `track.py fetch` first.")
        return
    today = date.today()

    lines = ["# Tracker report", "",
             f"_Generated {today.isoformat()} — {len(rows)} day(s) of data. "
             "All intervals are 95% credible intervals._", ""]

    # Binary habits
    lines += ["## Habits", ""]
    for label, col in BINARY:
        events = []
        for day, row in rows.items():
            x = _b(row, col)
            if x is not None:
                events.append((date.fromisoformat(day), x))
        lines.append(f"### {label}")
        if len(events) < 3:
            lines += ["", f"Only {len(events)} logged day(s) — log a few more.", ""]
            continue
        s = model.binary_summary(events, today)
        lines += [
            "",
            f"- Current use rate: **{_pct(s['rate_mean'])}** per day "
            f"({_pct(s['rate_ci_low'])}–{_pct(s['rate_ci_high'])}), "
            "recency-weighted",
            f"- Last 14 days: {_pct(s['recent_rate'])} vs baseline "
            f"{_pct(s['baseline_rate'])} — {_trend_line(s['p_improving'])}",
            f"- Clean streak: **{s['streak_days']} day(s)**",
            "",
        ]

    # Continuous metrics
    lines += ["## Metrics", ""]
    for col, (label, unit, hib, nonzero_only) in CONTINUOUS.items():
        points = []
        for day, row in rows.items():
            v = _f(row, col)
            if v is not None and not (nonzero_only and v <= 0):
                points.append((date.fromisoformat(day), v))
        lines.append(f"### {label}")
        s = model.continuous_summary(points, today, higher_is_better=hib)
        if s is None or s["n_days"] < 3:
            n = 0 if s is None else s["n_days"]
            lines += ["", f"Only {n} logged day(s) — need at least 3.", ""]
            continue

        def fmt(v):
            return f"${v:,.2f}" if unit == "$" else f"{v:.1f} {unit}"

        lines += [
            "",
            f"- Typical day: **{fmt(s['mean'])}** "
            f"(mean in {fmt(s['mu_ci_low'])}–{fmt(s['mu_ci_high'])})",
            f"- Normal single-day range: {fmt(max(0, s['pred_low']))}–{fmt(s['pred_high'])}",
        ]
        if s["recent_mean"] is not None and s["baseline_mean"] is not None:
            lines.append(
                f"- Last 14 days: {fmt(s['recent_mean'])} vs baseline "
                f"{fmt(s['baseline_mean'])} — {_trend_line(s['p_improving'])}")
        flag = " ⚠️ **outside normal range**" if s["latest_anomalous"] else ""
        lines += [f"- Latest ({s['latest_date']}): {fmt(s['latest_value'])}{flag}", ""]

    # Sleep -> habit interaction
    sleep = {}
    for day, row in rows.items():
        v = _f(row, "sleep_hours")
        if v is not None:
            sleep[date.fromisoformat(day)] = v
    inter_lines = []
    for label, col in BINARY:
        habit = {}
        for day, row in rows.items():
            x = _b(row, col)
            if x is not None:
                habit[date.fromisoformat(day)] = x
        s = model.conditional_habit_on_sleep(habit, sleep)
        if s:
            inter_lines.append(
                f"- **{label}** after short sleep (<{s['threshold']}h): "
                f"{_pct(s['p_habit_short_sleep'])} vs {_pct(s['p_habit_ok_sleep'])} "
                f"after decent sleep — P(short sleep makes it worse) = "
                f"{_pct(s['p_short_sleep_worse'])}")
    if inter_lines:
        lines += ["## Does sleep drive the habits?", ""] + inter_lines + [""]

    lines += _recent_table(rows)
    lines += _projections(rows, today)

    REPORT.write_text("\n".join(lines))
    print(f"Wrote {REPORT}")


def _recent_table(rows: dict[str, dict]) -> list[str]:
    lines = ["## Last 7 days", "",
             "| Date | Sleep h | Score | Nicotine mg | Porn | Reading min | Expenses | Income |",
             "|---|---|---|---|---|---|---|---|"]
    for day in sorted(rows)[-7:]:
        r = rows[day]

        def cell(key, money=False):
            v = _f(r, key)
            if v is None:
                return "—"
            return f"${v:,.2f}" if money else f"{v:g}"

        porn = _b(r, "porn")
        porn_s = "—" if porn is None else ("yes" if porn else "no")
        lines.append(
            f"| {day} | {cell('sleep_hours')} | {cell('sleep_score')} | "
            f"{cell('nicotine_mg')} | {porn_s} | {cell('reading_minutes')} | "
            f"{cell('expenses', True)} | {cell('income', True)} |")
    return lines + [""]


def _projections(rows: dict[str, dict], today: date) -> list[str]:
    lines = ["## Projections", "",
             "_Posterior-predictive forecasts from today's model. Ranges are "
             "90% intervals — wide ranges mean the model is still uncertain, "
             "and every logged day tightens them._", ""]

    def values(col, max_age, nonzero=False):
        out = []
        for day, row in rows.items():
            v = _f(row, col)
            if v is None or (nonzero and v <= 0):
                continue
            if 0 <= (today - date.fromisoformat(day)).days < max_age:
                out.append(v)
        return out

    def binary_events(col):
        out = []
        for day, row in rows.items():
            x = _b(row, col)
            if x is not None:
                out.append((date.fromisoformat(day), x))
        return out

    def rng(p, fmt=lambda v: f"{v:.0f}"):
        return f"**{fmt(p['mean'])}** ({fmt(p['lo'])}–{fmt(p['hi'])})"

    money = lambda v: f"${max(v, 0):,.0f}"

    # Nicotine: use days and total mg next 7 days.
    nic_events = binary_events("nicotine_mg")
    if len(nic_events) >= 3:
        freq = model.discounted_beta(nic_events, today)
        days7 = model.project_binary(freq, 7)
        line = f"- **Nicotine, next 7 days:** {rng(days7)} use day(s)"
        dose_vals = values("nicotine_mg", 60, nonzero=True)
        dose_post = model.fit_nig(dose_vals) if len(dose_vals) >= 3 else None
        if dose_post:
            load = model.project_habit_load(freq, dose_post, 7)
            line += f", totaling {rng(load, lambda v: f'{v:.0f} mg')}"
        lines.append(line)

    # Porn: use days next 7 days.
    porn_events = binary_events("porn")
    if len(porn_events) >= 3:
        days7 = model.project_binary(model.discounted_beta(porn_events, today), 7)
        lines.append(f"- **Porn, next 7 days:** {rng(days7)} use day(s)")

    # Sleep: average over the next 7 nights.
    sleep_post = model.fit_nig(values("sleep_hours", 30))
    if sleep_post and sleep_post.k >= 3:
        avg = model.project_continuous_mean(sleep_post, 7)
        lines.append(f"- **Sleep, next 7 nights:** average "
                     f"{rng(avg, lambda v: f'{v:.1f} h')} per night")

    # Reading: total minutes next 7 days.
    read_post = model.fit_nig(values("reading_minutes", 30))
    if read_post and read_post.k >= 3:
        tot = model.project_continuous_total(read_post, 7)
        lines.append(f"- **Reading, next 7 days:** "
                     f"{rng(tot, lambda v: f'{max(v, 0):.0f} min')} total")

    # Money: next 7 and 30 days.
    exp_post = model.fit_nig(values("expenses", 60))
    if exp_post and exp_post.k >= 3:
        w = model.project_continuous_total(exp_post, 7)
        m = model.project_continuous_total(exp_post, 30)
        lines.append(f"- **Expenses:** next 7 days {rng(w, money)}, "
                     f"next 30 days {rng(m, money)}")
    inc_post = model.fit_nig(values("income", 60))
    if inc_post and inc_post.k >= 3:
        m = model.project_continuous_total(inc_post, 30)
        lines.append(f"- **Income, next 30 days:** {rng(m, money)}")

    if len(lines) <= 4:
        lines.append("_Not enough data yet — projections appear at 3+ "
                     "logged days per metric._")
    return lines + [""]


# --------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    lg = sub.add_parser("log", help="record manual fields for a day")
    lg.add_argument("--date", help="YYYY-MM-DD (default: today)")
    lg.add_argument("--nicotine", type=float, help="mg (0 = none)")
    lg.add_argument("--porn", help="y/n")
    lg.add_argument("--reading", type=float, help="minutes read")
    lg.add_argument("--sleep", type=float, help="hours (manual override)")
    lg.add_argument("--expenses", type=float, help="manual override, $")
    lg.add_argument("--income", type=float, help="manual override, $")
    lg.add_argument("--notes")
    lg.set_defaults(func=cmd_log)

    ft = sub.add_parser("fetch", help="pull from Oura and bank")
    ft.add_argument("--days", type=int, default=7,
                    help="lookback window (default 7; use ~90 for first backfill)")
    ft.set_defaults(func=cmd_fetch)

    rp = sub.add_parser("report", help="rebuild report.md")
    rp.set_defaults(func=cmd_report)

    cl = sub.add_parser("claim-simplefin",
                        help="exchange a SimpleFIN setup token for an access URL")
    cl.add_argument("setup_token")
    cl.set_defaults(func=cmd_claim_simplefin)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
