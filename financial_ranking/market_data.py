"""Free market-price lookups used for valuation metrics.

Filings contain no market prices, so valuation metrics (P/E, PEG, FCF
yield, reverse-DCF implied growth) need a quote source. Yahoo Finance's
public chart endpoint serves a delayed quote per ticker with no API key.
Failures are non-fatal: callers treat a missing price as missing data and
the ranker's weight renormalization takes over.
"""

from __future__ import annotations

import json
import sys
import urllib.request

QUOTE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1d&interval=1d"
USER_AGENT = "Mozilla/5.0 (financial-ranking-demo)"


def get_price(ticker: str) -> float | None:
    """Latest market price for a ticker, or None if unavailable."""
    url = QUOTE_URL.format(ticker=ticker.upper())
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
        meta = payload["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        return float(price) if price is not None else None
    except Exception as exc:  # noqa: BLE001 - any failure means "no price"
        print(f"warning: no market price for {ticker}: {exc}", file=sys.stderr)
        return None


def implied_growth_rate(
    market_cap: float,
    fcf: float,
    discount_rate: float = 0.10,
    years: int = 10,
    terminal_growth: float = 0.025,
) -> float | None:
    """Reverse DCF: the constant FCF growth rate the current price implies.

    Solves (by bisection) for g such that the present value of `years` of
    FCF growing at g, plus a Gordon-growth terminal value, equals the
    market cap. Returns g as a percentage, or None when FCF <= 0 or no
    g in [-50%, +100%] reproduces the price.
    """
    if fcf <= 0 or market_cap <= 0:
        return None

    def present_value(g: float) -> float:
        pv = 0.0
        cash = fcf
        for year in range(1, years + 1):
            cash = fcf * (1 + g) ** year
            pv += cash / (1 + discount_rate) ** year
        terminal = cash * (1 + terminal_growth) / (discount_rate - terminal_growth)
        return pv + terminal / (1 + discount_rate) ** years

    lo, hi = -0.5, 1.0
    if not (present_value(lo) <= market_cap <= present_value(hi)):
        return None
    for _ in range(80):
        mid = (lo + hi) / 2
        if present_value(mid) < market_cap:
            lo = mid
        else:
            hi = mid
    return round(100.0 * (lo + hi) / 2, 4)
