"""
Rich terminal report generator — Bloomberg-terminal-style output.
Produces structured, coloured, multi-panel reports for equity and macro scores.
"""
from __future__ import annotations
from typing import List, Optional, Dict
import math

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.columns import Columns
    from rich.text import Text
    from rich.rule import Rule
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from ..data.models import EquityScore, MacroScore, ScoreGrade, RiskLevel


_CONSOLE = Console()

_GRADE_STYLE = {
    ScoreGrade.STRONG_BUY:  ("bold green",  "███ STRONG BUY"),
    ScoreGrade.BUY:         ("green",        " ██ BUY"),
    ScoreGrade.NEUTRAL:     ("yellow",       "  █ NEUTRAL"),
    ScoreGrade.SELL:        ("red",          " ██ SELL"),
    ScoreGrade.STRONG_SELL: ("bold red",     "███ STRONG SELL"),
}

_RISK_STYLE = {
    RiskLevel.VERY_LOW:  "bold green",
    RiskLevel.LOW:       "green",
    RiskLevel.MODERATE:  "yellow",
    RiskLevel.HIGH:      "bold red",
    RiskLevel.VERY_HIGH: "bold red on white",
}


def _bar(score: float, width: int = 20) -> str:
    filled = int(round(score / 100 * width))
    return "█" * filled + "░" * (width - filled)


def _score_colour(score: float) -> str:
    if score >= 70:
        return "bold green"
    if score >= 55:
        return "green"
    if score >= 45:
        return "yellow"
    if score >= 30:
        return "red"
    return "bold red"


def _fmt(val, fmt=".2f", suffix="") -> str:
    if val is None:
        return "[dim]N/A[/dim]"
    try:
        return f"{val:{fmt}}{suffix}"
    except Exception:
        return str(val)


def _pct(val) -> str:
    return _fmt(val, ".1%") if val is not None else "[dim]N/A[/dim]"


def print_equity_report(score: EquityScore, tail_metrics: Optional[Dict] = None) -> None:
    if not HAS_RICH:
        _plain_equity_report(score)
        return

    c = _CONSOLE
    grade_style, grade_label = _GRADE_STYLE.get(score.grade, ("white", score.grade.value))

    c.print()
    c.print(Rule(f"[bold cyan]EQUITY ANALYSIS — {score.ticker} | {score.name}[/bold cyan]"))
    c.print()

    # --- Header panel ---
    header = Table.grid(expand=True)
    header.add_column()
    header.add_column(justify="right")
    header.add_row(
        f"[bold]{score.ticker}[/bold]  [dim]{score.sector} | {score.country}[/dim]",
        f"[{grade_style}]{grade_label}[/{grade_style}]",
    )
    if score.current_price:
        mos_str = f"  |  MoS: [{_score_colour(50 + (score.margin_of_safety or 0)*100)}]{_pct(score.margin_of_safety)}[/]" if score.margin_of_safety else ""
        header.add_row(
            f"Price: [bold]{score.current_price:.2f}[/bold]{mos_str}",
            f"Risk: [{_RISK_STYLE.get(score.risk_level, 'white')}]{score.risk_level.value}[/]",
        )
    c.print(Panel(header, border_style="cyan"))

    # --- Score breakdown table ---
    score_table = Table(title="Score Breakdown", box=box.ROUNDED, expand=True, title_style="bold")
    score_table.add_column("Dimension", style="bold")
    score_table.add_column("Score", justify="right")
    score_table.add_column("Bar", justify="left")
    score_table.add_column("Weight", justify="right")
    score_table.add_column("Weighted", justify="right")

    dims = [
        ("Quality",  score.quality),
        ("Value",    score.value),
        ("Growth",   score.growth),
        ("Momentum", score.momentum),
    ]
    for label, sub in dims:
        col = _score_colour(sub.score)
        score_table.add_row(
            label,
            f"[{col}]{sub.score:.1f}[/{col}]",
            f"[{col}]{_bar(sub.score, 15)}[/{col}]",
            f"{sub.weight:.0%}",
            f"[{col}]{sub.weighted_score:.1f}[/{col}]",
        )
    # Composite
    comp_col = _score_colour(score.composite)
    score_table.add_section()
    score_table.add_row(
        "[bold]COMPOSITE[/bold]",
        f"[bold {comp_col}]{score.composite:.1f}[/bold {comp_col}]",
        f"[{comp_col}]{_bar(score.composite)}[/{comp_col}]",
        "100%",
        f"[bold {comp_col}]{score.composite:.1f}[/bold {comp_col}]",
    )
    c.print(score_table)

    # --- Factor exposures ---
    if score.factor_exposures:
        factor_table = Table(title="Factor Exposures (z-scores vs. universe)", box=box.SIMPLE, expand=True)
        factor_table.add_column("Factor")
        factor_table.add_column("Z-Score", justify="right")
        factor_table.add_column("Tilt", justify="left")
        for factor, z in score.factor_exposures.items():
            col = "green" if z > 0.3 else "red" if z < -0.3 else "dim"
            bar_str = ("▲" if z > 0 else "▼") * min(5, int(abs(z) * 2 + 1))
            factor_table.add_row(factor, f"[{col}]{z:+.2f}[/{col}]", f"[{col}]{bar_str}[/{col}]")
        c.print(factor_table)

    # --- Key metrics panels ---
    qual_table = _metrics_table("Quality Metrics", score.quality.drivers)
    val_table = _metrics_table("Value Metrics", score.value.drivers)
    c.print(Columns([qual_table, val_table]))

    growth_table = _metrics_table("Growth Metrics", score.growth.drivers)
    mom_table = _metrics_table("Momentum Metrics", score.momentum.drivers)
    c.print(Columns([growth_table, mom_table]))

    # --- Tail risk ---
    if tail_metrics:
        tr_table = Table(title="Tail Risk Analytics", box=box.SIMPLE, expand=False)
        tr_table.add_column("Metric")
        tr_table.add_column("Value", justify="right")
        pairs = [
            ("Ann. Return",    f"{tail_metrics.get('annualised_return', 'N/A'):.1%}" if tail_metrics.get('annualised_return') else "N/A"),
            ("Ann. Volatility", f"{tail_metrics.get('annualised_volatility', 'N/A'):.1%}" if tail_metrics.get('annualised_volatility') else "N/A"),
            ("Sharpe Ratio",   f"{tail_metrics.get('sharpe_ratio', 'N/A'):.2f}" if tail_metrics.get('sharpe_ratio') else "N/A"),
            ("Sortino Ratio",  f"{tail_metrics.get('sortino_ratio', 'N/A'):.2f}" if tail_metrics.get('sortino_ratio') else "N/A"),
            ("Max Drawdown",   f"{tail_metrics.get('max_drawdown', 'N/A'):.1%}" if tail_metrics.get('max_drawdown') else "N/A"),
            ("VaR 95% (1d)",   f"{tail_metrics.get('var_95_1d', 'N/A'):.2%}" if tail_metrics.get('var_95_1d') else "N/A"),
            ("CVaR 95% (1d)",  f"{tail_metrics.get('cvar_95_1d', 'N/A'):.2%}" if tail_metrics.get('cvar_95_1d') else "N/A"),
            ("Skewness",       f"{tail_metrics.get('skewness', 'N/A'):.2f}" if tail_metrics.get('skewness') else "N/A"),
        ]
        for name, val in pairs:
            tr_table.add_row(name, val)
        c.print(tr_table)

    # --- Alerts ---
    if score.alerts:
        c.print()
        c.print(Panel(
            "\n".join(f"[yellow]⚠[/yellow] {a}" for a in score.alerts),
            title="[bold yellow]Alerts[/bold yellow]",
            border_style="yellow",
        ))

    # --- Notes ---
    all_notes = (score.quality.notes + score.value.notes +
                 score.growth.notes + score.momentum.notes)
    if all_notes:
        c.print()
        c.print(Panel(
            "\n".join(f"[dim]•[/dim] {n}" for n in all_notes),
            title="[bold]Analytical Notes[/bold]",
            border_style="dim",
        ))

    c.print()


def _metrics_table(title: str, drivers: dict) -> Table:
    t = Table(title=title, box=box.SIMPLE, expand=True)
    t.add_column("Metric", style="dim")
    t.add_column("Value", justify="right")
    for k, v in drivers.items():
        if v is None:
            continue
        if isinstance(v, float):
            if abs(v) < 10:
                val_str = f"{v:.2f}"
            else:
                val_str = f"{v:,.0f}"
        else:
            val_str = str(v)
        t.add_row(k, val_str)
    return t


def print_macro_report(score: MacroScore) -> None:
    if not HAS_RICH:
        _plain_macro_report(score)
        return

    c = _CONSOLE
    grade_style, grade_label = _GRADE_STYLE.get(score.grade, ("white", score.grade.value))

    c.print()
    c.print(Rule(f"[bold cyan]MACRO ANALYSIS — {score.country} ({score.currency})[/bold cyan]"))
    c.print()

    # Header
    header = Table.grid(expand=True)
    header.add_column()
    header.add_column(justify="right")
    header.add_row(
        f"[bold]{score.country}[/bold]  [dim]Currency: {score.currency}[/dim]",
        f"[{grade_style}]{grade_label}[/{grade_style}]",
    )
    header.add_row(
        f"Macro Regime: [bold magenta]{score.regime.value}[/bold magenta]",
        "",
    )
    c.print(Panel(header, border_style="magenta"))

    # Score breakdown
    score_table = Table(title="Macro Score Breakdown", box=box.ROUNDED, expand=True, title_style="bold")
    score_table.add_column("Dimension", style="bold")
    score_table.add_column("Score", justify="right")
    score_table.add_column("Bar", justify="left")
    score_table.add_column("Weight", justify="right")

    dims = [
        ("Growth",    score.growth),
        ("Inflation", score.inflation),
        ("Fiscal",    score.fiscal),
        ("External",  score.external),
        ("Monetary",  score.monetary),
    ]
    for label, sub in dims:
        col = _score_colour(sub.score)
        score_table.add_row(
            label,
            f"[{col}]{sub.score:.1f}[/{col}]",
            f"[{col}]{_bar(sub.score, 15)}[/{col}]",
            f"{sub.weight:.0%}",
        )
    score_table.add_section()
    comp_col = _score_colour(score.composite)
    score_table.add_row(
        "[bold]COMPOSITE[/bold]",
        f"[bold {comp_col}]{score.composite:.1f}[/bold {comp_col}]",
        f"[{comp_col}]{_bar(score.composite)}[/{comp_col}]",
        "",
    )
    c.print(score_table)

    # Asset bias
    if score.asset_bias:
        bias_table = Table(title="Asset Class Bias (Dalio All-Weather)", box=box.SIMPLE, expand=True)
        bias_table.add_column("Asset Class")
        bias_table.add_column("Bias", justify="right")
        bias_table.add_column("Signal")
        for asset, bias in score.asset_bias.items():
            col = "green" if bias > 0 else "red" if bias < 0 else "dim"
            label = ("Overweight" if bias > 0.3 else "Slight OW" if bias > 0 else
                     "Underweight" if bias < -0.3 else "Slight UW" if bias < 0 else "Neutral")
            bias_table.add_row(
                asset.capitalize(), f"[{col}]{bias:+.1f}[/{col}]", f"[{col}]{label}[/{col}]"
            )
        c.print(bias_table)

    # Key indicators panels
    growth_metrics = _metrics_table("Growth Indicators", score.growth.drivers)
    inflation_metrics = _metrics_table("Inflation Indicators", score.inflation.drivers)
    c.print(Columns([growth_metrics, inflation_metrics]))

    fiscal_metrics = _metrics_table("Fiscal Indicators", score.fiscal.drivers)
    external_metrics = _metrics_table("External Indicators", score.external.drivers)
    c.print(Columns([fiscal_metrics, external_metrics]))

    # Alerts
    all_alerts = score.alerts.copy()
    if all_alerts:
        c.print()
        c.print(Panel(
            "\n".join(f"[yellow]⚠[/yellow] {a}" for a in all_alerts),
            title="[bold yellow]Macro Alerts[/bold yellow]",
            border_style="yellow",
        ))

    # Tail risks
    if score.tail_risks:
        c.print()
        c.print(Panel(
            "\n".join(f"[red]⛔[/red] {r}" for r in score.tail_risks),
            title="[bold red]Tail Risks[/bold red]",
            border_style="red",
        ))

    # Notes
    all_notes = (score.growth.notes + score.inflation.notes +
                 score.fiscal.notes + score.external.notes + score.monetary.notes)
    if all_notes:
        c.print()
        c.print(Panel(
            "\n".join(f"[dim]•[/dim] {n}" for n in all_notes),
            title="[bold]Analytical Notes[/bold]",
            border_style="dim",
        ))

    c.print()


def print_comparison_table(equity_scores: list, title: str = "Equity Comparison") -> None:
    """Print a ranked comparison table for multiple equities."""
    if not HAS_RICH:
        for s in sorted(equity_scores, key=lambda x: x.composite, reverse=True):
            print(s.summary_dict())
        return

    c = _CONSOLE
    c.print()
    c.print(Rule(f"[bold cyan]{title}[/bold cyan]"))

    t = Table(box=box.ROUNDED, expand=True)
    t.add_column("Rank", justify="right", width=4)
    t.add_column("Ticker", style="bold")
    t.add_column("Name")
    t.add_column("Sector")
    t.add_column("Composite", justify="right")
    t.add_column("Grade", justify="center")
    t.add_column("Quality", justify="right")
    t.add_column("Value", justify="right")
    t.add_column("Growth", justify="right")
    t.add_column("Momentum", justify="right")
    t.add_column("Risk")

    ranked = sorted(equity_scores, key=lambda x: x.composite, reverse=True)
    for i, s in enumerate(ranked, 1):
        comp_col = _score_colour(s.composite)
        grade_style = _GRADE_STYLE.get(s.grade, ("white",))[0]
        t.add_row(
            str(i),
            s.ticker,
            s.name[:25],
            s.sector[:15],
            f"[{comp_col}]{s.composite:.1f}[/{comp_col}]",
            f"[{grade_style}]{s.grade.value}[/{grade_style}]",
            f"[{_score_colour(s.quality.score)}]{s.quality.score:.0f}[/]",
            f"[{_score_colour(s.value.score)}]{s.value.score:.0f}[/]",
            f"[{_score_colour(s.growth.score)}]{s.growth.score:.0f}[/]",
            f"[{_score_colour(s.momentum.score)}]{s.momentum.score:.0f}[/]",
            f"[{_RISK_STYLE.get(s.risk_level, 'white')}]{s.risk_level.value}[/]",
        )
    c.print(t)
    c.print()


# ---- Fallback plain-text renderers ----

def _plain_equity_report(score: EquityScore) -> None:
    print(f"\n{'='*60}")
    print(f"EQUITY: {score.ticker} | {score.name}")
    print(f"Grade: {score.grade.value}  |  Composite: {score.composite:.1f}/100")
    print(f"Quality: {score.quality.score:.1f}  Value: {score.value.score:.1f}  "
          f"Growth: {score.growth.score:.1f}  Momentum: {score.momentum.score:.1f}")
    print(f"Risk: {score.risk_level.value}")
    if score.alerts:
        print("\nAlerts:")
        for a in score.alerts:
            print(f"  ! {a}")
    print('='*60)


def _plain_macro_report(score: MacroScore) -> None:
    print(f"\n{'='*60}")
    print(f"MACRO: {score.country} ({score.currency})")
    print(f"Grade: {score.grade.value}  |  Composite: {score.composite:.1f}/100")
    print(f"Regime: {score.regime.value}")
    print(f"Growth: {score.growth.score:.1f}  Inflation: {score.inflation.score:.1f}  "
          f"Fiscal: {score.fiscal.score:.1f}  External: {score.external.score:.1f}  "
          f"Monetary: {score.monetary.score:.1f}")
    if score.alerts:
        print("\nAlerts:")
        for a in score.alerts:
            print(f"  ! {a}")
    print('='*60)
