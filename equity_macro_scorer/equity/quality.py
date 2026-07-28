"""
Graham/Buffett quality screens and Aladdin profitability factor.

Scores profitability, balance sheet strength, and cash-flow quality
on a 0-100 scale, then combines into a Quality composite.
"""
from __future__ import annotations
import math
from typing import List

from ..data.models import EquityFundamentals, SubScore
from ..config import QUALITY_THRESHOLDS as T, WEIGHTS as W

_Q = T  # alias


def _score_metric(val: float | None, low: float, mid: float, high: float,
                  reverse: bool = False) -> float:
    """
    Map val onto [0, 100] with three anchor points.
    If reverse=True, lower values are better (e.g. debt ratios).
    """
    if val is None:
        return 50.0  # neutral if missing
    if reverse:
        val = -val
        low, mid, high = -high, -mid, -low
    if val <= low:
        return 0.0
    if val >= high:
        return 100.0
    if val <= mid:
        return 50.0 * (val - low) / (mid - low)
    return 50.0 + 50.0 * (val - mid) / (high - mid)


def score_profitability(f: EquityFundamentals) -> SubScore:
    """Scores: ROE, ROA, ROIC, gross margin, operating margin, net margin."""
    drivers = {}
    signals = {}
    notes: List[str] = []

    roe_s = _score_metric(f.roe, 0.05, _Q.roe_good, _Q.roe_excellent)
    roa_s = _score_metric(f.roa, 0.02, 0.06, 0.12)
    roic_s = _score_metric(f.roic, 0.04, _Q.roic_good, _Q.roic_excellent)
    gm_s = _score_metric(f.gross_margin, 0.10, _Q.gross_margin_good, _Q.gross_margin_excellent)
    om_s = _score_metric(f.operating_margin, 0.02, _Q.operating_margin_good, _Q.operating_margin_excellent)
    nm_s = _score_metric(f.net_margin, 0.01, 0.05, 0.15)

    score = (roe_s * 0.25 + roa_s * 0.15 + roic_s * 0.25 +
             gm_s * 0.15 + om_s * 0.15 + nm_s * 0.05)

    def _pct(v): return f"{v:.1%}" if v is not None else "N/A"

    drivers = {
        "ROE": f.roe, "ROA": f.roa, "ROIC": f.roic,
        "Gross Margin": f.gross_margin,
        "Operating Margin": f.operating_margin,
        "Net Margin": f.net_margin,
    }
    if f.roe and f.roe >= _Q.roe_excellent:
        notes.append(f"Excellent ROE of {_pct(f.roe)} — pricing power / leverage quality")
    if f.roic and f.roic >= _Q.roic_excellent:
        notes.append(f"High ROIC {_pct(f.roic)} — capital-light business model")
    if f.operating_margin and f.operating_margin < 0:
        notes.append("Negative operating margin — EBIT below breakeven")

    return SubScore(
        name="Profitability",
        score=min(100.0, max(0.0, score)),
        weight=W.quality_profitability,
        drivers=drivers,
        notes=notes,
    )


def score_balance_sheet(f: EquityFundamentals) -> SubScore:
    """Scores: D/E, current ratio, quick ratio, interest coverage, Altman Z."""
    de_s = _score_metric(f.debt_to_equity, 2.0, _Q.debt_equity_moderate, _Q.debt_equity_safe, reverse=True)
    cr_s = _score_metric(f.current_ratio, 0.5, _Q.current_ratio_adequate, _Q.current_ratio_safe)
    qr_s = _score_metric(f.quick_ratio, 0.3, 1.0, 1.5)
    ic_s = _score_metric(f.interest_coverage, 0.5, _Q.interest_coverage_adequate, _Q.interest_coverage_safe)

    # Altman Z: <1.81 distress, 1.81-2.99 grey, >2.99 safe
    az_s = 50.0
    az_note = None
    if f.altman_z is not None:
        if f.altman_z < 1.81:
            az_s = 5.0
            az_note = f"Altman Z={f.altman_z:.2f} — DISTRESS ZONE (bankruptcy risk)"
        elif f.altman_z < 2.99:
            az_s = 45.0
            az_note = f"Altman Z={f.altman_z:.2f} — grey zone"
        else:
            az_s = 90.0
            az_note = f"Altman Z={f.altman_z:.2f} — safe zone"

    score = de_s * 0.30 + cr_s * 0.20 + qr_s * 0.15 + ic_s * 0.25 + az_s * 0.10
    notes = [az_note] if az_note else []

    if f.debt_to_equity and f.debt_to_equity > 2.0:
        notes.append(f"High leverage D/E={f.debt_to_equity:.1f}x — monitor refinancing risk")

    return SubScore(
        name="Balance Sheet",
        score=min(100.0, max(0.0, score)),
        weight=W.quality_balance_sheet,
        drivers={
            "D/E Ratio": f.debt_to_equity,
            "Current Ratio": f.current_ratio,
            "Quick Ratio": f.quick_ratio,
            "Interest Coverage": f.interest_coverage,
            "Altman Z": f.altman_z,
        },
        notes=notes,
    )


def score_cashflow_quality(f: EquityFundamentals) -> SubScore:
    """Scores: FCF conversion, FCF yield backing, operating CF margin, CapEx intensity."""
    fcf_conv_s = _score_metric(
        f.fcf_to_net_income,
        0.0, _Q.fcf_conversion_good, _Q.fcf_conversion_excellent,
    )
    ocf_m_s = _score_metric(f.operating_cf_margin, 0.0, 0.10, 0.25)
    capex_s = _score_metric(f.capex_intensity, 0.30, 0.15, 0.05, reverse=True)  # lower CapEx intensity better

    score = fcf_conv_s * 0.50 + ocf_m_s * 0.30 + capex_s * 0.20
    notes: List[str] = []
    if f.fcf_to_net_income and f.fcf_to_net_income > 1.0:
        notes.append("FCF > Net Income — earnings quality confirmed by cash")
    if f.fcf_to_net_income and f.fcf_to_net_income < 0.40:
        notes.append("Low FCF conversion — accrual earnings may overstate quality")

    return SubScore(
        name="Cash Flow Quality",
        score=min(100.0, max(0.0, score)),
        weight=W.quality_cashflow,
        drivers={
            "FCF/Net Income": f.fcf_to_net_income,
            "Operating CF Margin": f.operating_cf_margin,
            "CapEx Intensity": f.capex_intensity,
        },
        notes=notes,
    )


def compute_quality_score(f: EquityFundamentals) -> SubScore:
    """Composite quality score = weighted average of three sub-dimensions."""
    prof = score_profitability(f)
    bs = score_balance_sheet(f)
    cf = score_cashflow_quality(f)

    composite = prof.weighted_score + bs.weighted_score + cf.weighted_score
    all_notes = prof.notes + bs.notes + cf.notes

    return SubScore(
        name="Quality",
        score=min(100.0, max(0.0, composite)),
        weight=W.equity_quality,
        drivers={**prof.drivers, **bs.drivers, **cf.drivers},
        signals={
            "Profitability": f"{prof.score:.0f}/100",
            "Balance Sheet": f"{bs.score:.0f}/100",
            "Cash Flow": f"{cf.score:.0f}/100",
        },
        notes=all_notes,
    )
