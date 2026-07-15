from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

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
from ceche.infrastructure.rdap.rdap_adapter import RDAPAdapter
from ceche.infrastructure.search.brave_adapter import BraveAdapter
from ceche.infrastructure.search.google_cse_adapter import GoogleCSEAdapter
from ceche.infrastructure.trademark.uspto_adapter import USPTOAdapter

app = typer.Typer(name="ceche", help="Domain Appraisal Engine")
console = Console()


def _build_router(cfg: Config) -> ModelRouter | None:
    import os

    router = ModelRouter()

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
        if mod_provider and mod_provider in router.providers:
            router.assign_modules(
                [module], mod_provider, model=mod_model,
                temperature=temperature, max_tokens=max_tokens,
            )
        elif mod_model:
            router.assign_modules(
                [module], primary, model=mod_model,
                temperature=temperature, max_tokens=max_tokens,
            )
        else:
            router.assign_modules(
                [module], primary,
                temperature=temperature, max_tokens=max_tokens,
            )

    return router


def _build_engine(cfg: Config) -> AppraisalEngine:
    cache = SQLiteCacheAdapter(cfg.cache_path)
    rdap = RDAPAdapter()
    keyword = StaticKeywordAdapter()
    trademark = USPTOAdapter()
    wayback = WaybackAdapter()
    ahrefs = AhrefsDRAdapter()
    opr = OPRAdapter(cfg.opr_key) if cfg.opr_key else None

    search = None
    search_backup = None
    if cfg.google_cse_key and cfg.google_cse_cx:
        search = GoogleCSEAdapter(cfg.google_cse_key, cfg.google_cse_cx)
    if cfg.brave_key:
        search_backup = BraveAdapter(cfg.brave_key)

    router: ModelRouter | None = None
    import os
    if os.getenv("CECHE_AI_ENABLED", "").lower() in ("1", "true", "yes"):
        router = _build_router(cfg)

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


def _resolve_domains(args: list[str]) -> list[str]:
    if len(args) == 1:
        path = Path(args[0])
        if path.is_file():
            return [
                line.strip()
                for line in path.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
    return [d.strip().lower() for d in args if d.strip()]


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
