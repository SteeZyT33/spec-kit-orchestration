from __future__ import annotations

import argparse
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Footer, Static


class FleetApp(App):
    """Top-level TUI app. Phase 0: empty shell that launches and quits."""

    BINDINGS = [("q", "quit", "quit")]
    CSS_PATH = "theme.tcss"

    def __init__(self, repo_root: Path, read_only: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.repo_root = repo_root
        self.read_only = read_only

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Static("orca tui v3 — scaffold", id="placeholder")
        yield Footer()


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
