from __future__ import annotations

import asyncio
import json
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import Provider
from textual.containers import Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Static,
)

from ceche.config import Config
from ceche.infrastructure.persistence.store import AppraisalStore


class CecheTUI(App[None]):
    """Ceche Terminal User Interface."""

    CSS = """
    Screen {
        layout: horizontal;
    }

    Sidebar {
        width: 24;
        height: 100%;
        background: $panel;
        border-right: solid $primary;
        display: none;
    }

    Sidebar.visible {
        display: block;
    }

    .sidebar-title {
        padding: 1;
        text-style: bold;
        color: $primary;
    }

    .sidebar-entry {
        padding: 0 1;
        height: 3;
    }

    .sidebar-entry:hover {
        background: $accent 20%;
    }

    .sidebar-entry .domain {
        text-style: bold;
    }

    .sidebar-entry .value {
        color: $success;
    }

    MainContent {
        width: 1fr;
        height: 100%;
    }

    #logo {
        content-align: center middle;
        padding: 2;
        text-style: bold;
        color: $primary;
    }

    #input-area {
        padding: 0 2;
        height: auto;
    }

    #domain-input {
        margin: 0 1;
    }

    #result-area {
        padding: 1 2;
        height: auto;
    }

    #value-card {
        height: 5;
        padding: 1;
        background: $boost;
    }

    .value-amount {
        text-style: bold;
        color: $success;
        padding: 0 1;
    }

    .value-range {
        color: $text-muted;
        padding: 0 1;
    }

    .value-confidence {
        padding: 0 1;
    }

    #module-table {
        height: auto;
        margin: 1 0;
    }

    #new-domain-btn {
        margin: 1 2;
        width: 20;
    }

    #status-bar {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "quit", show=True),
        Binding("escape", "new_domain", "new", show=True),
        Binding("ctrl+p", "command_palette", "commands", show=True),
        Binding("tab", "toggle_view", "toggle", show=True),
    ]

    sidebar_visible: reactive[bool] = reactive(False)

    def __init__(self, fresh: bool = False) -> None:
        super().__init__()
        self._fresh = fresh
        cfg = Config.load()
        from ceche.interfaces.cli import _build_engine
        self._engine = _build_engine(cfg)
        self._store = AppraisalStore()
        self._current_result: dict[str, Any] | None = None
        self._view_mode: str = "modules"  # modules or json

    def compose(self) -> ComposeResult:
        yield Sidebar(classes="visible" if self.sidebar_visible else "")
        with Vertical(id="main-content"):
            yield Logo()
            yield InputArea()
            yield ResultArea()
            yield StatusBar()

    def on_mount(self) -> None:
        self._update_sidebar_visibility()
        self.refresh_sidebar()

    def on_resize(self, event: Any) -> None:
        self._update_sidebar_visibility()

    def _update_sidebar_visibility(self) -> None:
        wide = self.size.width >= 120
        self.sidebar_visible = wide
        sidebar = self.query_one(Sidebar)
        sidebar.set_class(wide, "visible")

    def refresh_sidebar(self) -> None:
        sidebar = self.query_one(Sidebar)
        sidebar.refresh_entries()

    async def action_new_domain(self) -> None:
        self._current_result = None
        self._view_mode = "modules"
        input_area = self.query_one(InputArea)
        result_area = self.query_one(ResultArea)
        input_area.show_input()
        result_area.clear()

    async def action_toggle_view(self) -> None:
        if self._current_result is None:
            return
        self._view_mode = "json" if self._view_mode == "modules" else "modules"
        result_area = self.query_one(ResultArea)
        result_area.show_result(self._current_result)

    async def on_input_submitted(self, message: Input.Changed) -> None:
        """Called when Enter is pressed in the domain input."""
        if not message.value.strip():
            return
        domain = message.value.strip().lower()
        if "." not in domain:
            domain = f"{domain}.com"

        input_area = self.query_one(InputArea)
        result_area = self.query_one(ResultArea)

        input_area.show_loading()

        try:
            result = await self._engine.appraise(domain, fresh=self._fresh)
        except Exception as e:
            result_area.show_error(str(e))
            input_area.show_button()
            return

        data = {
            "domain": result.domain,
            "estimated_value": result.estimated_value,
            "range_low": result.range_low,
            "range_high": result.range_high,
            "confidence": result.confidence,
            "completeness_ratio": result.completeness_ratio,
            "tld_score": result.tld_score,
            "weight_profile": result.weight_profile,
            "modules": result.modules,
            "version": result.version,
            "generated_at": result.generated_at,
        }

        self._current_result = data
        self._store.record_run(
            [domain], [result], [], fresh=self._fresh, command="tui",
        )
        result_area.show_result(data)
        input_area.show_button()
        self.refresh_sidebar()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "new-domain-btn":
            asyncio.create_task(self.action_new_domain())

    def on_sidebar_sessions_changed(self) -> None:
        self.refresh_sidebar()


class Logo(Static):
    def compose(self) -> ComposeResult:
        yield Static("⚡ ceche", id="logo")


class InputArea(Vertical):
    """Domain input area that transforms into a button after appraisal."""

    def compose(self) -> ComposeResult:
        self._input = Input(
            placeholder="Enter domain (e.g. example.com)",
            id="domain-input",
        )
        self._button = Button("✓ Check new domain", id="new-domain-btn", variant="primary")
        self._button.display = False
        yield self._input
        yield self._button
        yield Static("", id="loading")

    def show_input(self) -> None:
        self._input.display = True
        self._button.display = False
        self._input.value = ""
        self._input.focus()

    def show_button(self) -> None:
        self._input.display = False
        self._button.display = True
        self._button.focus()

    def show_loading(self) -> None:
        self._input.display = False
        self._button.display = False


class ResultArea(VerticalScroll):
    """Displays appraisal results - value card + module table or JSON."""

    def compose(self) -> ComposeResult:
        yield Vertical(id="value-card")
        yield DataTable(id="module-table")
        yield Static("", id="json-view")

    def clear(self) -> None:
        card = self.query_one("#value-card")
        card.remove_children()
        self.query_one("#module-table").display = False
        self.query_one("#json-view").display = False

    def show_result(self, data: dict[str, Any]) -> None:
        self.clear()
        self._show_value_card(data)
        self._show_modules(data)

    def show_error(self, msg: str) -> None:
        self.clear()
        self.query_one("#value-card").mount(
            Static(f"[red]Error:[/red] {msg}")
        )

    def _show_value_card(self, data: dict[str, Any]) -> None:
        card = self.query_one("#value-card")
        val = data.get("estimated_value")
        lo = data.get("range_low")
        hi = data.get("range_high")
        conf = data.get("confidence", "--")
        domain = data.get("domain", "")

        val_str = f"${val:,.0f}" if val else "--"
        range_str = f"${lo:,.0f} - ${hi:,.0f}" if lo and hi else "--"

        card.mount(Static(f"[bold cyan]{domain}[/bold cyan]", id="card-domain"))
        card.mount(Static(f"[bold green]{val_str}[/bold green]", classes="value-amount"))
        card.mount(Static(f"[dim]Range: {range_str}[/dim]", classes="value-range"))
        card.mount(Static(f"[dim]Confidence: {conf}[/dim]", classes="value-confidence"))

    def _show_modules(self, data: dict[str, Any]) -> None:
        import typing
        app: CecheTUI = typing.cast(CecheTUI, self.app)
        modules = data.get("modules", {})
        view_mode = getattr(app, "_view_mode", "modules")

        if view_mode == "json":
            json_view = self.query_one("#json-view", Static)
            json_view.display = True
            json_view.update(json.dumps(data, indent=2, default=str))
            self.query_one("#module-table").display = False
            return

        table = self.query_one("#module-table", DataTable)
        table.display = True
        table.clear(columns=True)

        table.add_columns("Module", "Status", "Raw Mult", "Impact %", "Effect")

        for name, mod in modules.items():
            status = mod.get("status", "--")
            mult = mod.get("multiplier", mod.get("score", ""))

            if name == "m15_pricing":
                bd = mod.get("breakdown", {})
                for bname, bentry in bd.items():
                    if bentry and isinstance(bentry, dict):
                        emult = bentry.get("multiplier", "")
                        eimpact = bentry.get("impact", "")
                        eeffect = bentry.get("effect", "")
                        ename = bname.replace("m", "M").replace("_", "-")
                        table.add_row(
                            ename,
                            mod.get("status", ""),
                            str(emult) if emult else "",
                            f"{eimpact:.1f}%" if isinstance(eimpact, (int, float)) else "",
                            eeffect or "",
                        )
                continue

            table.add_row(
                name.replace("m", "M").replace("_", "-"),
                status,
                str(mult) if mult else "",
                "",
                "",
            )


class Sidebar(Vertical):
    """Recent sessions sidebar (4 domains + history link)."""

    def compose(self) -> ComposeResult:
        yield Static("Recent", classes="sidebar-title")
        self._entries: list[Static] = []
        for _ in range(4):
            entry = Static("", classes="sidebar-entry")
            self._entries.append(entry)
            yield entry
        yield Button("View full history", id="history-btn")

    def refresh_entries(self) -> None:
        import typing
        app: CecheTUI = typing.cast(CecheTUI, self.app)
        store = getattr(app, "_store", None)
        if not store:
            return
        try:
            runs = store.list_runs(days=7)
            domains: list[tuple[str, float | None]] = []
            for run in runs[:4]:
                import sqlite3
                conn = sqlite3.connect(store.db_path)
                try:
                    apps = conn.execute(
                        "SELECT domain, estimated_value FROM appraisals "
                        "WHERE run_id = ? ORDER BY created_at DESC LIMIT 4",
                        (run["id"],),
                    ).fetchall()
                    for d, v in apps:
                        domains.append((d.strip().lower(), v))
                finally:
                    conn.close()

            for i, (domain, val) in enumerate(domains[:4]):
                val_str = f"${val:,.0f}" if val else "--"
                name = domain if len(domain) <= 18 else domain[:15] + ".."
                self._entries[i].update(
                    f"[bold]{name}[/bold]\n[green]{val_str}[/green]"
                )
            for i in range(len(domains), 4):
                self._entries[i].update("")
        except Exception:
            pass


class StatusBar(Static):
    def compose(self) -> ComposeResult:
        yield Static(
            "  Ctrl+P commands  Tab toggle  Esc new domain  Ctrl+Q quit",
            id="status-bar",
        )


class CecheCommandProvider(Provider):
    """Command palette entries for Ceche TUI."""

    async def search(self, query: str) -> list[Any]:  # type: ignore[override]
        from textual.command import Hit
        from textual.widgets import Static as _S

        commands = [
            ("Check domain", "check <domain>"),
            ("View history", "ceche history"),
            ("View stats", "ceche stats"),
            ("Open portfolio", "ceche portfolio <name>"),
            ("Configure", "ceche config set <key> <value>"),
            ("Toggle view", "tab toggle modules/json"),
            ("New domain", "escape clear result"),
            ("Quit", "ctrl+q exit"),
        ]

        matches = []
        for title, help_text in commands:
            if query.lower() in title.lower() or query.lower() in help_text.lower():
                matches.append(Hit(
                    0, title, lambda: None, help=help_text,
                ))
        return matches
