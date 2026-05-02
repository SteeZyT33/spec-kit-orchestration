"""Keybindings: r/n/d are no-ops in read-only mode; present otherwise."""
from __future__ import annotations

import asyncio
from pathlib import Path


def test_read_only_mode_close_is_noop(tmp_path: Path, monkeypatch) -> None:
    asyncio.run(_run_readonly(tmp_path, monkeypatch))


async def _run_readonly(tmp_path: Path, monkeypatch) -> None:
    """Pressing 'r' in read-only mode does NOT call close_lane."""
    from orca.tui.app import FleetApp
    from orca.tui.flow_strip import strip_segments
    from orca.flow_state import FlowMilestone
    from orca.tui.models import FleetRow
    called: list[bool] = []
    monkeypatch.setattr("orca.tui.actions.close_lane",
                        lambda *a, **kw: called.append(True))
    app = FleetApp(repo_root=tmp_path, read_only=True)
    async with app.run_test() as pilot:
        empty = strip_segments([
            FlowMilestone(stage=s, status="not_started")
            for s in ["brainstorm", "specify", "plan", "tasks", "implement",
                      "review-spec", "review-code", "review-pr"]
        ])
        app.set_rows([FleetRow(
            lane_id="x", feature_id=None, branch="x", worktree_path="/tmp/x",
            agent="claude", state="live", stage_segments=empty,
            last_seen="1m", done="·  ·  · ", health="",
        )])
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
    assert called == []


def test_full_mode_close_pushes_confirm(tmp_path: Path) -> None:
    asyncio.run(_run_full(tmp_path))


async def _run_full(tmp_path: Path) -> None:
    """Pressing 'r' in full mode pushes a ConfirmModal."""
    from orca.tui.app import FleetApp
    from orca.tui.modals import ConfirmModal
    from orca.tui.flow_strip import strip_segments
    from orca.flow_state import FlowMilestone
    from orca.tui.models import FleetRow
    app = FleetApp(repo_root=tmp_path, read_only=False)
    async with app.run_test() as pilot:
        empty = strip_segments([
            FlowMilestone(stage=s, status="not_started")
            for s in ["brainstorm", "specify", "plan", "tasks", "implement",
                      "review-spec", "review-code", "review-pr"]
        ])
        app.set_rows([FleetRow(
            lane_id="x", feature_id=None, branch="x", worktree_path="/tmp/x",
            agent="claude", state="live", stage_segments=empty,
            last_seen="1m", done="·  ·  · ", health="",
        )])
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmModal)
