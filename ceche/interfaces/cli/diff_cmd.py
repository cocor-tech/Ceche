from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from ceche.infrastructure.persistence.store import AppraisalStore

diff_app = typer.Typer(help="Show domain value history")
console = Console()


@diff_app.command(name="run")
def diff_run(
    domain: str = typer.Argument(..., help="Domain to track"),
    days: int = typer.Option(90, "--days", "-d", help="Days of history"),
    fmt: str = typer.Option("table", "--format", "-F", help="Output: table, json"),
) -> None:
    store = AppraisalStore()
    history = store.get_domain_history(domain, days=days)
    if not history:
        console.print(f"[dim]No history for {domain}.[/dim]")
        return
    if fmt == "json":
        console.print(json.dumps(history, indent=2, default=str))
    else:
        table = Table(title=f"Value History: {domain}")
        table.add_column("Date", style="dim")
        table.add_column("Value", justify="right", style="green")
        table.add_column("Confidence")
        table.add_column("Range")
        prev: float | None = None
        for h in reversed(history):
            val = h.get("estimated_value")
            rl = h.get("range_low")
            rh = h.get("range_high")
            rng = f"${rl:,.0f} - ${rh:,.0f}" if rl and rh else "--"
            table.add_row(
                str(h.get("created_at", "")),
                f"${val:,.0f}" if val else "--",
                h.get("confidence", ""),
                rng,
            )
        console.print(table)
