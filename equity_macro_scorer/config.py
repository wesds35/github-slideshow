"""Global configuration, thresholds, and scoring weights."""
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class QualityThresholds:
    roe_excellent: float = 0.20       # >20% = excellent
    roe_good: float = 0.15
    roic_excellent: float = 0.15
    roic_good: float = 0.10
    gross_margin_excellent: float = 0.40
    gross_margin_good: float = 0.25
    operating_margin_excellent: float = 0.20
    operating_margin_good: float = 0.10
    debt_equity_safe: float = 0.50    # <50% = safe
    debt_equity_moderate: float = 1.0
    current_ratio_safe: float = 2.0
    current_ratio_adequate: float = 1.5
    interest_coverage_safe: float = 5.0
    interest_coverage_adequate: float = 3.0
    fcf_conversion_excellent: float = 0.85  # FCF/Net Income
    fcf_conversion_good: float = 0.65


@dataclass
class ValueThresholds:
    pe_cheap: float = 15.0
    pe_fair: float = 22.0
    pb_cheap: float = 1.5
    pb_fair: float = 3.0
    ev_ebitda_cheap: float = 8.0
    ev_ebitda_fair: float = 14.0
    fcf_yield_attractive: float = 0.06   # >6% = attractive
    fcf_yield_fair: float = 0.04
    dividend_yield_attractive: float = 0.04
    peg_cheap: float = 1.0
    peg_fair: float = 1.5


@dataclass
class GrowthThresholds:
    revenue_growth_excellent: float = 0.20
    revenue_growth_good: float = 0.10
    eps_growth_excellent: float = 0.20
    eps_growth_good: float = 0.10
    fcf_growth_excellent: float = 0.15
    fcf_growth_good: float = 0.08


@dataclass
class MacroThresholds:
    gdp_growth_strong: float = 0.03      # >3% real GDP = strong
    gdp_growth_moderate: float = 0.015
    inflation_target: float = 0.02
    inflation_high: float = 0.04
    inflation_very_high: float = 0.07
    unemployment_low: float = 0.045
    unemployment_high: float = 0.07
    current_account_surplus: float = 0.02   # CA/GDP
    current_account_deficit_safe: float = -0.03
    debt_gdp_safe: float = 0.60
    debt_gdp_elevated: float = 0.90
    debt_gdp_dangerous: float = 1.20
    fx_reserves_months: float = 3.0         # months of imports


@dataclass
class ScoringWeights:
    # Equity composite weights
    equity_quality: float = 0.35
    equity_value: float = 0.30
    equity_growth: float = 0.20
    equity_momentum: float = 0.15

    # Quality sub-weights
    quality_profitability: float = 0.40
    quality_balance_sheet: float = 0.35
    quality_cashflow: float = 0.25

    # Value sub-weights
    value_earnings: float = 0.35
    value_assets: float = 0.25
    value_cashflow: float = 0.25
    value_dividends: float = 0.15

    # Macro composite weights
    macro_growth: float = 0.30
    macro_inflation: float = 0.20
    macro_fiscal: float = 0.20
    macro_external: float = 0.15
    macro_monetary: float = 0.15

    def validate(self) -> None:
        equity_sum = self.equity_quality + self.equity_value + self.equity_growth + self.equity_momentum
        assert abs(equity_sum - 1.0) < 1e-6, f"Equity weights must sum to 1.0, got {equity_sum}"
        macro_sum = self.macro_growth + self.macro_inflation + self.macro_fiscal + self.macro_external + self.macro_monetary
        assert abs(macro_sum - 1.0) < 1e-6, f"Macro weights must sum to 1.0, got {macro_sum}"


# Factor risk model parameters (Fama-French 5 + Momentum + Quality)
FACTOR_NAMES = ["Market", "Size", "Value", "Profitability", "Investment", "Momentum", "LowVol"]

# Dalio All-Weather regime matrix: (Growth, Inflation) -> asset class expectations
REGIME_MATRIX = {
    ("rising", "rising"):   {"label": "Goldilocks",        "equity_bias": +0.7, "bond_bias": -0.2, "gold_bias": +0.2, "commodities_bias": +0.5},
    ("rising", "falling"):  {"label": "Goldilocks",        "equity_bias": +1.0, "bond_bias": +0.5, "gold_bias": -0.3, "commodities_bias": -0.2},
    ("falling", "rising"):  {"label": "Stagflation",       "equity_bias": -0.8, "bond_bias": -0.5, "gold_bias": +1.0, "commodities_bias": +0.8},
    ("falling", "falling"): {"label": "Deflationary Bust", "equity_bias": -0.5, "bond_bias": +1.0, "gold_bias": +0.2, "commodities_bias": -0.5},
}

QUALITY_THRESHOLDS = QualityThresholds()
VALUE_THRESHOLDS = ValueThresholds()
GROWTH_THRESHOLDS = GrowthThresholds()
MACRO_THRESHOLDS = MacroThresholds()
WEIGHTS = ScoringWeights()
WEIGHTS.validate()
