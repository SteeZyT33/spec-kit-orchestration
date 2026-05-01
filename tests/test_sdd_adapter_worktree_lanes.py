import json
from pathlib import Path

from orca.sdd_adapter import SpecKitAdapter


def test_reader_handles_v2_object_lanes(tmp_path):
    repo = tmp_path
    wt_root = repo / ".orca" / "worktrees"
    wt_root.mkdir(parents=True)

    # v2 registry: list of objects
    (wt_root / "registry.json").write_text(json.dumps({
        "schema_version": 2,
        "lanes": [
            {"lane_id": "015-wiz", "branch": "feature/015-wiz",
             "worktree_path": str(wt_root / "015-wiz"), "feature_id": "015"},
        ],
    }))
    # Sidecar with both v2 and legacy field names
    (wt_root / "015-wiz.json").write_text(json.dumps({
        "id": "015-wiz",        # legacy
        "feature": "015",        # legacy (matches feature_id arg)
        "branch": "feature/015-wiz",
        "path": str(wt_root / "015-wiz"),  # legacy
        "status": "active",
        "task_scope": [],
    }))

    lanes = SpecKitAdapter._load_worktree_lanes(repo, "015")
    assert len(lanes) == 1
    assert lanes[0].lane_id == "015-wiz"


def test_reader_skips_unknown_lane_entry_types(tmp_path):
    repo = tmp_path
    wt_root = repo / ".orca" / "worktrees"
    wt_root.mkdir(parents=True)
    # Mixed: one object, one string (v1 stragglers), one bogus number
    (wt_root / "registry.json").write_text(json.dumps({
        "schema_version": 2,
        "lanes": [
            {"lane_id": "a", "branch": "b", "worktree_path": "/p", "feature_id": "X"},
            "string-lane",
            42,
        ],
    }))
    # Sidecars
    (wt_root / "a.json").write_text(json.dumps({
        "id": "a", "feature": "X", "branch": "b", "path": "/p",
        "status": "active", "task_scope": [],
    }))
    (wt_root / "string-lane.json").write_text(json.dumps({
        "id": "string-lane", "feature": "X", "branch": "z", "path": "/q",
        "status": "active", "task_scope": [],
    }))

    lanes = SpecKitAdapter._load_worktree_lanes(repo, "X")
    # The numeric entry is skipped silently; the other two normalize.
    lane_ids = sorted(l.lane_id for l in lanes)
    assert lane_ids == ["a", "string-lane"]
