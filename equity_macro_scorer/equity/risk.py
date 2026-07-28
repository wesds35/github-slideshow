"""
Aladdin-style risk decomposition and factor exposure estimation.

Computes:
- Factor z-scores (Market Beta, Size, Value, Profitability, Investment, Momentum, LowVol)
- Risk classification (Very Low / Low / Moderate / High / Very High)
- Qualitative risk flags
"""
from __future__ import annotations
import math
from typing import Dict, List

from ..data.models import EquityFundamentals, RiskLevel
from ..config import FACTOR_NAMES


# Reference universe distribution parameters for z-score normalisation
# These represent approximate cross-sectional means and stds for large-cap US equities
_FACTOR_PARAMS: Dict[str, Dict] = {
    "Market": {"mean": 1.0, "std": 0.40},
    "Size": {"mean": 10.0, "std": 1.5},       # log10(market cap in USD)
    "Value": {"mean": 0.0, "std": 1.0},        # B/P z-scored
    "Profitability": {"mean": 0.0, "std": 1.0},
    "Investment": {"mean": 0.0, "std": 1.0},
    "Momentum": {"mean": 0.08, "std": 0.30},
    "LowVol": {"mean": 0.25, "std": 0.15},     # 1yr volatility
}


def _z(val: float | None, mean: float, std: float) -> float:
    if val is None:
        return 0.0
    return (val - mean) / std if std > 0 else 0.0


def compute_factor_exposures(f: EquityFundamentals) -> Dict[str, float]:
    """
    Estimate factor z-scores relative to the cross-sectional universe.
    Positive = tilted toward factor; negative = opposite tilt.
    """
    exposures: Dict[str, float] = {}

    # Market (Beta)
    exposures["Market"] = _z(f.beta, _FACTOR_PARAMS["Market"]["mean"], _FACTOR_PARAMS["Market"]["std"])

    # Size (SMB — negative z = large cap, positive = small cap)
    if f.market_cap and f.market_cap > 0:
        log_cap = math.log10(f.market_cap)
        exposures["Size"] = -_z(log_cap, _FACTOR_PARAMS["Size"]["mean"], _FACTOR_PARAMS["Size"]["std"])
    else:
        exposures["Size"] = 0.0

    # Value (HML) — proxy via book-to-price (inverse of P/B)
    btp = 1.0 / f.pb_ratio if f.pb_ratio and f.pb_ratio > 0 else None
    exposures["Value"] = _z(btp, 0.35, 0.25) if btp else 0.0

    # Profitability (RMW) — z-score of gross profitability
    exposures["Profitability"] = _z(
        f.gross_margin,
        _FACTOR_PARAMS["Profitability"]["mean"] + 0.30,
        0.20,
    )

    # Investment (CMA) — low CapEx intensity = conservative investment = positive CMA
    exposures["Investment"] = _z(
        -(f.capex_intensity or 0.10),
        -0.08,
        0.06,
    )

    # Momentum (UMD)
    exposures["Momentum"] = _z(
        f.momentum_12m,
        _FACTOR_PARAMS["Momentum"]["mean"],
        _FACTOR_PARAMS["Momentum"]["std"],
    )

    # Low Volatility — negative: low vol = positive exposure
    exposures["LowVol"] = -_z(
        f.volatility_1yr,
        _FACTOR_PARAMS["LowVol"]["mean"],
        _FACTOR_PARAMS["LowVol"]["std"],
    )

    # Clamp to [-3, +3]
    return {k: max(-3.0, min(3.0, v)) for k, v in exposures.items()}


def classify_risk(f: EquityFundamentals) -> tuple:
    """Returns (RiskLevel, list of risk flags)."""
    flags: List[str] = []
    risk_score = 50.0  # baseline moderate

    # Volatility contribution
    if f.volatility_1yr is not None:
        if f.volatility_1yr > 0.50:
            risk_score += 25
            flags.append(f"Very high 1yr volatility: {f.volatility_1yr:.0%}")
        elif f.volatility_1yr > 0.35:
            risk_score += 15
            flags.append(f"High 1yr volatility: {f.volatility_1yr:.0%}")
        elif f.volatility_1yr < 0.15:
            risk_score -= 15

    # Beta contribution
    if f.beta is not None:
        if f.beta > 1.5:
            risk_score += 15
            flags.append(f"High beta {f.beta:.2f} — amplified market moves")
        elif f.beta < 0.5:
            risk_score -= 10

    # Leverage contribution
    if f.debt_to_equity is not None:
        if f.debt_to_equity > 2.0:
            risk_score += 15
            flags.append(f"High leverage D/E={f.debt_to_equity:.1f}x")
        elif f.debt_to_equity > 1.0:
            risk_score += 8

    # Altman Z distress flag
    if f.altman_z is not None and f.altman_z < 1.81:
        risk_score += 20
        flags.append(f"Altman Z={f.altman_z:.2f} — financial distress zone")

    # Interest coverage
    if f.interest_coverage is not None and f.interest_coverage < 2.0:
        risk_score += 10
        flags.append(f"Thin interest coverage {f.interest_coverage:.1f}x")

    risk_score = max(0.0, min(100.0, risk_score))

    if risk_score >= 80:
        level = RiskLevel.VERY_HIGH
    elif risk_score >= 65:
        level = RiskLevel.HIGH
    elif risk_score >= 45:
        level = RiskLevel.MODERATE
    elif risk_score >= 30:
        level = RiskLevel.LOW
    else:
        level = RiskLevel.VERY_LOW

    return level, flags
