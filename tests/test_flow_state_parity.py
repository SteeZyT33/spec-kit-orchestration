"""019 Sub-phase A parity gate (T016).

For every snapshot in `tests/fixtures/flow_state_snapshots/`, the live
`compute_flow_state(feature_dir).to_dict()` must match the golden JSON
byte-for-byte after path normalization and after stripping any `kind`
field on `completed_milestones[*]` / `incomplete_milestones[*]` (the
snapshots predate `kind`; sub-phase B regenerates them).

The test intentionally mirrors the existing byte-exact gate in
`test_sdd_adapter.py::TestSpecKitLoadFeatureMatchesLegacy` so a
regression surfaces here first.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SNAPSHOTS_ROOT = Path(__file__).parent / "fixtures" / "flow_state_snapshots"


def _discover_snapshot_features() -> list[str]:
    if not SNAPSHOTS_ROOT.is_dir():
        return []
    return sorted(
        p.name
        for p in SNAPSHOTS_ROOT.iterdir()
        if p.is_dir() and (p / "golden.json").is_file()
    )


SNAPSHOT_FEATURES = _discover_snapshot_features()


def _normalize_paths(obj, fixture_root: Path):
    root_str = str(fixture_root)
    if isinstance(obj, str):
        return obj.replace(root_str, "<FIXTURE_ROOT>")
    if isinstance(obj, list):
        return [_normalize_paths(x, fixture_root) for x in obj]
    if isinstance(obj, dict):
        return {k: _normalize_paths(v, fixture_root) for k, v in obj.items()}
    return obj


def _strip_kind_from_milestones(obj):
    """Remove `kind` from completed/incomplete milestones entries.

    Sub-phase A's `StageProgress.kind` addition does not propagate into
    `FlowMilestone`, so snapshots should still match byte-exact. This
    helper runs defensively in case a future commit wires `kind` through.
    """
    if not isinstance(obj, dict):
        return obj
    out = dict(obj)
    for key in ("completed_milestones", "incomplete_milestones"):
        items = out.get(key)
        if isinstance(items, list):
            cleaned = []
            for entry in items:
                if isinstance(entry, dict) and "kind" in entry:
                    entry = {k: v for k, v in entry.items() if k != "kind"}
                cleaned.append(entry)
            out[key] = cleaned
    return out


@pytest.mark.parametrize("feature_id", SNAPSHOT_FEATURES)
def test_spec_kit_fixtures_match_phase1_snapshots_modulo_kind(feature_id: str):
    from speckit_orca.flow_state import compute_flow_state

    snapshot_dir = SNAPSHOTS_ROOT / feature_id
    fixture_root = (snapshot_dir / "fixture").resolve()
    feature_dir = fixture_root / "specs" / feature_id
    golden_path = snapshot_dir / "golden.json"

    assert fixture_root.is_dir(), f"missing fixture tree: {fixture_root}"
    assert golden_path.is_file(), f"missing golden snapshot: {golden_path}"

    golden_text = golden_path.read_text(encoding="utf-8")

    result = compute_flow_state(feature_dir, repo_root=fixture_root)
    live = _normalize_paths(result.to_dict(), fixture_root)
    live = _strip_kind_from_milestones(live)
    live_text = json.dumps(live, indent=2) + "\n"

    assert live_text == golden_text, (
        f"Flow-state parity drift for {feature_id}: sub-phase A must "
        "stay byte-exact against the pre-Phase-2 snapshots modulo kind."
    )
