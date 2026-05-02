"""FleetRow shape test."""
import dataclasses

import pytest

from orca.tui.models import FleetRow

_SAMPLE_SEGMENTS: tuple[tuple[str, str], ...] = (
    ("br", "dim"), ("·", "dim"), ("sp", "dim"), ("·", "dim"),
    ("pl", "dim"), ("·", "dim"), ("ta", "dim"), ("·", "dim"),
    ("IM", "bold yellow"), ("·", "dim"), ("rs", "dim"), ("·", "dim"),
    ("rc", "dim"), ("·", "dim"), ("rp", "dim"),
)


def test_fleetrow_has_required_fields():
    r = FleetRow(
        lane_id="tui-v3-impl",
        feature_id="tui-v3",
        branch="tui-v3-impl",
        worktree_path="/tmp/wt",
        agent="claude",
        state="live",
        stage_segments=_SAMPLE_SEGMENTS,
        last_seen="12s",
        done="spec✓ code· pr·",
        health="",
    )
    assert r.state == "live"
    assert r.agent == "claude"
    assert isinstance(r.stage_segments, tuple)


def test_fleetrow_is_frozen():
    r = FleetRow(
        lane_id="x", feature_id=None, branch="x", worktree_path="/x",
        agent="none", state="idle", stage_segments=(),
        last_seen="-", done="·" * 3, health="",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.state = "live"  # type: ignore[misc]
