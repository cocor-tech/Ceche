from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ceche.config import Config

cache_app = typer.Typer(help="Manage Ceche cache")
console = Console()


@cache_app.callback(invoke_without_command=True)
def cache_main() -> None:
    cfg = Config.load()
    cache_path = Path(cfg.cache_path)
    if cache_path.is_file():
        size = cache_path.stat().st_size
        console.print(f"  Path:  {cache_path.resolve()}")
        console.print(f"  Size:  {_fmt_size(size)}")
    else:
        console.print("[dim]No cache file found.[/dim]")


@cache_app.command(name="clear")
def cache_clear(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    if not force:
        console.print("[yellow]Use --force to confirm cache clear.[/yellow]")
        return
    cfg = Config.load()
    cache_path = Path(cfg.cache_path)
    if cache_path.is_file():
        cache_path.unlink()
        console.print(f"[yellow]Cache cleared:[/yellow] {cache_path}")
    else:
        console.print("[dim]No cache file found.[/dim]")


@cache_app.command(name="stats")
def cache_stats() -> None:
    cfg = Config.load()
    cache_path = Path(cfg.cache_path)
    if not cache_path.is_file():
        console.print("[dim]No cache file found.[/dim]")
        return
    size = cache_path.stat().st_size
    import sqlite3
    try:
        conn = sqlite3.connect(str(cache_path))
        count = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        expired = conn.execute(
            "SELECT COUNT(*) FROM cache WHERE expires_at < strftime('%s','now')",
        ).fetchone()[0]
        conn.close()
    except Exception:
        count = 0
        expired = 0
    table = Table(title="Cache Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Path", str(cache_path.resolve()))
    table.add_row("Size", _fmt_size(size))
    table.add_row("Entries", str(count))
    table.add_row("Expired", str(expired))
    console.print(table)


@cache_app.command(name="ttl")
def cache_ttl(
    ttl: int = typer.Argument(..., help="TTL in seconds"),
    provider: str = typer.Option("rdap", "--provider", "-p", help="Adapter provider"),
) -> None:
    import os as _os
    env_key = f"CECHE_{provider.upper()}_CACHE_TTL"
    _os.environ[env_key] = str(ttl)
    console.print(f"[green]Set[/green] {provider} cache TTL = {ttl}s "
                  f"(env: {env_key})")


def _fmt_size(size: int) -> str:
    s = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if s < 1024:
            return f"{s:.1f} {unit}"
        s /= 1024
    return f"{s:.1f} TB"
