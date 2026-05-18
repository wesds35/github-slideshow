#!/usr/bin/env python3
"""Game-theory-inspired stock/ETF/country rating tool.

Uses free data sources:
- Yahoo Finance public endpoints (price history, basic quote/news/company profile)
- World Bank public API (GDP growth, population growth)

Example:
  python market_game_theory.py --ticker AAPL --ticker SPY --country USA
"""

from __future__ import annotations

import argparse
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import json
import urllib.parse
import urllib.request
import urllib.error

UA = {"User-Agent": "Mozilla/5.0 (market-game-theory-script)"}
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_QUOTE = "https://query1.finance.yahoo.com/v7/finance/quote"
YAHOO_SEARCH = "https://query1.finance.yahoo.com/v1/finance/search"
YAHOO_PROFILE = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
WORLD_BANK = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"


@dataclass
class TickerAnalysis:
    ticker: str
    game_theory_score: float
    rating: str
    details: dict[str, float]
    notes: list[str]


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def zscore_to_0_100(z: float) -> float:
    return clamp(50 + z * 12.5, 0, 100)


def request_json(url: str, params: dict[str, Any] | None = None) -> Any:
    try:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return {}


def fetch_prices(symbol: str, days: int = 365) -> list[float]:
    period1 = int((datetime.now(timezone.utc) - timedelta(days=days + 20)).timestamp())
    period2 = int(datetime.now(timezone.utc).timestamp())
    payload = request_json(
        YAHOO_CHART.format(symbol=symbol),
        {
            "interval": "1d",
            "period1": period1,
            "period2": period2,
            "events": "history",
        },
    )
    result = payload.get("chart", {}).get("result", [])
    if not result:
        return []
    closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
    return [float(c) for c in closes if c is not None]


def fetch_quote(symbol: str) -> dict[str, Any]:
    payload = request_json(YAHOO_QUOTE, {"symbols": symbol})
    rows = payload.get("quoteResponse", {}).get("result", [])
    return rows[0] if rows else {}


def fetch_profile(symbol: str) -> dict[str, Any]:
    payload = request_json(
        YAHOO_PROFILE.format(symbol=symbol),
        {"modules": "defaultKeyStatistics,financialData,assetProfile"},
    )
    out = payload.get("quoteSummary", {}).get("result", [])
    return out[0] if out else {}


def fetch_news_sentiment(query: str, max_items: int = 12) -> float:
    payload = request_json(YAHOO_SEARCH, {"q": query, "quotesCount": 0, "newsCount": max_items})
    news = payload.get("news", [])
    if not news:
        return 50.0

    positive = {"beat", "upgrade", "growth", "surge", "profit", "strong", "record", "bull"}
    negative = {"miss", "downgrade", "fall", "lawsuit", "probe", "weak", "loss", "bear"}

    score = 0
    n = 0
    for item in news:
        title = (item.get("title") or "").lower()
        if not title:
            continue
        n += 1
        p = sum(word in title for word in positive)
        m = sum(word in title for word in negative)
        score += p - m

    if n == 0:
        return 50.0
    return clamp(50 + (score / n) * 20, 0, 100)


def fetch_world_bank_series(country: str, indicator: str, limit: int = 10) -> list[float]:
    payload = request_json(
        WORLD_BANK.format(country=country, indicator=indicator),
        {"format": "json", "per_page": limit},
    )
    if not isinstance(payload, list) or len(payload) < 2:
        return []
    series = payload[1]
    vals = []
    for row in series:
        v = row.get("value")
        if v is not None:
            vals.append(float(v))
    return vals


def country_macro_score(country: str) -> tuple[float, dict[str, float]]:
    gdp_growth = fetch_world_bank_series(country, "NY.GDP.MKTP.KD.ZG")
    pop_growth = fetch_world_bank_series(country, "SP.POP.GROW")

    gdp_latest = gdp_growth[0] if gdp_growth else 0.0
    gdp_avg = statistics.mean(gdp_growth[:5]) if gdp_growth else 0.0
    pop_latest = pop_growth[0] if pop_growth else 0.0

    gdp_component = clamp(50 + 8 * gdp_latest + 4 * gdp_avg, 0, 100)
    pop_component = clamp(60 + 20 * pop_latest, 0, 100)
    macro = 0.7 * gdp_component + 0.3 * pop_component

    return macro, {
        "gdp_component": round(gdp_component, 2),
        "pop_component": round(pop_component, 2),
        "macro_score": round(macro, 2),
    }


def analyze_ticker(symbol: str, country_macro: float | None = None) -> TickerAnalysis:
    prices = fetch_prices(symbol)
    quote = fetch_quote(symbol)
    profile = fetch_profile(symbol)

    notes: list[str] = []
    if len(prices) < 90:
        notes.append("limited historical data")

    rets = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices)) if prices[i - 1] > 0 and prices[i] > 0]
    mean_ret = statistics.mean(rets) if rets else 0.0
    vol = statistics.pstdev(rets) if len(rets) > 2 else 0.01
    sharpe_like = mean_ret / vol if vol > 0 else 0.0

    momentum_90 = (prices[-1] / prices[-90] - 1) if len(prices) >= 90 else 0.0
    momentum_score = clamp(50 + momentum_90 * 120, 0, 100)
    risk_score = zscore_to_0_100(sharpe_like)

    fin = profile.get("financialData", {})
    stats = profile.get("defaultKeyStatistics", {})
    roe = (fin.get("returnOnEquity") or {}).get("raw", 0.0)
    debt_equity = (fin.get("debtToEquity") or {}).get("raw", 100.0)
    fwd_pe = (stats.get("forwardPE") or {}).get("raw", quote.get("forwardPE", 20.0) or 20.0)

    quality = clamp(50 + roe * 40 - max(debt_equity - 100, 0) * 0.08, 0, 100)
    valuation = clamp(85 - (fwd_pe - 15) * 2.0, 0, 100)

    news_score = fetch_news_sentiment(symbol)

    macro = 50.0 if country_macro is None else country_macro

    # Game-theory style: payoff = alpha*(fundamental + macro) + beta*(momentum + sentiment) - gamma*risk_penalty
    payoff_fundamental = 0.5 * quality + 0.5 * valuation
    strategic_sentiment = 0.6 * momentum_score + 0.4 * news_score
    risk_penalty = 100 - risk_score

    game_score = 0.45 * payoff_fundamental + 0.3 * macro + 0.35 * strategic_sentiment - 0.1 * risk_penalty
    game_score = clamp(game_score, 0, 100)

    if game_score >= 80:
        rating = "Strong Buy"
    elif game_score >= 67:
        rating = "Buy"
    elif game_score >= 52:
        rating = "Hold"
    elif game_score >= 37:
        rating = "Reduce"
    else:
        rating = "Avoid"

    details = {
        "momentum_score": round(momentum_score, 2),
        "risk_score": round(risk_score, 2),
        "quality_score": round(quality, 2),
        "valuation_score": round(valuation, 2),
        "news_score": round(news_score, 2),
        "macro_score": round(macro, 2),
    }

    return TickerAnalysis(symbol, round(game_score, 2), rating, details, notes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Game theory market analyzer for stocks/ETFs and countries")
    parser.add_argument("--ticker", action="append", default=[], help="Ticker symbol (repeatable)")
    parser.add_argument("--country", action="append", default=[], help="World Bank country code, e.g. USA, IND")
    args = parser.parse_args()

    country_scores: dict[str, float] = {}
    if args.country:
        print("=== Country Macro Analysis ===")
        for c in args.country:
            score, details = country_macro_score(c.upper())
            country_scores[c.upper()] = score
            print(f"{c.upper()}: macro_score={score:.2f} details={details}")
        print()

    if args.ticker:
        print("=== Ticker/ETF Analysis ===")
        for t in args.ticker:
            tck = t.upper()
            inferred_country = None
            q = fetch_quote(tck)
            cc = q.get("region") or q.get("market") or q.get("fullExchangeName") or ""
            if cc in country_scores:
                inferred_country = country_scores[cc]
            elif len(country_scores) == 1:
                inferred_country = next(iter(country_scores.values()))

            result = analyze_ticker(tck, inferred_country)
            print(f"{result.ticker}: score={result.game_theory_score:.2f} rating={result.rating}")
            print(f"  components={result.details}")
            if result.notes:
                print(f"  notes={', '.join(result.notes)}")


if __name__ == "__main__":
    main()
