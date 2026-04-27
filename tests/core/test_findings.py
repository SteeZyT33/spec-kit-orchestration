from __future__ import annotations

import pytest

from orca.core.findings import Finding, Findings, Severity, Confidence


def test_finding_to_json_minimal():
    f = Finding(
        category="correctness",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        summary="Off-by-one in loop",
        detail="The range should be range(n+1) not range(n).",
        evidence=["src/foo.py:42"],
        suggestion="Use range(n+1)",
        reviewer="claude",
    )
    out = f.to_json()
    assert out["category"] == "correctness"
    assert out["severity"] == "high"
    assert out["confidence"] == "high"
    assert out["evidence"] == ["src/foo.py:42"]
    assert out["reviewer"] == "claude"
    assert "id" in out and len(out["id"]) == 16


def test_dedupe_id_stable_across_calls():
    base = dict(
        category="correctness",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        summary="Off-by-one in loop",
        detail="The range should be range(n+1) not range(n).",
        evidence=["src/foo.py:42"],
        suggestion="Use range(n+1)",
        reviewer="claude",
    )
    f1 = Finding(**base)
    f2 = Finding(**base)
    assert f1.dedupe_id() == f2.dedupe_id()


def test_dedupe_id_ignores_reviewer_and_confidence():
    base = dict(
        category="correctness",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        summary="Off-by-one in loop",
        detail="Detail text",
        evidence=["src/foo.py:42"],
        suggestion="Use range(n+1)",
    )
    f_claude = Finding(reviewer="claude", **base)
    f_codex = Finding(reviewer="codex", **{**base, "confidence": Confidence.MEDIUM})
    assert f_claude.dedupe_id() == f_codex.dedupe_id()


def test_dedupe_id_changes_with_evidence():
    base = dict(
        category="correctness",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        summary="x",
        detail="y",
        suggestion="z",
        reviewer="claude",
    )
    f1 = Finding(evidence=["a.py:1"], **base)
    f2 = Finding(evidence=["b.py:1"], **base)
    assert f1.dedupe_id() != f2.dedupe_id()


def test_findings_merge_dedupes_across_reviewers():
    a = Finding(
        category="correctness",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        summary="Off-by-one",
        detail="d",
        evidence=["x.py:1"],
        suggestion="s",
        reviewer="claude",
    )
    b = Finding(
        category="correctness",
        severity=Severity.HIGH,
        confidence=Confidence.MEDIUM,
        summary="Off-by-one",
        detail="d",
        evidence=["x.py:1"],
        suggestion="s",
        reviewer="codex",
    )
    merged = Findings.merge([a], [b])
    assert len(merged) == 1
    assert set(merged[0].reviewers) == {"claude", "codex"}


def test_findings_merge_keeps_distinct():
    a = Finding(
        category="correctness", severity=Severity.HIGH, confidence=Confidence.HIGH,
        summary="A", detail="d", evidence=["x.py:1"], suggestion="s", reviewer="claude",
    )
    b = Finding(
        category="security", severity=Severity.MEDIUM, confidence=Confidence.HIGH,
        summary="B", detail="d", evidence=["y.py:2"], suggestion="s", reviewer="codex",
    )
    merged = Findings.merge([a], [b])
    assert len(merged) == 2


def test_dedupe_id_normalizes_summary_punctuation_and_whitespace():
    base = dict(
        category="correctness",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        detail="d",
        evidence=["x.py:1"],
        suggestion="s",
        reviewer="claude",
    )
    f1 = Finding(summary="Off-by-one in loop", **base)
    f2 = Finding(summary="Off-by-one in loop.", **base)
    f3 = Finding(summary="Off-by-one  in  loop", **base)  # double spaces
    f4 = Finding(summary="off-by-one in loop!", **base)
    assert f1.dedupe_id() == f2.dedupe_id() == f3.dedupe_id() == f4.dedupe_id()


def test_finding_evidence_is_immutable_tuple():
    f = Finding(
        category="c", severity=Severity.HIGH, confidence=Confidence.HIGH,
        summary="x", detail="d", evidence=["a.py:1", "b.py:2"], suggestion="s",
        reviewer="claude",
    )
    assert isinstance(f.evidence, tuple)
    assert f.evidence == ("a.py:1", "b.py:2")


def test_finding_from_raw_basic():
    raw = {
        "category": "correctness",
        "severity": "high",
        "confidence": "high",
        "summary": "Off-by-one",
        "detail": "d",
        "evidence": ["x.py:1"],
        "suggestion": "s",
    }
    f = Finding.from_raw(raw, reviewer="claude")
    assert f.category == "correctness"
    assert f.severity == Severity.HIGH
    assert f.confidence == Confidence.HIGH
    assert f.reviewer == "claude"
    assert f.evidence == ("x.py:1",)


def test_finding_from_raw_normalizes_severity_aliases():
    base = {
        "category": "c", "confidence": "high",
        "summary": "S", "detail": "d",
        "evidence": [], "suggestion": "",
    }
    assert Finding.from_raw({**base, "severity": "critical"}, reviewer="r").severity == Severity.BLOCKER
    assert Finding.from_raw({**base, "severity": "informational"}, reviewer="r").severity == Severity.NIT
    assert Finding.from_raw({**base, "severity": "WARNING"}, reviewer="r").severity == Severity.MEDIUM


def test_finding_from_raw_unknown_severity_raises():
    raw = {
        "category": "c", "severity": "ULTRA_BLOCKER", "confidence": "high",
        "summary": "S", "detail": "d", "evidence": [], "suggestion": "",
    }
    with pytest.raises(ValueError):
        Finding.from_raw(raw, reviewer="r")


def test_finding_from_raw_missing_key_raises():
    raw = {"category": "c", "severity": "high", "confidence": "high"}  # no summary
    with pytest.raises(KeyError):
        Finding.from_raw(raw, reviewer="r")


def test_convert_raw_findings_rejects_non_dict():
    """Defense-in-depth: even if a non-dict slips past the parser, the
    converter wraps it as ReviewerError(underlying='malformed_finding')
    instead of letting TypeError escape the Result contract."""
    from orca.core.findings import convert_raw_findings
    from orca.core.reviewers.base import ReviewerError

    with pytest.raises(ReviewerError) as exc_info:
        convert_raw_findings(["not a dict"], reviewer="claude")
    assert exc_info.value.underlying == "malformed_finding"
