from __future__ import annotations

import asyncio
import time
from pathlib import Path

import typer
from rich.console import Console

from ceche.bulk_engine import BulkAppraisalEngine
from ceche.config import Config
from ceche.infrastructure.rate.limiter import RateLimiter

watch_app = typer.Typer(help="Watch a file for new domains and auto-appraise")
console = Console()


@watch_app.command(name="start")
def watch_start(
    path: str = typer.Argument(..., help="File path to watch"),
    interval: int = typer.Option(300, "--interval", "-i", help="Poll interval in seconds"),
    concurrency: int = typer.Option(5, "--concurrency", "-c", help="Concurrent appraisals"),
    fresh: bool = typer.Option(False, "--fresh", "-f", help="Force fresh data"),
) -> None:
    watch_file = Path(path)
    if not watch_file.is_file():
        console.print(f"[red]File not found:[/red] {path}")
        raise typer.Exit(code=1)

    cfg = Config.load()
    limiter = RateLimiter()
    from ceche.interfaces.cli import _build_engine
    engine = _build_engine(cfg, rate_limiter=limiter)
    bulk = BulkAppraisalEngine(engine, concurrency=concurrency, fresh=fresh)

    seen_domains: set[str] = set()

    console.print(f"[green]Watching[/green] {path} (interval={interval}s)")
    while True:
        try:
            content = watch_file.read_text()
            current: set[str] = set()
            for line in content.splitlines():
                d = line.strip().lower()
                if d and not d.startswith("#") and "." in d:
                    current.add(d)
            new_domains = current - seen_domains
            if new_domains:
                console.print(f"[cyan]New domains:[/cyan] {', '.join(sorted(new_domains))}")
                report = asyncio.run(bulk.run(list(new_domains)))
                for r in report.results:
                    val = f"${r.estimated_value:,.0f}" if r.estimated_value else "--"
                    console.print(f"  {r.domain}: {val} [{r.confidence}]")
                seen_domains = seen_domains | new_domains
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
        time.sleep(interval)
