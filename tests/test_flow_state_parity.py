"""019 Sub-phase B parity gate (T031).

For every snapshot in `tests/fixtures/flow_state_snapshots/`, the live
`compute_flow_state(feature_dir).to_dict()` must match the golden JSON
byte-for-byte after path normalization. The snapshots were regenerated
at sub-phase B with `FlowMilestone.kind` populated, so the parity gate
is now full-shape byte equality — no `kind` stripping.

The test intentionally mirrors the byte-exact gate in
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


@pytest.mark.parametrize("feature_id", SNAPSHOT_FEATURES)
def test_spec_kit_fixtures_match_snapshots_byte_exact(feature_id: str):
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
    live_text = json.dumps(live, indent=2) + "\n"

    assert live_text == golden_text, (
        f"Flow-state parity drift for {feature_id}: sub-phase B must "
        "stay byte-exact against the kind-populated snapshots."
    )
