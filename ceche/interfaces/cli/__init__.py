from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from ceche.bulk_engine import BulkAppraisalEngine, BulkReport
from ceche.config import Config
from ceche.domain.result import AppraisalResult
from ceche.engine import AppraisalEngine
from ceche.infrastructure.ai.key_manager import KeyManager
from ceche.infrastructure.ai.router import ModelRouter
from ceche.infrastructure.authority.ahrefs_adapter import AhrefsDRAdapter
from ceche.infrastructure.authority.opr_adapter import OPRAdapter
from ceche.infrastructure.authority.wayback_adapter import WaybackAdapter
from ceche.infrastructure.cache.sqlite_adapter import SQLiteCacheAdapter
from ceche.infrastructure.keyword.static_adapter import StaticKeywordAdapter
from ceche.infrastructure.rate.limiter import RateLimiter
from ceche.infrastructure.rdap.rdap_adapter import RDAPAdapter
from ceche.infrastructure.search.brave_adapter import BraveAdapter
from ceche.infrastructure.search.google_cse_adapter import GoogleCSEAdapter
from ceche.infrastructure.trademark.uspto_adapter import USPTOAdapter

app = typer.Typer(name="ceche", help="Domain Appraisal Engine")
console = Console()


def _build_router(cfg: Config, rate_limiter: RateLimiter | None = None) -> ModelRouter | None:
    import os

    router = ModelRouter(rate_limiter=rate_limiter)

    provider_keys: dict[str, list[str]] = {
        "deepseek": ["DEEPSEEK_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
        "kimi": ["KIMI_API_KEY", "MOONSHOT_API_KEY"],
        "glm": ["GLM_API_KEY", "ZHIPU_API_KEY"],
        "minimax": ["MINIMAX_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY"],
    }

    for provider_id, env_keys in provider_keys.items():
        for env_key in env_keys:
            key = os.getenv(env_key)
            if key:
                router.register_provider(
                    provider_id, key,
                    model=os.getenv(f"{provider_id.upper()}_MODEL"),
                )
                break

    if not router.enabled:
        km = KeyManager()
        for provider_id in provider_keys:
            if km.has_provider(provider_id):
                key = km.get_active_key(provider_id)
                if key:
                    router.register_provider(
                        provider_id, key,
                        model=os.getenv(f"{provider_id.upper()}_MODEL"),
                    )

    if not router.enabled:
        return None

    primary = router.providers[0]
    temperature = float(os.getenv("CECHE_AI_TEMPERATURE", "0.1"))
    max_tokens = int(os.getenv("CECHE_AI_MAX_TOKENS", "150"))

    router.set_default(primary, temperature=temperature, max_tokens=max_tokens)

    for module in ["m6", "m8", "m11", "m16"]:
        mod_model = os.getenv(f"CECHE_{module.upper()}_MODEL")
        mod_provider = os.getenv(f"CECHE_{module.upper()}_PROVIDER")
        mt = int(os.getenv(f"CECHE_{module.upper()}_MAX_TOKENS", str(max_tokens)))
        if module == "m6" and mt < 500:
            mt = 500
        if mod_provider and mod_provider in router.providers:
            router.assign_modules(
                [module], mod_provider, model=mod_model,
                temperature=temperature, max_tokens=mt,
            )
        elif mod_model:
            router.assign_modules(
                [module], primary, model=mod_model,
                temperature=temperature, max_tokens=mt,
            )
        else:
            router.assign_modules(
                [module], primary,
                temperature=temperature, max_tokens=mt,
            )

    return router


def _build_engine(cfg: Config, rate_limiter: RateLimiter | None = None) -> AppraisalEngine:
    cache = SQLiteCacheAdapter(cfg.cache_path)
    rdap_client = rate_limiter.client_for("rdap", timeout=15.0) if rate_limiter else None
    rdap = RDAPAdapter(client=rdap_client)
    keyword = StaticKeywordAdapter()
    trademark = USPTOAdapter()

    wayback_client = rate_limiter.client_for("wayback", timeout=15.0) if rate_limiter else None
    ahrefs_client = rate_limiter.client_for("ahrefs", timeout=10.0) if rate_limiter else None
    opr_client = rate_limiter.client_for("opr", timeout=10.0) if rate_limiter else None
    wayback = WaybackAdapter(client=wayback_client)
    ahrefs = AhrefsDRAdapter(client=ahrefs_client)
    opr = OPRAdapter(cfg.opr_key, client=opr_client) if cfg.opr_key else None

    search = None
    search_backup = None
    if cfg.google_cse_key and cfg.google_cse_cx:
        g_client = rate_limiter.client_for("google_cse", timeout=10.0) if rate_limiter else None
        search = GoogleCSEAdapter(cfg.google_cse_key, cfg.google_cse_cx, client=g_client)
    if cfg.brave_key:
        b_client = rate_limiter.client_for("brave", timeout=10.0) if rate_limiter else None
        search_backup = BraveAdapter(cfg.brave_key, client=b_client)

    router: ModelRouter | None = None
    import os
    if os.getenv("CECHE_AI_ENABLED", "").lower() in ("1", "true", "yes"):
        router = _build_router(cfg, rate_limiter=rate_limiter)

    return AppraisalEngine(
        rdap=rdap, cache=cache, keyword=keyword,
        search=search, search_backup=search_backup,
        trademark=trademark, wayback=wayback,
        ahrefs=ahrefs, opr=opr, router=router,
    )


ai_cmd = typer.Typer(help="AI key management")
app.add_typer(ai_cmd, name="ai")


@ai_cmd.command(name="key-add")
def key_add(
    provider: str = typer.Option(
        ..., "--provider", "-p",
        help="Provider: deepseek, openai, kimi, glm, minimax",
    ),
    key: str = typer.Option(..., "--key", "-k", help="API key"),
    label: str = typer.Option("", "--label", "-l", help="Optional label"),
    expiry: str = typer.Option("forever", "--expiry", "-e", help="24h, 7d, 30d, 365d, forever"),
) -> None:
    km = KeyManager()
    result = km.add(provider.lower(), key, label, expiry)
    kid = result["key_id"][:8]
    console.print(
        f"[green]Key stored:[/green] {kid}... ({result['provider']}) "
        f"expires: {result['expiry']}"
    )


@ai_cmd.command(name="key-list")
def key_list() -> None:
    km = KeyManager()
    keys = km.list_keys()
    if not keys:
        console.print("[dim]No keys stored.[/dim]")
        return
    for k in keys:
        status = "[red]revoked[/red]" if k["revoked"] else "[green]active[/green]"
        console.print(f"  {k['id'][:8]}... {k['provider']:12s} {k['label']:20s} {status}")


@ai_cmd.command(name="key-remove")
def key_remove(
    key_id: str = typer.Argument(..., help="Key ID to remove"),
) -> None:
    km = KeyManager()
    if km.remove(key_id):
        console.print(f"[green]Key revoked:[/green] {key_id[:8]}...")
    else:
        console.print(f"[red]Key not found:[/red] {key_id[:8]}...")


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
        import contextlib
        from pathlib import Path as _Path
        with contextlib.suppress(FileNotFoundError):
            _Path(cfg.cache_path).unlink()

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


@app.command(name="bulk")
def bulk_cmd(
    domains: list[str] = typer.Argument(
        None, help="Domain(s) to appraise or path to file. If empty, reads from stdin."
    ),
    concurrency: int = typer.Option(
        10, "--concurrency", "-c", min=1, max=100,
        help="Max concurrent domains (default: 10)",
    ),
    fresh: bool = typer.Option(
        False, "--fresh", "-f",
        help="Force recheck — bypass all caches",
    ),
) -> None:
    cfg = Config.load()
    if fresh:
        cfg.fresh = True
        import contextlib
        with contextlib.suppress(FileNotFoundError):
            Path(cfg.cache_path).unlink()

    resolved = _resolve_domains(domains or [])
    all_domains = [d for d in resolved if "." in d]
    if not all_domains:
        console.print("[red]No domains provided.[/red]")
        raise typer.Exit(code=1)

    limiter = RateLimiter()
    engine = _build_engine(cfg, rate_limiter=limiter)
    bulk = BulkAppraisalEngine(engine, concurrency=concurrency, fresh=fresh)

    if sys.stderr.isatty():
        report = _run_with_progress(bulk, all_domains, concurrency)
    else:
        report = _run_with_text_progress(bulk, all_domains)

    _output_bulk_json(report)

    if report.summary.succeeded == 0:
        raise typer.Exit(code=1)


def _run_with_progress(
    bulk: BulkAppraisalEngine, all_domains: list[str], concurrency: int,
) -> BulkReport:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("· {task.fields[failed]} failed · {task.fields[rate]}/s"),
        TimeRemainingColumn(),
        console=Console(stderr=True),
    ) as progress:
        task = progress.add_task(
            f"[cyan]Appraising {len(all_domains)} domains ({concurrency} concurrent)",
            total=len(all_domains),
            failed=0,
            rate="0.0",
        )

        def _on_progress(total: int, succeeded: int, failed: int) -> None:
            progress.update(task, completed=succeeded + failed, failed=failed,
                            rate=f"{succeeded / (progress.tasks[0].elapsed or 0.001):.1f}")

        return asyncio.run(bulk.run(all_domains, on_progress=_on_progress))


def _run_with_text_progress(bulk: BulkAppraisalEngine, all_domains: list[str]) -> BulkReport:
    last_report = [0, 0]  # succeeded, failed

    def _on_progress(total: int, succeeded: int, failed: int) -> None:
        if (succeeded + failed) != (last_report[0] + last_report[1]):
            last_report[0] = succeeded
            last_report[1] = failed
            sys.stderr.write(
                f"\r  {succeeded + failed}/{total} done · "
                f"{failed} failed\n"
            )
            sys.stderr.flush()

    sys.stderr.write(f"Appraising {len(all_domains)} domains\n")
    sys.stderr.flush()
    return asyncio.run(bulk.run(all_domains, on_progress=_on_progress))


def _resolve_domains(args: list[str]) -> list[str]:
    domains: list[str] = []

    if not sys.stdin.isatty():
        stdin_text = sys.stdin.read()
        for line in stdin_text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                domains.append(stripped.lower())

    if len(args) == 1:
        path = Path(args[0])
        if path.is_file():
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    domains.append(stripped.lower())
        else:
            domains.append(args[0].strip().lower())
    elif args:
        for d in args:
            stripped = d.strip().lower()
            if stripped:
                domains.append(stripped)

    seen: set[str] = set()
    result: list[str] = []
    for d in domains:
        if d not in seen:
            seen.add(d)
            result.append(d)
    return result


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


def _output_bulk_json(report: object) -> None:
    from ceche.bulk_engine import BulkReport

    if not isinstance(report, BulkReport):
        console.print(json.dumps({"error": "invalid report type"}, indent=2))
        return

    results_out = []
    for r in report.results:
        results_out.append({
            "domain": r.domain,
            "estimated_value": r.estimated_value,
            "range": {"low": r.range_low, "high": r.range_high},
            "confidence": r.confidence,
            "completeness_ratio": r.completeness_ratio,
            "tld_score": r.tld_score,
            "weight_profile": r.weight_profile,
            "modules": r.modules,
        })

    failures_out = []
    for f in report.failures:
        failures_out.append({
            "domain": f.domain,
            "error_type": f.error_type,
            "error_message": f.error_message,
            "phase": f.phase,
            "traceback": f.traceback_text,
        })

    output = {
        "summary": {
            "total": report.summary.total,
            "succeeded": report.summary.succeeded,
            "failed": report.summary.failed,
            "duration_seconds": report.summary.duration_seconds,
            "rate_domains_per_second": report.summary.rate_domains_per_second,
        },
        "results": results_out,
        "failures": failures_out,
    }
    console.print(json.dumps(output, indent=2, default=str))
