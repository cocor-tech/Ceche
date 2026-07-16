from __future__ import annotations

import typer
from rich.console import Console

server_app = typer.Typer(help="Start Ceche server")
console = Console()


@server_app.command(name="serve")
def server_serve(
    port: int = typer.Option(8080, "--port", "-p", help="Port to listen on"),
    host: str = typer.Option("127.0.0.1", "--host", "-H", help="Host to bind to"),
) -> None:
    """Start the Ceche HTTP API server."""
    import uvicorn

    from ceche.interfaces.api import create_app

    app = create_app()
    console.print(f"[green]Ceche API server[/green] → http://{host}:{port}")
    console.print(f"[dim]Docs:[/dim] http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port)


@server_app.command(name="web")
def server_web(
    port: int = typer.Option(8080, "--port", "-p", help="Port to listen on"),
    host: str = typer.Option("127.0.0.1", "--host", "-H", help="Host to bind to"),
) -> None:
    """Start server and open web dashboard."""
    import threading

    import uvicorn

    from ceche.interfaces.api import create_app

    app = create_app()
    url = f"http://{host}:{port}"

    def open_browser() -> None:
        import time
        time.sleep(1.5)
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()
    console.print(f"[green]Ceche Web Dashboard[/green] → {url}")
    uvicorn.run(app, host=host, port=port)


@server_app.command(name="tui")
def server_tui(
    port: int = typer.Option(8080, "--port", "-p", help="Port to listen on"),
) -> None:
    """Start a headless API server (no dashboard)."""
    import uvicorn

    from ceche.interfaces.api import create_app

    app = create_app()
    console.print(f"[green]Ceche API[/green] → http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
