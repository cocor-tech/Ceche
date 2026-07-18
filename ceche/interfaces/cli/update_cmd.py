from __future__ import annotations

import importlib.metadata
import subprocess
import sys

import httpx
import typer
from rich.console import Console

update_app = typer.Typer(help="Check for and install Ceche updates")
console = Console()

_PYPI_URL = "https://pypi.org/pypi/ceche/json"


def _current_version() -> str:
    try:
        return importlib.metadata.version("ceche")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


def _latest_version() -> str | None:
    try:
        resp = httpx.get(_PYPI_URL, timeout=10)
        return resp.json()["info"]["version"]
    except Exception:
        return None


@update_app.callback(invoke_without_command=True)
def update_check(
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Auto-confirm upgrade without prompting",
    ),
) -> None:
    """Check for available Ceche updates"""
    current = _current_version()
    latest = _latest_version()

    console.print(f"  Current: [cyan]{current}[/cyan]")
    if latest:
        console.print(f"  Latest:  [cyan]{latest}[/cyan]")
    else:
        console.print("  [yellow]Could not check PyPI for latest version.[/yellow]")
        raise typer.Exit(code=1)

    if latest == current:
        console.print("  [green]Up to date.[/green]")
        return

    console.print(f"  [yellow]Update available:[/yellow] {current} → {latest}")
    console.print()

    if not yes:
        confirm = typer.confirm("  Upgrade now?", default=False)
        if not confirm:
            console.print("  [dim]Upgrade cancelled.[/dim]")
            return

    console.print(f"  Upgrading from {current} to {latest}...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "ceche"],
        )
        new_ver = _current_version()
        console.print(f"  [green]Upgraded[/green] {current} → {new_ver}")
    except subprocess.CalledProcessError as e:
        console.print(f"  [red]Upgrade failed:[/red] {e}")
        raise typer.Exit(code=1)
