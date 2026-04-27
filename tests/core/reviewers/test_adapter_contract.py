"""Adapter contract: every reviewer's RawFindings round-trips into Finding.

Adding a new reviewer? Add it to the parametrize list. If your reviewer
can't pass this, it doesn't ship. The point is to lock the structural
contract that all reviewers must satisfy: name + review(bundle, prompt)
returning RawFindings with finding dicts that Finding.from_raw can convert.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from orca.core.bundle import build_bundle
from orca.core.findings import Confidence, Finding, Severity
from orca.core.reviewers.claude import ClaudeReviewer
from orca.core.reviewers.fixtures import FixtureReviewer

TESTS_DIR = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = TESTS_DIR / "fixtures" / "reviewers"


def _bundle(tmp_path: Path):
    f = tmp_path / "x.py"
    f.write_text("pass\n")
    return build_bundle(
        kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[],
    )


def _fake_anthropic_response(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "end_turn"
    response.usage = MagicMock(input_tokens=10, output_tokens=20)
    return response


_CANONICAL_FINDING_JSON = json.dumps([{
    "category": "correctness",
    "severity": "high",
    "confidence": "high",
    "summary": "Off-by-one in loop",
    "detail": "range(n) skips the last element.",
    "evidence": ["src/foo.py:42"],
    "suggestion": "Use range(n+1)",
}])


def _make_claude_reviewer():
    """Construct a ClaudeReviewer wired to a MagicMock that emits the canonical finding."""
    client = MagicMock()
    client.messages.create.return_value = _fake_anthropic_response(_CANONICAL_FINDING_JSON)
    return ClaudeReviewer(client=client)


def _make_codex_fixture_reviewer():
    """Construct a FixtureReviewer pinned to the codex scenario fixture."""
    fixture = FIXTURE_ROOT / "codex" / "simple_review.json"
    return FixtureReviewer(scenario=fixture, name="codex")


def _make_claude_fixture_reviewer():
    """Construct a FixtureReviewer pinned to the canonical claude scenario fixture."""
    fixture = FIXTURE_ROOT / "scenarios" / "simple_diff.json"
    return FixtureReviewer(scenario=fixture, name="claude")


@pytest.mark.parametrize("make_reviewer,expected_name", [
    (_make_claude_reviewer, "claude"),
    (_make_codex_fixture_reviewer, "codex"),
    (_make_claude_fixture_reviewer, "claude"),
], ids=["claude-sdk", "codex-fixture", "claude-fixture"])
def test_reviewer_returns_findings_that_round_trip(
    make_reviewer, expected_name, tmp_path: Path,
):
    """Every reviewer's RawFindings must round-trip into Finding via from_raw.

    Validates the structural contract: review() returns RawFindings(reviewer, findings, metadata),
    each finding dict has the fields Finding.from_raw expects, and the resulting Finding's
    JSON form satisfies the schema-level invariants (16-char id, valid enums).
    """
    reviewer = make_reviewer()
    raw = reviewer.review(_bundle(tmp_path), prompt="review")

    assert raw.reviewer == expected_name
    assert isinstance(raw.findings, list)

    # Every raw finding must convert via Finding.from_raw (no AttributeError,
    # no KeyError, no ValueError on enum values).
    for raw_finding in raw.findings:
        finding = Finding.from_raw(raw_finding, reviewer=raw.reviewer)
        json_form = finding.to_json()

        # Schema-level invariants downstream consumers depend on
        assert len(json_form["id"]) == 16
        assert json_form["severity"] in {s.value for s in Severity}
        assert json_form["confidence"] in {c.value for c in Confidence}
        assert json_form["reviewer"] == raw.reviewer
        # reviewers tuple is at least the singleton of reviewer name
        assert raw.reviewer in json_form["reviewers"]


def test_adapter_contract_catches_malformed_reviewer():
    """A reviewer that returns non-dict findings must NOT silently pass.

    This is the negative case: the contract test would catch a hypothetical
    'BadReviewer' that returned strings instead of dicts.
    """
    class _BadReviewer:
        name = "bad"

        def review(self, bundle, prompt):
            del bundle, prompt
            from orca.core.reviewers.base import RawFindings
            return RawFindings(
                reviewer="bad",
                findings=["not a dict"],  # contract violation
                metadata={},
            )

    import tempfile
    from orca.core.bundle import build_bundle as _build

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        f = td_path / "x.py"
        f.write_text("pass\n")
        bundle = _build(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])
        raw = _BadReviewer().review(bundle, prompt="x")

    # from_raw should reject the non-dict
    with pytest.raises((TypeError, KeyError, AttributeError)):
        Finding.from_raw(raw.findings[0], reviewer=raw.reviewer)
