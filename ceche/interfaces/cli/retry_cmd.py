from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console

from ceche.config import Config
from ceche.infrastructure.persistence.store import AppraisalStore

retry_app = typer.Typer(help="Re-appraise domains from a previous run")
console = Console()


@retry_app.command(name="run")
def retry_run(
    run_id: str = typer.Argument(..., help="Run ID to retry"),
    failed_only: bool = typer.Option(False, "--failed-only", "-f", help="Only retry failed"),
    concurrency: int = typer.Option(5, "--concurrency", "-c", help="Concurrent domains"),
) -> None:
    from ceche.bulk_engine import BulkAppraisalEngine
    from ceche.infrastructure.rate.limiter import RateLimiter
    from ceche.interfaces.cli import _build_engine

    store = AppraisalStore()
    run = store.get_run(run_id)
    if not run:
        console.print(f"[red]Run {run_id} not found.[/red]")
        raise typer.Exit(code=1)

    cfg = Config.load()
    limiter = RateLimiter()
    engine = _build_engine(cfg, rate_limiter=limiter)
    bulk = BulkAppraisalEngine(engine, concurrency=concurrency, fresh=True)

    import sqlite3
    conn = sqlite3.connect(store.db_path)
    conn.row_factory = sqlite3.Row
    domains_data = conn.execute(
        "SELECT domain, error_type FROM appraisals WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    conn.close()

    if failed_only:
        domains = [d["domain"] for d in domains_data if d["error_type"]]
    else:
        domains = [d["domain"] for d in domains_data]

    if not domains:
        console.print("[dim]No domains to retry.[/dim]")
        return

    console.print(f"[cyan]Retrying[/cyan] {len(domains)} domains from run {run_id[:8]}...")
    report = asyncio.run(bulk.run(domains))
    console.print(json.dumps({
        "succeeded": report.summary.succeeded,
        "failed": report.summary.failed,
        "results": [
            {"domain": r.domain, "estimated_value": r.estimated_value}
            for r in report.results
        ],
        "failures": [
            {"domain": f.domain, "error_type": f.error_type}
            for f in report.failures
        ],
    }, indent=2, default=str))
