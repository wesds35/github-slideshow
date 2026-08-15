"""Tests for the weighted financial ranking algorithm (stdlib unittest)."""

import os
import unittest

from financial_ranking.ranker import (
    Company,
    FinancialRanker,
    Metric,
    WEIGHT_PROFILES,
    load_companies_from_csv,
)

SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "sample_data.csv")


def simple_ranker() -> FinancialRanker:
    """Two metrics, one category, no winsorization — easy to reason about."""
    metrics = (
        Metric("roe", "ROE", "profitability", 0.5),
        Metric("net_margin", "Net margin", "profitability", 0.5),
    )
    return FinancialRanker(
        metrics=metrics,
        category_weights={"profitability": 1.0},
        winsor_pcts=(0.0, 1.0),
    )


class RankingBehaviorTests(unittest.TestCase):
    def test_dominant_company_ranks_first(self):
        companies = [
            Company("STRONG", "Strong Co", {"roe": 30.0, "net_margin": 25.0}),
            Company("MID", "Mid Co", {"roe": 15.0, "net_margin": 12.0}),
            Company("WEAK", "Weak Co", {"roe": 2.0, "net_margin": 1.0}),
        ]
        results = simple_ranker().rank(companies)
        self.assertEqual([r.ticker for r in results], ["STRONG", "MID", "WEAK"])
        self.assertEqual([r.rank for r in results], [1, 2, 3])
        self.assertGreater(results[0].composite_score, results[-1].composite_score)

    def test_scores_bounded_0_100(self):
        companies = load_companies_from_csv(SAMPLE_CSV)
        results = FinancialRanker().rank(companies)
        for r in results:
            self.assertGreaterEqual(r.composite_score, 0.0)
            self.assertLessEqual(r.composite_score, 100.0)
            for score in r.category_scores.values():
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 100.0)

    def test_lower_is_better_metric_is_flipped(self):
        metrics = (Metric("debt_to_equity", "D/E", "health", 1.0,
                          higher_is_better=False),)
        ranker = FinancialRanker(metrics=metrics,
                                 category_weights={"health": 1.0},
                                 winsor_pcts=(0.0, 1.0))
        companies = [
            Company("LOWDEBT", "Low Debt", {"debt_to_equity": 0.2}),
            Company("HIGHDEBT", "High Debt", {"debt_to_equity": 3.0}),
        ]
        results = ranker.rank(companies)
        self.assertEqual(results[0].ticker, "LOWDEBT")

    def test_missing_metric_renormalizes_instead_of_penalizing(self):
        # MISSING matches STRONG on ROE and lacks net_margin entirely;
        # renormalization should score it on ROE alone, beating WEAK.
        companies = [
            Company("STRONG", "Strong", {"roe": 30.0, "net_margin": 25.0}),
            Company("MISSING", "Missing", {"roe": 30.0}),
            Company("WEAK", "Weak", {"roe": 5.0, "net_margin": 4.0}),
        ]
        results = simple_ranker().rank(companies)
        by_ticker = {r.ticker: r for r in results}
        self.assertGreater(by_ticker["MISSING"].composite_score,
                           by_ticker["WEAK"].composite_score)
        self.assertAlmostEqual(by_ticker["MISSING"].data_coverage, 0.5)
        self.assertNotIn("net_margin", by_ticker["MISSING"].metric_zscores)

    def test_identical_companies_tie_at_50(self):
        companies = [
            Company("A", "A Co", {"roe": 10.0, "net_margin": 10.0}),
            Company("B", "B Co", {"roe": 10.0, "net_margin": 10.0}),
        ]
        results = simple_ranker().rank(companies)
        for r in results:
            self.assertAlmostEqual(r.composite_score, 50.0)

    def test_outlier_does_not_compress_peer_scores(self):
        # With plain mean/stdev z-scores one extreme outlier compresses
        # everyone else; robust median/MAD scoring keeps them separated.
        companies = [
            Company("OUT", "Outlier", {"roe": 10000.0}),
            Company("A", "A", {"roe": 30.0}),
            Company("B", "B", {"roe": 20.0}),
            Company("C", "C", {"roe": 10.0}),
            Company("D", "D", {"roe": 5.0}),
        ]
        metrics = (Metric("roe", "ROE", "profitability", 1.0),)
        winsorized = FinancialRanker(
            metrics=metrics, category_weights={"profitability": 1.0}
        ).rank(companies)
        by_ticker = {r.ticker: r for r in winsorized}
        spread = by_ticker["A"].composite_score - by_ticker["D"].composite_score
        self.assertGreater(spread, 10.0)
        self.assertEqual(winsorized[0].ticker, "OUT")

    def test_weight_profiles_change_ordering(self):
        companies = [
            Company("GROW", "Grower",
                    {"roe": 5.0, "net_margin": 2.0, "revenue_growth": 80.0,
                     "eps_growth": 90.0}),
            Company("QUAL", "Quality",
                    {"roe": 35.0, "net_margin": 30.0, "revenue_growth": 2.0,
                     "eps_growth": 3.0}),
            Company("MID", "Middle",
                    {"roe": 15.0, "net_margin": 12.0, "revenue_growth": 20.0,
                     "eps_growth": 15.0}),
        ]
        growth = FinancialRanker.from_profile("growth_focused").rank(companies)
        quality = FinancialRanker.from_profile("quality_focused").rank(companies)
        self.assertEqual(growth[0].ticker, "GROW")
        self.assertEqual(quality[0].ticker, "QUAL")

    def test_custom_weights_are_renormalized(self):
        metrics = (Metric("roe", "ROE", "profitability", 1.0),)
        ranker = FinancialRanker(metrics=metrics,
                                 category_weights={"profitability": 7.0})
        self.assertAlmostEqual(ranker.category_weights["profitability"], 1.0)


class ValidationTests(unittest.TestCase):
    def test_rejects_duplicate_tickers(self):
        companies = [
            Company("A", "A", {"roe": 1.0}),
            Company("A", "A again", {"roe": 2.0}),
        ]
        with self.assertRaises(ValueError):
            simple_ranker().rank(companies)

    def test_rejects_single_company(self):
        with self.assertRaises(ValueError):
            simple_ranker().rank([Company("A", "A", {"roe": 1.0})])

    def test_rejects_unknown_profile(self):
        with self.assertRaises(KeyError):
            FinancialRanker.from_profile("yolo")

    def test_rejects_incomplete_category_weights(self):
        with self.assertRaises(ValueError):
            FinancialRanker(category_weights={"profitability": 1.0})

    def test_rejects_negative_weights(self):
        metrics = (Metric("roe", "ROE", "profitability", 1.0),)
        with self.assertRaises(ValueError):
            FinancialRanker(metrics=metrics,
                            category_weights={"profitability": -1.0})

    def test_all_profiles_valid(self):
        for profile in WEIGHT_PROFILES:
            ranker = FinancialRanker.from_profile(profile)
            self.assertAlmostEqual(sum(ranker.category_weights.values()), 1.0)


class MarketDataTests(unittest.TestCase):
    def test_implied_growth_monotonic_in_price(self):
        from financial_ranking.market_data import implied_growth_rate
        cheap = implied_growth_rate(market_cap=1_000e9, fcf=60e9)
        rich = implied_growth_rate(market_cap=3_000e9, fcf=60e9)
        self.assertIsNotNone(cheap)
        self.assertIsNotNone(rich)
        self.assertLess(cheap, rich)

    def test_implied_growth_none_for_negative_fcf(self):
        from financial_ranking.market_data import implied_growth_rate
        self.assertIsNone(implied_growth_rate(market_cap=1e12, fcf=-5e9))

    def test_implied_growth_roundtrip(self):
        # A market cap constructed from a known growth rate should be
        # recovered by the solver.
        from financial_ranking.market_data import implied_growth_rate
        fcf, g, r, tg = 10e9, 0.12, 0.10, 0.025
        pv, cash = 0.0, fcf
        for year in range(1, 11):
            cash = fcf * (1 + g) ** year
            pv += cash / (1 + r) ** year
        pv += (cash * (1 + tg) / (r - tg)) / (1 + r) ** 10
        recovered = implied_growth_rate(pv, fcf)
        self.assertAlmostEqual(recovered, 12.0, places=2)


class EdgarDerivationTests(unittest.TestCase):
    """TTM / acceleration / consistency math on synthetic XBRL periods."""

    @staticmethod
    def _quarters(values_by_end):
        from datetime import date, timedelta
        out = []
        for end_iso, val in values_by_end.items():
            end = date.fromisoformat(end_iso)
            out.append((end - timedelta(days=90), end, val))
        out.sort(key=lambda p: p[1])
        return out

    def test_ttm_adds_stub_and_subtracts_counterpart(self):
        from datetime import date
        from financial_ranking.sec_edgar import _ttm
        periods = self._quarters({
            "2024-03-31": 100.0, "2024-06-30": 110.0,
            "2025-03-31": 130.0, "2025-06-30": 150.0,
        })
        # FY2024 (calendar year) = 450
        periods.append((date(2024, 1, 1), date(2024, 12, 31), 450.0))
        ttm_now, _, as_of = _ttm(periods)
        # 450 + (130-100) + (150-110) = 520
        self.assertAlmostEqual(ttm_now, 520.0)
        self.assertEqual(as_of, date(2025, 6, 30))

    def test_ttm_falls_back_to_fiscal_year(self):
        from datetime import date
        from financial_ranking.sec_edgar import _ttm
        periods = [(date(2024, 1, 1), date(2024, 12, 31), 450.0)]
        ttm_now, ttm_prior, _ = _ttm(periods)
        self.assertAlmostEqual(ttm_now, 450.0)
        self.assertIsNone(ttm_prior)

    def test_acceleration_detects_speedup(self):
        from financial_ranking.sec_edgar import _acceleration
        periods = self._quarters({
            "2024-03-31": 100.0, "2024-06-30": 100.0,
            "2024-09-30": 100.0, "2024-12-31": 100.0,
            "2025-03-31": 110.0, "2025-06-30": 115.0,
            "2025-09-30": 125.0, "2025-12-31": 140.0,
        })
        # YoY growth: 10%, 15%, 25%, 40% -> latest (40%) vs two quarters
        # earlier (15%) = +25pp
        self.assertAlmostEqual(_acceleration(periods), 25.0)

    def test_acceleration_none_without_history(self):
        from financial_ranking.sec_edgar import _acceleration
        periods = self._quarters({"2025-03-31": 100.0, "2025-06-30": 110.0})
        self.assertIsNone(_acceleration(periods))


class CsvLoadingTests(unittest.TestCase):
    def test_sample_csv_loads_with_missing_cells(self):
        companies = load_companies_from_csv(SAMPLE_CSV)
        self.assertEqual(len(companies), 10)
        jpm = next(c for c in companies if c.ticker == "JPM")
        self.assertNotIn("current_ratio", jpm.metrics)   # blank cell in CSV
        self.assertIn("roe", jpm.metrics)


if __name__ == "__main__":
    unittest.main()
