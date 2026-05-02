"""FleetTable: Pilot-driven render and content checks."""
from __future__ import annotations

import asyncio
from pathlib import Path

from orca.tui.app import FleetApp
from orca.tui.models import FleetRow


def test_fleet_table_renders_rows(tmp_path: Path) -> None:
    rows = [
        FleetRow(lane_id="alpha", feature_id="alpha", branch="alpha",
                 worktree_path="/tmp/alpha", agent="claude", state="live",
                 stage_strip="br·sp·pl·ta·IM·rs·rc·rp", last_seen="12s",
                 done="✓  ·  · ", health=""),
        FleetRow(lane_id="beta", feature_id=None, branch="beta",
                 worktree_path="/tmp/beta", agent="codex", state="stale",
                 stage_strip="br·sp·pl·ta·im·rs·rc·rp", last_seen="2d",
                 done="·  ·  · ", health="stale 2d"),
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
