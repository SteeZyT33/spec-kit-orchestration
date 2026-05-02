"""Integration test: collect_fleet builds FleetRows from real sidecars."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from orca.tui.collect import collect_fleet
from orca.tui.models import FleetRow


def _write_sidecar(worktree_root: Path, lane_id: str, **fields) -> None:
    base = {
        "schema_version": 2,
        "lane_id": lane_id,
        "lane_mode": "branch",
        "feature_id": fields.get("feature_id"),
        "lane_name": fields.get("lane_name"),
        "branch": fields.get("branch", lane_id),
        "base_branch": "main",
        "worktree_path": fields.get("worktree_path", f"/tmp/{lane_id}"),
        "created_at": fields.get("created_at", "2026-05-01T10:00:00+00:00"),
        "tmux_session": fields.get("tmux_session", f"orca-{lane_id}"),
        "tmux_window": lane_id[:32],
        "agent": fields.get("agent", "claude"),
        "setup_version": "abc123",
        "last_attached_at": fields.get("last_attached_at"),
        "host_system": "superpowers",
        "status": "active",
        "task_scope": fields.get("task_scope", []),
    }
    (worktree_root / f"{lane_id}.json").write_text(json.dumps(base))


def _write_registry(worktree_root: Path, lanes: list[dict]) -> None:
    (worktree_root / "registry.json").write_text(json.dumps({
        "schema_version": 2,
        "lanes": lanes,
    }))


def _seed_repo(tmp_path: Path) -> Path:
    """Seed minimal repo with adoption manifest + .orca/worktrees/ scaffold."""
    wt_root = tmp_path / ".orca" / "worktrees"
    wt_root.mkdir(parents=True)
    (tmp_path / ".orca" / "adoption.toml").write_text(
        '[host]\nsystem = "superpowers"\n'
        'constitution_path = ""\n'
        'agents_md_path = "AGENTS.md"\n'
        '[install]\nslash_command_namespace = "orca"\n'
        '[scope]\nclaude_md = "track"\n'
    )
    return wt_root


def test_collect_fleet_empty_when_no_lanes(tmp_path):
    _seed_repo(tmp_path)
    rows = collect_fleet(tmp_path,
                          tmux_alive=lambda s: False,
                          branch_merged=lambda b, base: False)
    assert rows == []


def test_collect_fleet_one_live_lane(tmp_path):
    wt_root = _seed_repo(tmp_path)
    _write_registry(wt_root, [{
        "lane_id": "lane-A", "branch": "lane-A",
        "worktree_path": str(tmp_path / "wt-A"), "feature_id": None,
    }])
    now_iso = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    _write_sidecar(wt_root, "lane-A",
                   last_attached_at=now_iso,
                   worktree_path=str(tmp_path / "wt-A"))

    rows = collect_fleet(
        tmp_path,
        tmux_alive=lambda s: True,
        branch_merged=lambda b, base: False,
        now=datetime(2026, 5, 1, 12, 0, 30, tzinfo=timezone.utc),
        last_event=lambda lane_id: "agent.launched",
        last_setup_failed=lambda lane_id: False,
    )

    assert len(rows) == 1
    r = rows[0]
    assert isinstance(r, FleetRow)
    assert r.lane_id == "lane-A"
    assert r.agent == "claude"
    assert r.state == "live"
    assert r.last_seen == "30s"


def test_collect_fleet_sorts_live_first_then_stale_then_merged(tmp_path):
    wt_root = _seed_repo(tmp_path)
    lanes = [
        {"lane_id": l, "branch": l, "worktree_path": str(tmp_path / l),
         "feature_id": None}
        for l in ("z-merged", "a-stale", "m-live")
    ]
    _write_registry(wt_root, lanes)
    now = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    _write_sidecar(wt_root, "z-merged",
                   last_attached_at=now.isoformat(),
                   worktree_path=str(tmp_path / "z-merged"))
    _write_sidecar(wt_root, "a-stale",
                   last_attached_at="2026-04-01T10:00:00+00:00",
                   worktree_path=str(tmp_path / "a-stale"))
    _write_sidecar(wt_root, "m-live",
                   last_attached_at=now.isoformat(),
                   worktree_path=str(tmp_path / "m-live"))

    rows = collect_fleet(
        tmp_path,
        tmux_alive=lambda s: s.endswith("m-live"),
        branch_merged=lambda b, base: b == "z-merged",
        now=now,
        last_event=lambda lane_id: "agent.launched" if lane_id == "m-live" else None,
        last_setup_failed=lambda lane_id: False,
    )
    assert [r.lane_id for r in rows] == ["m-live", "a-stale", "z-merged"]
