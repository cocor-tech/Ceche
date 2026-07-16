from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ceche.config import Config
from ceche.domain.result import AppraisalResult
from ceche.infrastructure.portfolio.store import PortfolioStore

portfolio_app = typer.Typer(help="Manage domain portfolios")
console = Console()
_store = PortfolioStore()


@portfolio_app.command(name="create")
def portfolio_create(
    name: str = typer.Argument(..., help="Portfolio name"),
) -> None:
    try:
        result = _store.create(name)
        console.print(f"[green]Portfolio[/green] '{result['name']}' [green]created.[/green]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from None


@portfolio_app.command(name="list")
def portfolio_list(
    fmt: str = typer.Option("table", "--format", "-F", help="Output: table, json"),
) -> None:
    portfolios = _store.list_all()
    if not portfolios:
        console.print("[dim]No portfolios.[/dim]")
        return
    if fmt == "json":
        console.print(json.dumps(portfolios, indent=2, default=str))
    else:
        table = Table(title="Portfolios")
        table.add_column("Name", style="cyan")
        table.add_column("Domains", justify="right")
        table.add_column("Created")
        for p in portfolios:
            table.add_row(
                p["name"], str(p.get("domain_count", 0)),
                str(p.get("created_at", "")),
            )
        console.print(table)


@portfolio_app.command(name="show")
def portfolio_show(
    name: str = typer.Argument(..., help="Portfolio name"),
    fmt: str = typer.Option("table", "--format", "-F", help="Output: table, json"),
) -> None:
    data = _store.show(name)
    if not data:
        console.print(f"[red]Portfolio '{name}' not found.[/red]")
        raise typer.Exit(code=1) from None
    if fmt == "json":
        console.print(json.dumps(data, indent=2, default=str))
    else:
        console.print(
            f"[bold cyan]{name}[/bold cyan] "
            f"({data.get('domain_count', len(data.get('domains', [])))} domains)"
        )
        table = Table()
        table.add_column("Domain", style="cyan")
        table.add_column("Value", justify="right")
        table.add_column("Confidence")
        table.add_column("Tags")
        for d in data.get("domains", []):
            tags = d.get("tags", "[]")
            if isinstance(tags, str):
                try:
                    tags_list = json.loads(tags)
                except (ValueError, TypeError):
                    tags_list = []
            else:
                tags_list = tags
            tags_str = ", ".join(tags_list) if tags_list else ""
            val = f"${d['estimated_value']:,.0f}" if d.get("estimated_value") else "--"
            table.add_row(d["domain"], val, d.get("confidence", ""), tags_str)
        console.print(table)


@portfolio_app.command(name="delete")
def portfolio_delete(
    name: str = typer.Argument(..., help="Portfolio name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    if not force:
        console.print("[yellow]Use --force to confirm deletion.[/yellow]")
        return
    if _store.delete(name):
        console.print(f"[yellow]Portfolio '{name}' deleted.[/yellow]")
    else:
        console.print(f"[red]Portfolio '{name}' not found.[/red]")
        raise typer.Exit(code=1) from None


@portfolio_app.command(name="add")
def portfolio_add(
    name: str = typer.Argument(..., help="Portfolio name"),
    domains: list[str] = typer.Argument(..., help="Domain(s) to add or path to file"),
) -> None:
    all_domains = _resolve_domains_flat(domains)
    try:
        added = _store.add(name, all_domains)
        console.print(f"[green]Added[/green] {added} domain(s) to '{name}'.")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from None


@portfolio_app.command(name="remove")
def portfolio_remove(
    name: str = typer.Argument(..., help="Portfolio name"),
    domains: list[str] = typer.Argument(..., help="Domain(s) to remove"),
) -> None:
    try:
        removed = _store.remove(name, domains)
        console.print(f"[yellow]Removed[/yellow] {removed} domain(s) from '{name}'.")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from None


@portfolio_app.command(name="appraise")
def portfolio_appraise(
    name: str = typer.Argument(..., help="Portfolio name"),
    fresh: bool = typer.Option(False, "--fresh", "-f", help="Bypass cache"),
    concurrency: int = typer.Option(5, "--concurrency", "-c", help="Concurrent domains"),
) -> None:
    data = _store.show(name)
    if not data:
        console.print(f"[red]Portfolio '{name}' not found.[/red]")
        raise typer.Exit(code=1) from None
    domains = [d["domain"] for d in data.get("domains", [])]
    if not domains:
        console.print(f"[dim]No domains in '{name}'.[/dim]")
        return

    cfg = Config.load()
    import contextlib
    if fresh:
        with contextlib.suppress(FileNotFoundError):
            Path(cfg.cache_path).unlink()

    from ceche.bulk_engine import BulkAppraisalEngine
    from ceche.infrastructure.rate.limiter import RateLimiter
    from ceche.interfaces.cli import _build_engine

    limiter = RateLimiter()
    engine = _build_engine(cfg, rate_limiter=limiter)
    bulk = BulkAppraisalEngine(engine, concurrency=concurrency, fresh=fresh)
    report = asyncio.run(bulk.run(domains))

    for r in report.results:
        _store.update_domain_value(
            name, r.domain,
            r.estimated_value, r.confidence,
        )

    sys.stdout.write(
        json.dumps({
            "summary": {
                "total": report.summary.total,
                "succeeded": report.summary.succeeded,
                "failed": report.summary.failed,
            },
            "results": [_r_to_dict(r) for r in report.results],
        }, indent=2, default=str) + "\n"
    )


@portfolio_app.command(name="value")
def portfolio_value(
    name: str = typer.Argument(..., help="Portfolio name"),
    fmt: str = typer.Option("table", "--format", "-F", help="Output: table, json"),
) -> None:
    data = _store.show(name)
    if not data:
        console.print(f"[red]Portfolio '{name}' not found.[/red]")
        raise typer.Exit(code=1) from None
    domains = data.get("domains", [])
    total = sum(d.get("estimated_value") or 0 for d in domains)
    count = sum(1 for d in domains if d.get("estimated_value"))
    if fmt == "json":
        console.print(json.dumps({
            "portfolio": name,
            "total_value": round(total, 2),
            "domain_count": len(domains),
            "appraised_count": count,
        }, indent=2))
    else:
        console.print(f"[bold cyan]{name}[/bold cyan]")
        console.print(f"  Total Value:   [green bold]${total:,.0f}[/green bold]")
        console.print(f"  Domains:       {len(domains)}")
        console.print(f"  Appraised:     {count}")


@portfolio_app.command(name="import")
def portfolio_import(
    name: str = typer.Argument(..., help="Portfolio name"),
    path: str = typer.Argument(..., help="CSV file path"),
) -> None:
    if not _store.portfolio_exists(name):
        _store.create(name)
    csv_text = Path(path).read_text()
    added = _store.import_csv(name, csv_text)
    console.print(f"[green]Imported[/green] {added} domain(s) into '{name}'.")


@portfolio_app.command(name="export")
def portfolio_export(
    name: str = typer.Argument(..., help="Portfolio name"),
    output: str = typer.Option("", "--output", "-o", help="Output file path"),
) -> None:
    try:
        csv_text = _store.export_csv(name)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from None
    if output:
        Path(output).write_text(csv_text)
        console.print(f"[green]Exported[/green] '{name}' → {output}")
    else:
        sys.stdout.write(csv_text)


@portfolio_app.command(name="tag")
def portfolio_tag(
    name: str = typer.Argument(..., help="Portfolio name"),
    domain: str = typer.Argument(..., help="Domain"),
    tag: str = typer.Argument(..., help="Tag"),
) -> None:
    if _store.tag(name, domain, tag):
        console.print(f"[green]Tagged[/green] {domain} with '{tag}'.")
    else:
        console.print(f"[red]Domain {domain} not found in '{name}'.[/red]")
        raise typer.Exit(code=1) from None


@portfolio_app.command(name="note")
def portfolio_note(
    name: str = typer.Argument(..., help="Portfolio name"),
    domain: str = typer.Argument(..., help="Domain"),
    note_text: str = typer.Argument(..., help="Note text"),
) -> None:
    if _store.note(name, domain, note_text):
        console.print(f"[green]Note added[/green] to {domain}.")
    else:
        console.print(f"[red]Domain {domain} not found in '{name}'.[/red]")
        raise typer.Exit(code=1) from None


@portfolio_app.command(name="search")
def portfolio_search(
    query: str = typer.Argument(..., help="Search term"),
    fmt: str = typer.Option("table", "--format", "-F", help="Output: table, json"),
) -> None:
    results = _store.search(query)
    if not results:
        console.print("[dim]No matches.[/dim]")
        return
    if fmt == "json":
        console.print(json.dumps(results, indent=2, default=str))
    else:
        table = Table(title=f"Search: '{query}'")
        table.add_column("Portfolio", style="cyan")
        table.add_column("Domain")
        table.add_column("Value", justify="right")
        table.add_column("Confidence")
        for r in results:
            val = f"${r['estimated_value']:,.0f}" if r.get("estimated_value") else "--"
            table.add_row(r["portfolio_name"], r["domain"], val, r.get("confidence", ""))
        console.print(table)


def _resolve_domains_flat(args: list[str]) -> list[str]:
    domains: list[str] = []
    for s in args:
        s = s.strip().lower()
        if not s:
            continue
        p = Path(s)
        if p.is_file():
            for line in p.read_text().splitlines():
                d = line.strip().lower()
                if d and not d.startswith("#"):
                    domains.append(d)
        else:
            domains.append(s)
    seen: set[str] = set()
    result: list[str] = []
    for d in domains:
        if d not in seen:
            seen.add(d)
            result.append(d)
    return result


def _r_to_dict(r: AppraisalResult) -> dict[str, object]:
    mod_summary: dict[str, int] = {}
    for me in r.modules.values():
        s = me.get("status", "UNKNOWN")
        mod_summary[s] = mod_summary.get(s, 0) + 1
    return {
        "domain": r.domain,
        "estimated_value": r.estimated_value,
        "range": {"low": r.range_low, "high": r.range_high},
        "confidence": r.confidence,
        "completeness_ratio": r.completeness_ratio,
        "tld_score": r.tld_score,
        "weight_profile": r.weight_profile,
        "module_summary": mod_summary,
    }
