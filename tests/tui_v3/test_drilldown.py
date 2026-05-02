"""LaneScreen: Enter pushes drill-down with metadata + recent events."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path


def test_enter_pushes_lane_screen(tmp_path: Path) -> None:
    asyncio.run(_run(tmp_path))


async def _run(tmp_path: Path) -> None:
    from orca.tui.app import FleetApp
    from orca.tui.drilldown import LaneScreen
    from orca.tui.flow_strip import strip_segments
    from orca.flow_state import FlowMilestone
    from orca.tui.models import FleetRow

    # Seed minimal events so drill-down has something to show.
    wt_root = tmp_path / ".orca" / "worktrees"
    wt_root.mkdir(parents=True)
    (wt_root / "events.jsonl").write_text(
        json.dumps({"event": "lane.created", "lane_id": "alpha",
                    "ts": "2026-05-01T10:00:00+00:00"}) + "\n"
        + json.dumps({"event": "agent.launched", "lane_id": "alpha",
                      "ts": "2026-05-01T11:00:00+00:00"}) + "\n"
    )
    empty_segs = strip_segments([
        FlowMilestone(stage=s, status="not_started")
        for s in ["brainstorm", "specify", "plan", "tasks", "implement",
                  "review-spec", "review-code", "review-pr"]
    ])
    row = FleetRow(lane_id="alpha", feature_id=None, branch="alpha",
                   worktree_path="/tmp/alpha", agent="claude", state="live",
                   stage_segments=empty_segs, last_seen="12s",
                   done="·  ·  · ", health="")

    app = FleetApp(repo_root=tmp_path, read_only=True)
    async with app.run_test() as pilot:
        app.set_rows([row])
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, LaneScreen)
