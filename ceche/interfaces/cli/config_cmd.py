from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ceche.infrastructure.config.loader import ConfigLoader
from ceche.infrastructure.config.store import ConfigStore

config_app = typer.Typer(help="Manage Ceche configuration")
console = Console()

_STORE = ConfigStore()
_LOADER = ConfigLoader()


@config_app.callback(invoke_without_command=True)
def config_main(
    fmt: str = typer.Option("table", "--format", "-F", help="Output format: table, json"),
) -> None:
    cfg = _LOADER.load()
    if fmt == "json":
        console.print(json.dumps(vars(cfg), indent=2, default=str))
    else:
        table = Table(title="Ceche Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Source", style="dim")
        for key in vars(cfg):
            val = getattr(cfg, key)
            source = "env" if _is_from_env(key) else "file" if _STORE.config_exists() else "default"
            table.add_row(key, str(val), source)
        console.print(table)


@config_app.command(name="path")
def config_path() -> None:
    console.print(f"  Global:  {_STORE.global_path}")
    console.print(f"  Project: {_STORE.project_path}")


@config_app.command(name="set")
def config_set(
    key: str = typer.Argument(..., help="Config key"),
    value: str = typer.Argument(..., help="Config value"),
    global_: bool = typer.Option(False, "--global", "-g", help="Write to global config"),
) -> None:
    path = _STORE.set(key, value, global_=global_)
    console.print(f"[green]Set[/green] {key} = {value} in {path.name}")


@config_app.command(name="reset")
def config_reset(
    global_: bool = typer.Option(False, "--global", "-g", help="Reset global config"),
) -> None:
    _STORE.reset(global_=global_)
    label = "Global" if global_ else "Project"
    console.print(f"[yellow]{label} config reset to defaults.[/yellow]")


@config_app.command(name="import")
def config_import(
    source: str = typer.Argument(..., help="Path to TOML file"),
    global_: bool = typer.Option(False, "--global", "-g", help="Import to global config"),
) -> None:
    path = _STORE.import_config(Path(source), global_=global_)
    console.print(f"[green]Imported[/green] {source} → {path}")


@config_app.command(name="export")
def config_export(
    dest: str = typer.Argument(None, help="Output path (default: stdout)"),
    global_: bool = typer.Option(False, "--global", "-g", help="Export global config"),
) -> None:
    if dest:
        path = _STORE.export_config(Path(dest), global_=global_)
        console.print(f"[green]Exported[/green] → {path}")
    else:
        source = _STORE.global_path if global_ else _STORE.project_path
        if not source.is_file():
            console.print("[yellow]No config file found.[/yellow]")
        else:
            sys.stdout.write(source.read_text() + "\n")


profile_app = typer.Typer(help="Manage configuration profiles", hidden=True)
config_app.add_typer(profile_app, name="profile")


@profile_app.command(name="list")
def profile_list() -> None:
    profiles_dir = Path.home() / ".config" / "ceche" / "profiles"
    if not profiles_dir.is_dir():
        console.print("[dim]No profiles found.[/dim]")
        return
    for p in sorted(profiles_dir.iterdir()):
        if p.suffix == ".toml":
            console.print(f"  {p.stem}")


@profile_app.command(name="create")
def profile_create(
    name: str = typer.Argument(..., help="Profile name"),
    source: str = typer.Option("", "--from", "-f", help="Copy from existing profile or config"),
) -> None:
    profiles_dir = Path.home() / ".config" / "ceche" / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    target = profiles_dir / f"{name}.toml"
    if target.is_file():
        console.print(f"[red]Profile {name} already exists.[/red]")
        raise typer.Exit(code=1)
    if source:
        src_path = Path(source)
        if src_path.is_file():
            target.write_text(src_path.read_text())
        else:
            src_profile = profiles_dir / f"{source}.toml"
            if src_profile.is_file():
                target.write_text(src_profile.read_text())
            else:
                console.print(f"[red]Source {source} not found.[/red]")
                raise typer.Exit(code=1)
    target.write_text("# Profile: " + name + "\n")
    console.print(f"[green]Profile {name} created.[/green]")


@profile_app.command(name="use")
def profile_use(
    name: str = typer.Argument(..., help="Profile name"),
) -> None:
    profiles_dir = Path.home() / ".config" / "ceche" / "profiles"
    target = profiles_dir / f"{name}.toml"
    if not target.is_file():
        console.print(f"[red]Profile {name} not found.[/red]")
        raise typer.Exit(code=1)
    cfg_path = _STORE.project_path
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(f'# Use profile: {name}\nprofile = "{name}"\n')
    console.print(f"[green]Profile {name} set for this project.[/green]")


@profile_app.command(name="delete")
def profile_delete(
    name: str = typer.Argument(..., help="Profile name"),
) -> None:
    profiles_dir = Path.home() / ".config" / "ceche" / "profiles"
    target = profiles_dir / f"{name}.toml"
    if not target.is_file():
        console.print(f"[red]Profile {name} not found.[/red]")
        raise typer.Exit(code=1)
    target.unlink()
    console.print(f"[yellow]Profile {name} deleted.[/yellow]")


def _is_from_env(key: str) -> bool:
    import os
    mapping = {
        "google_cse_key": "CECHE_GOOGLE_CSE_KEY",
        "google_cse_cx": "CECHE_GOOGLE_CSE_CX",
        "brave_key": "CECHE_BRAVE_KEY",
        "opr_key": "CECHE_OPR_KEY",
        "cache_path": "CECHE_CACHE_PATH",
        "fresh": "CECHE_FRESH",
        "concurrency": "CECHE_CONCURRENCY",
        "format": "CECHE_FORMAT",
        "cache_enabled": "CECHE_CACHE_ENABLED",
        "ai_enabled": "CECHE_AI_ENABLED",
        "ai_temperature": "CECHE_AI_TEMPERATURE",
        "ai_max_tokens": "CECHE_AI_MAX_TOKENS",
    }
    env_key = mapping.get(key)
    return bool(env_key and os.getenv(env_key) is not None)
