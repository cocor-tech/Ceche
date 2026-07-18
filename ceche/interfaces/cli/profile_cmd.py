from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from ceche.infrastructure.config.store import ConfigStore

console = Console()
_STORE = ConfigStore()
_PROFILES_DIR = Path.home() / ".config" / "ceche" / "profiles"


def register(app: typer.Typer) -> None:
    """Register profile commands on the given Typer app."""

    @app.command(name="profiles")
    def profile_list() -> None:
        """List available configuration profiles"""
        if not _PROFILES_DIR.is_dir():
            console.print("[dim]No profiles found.[/dim]")
            return
        for p in sorted(_PROFILES_DIR.iterdir()):
            if p.suffix == ".toml":
                console.print(f"  {p.stem}")

    @app.command(name="profile-create")
    def profile_create(
        name: str = typer.Argument(..., help="Profile name"),
    ) -> None:
        """Create a new configuration profile"""
        _PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        target = _PROFILES_DIR / f"{name}.toml"
        if target.is_file():
            console.print(f"[red]Profile '{name}' already exists.[/red]")
            raise typer.Exit(code=1)
        target.write_text("# Profile: " + name + "\n")
        console.print(f"[green]Profile '{name}' created.[/green]")

    @app.command(name="profile-use")
    def profile_use(
        name: str = typer.Argument(..., help="Profile name"),
    ) -> None:
        """Activate a profile for the current project"""
        target = _PROFILES_DIR / f"{name}.toml"
        if not target.is_file():
            console.print(f"[red]Profile '{name}' not found.[/red]")
            raise typer.Exit(code=1)
        cfg_path = _STORE.project_path
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(f'profile = "{name}"\n')
        console.print(f"[green]Profile '{name}' activated.[/green]")

    @app.command(name="profile-delete")
    def profile_delete(
        name: str = typer.Argument(..., help="Profile name"),
    ) -> None:
        """Delete a configuration profile"""
        target = _PROFILES_DIR / f"{name}.toml"
        if not target.is_file():
            console.print(f"[red]Profile '{name}' not found.[/red]")
            raise typer.Exit(code=1)
        target.unlink()
        console.print(f"[yellow]Profile '{name}' deleted.[/yellow]")