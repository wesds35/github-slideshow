"""
Top-level macro scorer — integrates all five sovereign dimensions and regime detection.
"""
from __future__ import annotations
from typing import List

from ..data.models import MacroIndicators, MacroScore, ScoreGrade
from ..config import WEIGHTS as W
from .sovereign import score_growth, score_inflation, score_fiscal, score_external, score_monetary
from .regime import detect_regime, regime_confidence


def _grade(score: float) -> ScoreGrade:
    if score >= 72:
        return ScoreGrade.STRONG_BUY   # re-used: Overweight / Constructive
    if score >= 58:
        return ScoreGrade.BUY          # Overweight
    if score >= 42:
        return ScoreGrade.NEUTRAL
    if score >= 28:
        return ScoreGrade.SELL         # Underweight
    return ScoreGrade.STRONG_SELL      # Strongly Underweight


def _tail_risks(ind: MacroIndicators) -> List[str]:
    risks: List[str] = []
    if ind.debt_pct_gdp and ind.debt_pct_gdp > 1.20:
        risks.append("Debt-to-GDP > 120% — debt restructuring / default scenario non-trivial")
    if ind.cpi_yoy and ind.cpi_yoy > 0.10:
        risks.append("Inflation > 10% — hyperinflation tail or emergency rate hikes")
    if ind.yield_curve_slope and ind.yield_curve_slope < -0.01:
        risks.append("Deeply inverted yield curve — elevated near-term recession probability")
    if ind.current_account_pct_gdp and ind.current_account_pct_gdp < -0.07:
        risks.append("CA deficit > 7% GDP — sudden stop / BoP crisis risk")
    if ind.fx_reserves_months_imports and ind.fx_reserves_months_imports < 2:
        risks.append("FX reserves < 2 months imports — currency crisis vulnerability")
    if ind.credit_spread_hy and ind.credit_spread_hy > 0.10:
        risks.append("HY spreads > 1000bps — systemic credit event signalled")
    if ind.fiscal_deficit_pct_gdp and ind.fiscal_deficit_pct_gdp < -0.12:
        risks.append("Fiscal deficit > 12% GDP — MMT territory or emergency spending")
    return risks


def score_macro(ind: MacroIndicators) -> MacroScore:
    """Compute the full composite macro score for a country/region."""
    growth = score_growth(ind)
    inflation = score_inflation(ind)
    fiscal = score_fiscal(ind)
    external = score_external(ind)
    monetary = score_monetary(ind)

    composite = (
        growth.weighted_score
        + inflation.weighted_score
        + fiscal.weighted_score
        + external.weighted_score
        + monetary.weighted_score
    )

    grade = _grade(composite)
    regime, asset_bias = detect_regime(ind)
    confidence = regime_confidence(ind)

    alerts: List[str] = []
    # Cross-dimension alerts
    if growth.score < 35 and inflation.score < 35:
        alerts.append("Stagflation signature — worst combination for risky assets")
    if growth.score > 65 and inflation.score < 50:
        alerts.append("Goldilocks environment — historically supportive for equities/credit")
    if fiscal.score < 30 and external.score < 40:
        alerts.append("Twin deficit / fiscal-external stress — sovereign spread widening risk")
    if monetary.score < 35 and growth.score < 45:
        alerts.append("Restrictive monetary policy amid slowing growth — policy error risk")
    if confidence < 0.4:
        alerts.append(f"Regime confidence low ({confidence:.0%}) — signals mixed, transitional environment")

    tail_risks = _tail_risks(ind)

    return MacroScore(
        country=ind.country,
        currency=ind.currency,
        composite=composite,
        grade=grade,
        regime=regime,
        growth=growth,
        inflation=inflation,
        fiscal=fiscal,
        external=external,
        monetary=monetary,
        asset_bias=asset_bias,
        alerts=alerts,
        tail_risks=tail_risks,
    )
