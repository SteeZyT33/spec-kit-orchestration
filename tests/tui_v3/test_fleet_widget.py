"""FleetTable: Pilot-driven render and content checks."""
from __future__ import annotations

import asyncio
from pathlib import Path

from orca.flow_state import FlowMilestone
from orca.tui.app import FleetApp
from orca.tui.flow_strip import strip_segments
from orca.tui.models import FleetRow


def _segs(*statuses: str) -> tuple[tuple[str, str], ...]:
    """Build stage_segments from 8 status strings."""
    stages = ["brainstorm", "specify", "plan", "tasks",
              "implement", "review-spec", "review-code", "review-pr"]
    milestones = [FlowMilestone(stage=s, status=st)
                  for s, st in zip(stages, statuses)]
    return strip_segments(milestones)


def test_fleet_table_renders_rows(tmp_path: Path) -> None:
    rows = [
        FleetRow(lane_id="alpha", feature_id="alpha", branch="alpha",
                 worktree_path="/tmp/alpha", agent="claude", state="live",
                 stage_segments=_segs("not_started", "not_started", "not_started",
                                      "not_started", "in_progress", "not_started",
                                      "not_started", "not_started"),
                 last_seen="12s", done="✓  ·  · ", health=""),
        FleetRow(lane_id="beta", feature_id=None, branch="beta",
                 worktree_path="/tmp/beta", agent="codex", state="stale",
                 stage_segments=_segs("not_started", "not_started", "not_started",
                                      "not_started", "not_started", "not_started",
                                      "not_started", "not_started"),
                 last_seen="2d", done="·  ·  · ", health="stale 2d"),
    ]

    async def _run() -> None:
        app = FleetApp(repo_root=tmp_path, read_only=True)
        async with app.run_test() as pilot:
            app.set_rows(rows)
            await pilot.pause()
            from orca.tui.fleet import FleetTable
            table = app.query_one(FleetTable)
            assert table.row_count == 2

    asyncio.run(_run())
