"""Drill-down: lane metadata + recent events."""
from __future__ import annotations

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from orca.tui.models import FleetRow


def load_recent_events(repo_root: Path, lane_id: str, n: int = 20) -> list[dict]:
    """Return last n events for the given lane, newest first."""
    path = repo_root / ".orca" / "worktrees" / "events.jsonl"
    if not path.exists():
        return []
    matches: list[dict] = []
    with path.open() as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("lane_id") == lane_id:
                matches.append(entry)
    return list(reversed(matches[-n:]))


class LaneScreen(Screen):
    """Single-lane drill-down. Esc returns."""

    BINDINGS = [("escape", "app.pop_screen", "back")]

    def __init__(self, repo_root: Path, row: FleetRow, **kwargs) -> None:
        super().__init__(**kwargs)
        self.repo_root = repo_root
        self.row = row

    def compose(self) -> ComposeResult:  # type: ignore[override]
        meta_lines = [
            f"path     {self.row.worktree_path}",
            f"branch   {self.row.branch}",
            f"agent    {self.row.agent}",
            f"state    {self.row.state}  ({self.row.last_seen})",
            f"feature  {self.row.feature_id or '-'}",
            f"done     {self.row.done.strip()}",
        ]
        if self.row.health:
            meta_lines.append(f"health   {self.row.health}")
        yield Static("\n".join(meta_lines), id="lane-meta")

        events = load_recent_events(self.repo_root, self.row.lane_id)
        if not events:
            body = "(no events)"
        else:
            body = "\n".join(
                f"{e.get('ts', '?'):26s}  {e.get('event', '?'):24s}  "
                f"{e.get('agent', '')}"
                for e in events
            )
        yield Vertical(
            Static("RECENT EVENTS", classes="label"),
            Static(body),
            id="lane-events",
        )
        yield Footer()
