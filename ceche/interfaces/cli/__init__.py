from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

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
from ceche.interfaces.cli.config_cmd import config_app
from ceche.interfaces.output.engine import OutputEngine, OutputOptions

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
    if cfg.ai_enabled:
        router = _build_router(cfg, rate_limiter=rate_limiter)

    return AppraisalEngine(
        rdap=rdap, cache=cache, keyword=keyword,
        search=search, search_backup=search_backup,
        trademark=trademark, wayback=wayback,
        ahrefs=ahrefs, opr=opr, router=router,
    )


ai_cmd = typer.Typer(help="AI key management")
app.add_typer(ai_cmd, name="ai")
app.add_typer(config_app, name="config")


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
    fmt: str = typer.Option("pretty", "--format", "-F",
                         help="Output format: json, jsonl, csv, table, pretty"),
    output: str = typer.Option("", "--output", "-o",
                            help="Write output to file"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output"),
    min_value: float | None = typer.Option(None, "--min-value", help="Minimum estimated value"),
    max_value: float | None = typer.Option(None, "--max-value", help="Maximum estimated value"),
    tld: str | None = typer.Option(None, "--tld", help="Filter by TLD (e.g. com, io)"),
    confidence: str | None = typer.Option(None, "--confidence", help="Filter by confidence level"),
    registered: bool | None = typer.Option(None, "--registered",
        help="Only registered domains"),
    unregistered: bool | None = typer.Option(None, "--unregistered",
        help="Only unregistered domains"),
    brandable: bool | None = typer.Option(None, "--brandable",
        help="Only brandable (no_split) domains"),
    keyword: bool | None = typer.Option(None, "--keyword",
        help="Only keyword (split_found) domains"),
    word_count: int | None = typer.Option(None, "--word-count", help="Filter by exact word count"),
    min_age: float | None = typer.Option(None, "--min-age", help="Minimum domain age in years"),
    max_age: float | None = typer.Option(None, "--max-age", help="Maximum domain age in years"),
    sort: str | None = typer.Option(None, "--sort",
        help="Sort by: value, name, tld, confidence, age, word_count"),
    sort_order: str = typer.Option("asc", "--sort-order", help="asc or desc"),
    limit: int | None = typer.Option(None, "--limit", help="Max results to show"),
    skip: int | None = typer.Option(None, "--skip", help="Skip first N results"),
) -> None:
    cfg = Config.load()
    if fresh:
        cfg.fresh = True
        import contextlib
        with contextlib.suppress(FileNotFoundError):
            Path(cfg.cache_path).unlink()

    engine = _build_engine(cfg)

    all_domains = [d for d in _resolve_domains(domains) if "." in d]
    if not all_domains:
        console.print("[red]No domains provided.[/red]")
        raise typer.Exit(code=1)

    results: list[AppraisalResult] = []
    for domain in all_domains:
        if not quiet:
            sys.stderr.write(f"Appraising {domain}...\n")
        result = asyncio.run(engine.appraise(domain))
        results.append(result)

    if fmt in ("json", "jsonl", "csv"):
        opts = _build_output_opts(fmt, output, min_value, max_value, tld,
                                  confidence, registered, unregistered,
                                  brandable, keyword, word_count,
                                  min_age, max_age, sort, sort_order,
                                  limit, skip)
        eng = OutputEngine(results, opts)
        eng.write()
    elif fmt == "table":
        filtered = _filter_sorted(results, min_value, max_value, tld,
                                  confidence, registered, unregistered,
                                  brandable, keyword, word_count,
                                  min_age, max_age, sort, sort_order,
                                  limit, skip)
        _output_table(filtered)
    else:
        filtered = _filter_sorted(results, min_value, max_value, tld,
                                  confidence, registered, unregistered,
                                  brandable, keyword, word_count,
                                  min_age, max_age, sort, sort_order,
                                  limit, skip)
        _output_pretty(filtered)


@app.command(name="bulk")
def bulk_cmd(
    domains: list[str] = typer.Argument(
        None, help="Domain(s) to appraise or path to file. If empty, reads from stdin."
    ),
    concurrency: int = typer.Option(
        10, "--concurrency", "-c", min=1, max=100,
        help="Max concurrent domains (default: 10 from config)",
    ),
    fresh: bool = typer.Option(
        False, "--fresh", "-f",
        help="Force recheck — bypass all caches",
    ),
    fmt: str = typer.Option("json", "--format", "-F", help="Output format: json, jsonl, csv"),
    output: str = typer.Option("", "--output", "-o", help="Write output to file"),
    min_value: float | None = typer.Option(None, "--min-value", help="Minimum estimated value"),
    max_value: float | None = typer.Option(None, "--max-value", help="Maximum estimated value"),
    tld: str | None = typer.Option(None, "--tld", help="Filter by TLD (e.g. com, io)"),
    confidence: str | None = typer.Option(None, "--confidence", help="Filter by confidence level"),
    registered: bool | None = typer.Option(None, "--registered",
        help="Only registered domains"),
    unregistered: bool | None = typer.Option(None, "--unregistered",
        help="Only unregistered domains"),
    brandable: bool | None = typer.Option(None, "--brandable",
        help="Only brandable (no_split) domains"),
    keyword: bool | None = typer.Option(None, "--keyword",
        help="Only keyword (split_found) domains"),
    word_count: int | None = typer.Option(None, "--word-count", help="Filter by exact word count"),
    min_age: float | None = typer.Option(None, "--min-age", help="Minimum domain age in years"),
    max_age: float | None = typer.Option(None, "--max-age", help="Maximum domain age in years"),
    sort: str | None = typer.Option(None, "--sort",
        help="Sort by: value, name, tld, confidence, age, word_count"),
    sort_order: str = typer.Option("asc", "--sort-order", help="asc or desc"),
    limit: int | None = typer.Option(None, "--limit", help="Max results to show"),
    skip: int | None = typer.Option(None, "--skip", help="Skip first N results"),
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

    if fmt in ("json", "jsonl", "csv"):
        opts = _build_output_opts(fmt, output, min_value, max_value, tld,
                                  confidence, registered, unregistered,
                                  brandable, keyword, word_count,
                                  min_age, max_age, sort, sort_order,
                                  limit, skip)
        eng = OutputEngine(report.results, opts)
        eng.write()
    else:
        out = _build_unified_output(
        report.results, report.failures,
        report.summary.duration_seconds)
        sys.stdout.write(json.dumps(out, indent=2, default=str) + "\n")

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


def _result_to_dict(r: AppraisalResult) -> dict[str, object]:
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
        "modules": r.modules,
        "module_summary": mod_summary,
    }


def _failure_to_dict(f: object) -> dict[str, object]:
    from ceche.bulk_engine import BulkFailure
    if not isinstance(f, BulkFailure):
        return {"domain": "", "error_type": "Unknown", "error_message": str(f)}
    return {
        "domain": f.domain,
        "error_type": f.error_type,
        "error_message": f.error_message,
        "phase": f.phase,
        "traceback": f.traceback_text,
    }


def _build_unified_output(
    results: list[AppraisalResult],
    failures: Sequence[object] | None = None,
    duration_seconds: float = 0.0,
) -> dict[str, object]:
    succeeded = len(results)
    failed = len(failures) if failures else 0
    total = succeeded + failed
    version = results[0].version if results else ""
    generated_at = results[0].generated_at if results else ""
    rate = succeeded / duration_seconds if duration_seconds > 0 and succeeded > 0 else 0.0

    agg_mod_summary: dict[str, int] = {}
    for r in results:
        for me in r.modules.values():
            s = me.get("status", "UNKNOWN")
            agg_mod_summary[s] = agg_mod_summary.get(s, 0) + 1

    return {
        "version": version,
        "generated_at": generated_at,
        "summary": {
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "duration_seconds": round(duration_seconds, 2),
            "rate_domains_per_second": round(rate, 2),
        },
        "module_summary": agg_mod_summary,
        "results": [_result_to_dict(r) for r in results],
        "failures": [_failure_to_dict(f) for f in (failures or [])],
    }


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
        sys.stdout.write(json.dumps({"error": "invalid report type"}, indent=2) + "\n")
        return

    results_out = [_result_to_dict(r) for r in report.results]
    failures_out = [_failure_to_dict(f) for f in report.failures]

    agg_mod_summary: dict[str, int] = {}
    for r in report.results:
        for me in r.modules.values():
            s = me.get("status", "UNKNOWN")
            agg_mod_summary[s] = agg_mod_summary.get(s, 0) + 1

    output = {
        "version": report.results[0].version if report.results else "",
        "generated_at": report.results[0].generated_at if report.results else "",
        "summary": {
            "total": report.summary.total,
            "succeeded": report.summary.succeeded,
            "failed": report.summary.failed,
            "duration_seconds": report.summary.duration_seconds,
            "rate_domains_per_second": report.summary.rate_domains_per_second,
        },
        "module_summary": agg_mod_summary,
        "results": results_out,
        "failures": failures_out,
    }
    sys.stdout.write(json.dumps(output, indent=2, default=str) + "\n")


def _build_output_opts(
    fmt: str, output: str,
    min_value: float | None, max_value: float | None,
    tld: str | None, confidence: str | None,
    registered: bool | None, unregistered: bool | None,
    brandable: bool | None, keyword: bool | None,
    word_count: int | None,
    min_age: float | None, max_age: float | None,
    sort: str | None, sort_order: str,
    limit: int | None, skip: int | None,
) -> OutputOptions:
    return OutputOptions(
        format=fmt, output=output,
        min_value=min_value, max_value=max_value,
        tld=tld, confidence=confidence,
        registered=registered, unregistered=unregistered,
        brandable=brandable, keyword=keyword,
        word_count=word_count,
        min_age=min_age, max_age=max_age,
        sort=sort, sort_order=sort_order,
        limit=limit, skip=skip,
    )


def _filter_sorted(
    results: list[AppraisalResult],
    min_value: float | None, max_value: float | None,
    tld: str | None, confidence: str | None,
    registered: bool | None, unregistered: bool | None,
    brandable: bool | None, keyword: bool | None,
    word_count: int | None,
    min_age: float | None, max_age: float | None,
    sort: str | None, sort_order: str,
    limit: int | None, skip: int | None,
) -> list[AppraisalResult]:
    from ceche.interfaces.output.filters import FilterOptions, apply_filters
    opts = FilterOptions(
        min_value=min_value, max_value=max_value,
        tld=tld, confidence=confidence,
        registered=registered, unregistered=unregistered,
        brandable=brandable, keyword=keyword,
        word_count=word_count,
        min_age=min_age, max_age=max_age,
        sort=sort, sort_order=sort_order,
        limit=limit, skip=skip,
    )
    return apply_filters(results, opts)
