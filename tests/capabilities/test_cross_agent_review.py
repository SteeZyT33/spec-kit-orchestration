from __future__ import annotations

import json
from pathlib import Path

import pytest

from orca.core.bundle import build_bundle
from orca.core.errors import ErrorKind
from orca.core.reviewers.base import RawFindings, ReviewerError
from orca.capabilities.cross_agent_review import (
    CrossAgentReviewInput,
    cross_agent_review,
)


class _StubReviewer:
    def __init__(self, name: str, *, findings=None, raise_error: bool = False):
        self.name = name
        self._findings = findings or []
        self._raise = raise_error

    def review(self, bundle, prompt):
        if self._raise:
            raise ReviewerError(f"{self.name} failed")
        return RawFindings(reviewer=self.name, findings=self._findings, metadata={})


def _input(tmp_path, **overrides):
    f = tmp_path / "x.py"
    f.write_text("pass\n")
    base = dict(
        kind="diff", target=[str(f)], feature_id=None,
        reviewer="cross", criteria=[], context=[], prompt="review",
    )
    base.update(overrides)
    return CrossAgentReviewInput(**base)


def test_cross_agent_review_returns_ok(tmp_path):
    finding = {
        "category": "correctness", "severity": "high", "confidence": "high",
        "summary": "Off-by-one", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s",
    }
    result = cross_agent_review(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", findings=[finding]),
                   "codex": _StubReviewer("codex", findings=[finding])},
    )
    assert result.ok
    assert len(result.value["findings"]) == 1
    assert result.value["partial"] is False
    assert result.value["missing_reviewers"] == []


def test_cross_agent_review_partial_when_one_fails(tmp_path):
    finding = {
        "category": "c", "severity": "high", "confidence": "high",
        "summary": "Z", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s",
    }
    result = cross_agent_review(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", findings=[finding]),
                   "codex": _StubReviewer("codex", raise_error=True)},
    )
    assert result.ok
    assert result.value["partial"] is True
    assert result.value["missing_reviewers"] == ["codex"]


def test_cross_agent_review_all_fail_returns_backend_failure(tmp_path):
    result = cross_agent_review(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", raise_error=True),
                   "codex": _StubReviewer("codex", raise_error=True)},
    )
    assert not result.ok
    assert result.error.kind == ErrorKind.BACKEND_FAILURE


def test_cross_agent_review_invalid_kind(tmp_path):
    inp = _input(tmp_path, kind="bogus")
    result = cross_agent_review(inp, reviewers={"claude": _StubReviewer("claude")})
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_cross_agent_review_invalid_reviewer(tmp_path):
    inp = _input(tmp_path, reviewer="banana")
    result = cross_agent_review(inp, reviewers={})
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_cross_agent_review_single_reviewer_mode(tmp_path):
    finding = {
        "category": "c", "severity": "high", "confidence": "high",
        "summary": "Z", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s",
    }
    inp = _input(tmp_path, reviewer="claude")
    result = cross_agent_review(
        inp, reviewers={"claude": _StubReviewer("claude", findings=[finding])},
    )
    assert result.ok
    assert result.value["partial"] is False
    assert result.value["missing_reviewers"] == []
    assert len(result.value["findings"]) == 1


def test_cross_agent_review_single_reviewer_not_configured(tmp_path):
    inp = _input(tmp_path, reviewer="claude")
    result = cross_agent_review(inp, reviewers={})  # claude not configured
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_cross_agent_review_single_reviewer_backend_failure(tmp_path):
    inp = _input(tmp_path, reviewer="claude")
    result = cross_agent_review(
        inp, reviewers={"claude": _StubReviewer("claude", raise_error=True)},
    )
    assert not result.ok
    assert result.error.kind == ErrorKind.BACKEND_FAILURE


def test_cross_agent_review_single_reviewer_malformed_finding(tmp_path):
    """Single-reviewer mode: when the reviewer responds with a finding
    missing required keys, the capability surfaces BACKEND_FAILURE with
    detail.underlying='malformed_finding'."""
    bad = {"category": "c", "severity": "high", "confidence": "high"}  # missing keys
    inp = _input(tmp_path, reviewer="claude")
    result = cross_agent_review(
        inp, reviewers={"claude": _StubReviewer("claude", findings=[bad])},
    )
    assert not result.ok
    assert result.error.kind == ErrorKind.BACKEND_FAILURE


def test_cross_agent_review_cross_mode_missing_backend_reviewer(tmp_path):
    """Cross mode requires both 'claude' and 'codex' in the reviewers dict."""
    inp = _input(tmp_path, reviewer="cross")
    result = cross_agent_review(inp, reviewers={"claude": _StubReviewer("claude")})  # no codex
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_cross_agent_review_output_validates_against_schema(tmp_path):
    pytest.importorskip("jsonschema")
    import jsonschema

    schema_path = Path(__file__).resolve().parents[2] / "docs" / "capabilities" / "cross-agent-review" / "schema" / "output.json"
    schema = json.loads(schema_path.read_text())

    finding = {
        "category": "c", "severity": "high", "confidence": "high",
        "summary": "Z", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s",
    }
    result = cross_agent_review(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", findings=[finding]),
                   "codex": _StubReviewer("codex", findings=[finding])},
    )
    assert result.ok
    jsonschema.validate(result.value, schema)


def test_cross_agent_review_threads_criteria_to_bundle(tmp_path):
    """Criteria pass through to the underlying ReviewBundle so reviewers
    can see them. We verify by inspecting the bundle reviewer was called with."""
    captured: dict = {}

    class _CapturingReviewer:
        name = "claude"

        def review(self, bundle, prompt):
            captured["criteria"] = bundle.criteria
            captured["context_paths"] = bundle.context_paths
            return RawFindings(reviewer="claude", findings=[], metadata={})

    inp = _input(tmp_path, reviewer="claude", criteria=["correctness", "security"])
    result = cross_agent_review(inp, reviewers={"claude": _CapturingReviewer()})
    assert result.ok
    assert captured["criteria"] == ("correctness", "security")


def test_cross_agent_review_non_dict_finding_returns_backend_failure(tmp_path):
    """A reviewer returning a non-dict finding (e.g., a bare string)
    must not crash with TypeError; it routes through the malformed-
    finding path the same as a missing-key dict."""
    inp = _input(tmp_path, reviewer="claude")
    result = cross_agent_review(
        inp,
        reviewers={"claude": _StubReviewer("claude", findings=["not-a-finding-string"])},
    )
    assert not result.ok
    assert result.error.kind == ErrorKind.BACKEND_FAILURE


def test_cross_agent_review_missing_target_path(tmp_path):
    inp = CrossAgentReviewInput(
        kind="diff",
        target=[str(tmp_path / "nonexistent.py")],
        reviewer="claude",
    )
    result = cross_agent_review(inp, reviewers={"claude": _StubReviewer("claude")})
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID
