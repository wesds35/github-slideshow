"""
Graham/Buffett value screens + DCF-based margin-of-safety estimation.

Implements multi-metric valuation scoring:
- Earnings-based: trailing/forward P/E, PEG
- Asset-based: P/B, EV/Revenue
- Cash-flow-based: EV/EBITDA, FCF Yield
- Income: Dividend Yield

Also computes a simplified two-stage DCF for intrinsic value range.
"""
from __future__ import annotations
import math
from typing import Optional, Tuple, List

from ..data.models import EquityFundamentals, SubScore
from ..config import VALUE_THRESHOLDS as V, WEIGHTS as W


def _score_metric(val: float | None, best: float, neutral: float, worst: float) -> float:
    """Lower is better for multiples (P/E, EV/EBITDA). best < neutral < worst."""
    if val is None or val <= 0:
        return 50.0
    if val <= best:
        return 100.0
    if val <= neutral:
        return 50.0 + 50.0 * (neutral - val) / (neutral - best)
    if val <= worst:
        return 50.0 * (worst - val) / (worst - neutral)
    return 0.0


def _score_yield(val: float | None, floor: float, fair: float, excellent: float) -> float:
    """Higher is better for yields."""
    if val is None or val < 0:
        return 50.0
    if val >= excellent:
        return 100.0
    if val >= fair:
        return 50.0 + 50.0 * (val - fair) / (excellent - fair)
    if val >= floor:
        return 50.0 * (val - floor) / (fair - floor)
    return 0.0


def score_earnings_value(f: EquityFundamentals) -> SubScore:
    """Trailing P/E, forward P/E, PEG."""
    pe_s = _score_metric(f.pe_ratio, V.pe_cheap, V.pe_fair, 40.0)
    fpe_s = _score_metric(f.forward_pe, V.pe_cheap, V.pe_fair, 35.0)
    peg_s = _score_metric(f.peg_ratio, V.peg_cheap, V.peg_fair, 3.0)

    # Forward PE is more informative if available
    if f.forward_pe and f.pe_ratio:
        score = pe_s * 0.30 + fpe_s * 0.50 + peg_s * 0.20
    elif f.forward_pe:
        score = fpe_s * 0.75 + peg_s * 0.25
    else:
        score = pe_s * 0.70 + peg_s * 0.30

    notes: List[str] = []
    if f.pe_ratio and f.pe_ratio > 40:
        notes.append(f"Elevated trailing P/E={f.pe_ratio:.1f}x — requires high growth justification")
    if f.peg_ratio and f.peg_ratio < 1.0:
        notes.append(f"PEG={f.peg_ratio:.2f} below 1 — potential growth at reasonable price (GARP)")

    return SubScore(
        name="Earnings Value",
        score=min(100.0, max(0.0, score)),
        weight=W.value_earnings,
        drivers={"Trailing P/E": f.pe_ratio, "Forward P/E": f.forward_pe, "PEG": f.peg_ratio},
        notes=notes,
    )


def score_asset_value(f: EquityFundamentals) -> SubScore:
    """P/B, P/S, EV/Revenue — asset and revenue-based multiples."""
    pb_s = _score_metric(f.pb_ratio, V.pb_cheap, V.pb_fair, 6.0)
    ps_s = _score_metric(f.ps_ratio, 1.0, 3.0, 7.0)
    evr_s = _score_metric(f.ev_revenue, 1.0, 3.0, 8.0)

    score = pb_s * 0.50 + ps_s * 0.25 + evr_s * 0.25
    notes: List[str] = []
    if f.pb_ratio and f.pb_ratio < 1.0:
        notes.append(f"Trading below book value (P/B={f.pb_ratio:.2f}) — Graham net-net territory or value trap")

    return SubScore(
        name="Asset Value",
        score=min(100.0, max(0.0, score)),
        weight=W.value_assets,
        drivers={"P/B": f.pb_ratio, "P/S": f.ps_ratio, "EV/Revenue": f.ev_revenue},
        notes=notes,
    )


def score_cashflow_value(f: EquityFundamentals) -> SubScore:
    """EV/EBITDA and FCF Yield."""
    ev_ebitda_s = _score_metric(f.ev_ebitda, V.ev_ebitda_cheap, V.ev_ebitda_fair, 25.0)
    fcf_yield_s = _score_yield(f.fcf_yield, 0.01, V.fcf_yield_fair, V.fcf_yield_attractive)

    score = ev_ebitda_s * 0.50 + fcf_yield_s * 0.50
    notes: List[str] = []
    if f.fcf_yield and f.fcf_yield > 0.08:
        notes.append(f"FCF yield of {f.fcf_yield:.1%} — compares favourably to risk-free rate")

    return SubScore(
        name="Cash Flow Value",
        score=min(100.0, max(0.0, score)),
        weight=W.value_cashflow,
        drivers={"EV/EBITDA": f.ev_ebitda, "FCF Yield": f.fcf_yield},
        notes=notes,
    )


def score_dividend_value(f: EquityFundamentals) -> SubScore:
    """Dividend yield scoring."""
    dy_s = _score_yield(
        f.dividend_yield, 0.0,
        V.dividend_yield_attractive / 2,
        V.dividend_yield_attractive,
    )
    notes: List[str] = []
    if f.dividend_yield and f.dividend_yield > 0.06:
        notes.append(f"High dividend yield {f.dividend_yield:.1%} — verify sustainability vs. payout ratio")
    if not f.dividend_yield:
        notes.append("No dividend — value from capital appreciation only")

    return SubScore(
        name="Dividend Value",
        score=min(100.0, max(0.0, dy_s)),
        weight=W.value_dividends,
        drivers={"Dividend Yield": f.dividend_yield},
        notes=notes,
    )


def estimate_intrinsic_value(
    f: EquityFundamentals,
    risk_free_rate: float = 0.045,
    equity_risk_premium: float = 0.055,
    terminal_growth: float = 0.03,
) -> Optional[Tuple[float, float]]:
    """
    Simplified two-stage DCF for intrinsic value range.
    Stage 1: 5-year high-growth, Stage 2: terminal value.
    Returns (bear_value, bull_value) per share, or None if insufficient data.
    """
    if not (f.fcf_yield and f.market_cap and f.eps_growth_3yr is not None):
        return None

    try:
        # Approximate FCF per share from FCF yield and market cap
        shares = 1e6  # normalised — we compute relative range
        fcf_ps = f.fcf_yield  # already normalised as yield

        # Growth assumptions: bear/base/bull
        g_bear = max(terminal_growth, (f.eps_growth_3yr or 0.05) * 0.5)
        g_bull = min(0.30, (f.eps_growth_3yr or 0.10) * 1.5)

        wacc = risk_free_rate + (f.beta or 1.0) * equity_risk_premium

        def dcf(g_stage1: float) -> float:
            pv = 0.0
            for yr in range(1, 6):
                cf = fcf_ps * (1 + g_stage1) ** yr
                pv += cf / (1 + wacc) ** yr
            terminal = fcf_ps * (1 + g_stage1) ** 5 * (1 + terminal_growth) / (wacc - terminal_growth)
            pv += terminal / (1 + wacc) ** 5
            return pv

        bear = dcf(g_bear)
        bull = dcf(g_bull)
        return (bear, bull)
    except Exception:
        return None


def compute_value_score(f: EquityFundamentals, current_price_normalised: float = 1.0) -> tuple:
    """
    Returns (SubScore, intrinsic_value_range, margin_of_safety).
    intrinsic_value_range is relative (bear/bull vs current=1.0).
    """
    earnings = score_earnings_value(f)
    assets = score_asset_value(f)
    cashflow = score_cashflow_value(f)
    dividends = score_dividend_value(f)

    composite = (
        earnings.weighted_score
        + assets.weighted_score
        + cashflow.weighted_score
        + dividends.weighted_score
    )

    all_notes = earnings.notes + assets.notes + cashflow.notes + dividends.notes

    # Margin of safety from DCF
    iv_range = estimate_intrinsic_value(f)
    mos = None
    if iv_range:
        bear, bull = iv_range
        mid = (bear + bull) / 2
        # Relative to current normalised price (1.0 = current)
        mos = mid - 1.0
        if mos > 0.20:
            all_notes.append(f"DCF suggests ~{mos:.0%} upside — potential margin of safety")
        elif mos < -0.20:
            all_notes.append(f"DCF suggests potential {abs(mos):.0%} downside vs. intrinsic value")

    value_score = SubScore(
        name="Value",
        score=min(100.0, max(0.0, composite)),
        weight=W.equity_value,
        drivers={
            **earnings.drivers, **assets.drivers,
            **cashflow.drivers, **dividends.drivers,
        },
        signals={
            "Earnings Value": f"{earnings.score:.0f}/100",
            "Asset Value": f"{assets.score:.0f}/100",
            "CF Value": f"{cashflow.score:.0f}/100",
            "Dividend Value": f"{dividends.score:.0f}/100",
        },
        notes=all_notes,
    )

    return value_score, iv_range, mos
