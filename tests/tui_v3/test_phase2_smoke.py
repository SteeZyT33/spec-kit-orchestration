"""Phase 2 visual smoke: render fleet with 5 fixture rows at three sizes,
write SVG snapshots that the tui-reviewer agent inspects."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

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


_NS = "not_started"
_CP = "complete"
_IP = "in_progress"
_BL = "blocked"

_FIXTURES: list[FleetRow] = [
    # tui-v3-impl: implement in_progress
    FleetRow(lane_id="tui-v3-impl", feature_id="tui-v3", branch="tui-v3-impl",
             worktree_path="/tmp/tui", agent="claude", state="live",
             stage_segments=_segs(_NS, _NS, _NS, _NS, _IP, _NS, _NS, _NS),
             last_seen="12s", done="·  ·  · ", health=""),
    # wt-contract: review-spec in_progress
    FleetRow(lane_id="wt-contract", feature_id="wt-contract",
             branch="wt-contract", worktree_path="/tmp/wt-c",
             agent="codex", state="live",
             stage_segments=_segs(_NS, _NS, _NS, _NS, _NS, _IP, _NS, _NS),
             last_seen="2m", done="·  ·  · ", health=""),
    # perf-lab: review-code in_progress, stale
    FleetRow(lane_id="perf-lab", feature_id="perf-lab", branch="perf-lab",
             worktree_path="/tmp/p", agent="claude", state="stale",
             stage_segments=_segs(_NS, _NS, _NS, _NS, _NS, _NS, _IP, _NS),
             last_seen="2h", done="✓  ·  · ", health="stale 2h"),
    # 015-adopt: review-pr in_progress, merged
    FleetRow(lane_id="015-adopt", feature_id="015-adopt",
             branch="015-adopt", worktree_path="/tmp/a", agent="none",
             state="merged",
             stage_segments=_segs(_NS, _NS, _NS, _NS, _NS, _NS, _NS, _IP),
             last_seen="3h", done="✓  ✓  ⏵", health="merged·cleanup"),
    # broken: plan in_progress, failed
    FleetRow(lane_id="broken", feature_id=None, branch="broken",
             worktree_path="/tmp/b", agent="codex", state="failed",
             stage_segments=_segs(_NS, _NS, _IP, _NS, _NS, _NS, _NS, _NS),
             last_seen="1h", done="·  ·  · ", health="setup-failed"),
]


@pytest.mark.parametrize("size", [(80, 24), (100, 30), (140, 44)])
def test_render_snapshot_at(tmp_path: Path, size: tuple[int, int]):
    w, h = size

    async def _run() -> None:
        app = FleetApp(repo_root=tmp_path, read_only=True)
        async with app.run_test(size=(w, h)) as pilot:
            app.set_rows(_FIXTURES)
            await pilot.pause()
            out = Path(__file__).parent / "snapshots" / f"phase2-{w}x{h}.svg"
            out.parent.mkdir(exist_ok=True)
            out.write_text(app.export_screenshot())

    asyncio.run(_run())


def test_drilldown_snapshot_100x30(tmp_path: Path) -> None:
    asyncio.run(_drilldown_snapshot(tmp_path, 100, 30))


def test_drilldown_snapshot_140x44(tmp_path: Path) -> None:
    asyncio.run(_drilldown_snapshot(tmp_path, 140, 44))


async def _drilldown_snapshot(tmp_path: Path, w: int, h: int) -> None:
    import json
    from orca.tui.drilldown import LaneScreen

    wt_root = tmp_path / ".orca" / "worktrees"
    wt_root.mkdir(parents=True)
    (wt_root / "events.jsonl").write_text(
        "\n".join(json.dumps(d) for d in [
            {"event": "lane.created", "lane_id": "tui-v3-impl",
             "ts": "2026-05-01T10:00:00+00:00"},
            {"event": "tmux.session.created", "lane_id": "tui-v3-impl",
             "ts": "2026-05-01T10:00:01+00:00"},
            {"event": "setup.after_create.started", "lane_id": "tui-v3-impl",
             "ts": "2026-05-01T10:00:05+00:00"},
            {"event": "setup.after_create.completed", "lane_id": "tui-v3-impl",
             "ts": "2026-05-01T10:00:42+00:00"},
            {"event": "agent.launched", "lane_id": "tui-v3-impl",
             "ts": "2026-05-01T11:00:00+00:00", "agent": "claude"},
        ]) + "\n"
    )
    app = FleetApp(repo_root=tmp_path, read_only=True)
    async with app.run_test(size=(w, h)) as pilot:
        app.set_rows(_FIXTURES)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, LaneScreen), (
            f"Enter did not navigate to LaneScreen; got {type(app.screen).__name__}. "
            "Cannot capture drill-down snapshot."
        )
        out = Path(__file__).parent / "snapshots" / f"phase3-drilldown-{w}x{h}.svg"
        out.write_text(app.export_screenshot())
