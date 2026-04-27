from __future__ import annotations

import json
from pathlib import Path

import pytest

from orca.core.errors import ErrorKind
from orca.capabilities.flow_state_projection import (
    FlowStateProjectionInput,
    flow_state_projection,
)


@pytest.fixture
def speckit_feature(tmp_path: Path) -> Path:
    """Create a minimal spec-kit-shaped feature directory."""
    feat = tmp_path / "specs" / "001-example"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("# Example Spec\n\nNo unclarified items.\n")
    (feat / "plan.md").write_text("# Plan\n")
    (feat / "tasks.md").write_text("- [ ] T001 Do the thing\n")
    return feat


def test_flow_state_projection_returns_ok(speckit_feature: Path):
    result = flow_state_projection(FlowStateProjectionInput(
        feature_dir=str(speckit_feature),
    ))
    assert result.ok
    out = result.value
    assert out["feature_id"] == "001-example"
    # Top-level keys all present
    assert "current_stage" in out
    assert "completed_milestones" in out
    assert "incomplete_milestones" in out
    assert "review_milestones" in out
    assert "ambiguities" in out
    assert "next_step" in out
    assert "evidence_summary" in out


def test_flow_state_projection_resolves_feature_id_with_repo_root(speckit_feature: Path):
    repo_root = speckit_feature.parent.parent  # tmp_path
    result = flow_state_projection(FlowStateProjectionInput(
        feature_id="001-example",
        repo_root=str(repo_root),
    ))
    assert result.ok
    assert result.value["feature_id"] == "001-example"


def test_flow_state_projection_no_id_or_dir():
    result = flow_state_projection(FlowStateProjectionInput())
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID
    assert "feature_id" in result.error.message or "feature_dir" in result.error.message


def test_flow_state_projection_feature_id_without_repo_root():
    result = flow_state_projection(FlowStateProjectionInput(feature_id="001-example"))
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_flow_state_projection_missing_feature_dir():
    result = flow_state_projection(FlowStateProjectionInput(
        feature_dir="/nonexistent/path",
    ))
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_flow_state_projection_resolved_feature_id_dir_missing(tmp_path: Path):
    """feature_id + repo_root, but repo_root has no specs/<id> subdir."""
    result = flow_state_projection(FlowStateProjectionInput(
        feature_id="999-missing",
        repo_root=str(tmp_path),
    ))
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_flow_state_projection_output_validates_against_schema(speckit_feature: Path):
    pytest.importorskip("jsonschema")
    import jsonschema

    schema_path = (
        Path(__file__).resolve().parents[2]
        / "docs" / "capabilities" / "flow-state-projection" / "schema" / "output.json"
    )
    schema = json.loads(schema_path.read_text())

    result = flow_state_projection(FlowStateProjectionInput(
        feature_dir=str(speckit_feature),
    ))
    assert result.ok
    jsonschema.validate(result.value, schema)


def test_flow_state_projection_internal_error_on_unexpected_exception(monkeypatch, tmp_path: Path):
    """If compute_flow_state raises something unexpected, capability surfaces INTERNAL."""
    feat = tmp_path / "specs" / "001-bad"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("# Spec\n")

    def boom(*args, **kwargs):
        raise RuntimeError("simulated flow_state failure")

    monkeypatch.setattr(
        "orca.capabilities.flow_state_projection.compute_flow_state",
        boom,
    )
    result = flow_state_projection(FlowStateProjectionInput(feature_dir=str(feat)))
    assert not result.ok
    assert result.error.kind == ErrorKind.INTERNAL
    assert result.error.detail is not None
    assert result.error.detail.get("underlying") == "RuntimeError"
