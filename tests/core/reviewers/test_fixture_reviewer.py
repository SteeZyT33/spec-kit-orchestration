from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.bundle import build_bundle
from orca.core.reviewers.base import ReviewerError
from orca.core.reviewers.fixtures import FixtureReviewer


FIXTURE_ROOT = Path(__file__).parent.parent.parent / "fixtures" / "reviewers" / "scenarios"


def _bundle(tmp_path: Path):
    f = tmp_path / "foo.py"
    f.write_text("for i in range(n): pass\n")
    return build_bundle(
        kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[],
    )


def test_fixture_reviewer_replays_recorded_findings(tmp_path):
    reviewer = FixtureReviewer(scenario=FIXTURE_ROOT / "simple_diff.json")
    raw = reviewer.review(_bundle(tmp_path), prompt="any")
    assert raw.reviewer == "claude"
    assert len(raw.findings) == 1
    assert raw.findings[0]["summary"] == "Off-by-one in loop"


def test_fixture_reviewer_missing_file_errors(tmp_path):
    reviewer = FixtureReviewer(scenario=tmp_path / "missing.json")
    with pytest.raises(ReviewerError, match="fixture not found"):
        reviewer.review(_bundle(tmp_path), prompt="any")


def test_fixture_reviewer_explicit_name_overrides_scenario(tmp_path):
    """Explicit name= argument wins over the scenario's reviewer field."""
    reviewer = FixtureReviewer(scenario=FIXTURE_ROOT / "simple_diff.json", name="codex")
    assert reviewer.name == "codex"  # scenario says "claude"


def test_reviewer_error_carries_retryable_and_underlying():
    err = ReviewerError("rate limited", retryable=True, underlying="anthropic.RateLimitError")
    assert err.retryable is True
    assert err.underlying == "anthropic.RateLimitError"


def test_reviewer_error_default_attributes():
    err = ReviewerError("plain")
    assert err.retryable is False
    assert err.underlying is None


def test_fixture_reviewer_name_safe_when_scenario_missing(tmp_path):
    """Accessing .name on a misconfigured FixtureReviewer should NOT raise.

    review() is the surface where missing-fixture surfaces as ReviewerError;
    .name should be cheap and safe so loggers/exception handlers can use it.
    """
    reviewer = FixtureReviewer(scenario=tmp_path / "does-not-exist.json")
    assert reviewer.name == "fixture"  # safe fallback


def test_fixture_reviewer_malformed_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json {{{")
    reviewer = FixtureReviewer(scenario=bad)
    with pytest.raises(ReviewerError, match="malformed fixture"):
        reviewer.review(_bundle(tmp_path), prompt="any")
