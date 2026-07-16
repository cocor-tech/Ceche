from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from ceche.config import Config
from ceche.domain.result import AppraisalResult

compare_app = typer.Typer(help="Compare two domain appraisals")
console = Console()


@compare_app.command(name="run")
def compare_run(
    domain1: str = typer.Argument(..., help="First domain"),
    domain2: str = typer.Argument(..., help="Second domain"),
    fresh: bool = typer.Option(False, "--fresh", "-f", help="Bypass cache"),
    fmt: str = typer.Option("table", "--format", "-F", help="Output: table, json"),
) -> None:
    from ceche.interfaces.cli import _build_engine

    cfg = Config.load()
    engine = _build_engine(cfg)

    r1 = asyncio.run(engine.appraise(domain1, fresh=fresh))
    r2 = asyncio.run(engine.appraise(domain2, fresh=fresh))

    if fmt == "json":
        import json
        console.print(json.dumps({
            "domain1": _r_to_d(r1),
            "domain2": _r_to_d(r2),
        }, indent=2, default=str))
    else:
        table = Table(title=f"Comparison: {domain1} vs {domain2}")
        table.add_column("Metric", style="cyan")
        table.add_column(domain1, style="green")
        table.add_column(domain2, style="green")
        table.add_row("Value", _fv(r1.estimated_value), _fv(r2.estimated_value))
        table.add_row("Range", _fr(r1), _fr(r2))
        table.add_row("Confidence", r1.confidence or "--", r2.confidence or "--")
        table.add_row("TLD Score", _fv(r1.tld_score), _fv(r2.tld_score))
        table.add_row("Weight", r1.weight_profile or "--", r2.weight_profile or "--")
        table.add_row("Words", str(_m6_wc(r1)), str(_m6_wc(r2)))
        table.add_row("Result", _m6_r(r1), _m6_r(r2))
        table.add_row("Registered", _reg(r1), _reg(r2))
        table.add_row("Age", _fv(_age(r1)), _fv(_age(r2)))
        console.print(table)


def _r_to_d(r: AppraisalResult) -> dict[str, object]:
    return {
        "domain": r.domain,
        "estimated_value": r.estimated_value,
        "range": {"low": r.range_low, "high": r.range_high},
        "confidence": r.confidence,
        "tld_score": r.tld_score,
        "weight_profile": r.weight_profile,
    }


def _fv(v: float | None) -> str:
    return f"${v:,.0f}" if v is not None else "--"


def _fr(r: AppraisalResult) -> str:
    if r.range_low is not None and r.range_high is not None:
        return f"${r.range_low:,.0f} - ${r.range_high:,.0f}"
    return "--"


def _m6_wc(r: AppraisalResult) -> int:
    m6 = r.modules.get("m6_segmenter", {})
    return m6.get("word_count") or 0


def _m6_r(r: AppraisalResult) -> str:
    m6 = r.modules.get("m6_segmenter", {})
    return m6.get("result") or "--"


def _reg(r: AppraisalResult) -> str:
    m1 = r.modules.get("m1_rdap", {})
    return "Yes" if m1.get("registered") else "No"


def _age(r: AppraisalResult) -> float | None:
    m12 = r.modules.get("m12_authority", {})
    return m12.get("age_years")
