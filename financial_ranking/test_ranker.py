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


class CsvLoadingTests(unittest.TestCase):
    def test_sample_csv_loads_with_missing_cells(self):
        companies = load_companies_from_csv(SAMPLE_CSV)
        self.assertEqual(len(companies), 10)
        jpm = next(c for c in companies if c.ticker == "JPM")
        self.assertNotIn("current_ratio", jpm.metrics)   # blank cell in CSV
        self.assertIn("roe", jpm.metrics)


if __name__ == "__main__":
    unittest.main()
