from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console

debug_app = typer.Typer(help="Debug a domain appraisal step by step")
console = Console()


@debug_app.command(name="run")
def debug_run(
    domain: str = typer.Argument(..., help="Domain to debug"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Use mock data, no network"),
    trace: bool = typer.Option(False, "--trace", "-t", help="Per-module timing and data dump"),
) -> None:

    if dry_run:
        console.print("[yellow]Dry-run mode:[/yellow] using mock adapters")
        from ceche.engine import AppraisalEngine

        class _MockRDAP:
            async def lookup(self, domain): return {"_not_found": True}
        class _MockCache:
            async def get(self, key): return None
            async def set(self, key, v, ttl): pass
            async def get_or_compute(self, key, ttl, fn): return await fn()
        class _MockKeyword:
            async def get_popularity(self, w): return 50.0
        class _MockTM:
            async def check(self, t):
                from ceche.domain.models import TrademarkResult
                return TrademarkResult(conflict=False, severity="none", marks=[])
        class _MockWB:
            async def get_snapshots(self, d): return {"count": 10}
        class _MockAH:
            async def lookup(self, d): return 30.0
        class _MockOPR:
            async def lookup(self, d): return {"rank": 10000}

        engine = AppraisalEngine(
            rdap=_MockRDAP(), cache=_MockCache(),
            keyword=_MockKeyword(), trademark=_MockTM(),
            wayback=_MockWB(), ahrefs=_MockAH(), opr=_MockOPR(),
        )

    result = asyncio.run(engine.appraise(domain, fresh=True))

    modules = result.modules
    console.print(f"[bold cyan]{domain}[/bold cyan]")
    console.print(f"  Value: ${result.estimated_value:,.0f}" if result.estimated_value else "  Value: --")
    console.print(f"  Confidence: {result.confidence}")
    console.print(f"  Completeness: {result.completeness_ratio}")
    console.print(f"  Version: {result.version}")
    console.print(f"  Generated: {result.generated_at}")
    console.print()

    for name in sorted(modules.keys()):
        m = modules[name]
        console.print(f"[cyan]{name}:[/cyan] status={m.get('status')}", end="")
        if m.get("result"):
            console.print(f" result={m['result']}", end="")
        if m.get("reason"):
            console.print(f" reason={m['reason']}", end="")
        console.print()

    if trace:
        console.print("\n[underline]Full module data:[/underline]")
        console.print(json.dumps(modules, indent=2, default=str))
