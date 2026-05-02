"""Phase 2 visual smoke: render fleet with 5 fixture rows at three sizes,
write SVG snapshots that the tui-reviewer agent inspects."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orca.tui.app import FleetApp
from orca.tui.models import FleetRow


_FIXTURES: list[FleetRow] = [
    FleetRow(lane_id="tui-v3-impl", feature_id="tui-v3", branch="tui-v3-impl",
             worktree_path="/tmp/tui", agent="claude", state="live",
             stage_strip="br·sp·pl·ta·IM·rs·rc·rp", last_seen="12s",
             done="·  ·  · ", health=""),
    FleetRow(lane_id="wt-contract", feature_id="wt-contract",
             branch="wt-contract", worktree_path="/tmp/wt-c",
             agent="codex", state="live", stage_strip="br·sp·pl·ta·im·RS·rc·rp",
             last_seen="2m", done="·  ·  · ", health=""),
    FleetRow(lane_id="perf-lab", feature_id="perf-lab", branch="perf-lab",
             worktree_path="/tmp/p", agent="claude", state="stale",
             stage_strip="br·sp·pl·ta·im·rs·RC·rp", last_seen="2h",
             done="✓  ·  · ", health="stale 2h"),
    FleetRow(lane_id="015-adopt", feature_id="015-adopt",
             branch="015-adopt", worktree_path="/tmp/a", agent="none",
             state="merged", stage_strip="br·sp·pl·ta·im·rs·rc·RP",
             last_seen="merged", done="✓  ✓  ⏵", health="merged·cleanup"),
    FleetRow(lane_id="broken", feature_id=None, branch="broken",
             worktree_path="/tmp/b", agent="codex", state="failed",
             stage_strip="br·sp·PL·ta·im·rs·rc·rp", last_seen="1h",
             done="·  ·  · ", health="setup-failed"),
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
