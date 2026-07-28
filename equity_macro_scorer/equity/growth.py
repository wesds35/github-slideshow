"""
Growth scoring — revenue, EPS, FCF, and dividend CAGR quality assessment.
"""
from __future__ import annotations
from typing import List

from ..data.models import EquityFundamentals, SubScore
from ..config import GROWTH_THRESHOLDS as G, WEIGHTS as W


def _score(val: float | None, low: float, mid: float, high: float) -> float:
    if val is None:
        return 50.0
    if val <= low:
        return max(0.0, 25.0 + 25.0 * val / low) if low != 0 else 0.0
    if val <= mid:
        return 50.0 * (val - low) / (mid - low) + (0 if low > 0 else 25.0)
    if val >= high:
        return 100.0
    return 50.0 + 50.0 * (val - mid) / (high - mid)


def compute_growth_score(f: EquityFundamentals) -> SubScore:
    rev_s = _score(f.revenue_growth_3yr, 0.0, G.revenue_growth_good, G.revenue_growth_excellent)
    eps_s = _score(f.eps_growth_3yr, 0.0, G.eps_growth_good, G.eps_growth_excellent)
    fcf_s = _score(f.fcf_growth_3yr, 0.0, G.fcf_growth_good, G.fcf_growth_excellent)
    div_s = _score(f.dividend_growth_3yr, 0.0, 0.05, 0.12)

    # Weighted — EPS and FCF growth more reliable signals than revenue
    if f.fcf_growth_3yr is not None:
        score = rev_s * 0.25 + eps_s * 0.35 + fcf_s * 0.30 + div_s * 0.10
    elif f.eps_growth_3yr is not None:
        score = rev_s * 0.35 + eps_s * 0.55 + div_s * 0.10
    else:
        score = rev_s * 0.80 + div_s * 0.20

    notes: List[str] = []

    if f.revenue_growth_3yr and f.eps_growth_3yr:
        if f.eps_growth_3yr > f.revenue_growth_3yr * 1.5:
            notes.append("EPS growing faster than revenue — operating leverage or margin expansion")
        elif f.eps_growth_3yr < f.revenue_growth_3yr * 0.3:
            notes.append("EPS growing much slower than revenue — margin compression or dilution")

    if f.revenue_growth_3yr and f.revenue_growth_3yr < 0:
        notes.append("Negative revenue growth — secular decline or cyclical trough")

    if f.eps_growth_3yr and f.eps_growth_3yr > 0.25:
        notes.append(f"High EPS CAGR {f.eps_growth_3yr:.0%} — verify sustainability and base effect")

    return SubScore(
        name="Growth",
        score=min(100.0, max(0.0, score)),
        weight=W.equity_growth,
        drivers={
            "Revenue Growth (3yr)": f.revenue_growth_3yr,
            "EPS Growth (3yr)": f.eps_growth_3yr,
            "FCF Growth (3yr)": f.fcf_growth_3yr,
            "Dividend Growth (3yr)": f.dividend_growth_3yr,
        },
        notes=notes,
    )
