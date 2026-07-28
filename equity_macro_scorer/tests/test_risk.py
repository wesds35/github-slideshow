"""Tests for tail risk analytics."""
import numpy as np
import pytest
from ..risk.tail_risk import compute_tail_risk_metrics, stress_scenarios


def _normal_returns(n=500, mean=0.0006, std=0.012, seed=42):
    rng = np.random.default_rng(seed)
    return rng.normal(mean, std, n)


class TestTailRisk:
    def test_returns_all_expected_keys(self):
        r = _normal_returns()
        m = compute_tail_risk_metrics(r)
        assert "sharpe_ratio" in m
        assert "max_drawdown" in m
        assert "var_95_1d" in m
        assert "cvar_95_1d" in m
        assert "skewness" in m

    def test_var_less_than_cvar(self):
        r = _normal_returns()
        m = compute_tail_risk_metrics(r)
        assert m["var_95_1d"] < m["cvar_95_1d"]

    def test_max_drawdown_negative(self):
        r = _normal_returns()
        m = compute_tail_risk_metrics(r)
        assert m["max_drawdown"] < 0

    def test_empty_returns_returns_empty(self):
        m = compute_tail_risk_metrics(np.array([0.01, 0.02]))
        assert m == {}

    def test_sharpe_positive_for_good_returns(self):
        rng = np.random.default_rng(0)
        r = rng.normal(0.002, 0.008, 500)  # strong positive drift
        m = compute_tail_risk_metrics(r)
        assert m["sharpe_ratio"] > 0

    def test_stress_scenarios_all_negative(self):
        ss = stress_scenarios(100.0, 0.25, beta=1.2)
        for name, loss in ss.items():
            assert loss < 0, f"Stress scenario {name!r} should be negative, got {loss}"

    def test_stress_scenarios_high_beta_amplifies(self):
        ss1 = stress_scenarios(100.0, 0.25, beta=1.0)
        ss2 = stress_scenarios(100.0, 0.25, beta=2.0)
        key = "2008 GFC (-50% market)"
        assert ss2[key] < ss1[key]   # more negative
