from __future__ import annotations

import asyncio
import json
import string

import typer
from rich.console import Console
from rich.table import Table

from ceche.config import Config
from ceche.domain.result import AppraisalResult

similar_app = typer.Typer(help="Find similar domain suggestions")
console = Console()


@similar_app.command(name="run")
def similar_run(
    domain: str = typer.Argument(..., help="Domain to base suggestions on"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max suggestions"),
    tld: str = typer.Option("", "--tld", help="Restrict to TLD"),
    fresh: bool = typer.Option(False, "--fresh", "-f", help="Bypass cache"),
    fmt: str = typer.Option("table", "--format", "-F", help="Output: table, json"),
) -> None:
    from ceche.interfaces.cli import _build_engine

    cfg = Config.load()
    engine = _build_engine(cfg)

    sld, orig_tld = _split_domain(domain)
    target_tld = tld or orig_tld
    candidates = _generate_candidates(sld, target_tld, limit * 3)
    candidates = candidates[:limit * 2]

    results: list[AppraisalResult] = []
    for c in candidates:
        try:
            r = asyncio.run(engine.appraise(c, fresh=fresh))
            results.append(r)
        except Exception:
            pass
        if len(results) >= limit:
            break

    results.sort(key=lambda r: r.estimated_value or 0, reverse=True)
    results = results[:limit]

    if fmt == "json":
        console.print(json.dumps([
            {"domain": r.domain, "estimated_value": r.estimated_value,
             "confidence": r.confidence, "weight_profile": r.weight_profile}
            for r in results
        ], indent=2, default=str))
    else:
        table = Table(title=f"Similar to {domain}")
        table.add_column("Domain", style="cyan")
        table.add_column("Value", justify="right", style="green")
        table.add_column("Confidence")
        table.add_column("Profile")
        for r in results:
            table.add_row(
                r.domain,
                f"${r.estimated_value:,.0f}" if r.estimated_value else "--",
                r.confidence or "--",
                r.weight_profile or "--",
            )
        console.print(table)


def _split_domain(domain: str) -> tuple[str, str]:
    parts = domain.rsplit(".", 1)
    if len(parts) == 2:
        return parts[0].lower(), parts[1].lower()
    return domain.lower(), "com"


def _generate_candidates(sld: str, tld: str, n: int) -> list[str]:
    candidates: list[str] = []
    if len(sld) >= 4:
        for i in range(1, len(sld) - 1):
            candidates.append(f"{sld[:i]}-{sld[i:]}.{tld}")
    for ch in string.ascii_lowercase:
        candidates.append(f"{sld}{ch}.{tld}")
        candidates.append(f"{ch}{sld}.{tld}")
    for suffix in ["s", "es", "ly", "er", "ing", "ify", "hub", "zone", "lab"]:
        candidates.append(f"{sld}{suffix}.{tld}")
    for prefix in ["my", "go", "get", "the", "try", "new", "top"]:
        candidates.append(f"{prefix}{sld}.{tld}")
    seen: set[str] = set()
    result: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result[:n]
