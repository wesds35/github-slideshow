# Financial Ranking

A weighted scoring algorithm that compares public companies' financial
performance and ranks them on a single comparable 0–100 composite score,
with per-category breakdowns. Pure Python standard library — no
dependencies.

## Quick start

```bash
# Rank the bundled 10-company sample dataset
python -m financial_ranking

# Use a different weight profile
python -m financial_ranking --profile growth_focused

# Rank your own CSV (columns: ticker, name, plus any metric columns)
python -m financial_ranking --csv my_peers.csv

# Rank on LIVE fundamentals pulled from SEC EDGAR (free, no API key)
python -m financial_ranking --edgar AAPL MSFT NVDA JNJ WMT

# Run the tests
python -m unittest financial_ranking.test_ranker
```

## How the algorithm works

1. **Metrics** — each company reports raw metrics across five categories:

   | Category | Metrics (default weights within category) |
   |---|---|
   | Profitability (30%) | ROE 35%, net margin 35%, ROA 30% |
   | Growth (25%) | revenue growth 50%, EPS growth 50% |
   | Financial health (20%) | current ratio 40%, debt/equity 40% (lower = better), interest coverage 20% |
   | Efficiency (15%) | asset turnover 60%, FCF margin 40% |
   | Valuation (10%) | P/E 60%, EV/EBITDA 40% (lower = better) |

2. **Winsorize** — each metric is clamped to its 5th–95th percentile
   across the peer group to tame outliers.
3. **Robust standardization** — values become median/MAD z-scores
   (clamped to ±3), so metrics with different units are comparable and a
   single extreme outlier can't compress everyone else's scores.
4. **Direction** — "lower is better" metrics (debt/equity, P/E,
   EV/EBITDA) have their z-scores flipped so higher always means better.
5. **Weighted roll-up** — metric z-scores combine into category scores,
   and categories into the composite, using the configurable weights.
6. **Missing data** — a company missing a metric isn't penalized
   directly: remaining weights renormalize, and a `data_coverage` figure
   is reported so you can judge how complete the picture is.
7. **Score & rank** — composite z-scores map through the normal CDF onto
   a 0–100 scale (50 = peer average) and companies are ranked descending.

Because scoring is peer-relative, rank companies against a sensible peer
group (same sector/size) for the most meaningful results — a bank's
current ratio and a retailer's asset turnover aren't comparable.

### Custom weights

```python
from financial_ranking import FinancialRanker, load_companies_from_csv, format_report

companies = load_companies_from_csv("financial_ranking/sample_data.csv")
ranker = FinancialRanker(category_weights={
    "profitability": 0.40, "growth": 0.30, "financial_health": 0.15,
    "efficiency": 0.10, "valuation": 0.05,
})
for result in ranker.rank(companies):
    print(result.rank, result.ticker, result.composite_score)
```

Ready-made profiles: `balanced` (default), `growth_focused`,
`value_focused`, `quality_focused` — via
`FinancialRanker.from_profile("growth_focused")`.

## Data source: SEC EDGAR (open, free, up to date)

The best open dataset covering **all** US public companies' financials is
the SEC's own EDGAR XBRL data — official, free, no API key, and updated
as filings are accepted (typically within minutes):

- **Per-company API** (used by `sec_edgar.py`):
  `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` —
  every XBRL-tagged fact from every filing for one company.
- **Bulk download** (all companies, refreshed nightly, ~1 GB):
  `https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip`
- **Ticker → CIK map**: `https://www.sec.gov/files/company_tickers.json`
- **Quarterly Financial Statement Data Sets** (flat files):
  https://www.sec.gov/dera/data/financial-statement-data-sets

Per SEC fair-access policy, send a descriptive `User-Agent` (set
`USER_AGENT` in `sec_edgar.py` to your name/email) and stay under ~10
requests/second.

`sec_edgar.py` derives profitability, growth, health, and efficiency
metrics from each registrant's last two fiscal years of 10-K data.
Valuation metrics (P/E, EV/EBITDA) need market prices, which filings
don't contain — those metrics are simply omitted and the ranker's
missing-data handling takes over. Non-US companies and market data need
other sources (e.g. [SimFin](https://simfin.com/) free tier, the
[S&P 500 financials dataset](https://datahub.io/core/s-and-p-500-companies-financials),
or [Finnhub](https://finnhub.io/)'s free API), but none are as complete
or current as EDGAR for US fundamentals.

## Files

| File | Purpose |
|---|---|
| `ranker.py` | Core algorithm: metrics, weights, robust scoring, ranking |
| `sec_edgar.py` | Live data source: SEC EDGAR XBRL company-facts API |
| `sample_data.csv` | Bundled 10-company sample dataset (illustrative figures) |
| `__main__.py` | CLI entry point |
| `test_ranker.py` | Unit tests (`python -m unittest financial_ranking.test_ranker`) |
