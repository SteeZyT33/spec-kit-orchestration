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


def test_fixture_reviewer_name_property(tmp_path):
    reviewer = FixtureReviewer(scenario=FIXTURE_ROOT / "simple_diff.json", name="claude")
    assert reviewer.name == "claude"
