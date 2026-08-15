"""CLI demo: rank companies from a CSV (or the bundled sample) or from SEC EDGAR.

Usage:
    python -m financial_ranking                          # bundled sample data
    python -m financial_ranking --csv my_peers.csv
    python -m financial_ranking --profile growth_focused
    python -m financial_ranking --edgar AAPL MSFT NVDA   # live SEC data
"""

from __future__ import annotations

import argparse
import os
import sys

from .ranker import FinancialRanker, format_report, load_companies_from_csv

SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "sample_data.csv")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="financial_ranking",
        description="Rank public companies on weighted financial performance.",
    )
    parser.add_argument("--csv", default=SAMPLE_CSV,
                        help="CSV of companies and metrics (default: bundled sample)")
    parser.add_argument("--profile", default="balanced",
                        help="weight profile: balanced, growth_focused, "
                             "value_focused, quality_focused")
    parser.add_argument("--edgar", nargs="+", metavar="TICKER",
                        help="fetch live fundamentals for these tickers from "
                             "SEC EDGAR instead of reading a CSV")
    parser.add_argument("--no-price", action="store_true",
                        help="skip market-price lookups (valuation metrics "
                             "will be omitted)")
    args = parser.parse_args(argv)

    if args.edgar:
        from .sec_edgar import companies_from_edgar
        companies = companies_from_edgar(args.edgar, fetch_price=not args.no_price)
    else:
        companies = load_companies_from_csv(args.csv)

    ranker = FinancialRanker.from_profile(args.profile)
    results = ranker.rank(companies)

    print(f"Weight profile: {args.profile}")
    print(format_report(results, ranker.category_weights))
    return 0


if __name__ == "__main__":
    sys.exit(main())
