"""Unit tests for the macro scoring subsystem."""
import pytest
from ..data.models import MacroIndicators, ScoreGrade, MacroRegime
from ..macro.sovereign import score_growth, score_inflation, score_fiscal, score_external, score_monetary
from ..macro.regime import detect_regime, regime_confidence
from ..macro.scorer import score_macro


def _goldilocks() -> MacroIndicators:
    return MacroIndicators(
        country="IDEAL",
        currency="USD",
        gdp_growth_yoy=0.035,
        pmi_manufacturing=55.0,
        pmi_services=57.0,
        unemployment_rate=0.038,
        cpi_yoy=0.020,
        core_cpi_yoy=0.019,
        breakeven_inflation_5y=0.021,
        fiscal_deficit_pct_gdp=-0.025,
        debt_pct_gdp=0.50,
        debt_trend_3yr=-0.02,
        tax_revenue_pct_gdp=0.28,
        current_account_pct_gdp=0.02,
        fx_reserves_months_imports=6.0,
        external_debt_pct_gdp=0.30,
        fx_change_1yr=0.01,
        policy_rate=0.05,
        real_policy_rate=0.03,
        yield_curve_slope=0.015,
        credit_spread_ig=0.008,
        credit_spread_hy=0.030,
        m2_growth=0.06,
    )


def _crisis() -> MacroIndicators:
    return MacroIndicators(
        country="CRISIS",
        currency="CRS",
        gdp_growth_yoy=-0.05,
        pmi_manufacturing=40.0,
        pmi_services=42.0,
        unemployment_rate=0.12,
        cpi_yoy=0.15,
        core_cpi_yoy=0.12,
        fiscal_deficit_pct_gdp=-0.15,
        debt_pct_gdp=1.50,
        debt_trend_3yr=0.25,
        current_account_pct_gdp=-0.10,
        fx_reserves_months_imports=1.5,
        external_debt_pct_gdp=0.80,
        fx_change_1yr=-0.35,
        policy_rate=0.20,
        real_policy_rate=0.05,
        yield_curve_slope=-0.025,
        credit_spread_hy=0.15,
        credit_spread_ig=0.04,
    )


class TestGrowthScoring:
    def test_goldilocks_growth_above_70(self):
        g = score_growth(_goldilocks())
        assert g.score >= 70

    def test_crisis_growth_below_30(self):
        g = score_growth(_crisis())
        assert g.score <= 30

    def test_recession_note_generated(self):
        g = score_growth(_crisis())
        assert any("contraction" in n.lower() or "recession" in n.lower() for n in g.notes)


class TestInflationScoring:
    def test_on_target_inflation_scores_high(self):
        ind = _goldilocks()
        inf = score_inflation(ind)
        assert inf.score >= 80

    def test_runaway_inflation_scores_low(self):
        ind = _crisis()
        inf = score_inflation(ind)
        assert inf.score <= 30

    def test_deflation_generates_note(self):
        ind = _goldilocks()
        ind.cpi_yoy = -0.01
        inf = score_inflation(ind)
        assert any("deflation" in n.lower() for n in inf.notes)


class TestFiscalScoring:
    def test_healthy_fiscal_scores_high(self):
        f = score_fiscal(_goldilocks())
        assert f.score >= 60

    def test_debt_crisis_scores_low(self):
        f = score_fiscal(_crisis())
        assert f.score <= 20

    def test_debt_above_threshold_generates_note(self):
        f = score_fiscal(_crisis())
        assert any("danger" in n.lower() or "above" in n.lower() or "risk" in n.lower() for n in f.notes)


class TestExternalScoring:
    def test_strong_external_scores_high(self):
        e = score_external(_goldilocks())
        assert e.score >= 65

    def test_weak_external_scores_low(self):
        e = score_external(_crisis())
        assert e.score <= 25


class TestMonetaryScoring:
    def test_healthy_monetary_scores_high(self):
        m = score_monetary(_goldilocks())
        assert m.score >= 60

    def test_inverted_curve_generates_note(self):
        m = score_monetary(_crisis())
        assert any("inverted" in n.lower() for n in m.notes)


class TestRegimeDetection:
    def test_goldilocks_regime(self):
        regime, bias = detect_regime(_goldilocks())
        assert regime == MacroRegime.GOLDILOCKS
        assert bias["equities"] > 0

    def test_stagflation_regime(self):
        ind = MacroIndicators(
            country="STAG",
            pmi_manufacturing=44.0,
            gdp_growth_yoy=0.005,
            cpi_yoy=0.09,
            core_cpi_yoy=0.08,
        )
        regime, bias = detect_regime(ind)
        # falling growth, rising inflation
        assert regime == MacroRegime.STAGFLATION
        assert bias["equities"] < 0

    def test_deflationary_bust(self):
        ind = MacroIndicators(
            country="DEFLBUST",
            pmi_manufacturing=43.0,
            gdp_growth_yoy=-0.02,
            cpi_yoy=0.00,
            core_cpi_yoy=-0.005,
        )
        regime, bias = detect_regime(ind)
        assert regime == MacroRegime.DEFLATIONARY_BUST
        assert bias["bonds"] > 0


class TestMacroComposite:
    def test_goldilocks_composite_high(self):
        s = score_macro(_goldilocks())
        assert s.composite >= 65
        assert s.grade in (ScoreGrade.BUY, ScoreGrade.STRONG_BUY)

    def test_crisis_composite_low(self):
        s = score_macro(_crisis())
        assert s.composite <= 30
        assert s.grade in (ScoreGrade.SELL, ScoreGrade.STRONG_SELL)

    def test_crisis_generates_tail_risks(self):
        s = score_macro(_crisis())
        assert len(s.tail_risks) >= 3

    def test_asset_bias_populated(self):
        s = score_macro(_goldilocks())
        assert "equities" in s.asset_bias
        assert "bonds" in s.asset_bias

    def test_score_in_valid_range(self):
        for ind in [_goldilocks(), _crisis()]:
            s = score_macro(ind)
            assert 0.0 <= s.composite <= 100.0
