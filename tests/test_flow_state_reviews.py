"""Tests for the 012 three-review-artifact model in flow_state.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from orca.flow_state import (
    REVIEW_ARTIFACT_NAMES,
    ReviewMilestone,
    compute_flow_state,
)


@pytest.fixture()
def feature_dir(tmp_path: Path) -> Path:
    d = tmp_path / "specs" / "020-example"
    d.mkdir(parents=True)
    (d / "spec.md").write_text("# Feature Specification: Example\n\n**Status**: Draft\n")
    (d / "plan.md").write_text("# Plan\n")
    (d / "tasks.md").write_text("# Tasks\n\n- [x] T1 implement widget [@claude]\n")
    return d


def _review_map(result) -> dict[str, ReviewMilestone]:
    return {m.review_type: m for m in result.review_milestones}


class TestReviewSpec:
    def test_missing(self, feature_dir: Path) -> None:
        result = compute_flow_state(feature_dir)
        rm = _review_map(result)
        assert rm["review-spec"].status == "missing"

    def test_ready(self, feature_dir: Path) -> None:
        spec = feature_dir / "spec.md"
        spec.write_text(
            "# Spec\n\n## Clarifications\n\n### Session 2026-04-10\n- Q: a → A: b\n"
        )
        (feature_dir / "review-spec.md").write_text(
            "# Review: Spec\n\n"
            "## Prerequisites\n- Clarify session: 2026-04-10\n\n"
            "## Cross Pass (agent: codex, date: 2026-04-10)\n"
            "### Cross-spec consistency\n- None\n"
            "### Feasibility / tradeoff\n- None\n"
            "### Security / compliance\n- None\n"
            "### Dependency graph\n- None\n"
            "### Industry-pattern comparison\n- None\n\n"
            "## Verdict\n- status: ready\n- rationale: Clean.\n- follow-ups: none\n"
        )
        result = compute_flow_state(feature_dir)
        rm = _review_map(result)
        assert rm["review-spec"].status == "present"
        assert rm["review-spec"].evidence_sources

    def test_needs_revision(self, feature_dir: Path) -> None:
        spec = feature_dir / "spec.md"
        spec.write_text(
            "# Spec\n\n## Clarifications\n\n### Session 2026-04-10\n- Q: a → A: b\n"
        )
        (feature_dir / "review-spec.md").write_text(
            "# Review: Spec\n\n"
            "## Prerequisites\n- Clarify session: 2026-04-10\n\n"
            "## Cross Pass (agent: codex, date: 2026-04-10)\n"
            "### Cross-spec consistency\n- Conflict found\n\n"
            "## Verdict\n- status: needs-revision\n- rationale: Fix conflict.\n- follow-ups:\n  - resolve 018\n"
        )
        result = compute_flow_state(feature_dir)
        rm = _review_map(result)
        assert rm["review-spec"].status == "needs-revision"

    def test_stale_against_clarify(self, feature_dir: Path) -> None:
        spec = feature_dir / "spec.md"
        spec.write_text(
            "# Spec\n\n## Clarifications\n\n"
            "### Session 2026-04-10\n- Q: a → A: b\n\n"
            "### Session 2026-04-12\n- Q: c → A: d\n"
        )
        (feature_dir / "review-spec.md").write_text(
            "# Review: Spec\n\n"
            "## Prerequisites\n- Clarify session: 2026-04-10\n\n"
            "## Cross Pass (agent: codex, date: 2026-04-10)\n\n"
            "## Verdict\n- status: ready\n- rationale: Clean.\n- follow-ups: none\n"
        )
        result = compute_flow_state(feature_dir)
        rm = _review_map(result)
        assert rm["review-spec"].status == "stale"
        assert any("stale" in a for a in result.ambiguities)


class TestReviewCode:
    def test_not_started(self, feature_dir: Path) -> None:
        result = compute_flow_state(feature_dir)
        rm = _review_map(result)
        assert rm["review-code"].status == "not_started"

    def test_phases_partial(self, feature_dir: Path) -> None:
        (feature_dir / "review-code.md").write_text(
            "# Review: Code\n\n"
            "## US1 Self Pass (agent: claude, date: 2026-04-14)\n"
            "### Spec compliance\n- OK\n\n"
            "## US1 Cross Pass (agent: codex, date: 2026-04-14)\n"
            "### Spec compliance\n- OK\n"
        )
        result = compute_flow_state(feature_dir)
        rm = _review_map(result)
        assert rm["review-code"].status == "phases_partial"
        assert "US1" in rm["review-code"].notes[0]

    def test_overall_complete(self, feature_dir: Path) -> None:
        (feature_dir / "review-code.md").write_text(
            "# Review: Code\n\n"
            "## US1 Self Pass (agent: claude, date: 2026-04-14)\n\n"
            "## US1 Cross Pass (agent: codex, date: 2026-04-14)\n\n"
            "## Overall Verdict\n- status: ready-for-pr\n- rationale: Clean.\n- follow-ups: none\n"
        )
        result = compute_flow_state(feature_dir)
        rm = _review_map(result)
        assert rm["review-code"].status == "overall_complete"
        assert rm["review-code"].evidence_sources


class TestReviewPr:
    def test_not_started(self, feature_dir: Path) -> None:
        result = compute_flow_state(feature_dir)
        rm = _review_map(result)
        assert rm["review-pr"].status == "not_started"

    def test_pending_merge(self, feature_dir: Path) -> None:
        (feature_dir / "review-pr.md").write_text(
            "# Review: PR Comments\n\n"
            "## PR Identifier\n- repository: test/repo\n- number: 42\n- opened: 2026-04-16\n\n"
            "## External Comments\n\n"
            "## Retro Note\nNo workflow changes needed this cycle.\n\n"
            "## Verdict\n- status: pending-merge\n"
        )
        result = compute_flow_state(feature_dir)
        rm = _review_map(result)
        assert rm["review-pr"].status == "in_progress"

    def test_merged(self, feature_dir: Path) -> None:
        (feature_dir / "review-pr.md").write_text(
            "# Review: PR Comments\n\n"
            "## PR Identifier\n- repository: test/repo\n- number: 42\n- opened: 2026-04-16\n\n"
            "## External Comments\n\n"
            "## Retro Note\nCross-pass caught a real bug.\n\n"
            "## Verdict\n- status: merged\n- merged-at: 2026-04-16\n"
        )
        result = compute_flow_state(feature_dir)
        rm = _review_map(result)
        assert rm["review-pr"].status == "complete"


class TestReviewArtifactNames:
    def test_three_reviews_only(self) -> None:
        assert REVIEW_ARTIFACT_NAMES == ("review-spec", "review-code", "review-pr")

    def test_all_review_milestones_present(self, feature_dir: Path) -> None:
        result = compute_flow_state(feature_dir)
        types = {m.review_type for m in result.review_milestones}
        assert types == {"review-spec", "review-code", "review-pr"}


class TestNextStep:
    def test_suggests_review_spec(self, feature_dir: Path) -> None:
        (feature_dir / "spec.md").write_text("# Spec\n")
        (feature_dir / "plan.md").write_text("# Plan\n")
        (feature_dir / "tasks.md").write_text("# Tasks\n\n- [x] T1 done [@claude]\n")
        result = compute_flow_state(feature_dir)
        assert result.next_step and "review-spec" in result.next_step

    def test_suggests_review_code_after_spec_ready(self, feature_dir: Path) -> None:
        spec = feature_dir / "spec.md"
        spec.write_text(
            "# Spec\n\n## Clarifications\n\n### Session 2026-04-10\n- Q: a → A: b\n"
        )
        (feature_dir / "review-spec.md").write_text(
            "# Review: Spec\n\n"
            "## Prerequisites\n- Clarify session: 2026-04-10\n\n"
            "## Cross Pass (agent: codex, date: 2026-04-10)\n\n"
            "## Verdict\n- status: ready\n- rationale: ok\n- follow-ups: none\n"
        )
        result = compute_flow_state(feature_dir)
        assert result.next_step and "review-code" in result.next_step
