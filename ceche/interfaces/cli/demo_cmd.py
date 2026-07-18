from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console

from ceche.engine import AppraisalEngine

demo_app = typer.Typer(help="Run a demo with mock data")
console = Console()


@demo_app.callback(invoke_without_command=True)
def demo_main(
    count: int = typer.Option(5, "--count", "-n", help="Number of mock domains"),
    fmt: str = typer.Option("pretty", "--format", "-F", help="Output: pretty, json, table"),
) -> None:
    run_demo(count, fmt)


@demo_app.command(name="run", hidden=True)
def demo_run(
    count: int = typer.Option(5, "--count", "-n", help="Number of mock domains"),
    fmt: str = typer.Option("pretty", "--format", "-F", help="Output: pretty, json, table"),
) -> None:
    run_demo(count, fmt)


def run_demo(count: int = 5, fmt: str = "pretty") -> None:
    from typing import Any

    class _MockRDAP:
        async def lookup(self, domain): return {"_not_found": True}
    class _MockCache:
        async def get(self, key): return None
        async def set(self, key, v, ttl): pass
        async def get_or_compute(self, key, ttl, fn): return await fn()
    class _MockKW:
        async def get_popularity(self, w):
            return 50.0 if len(w) > 3 else 10.0
    class _MockTM:
        async def check(self, t):
            from ceche.domain.models import TrademarkResult
            return TrademarkResult(conflict=False, severity="none", marks=[])
    class _MockWB:
        async def get_snapshots(self, d): return {"count": 50}
    class _MockAH:
        async def lookup(self, d): return 25.0
    class _MockOPR:
        async def lookup(self, d): return {"rank": 50000}

    engine = AppraisalEngine(
        rdap=_MockRDAP(), cache=_MockCache(),
        keyword=_MockKW(), trademark=_MockTM(),
        wayback=_MockWB(), ahrefs=_MockAH(), opr=_MockOPR(),
    )

    mock_domains = [
        "alphadomain.com", "betasite.io", "gammalabs.ai",
        "deltaventures.co", "epsilonapps.dev", "zetaworks.org",
        "etasolutions.net", "thetanetwork.cloud", "iotahub.biz",
        "kappamarket.store", "lambdacode.tech", "muservices.online",
    ][:count]

    from ceche.domain.result import AppraisalResult
    results: list[AppraisalResult] = []
    for d in mock_domains:
        r = asyncio.run(engine.appraise(d))
        results.append(r)

    from ceche.interfaces.cli import _build_unified_output, _output_table, _output_pretty
    if fmt == "json":
        out = _build_unified_output(results)
        console.print(json.dumps(out, indent=2, default=str))
    elif fmt == "table":
        _output_table(results)
    else:
        _output_pretty(results)
