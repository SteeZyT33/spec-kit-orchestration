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


def test_fixture_reviewer_explicit_name_attributes_findings(tmp_path):
    """When name= is pinned, RawFindings.reviewer must use it too — not
    the scenario file's recorded reviewer. Otherwise findings get
    misattributed (e.g., FixtureReviewer(name='codex') with a fixture
    that says reviewer='claude' would tag findings as 'claude')."""
    scenario = tmp_path / "scenario.json"
    import json as _json
    scenario.write_text(_json.dumps({
        "reviewer": "claude",
        "raw_findings": [
            {"category": "c", "severity": "high", "confidence": "high",
             "summary": "S", "detail": "d", "evidence": [], "suggestion": ""}
        ],
    }))
    reviewer = FixtureReviewer(scenario=scenario, name="codex")
    raw = reviewer.review(_bundle(tmp_path), prompt="any")
    assert raw.reviewer == "codex"


def test_parse_findings_array_rejects_non_dict_items():
    """Greedy-path: a JSON array of non-dicts must surface as a parser-
    boundary ReviewerError, not as a TypeError in Finding.from_raw."""
    from orca.core.reviewers._parse import parse_findings_array

    with pytest.raises(ReviewerError) as exc_info:
        parse_findings_array('["not a dict"]', source="test")
    assert exc_info.value.underlying == "malformed_finding"


def test_parse_findings_array_rejects_mixed_dict_and_non_dict_items_balanced_path():
    """Fallback balanced-scan path: the existing guard checks only the
    FIRST element for dict-ness, so a mixed list (first dict, second
    string) reaches the validator and must surface as
    underlying='malformed_finding'."""
    from orca.core.reviewers._parse import parse_findings_array

    # Greedy regex grabs everything between the first '[' and last ']',
    # which is unparseable. Balanced scan finds the second array, where
    # the first item is a dict (passes the existing guard) but the
    # second is a string (must trip the new validator).
    text = '[unparseable\n{garbage}] then final: [{"a": 1}, "rogue-string"]'
    with pytest.raises(ReviewerError) as exc_info:
        parse_findings_array(text, source="test")
    assert exc_info.value.underlying == "malformed_finding"


def test_fixture_reviewer_malformed_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json {{{")
    reviewer = FixtureReviewer(scenario=bad)
    with pytest.raises(ReviewerError, match="malformed fixture"):
        reviewer.review(_bundle(tmp_path), prompt="any")
