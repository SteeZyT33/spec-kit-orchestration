"""Unit tests for FileBackedReviewer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orca.core.bundle import ReviewBundle
from orca.core.reviewers.base import ReviewerError
from orca.core.reviewers.file_backed import FileBackedReviewer


def _make_findings_file(tmp_path: Path, findings: list[dict]) -> Path:
    p = tmp_path / "claude-findings.json"
    p.write_text(json.dumps(findings), encoding="utf-8")
    return p


def _bundle() -> ReviewBundle:
    # FileBackedReviewer ignores the bundle, so build a minimal valid instance
    # directly rather than going through build_bundle (which requires real files).
    return ReviewBundle(
        kind="diff",
        target_paths=(),
        feature_id=None,
        criteria=(),
        context_paths=(),
        bundle_hash="0" * 64,
        _target_bytes=(),
        _context_bytes=(),
    )


def test_file_backed_reviewer_reads_valid_findings(tmp_path: Path) -> None:
    findings = [{
        "id": "abc1234567890def",
        "category": "correctness",
        "severity": "high",
        "confidence": "high",
        "summary": "test claim",
        "detail": "details",
        "evidence": ["src/foo.py:1"],
        "suggestion": "fix it",
        "reviewer": "claude",
    }]
    path = _make_findings_file(tmp_path, findings)
    reviewer = FileBackedReviewer(name="claude", findings_path=path)
    result = reviewer.review(_bundle(), prompt="ignored")
    assert result.reviewer == "claude"
    assert result.findings == findings
    assert result.metadata["source"] == "in-session-subagent"
    assert result.metadata["findings_path"] == str(path)


def test_file_backed_reviewer_missing_file(tmp_path: Path) -> None:
    reviewer = FileBackedReviewer(name="claude", findings_path=tmp_path / "missing.json")
    with pytest.raises(ReviewerError, match="file not found"):
        reviewer.review(_bundle(), prompt="ignored")


def test_file_backed_reviewer_rejects_symlink(tmp_path: Path) -> None:
    real = _make_findings_file(tmp_path, [])
    link = tmp_path / "link.json"
    link.symlink_to(real)
    reviewer = FileBackedReviewer(name="claude", findings_path=link)
    with pytest.raises(ReviewerError, match="symlinks rejected"):
        reviewer.review(_bundle(), prompt="ignored")


def test_file_backed_reviewer_rejects_oversize(tmp_path: Path) -> None:
    p = tmp_path / "big.json"
    # 11 MB of valid-ish JSON to exceed the 10 MB cap
    p.write_bytes(b"[" + b'"x",' * (11 * 1024 * 1024 // 4) + b'"x"]')
    reviewer = FileBackedReviewer(name="claude", findings_path=p)
    with pytest.raises(ReviewerError, match="exceeds"):
        reviewer.review(_bundle(), prompt="ignored")


def test_file_backed_reviewer_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json at all", encoding="utf-8")
    reviewer = FileBackedReviewer(name="claude", findings_path=p)
    with pytest.raises(ReviewerError, match="invalid JSON"):
        reviewer.review(_bundle(), prompt="ignored")


def test_file_backed_reviewer_not_an_array(tmp_path: Path) -> None:
    p = tmp_path / "obj.json"
    p.write_text('{"findings": []}', encoding="utf-8")
    reviewer = FileBackedReviewer(name="claude", findings_path=p)
    with pytest.raises(ReviewerError, match="expected JSON array"):
        reviewer.review(_bundle(), prompt="ignored")


def test_file_backed_reviewer_per_finding_validation(tmp_path: Path) -> None:
    # Non-dict element triggers parse_findings_array's _validate_findings_array.
    p = _make_findings_file(tmp_path, ["not a dict"])  # type: ignore[list-item]
    reviewer = FileBackedReviewer(name="claude", findings_path=p)
    with pytest.raises(ReviewerError, match="non-dict"):
        reviewer.review(_bundle(), prompt="ignored")


def test_file_backed_reviewer_rejects_dangling_symlink(tmp_path: Path) -> None:
    """A symlink to a missing target rejects as symlink, not file_not_found."""
    target = tmp_path / "missing.json"
    link = tmp_path / "dangling-link.json"
    link.symlink_to(target)
    reviewer = FileBackedReviewer(name="claude", findings_path=link)
    with pytest.raises(ReviewerError, match="symlinks rejected"):
        reviewer.review(_bundle(), prompt="ignored")


def test_file_backed_reviewer_empty_array(tmp_path: Path) -> None:
    """Empty findings array is a valid no-findings result."""
    path = _make_findings_file(tmp_path, [])
    reviewer = FileBackedReviewer(name="claude", findings_path=path)
    result = reviewer.review(_bundle(), prompt="ignored")
    assert result.findings == []
    assert result.reviewer == "claude"
    assert result.metadata["source"] == "in-session-subagent"
