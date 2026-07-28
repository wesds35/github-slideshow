"""Unit tests for the equity scoring subsystem."""
import pytest
from ..data.models import EquityFundamentals, ScoreGrade, RiskLevel
from ..equity.quality import compute_quality_score, score_profitability, score_balance_sheet
from ..equity.value import compute_value_score, estimate_intrinsic_value
from ..equity.growth import compute_growth_score
from ..equity.momentum import compute_momentum_score
from ..equity.scorer import score_equity
from ..equity.risk import compute_factor_exposures, classify_risk


def _make_high_quality() -> EquityFundamentals:
    return EquityFundamentals(
        ticker="HQCO",
        name="High Quality Co",
        sector="Technology",
        country="US",
        roe=0.35, roa=0.18, roic=0.25,
        gross_margin=0.65, operating_margin=0.28, net_margin=0.22,
        debt_to_equity=0.15, current_ratio=3.5, quick_ratio=2.8, interest_coverage=25.0,
        altman_z=4.5,
        pe_ratio=22.0, forward_pe=18.0, pb_ratio=5.5, ev_ebitda=15.0,
        fcf_yield=0.05, dividend_yield=0.015, peg_ratio=1.1,
        revenue_growth_3yr=0.18, eps_growth_3yr=0.22, fcf_growth_3yr=0.15,
        fcf_to_net_income=0.95, capex_intensity=0.04, operating_cf_margin=0.28,
        momentum_12m=0.25, momentum_6m=0.14, momentum_3m=0.06, price_vs_52w_high=-0.03,
        beta=1.0, volatility_1yr=0.22, market_cap=500e9,
    )


def _make_distressed() -> EquityFundamentals:
    return EquityFundamentals(
        ticker="DIST",
        name="Distressed Co",
        sector="Industrials",
        country="US",
        roe=-0.05, roa=-0.02, roic=-0.03,
        gross_margin=0.05, operating_margin=-0.08, net_margin=-0.12,
        debt_to_equity=3.5, current_ratio=0.7, quick_ratio=0.4, interest_coverage=0.8,
        altman_z=1.2,
        pe_ratio=None, forward_pe=None, pb_ratio=0.4, ev_ebitda=None,
        fcf_yield=-0.04, dividend_yield=None,
        revenue_growth_3yr=-0.12, eps_growth_3yr=-0.35, fcf_growth_3yr=None,
        fcf_to_net_income=0.20, capex_intensity=0.18, operating_cf_margin=-0.05,
        momentum_12m=-0.45, momentum_6m=-0.30, momentum_3m=-0.15, price_vs_52w_high=-0.48,
        beta=2.1, volatility_1yr=0.65, market_cap=200e6,
    )


class TestQualityScoring:
    def test_high_quality_scores_above_70(self):
        q = compute_quality_score(_make_high_quality())
        assert q.score >= 70, f"Expected >=70, got {q.score}"

    def test_distressed_scores_below_35(self):
        q = compute_quality_score(_make_distressed())
        assert q.score <= 35, f"Expected <=35, got {q.score}"

    def test_altman_z_distress_flag(self):
        bs = score_balance_sheet(_make_distressed())
        assert any("distress" in n.lower() or "DISTRESS" in n for n in bs.notes)

    def test_profitability_weights_sum_to_one(self):
        # Test score stays in [0, 100]
        q = score_profitability(_make_high_quality())
        assert 0.0 <= q.score <= 100.0

    def test_none_inputs_handled_gracefully(self):
        f = EquityFundamentals(ticker="NULL", name="Null Co")
        q = compute_quality_score(f)
        assert 0.0 <= q.score <= 100.0


class TestValueScoring:
    def test_cheap_stock_scores_high(self):
        f = _make_high_quality()
        f.pe_ratio = 10.0
        f.forward_pe = 9.0
        f.pb_ratio = 1.2
        f.ev_ebitda = 7.0
        f.fcf_yield = 0.08
        v, _, _ = compute_value_score(f)
        assert v.score >= 65, f"Expected >=65, got {v.score}"

    def test_expensive_stock_scores_low(self):
        f = _make_high_quality()
        f.pe_ratio = 80.0
        f.forward_pe = 70.0
        f.pb_ratio = 20.0
        f.ev_ebitda = 60.0
        f.fcf_yield = 0.005
        v, _, _ = compute_value_score(f)
        assert v.score <= 40, f"Expected <=40, got {v.score}"

    def test_intrinsic_value_returns_range(self):
        f = _make_high_quality()
        iv = estimate_intrinsic_value(f)
        assert iv is not None
        bear, bull = iv
        assert bear < bull
        assert bear > 0


class TestGrowthScoring:
    def test_high_growth_scores_above_70(self):
        f = _make_high_quality()
        g = compute_growth_score(f)
        assert g.score >= 65

    def test_negative_growth_scores_below_35(self):
        f = _make_distressed()
        g = compute_growth_score(f)
        assert g.score <= 40


class TestMomentumScoring:
    def test_strong_momentum_scores_high(self):
        f = _make_high_quality()
        m = compute_momentum_score(f)
        assert m.score >= 65

    def test_negative_momentum_scores_low(self):
        f = _make_distressed()
        m = compute_momentum_score(f)
        assert m.score <= 35


class TestEquityScorer:
    def test_high_quality_composite_buy_signal(self):
        s = score_equity(_make_high_quality())
        assert s.composite >= 60
        assert s.grade in (ScoreGrade.BUY, ScoreGrade.STRONG_BUY)

    def test_distressed_composite_sell_signal(self):
        s = score_equity(_make_distressed())
        assert s.composite <= 40
        assert s.grade in (ScoreGrade.SELL, ScoreGrade.STRONG_SELL)

    def test_distressed_risk_high(self):
        s = score_equity(_make_distressed())
        assert s.risk_level in (RiskLevel.HIGH, RiskLevel.VERY_HIGH)

    def test_factor_exposures_populated(self):
        s = score_equity(_make_high_quality())
        assert len(s.factor_exposures) == 7
        for v in s.factor_exposures.values():
            assert -3.0 <= v <= 3.0

    def test_score_in_valid_range(self):
        for f in [_make_high_quality(), _make_distressed()]:
            s = score_equity(f)
            assert 0.0 <= s.composite <= 100.0

    def test_grade_logic(self):
        from ..equity.scorer import _grade
        assert _grade(80) == ScoreGrade.STRONG_BUY
        assert _grade(65) == ScoreGrade.BUY
        assert _grade(50) == ScoreGrade.NEUTRAL
        assert _grade(38) == ScoreGrade.SELL
        assert _grade(20) == ScoreGrade.STRONG_SELL
