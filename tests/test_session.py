"""Tests for 017 session presence primitive."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from orca import session as session_mod
from orca.session import (
    Session,
    SessionScope,
    SESSIONS_DIRNAME,
    SESSION_TTL_SECONDS,
    end_session,
    find_conflicting_session,
    heartbeat,
    list_active_sessions,
    session_scope,
    start_session,
)


# ─── SessionScope ────────────────────────────────────────────────────────


def test_scope_overlaps_by_lane_id():
    a = SessionScope(lane_id="022-T001")
    b = SessionScope(lane_id="022-T001", feature_dir="specs/022")
    assert a.overlaps(b)
    assert b.overlaps(a)


def test_scope_overlaps_by_feature_dir():
    a = SessionScope(feature_dir="specs/022")
    b = SessionScope(feature_dir="specs/022", lane_id="T002")
    assert a.overlaps(b)


def test_scope_does_not_overlap_different_lanes():
    a = SessionScope(lane_id="022-T001")
    b = SessionScope(lane_id="022-T002")
    assert not a.overlaps(b)


def test_scope_empty_does_not_overlap_anything():
    empty = SessionScope()
    populated = SessionScope(lane_id="X", feature_dir="Y")
    assert not empty.overlaps(populated)
    assert not populated.overlaps(empty)


def test_scope_worktree_alone_does_not_conflict():
    """Two sessions in the same worktree don't conflict unless they also
    claim the same lane/feature. Read-only inspection is fine."""
    a = SessionScope(worktree="/tmp/wt")
    b = SessionScope(worktree="/tmp/wt")
    assert not a.overlaps(b)


# ─── Session.is_stale ────────────────────────────────────────────────────


def test_session_is_stale_when_heartbeat_old():
    old_hb = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    s = Session(
        session_id="x", agent="claude", started=old_hb, last_heartbeat=old_hb
    )
    assert s.is_stale()


def test_session_is_fresh_when_heartbeat_recent():
    recent = datetime.now(timezone.utc).isoformat()
    s = Session(
        session_id="x", agent="claude", started=recent, last_heartbeat=recent
    )
    assert not s.is_stale()


def test_session_is_stale_with_garbage_timestamp():
    s = Session(
        session_id="x", agent="claude", started="2026-01-01",
        last_heartbeat="not-a-timestamp",
    )
    assert s.is_stale()


def test_session_is_stale_with_naive_iso_timestamp():
    """Regression for PR #58: a naive ISO string (no tz) parses via
    ``fromisoformat`` but raises ``TypeError`` when subtracted from an
    aware ``now``. The old code only caught ``ValueError``, which let
    the TypeError propagate and crashed ``_reap_stale_unlocked``. The
    hardened ``is_stale`` now treats naive timestamps as stale."""
    s = Session(
        session_id="x",
        agent="claude",
        started="2026-04-16T10:15:00",
        last_heartbeat="2026-04-16T10:15:00",  # naive, no timezone
    )
    assert s.is_stale()


def test_session_is_stale_with_naive_reap_does_not_crash(tmp_path: Path):
    """Exercise the crash path end-to-end: drop a session file with a
    naive timestamp and confirm ``list_active_sessions`` reaps it
    without raising."""
    sessions_dir = tmp_path / SESSIONS_DIRNAME
    sessions_dir.mkdir(parents=True)
    path = sessions_dir / "legacy.json"
    path.write_text(json.dumps({
        "session_id": "legacy",
        "agent": "claude",
        "started": "2026-04-16T10:15:00",
        "last_heartbeat": "2026-04-16T10:15:00",
        "scope": {},
        "pid": 1,
        "host": "h",
    }))
    # Must not raise TypeError
    active = list_active_sessions(repo_root=tmp_path)
    assert active == []
    assert not path.exists()


# ─── session_id validation (path-traversal guard, PR #58) ────────────────


def test_start_session_rejects_path_traversal_id(tmp_path: Path):
    """session_id is used verbatim in the filename; values like
    ``../../evil`` must be rejected before touching the filesystem."""
    with pytest.raises(ValueError):
        start_session(
            agent="claude",
            repo_root=tmp_path,
            session_id="../../evil",
        )


def test_start_session_rejects_separator_id(tmp_path: Path):
    with pytest.raises(ValueError):
        start_session(
            agent="claude", repo_root=tmp_path, session_id="foo/bar"
        )


def test_start_session_rejects_dotfile_id(tmp_path: Path):
    with pytest.raises(ValueError):
        start_session(
            agent="claude", repo_root=tmp_path, session_id=".hidden"
        )


def test_heartbeat_rejects_path_traversal_id(tmp_path: Path):
    (tmp_path / SESSIONS_DIRNAME).mkdir(parents=True)
    with pytest.raises(ValueError):
        heartbeat("../../evil", repo_root=tmp_path)


def test_end_session_rejects_path_traversal_id(tmp_path: Path):
    (tmp_path / SESSIONS_DIRNAME).mkdir(parents=True)
    with pytest.raises(ValueError):
        end_session("../../evil", repo_root=tmp_path)


def test_end_session_rejects_does_not_delete_outside_dir(tmp_path: Path):
    """Integration check: an attacker-controlled id that would escape
    the sessions dir must not remove the target file."""
    (tmp_path / SESSIONS_DIRNAME).mkdir(parents=True)
    target = tmp_path / "outside.json"
    target.write_text("{}")
    # Even relative traversal segments must be rejected.
    with pytest.raises(ValueError):
        end_session("../outside", repo_root=tmp_path)
    assert target.exists()


# ─── start / heartbeat / end roundtrip ───────────────────────────────────


def test_start_creates_file(tmp_path: Path):
    s = start_session(agent="claude", repo_root=tmp_path)
    path = tmp_path / SESSIONS_DIRNAME / f"{s.session_id}.json"
    assert path.is_file()
    with open(path) as fh:
        data = json.load(fh)
    assert data["agent"] == "claude"
    assert data["session_id"] == s.session_id


def test_start_assigns_pid_and_host(tmp_path: Path):
    s = start_session(agent="codex", repo_root=tmp_path)
    assert s.pid > 0
    # host may be empty on some sandboxes but the field exists
    assert isinstance(s.host, str)


def test_start_writes_scope(tmp_path: Path):
    scope = SessionScope(lane_id="X", feature_dir="specs/X")
    s = start_session(agent="claude", repo_root=tmp_path, scope=scope)
    assert s.scope.lane_id == "X"
    assert s.scope.feature_dir == "specs/X"


def test_heartbeat_updates_timestamp(tmp_path: Path):
    s = start_session(agent="claude", repo_root=tmp_path)
    original = s.last_heartbeat
    time.sleep(0.01)
    updated = heartbeat(s.session_id, repo_root=tmp_path)
    assert updated.last_heartbeat >= original
    # On slow machines the tick might match to the microsecond; assert it's
    # at least not regressing.
    assert updated.last_heartbeat != "" and len(updated.last_heartbeat) > 10


def test_heartbeat_can_change_scope(tmp_path: Path):
    s = start_session(agent="claude", repo_root=tmp_path)
    new_scope = SessionScope(lane_id="new-lane")
    updated = heartbeat(s.session_id, repo_root=tmp_path, scope=new_scope)
    assert updated.scope.lane_id == "new-lane"


def test_heartbeat_on_missing_session_raises(tmp_path: Path):
    # Need the sessions dir to exist for lock acquisition to work
    (tmp_path / SESSIONS_DIRNAME).mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        heartbeat("does-not-exist", repo_root=tmp_path)


def test_end_removes_file(tmp_path: Path):
    s = start_session(agent="claude", repo_root=tmp_path)
    assert end_session(s.session_id, repo_root=tmp_path) is True
    path = tmp_path / SESSIONS_DIRNAME / f"{s.session_id}.json"
    assert not path.exists()


def test_end_on_missing_session_returns_false(tmp_path: Path):
    (tmp_path / SESSIONS_DIRNAME).mkdir(parents=True)
    assert end_session("nope", repo_root=tmp_path) is False


# ─── list / reap ─────────────────────────────────────────────────────────


def test_list_empty_when_no_sessions(tmp_path: Path):
    assert list_active_sessions(repo_root=tmp_path) == []


def test_list_shows_active_session(tmp_path: Path):
    s = start_session(agent="claude", repo_root=tmp_path)
    active = list_active_sessions(repo_root=tmp_path)
    assert len(active) == 1
    assert active[0].session_id == s.session_id


def test_list_reaps_stale_sessions(tmp_path: Path):
    # Create a session, then manually age its heartbeat beyond TTL
    s = start_session(agent="claude", repo_root=tmp_path)
    path = tmp_path / SESSIONS_DIRNAME / f"{s.session_id}.json"
    with open(path) as fh:
        data = json.load(fh)
    ancient = (datetime.now(timezone.utc) - timedelta(seconds=SESSION_TTL_SECONDS + 60)).isoformat()
    data["last_heartbeat"] = ancient
    with open(path, "w") as fh:
        json.dump(data, fh)

    # List should reap it and return empty
    active = list_active_sessions(repo_root=tmp_path)
    assert active == []
    assert not path.exists()


def test_list_reaps_corrupt_json(tmp_path: Path):
    # Create a session dir and drop a corrupt file into it
    (tmp_path / SESSIONS_DIRNAME).mkdir(parents=True)
    corrupt = tmp_path / SESSIONS_DIRNAME / "corrupt.json"
    corrupt.write_text("{ not valid json")
    active = list_active_sessions(repo_root=tmp_path)
    assert active == []
    assert not corrupt.exists()


def test_list_skips_reap_when_reap_false(tmp_path: Path):
    s = start_session(agent="claude", repo_root=tmp_path)
    path = tmp_path / SESSIONS_DIRNAME / f"{s.session_id}.json"
    # Age it
    with open(path) as fh:
        data = json.load(fh)
    ancient = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    data["last_heartbeat"] = ancient
    with open(path, "w") as fh:
        json.dump(data, fh)

    # With reap=False, file still on disk but stale session filtered out of return
    active = list_active_sessions(repo_root=tmp_path, reap=False)
    assert active == []
    assert path.exists()  # not reaped


# ─── find_conflicting_session ────────────────────────────────────────────


def test_conflict_found_on_same_lane(tmp_path: Path):
    a = start_session(
        agent="claude", repo_root=tmp_path, scope=SessionScope(lane_id="X")
    )
    conflict = find_conflicting_session(
        SessionScope(lane_id="X"), repo_root=tmp_path
    )
    assert conflict is not None
    assert conflict.session_id == a.session_id


def test_no_conflict_on_different_lane(tmp_path: Path):
    start_session(
        agent="claude", repo_root=tmp_path, scope=SessionScope(lane_id="X")
    )
    assert (
        find_conflicting_session(SessionScope(lane_id="Y"), repo_root=tmp_path)
        is None
    )


def test_conflict_excludes_self(tmp_path: Path):
    a = start_session(
        agent="claude", repo_root=tmp_path, scope=SessionScope(lane_id="X")
    )
    assert (
        find_conflicting_session(
            SessionScope(lane_id="X"),
            repo_root=tmp_path,
            exclude_session_id=a.session_id,
        )
        is None
    )


def test_conflict_not_found_when_only_session_is_stale(tmp_path: Path):
    s = start_session(
        agent="claude", repo_root=tmp_path, scope=SessionScope(lane_id="X")
    )
    # Age it past TTL
    path = tmp_path / SESSIONS_DIRNAME / f"{s.session_id}.json"
    with open(path) as fh:
        data = json.load(fh)
    ancient = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    data["last_heartbeat"] = ancient
    with open(path, "w") as fh:
        json.dump(data, fh)

    assert (
        find_conflicting_session(SessionScope(lane_id="X"), repo_root=tmp_path)
        is None
    )


# ─── session_scope context manager ───────────────────────────────────────


def test_session_scope_cleans_up_on_normal_exit(tmp_path: Path):
    sid = None
    with session_scope(agent="claude", repo_root=tmp_path) as s:
        sid = s.session_id
        assert (tmp_path / SESSIONS_DIRNAME / f"{sid}.json").exists()
    # After context exit, file should be gone
    assert not (tmp_path / SESSIONS_DIRNAME / f"{sid}.json").exists()


def test_session_scope_cleans_up_on_exception(tmp_path: Path):
    sid = None
    with pytest.raises(RuntimeError):
        with session_scope(agent="claude", repo_root=tmp_path) as s:
            sid = s.session_id
            assert (tmp_path / SESSIONS_DIRNAME / f"{sid}.json").exists()
            raise RuntimeError("boom")
    assert not (tmp_path / SESSIONS_DIRNAME / f"{sid}.json").exists()
