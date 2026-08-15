"""Fetch company fundamentals from SEC EDGAR's free XBRL APIs.

EDGAR is the most complete open dataset of US public company financials:
every registrant's XBRL-tagged filings are exposed, free, no API key, and
updated as filings arrive (typically within minutes of acceptance).

Endpoints used
--------------
- Per-company facts (all tagged concepts, all years):
    https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json
- Ticker -> CIK mapping:
    https://www.sec.gov/files/company_tickers.json
- Bulk download of ALL companies' facts (~1 GB zip, refreshed nightly):
    https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip

SEC fair-access policy requires a descriptive User-Agent identifying you
(e.g. "Jane Doe jane@example.com") and asks for <= 10 requests/second.

What gets derived
-----------------
- Trailing-twelve-month (TTM) flows built from the latest 10-K plus 10-Q
  stub quarters, so metrics reflect the most recent four quarters rather
  than a fiscal year that may be nearly a year stale.
- Revenue growth (TTM YoY) and revenue *acceleration* (change in the YoY
  growth rate over roughly two quarters) as a leading growth indicator.
- Multi-year consistency: 5-year average ROE and net-margin volatility.
- Valuation vs growth, when a market price is available (market_data):
  TTM P/E, FCF yield, PEG, and the gap between actual growth and the
  growth rate a reverse DCF says the current price implies.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.request
from datetime import date, timedelta

from .market_data import get_price, implied_growth_rate
from .ranker import Company

USER_AGENT = "financial-ranking-demo contact@example.com"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

# Concept fallbacks: companies tag the same idea with different us-gaap tags.
REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
EPS_TAGS = ("EarningsPerShareDiluted", "EarningsPerShareBasic")

_QTR_DAYS = (75, 105)     # duration window that counts as "a quarter"
_YEAR_DAYS = (340, 385)   # duration window that counts as "a fiscal year"
_MATCH_TOLERANCE = timedelta(days=14)


def _get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def ticker_to_cik(ticker: str) -> int:
    """Resolve a ticker symbol to its SEC CIK number."""
    mapping = _get_json(TICKER_MAP_URL)
    wanted = ticker.upper()
    for entry in mapping.values():
        if entry.get("ticker", "").upper() == wanted:
            return int(entry["cik_str"])
    raise KeyError(f"ticker {ticker!r} not found in SEC ticker map")


# ---------------------------------------------------------------------------
# XBRL fact extraction
# ---------------------------------------------------------------------------


def _unit_entries(facts: dict, taxonomy: str, tag: str) -> list[dict]:
    concept = facts.get("facts", {}).get(taxonomy, {}).get(tag)
    if not concept:
        return []
    units = concept.get("units", {})
    for key in ("USD", "USD/shares", "shares"):
        if key in units:
            return units[key]
    return next(iter(units.values()), [])


def _flow_entries(facts: dict, tag: str) -> list[tuple[date, date, float]]:
    """Deduplicated (start, end, value) periods for a duration concept."""
    best: dict[tuple[str, str], tuple[str, float]] = {}
    for entry in _unit_entries(facts, "us-gaap", tag):
        if entry.get("form") not in ("10-K", "10-Q") or entry.get("val") is None:
            continue
        start, end = entry.get("start"), entry.get("end")
        if not start or not end:
            continue
        filed = entry.get("filed", "")
        key = (start, end)
        if key not in best or filed > best[key][0]:
            best[key] = (filed, float(entry["val"]))
    periods = [
        (date.fromisoformat(s), date.fromisoformat(e), v)
        for (s, e), (_, v) in best.items()
    ]
    periods.sort(key=lambda p: p[1])
    return periods


def _first_tag_flows(facts: dict, tags: tuple[str, ...]) -> list[tuple[date, date, float]]:
    for tag in tags:
        flows = _flow_entries(facts, tag)
        if flows:
            return flows
    return []


def _with_duration(periods: list[tuple[date, date, float]],
                   days: tuple[int, int]) -> list[tuple[date, date, float]]:
    lo, hi = days
    return [p for p in periods if lo <= (p[1] - p[0]).days <= hi]


def _latest_instant(facts: dict, tag: str,
                    taxonomy: str = "us-gaap") -> tuple[date, float] | None:
    """Most recent point-in-time (balance sheet) value for a concept."""
    best: tuple[date, str, float] | None = None
    for entry in _unit_entries(facts, taxonomy, tag):
        if entry.get("start") or entry.get("val") is None or not entry.get("end"):
            continue
        end = date.fromisoformat(entry["end"])
        filed = entry.get("filed", "")
        if best is None or (end, filed) > (best[0], best[1]):
            best = (end, filed, float(entry["val"]))
    return (best[0], best[2]) if best else None


def _find_near(periods: list[tuple[date, date, float]], end: date) -> float | None:
    """Value of the period whose end date is within tolerance of `end`."""
    for _, e, v in periods:
        if abs(e - end) <= _MATCH_TOLERANCE:
            return v
    return None


# ---------------------------------------------------------------------------
# TTM, growth, acceleration, consistency
# ---------------------------------------------------------------------------


def _ttm(periods: list[tuple[date, date, float]]) -> tuple[float | None, float | None, date | None]:
    """(ttm_now, ttm_one_year_ago, as_of) built as FY + stub quarters.

    TTM_now = latest fiscal year + quarters reported after the FY end
    minus their year-ago counterparts. Falls back to the plain fiscal-year
    value when stub counterparts are missing. TTM_year_ago is the same
    construction shifted one year (used for TTM YoY growth).
    """
    annuals = _with_duration(periods, _YEAR_DAYS)
    quarters = _with_duration(periods, _QTR_DAYS)
    if not annuals:
        return None, None, None

    def build(fy_end: date, fy_val: float) -> tuple[float, date]:
        stubs = [q for q in quarters if q[1] > fy_end]
        total, as_of = fy_val, fy_end
        for _, q_end, q_val in stubs:
            counterpart = _find_near(quarters, q_end - timedelta(days=365))
            if counterpart is None:
                continue
            total += q_val - counterpart
            as_of = max(as_of, q_end)
        return total, as_of

    fy_start, fy_end, fy_val = annuals[-1]
    ttm_now, as_of = build(fy_end, fy_val)

    ttm_prior: float | None = None
    prior_val = _find_near(annuals, fy_end - timedelta(days=365))
    if prior_val is not None:
        # Shift the same stub construction back one year.
        prior_end = fy_end - timedelta(days=365)
        total = prior_val
        for _, q_end, q_val in [q for q in quarters if q[1] > fy_end]:
            year_ago = _find_near(quarters, q_end - timedelta(days=365))
            two_years_ago = _find_near(quarters, q_end - timedelta(days=730))
            if year_ago is None or two_years_ago is None:
                continue
            total += year_ago - two_years_ago
        ttm_prior = total
    return ttm_now, ttm_prior, as_of


def _growth_pct(now: float | None, prior: float | None) -> float | None:
    if now is None or prior in (None, 0):
        return None
    return round(100.0 * (now - prior) / abs(prior), 4)


def _acceleration(periods: list[tuple[date, date, float]]) -> float | None:
    """Change in quarterly YoY growth (pp): latest vs ~2 quarters earlier."""
    quarters = _with_duration(periods, _QTR_DAYS)
    growths: list[tuple[date, float]] = []
    for _, end, val in quarters:
        year_ago = _find_near(quarters, end - timedelta(days=365))
        if year_ago not in (None, 0):
            growths.append((end, 100.0 * (val - year_ago) / abs(year_ago)))
    if len(growths) < 2:
        return None
    latest_end, latest_growth = growths[-1]
    earlier = [g for g in growths if g[0] <= latest_end - timedelta(days=150)]
    if not earlier:
        return None
    return round(latest_growth - earlier[-1][1], 4)


def _annual_series(periods: list[tuple[date, date, float]]) -> list[tuple[date, float]]:
    return [(end, val) for _, end, val in _with_duration(periods, _YEAR_DAYS)]


def _consistency(revenue: list[tuple[date, date, float]],
                 net_income: list[tuple[date, date, float]],
                 facts: dict) -> dict[str, float]:
    """5-year average ROE and net-margin volatility from annual history."""
    out: dict[str, float] = {}
    ni_by_end = dict(_annual_series(net_income))
    rev_by_end = dict(_annual_series(revenue))

    equity_periods: dict[date, float] = {}
    for entry in _unit_entries(facts, "us-gaap", "StockholdersEquity"):
        if entry.get("val") is None or not entry.get("end") or entry.get("start"):
            continue
        equity_periods[date.fromisoformat(entry["end"])] = float(entry["val"])

    def near(mapping: dict[date, float], when: date) -> float | None:
        for d, v in mapping.items():
            if abs(d - when) <= _MATCH_TOLERANCE:
                return v
        return None

    roes, margins = [], []
    for end in sorted(ni_by_end)[-5:]:
        ni = ni_by_end[end]
        eq = near(equity_periods, end)
        if eq not in (None, 0):
            roes.append(100.0 * ni / eq)
        rev = near(rev_by_end, end)
        if rev not in (None, 0):
            margins.append(100.0 * ni / rev)
    if len(roes) >= 3:
        out["roe_5y_avg"] = round(statistics.fmean(roes), 4)
    if len(margins) >= 3:
        out["margin_volatility"] = round(statistics.pstdev(margins), 4)
    return out


def _shares_outstanding(facts: dict) -> float | None:
    """Share count with fallbacks — not every registrant tags the dei concept."""
    for taxonomy, tag in (
        ("dei", "EntityCommonStockSharesOutstanding"),
        ("us-gaap", "CommonStockSharesOutstanding"),
        ("us-gaap", "CommonStockSharesIssued"),
    ):
        instant = _latest_instant(facts, tag, taxonomy=taxonomy)
        if instant and instant[1] > 0:
            return instant[1]
    # Last resort: latest reported weighted-average diluted share count
    # (a duration concept, so instants above never match it).
    flows = _flow_entries(facts, "WeightedAverageNumberOfDilutedSharesOutstanding")
    if flows:
        return flows[-1][2]
    return None


# ---------------------------------------------------------------------------
# Company assembly
# ---------------------------------------------------------------------------


def company_from_edgar(ticker: str, cik: int | None = None,
                       fetch_price: bool = True) -> Company:
    """Build a ranker Company from a registrant's XBRL facts.

    Flow metrics use trailing-twelve-month values (10-K plus 10-Q stubs);
    balance-sheet metrics use the latest reported instant. Valuation
    metrics are added when a market price is available and are omitted
    otherwise; anything that cannot be derived is simply left out.
    """
    if cik is None:
        cik = ticker_to_cik(ticker)
    facts = _get_json(COMPANY_FACTS_URL.format(cik=cik))
    name = facts.get("entityName", ticker)

    revenue = _first_tag_flows(facts, REVENUE_TAGS)
    net_income = _flow_entries(facts, "NetIncomeLoss")
    eps = _first_tag_flows(facts, EPS_TAGS)
    op_cash = _flow_entries(facts, "NetCashProvidedByUsedInOperatingActivities")
    capex = _flow_entries(facts, "PaymentsToAcquirePropertyPlantAndEquipment")

    rev_ttm, rev_ttm_prior, _ = _ttm(revenue)
    ni_ttm, _, _ = _ttm(net_income)
    ocf_ttm, _, _ = _ttm(op_cash)
    capex_ttm, _, _ = _ttm(capex)
    eps_annual = _annual_series(eps)

    if rev_ttm is None and ni_ttm is None:
        raise ValueError(f"no annual XBRL data found for {ticker} (CIK {cik})")

    equity = _latest_instant(facts, "StockholdersEquity")
    assets = _latest_instant(facts, "Assets")
    liabilities = _latest_instant(facts, "Liabilities")
    assets_current = _latest_instant(facts, "AssetsCurrent")
    liabilities_current = _latest_instant(facts, "LiabilitiesCurrent")

    metrics: dict[str, float] = {}

    def ratio(numer: float | None, denom: tuple[date, float] | None, key: str,
              as_pct: bool = False) -> None:
        if numer is None or denom is None or denom[1] == 0:
            return
        metrics[key] = round((numer / denom[1]) * (100.0 if as_pct else 1.0), 4)

    if rev_ttm not in (None, 0) and ni_ttm is not None:
        metrics["net_margin"] = round(100.0 * ni_ttm / rev_ttm, 4)
    ratio(ni_ttm, equity, "roe", as_pct=True)
    ratio(ni_ttm, assets, "roa", as_pct=True)
    ratio(rev_ttm, assets, "asset_turnover")
    if assets_current and liabilities_current and liabilities_current[1] != 0:
        metrics["current_ratio"] = round(assets_current[1] / liabilities_current[1], 4)
    if liabilities and equity and equity[1] != 0:
        metrics["debt_to_equity"] = round(liabilities[1] / equity[1], 4)

    growth = _growth_pct(rev_ttm, rev_ttm_prior)
    if growth is not None:
        metrics["revenue_growth"] = growth
    accel = _acceleration(revenue)
    if accel is not None:
        metrics["revenue_acceleration"] = accel
    if len(eps_annual) >= 2 and eps_annual[-2][1] != 0:
        metrics["eps_growth"] = round(
            100.0 * (eps_annual[-1][1] - eps_annual[-2][1]) / abs(eps_annual[-2][1]), 4
        )

    fcf_ttm = None
    if ocf_ttm is not None:
        fcf_ttm = ocf_ttm - (capex_ttm or 0.0)
        if rev_ttm not in (None, 0):
            metrics["fcf_margin"] = round(100.0 * fcf_ttm / rev_ttm, 4)

    metrics.update(_consistency(revenue, net_income, facts))

    if fetch_price:
        price = get_price(ticker)
        shares = _shares_outstanding(facts)
        if price is not None and shares:
            market_cap = price * shares
            if ni_ttm is not None and ni_ttm > 0:
                pe = market_cap / ni_ttm
                metrics["pe_ratio"] = round(pe, 4)
                if growth is not None and growth > 0:
                    metrics["peg_ratio"] = round(pe / growth, 4)
            if fcf_ttm is not None:
                metrics["fcf_yield"] = round(100.0 * fcf_ttm / market_cap, 4)
                implied = implied_growth_rate(market_cap, fcf_ttm)
                if implied is not None and growth is not None:
                    metrics["growth_vs_implied"] = round(growth - implied, 4)

    return Company(ticker=ticker.upper(), name=name, metrics=metrics)


def companies_from_edgar(tickers: list[str], pause_seconds: float = 0.15,
                         fetch_price: bool = True) -> list[Company]:
    """Fetch a peer group from EDGAR, pacing requests per SEC policy.

    Tickers that cannot be resolved or have no derivable annual data (e.g.
    freshly reorganized registrants with a new CIK and no 10-K yet) are
    skipped with a warning on stderr instead of failing the whole batch.
    """
    mapping = _get_json(TICKER_MAP_URL)
    by_ticker = {e["ticker"].upper(): int(e["cik_str"]) for e in mapping.values()}
    companies: list[Company] = []
    for ticker in tickers:
        cik = by_ticker.get(ticker.upper())
        if cik is None:
            print(f"warning: ticker {ticker!r} not in SEC ticker map; skipping",
                  file=sys.stderr)
            continue
        try:
            companies.append(company_from_edgar(ticker, cik, fetch_price=fetch_price))
        except ValueError as exc:
            print(f"warning: {exc}; skipping", file=sys.stderr)
        time.sleep(pause_seconds)
    return companies
