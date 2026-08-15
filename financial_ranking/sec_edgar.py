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

Notes
-----
Market-price-based metrics (P/E, EV/EBITDA) are not in EDGAR filings, so
companies built here simply omit them; the ranker's missing-data handling
renormalizes weights accordingly.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from typing import Any

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


def _get_json(url: str) -> Any:
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


def _annual_values(facts: dict, tag: str, unit_hint: str | None = None) -> dict[int, float]:
    """Extract fiscal-year (10-K, fp=FY) values for a us-gaap tag.

    Returns {fiscal_year: value}, keeping the latest-filed value per year.
    """
    concept = facts.get("facts", {}).get("us-gaap", {}).get(tag)
    if not concept:
        return {}
    units = concept.get("units", {})
    if unit_hint and unit_hint in units:
        entries = units[unit_hint]
    else:
        # Prefer USD, then USD-per-share, then whatever exists.
        for key in ("USD", "USD/shares"):
            if key in units:
                entries = units[key]
                break
        else:
            entries = next(iter(units.values()), [])
    out: dict[int, float] = {}
    for entry in entries:
        if entry.get("form") != "10-K" or entry.get("fp") != "FY":
            continue
        fy = entry.get("fy")
        if fy is None or entry.get("val") is None:
            continue
        out[int(fy)] = float(entry["val"])
    return out


def _first_tag_values(facts: dict, tags: tuple[str, ...]) -> dict[int, float]:
    for tag in tags:
        values = _annual_values(facts, tag)
        if values:
            return values
    return {}


def company_from_edgar(ticker: str, cik: int | None = None) -> Company:
    """Build a ranker Company from a registrant's latest two fiscal years.

    Derives: net_margin, roe, roa, revenue_growth, eps_growth,
    current_ratio, debt_to_equity, asset_turnover, fcf_margin.
    Metrics that cannot be derived from the filing are omitted.
    """
    if cik is None:
        cik = ticker_to_cik(ticker)
    facts = _get_json(COMPANY_FACTS_URL.format(cik=cik))
    name = facts.get("entityName", ticker)

    revenue = _first_tag_values(facts, REVENUE_TAGS)
    net_income = _annual_values(facts, "NetIncomeLoss")
    equity = _annual_values(facts, "StockholdersEquity")
    assets = _annual_values(facts, "Assets")
    liabilities = _annual_values(facts, "Liabilities")
    assets_current = _annual_values(facts, "AssetsCurrent")
    liabilities_current = _annual_values(facts, "LiabilitiesCurrent")
    eps = _first_tag_values(facts, EPS_TAGS)
    op_cash = _annual_values(facts, "NetCashProvidedByUsedInOperatingActivities")
    capex = _annual_values(facts, "PaymentsToAcquirePropertyPlantAndEquipment")

    years = sorted(revenue) or sorted(net_income)
    if not years:
        raise ValueError(f"no annual XBRL data found for {ticker} (CIK {cik})")
    latest = years[-1]
    prior = latest - 1

    metrics: dict[str, float] = {}

    def ratio(numer: dict[int, float], denom: dict[int, float], key: str,
              as_pct: bool = False) -> None:
        n, d = numer.get(latest), denom.get(latest)
        if n is not None and d not in (None, 0):
            metrics[key] = round((n / d) * (100.0 if as_pct else 1.0), 4)

    ratio(net_income, revenue, "net_margin", as_pct=True)
    ratio(net_income, equity, "roe", as_pct=True)
    ratio(net_income, assets, "roa", as_pct=True)
    ratio(assets_current, liabilities_current, "current_ratio")
    ratio(liabilities, equity, "debt_to_equity")
    ratio(revenue, assets, "asset_turnover")

    if latest in revenue and prior in revenue and revenue[prior] != 0:
        metrics["revenue_growth"] = round(
            100.0 * (revenue[latest] - revenue[prior]) / abs(revenue[prior]), 4
        )
    if latest in eps and prior in eps and eps[prior] != 0:
        metrics["eps_growth"] = round(
            100.0 * (eps[latest] - eps[prior]) / abs(eps[prior]), 4
        )
    if latest in op_cash and latest in revenue and revenue[latest] != 0:
        fcf = op_cash[latest] - capex.get(latest, 0.0)
        metrics["fcf_margin"] = round(100.0 * fcf / revenue[latest], 4)

    return Company(ticker=ticker.upper(), name=name, metrics=metrics)


def companies_from_edgar(tickers: list[str], pause_seconds: float = 0.15) -> list[Company]:
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
            companies.append(company_from_edgar(ticker, cik))
        except ValueError as exc:
            print(f"warning: {exc}; skipping", file=sys.stderr)
        time.sleep(pause_seconds)
    return companies
