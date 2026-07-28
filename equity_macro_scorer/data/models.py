"""Core data models for equities and macro environments."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum


class ScoreGrade(str, Enum):
    STRONG_BUY = "Strong Buy"
    BUY = "Buy"
    NEUTRAL = "Neutral"
    SELL = "Sell"
    STRONG_SELL = "Strong Sell"


class MacroRegime(str, Enum):
    GOLDILOCKS = "Goldilocks"
    STAGFLATION = "Stagflation"
    DEFLATIONARY_BUST = "Deflationary Bust"
    TRANSITIONAL = "Transitional"


class RiskLevel(str, Enum):
    VERY_LOW = "Very Low"
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    VERY_HIGH = "Very High"


@dataclass
class EquityFundamentals:
    """Raw fundamental data for a single equity."""
    ticker: str
    name: str = ""
    sector: str = ""
    country: str = ""

    # Profitability
    roe: Optional[float] = None          # Return on Equity
    roa: Optional[float] = None          # Return on Assets
    roic: Optional[float] = None         # Return on Invested Capital
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None

    # Balance sheet
    debt_to_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    interest_coverage: Optional[float] = None
    altman_z: Optional[float] = None

    # Valuation
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    ev_ebitda: Optional[float] = None
    ev_revenue: Optional[float] = None
    fcf_yield: Optional[float] = None
    dividend_yield: Optional[float] = None
    peg_ratio: Optional[float] = None

    # Growth (trailing 3yr CAGR)
    revenue_growth_3yr: Optional[float] = None
    eps_growth_3yr: Optional[float] = None
    fcf_growth_3yr: Optional[float] = None
    dividend_growth_3yr: Optional[float] = None

    # Cash flow quality
    fcf_to_net_income: Optional[float] = None
    capex_intensity: Optional[float] = None     # CapEx / Revenue
    operating_cf_margin: Optional[float] = None

    # Momentum
    momentum_12m: Optional[float] = None        # 12m price return ex-1m
    momentum_6m: Optional[float] = None
    momentum_3m: Optional[float] = None
    price_vs_52w_high: Optional[float] = None

    # Risk
    beta: Optional[float] = None
    volatility_1yr: Optional[float] = None
    market_cap: Optional[float] = None


@dataclass
class MacroIndicators:
    """Macro-economic indicators for a country/region."""
    country: str
    currency: str = ""

    # Growth
    gdp_growth_yoy: Optional[float] = None       # Real GDP growth YoY
    gdp_growth_qoq_ann: Optional[float] = None   # Annualized QoQ
    industrial_production: Optional[float] = None
    pmi_manufacturing: Optional[float] = None    # 50 = neutral
    pmi_services: Optional[float] = None
    unemployment_rate: Optional[float] = None
    consumer_confidence: Optional[float] = None

    # Inflation
    cpi_yoy: Optional[float] = None
    core_cpi_yoy: Optional[float] = None
    pce_yoy: Optional[float] = None
    ppi_yoy: Optional[float] = None
    breakeven_inflation_5y: Optional[float] = None

    # Fiscal
    fiscal_deficit_pct_gdp: Optional[float] = None   # negative = deficit
    debt_pct_gdp: Optional[float] = None
    debt_trend_3yr: Optional[float] = None            # change in debt/GDP
    tax_revenue_pct_gdp: Optional[float] = None

    # Monetary
    policy_rate: Optional[float] = None
    real_policy_rate: Optional[float] = None          # rate - inflation
    yield_curve_slope: Optional[float] = None         # 10y - 2y spread
    credit_spread_ig: Optional[float] = None          # IG OAS
    credit_spread_hy: Optional[float] = None          # HY OAS
    m2_growth: Optional[float] = None

    # External / Balance of Payments
    current_account_pct_gdp: Optional[float] = None
    fx_reserves_months_imports: Optional[float] = None
    external_debt_pct_gdp: Optional[float] = None
    fx_change_1yr: Optional[float] = None             # vs USD

    # Institutional / Governance
    credit_rating_score: Optional[float] = None      # 1-21 (AAA=21, D=1)
    wgi_governance: Optional[float] = None           # World Governance Index (-2.5 to 2.5)
    ease_of_doing_business: Optional[float] = None   # 0-100
    corruption_index: Optional[float] = None         # 0-100 (100=clean)


@dataclass
class SubScore:
    """A scored sub-dimension with breakdown."""
    name: str
    score: float           # 0-100
    weight: float
    drivers: Dict[str, float] = field(default_factory=dict)   # metric -> raw value
    signals: Dict[str, str] = field(default_factory=dict)     # metric -> qualitative signal
    notes: List[str] = field(default_factory=list)

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass
class EquityScore:
    """Full composite equity score."""
    ticker: str
    name: str
    sector: str
    country: str
    composite: float           # 0-100
    grade: ScoreGrade
    quality: SubScore
    value: SubScore
    growth: SubScore
    momentum: SubScore
    risk_level: RiskLevel
    # Aladdin-style factor exposures (z-scores)
    factor_exposures: Dict[str, float] = field(default_factory=dict)
    # Graham margin of safety estimate
    intrinsic_value_range: Optional[tuple] = None
    margin_of_safety: Optional[float] = None
    upside_potential: Optional[float] = None
    current_price: Optional[float] = None
    alerts: List[str] = field(default_factory=list)

    def summary_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "sector": self.sector,
            "composite_score": round(self.composite, 1),
            "grade": self.grade.value,
            "quality": round(self.quality.score, 1),
            "value": round(self.value.score, 1),
            "growth": round(self.growth.score, 1),
            "momentum": round(self.momentum.score, 1),
            "risk": self.risk_level.value,
            "margin_of_safety": f"{self.margin_of_safety:.1%}" if self.margin_of_safety else "N/A",
        }


@dataclass
class MacroScore:
    """Full composite macro score for a sovereign/region."""
    country: str
    currency: str
    composite: float
    grade: ScoreGrade
    regime: MacroRegime
    growth: SubScore
    inflation: SubScore
    fiscal: SubScore
    external: SubScore
    monetary: SubScore
    # Asset class implications
    asset_bias: Dict[str, float] = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)
    tail_risks: List[str] = field(default_factory=list)

    def summary_dict(self) -> dict:
        return {
            "country": self.country,
            "composite_score": round(self.composite, 1),
            "grade": self.grade.value,
            "regime": self.regime.value,
            "growth": round(self.growth.score, 1),
            "inflation": round(self.inflation.score, 1),
            "fiscal": round(self.fiscal.score, 1),
            "external": round(self.external.score, 1),
            "monetary": round(self.monetary.score, 1),
        }
