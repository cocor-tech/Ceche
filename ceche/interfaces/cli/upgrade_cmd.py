from __future__ import annotations

import importlib.metadata
import subprocess
import sys

import httpx
import typer
from rich.console import Console

upgrade_app = typer.Typer(help="Update Ceche to the latest version")
console = Console()

_PYPI_JSON = "https://pypi.org/pypi/ceche/json"


@upgrade_app.command(name="check")
def upgrade_check() -> None:
    current = importlib.metadata.version("ceche")
    console.print(f"  Current: [cyan]{current}[/cyan]")
    try:
        resp = httpx.get(_PYPI_JSON, timeout=10)
        latest = resp.json()["info"]["version"]
        console.print(f"  Latest:  [cyan]{latest}[/cyan]")
        if latest != current:
            console.print(f"  [yellow]Update available:[/yellow] {current} → {latest}")
            console.print("  Run [bold]ceche upgrade install[/bold] to update")
        else:
            console.print("  [green]Up to date.[/green]")
    except Exception as e:
        console.print(f"  [red]Check failed:[/red] {e}")


@upgrade_app.command(name="install")
def upgrade_install(
    method: str = typer.Option("pip", "--method", "-m", help="Install method: pip, pipx"),
) -> None:
    current = importlib.metadata.version("ceche")
    console.print(f"[yellow]Upgrading[/yellow] {current} → latest (via {method})...")
    try:
        if method == "pipx":
            subprocess.check_call([sys.executable, "-m", "pipx", "upgrade", "ceche"])
        else:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--upgrade", "ceche[cli]"]
            )
        new_ver = importlib.metadata.version("ceche")
        console.print(f"[green]Upgraded[/green] {current} → {new_ver}")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Upgrade failed:[/red] {e}")
        raise typer.Exit(code=1)
