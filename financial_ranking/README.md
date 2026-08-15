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

# Judge each company against its sector peers instead of the whole universe
python -m financial_ranking --edgar AAPL JPM XOM NEE BAC --sector-relative

# Run the tests
python -m unittest financial_ranking.test_ranker
```

## How the algorithm works

1. **Metrics** — each company reports raw metrics across five categories:

   | Category | Metrics (default weights within category) |
   |---|---|
   | Profitability (30%) | ROE 25%, net margin 25%, ROA 15%, 5-year avg ROE 20%, margin volatility 15% (lower = better) |
   | Growth (25%) | revenue growth 40%, EPS growth 25%, revenue acceleration 35% |
   | Financial health (20%) | current ratio 40%, debt/equity 40% (lower = better), interest coverage 20% |
   | Efficiency (15%) | asset turnover 60%, FCF margin 40% |
   | Valuation (10%) | P/E 25%, EV/EBITDA 10%, PEG 20% (all lower = better), FCF yield 25%, actual-minus-implied growth 20% |

   Three metric groups deserve explanation:

   - **Consistency** (`roe_5y_avg`, `margin_volatility`) scores multi-year
     durability, so one great year can't masquerade as a solid company.
   - **Acceleration** (`revenue_acceleration`) is the change in the YoY
     quarterly growth rate — a leading indicator of whether growth is
     speeding up or rolling over.
   - **Growth-adjusted valuation** (`peg_ratio`, `fcf_yield`,
     `growth_vs_implied`) asks whether the price is fair *for this growth
     rate*. `growth_vs_implied` runs a reverse DCF: it solves for the FCF
     growth rate the current market cap implies (10% discount, 10-year
     horizon, 2.5% terminal growth) and reports actual growth minus that.
     Negative = priced for more growth than the company is delivering.

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

### Sector-relative scoring

With `sector_relative=True` (CLI: `--sector-relative`), z-scores are
computed within each company's sector peer group — banks against banks,
utilities against utilities — so structurally different balance sheets
stop distorting cross-sector comparisons. Sectors come from each
registrant's SIC code (EDGAR submissions API) mapped to coarse buckets
(technology, healthcare, financials, energy, utilities, consumer,
industrials, materials, communications), or from an optional `sector` CSV
column. Sectors with fewer than `min_sector_peers` members (default 3)
are pooled and scored against each other. A company's composite then
answers "how strong is it *for its sector*", making cross-sector ranks
comparable on a level footing.

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

`sec_edgar.py` builds **trailing-twelve-month (TTM)** flow metrics by
combining the latest 10-K with 10-Q stub quarters (FY + new quarters −
their year-ago counterparts), so scores reflect the most recent four
quarters instead of a fiscal year that may be nearly a year stale.
Balance-sheet metrics use the latest reported instant from any filing.
Quarterly history also feeds revenue acceleration, and the full annual
history feeds the 5-year consistency metrics.

Market prices come from `market_data.py` (Yahoo Finance's public chart
endpoint — free, no API key, delayed quotes), combined with share counts
from the filings to compute market cap and the valuation metrics. Pass
`--no-price` to skip the lookup; any missing price simply omits those
metrics and the ranker's weight renormalization takes over. Non-US
companies need other sources (e.g. [SimFin](https://simfin.com/) free
tier or [Finnhub](https://finnhub.io/)'s free API), but none are as
complete or current as EDGAR for US fundamentals.

## Files

| File | Purpose |
|---|---|
| `ranker.py` | Core algorithm: metrics, weights, robust scoring, ranking |
| `sec_edgar.py` | Live data source: EDGAR XBRL facts → TTM, acceleration, consistency, valuation |
| `market_data.py` | Free price quotes (Yahoo chart API) and reverse-DCF implied growth |
| `sample_data.csv` | Bundled 10-company sample dataset (illustrative figures) |
| `__main__.py` | CLI entry point |
| `test_ranker.py` | Unit tests (`python -m unittest financial_ranking.test_ranker`) |
