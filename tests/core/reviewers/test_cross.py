from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.bundle import build_bundle
from orca.core.reviewers.base import RawFindings, ReviewerError
from orca.core.reviewers.cross import CrossReviewer, CrossResult


class _StubReviewer:
    """Minimal Reviewer-protocol-conforming stub for testing CrossReviewer.

    Either returns recorded findings or raises ReviewerError on demand.
    Does NOT inherit Reviewer (structural typing).
    """

    def __init__(self, name: str, *, raise_error: bool = False, findings: list[dict] | None = None):
        self.name = name
        self._raise = raise_error
        self._findings = findings if findings is not None else []

    def review(self, bundle, prompt):
        if self._raise:
            raise ReviewerError(f"{self.name} failed", retryable=True)
        return RawFindings(reviewer=self.name, findings=self._findings, metadata={})


def _bundle(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("pass\n")
    return build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])


def test_cross_both_succeed_merges_findings(tmp_path):
    a_finding = {
        "category": "correctness", "severity": "high", "confidence": "high",
        "summary": "Off-by-one", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s",
    }
    b_finding = {
        "category": "security", "severity": "medium", "confidence": "high",
        "summary": "Unsafe eval", "detail": "d", "evidence": ["y.py:2"], "suggestion": "s",
    }
    cross = CrossReviewer(reviewers=[
        _StubReviewer("claude", findings=[a_finding]),
        _StubReviewer("codex", findings=[b_finding]),
    ])
    result = cross.review(_bundle(tmp_path), prompt="x")
    assert result.partial is False
    assert result.missing_reviewers == ()
    assert len(result.findings) == 2
    assert {f.reviewer for f in result.findings} == {"claude", "codex"}


def test_cross_dedupes_overlap(tmp_path):
    same = {
        "category": "correctness", "severity": "high", "confidence": "high",
        "summary": "Off-by-one", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s",
    }
    cross = CrossReviewer(reviewers=[
        _StubReviewer("claude", findings=[same]),
        _StubReviewer("codex", findings=[same]),
    ])
    result = cross.review(_bundle(tmp_path), prompt="x")
    assert len(result.findings) == 1
    assert set(result.findings[0].reviewers) == {"claude", "codex"}


def test_cross_partial_when_one_fails(tmp_path):
    f = {"category": "c", "severity": "high", "confidence": "high",
         "summary": "Z", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s"}
    cross = CrossReviewer(reviewers=[
        _StubReviewer("claude", findings=[f]),
        _StubReviewer("codex", raise_error=True),
    ])
    result = cross.review(_bundle(tmp_path), prompt="x")
    assert result.partial is True
    assert result.missing_reviewers == ("codex",)
    assert len(result.findings) == 1


def test_cross_partial_with_multiple_failures(tmp_path):
    """When >2 reviewers and 2 fail, missing_reviewers lists ALL failed names."""
    f = {"category": "c", "severity": "high", "confidence": "high",
         "summary": "Z", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s"}
    cross = CrossReviewer(reviewers=[
        _StubReviewer("claude", findings=[f]),
        _StubReviewer("codex", raise_error=True),
        _StubReviewer("gemini", raise_error=True),
    ])
    result = cross.review(_bundle(tmp_path), prompt="x")
    assert result.partial is True
    assert result.missing_reviewers == ("codex", "gemini")  # sorted
    assert len(result.findings) == 1


def test_cross_rejects_duplicate_reviewer_names(tmp_path):
    """Two reviewers with the same name would silently overwrite metadata
    and break finding attribution."""
    with pytest.raises(ValueError, match="unique names"):
        CrossReviewer(reviewers=[
            _StubReviewer("claude"),
            _StubReviewer("claude"),
        ])


def test_cross_malformed_finding_treated_as_failure(tmp_path):
    """Reviewer returning a finding without required fields should land
    in failures (not propagate KeyError)."""
    bad = {"category": "c", "severity": "high", "confidence": "high"}  # missing summary, detail, evidence, suggestion
    good = {"category": "c", "severity": "high", "confidence": "high",
            "summary": "Z", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s"}
    cross = CrossReviewer(reviewers=[
        _StubReviewer("claude", findings=[bad]),
        _StubReviewer("codex", findings=[good]),
    ])
    result = cross.review(_bundle(tmp_path), prompt="x")
    assert result.partial is True
    assert result.missing_reviewers == ("claude",)
    assert len(result.findings) == 1


def test_cross_all_fail_raises(tmp_path):
    cross = CrossReviewer(reviewers=[
        _StubReviewer("claude", raise_error=True),
        _StubReviewer("codex", raise_error=True),
    ])
    with pytest.raises(ReviewerError, match="all reviewers failed") as exc_info:
        cross.review(_bundle(tmp_path), prompt="x")
    # Sentinel for downstream observers (capability code, perf-lab shim).
    assert exc_info.value.underlying == "all_reviewers_failed"
    # _StubReviewer raises with retryable=True by default; aggregate via any().
    assert exc_info.value.retryable is True


def test_cross_requires_at_least_two_reviewers(tmp_path):
    """Single-reviewer 'cross' is meaningless — that's just the underlying reviewer."""
    with pytest.raises(ValueError, match="at least 2"):
        CrossReviewer(reviewers=[_StubReviewer("claude")])
