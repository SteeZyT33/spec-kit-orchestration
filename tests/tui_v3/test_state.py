"""State glyph derivation from sidecar + events."""
from datetime import datetime, timedelta, timezone

import pytest

from orca.tui.state import derive_state, StateInputs


@pytest.fixture
def now():
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def _iso(now, **delta):
    return (now - timedelta(**delta)).isoformat()


def test_state_live_when_recent_attach_and_tmux_alive(now):
    inp = StateInputs(
        last_attached_at=_iso(now, seconds=30),
        last_event="agent.launched",
        tmux_alive=True,
        branch_merged=False,
        last_setup_failed=False,
    )
    assert derive_state(inp, now=now) == "live"


def test_state_stale_when_attach_old(now):
    inp = StateInputs(
        last_attached_at=_iso(now, days=2),
        last_event=None,
        tmux_alive=False,
        branch_merged=False,
        last_setup_failed=False,
    )
    assert derive_state(inp, now=now) == "stale"


def test_state_merged_when_branch_merged(now):
    inp = StateInputs(
        last_attached_at=_iso(now, hours=1),
        last_event=None,
        tmux_alive=False,
        branch_merged=True,
        last_setup_failed=False,
    )
    assert derive_state(inp, now=now) == "merged"


def test_state_failed_when_setup_failed(now):
    inp = StateInputs(
        last_attached_at=_iso(now, hours=1),
        last_event="setup.before_run.failed",
        tmux_alive=False,
        branch_merged=False,
        last_setup_failed=True,
    )
    assert derive_state(inp, now=now) == "failed"


def test_state_idle_otherwise(now):
    inp = StateInputs(
        last_attached_at=_iso(now, hours=1),
        last_event=None,
        tmux_alive=False,
        branch_merged=False,
        last_setup_failed=False,
    )
    assert derive_state(inp, now=now) == "idle"
