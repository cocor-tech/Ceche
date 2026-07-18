from __future__ import annotations

import json

import typer
from rich.console import Console

from ceche.infrastructure.persistence.store import AppraisalStore

history_app = typer.Typer(help="View appraisal history")
console = Console()
_store = AppraisalStore()


@history_app.callback(invoke_without_command=True)
def history_main(
    days: int = typer.Option(30, "--days", "-d", help="Days of history"),
    domain: str = typer.Option("", "--domain", help="Filter by domain"),
    fmt: str = typer.Option("table", "--format", "-F", help="Output: table, json"),
) -> None:
    if domain:
        entries = _store.get_domain_history(domain, days=days)
    else:
        entries = _store.list_runs(days=days)
    if fmt == "json":
        console.print(json.dumps(entries, indent=2, default=str))
    else:
        from rich.table import Table
        if domain:
            table = Table(title=f"History for {domain}")
            table.add_column("Date", style="dim")
            table.add_column("Value", justify="right", style="green")
            table.add_column("Confidence")
            for e in entries:
                val = f"${e['estimated_value']:,.0f}" if e.get("estimated_value") else "--"
                table.add_row(str(e.get("created_at", "")), val, e.get("confidence", "--"))
        else:
            table = Table(title=f"Appraisal Runs (last {days}d)")
            table.add_column("Run ID", style="cyan")
            table.add_column("Date")
            table.add_column("Total")
            table.add_column("Succeeded")
            table.add_column("Failed")
            table.add_column("Command")
            table.add_column("Fresh")
            for r in entries:
                table.add_row(
                    r.get("id", "")[:8] + "...",
                    str(r.get("started_at", "")),
                    str(r.get("total", 0)),
                    str(r.get("succeeded", 0)),
                    str(r.get("failed", 0)),
                    r.get("command", ""),
                    "[green]yes[/green]" if r.get("fresh") else "",
                )
        console.print(table)


@history_app.command(name="export")
def history_export(
    path: str = typer.Argument(..., help="Output file path"),
    days: int = typer.Option(30, "--days", "-d", help="Days of history to export"),
) -> None:
    _store.export(path, days=days)
    console.print(f"[green]Exported[/green] history → {path}")


@history_app.command(name="clear")
def history_clear(
    days: int | None = typer.Option(None, "--days", "-d", help="Clear older than N days"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    if not force:
        console.print("[yellow]Use --force to confirm clearing history.[/yellow]")
        return
    _store.clear(days=days)
    msg = f"older than {days}d" if days else "all"
    console.print(f"[yellow]History cleared ({msg}).[/yellow]")
