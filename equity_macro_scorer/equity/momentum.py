"""
Momentum scoring — cross-sectional price momentum signals (Carhart / AQR style).

12m-1m momentum is the primary signal, supplemented by 6m and 3m.
Also incorporates technical positioning (vs 52-week high).
"""
from __future__ import annotations
from typing import List

from ..data.models import EquityFundamentals, SubScore
from ..config import WEIGHTS as W


def _score_return(ret: float | None, threshold_strong: float = 0.20) -> float:
    """Score momentum returns: 0% = 50, threshold = 100, -threshold = 0."""
    if ret is None:
        return 50.0
    if ret >= threshold_strong:
        return 100.0
    if ret >= 0:
        return 50.0 + 50.0 * ret / threshold_strong
    if ret >= -threshold_strong:
        return 50.0 + 50.0 * ret / threshold_strong
    return 0.0


def compute_momentum_score(f: EquityFundamentals) -> SubScore:
    m12_s = _score_return(f.momentum_12m, threshold_strong=0.20)
    m6_s = _score_return(f.momentum_6m, threshold_strong=0.15)
    m3_s = _score_return(f.momentum_3m, threshold_strong=0.10)

    # Distance from 52-week high (0% = at high = 100, -30% = 0)
    h52_s = 50.0
    if f.price_vs_52w_high is not None:
        h52_s = max(0.0, min(100.0, 100.0 + f.price_vs_52w_high * 300))

    # Weights: 12m carries most signal, recent short-term momentum as confirmation
    score = m12_s * 0.50 + m6_s * 0.25 + m3_s * 0.15 + h52_s * 0.10

    notes: List[str] = []
    if f.momentum_12m and f.momentum_12m > 0.30:
        notes.append(f"Strong 12m momentum +{f.momentum_12m:.0%} — trend following signal")
    if f.momentum_12m and f.momentum_12m < -0.25:
        notes.append(f"Negative 12m momentum {f.momentum_12m:.0%} — mean reversion watch or continued sell-off")
    if f.momentum_3m and f.momentum_12m and f.momentum_3m > 0 and f.momentum_12m < 0:
        notes.append("Short-term reversal within longer-term downtrend — confirm with fundamentals")
    if f.price_vs_52w_high and f.price_vs_52w_high > -0.05:
        notes.append("Near 52-week high — strong price action / breakout territory")

    return SubScore(
        name="Momentum",
        score=min(100.0, max(0.0, score)),
        weight=W.equity_momentum,
        drivers={
            "12m Momentum (ex-1m)": f.momentum_12m,
            "6m Momentum": f.momentum_6m,
            "3m Momentum": f.momentum_3m,
            "vs 52w High": f.price_vs_52w_high,
        },
        notes=notes,
    )
