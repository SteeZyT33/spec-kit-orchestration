from __future__ import annotations

from pathlib import Path

import pytest

from speckit_orca.context_handoffs import (
    HandoffRecord,
    _sort_candidates,
    create_handoff,
    parse_handoff_file,
    resolve_handoff,
)


def _feature_dir(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    feature_dir = root / "specs" / "007-orca-context-handoffs"
    feature_dir.mkdir(parents=True)
    (root / ".specify").mkdir()
    return feature_dir


def test_create_and_parse_handoff_round_trip(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    (feature_dir / "brainstorm.md").write_text("# Brainstorm\n", encoding="utf-8")

    record = create_handoff(
        feature_dir,
        source_stage="brainstorm",
        target_stage="specify",
        summary="Turn the brainstorm into a feature spec.",
        upstream_artifacts=[feature_dir / "brainstorm.md"],
        open_questions=["Should embedded handoffs remain optional?"],
        branch="007-orca-context-handoffs-impl",
    )

    parsed = parse_handoff_file(feature_dir / "handoffs" / "brainstorm-to-specify.md", feature_dir=feature_dir)

    assert parsed.source_stage == "brainstorm"
    assert parsed.target_stage == "specify"
    assert parsed.summary == record.summary
    assert parsed.branch == "007-orca-context-handoffs-impl"
    assert parsed.upstream_artifacts == ["specs/007-orca-context-handoffs/brainstorm.md"]
    assert parsed.open_questions == ["Should embedded handoffs remain optional?"]


def test_resolve_prefers_canonical_file_over_embedded_section(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    brainstorm = feature_dir / "brainstorm.md"
    brainstorm.write_text(
        "\n".join(
            [
                "# Brainstorm",
                "",
                "## Handoff: brainstorm -> specify",
                "Source: brainstorm",
                "Target: specify",
                "Branch: feature-x",
                "Lane: lane-1",
                "Created: 2026-04-09T00:00:00Z",
                "",
                "## Summary",
                "Embedded version.",
                "",
                "## Upstream Artifacts",
                "- specs/007-orca-context-handoffs/brainstorm.md",
                "",
                "## Open Questions",
                "- None",
                "",
            ]
        ),
        encoding="utf-8",
    )
    create_handoff(
        feature_dir,
        source_stage="brainstorm",
        target_stage="specify",
        summary="Canonical file version.",
        upstream_artifacts=[brainstorm],
        branch="feature-x",
        lane_id="lane-1",
        created_at="2026-04-10T00:00:00Z",
    )

    result = resolve_handoff(
        feature_dir,
        source_stage="brainstorm",
        target_stage="specify",
        branch="feature-x",
        lane_id="lane-1",
    )

    assert result.winning_storage_shape == "file"
    assert result.resolved_handoff == "specs/007-orca-context-handoffs/handoffs/brainstorm-to-specify.md"
    assert result.used_branch_context is True
    assert result.used_lane_context is True


def test_resolve_falls_back_to_artifact_only_when_no_explicit_handoff_exists(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")

    result = resolve_handoff(feature_dir, target_stage="plan")

    assert result.winning_storage_shape == "artifact-only"
    assert result.resolved_handoff is None
    assert result.resolved_source_stage == "specify"
    assert result.resolved_artifacts == ["specs/007-orca-context-handoffs/spec.md"]
    assert "Inferred specify -> plan" in result.resolution_reason


def test_resolve_prefers_assign_context_for_implement_when_tasks_are_assigned(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    (feature_dir / "tasks.md").write_text("- [ ] T001 [@Backend Architect] Do the thing\n", encoding="utf-8")

    result = resolve_handoff(feature_dir, target_stage="implement")

    assert result.resolved_source_stage == "assign"
    assert result.resolved_artifacts == ["specs/007-orca-context-handoffs/tasks.md"]


def test_resolve_embedded_locator_uses_exact_section_title(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    spec_path = feature_dir / "spec.md"
    spec_path.write_text(
        "\n".join(
            [
                "# Feature Specification",
                "",
                "## Handoff: specify -> plan",
                "Source: specify",
                "Target: plan",
                "Branch: main",
                "Lane:",
                "Created: 2026-04-09T00:00:00Z",
                "",
                "## Summary",
                "Carry the agreed requirements into planning.",
                "",
                "## Upstream Artifacts",
                "- specs/007-orca-context-handoffs/spec.md",
                "",
                "## Open Questions",
                "- None",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = resolve_handoff(feature_dir, source_stage="specify", target_stage="plan", branch="main")

    assert result.winning_storage_shape == "embedded"
    assert result.resolved_handoff == (
        "specs/007-orca-context-handoffs/spec.md::section-title=Handoff: specify -> plan"
    )


def test_create_handoff_rejects_naive_created_at(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    (feature_dir / "brainstorm.md").write_text("# Brainstorm\n", encoding="utf-8")

    with pytest.raises(ValueError, match="timezone offset"):
        create_handoff(
            feature_dir,
            source_stage="brainstorm",
            target_stage="specify",
            summary="Turn the brainstorm into a feature spec.",
            upstream_artifacts=[feature_dir / "brainstorm.md"],
            created_at="2026-04-10T00:00:00",
        )


def test_sort_candidates_reports_ambiguity_for_top_rank_tie() -> None:
    record_a = HandoffRecord(
        source_stage="specify",
        target_stage="plan",
        summary="one",
        upstream_artifacts=["specs/007-orca-context-handoffs/spec.md"],
        open_questions=[],
        branch="main",
        lane_id=None,
        created_at="2026-04-09T00:00:00Z",
        storage_shape="file",
        locator="specs/007-orca-context-handoffs/handoffs/specify-to-plan-a.md",
    )
    record_b = HandoffRecord(
        source_stage="specify",
        target_stage="plan",
        summary="two",
        upstream_artifacts=["specs/007-orca-context-handoffs/spec.md"],
        open_questions=[],
        branch="main",
        lane_id=None,
        created_at="2026-04-09T00:00:00Z",
        storage_shape="file",
        locator="specs/007-orca-context-handoffs/handoffs/specify-to-plan-a.md",
    )

    ranked, ambiguity = _sort_candidates([record_a, record_b], branch="main", lane_id=None)

    assert len(ranked) == 2
    assert ambiguity is True
