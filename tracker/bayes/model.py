"""Bayesian models for daily habit / lifestyle tracking.

Two model families:

* Binary habits (nicotine, porn): Beta-Bernoulli with exponential
  discounting, so the posterior tracks your *current* rate rather than a
  lifetime average. Trend detection compares a recent window against a
  baseline window and reports P(recent rate < baseline rate).

* Continuous metrics (sleep hours, reading minutes, expenses, income):
  Normal model with unknown mean and variance (Normal-Inverse-Gamma
  conjugate prior). Reports a credible interval for the underlying mean,
  a posterior-predictive interval for a single day, and flags anomalies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
from scipy import stats

RNG = np.random.default_rng(1234)
MC_SAMPLES = 40_000


# --------------------------------------------------------------------------
# Binary habits: Beta-Bernoulli
# --------------------------------------------------------------------------

@dataclass
class BetaPosterior:
    a: float
    b: float

    @property
    def mean(self) -> float:
        return self.a / (self.a + self.b)

    def ci(self, level: float = 0.95) -> tuple[float, float]:
        lo = (1 - level) / 2
        return (stats.beta.ppf(lo, self.a, self.b),
                stats.beta.ppf(1 - lo, self.a, self.b))

    def sample(self, n: int = MC_SAMPLES) -> np.ndarray:
        return RNG.beta(self.a, self.b, size=n)


def discounted_beta(events: list[tuple[date, int]], as_of: date,
                    half_life_days: float = 21.0,
                    prior_a: float = 1.0, prior_b: float = 1.0) -> BetaPosterior:
    """Beta posterior where each observation is weighted by 0.5^(age/half_life).

    An abstinent day from three weeks ago counts half as much as one from
    today, so the estimate adapts as behavior actually changes.
    """
    a, b = prior_a, prior_b
    for d, x in events:
        age = (as_of - d).days
        if age < 0:
            continue
        w = 0.5 ** (age / half_life_days)
        if x:
            a += w
        else:
            b += w
    return BetaPosterior(a, b)


def window_beta(events: list[tuple[date, int]], as_of: date,
                start_age: int, end_age: int) -> BetaPosterior:
    """Flat Beta(1,1) posterior over days whose age is in [start_age, end_age)."""
    a, b = 1.0, 1.0
    for d, x in events:
        age = (as_of - d).days
        if start_age <= age < end_age:
            if x:
                a += 1
            else:
                b += 1
    return BetaPosterior(a, b)


def binary_summary(events: list[tuple[date, int]], as_of: date,
                   recent_days: int = 14, baseline_days: int = 60) -> dict:
    """Full report for one binary habit."""
    post = discounted_beta(events, as_of)
    recent = window_beta(events, as_of, 0, recent_days)
    baseline = window_beta(events, as_of, recent_days, recent_days + baseline_days)

    # P(recent rate < baseline rate) by Monte Carlo over the two posteriors.
    p_improving = float(np.mean(recent.sample() < baseline.sample()))

    # Current abstinence streak.
    streak = 0
    for d, x in sorted(events, key=lambda e: e[0], reverse=True):
        if d > as_of:
            continue
        if x == 0:
            streak += 1
        else:
            break

    ci = post.ci()
    return {
        "n_days": len(events),
        "rate_mean": post.mean,
        "rate_ci_low": ci[0],
        "rate_ci_high": ci[1],
        "recent_rate": recent.mean,
        "baseline_rate": baseline.mean,
        "p_improving": p_improving,
        "streak_days": streak,
    }


# --------------------------------------------------------------------------
# Continuous metrics: Normal-Inverse-Gamma
# --------------------------------------------------------------------------

@dataclass
class NIGPosterior:
    """Posterior for Normal likelihood with unknown mean and variance."""
    m: float      # posterior mean of mu
    k: float      # pseudo-observations behind m
    alpha: float
    beta: float

    def mu_ci(self, level: float = 0.95) -> tuple[float, float]:
        """Credible interval for the underlying mean mu."""
        scale = math.sqrt(self.beta / (self.alpha * self.k))
        lo = (1 - level) / 2
        t = stats.t(df=2 * self.alpha, loc=self.m, scale=scale)
        return (t.ppf(lo), t.ppf(1 - lo))

    def predictive_ci(self, level: float = 0.95) -> tuple[float, float]:
        """Interval where a single new day's value should fall."""
        scale = math.sqrt(self.beta * (self.k + 1) / (self.alpha * self.k))
        lo = (1 - level) / 2
        t = stats.t(df=2 * self.alpha, loc=self.m, scale=scale)
        return (t.ppf(lo), t.ppf(1 - lo))

    def sample_mu(self, n: int = MC_SAMPLES) -> np.ndarray:
        scale = math.sqrt(self.beta / (self.alpha * self.k))
        return stats.t.rvs(df=2 * self.alpha, loc=self.m, scale=scale,
                           size=n, random_state=RNG)


def fit_nig(values: list[float],
            m0: float = 0.0, k0: float = 0.01,
            alpha0: float = 0.5, beta0: float = 0.5) -> NIGPosterior | None:
    """Conjugate NIG update with a near-flat prior."""
    n = len(values)
    if n == 0:
        return None
    xs = np.asarray(values, dtype=float)
    xbar = float(xs.mean())
    ss = float(((xs - xbar) ** 2).sum())

    k = k0 + n
    m = (k0 * m0 + n * xbar) / k
    alpha = alpha0 + n / 2
    beta = beta0 + 0.5 * ss + (k0 * n * (xbar - m0) ** 2) / (2 * k)
    return NIGPosterior(m=m, k=k, alpha=alpha, beta=beta)


def continuous_summary(points: list[tuple[date, float]], as_of: date,
                       recent_days: int = 14, baseline_days: int = 60,
                       higher_is_better: bool = True) -> dict | None:
    """Full report for one continuous metric."""
    points = [(d, v) for d, v in points if d <= as_of and v is not None]
    if not points:
        return None

    all_vals = [v for _, v in points]
    post = fit_nig(all_vals)

    recent_vals = [v for d, v in points if (as_of - d).days < recent_days]
    base_vals = [v for d, v in points
                 if recent_days <= (as_of - d).days < recent_days + baseline_days]

    p_improving = None
    recent_post = fit_nig(recent_vals) if len(recent_vals) >= 3 else None
    base_post = fit_nig(base_vals) if len(base_vals) >= 3 else None
    if recent_post and base_post:
        diff = recent_post.sample_mu() - base_post.sample_mu()
        p_higher = float(np.mean(diff > 0))
        p_improving = p_higher if higher_is_better else 1 - p_higher

    latest_date, latest_val = max(points, key=lambda p: p[0])
    pred_lo, pred_hi = post.predictive_ci()
    mu_lo, mu_hi = post.mu_ci()

    return {
        "n_days": len(points),
        "mean": post.m,
        "mu_ci_low": mu_lo,
        "mu_ci_high": mu_hi,
        "pred_low": pred_lo,
        "pred_high": pred_hi,
        "recent_mean": float(np.mean(recent_vals)) if recent_vals else None,
        "baseline_mean": float(np.mean(base_vals)) if base_vals else None,
        "p_improving": p_improving,
        "latest_date": latest_date.isoformat(),
        "latest_value": latest_val,
        "latest_anomalous": not (pred_lo <= latest_val <= pred_hi),
    }


# --------------------------------------------------------------------------
# Cross-metric: does short sleep predict a habit?
# --------------------------------------------------------------------------

def conditional_habit_on_sleep(habit_events: dict[date, int],
                               sleep_hours: dict[date, float],
                               threshold: float = 6.5) -> dict | None:
    """P(habit | previous night short sleep) vs P(habit | decent sleep).

    Sleep for date D is the night ending on morning D, so it conditions the
    *same* day's behavior.
    """
    short_a, short_b = 1.0, 1.0
    ok_a, ok_b = 1.0, 1.0
    n = 0
    for d, x in habit_events.items():
        h = sleep_hours.get(d)
        if h is None:
            continue
        n += 1
        if h < threshold:
            short_a, short_b = short_a + x, short_b + (1 - x)
        else:
            ok_a, ok_b = ok_a + x, ok_b + (1 - x)
    if n < 10:
        return None

    short = BetaPosterior(short_a, short_b)
    ok = BetaPosterior(ok_a, ok_b)
    return {
        "n_days": n,
        "threshold": threshold,
        "p_habit_short_sleep": short.mean,
        "p_habit_ok_sleep": ok.mean,
        "p_short_sleep_worse": float(np.mean(short.sample() > ok.sample())),
    }
