from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from ceche.infrastructure.persistence.store import AppraisalStore

stats_app = typer.Typer(help="View usage statistics", invoke_without_command=True)
console = Console()
_store = AppraisalStore()


@stats_app.callback()
def stats_callback(
    days: int = typer.Option(30, "--days", "-d", help="Days of stats"),
    fmt: str = typer.Option("table", "--format", "-F", help="Output: table, json"),
) -> None:
    s = _store.get_stats(days=days)
    ai = _store.get_ai_usage_summary(days=days)
    if fmt == "json":
        console.print(json.dumps({**s, "ai_usage": ai}, indent=2, default=str))
    else:
        table = Table(title=f"Statistics (last {days}d)")
        table.add_column("Metric", style="green")
        table.add_column("Value", style="green")
        table.add_row("Total Appraisals", str(s.get("total_appraisals", 0)))
        table.add_row("With Value", str(s.get("with_value", 0)))
        val = f"${s.get('avg_estimated_value', 0):,.0f}" if s.get("avg_estimated_value") else "--"
        table.add_row("Avg Value", val)
        console.print(table)
        if ai:
            ai_table = Table(title=f"AI Usage (last {days}d)")
            ai_table.add_column("Provider")
            ai_table.add_column("Model")
            ai_table.add_column("Calls")
            ai_table.add_column("Tokens In")
            ai_table.add_column("Tokens Out")
            ai_table.add_column("Cost")
            for a in ai:
                ai_table.add_row(
                    a.get("provider", ""),
                    a.get("model", ""),
                    str(a.get("calls", 0)),
                    str(a.get("tokens_in", 0)),
                    str(a.get("tokens_out", 0)),
                    f"${a.get('cost_usd', 0):.4f}",
                )
            console.print(ai_table)
