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
        # 1. Metadata block
        meta_lines = [
            f"{self.row.lane_id} · {self.row.agent} · {self.row.state}",
            "",
            f"path     {self.row.worktree_path}",
            f"branch   {self.row.branch}",
            f"feature  {self.row.feature_id or '-'}",
            f"done     {self.row.done.strip()}",
            f"seen     {self.row.last_seen}",
        ]
        if self.row.health:
            meta_lines.append(f"health   {self.row.health}")
        yield Static("\n".join(meta_lines), id="lane-meta")

        # 2. Stage progress block
        yield Static(self._stage_block(), id="lane-stages")

        # 3. Recent events
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

    def _stage_block(self) -> str:
        """Render the 8-stage progress lines for the row's feature."""
        if not self.row.feature_id:
            return "STAGE PROGRESS\n(no feature linked)"
        try:
            from orca.core.host_layout import from_manifest
            from orca.flow_state import compute_flow_state
            layout = from_manifest(self.repo_root)
            result = compute_flow_state(
                layout.resolve_feature_dir(self.row.feature_id),
                repo_root=self.repo_root,
            )
        except Exception:
            return "STAGE PROGRESS\n(unavailable)"

        all_milestones = result.completed_milestones + result.incomplete_milestones
        order = ["brainstorm", "specify", "plan", "tasks", "implement",
                 "review-spec", "review-code", "review-pr"]
        by_stage = {m.stage: m for m in all_milestones}
        lines = ["STAGE PROGRESS"]
        for stage in order:
            m = by_stage.get(stage)
            status = m.status if m else "not_started"
            evidence = ""
            if m and m.evidence_sources:
                evidence = m.evidence_sources[0]
            lines.append(f"  {stage:14s}  {status:14s}  {evidence}")
        return "\n".join(lines)
