"""
Bridgewater / Ray Dalio macro regime detection.

The All-Weather framework classifies the environment into four quadrants based
on whether growth and inflation are RISING or FALLING relative to expectations.
"""
from __future__ import annotations
from typing import Dict, Tuple, Optional

from ..data.models import MacroIndicators, MacroRegime
from ..config import REGIME_MATRIX, MACRO_THRESHOLDS as T


def _classify_growth(ind: MacroIndicators) -> str:
    """
    Determine if growth is rising or falling.
    Uses PMI as leading indicator, confirmed by GDP trend.
    """
    signals = []
    if ind.pmi_manufacturing is not None:
        signals.append("rising" if ind.pmi_manufacturing > 50 else "falling")
    if ind.gdp_growth_yoy is not None:
        signals.append("rising" if ind.gdp_growth_yoy > T.gdp_growth_moderate else "falling")
    if ind.industrial_production is not None:
        signals.append("rising" if ind.industrial_production > 0.02 else "falling")
    if ind.consumer_confidence is not None:
        signals.append("rising" if ind.consumer_confidence > 100 else "falling")

    if not signals:
        return "rising"  # default
    return "rising" if signals.count("rising") >= len(signals) / 2 else "falling"


def _classify_inflation(ind: MacroIndicators) -> str:
    """
    Determine if inflation is rising or falling relative to target.
    """
    signals = []
    if ind.cpi_yoy is not None:
        # Rising if above 2.5% (above target) or accelerating
        signals.append("rising" if ind.cpi_yoy > T.inflation_target + 0.005 else "falling")
    if ind.core_cpi_yoy is not None:
        signals.append("rising" if ind.core_cpi_yoy > T.inflation_target + 0.005 else "falling")
    if ind.ppi_yoy is not None:
        signals.append("rising" if ind.ppi_yoy > 0.025 else "falling")
    if ind.breakeven_inflation_5y is not None:
        signals.append("rising" if ind.breakeven_inflation_5y > T.inflation_target + 0.003 else "falling")

    if not signals:
        return "falling"
    return "rising" if signals.count("rising") >= len(signals) / 2 else "falling"


def detect_regime(ind: MacroIndicators) -> Tuple[MacroRegime, Dict]:
    """
    Returns the current macro regime and asset class bias dictionary.
    """
    growth_dir = _classify_growth(ind)
    inflation_dir = _classify_inflation(ind)

    key = (growth_dir, inflation_dir)
    matrix_entry = REGIME_MATRIX.get(key, {})

    label = matrix_entry.get("label", "Transitional")
    try:
        regime = MacroRegime(label)
    except ValueError:
        regime = MacroRegime.TRANSITIONAL

    asset_bias = {
        "equities": matrix_entry.get("equity_bias", 0.0),
        "bonds": matrix_entry.get("bond_bias", 0.0),
        "gold": matrix_entry.get("gold_bias", 0.0),
        "commodities": matrix_entry.get("commodities_bias", 0.0),
    }

    return regime, asset_bias


def regime_confidence(ind: MacroIndicators) -> float:
    """
    0-1 confidence in the detected regime.
    High if signals are unambiguous; low if mixed.
    """
    signals = []
    if ind.pmi_manufacturing is not None:
        distance = abs(ind.pmi_manufacturing - 50)
        signals.append(min(1.0, distance / 5.0))  # 5pt away = full confidence
    if ind.gdp_growth_yoy is not None:
        distance = abs(ind.gdp_growth_yoy - T.gdp_growth_moderate)
        signals.append(min(1.0, distance / 0.02))
    if ind.cpi_yoy is not None:
        distance = abs(ind.cpi_yoy - T.inflation_target)
        signals.append(min(1.0, distance / 0.02))
    return sum(signals) / max(1, len(signals))
