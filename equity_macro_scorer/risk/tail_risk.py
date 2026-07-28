"""
Tail risk analytics — VaR, CVaR, max drawdown, Sharpe, Sortino from price history.
"""
from __future__ import annotations
import math
from typing import Optional, Dict
import numpy as np


def compute_tail_risk_metrics(returns: "np.ndarray", confidence: float = 0.95) -> Dict:
    """
    Given a 1D array of daily returns, compute risk metrics.
    returns: numpy array of daily returns (not cumulative)
    confidence: VaR confidence level (default 95%)
    """
    if len(returns) < 20:
        return {}

    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]

    ann = math.sqrt(252)
    rf_daily = 0.045 / 252

    vol = r.std() * ann
    mean_ann = r.mean() * 252
    excess = r - rf_daily

    # VaR (historical simulation)
    var_1d = -np.percentile(r, (1 - confidence) * 100)
    var_ann = var_1d * math.sqrt(252)

    # CVaR / Expected Shortfall
    tail_returns = r[r < -var_1d]
    cvar_1d = -tail_returns.mean() if len(tail_returns) > 0 else var_1d
    cvar_ann = cvar_1d * math.sqrt(252)

    # Max Drawdown
    cumulative = (1 + r).cumprod()
    rolling_max = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - rolling_max) / rolling_max
    max_drawdown = float(drawdowns.min())
    calmar = mean_ann / abs(max_drawdown) if max_drawdown != 0 else None

    # Sharpe
    sharpe = excess.mean() / excess.std() * ann if excess.std() > 0 else None

    # Sortino (downside deviation)
    downside = excess[excess < 0]
    sortino = excess.mean() / downside.std() * ann if len(downside) > 0 and downside.std() > 0 else None

    # Skewness and Kurtosis
    n = len(r)
    mean_r = r.mean()
    std_r = r.std()
    skew = ((r - mean_r) ** 3).mean() / (std_r ** 3) if std_r > 0 else 0
    kurt = ((r - mean_r) ** 4).mean() / (std_r ** 4) - 3 if std_r > 0 else 0

    return {
        "annualised_return": mean_ann,
        "annualised_volatility": vol,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_drawdown,
        "calmar_ratio": calmar,
        f"var_{int(confidence*100)}_1d": var_1d,
        f"cvar_{int(confidence*100)}_1d": cvar_1d,
        f"var_{int(confidence*100)}_ann": var_ann,
        f"cvar_{int(confidence*100)}_ann": cvar_ann,
        "skewness": skew,
        "excess_kurtosis": kurt,
        "observations": n,
    }


def stress_scenarios(
    current_price: float,
    volatility_1yr: float,
    beta: float = 1.0,
) -> Dict[str, float]:
    """
    Parametric stress tests: given equity vol and beta, estimate losses in tail scenarios.
    Returns dict of scenario_name -> estimated_loss_pct.
    """
    scenarios = {
        "2008 GFC (-50% market)": beta * -0.50,
        "2020 COVID (-34% market)": beta * -0.34,
        "2022 Rates Shock (-25% market)": beta * -0.25,
        "3-Sigma Vol Event": -3 * volatility_1yr / math.sqrt(252),
        "5-Sigma Fat Tail": -5 * volatility_1yr / math.sqrt(252),
    }
    return {k: round(v, 4) for k, v in scenarios.items()}
