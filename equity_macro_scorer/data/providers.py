"""Data provider layer — fetches fundamentals and macro data from yfinance and FRED-compatible sources."""
from __future__ import annotations
import logging
from typing import Optional, Dict
import numpy as np

from .models import EquityFundamentals, MacroIndicators

logger = logging.getLogger(__name__)


def _safe(val, default=None):
    """Return default if val is None, NaN, or inf."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def fetch_equity_fundamentals(ticker: str) -> EquityFundamentals:
    """Fetch fundamental data for an equity via yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance is required: pip install yfinance")

    t = yf.Ticker(ticker)
    info = t.info or {}

    name = info.get("longName") or info.get("shortName") or ticker
    sector = info.get("sector") or ""
    country = info.get("country") or ""

    # --- Profitability ---
    roe = _safe(info.get("returnOnEquity"))
    roa = _safe(info.get("returnOnAssets"))
    gross_margin = _safe(info.get("grossMargins"))
    operating_margin = _safe(info.get("operatingMargins"))
    net_margin = _safe(info.get("profitMargins"))

    # ROIC = NOPAT / Invested Capital — approximate from available fields
    roic = _safe(info.get("returnOnEquity"))   # fallback; refined below
    ebit = _safe(info.get("ebit"))
    tax_rate = _safe(info.get("effectiveTaxRate"), 0.21)
    total_assets = _safe(info.get("totalAssets"))
    total_current_liabilities = _safe(info.get("totalCurrentLiabilities"))
    total_debt = _safe(info.get("totalDebt"), 0.0)
    market_cap = _safe(info.get("marketCap"))
    if ebit and tax_rate and total_assets and total_current_liabilities:
        nopat = ebit * (1 - tax_rate)
        invested_capital = total_assets - total_current_liabilities
        roic = nopat / invested_capital if invested_capital > 0 else roic

    # --- Balance Sheet ---
    debt_to_equity = _safe(info.get("debtToEquity"))
    if debt_to_equity is not None:
        debt_to_equity /= 100.0   # yfinance returns as percentage
    current_ratio = _safe(info.get("currentRatio"))
    quick_ratio = _safe(info.get("quickRatio"))

    # Interest coverage = EBIT / Interest Expense
    interest_expense = _safe(info.get("interestExpense"))
    interest_coverage = None
    if ebit and interest_expense and interest_expense != 0:
        interest_coverage = abs(ebit / interest_expense)

    # Altman Z-Score (public company version)
    altman_z = _compute_altman_z(info)

    # --- Valuation ---
    pe_ratio = _safe(info.get("trailingPE"))
    forward_pe = _safe(info.get("forwardPE"))
    pb_ratio = _safe(info.get("priceToBook"))
    ps_ratio = _safe(info.get("priceToSalesTrailing12Months"))
    ev_ebitda = _safe(info.get("enterpriseToEbitda"))
    ev_revenue = _safe(info.get("enterpriseToRevenue"))
    dividend_yield = _safe(info.get("dividendYield"))
    peg_ratio = _safe(info.get("pegRatio"))

    # FCF Yield = FCF / Market Cap
    fcf = _safe(info.get("freeCashflow"))
    fcf_yield = None
    if fcf and market_cap and market_cap > 0:
        fcf_yield = fcf / market_cap

    # --- Growth ---
    revenue_growth = _safe(info.get("revenueGrowth"))
    earnings_growth = _safe(info.get("earningsGrowth"))

    # --- Cash Flow Quality ---
    operating_cf = _safe(info.get("operatingCashflow"))
    net_income = _safe(info.get("netIncomeToCommon"))
    revenue = _safe(info.get("totalRevenue"))

    fcf_to_net_income = None
    if fcf and net_income and net_income != 0:
        fcf_to_net_income = fcf / net_income

    capex = _safe(info.get("capitalExpenditures"))
    capex_intensity = None
    if capex and revenue and revenue > 0:
        capex_intensity = abs(capex) / revenue

    operating_cf_margin = None
    if operating_cf and revenue and revenue > 0:
        operating_cf_margin = operating_cf / revenue

    # --- Momentum ---
    hist = _get_price_history(t)
    mom_12m, mom_6m, mom_3m, vs_52w = _compute_momentum(hist)

    beta = _safe(info.get("beta"))
    volatility_1yr = _compute_volatility(hist)

    return EquityFundamentals(
        ticker=ticker.upper(),
        name=name,
        sector=sector,
        country=country,
        roe=roe,
        roa=roa,
        roic=roic,
        gross_margin=gross_margin,
        operating_margin=operating_margin,
        net_margin=net_margin,
        debt_to_equity=debt_to_equity,
        current_ratio=current_ratio,
        quick_ratio=quick_ratio,
        interest_coverage=interest_coverage,
        altman_z=altman_z,
        pe_ratio=pe_ratio,
        forward_pe=forward_pe,
        pb_ratio=pb_ratio,
        ps_ratio=ps_ratio,
        ev_ebitda=ev_ebitda,
        ev_revenue=ev_revenue,
        fcf_yield=fcf_yield,
        dividend_yield=dividend_yield,
        peg_ratio=peg_ratio,
        revenue_growth_3yr=revenue_growth,
        eps_growth_3yr=earnings_growth,
        fcf_to_net_income=fcf_to_net_income,
        capex_intensity=capex_intensity,
        operating_cf_margin=operating_cf_margin,
        momentum_12m=mom_12m,
        momentum_6m=mom_6m,
        momentum_3m=mom_3m,
        price_vs_52w_high=vs_52w,
        beta=beta,
        volatility_1yr=volatility_1yr,
        market_cap=market_cap,
    )


def _get_price_history(ticker_obj) -> Optional[object]:
    try:
        hist = ticker_obj.history(period="13mo")
        return hist if len(hist) > 20 else None
    except Exception:
        return None


def _compute_momentum(hist) -> tuple:
    if hist is None or len(hist) < 20:
        return None, None, None, None
    closes = hist["Close"]
    current = closes.iloc[-1]
    try:
        m12 = (current / closes.iloc[-(252)] - 1) if len(closes) >= 252 else None
    except Exception:
        m12 = None
    try:
        # 12m-1m momentum (skip last month)
        m12 = (closes.iloc[-21] / closes.iloc[min(-252, -len(closes))] - 1) if len(closes) >= 63 else None
    except Exception:
        m12 = None
    try:
        m6 = (current / closes.iloc[-126] - 1) if len(closes) >= 126 else None
    except Exception:
        m6 = None
    try:
        m3 = (current / closes.iloc[-63] - 1) if len(closes) >= 63 else None
    except Exception:
        m3 = None
    try:
        high_52w = closes.rolling(252).max().iloc[-1] if len(closes) >= 252 else closes.max()
        vs_52w = current / high_52w - 1
    except Exception:
        vs_52w = None
    return m12, m6, m3, vs_52w


def _compute_volatility(hist) -> Optional[float]:
    if hist is None or len(hist) < 20:
        return None
    try:
        returns = hist["Close"].pct_change().dropna()
        return float(returns.std() * np.sqrt(252))
    except Exception:
        return None


def _compute_altman_z(info: dict) -> Optional[float]:
    """Altman Z-Score for public companies: Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5"""
    try:
        wc = _safe(info.get("totalCurrentAssets"), 0) - _safe(info.get("totalCurrentLiabilities"), 0)
        ta = _safe(info.get("totalAssets"))
        re = _safe(info.get("retainedEarnings"))
        ebit = _safe(info.get("ebit"))
        mc = _safe(info.get("marketCap"))
        tl = _safe(info.get("totalLiabilities") or info.get("totalDebt"))
        rev = _safe(info.get("totalRevenue"))
        if not all([ta, ta > 0, rev, tl]):
            return None
        x1 = wc / ta
        x2 = (re or 0) / ta
        x3 = (ebit or 0) / ta
        x4 = (mc or 0) / tl if tl > 0 else 0
        x5 = rev / ta
        return 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Macro data — yfinance proxies for key indicators
# ---------------------------------------------------------------------------

_MACRO_PROXIES: Dict[str, Dict] = {
    "US": {
        "yield_10y": "^TNX",
        "yield_2y": "^IRX",
        "sp500": "^GSPC",
        "vix": "^VIX",
        "gold": "GC=F",
        "oil": "CL=F",
        "dxy": "DX-Y.NYB",
    },
}


def fetch_macro_indicators(country: str, manual_overrides: Optional[Dict] = None) -> MacroIndicators:
    """
    Build a MacroIndicators object.

    yfinance doesn't expose full macro databases, so this combines:
    - Hard-coded / manually supplied macro numbers (the primary path)
    - Market-implied signals from yfinance (yield curve, credit spreads via ETF proxies)

    In production, replace with Bloomberg / FRED / IMF / World Bank API calls.
    """
    ind = MacroIndicators(country=country)
    if manual_overrides:
        for k, v in manual_overrides.items():
            if hasattr(ind, k):
                setattr(ind, k, v)

    # Derive real policy rate
    if ind.policy_rate is not None and ind.cpi_yoy is not None:
        ind.real_policy_rate = ind.policy_rate - ind.cpi_yoy

    return ind
