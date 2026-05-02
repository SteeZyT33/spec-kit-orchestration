"""FleetRow shape test."""
import dataclasses

import pytest

from orca.tui.models import FleetRow


def test_fleetrow_has_required_fields():
    r = FleetRow(
        lane_id="tui-v3-impl",
        feature_id="tui-v3",
        branch="tui-v3-impl",
        worktree_path="/tmp/wt",
        agent="claude",
        state="live",
        stage_strip="br·sp·pl·ta·IM·rs·rc·rp",
        last_seen="12s",
        done="spec✓ code· pr·",
        health="",
    )
    assert r.state == "live"
    assert r.agent == "claude"


def test_fleetrow_is_frozen():
    r = FleetRow(
        lane_id="x", feature_id=None, branch="x", worktree_path="/x",
        agent="none", state="idle", stage_strip="·" * 8,
        last_seen="-", done="·" * 3, health="",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.state = "live"  # type: ignore[misc]
