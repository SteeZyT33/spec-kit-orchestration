from __future__ import annotations

import argparse
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Footer, Static

from orca.tui.fleet import FleetTable
from orca.tui.models import FleetRow


class FleetApp(App):
    """Top-level TUI app."""

    TITLE = "orca"
    SUB_TITLE = "fleet"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        ("q", "quit", "quit"),
        ("g", "refresh", "refresh"),
    ]
    CSS_PATH = "theme.tcss"

    def __init__(self, repo_root: Path, read_only: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.repo_root = repo_root
        self.read_only = read_only
        self._rows: list[FleetRow] = []

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield FleetTable(id="fleet")
        yield Static("", id="status-line")
        yield Footer()

    def set_rows(self, rows: list[FleetRow]) -> None:
        self._rows = list(rows)
        self.query_one(FleetTable).set_rows(rows)
        self._update_status_line()

    def _update_status_line(self) -> None:
        n = len(self._rows)
        stale = sum(1 for r in self._rows if r.state == "stale")
        merged = sum(1 for r in self._rows if r.state == "merged")
        line = f"  {n} lanes · {stale} stale · {merged} ready-to-merge"
        self.query_one("#status-line", Static).update(line)

    def action_refresh(self) -> None:
        self._collect_and_set()

    def on_mount(self) -> None:
        from orca.tui.watcher import Watcher
        self._collect_and_set()
        self._watcher = Watcher(
            self.repo_root,
            on_change=lambda _p: self.call_from_thread(self._collect_and_set),
        )

    def on_unmount(self) -> None:
        w = getattr(self, "_watcher", None)
        if w is not None:
            w.stop()

    def _collect_and_set(self) -> None:
        from orca.tui.collect import collect_fleet
        from orca.tui.actions import (
            tmux_alive, branch_merged, last_event, last_setup_failed,
        )
        try:
            rows = collect_fleet(
                self.repo_root,
                tmux_alive=tmux_alive,
                branch_merged=lambda b, base: branch_merged(self.repo_root, b, base),
                last_event=lambda lid: last_event(self.repo_root, lid),
                last_setup_failed=lambda lid: last_setup_failed(self.repo_root, lid),
            )
            self.set_rows(rows)
        except Exception:
            self.set_rows([])


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="orca-tui")
    p.add_argument("--repo-root", default=".", help="Path to repo root")
    p.add_argument("--read-only", action="store_true",
                   help="Suppress mutating actions (r/n/d)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    FleetApp(repo_root=Path(args.repo_root).resolve(),
             read_only=args.read_only).run()
    return 0
