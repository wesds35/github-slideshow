"""
Sovereign macro scoring — IMF/World Bank / ratings-agency style framework.

Dimensions scored:
1. Growth — GDP, PMI, unemployment
2. Inflation — CPI, core CPI, policy credibility
3. Fiscal — deficit/GDP, debt/GDP trend, fiscal space
4. External — current account, FX reserves, external debt, FX stability
5. Monetary — real rate, yield curve, credit spreads, CB credibility
"""
from __future__ import annotations
from typing import List

from ..data.models import MacroIndicators, SubScore
from ..config import MACRO_THRESHOLDS as T, WEIGHTS as W


def _score(val, bad: float, neutral: float, good: float, reverse: bool = False) -> float:
    """Score val between 0 and 100. If reverse=True, lower is better."""
    if val is None:
        return 50.0
    if reverse:
        val, bad, neutral, good = -val, -good, -neutral, -bad
    if val <= bad:
        return 0.0
    if val >= good:
        return 100.0
    if val <= neutral:
        return 50.0 * (val - bad) / (neutral - bad)
    return 50.0 + 50.0 * (val - neutral) / (good - neutral)


def score_growth(ind: MacroIndicators) -> SubScore:
    gdp_s = _score(ind.gdp_growth_yoy, -0.02, T.gdp_growth_moderate, T.gdp_growth_strong)
    pmi_mfg_s = _score(ind.pmi_manufacturing, 44.0, 50.0, 57.0)
    pmi_svc_s = _score(ind.pmi_services, 44.0, 50.0, 57.0)
    unemp_s = _score(ind.unemployment_rate, T.unemployment_high, 0.055, T.unemployment_low, reverse=True)
    ip_s = _score(ind.industrial_production, -0.05, 0.01, 0.04)

    scores = [(gdp_s, 0.35), (pmi_mfg_s, 0.20), (pmi_svc_s, 0.15),
              (unemp_s, 0.20), (ip_s, 0.10)]
    composite = sum(s * w for s, w in scores)

    notes: List[str] = []
    if ind.gdp_growth_yoy and ind.gdp_growth_yoy < 0:
        notes.append("GDP contraction — recessionary environment")
    if ind.pmi_manufacturing and ind.pmi_manufacturing < 46:
        notes.append(f"PMI manufacturing deep contraction at {ind.pmi_manufacturing:.1f}")
    if ind.unemployment_rate and ind.unemployment_rate > T.unemployment_high:
        notes.append(f"Elevated unemployment {ind.unemployment_rate:.1%} — labour market slack")

    return SubScore(
        name="Growth",
        score=min(100.0, max(0.0, composite)),
        weight=W.macro_growth,
        drivers={
            "GDP Growth YoY": ind.gdp_growth_yoy,
            "PMI Manufacturing": ind.pmi_manufacturing,
            "PMI Services": ind.pmi_services,
            "Unemployment Rate": ind.unemployment_rate,
            "Industrial Production": ind.industrial_production,
        },
        notes=notes,
    )


def score_inflation(ind: MacroIndicators) -> SubScore:
    """Higher score = more favourable inflation environment (anchored, on-target)."""
    # Score CPI proximity to 2% target
    cpi = ind.cpi_yoy
    cpi_s = 50.0
    if cpi is not None:
        dist = abs(cpi - T.inflation_target)
        if dist < 0.005:
            cpi_s = 100.0
        elif dist < 0.01:
            cpi_s = 85.0
        elif dist < 0.02:
            cpi_s = 65.0
        elif dist < 0.05:
            cpi_s = 35.0
        else:
            cpi_s = 5.0
        # Extra penalty for runaway inflation
        if cpi > T.inflation_very_high:
            cpi_s = max(0.0, cpi_s - 20)

    core_s = 50.0
    if ind.core_cpi_yoy is not None:
        dist = abs(ind.core_cpi_yoy - T.inflation_target)
        core_s = max(0.0, 100.0 - dist * 2000)  # linear decay

    breakeven_s = 50.0
    if ind.breakeven_inflation_5y is not None:
        dist = abs(ind.breakeven_inflation_5y - T.inflation_target)
        breakeven_s = max(0.0, 100.0 - dist * 1500)

    composite = cpi_s * 0.50 + core_s * 0.35 + breakeven_s * 0.15

    notes: List[str] = []
    if cpi and cpi > T.inflation_very_high:
        notes.append(f"Inflation very high ({cpi:.1%}) — potential monetary credibility crisis")
    if cpi and cpi < 0:
        notes.append("Deflation risk — negative CPI may signal demand weakness")
    if ind.core_cpi_yoy and ind.core_cpi_yoy > T.inflation_high:
        notes.append(f"Core CPI {ind.core_cpi_yoy:.1%} well above target — persistent inflationary pressure")

    return SubScore(
        name="Inflation",
        score=min(100.0, max(0.0, composite)),
        weight=W.macro_inflation,
        drivers={
            "CPI YoY": ind.cpi_yoy,
            "Core CPI YoY": ind.core_cpi_yoy,
            "5yr Breakeven": ind.breakeven_inflation_5y,
            "PPI YoY": ind.ppi_yoy,
        },
        notes=notes,
    )


def score_fiscal(ind: MacroIndicators) -> SubScore:
    """Fiscal sustainability: deficit, debt level, and debt trajectory."""
    deficit_s = _score(ind.fiscal_deficit_pct_gdp, -0.12, -0.03, 0.00)   # negative = deficit
    debt_s = _score(ind.debt_pct_gdp, T.debt_gdp_dangerous, T.debt_gdp_elevated, T.debt_gdp_safe, reverse=True)
    trend_s = _score(ind.debt_trend_3yr, 0.20, 0.05, -0.02, reverse=True)  # rising debt = bad
    tax_s = _score(ind.tax_revenue_pct_gdp, 0.10, 0.20, 0.35)             # fiscal capacity

    composite = deficit_s * 0.35 + debt_s * 0.35 + trend_s * 0.20 + tax_s * 0.10

    notes: List[str] = []
    if ind.fiscal_deficit_pct_gdp and ind.fiscal_deficit_pct_gdp < -0.07:
        notes.append(f"Large fiscal deficit ({ind.fiscal_deficit_pct_gdp:.1%} of GDP) — debt sustainability risk")
    if ind.debt_pct_gdp and ind.debt_pct_gdp > T.debt_gdp_dangerous:
        notes.append(f"Debt/GDP={ind.debt_pct_gdp:.0%} — above danger threshold ({T.debt_gdp_dangerous:.0%})")
    if ind.debt_trend_3yr and ind.debt_trend_3yr > 0.15:
        notes.append(f"Debt/GDP rising rapidly (+{ind.debt_trend_3yr:.0%} over 3yrs) — trajectory unsustainable")

    return SubScore(
        name="Fiscal",
        score=min(100.0, max(0.0, composite)),
        weight=W.macro_fiscal,
        drivers={
            "Fiscal Deficit/GDP": ind.fiscal_deficit_pct_gdp,
            "Debt/GDP": ind.debt_pct_gdp,
            "Debt Trend (3yr)": ind.debt_trend_3yr,
            "Tax Revenue/GDP": ind.tax_revenue_pct_gdp,
        },
        notes=notes,
    )


def score_external(ind: MacroIndicators) -> SubScore:
    """External balance: current account, FX reserves, external debt, currency stability."""
    ca_s = _score(ind.current_account_pct_gdp, T.current_account_deficit_safe * 2,
                  T.current_account_deficit_safe, T.current_account_surplus)
    reserves_s = _score(ind.fx_reserves_months_imports, 1.0, T.fx_reserves_months, 8.0)
    ext_debt_s = _score(ind.external_debt_pct_gdp, 1.50, 0.80, 0.30, reverse=True)
    fx_s = _score(ind.fx_change_1yr, -0.25, -0.05, 0.05)

    composite = ca_s * 0.30 + reserves_s * 0.30 + ext_debt_s * 0.25 + fx_s * 0.15

    notes: List[str] = []
    if ind.current_account_pct_gdp and ind.current_account_pct_gdp < -0.06:
        notes.append(f"Large current account deficit ({ind.current_account_pct_gdp:.1%} GDP) — external financing dependency")
    if ind.fx_reserves_months_imports and ind.fx_reserves_months_imports < T.fx_reserves_months:
        notes.append(f"Low FX reserves ({ind.fx_reserves_months_imports:.1f} months) — BoP vulnerability")
    if ind.fx_change_1yr and ind.fx_change_1yr < -0.15:
        notes.append(f"Currency depreciation {ind.fx_change_1yr:.0%} YoY — imported inflation risk")

    return SubScore(
        name="External",
        score=min(100.0, max(0.0, composite)),
        weight=W.macro_external,
        drivers={
            "Current Account/GDP": ind.current_account_pct_gdp,
            "FX Reserves (months)": ind.fx_reserves_months_imports,
            "External Debt/GDP": ind.external_debt_pct_gdp,
            "FX Change 1yr": ind.fx_change_1yr,
        },
        notes=notes,
    )


def score_monetary(ind: MacroIndicators) -> SubScore:
    """Monetary policy stance, yield curve, and credit conditions."""
    real_rate_s = _score(ind.real_policy_rate, -0.05, 0.00, 0.025)
    # Yield curve: steep positive (>1%) = good; inverted (<0) = recessionary signal
    yc_s = _score(ind.yield_curve_slope, -0.015, 0.005, 0.015)
    # Credit spreads: lower = better
    ig_s = _score(ind.credit_spread_ig, 0.025, 0.012, 0.005, reverse=True)
    hy_s = _score(ind.credit_spread_hy, 0.10, 0.05, 0.03, reverse=True)
    m2_s = _score(ind.m2_growth, -0.02, 0.04, 0.08)

    composite = real_rate_s * 0.30 + yc_s * 0.25 + ig_s * 0.20 + hy_s * 0.15 + m2_s * 0.10

    notes: List[str] = []
    if ind.yield_curve_slope and ind.yield_curve_slope < 0:
        notes.append(f"Inverted yield curve ({ind.yield_curve_slope:.2%}) — recessionary signal within 12-18mo")
    if ind.real_policy_rate and ind.real_policy_rate < -0.03:
        notes.append(f"Deeply negative real rates ({ind.real_policy_rate:.1%}) — financial repression")
    if ind.credit_spread_hy and ind.credit_spread_hy > 0.08:
        notes.append(f"Wide HY spreads ({ind.credit_spread_hy:.0%}) — credit stress / risk-off environment")

    return SubScore(
        name="Monetary",
        score=min(100.0, max(0.0, composite)),
        weight=W.macro_monetary,
        drivers={
            "Real Policy Rate": ind.real_policy_rate,
            "Yield Curve Slope (10y-2y)": ind.yield_curve_slope,
            "IG Credit Spread": ind.credit_spread_ig,
            "HY Credit Spread": ind.credit_spread_hy,
            "M2 Growth": ind.m2_growth,
        },
        notes=notes,
    )
