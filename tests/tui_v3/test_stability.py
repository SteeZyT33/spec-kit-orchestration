"""Render stability: 50 identical-input set_rows must not change the
rendered SVG. Asserts our signature short-circuit (or equivalent) works."""
from __future__ import annotations

import asyncio
from pathlib import Path


def test_idle_render_is_stable(tmp_path: Path) -> None:
    asyncio.run(_run(tmp_path))


async def _run(tmp_path: Path) -> None:
    from orca.tui.app import FleetApp
    from orca.tui.flow_strip import strip_segments
    from orca.flow_state import FlowMilestone
    from orca.tui.models import FleetRow
    empty = strip_segments([
        FlowMilestone(stage=s, status="not_started")
        for s in ["brainstorm", "specify", "plan", "tasks", "implement",
                  "review-spec", "review-code", "review-pr"]
    ])
    rows = [FleetRow(lane_id="x", feature_id=None, branch="x",
                     worktree_path="/tmp/x", agent="claude", state="live",
                     stage_segments=empty, last_seen="1m",
                     done="·  ·  · ", health="")]
    app = FleetApp(repo_root=tmp_path, read_only=True)
    async with app.run_test(size=(100, 30)) as pilot:
        app.set_rows(rows)
        await pilot.pause()
        first = app.export_screenshot()
        for _ in range(50):
            app.set_rows(rows)
            await pilot.pause()
        second = app.export_screenshot()
    assert first == second, "render diverged on identical input — flicker risk"
