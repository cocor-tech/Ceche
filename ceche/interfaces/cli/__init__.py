from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ceche.config import Config
from ceche.domain.result import AppraisalResult
from ceche.engine import AppraisalEngine
from ceche.infrastructure.authority.ahrefs_adapter import AhrefsDRAdapter
from ceche.infrastructure.authority.opr_adapter import OPRAdapter
from ceche.infrastructure.authority.wayback_adapter import WaybackAdapter
from ceche.infrastructure.cache.sqlite_adapter import SQLiteCacheAdapter
from ceche.infrastructure.keyword.static_adapter import StaticKeywordAdapter
from ceche.infrastructure.rdap.rdap_adapter import RDAPAdapter
from ceche.infrastructure.search.brave_adapter import BraveAdapter
from ceche.infrastructure.search.google_cse_adapter import GoogleCSEAdapter
from ceche.infrastructure.trademark.uspto_adapter import USPTOAdapter

app = typer.Typer(name="ceche", help="Domain Appraisal Engine")
console = Console()


def _build_engine(cfg: Config) -> AppraisalEngine:
    cache = SQLiteCacheAdapter(cfg.cache_path)
    rdap = RDAPAdapter()
    keyword = StaticKeywordAdapter()
    trademark = USPTOAdapter()
    wayback = WaybackAdapter()
    ahrefs = AhrefsDRAdapter()
    opr = OPRAdapter(cfg.opr_key) if cfg.opr_key else None

    search = None
    search_backup = None
    if cfg.google_cse_key and cfg.google_cse_cx:
        search = GoogleCSEAdapter(cfg.google_cse_key, cfg.google_cse_cx)
    if cfg.brave_key:
        search_backup = BraveAdapter(cfg.brave_key)

    return AppraisalEngine(
        rdap=rdap,
        cache=cache,
        keyword=keyword,
        search=search,
        search_backup=search_backup,
        trademark=trademark,
        wayback=wayback,
        ahrefs=ahrefs,
        opr=opr,
    )


@app.command(name="appraise")
def appraise_cmd(
    domains: list[str] = typer.Argument(..., help="Domain(s) to appraise or path to file"),
    fresh: bool = typer.Option(False, "--fresh", "-f", help="Bypass cache"),
    fmt: str = typer.Option("pretty", "--format", help="Output format: json, table, pretty"),
    include_raw: bool = typer.Option(False, "--include-raw", "-r", help="Include raw module data"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output"),
) -> None:
    cfg = Config.load()
    if fresh:
        cfg.fresh = True
        import os
        try:
            os.remove(cfg.cache_path)
        except FileNotFoundError:
            pass

    engine = _build_engine(cfg)

    all_domains = [d for d in _resolve_domains(domains) if "." in d]
    if not all_domains:
        console.print("[red]No domains provided.[/red]")
        raise typer.Exit(code=1)

    results: list[AppraisalResult] = []
    for domain in all_domains:
        if not quiet:
            console.print(f"[dim]Appraising [bold]{domain}[/bold]...[/dim]")
        result = asyncio.run(engine.appraise(domain))
        results.append(result)

    if fmt == "json":
        _output_json(results, include_raw)
    elif fmt == "table":
        _output_table(results)
    else:
        _output_pretty(results)


def _resolve_domains(args: list[str]) -> list[str]:
    if len(args) == 1:
        path = Path(args[0])
        if path.is_file():
            return [
                line.strip()
                for line in path.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
    return [d.strip().lower() for d in args if d.strip()]


def _output_json(results: list[AppraisalResult], include_raw: bool) -> None:
    output = []
    for r in results:
        entry: dict[str, object] = {
            "domain": r.domain,
            "estimated_value": r.estimated_value,
            "range": {"low": r.range_low, "high": r.range_high},
            "confidence": r.confidence,
            "completeness_ratio": r.completeness_ratio,
        }
        if include_raw:
            entry["modules"] = r.modules
        output.append(entry)
    console.print(json.dumps(output, indent=2, default=str))


def _output_table(results: list[AppraisalResult]) -> None:
    table = Table(title="Ceche -- Domain Appraisal")
    table.add_column("Domain", style="cyan")
    table.add_column("Estimate", justify="right", style="green")
    table.add_column("Range", style="dim")
    table.add_column("Confidence")

    for r in results:
        estimate = f"${r.estimated_value:,.0f}" if r.estimated_value else "--"
        lo = f"${r.range_low:,.0f}" if r.range_low else "--"
        hi = f"${r.range_high:,.0f}" if r.range_high else "--"
        table.add_row(r.domain, estimate, f"{lo} - {hi}", r.confidence or "--")

    console.print(table)


def _output_pretty(results: list[AppraisalResult]) -> None:
    for r in results:
        console.rule(f"[bold cyan]{r.domain}[/bold cyan]")
        if r.estimated_value:
            console.print(
                f"  Estimated Value: [green bold]${r.estimated_value:,.0f}[/green bold]"
            )
        if r.range_low and r.range_high:
            console.print(
                f"  Range:           [dim]${r.range_low:,.0f} - ${r.range_high:,.0f}[/dim]"
            )
        if r.confidence:
            console.print(f"  Confidence:      [bold]{r.confidence}[/bold]")
        if r.tld_score:
            console.print(f"  TLD Score:       {r.tld_score}")
        console.print("")
