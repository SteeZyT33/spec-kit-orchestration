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
    lane_ids = sorted(lane.lane_id for lane in lanes)
    assert lane_ids == ["a", "string-lane"]


def test_reader_does_not_match_lane_id_as_feature_id(tmp_path):
    """Regression for the dropped `id == feature_id` back-compat clause.

    A sidecar with ``id == "015"`` (lane name happens to equal a feature_id)
    but ``feature == "999"`` MUST NOT be returned for ``feature_id="015"``
    queries. The legacy clause matched on either field; today's dual-emit
    writes ``id = lane.lane_id``, so that fallback was wrong.
    """
    repo = tmp_path
    wt_root = repo / ".orca" / "worktrees"
    wt_root.mkdir(parents=True)
    (wt_root / "registry.json").write_text(json.dumps({
        "schema_version": 2,
        "lanes": [
            {"lane_id": "015", "branch": "b",
             "worktree_path": str(wt_root / "015"), "feature_id": "999"},
        ],
    }))
    (wt_root / "015.json").write_text(json.dumps({
        "id": "015", "feature": "999", "branch": "b",
        "path": str(wt_root / "015"), "status": "active", "task_scope": [],
    }))

    # Querying for feature 015 must NOT match the lane whose id is "015"
    # but whose feature is "999".
    lanes = SpecKitAdapter._load_worktree_lanes(repo, "015")
    assert lanes == []
    # Sanity: querying for the actual feature does match.
    lanes = SpecKitAdapter._load_worktree_lanes(repo, "999")
    assert len(lanes) == 1 and lanes[0].lane_id == "015"
