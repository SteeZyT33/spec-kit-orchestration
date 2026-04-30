"""Every capability's output JSON must validate against its declared output schema.

Schema drift is a build break. Two layers:

1. Every published schema is itself valid Draft 7.
2. A canonical sample output for each capability validates against that
   schema. If a capability's wire format changes, either the schema or
   the sample must update in lockstep.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs" / "capabilities"

CAPABILITIES = [
    "cross-agent-review",
    "worktree-overlap-check",
    "flow-state-projection",
    "completion-gate",
    "citation-validator",
    "contradiction-detector",
]


@pytest.mark.parametrize("capability", CAPABILITIES)
def test_schemas_are_valid_draft7(capability: str):
    """Both input.json and output.json for every capability must be valid Draft 7 schemas."""
    schema_dir = DOCS / capability / "schema"
    for name in ("input.json", "output.json"):
        schema_path = schema_dir / name
        assert schema_path.exists(), f"missing schema: {schema_path}"
        schema = json.loads(schema_path.read_text())
        jsonschema.Draft7Validator.check_schema(schema)


def _load_output_schema(capability: str) -> dict:
    return json.loads((DOCS / capability / "schema" / "output.json").read_text())


def test_cross_agent_review_sample_output_validates():
    """Sample output: 1 cross-merged finding from claude+codex."""
    schema = _load_output_schema("cross-agent-review")
    sample = {
        "findings": [{
            "id": "0123456789abcdef",
            "category": "correctness",
            "severity": "high",
            "confidence": "high",
            "summary": "S",
            "detail": "d",
            "evidence": ["x:1"],
            "suggestion": "s",
            "reviewer": "claude",
            "reviewers": ["claude", "codex"],
        }],
        "partial": False,
        "missing_reviewers": [],
        "reviewer_metadata": {"claude": {}, "codex": {}},
    }
    jsonschema.validate(sample, schema)


def test_cross_agent_review_partial_sample_validates():
    """Sample output with partial=True and one missing reviewer."""
    schema = _load_output_schema("cross-agent-review")
    sample = {
        "findings": [],
        "partial": True,
        "missing_reviewers": ["codex"],
        "reviewer_metadata": {"claude": {}},
    }
    jsonschema.validate(sample, schema)


def test_worktree_overlap_sample_output_validates():
    """Sample output: safe state with empty conflicts."""
    schema = _load_output_schema("worktree-overlap-check")
    sample = {"safe": True, "conflicts": [], "proposed_overlaps": []}
    jsonschema.validate(sample, schema)


def test_worktree_overlap_with_conflict_validates():
    """Sample output: containment conflict + proposed overlap with multi-blocker."""
    schema = _load_output_schema("worktree-overlap-check")
    sample = {
        "safe": False,
        "conflicts": [
            {"paths": ["src/foo/", "src/foo/bar.py"], "worktrees": ["/a", "/b"]},
        ],
        "proposed_overlaps": [
            {"path": "src/foo/x.py", "blocked_by": ["/a"]},
        ],
    }
    jsonschema.validate(sample, schema)


def test_flow_state_projection_sample_output_validates():
    """Sample output: minimal flow state shape."""
    schema = _load_output_schema("flow-state-projection")
    sample = {
        "feature_id": "001-example",
        "current_stage": "specify",
        "completed_milestones": [{"stage": "brainstorm", "status": "complete", "evidence_sources": []}],
        "incomplete_milestones": [{"stage": "plan", "status": "missing", "evidence_sources": []}],
        "review_milestones": [{"review_type": "review-spec", "status": "pending"}],
        "ambiguities": [],
        "next_step": "Run /speckit.plan",
        "evidence_summary": ["spec.md present"],
    }
    jsonschema.validate(sample, schema)


def test_completion_gate_sample_output_validates():
    """Sample output: pass status with one passing gate."""
    schema = _load_output_schema("completion-gate")
    sample = {
        "status": "pass",
        "gates_evaluated": [{"gate": "spec_exists", "passed": True, "reason": ""}],
        "blockers": [],
        "stale_artifacts": [],
    }
    jsonschema.validate(sample, schema)


def test_completion_gate_blocked_sample_validates():
    """Sample output: blocked status with reason populated."""
    schema = _load_output_schema("completion-gate")
    sample = {
        "status": "blocked",
        "gates_evaluated": [
            {"gate": "spec_exists", "passed": False, "reason": ""},
            {"gate": "no_unclarified", "passed": False, "reason": "spec.md missing"},
        ],
        "blockers": ["spec_exists", "no_unclarified"],
        "stale_artifacts": [],
    }
    jsonschema.validate(sample, schema)


def test_citation_validator_sample_output_validates():
    """Sample output: full coverage, no findings."""
    schema = _load_output_schema("citation-validator")
    sample = {
        "uncited_claims": [],
        "broken_refs": [],
        "well_supported_claims": [],
        "citation_coverage": 1.0,
    }
    jsonschema.validate(sample, schema)


def test_citation_validator_with_findings_validates():
    """Sample output: partial coverage with both uncited claims and broken refs."""
    schema = _load_output_schema("citation-validator")
    sample = {
        "uncited_claims": [{"text": "Results show 42% gain.", "line": 1}],
        "broken_refs": [{"ref": "missing-doc", "line": 2}],
        "well_supported_claims": [{"text": "Tests prove [evidence].", "line": 3}],
        "citation_coverage": 0.5,
    }
    jsonschema.validate(sample, schema)


def test_contradiction_detector_sample_output_validates():
    """Sample output: one contradiction with cross-mode consensus (plural reviewers + refs)."""
    schema = _load_output_schema("contradiction-detector")
    sample = {
        "contradictions": [{
            "new_claim": "X is fast",
            "conflicting_evidence_refs": ["evidence.md", "summary.md"],
            "confidence": "high",
            "suggested_resolution": "re-measure",
            "reviewers": ["claude", "codex"],
        }],
        "partial": False,
        "missing_reviewers": [],
        "reviewer_metadata": {"claude": {}, "codex": {}},
    }
    jsonschema.validate(sample, schema)


def test_contradiction_detector_partial_sample_validates():
    """Sample output: partial with single surviving reviewer."""
    schema = _load_output_schema("contradiction-detector")
    sample = {
        "contradictions": [],
        "partial": True,
        "missing_reviewers": ["codex"],
        "reviewer_metadata": {"claude": {}},
    }
    jsonschema.validate(sample, schema)
