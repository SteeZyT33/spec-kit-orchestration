from __future__ import annotations

import json
from pathlib import Path

import pytest

from orca.core.errors import ErrorKind
from orca.core.reviewers.base import RawFindings, ReviewerError
from orca.capabilities.contradiction_detector import (
    ContradictionDetectorInput,
    contradiction_detector,
)


class _StubReviewer:
    def __init__(self, name: str, *, contradictions: list[dict] | None = None, raise_error: bool = False):
        self.name = name
        self._contradictions = contradictions or []
        self._raise = raise_error

    def review(self, bundle, prompt):
        if self._raise:
            raise ReviewerError(f"{self.name} failed", retryable=True, underlying="stub_failure")
        # Map contradiction-shape into RawFindings (capability normalizes back)
        raw_findings = [{
            "category": "contradiction",
            "severity": "high",
            "confidence": c.get("confidence", "high"),
            "summary": c["new_claim"],
            "detail": f"conflicts with {c['conflicting_evidence_ref']}",
            "evidence": [c["conflicting_evidence_ref"]],
            "suggestion": c.get("suggested_resolution", ""),
        } for c in self._contradictions]
        return RawFindings(reviewer=self.name, findings=raw_findings, metadata={"stub": True})


def _input(tmp_path, **overrides):
    new = tmp_path / "synthesis.md"
    new.write_text("New claim X is fast.")
    prior = tmp_path / "evidence.md"
    prior.write_text("Old claim Y. X measured slow in prior runs.")
    base = dict(
        new_content=str(new),
        prior_evidence=[str(prior)],
        reviewer="cross",
    )
    base.update(overrides)
    return ContradictionDetectorInput(**base)


def test_returns_contradictions(tmp_path):
    contradictions = [{
        "new_claim": "X is fast",
        "conflicting_evidence_ref": "evidence.md",
        "confidence": "high",
        "suggested_resolution": "re-measure",
    }]
    result = contradiction_detector(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", contradictions=contradictions),
                   "codex": _StubReviewer("codex", contradictions=contradictions)},
    )
    assert result.ok
    # Cross mode dedupes the same contradiction across reviewers
    assert len(result.value["contradictions"]) == 1
    c = result.value["contradictions"][0]
    assert c["new_claim"] == "X is fast"
    # Plural refs (now list with single entry from this stub)
    assert c["conflicting_evidence_refs"] == ["evidence.md"]
    # Multi-reviewer consensus surfaces
    assert set(c["reviewers"]) == {"claude", "codex"}
    assert result.value["partial"] is False
    assert result.value["missing_reviewers"] == []


def test_no_contradictions_returns_empty(tmp_path):
    result = contradiction_detector(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude"), "codex": _StubReviewer("codex")},
    )
    assert result.ok
    assert result.value["contradictions"] == []
    assert result.value["missing_reviewers"] == []


def test_partial_when_one_fails(tmp_path):
    contradictions = [{
        "new_claim": "X", "conflicting_evidence_ref": "e", "confidence": "high",
        "suggested_resolution": "",
    }]
    result = contradiction_detector(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", contradictions=contradictions),
                   "codex": _StubReviewer("codex", raise_error=True)},
    )
    assert result.ok
    assert result.value["partial"] is True
    assert result.value["missing_reviewers"] == ["codex"]
    # Single surviving reviewer attribution
    assert result.value["contradictions"][0]["reviewers"] == ["claude"]


def test_all_fail_returns_backend_failure(tmp_path):
    result = contradiction_detector(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", raise_error=True),
                   "codex": _StubReviewer("codex", raise_error=True)},
    )
    assert not result.ok
    assert result.error.kind == ErrorKind.BACKEND_FAILURE
    # Cross path also preserves diagnostics through CrossReviewer's
    # 'all reviewers failed' wrapped ReviewerError
    assert result.error.detail is not None
    assert result.error.detail.get("underlying") == "all_reviewers_failed"
    assert "retryable" in result.error.detail


def test_invalid_reviewer(tmp_path):
    inp = _input(tmp_path, reviewer="bogus")
    result = contradiction_detector(inp, reviewers={})
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_missing_new_content(tmp_path):
    inp = _input(tmp_path)
    inp_bad = ContradictionDetectorInput(
        new_content=str(tmp_path / "nope.md"),
        prior_evidence=inp.prior_evidence,
        reviewer="cross",
    )
    result = contradiction_detector(
        inp_bad,
        reviewers={"claude": _StubReviewer("claude"), "codex": _StubReviewer("codex")},
    )
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_cross_mode_missing_backend_reviewer(tmp_path):
    """Cross mode requires both 'claude' and 'codex' configured."""
    inp = _input(tmp_path, reviewer="cross")
    result = contradiction_detector(inp, reviewers={"claude": _StubReviewer("claude")})  # no codex
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_single_reviewer_mode_claude(tmp_path):
    contradictions = [{
        "new_claim": "X is broken", "conflicting_evidence_ref": "e", "confidence": "medium",
        "suggested_resolution": "investigate",
    }]
    inp = _input(tmp_path, reviewer="claude")
    result = contradiction_detector(
        inp,
        reviewers={"claude": _StubReviewer("claude", contradictions=contradictions)},
    )
    assert result.ok
    assert result.value["partial"] is False
    assert result.value["missing_reviewers"] == []
    assert len(result.value["contradictions"]) == 1
    assert result.value["contradictions"][0]["reviewers"] == ["claude"]


def test_single_reviewer_not_configured(tmp_path):
    inp = _input(tmp_path, reviewer="claude")
    result = contradiction_detector(inp, reviewers={})  # claude not configured
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_single_reviewer_backend_failure_preserves_diagnostic(tmp_path):
    inp = _input(tmp_path, reviewer="claude")
    result = contradiction_detector(
        inp,
        reviewers={"claude": _StubReviewer("claude", raise_error=True)},
    )
    assert not result.ok
    assert result.error.kind == ErrorKind.BACKEND_FAILURE
    # Detail block preserves underlying + retryable from ReviewerError
    assert result.error.detail is not None
    assert result.error.detail.get("underlying") == "stub_failure"
    assert result.error.detail.get("retryable") is True


def test_empty_prior_evidence_returns_input_invalid(tmp_path):
    """Schema says minItems:1; capability also enforces."""
    new = tmp_path / "synthesis.md"
    new.write_text("X.")
    inp = ContradictionDetectorInput(
        new_content=str(new),
        prior_evidence=[],
        reviewer="cross",
    )
    result = contradiction_detector(
        inp,
        reviewers={"claude": _StubReviewer("claude"), "codex": _StubReviewer("codex")},
    )
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_output_validates_against_schema(tmp_path):
    pytest.importorskip("jsonschema")
    import jsonschema
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "docs" / "capabilities" / "contradiction-detector" / "schema" / "output.json"
    )
    schema = json.loads(schema_path.read_text())

    contradictions = [{
        "new_claim": "X",
        "conflicting_evidence_ref": "e.md",
        "confidence": "high",
        "suggested_resolution": "investigate",
    }]
    result = contradiction_detector(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", contradictions=contradictions),
                   "codex": _StubReviewer("codex", contradictions=contradictions)},
    )
    assert result.ok
    jsonschema.validate(result.value, schema)


def test_contradiction_preserves_multiple_evidence_refs(tmp_path):
    """When one new claim conflicts with multiple prior evidence files,
    all refs should appear in conflicting_evidence_refs (plural)."""

    # Stub returns a finding with multi-ref evidence
    class _MultiRefStub:
        name = "claude"

        def review(self, bundle, prompt):
            return RawFindings(
                reviewer="claude",
                findings=[{
                    "category": "contradiction",
                    "severity": "high",
                    "confidence": "high",
                    "summary": "X is fast",
                    "detail": "conflicts with multiple prior runs",
                    "evidence": ["run1.jsonl", "run2.jsonl", "summary.md"],
                    "suggestion": "re-measure across all runs",
                }],
                metadata={},
            )

    inp = _input(tmp_path, reviewer="claude")
    result = contradiction_detector(
        inp,
        reviewers={"claude": _MultiRefStub()},
    )
    assert result.ok
    assert len(result.value["contradictions"]) == 1
    refs = result.value["contradictions"][0]["conflicting_evidence_refs"]
    assert refs == ["run1.jsonl", "run2.jsonl", "summary.md"]


def test_contradiction_with_empty_suggestion(tmp_path):
    """An empty suggestion should pass schema validation as empty string."""
    contradictions = [{
        "new_claim": "X",
        "conflicting_evidence_ref": "e.md",
        "confidence": "low",
        "suggested_resolution": "",
    }]
    inp = _input(tmp_path, reviewer="claude")
    result = contradiction_detector(
        inp,
        reviewers={"claude": _StubReviewer("claude", contradictions=contradictions)},
    )
    assert result.ok
    assert result.value["contradictions"][0]["suggested_resolution"] == ""
