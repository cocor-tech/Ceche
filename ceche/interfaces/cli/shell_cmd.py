from __future__ import annotations

import typer
from rich.console import Console

shell_app = typer.Typer(help="Generate shell completion scripts")
console = Console()


@shell_app.command(name="generate")
def shell_generate(
    shell: str = typer.Argument("bash", help="Shell type: bash, zsh, fish"),
) -> None:
    import subprocess
    import sys

    try:
        result = subprocess.run(
            [sys.executable, "-m", "typer", "ceche.interfaces.cli", "utils", "completion", "--name", "ceche", "--shell", shell],
            capture_output=True, text=True, check=True,
        )
        print(result.stdout)
    except subprocess.CalledProcessError:
        # Fallback — just tell user
        console.print(f"[yellow]To enable {shell} completion:[/yellow]")
        if shell == "bash":
            console.print("  eval \"$(_CEHE_COMPLETE=bash_source ceche)\"")
        elif shell == "zsh":
            console.print("  eval \"$(_CEHE_COMPLETE=zsh_source ceche)\"")
        elif shell == "fish":
            console.print("  ceche --help | grep -q fish || true; and eval (env _CEHE_COMPLETE=fish_source ceche)")
