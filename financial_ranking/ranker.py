"""Weighted financial performance ranking for public companies.

This module implements a peer-relative, weighted scoring algorithm that
turns raw financial metrics into a single comparable composite score
(0-100) per company, plus per-category sub-scores, so companies can be
ranked on overall financial performance.

Algorithm overview
------------------
1.  Each company reports raw metrics (ROE, revenue growth, debt/equity, ...).
2.  Metrics are winsorized across the peer group, then standardized with
    robust z-scores (median/MAD, clamped to +/-3) so metrics with
    different units/scales are comparable and a single extreme outlier
    cannot compress everyone else's scores — a failure mode of plain
    mean/stdev z-scores in small peer groups.
3.  Metrics where lower values are better (e.g. debt/equity, P/E) have
    their z-scores flipped so that "higher = better" holds everywhere.
4.  Metrics roll up into weighted categories (profitability, growth,
    financial health, efficiency, valuation), and categories roll up into
    the composite score using a configurable weight profile.
5.  Missing metrics never punish a company directly: the weights of the
    metrics a company does report are renormalized within each category
    (and categories within the composite), and a data-coverage figure is
    reported alongside the score.
6.  Final composite z-scores are mapped onto a 0-100 scale via the normal
    CDF for readability, and companies are ranked descending.

Only the Python standard library is used.
"""

from __future__ import annotations

import csv
import math
import statistics
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Metric:
    """A single financial metric used in scoring.

    higher_is_better: False for metrics like debt/equity or P/E where a
    lower value indicates stronger performance / cheaper valuation.
    """

    key: str
    label: str
    category: str
    weight: float
    higher_is_better: bool = True


# Default metric set. Weights are *within* a category and are renormalized
# at runtime, so they only need to be meaningful relative to each other.
DEFAULT_METRICS: tuple[Metric, ...] = (
    # Profitability & quality. Point-in-time returns plus multi-year
    # consistency: a durable 20% ROE beats one great year.
    Metric("roe", "Return on equity (%)", "profitability", 0.25),
    Metric("net_margin", "Net profit margin (%)", "profitability", 0.25),
    Metric("roa", "Return on assets (%)", "profitability", 0.15),
    Metric("roe_5y_avg", "5-year average ROE (%)", "profitability", 0.20),
    Metric("margin_volatility", "Net margin volatility, 5y stdev (pp)",
           "profitability", 0.15, higher_is_better=False),
    # Growth. Acceleration (change in YoY growth rate) is a leading
    # indicator: is growth speeding up or slowing down?
    Metric("revenue_growth", "Revenue growth YoY (%)", "growth", 0.40),
    Metric("eps_growth", "EPS growth YoY (%)", "growth", 0.25),
    Metric("revenue_acceleration", "Revenue growth acceleration (pp)",
           "growth", 0.35),
    # Financial health (liquidity & solvency)
    Metric("current_ratio", "Current ratio", "financial_health", 0.40),
    Metric("debt_to_equity", "Debt to equity", "financial_health", 0.40,
           higher_is_better=False),
    Metric("interest_coverage", "Interest coverage (x)", "financial_health", 0.20),
    # Efficiency
    Metric("asset_turnover", "Asset turnover (x)", "efficiency", 0.60),
    Metric("fcf_margin", "Free cash flow margin (%)", "efficiency", 0.40),
    # Valuation: price relative to earnings, cash, and growth. PEG and
    # the reverse-DCF gap ask "is the price fair FOR this growth rate",
    # so fast growers aren't punished by raw multiples alone.
    Metric("pe_ratio", "Price/earnings (TTM)", "valuation", 0.25,
           higher_is_better=False),
    Metric("ev_to_ebitda", "EV/EBITDA", "valuation", 0.10,
           higher_is_better=False),
    Metric("peg_ratio", "PEG (P/E over growth)", "valuation", 0.20,
           higher_is_better=False),
    Metric("fcf_yield", "FCF yield (%)", "valuation", 0.25),
    Metric("growth_vs_implied", "Actual minus DCF-implied growth (pp)",
           "valuation", 0.20),
)

# Default category weights for the composite score. Must sum to 1.0 (they
# are renormalized anyway, so relative sizes are what matters).
DEFAULT_CATEGORY_WEIGHTS: dict[str, float] = {
    "profitability": 0.30,
    "growth": 0.25,
    "financial_health": 0.20,
    "efficiency": 0.15,
    "valuation": 0.10,
}

# Alternative ready-made profiles for different investor priorities.
WEIGHT_PROFILES: dict[str, dict[str, float]] = {
    "balanced": DEFAULT_CATEGORY_WEIGHTS,
    "growth_focused": {
        "profitability": 0.20,
        "growth": 0.45,
        "financial_health": 0.15,
        "efficiency": 0.10,
        "valuation": 0.10,
    },
    "value_focused": {
        "profitability": 0.25,
        "growth": 0.10,
        "financial_health": 0.20,
        "efficiency": 0.15,
        "valuation": 0.30,
    },
    "quality_focused": {
        "profitability": 0.35,
        "growth": 0.10,
        "financial_health": 0.30,
        "efficiency": 0.20,
        "valuation": 0.05,
    },
}


# ---------------------------------------------------------------------------
# Input / output records
# ---------------------------------------------------------------------------


@dataclass
class Company:
    """Raw inputs for one company. Metrics may be partially missing."""

    ticker: str
    name: str
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class ScoredCompany:
    """Ranking output for one company."""

    ticker: str
    name: str
    rank: int
    composite_score: float                 # 0-100
    category_scores: dict[str, float]      # category -> 0-100
    metric_zscores: dict[str, float]       # metric key -> directed z-score
    data_coverage: float                   # fraction of metrics reported


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------


def _winsorize(values: Sequence[float], lower_pct: float, upper_pct: float) -> list[float]:
    """Clamp values to the given percentile bounds to tame outliers."""
    if len(values) < 3:
        return list(values)
    ordered = sorted(values)
    lo = _percentile(ordered, lower_pct)
    hi = _percentile(ordered, upper_pct)
    return [min(max(v, lo), hi) for v in values]


def _percentile(ordered: Sequence[float], pct: float) -> float:
    """Linear-interpolated percentile on an already sorted sequence."""
    if not ordered:
        raise ValueError("empty sequence")
    k = (len(ordered) - 1) * pct
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return ordered[int(k)]
    return ordered[f] * (c - k) + ordered[c] * (k - f)


# 0.6745 scales MAD to match the stdev of a normal distribution, and the
# +/-3 clamp keeps any single extreme value from dominating a category.
_MAD_TO_STDEV = 0.6745
_Z_CLAMP = 3.0


def _zscores(values: Sequence[float]) -> list[float]:
    """Robust standardization via median/MAD, clamped to +/-_Z_CLAMP.

    Falls back to mean/stdev when MAD is zero (e.g. most values identical);
    a zero-variance group maps to all zeros.
    """
    if len(values) < 2:
        return [0.0] * len(values)
    median = statistics.median(values)
    mad = statistics.median(abs(v - median) for v in values)
    if mad > 0:
        zs = [_MAD_TO_STDEV * (v - median) / mad for v in values]
    else:
        mean = statistics.fmean(values)
        stdev = statistics.pstdev(values)
        if stdev == 0:
            return [0.0] * len(values)
        zs = [(v - mean) / stdev for v in values]
    return [max(-_Z_CLAMP, min(_Z_CLAMP, z)) for z in zs]


def _normal_cdf(z: float) -> float:
    """Standard normal CDF via erf (no scipy needed)."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# ---------------------------------------------------------------------------
# Core ranking algorithm
# ---------------------------------------------------------------------------


class FinancialRanker:
    """Ranks a peer group of companies on weighted financial performance.

    Parameters
    ----------
    metrics:
        Metric definitions to score with (defaults to DEFAULT_METRICS).
    category_weights:
        Mapping of category -> weight for the composite. Accepts any
        positive weights; they are renormalized to sum to 1.
    winsor_pcts:
        (lower, upper) percentile bounds used to clamp outliers before
        standardization. Set to (0.0, 1.0) to disable winsorization.
    """

    def __init__(
        self,
        metrics: Iterable[Metric] = DEFAULT_METRICS,
        category_weights: Mapping[str, float] | None = None,
        winsor_pcts: tuple[float, float] = (0.05, 0.95),
    ) -> None:
        self.metrics: list[Metric] = list(metrics)
        if not self.metrics:
            raise ValueError("at least one metric is required")

        raw_weights = dict(category_weights or DEFAULT_CATEGORY_WEIGHTS)
        metric_categories = {m.category for m in self.metrics}
        unknown = set(raw_weights) - metric_categories
        if unknown:
            raise ValueError(f"category weights refer to unknown categories: {sorted(unknown)}")
        missing = metric_categories - set(raw_weights)
        if missing:
            raise ValueError(f"missing category weights for: {sorted(missing)}")
        if any(w < 0 for w in raw_weights.values()):
            raise ValueError("category weights must be non-negative")
        total = sum(raw_weights.values())
        if total <= 0:
            raise ValueError("category weights must sum to a positive value")
        self.category_weights = {k: v / total for k, v in raw_weights.items()}

        lo, hi = winsor_pcts
        if not (0.0 <= lo < hi <= 1.0):
            raise ValueError("winsor_pcts must satisfy 0 <= lower < upper <= 1")
        self.winsor_pcts = winsor_pcts

    @classmethod
    def from_profile(cls, profile: str, **kwargs) -> "FinancialRanker":
        """Build a ranker from a named weight profile (see WEIGHT_PROFILES)."""
        if profile not in WEIGHT_PROFILES:
            raise KeyError(
                f"unknown profile {profile!r}; choose from {sorted(WEIGHT_PROFILES)}"
            )
        return cls(category_weights=WEIGHT_PROFILES[profile], **kwargs)

    # -- pipeline steps ----------------------------------------------------

    def _directed_zscores(self, companies: Sequence[Company]) -> dict[str, dict[str, float]]:
        """Per-metric peer-relative z-scores, flipped so higher = better.

        Returns {metric_key: {ticker: z}} containing only companies that
        reported that metric.
        """
        result: dict[str, dict[str, float]] = {}
        for metric in self.metrics:
            reporters = [c for c in companies if metric.key in c.metrics]
            values = [float(c.metrics[metric.key]) for c in reporters]
            if not reporters:
                continue
            clamped = _winsorize(values, *self.winsor_pcts)
            zs = _zscores(clamped)
            sign = 1.0 if metric.higher_is_better else -1.0
            result[metric.key] = {
                c.ticker: sign * z for c, z in zip(reporters, zs)
            }
        return result

    def _category_score(
        self, company: Company, zscores: dict[str, dict[str, float]], category: str
    ) -> float | None:
        """Weighted mean of the company's directed z-scores in a category.

        Weights renormalize over the metrics the company actually has, so
        missing data reduces coverage rather than dragging the score down.
        Returns None when the company reports nothing in the category.
        """
        total_weight = 0.0
        weighted_sum = 0.0
        for metric in self.metrics:
            if metric.category != category:
                continue
            z = zscores.get(metric.key, {}).get(company.ticker)
            if z is None:
                continue
            weighted_sum += metric.weight * z
            total_weight += metric.weight
        if total_weight == 0:
            return None
        return weighted_sum / total_weight

    # -- public API --------------------------------------------------------

    def rank(self, companies: Sequence[Company]) -> list[ScoredCompany]:
        """Score and rank the peer group, best composite score first.

        Ties on composite score break on data coverage (more complete data
        first), then ticker for determinism.
        """
        if len(companies) < 2:
            raise ValueError("need at least two companies to rank a peer group")
        tickers = [c.ticker for c in companies]
        if len(set(tickers)) != len(tickers):
            raise ValueError("duplicate tickers in peer group")

        zscores = self._directed_zscores(companies)
        categories = list(self.category_weights)

        scored: list[ScoredCompany] = []
        for company in companies:
            cat_z: dict[str, float] = {}
            for category in categories:
                z = self._category_score(company, zscores, category)
                if z is not None:
                    cat_z[category] = z

            # Composite: category weights renormalized over available categories.
            available_weight = sum(self.category_weights[c] for c in cat_z)
            if available_weight > 0:
                composite_z = sum(
                    self.category_weights[c] * z for c, z in cat_z.items()
                ) / available_weight
            else:
                composite_z = 0.0

            reported = sum(1 for m in self.metrics if m.key in company.metrics)
            scored.append(
                ScoredCompany(
                    ticker=company.ticker,
                    name=company.name,
                    rank=0,  # assigned below
                    composite_score=round(100.0 * _normal_cdf(composite_z), 2),
                    category_scores={
                        c: round(100.0 * _normal_cdf(z), 2) for c, z in cat_z.items()
                    },
                    metric_zscores={
                        m.key: round(zscores[m.key][company.ticker], 4)
                        for m in self.metrics
                        if m.key in zscores and company.ticker in zscores[m.key]
                    },
                    data_coverage=round(reported / len(self.metrics), 3),
                )
            )

        scored.sort(
            key=lambda s: (-s.composite_score, -s.data_coverage, s.ticker)
        )
        for position, entry in enumerate(scored, start=1):
            entry.rank = position
        return scored


# ---------------------------------------------------------------------------
# Loading helpers & report formatting
# ---------------------------------------------------------------------------


def load_companies_from_csv(path: str) -> list[Company]:
    """Load companies from a CSV with `ticker`, `name`, and metric columns.

    Empty cells are treated as missing metrics; non-numeric cells raise.
    """
    companies: list[Company] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "ticker" not in reader.fieldnames:
            raise ValueError("CSV must have a header row including 'ticker'")
        for row in reader:
            ticker = (row.get("ticker") or "").strip()
            if not ticker:
                continue
            name = (row.get("name") or ticker).strip()
            metrics: dict[str, float] = {}
            for column, cell in row.items():
                if column in ("ticker", "name") or cell is None:
                    continue
                cell = cell.strip()
                if cell == "":
                    continue
                metrics[column] = float(cell)
            companies.append(Company(ticker=ticker, name=name, metrics=metrics))
    return companies


def format_report(results: Sequence[ScoredCompany], category_weights: Mapping[str, float]) -> str:
    """Render results as a plain-text leaderboard table."""
    categories = list(category_weights)
    header_cats = "  ".join(f"{c[:12]:>12}" for c in categories)
    lines = [
        f"{'#':>3}  {'Ticker':<8}{'Company':<28}{'Score':>7}  {header_cats}  {'Coverage':>8}",
        "-" * (3 + 2 + 8 + 28 + 7 + 2 + 14 * len(categories) + 2 + 8),
    ]
    for entry in results:
        cat_cells = "  ".join(
            f"{entry.category_scores[c]:>12.1f}" if c in entry.category_scores
            else f"{'—':>12}"
            for c in categories
        )
        lines.append(
            f"{entry.rank:>3}  {entry.ticker:<8}{entry.name[:27]:<28}"
            f"{entry.composite_score:>7.1f}  {cat_cells}  {entry.data_coverage:>7.0%}"
        )
    return "\n".join(lines)
