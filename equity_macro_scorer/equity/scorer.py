"""
Top-level equity scorer — integrates quality, value, growth, momentum, and risk.
"""
from __future__ import annotations
from typing import Optional

from ..data.models import EquityFundamentals, EquityScore, ScoreGrade, SubScore
from ..config import WEIGHTS as W
from .quality import compute_quality_score
from .value import compute_value_score
from .growth import compute_growth_score
from .momentum import compute_momentum_score
from .risk import compute_factor_exposures, classify_risk


def _grade(score: float) -> ScoreGrade:
    if score >= 75:
        return ScoreGrade.STRONG_BUY
    if score >= 62:
        return ScoreGrade.BUY
    if score >= 45:
        return ScoreGrade.NEUTRAL
    if score >= 30:
        return ScoreGrade.SELL
    return ScoreGrade.STRONG_SELL


def score_equity(f: EquityFundamentals, current_price: Optional[float] = None) -> EquityScore:
    """Compute the full composite equity score from fundamentals."""
    quality = compute_quality_score(f)
    value, iv_range, mos = compute_value_score(f)
    growth = compute_growth_score(f)
    momentum = compute_momentum_score(f)

    composite = (
        quality.weighted_score
        + value.weighted_score
        + growth.weighted_score
        + momentum.weighted_score
    )

    grade = _grade(composite)
    risk_level, risk_flags = classify_risk(f)
    factor_exposures = compute_factor_exposures(f)

    upside = None
    if iv_range:
        bear, bull = iv_range
        # relative upside from DCF midpoint
        upside = (bear + bull) / 2 - 1.0

    alerts = risk_flags.copy()
    # Collect analyst-style alerts
    if grade in (ScoreGrade.STRONG_BUY, ScoreGrade.BUY) and risk_level.value in ("High", "Very High"):
        alerts.append("High-conviction score offset by elevated risk — position size carefully")
    if quality.score < 35 and value.score > 65:
        alerts.append("Deep value but weak quality — classic value trap risk")
    if momentum.score < 30 and composite > 65:
        alerts.append("Strong fundamentals but bearish price action — wait for momentum confirmation")

    return EquityScore(
        ticker=f.ticker,
        name=f.name,
        sector=f.sector,
        country=f.country,
        composite=composite,
        grade=grade,
        quality=quality,
        value=value,
        growth=growth,
        momentum=momentum,
        risk_level=risk_level,
        factor_exposures=factor_exposures,
        intrinsic_value_range=iv_range,
        margin_of_safety=mos,
        upside_potential=upside,
        current_price=current_price,
        alerts=alerts,
    )
