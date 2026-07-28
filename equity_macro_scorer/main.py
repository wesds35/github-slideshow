"""
Equity & Macro Scoring System — main entry point.

Usage:
    python -m equity_macro_scorer.main equity AAPL MSFT GOOGL
    python -m equity_macro_scorer.main macro US
    python -m equity_macro_scorer.main full AAPL US
"""
from __future__ import annotations
import argparse
import sys
import logging
from typing import List, Optional, Dict

logging.basicConfig(level=logging.WARNING)


# ---- Bundled macro data for key economies ----
# In production: replace with live FRED / Bloomberg / IMF API calls.
MACRO_DATA: Dict[str, dict] = {
    "US": {
        "currency": "USD",
        "gdp_growth_yoy": 0.025,
        "pmi_manufacturing": 49.5,
        "pmi_services": 53.0,
        "unemployment_rate": 0.041,
        "cpi_yoy": 0.033,
        "core_cpi_yoy": 0.034,
        "breakeven_inflation_5y": 0.028,
        "fiscal_deficit_pct_gdp": -0.063,
        "debt_pct_gdp": 1.21,
        "debt_trend_3yr": 0.08,
        "tax_revenue_pct_gdp": 0.175,
        "current_account_pct_gdp": -0.032,
        "fx_reserves_months_imports": 3.2,
        "policy_rate": 0.0525,
        "yield_curve_slope": -0.0005,
        "credit_spread_ig": 0.010,
        "credit_spread_hy": 0.038,
        "m2_growth": 0.02,
        "credit_rating_score": 20,
    },
    "EU": {
        "currency": "EUR",
        "gdp_growth_yoy": 0.008,
        "pmi_manufacturing": 46.0,
        "pmi_services": 51.5,
        "unemployment_rate": 0.060,
        "cpi_yoy": 0.026,
        "core_cpi_yoy": 0.028,
        "fiscal_deficit_pct_gdp": -0.047,
        "debt_pct_gdp": 0.90,
        "debt_trend_3yr": 0.03,
        "current_account_pct_gdp": 0.020,
        "fx_reserves_months_imports": 4.0,
        "policy_rate": 0.040,
        "yield_curve_slope": 0.005,
        "credit_spread_ig": 0.012,
        "credit_spread_hy": 0.045,
        "credit_rating_score": 18,
    },
    "CHINA": {
        "currency": "CNY",
        "gdp_growth_yoy": 0.050,
        "pmi_manufacturing": 51.5,
        "pmi_services": 54.0,
        "unemployment_rate": 0.052,
        "cpi_yoy": 0.003,
        "core_cpi_yoy": 0.006,
        "fiscal_deficit_pct_gdp": -0.065,
        "debt_pct_gdp": 0.85,
        "debt_trend_3yr": 0.12,
        "current_account_pct_gdp": 0.015,
        "fx_reserves_months_imports": 14.0,
        "external_debt_pct_gdp": 0.18,
        "policy_rate": 0.0250,
        "yield_curve_slope": 0.008,
        "credit_rating_score": 16,
        "corruption_index": 42,
        "wgi_governance": -0.3,
    },
    "JAPAN": {
        "currency": "JPY",
        "gdp_growth_yoy": 0.012,
        "pmi_manufacturing": 48.5,
        "pmi_services": 53.0,
        "unemployment_rate": 0.025,
        "cpi_yoy": 0.030,
        "core_cpi_yoy": 0.027,
        "fiscal_deficit_pct_gdp": -0.055,
        "debt_pct_gdp": 2.55,
        "debt_trend_3yr": 0.06,
        "current_account_pct_gdp": 0.035,
        "fx_reserves_months_imports": 13.0,
        "policy_rate": 0.001,
        "yield_curve_slope": 0.007,
        "credit_rating_score": 17,
    },
    "BRAZIL": {
        "currency": "BRL",
        "gdp_growth_yoy": 0.028,
        "pmi_manufacturing": 52.0,
        "pmi_services": 54.5,
        "unemployment_rate": 0.073,
        "cpi_yoy": 0.048,
        "core_cpi_yoy": 0.045,
        "fiscal_deficit_pct_gdp": -0.078,
        "debt_pct_gdp": 0.91,
        "debt_trend_3yr": 0.10,
        "current_account_pct_gdp": -0.028,
        "fx_reserves_months_imports": 12.0,
        "external_debt_pct_gdp": 0.35,
        "fx_change_1yr": -0.12,
        "policy_rate": 0.1050,
        "yield_curve_slope": 0.020,
        "credit_rating_score": 12,
        "corruption_index": 36,
    },
    "INDIA": {
        "currency": "INR",
        "gdp_growth_yoy": 0.065,
        "pmi_manufacturing": 57.0,
        "pmi_services": 61.0,
        "unemployment_rate": 0.085,
        "cpi_yoy": 0.042,
        "core_cpi_yoy": 0.038,
        "fiscal_deficit_pct_gdp": -0.056,
        "debt_pct_gdp": 0.84,
        "debt_trend_3yr": 0.04,
        "current_account_pct_gdp": -0.015,
        "fx_reserves_months_imports": 9.5,
        "external_debt_pct_gdp": 0.19,
        "policy_rate": 0.065,
        "yield_curve_slope": 0.006,
        "credit_rating_score": 14,
        "corruption_index": 39,
    },
}


def run_equity(tickers: List[str], verbose: bool = True) -> list:
    from .data.providers import fetch_equity_fundamentals
    from .equity.scorer import score_equity
    from .reports.generator import print_equity_report, print_comparison_table
    from .risk.tail_risk import compute_tail_risk_metrics

    scores = []
    for ticker in tickers:
        print(f"\n[Fetching data for {ticker}...]")
        try:
            f = fetch_equity_fundamentals(ticker)
        except Exception as e:
            print(f"  Error fetching {ticker}: {e}")
            continue

        score = score_equity(f)
        scores.append(score)

        # Fetch price history for tail risk
        tail_metrics = None
        try:
            import yfinance as yf
            import numpy as np
            hist = yf.Ticker(ticker).history(period="2y")
            if len(hist) > 30:
                returns = hist["Close"].pct_change().dropna().values
                tail_metrics = compute_tail_risk_metrics(returns)
        except Exception:
            pass

        if verbose:
            print_equity_report(score, tail_metrics)

    if len(scores) > 1:
        print_comparison_table(scores)

    return scores


def run_macro(countries: List[str], verbose: bool = True) -> list:
    from .data.providers import fetch_macro_indicators
    from .macro.scorer import score_macro
    from .reports.generator import print_macro_report

    scores = []
    for country in countries:
        overrides = MACRO_DATA.get(country.upper(), {})
        currency = overrides.pop("currency", "")
        ind = fetch_macro_indicators(country.upper(), manual_overrides=overrides)
        ind.currency = currency
        score = score_macro(ind)
        scores.append(score)
        if verbose:
            print_macro_report(score)

    return scores


def run_full(ticker: str, country: str) -> None:
    from .reports.generator import _CONSOLE
    from rich.rule import Rule

    equity_scores = run_equity([ticker], verbose=True)
    macro_scores = run_macro([country], verbose=True)

    if equity_scores and macro_scores:
        eq = equity_scores[0]
        mac = macro_scores[0]
        _CONSOLE.print()
        _CONSOLE.print(Rule("[bold cyan]COMBINED SIGNAL[/bold cyan]"))
        _CONSOLE.print(f"\n[bold]{ticker}[/bold] in macro context of [bold]{country}[/bold]:")
        _CONSOLE.print(f"  Equity composite: [bold]{eq.composite:.1f}[/bold] ({eq.grade.value})")
        _CONSOLE.print(f"  Macro composite:  [bold]{mac.composite:.1f}[/bold] ({mac.grade.value})")
        _CONSOLE.print(f"  Macro regime:     [magenta]{mac.regime.value}[/magenta]")
        eq_bias = mac.asset_bias.get("equities", 0.0)
        if eq_bias > 0.3 and eq.composite >= 60:
            _CONSOLE.print(f"\n  [bold green]✓ Constructive:[/bold green] Favourable macro regime + strong equity fundamentals")
        elif eq_bias < -0.3 and eq.composite >= 60:
            _CONSOLE.print(f"\n  [yellow]⚠ Caution:[/yellow] Strong equity but macro headwinds — reduce position sizing")
        elif eq.composite < 45:
            _CONSOLE.print(f"\n  [red]✗ Avoid:[/red] Weak equity score regardless of macro")
        _CONSOLE.print()


def list_available_countries():
    print("Available countries:")
    for k in MACRO_DATA:
        print(f"  {k}")


def main():
    parser = argparse.ArgumentParser(
        description="Production-grade Equity & Macro Scoring System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m equity_macro_scorer.main equity AAPL MSFT GOOGL
  python -m equity_macro_scorer.main macro US EU CHINA
  python -m equity_macro_scorer.main full AAPL US
  python -m equity_macro_scorer.main countries
        """,
    )
    sub = parser.add_subparsers(dest="command")

    eq_p = sub.add_parser("equity", help="Score one or more equities")
    eq_p.add_argument("tickers", nargs="+", help="Ticker symbols (e.g. AAPL MSFT)")

    mac_p = sub.add_parser("macro", help="Score one or more macro environments")
    mac_p.add_argument("countries", nargs="+", help="Country codes (US, EU, CHINA, JAPAN, BRAZIL, INDIA)")

    full_p = sub.add_parser("full", help="Score an equity within its macro context")
    full_p.add_argument("ticker", help="Equity ticker")
    full_p.add_argument("country", help="Country code")

    sub.add_parser("countries", help="List available country macro datasets")

    args = parser.parse_args()

    if args.command == "equity":
        run_equity(args.tickers)
    elif args.command == "macro":
        run_macro(args.countries)
    elif args.command == "full":
        run_full(args.ticker, args.country)
    elif args.command == "countries":
        list_available_countries()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
