from __future__ import annotations

from pathlib import Path

import pytest

from speckit_orca.flow_state import (
    SpecLiteFlowState,
    _is_spec_lite_target,
    compute_flow_state,
    compute_spec_lite_state,
    main as flow_state_main,
)
from speckit_orca.spec_lite import create_record, update_status


def _make_record(
    tmp_path: Path,
    *,
    title: str = "Sample",
    problem: str = "p",
    solution: str = "s",
    acceptance: str = "given/when/then",
    files_affected: list[str] | None = None,
    source_name: str = "operator",
    created: str | None = None,
):
    return create_record(
        repo_root=tmp_path,
        title=title,
        problem=problem,
        solution=solution,
        acceptance=acceptance,
        files_affected=list(files_affected) if files_affected else ["src/foo.py"],
        source_name=source_name,
        created=created,
    )


def test_detects_canonical_spec_lite_path(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="Detect me")
    assert _is_spec_lite_target(record.path) is True


def test_does_not_detect_feature_directory(tmp_path: Path) -> None:
    feature_dir = tmp_path / "specs" / "020-something"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Feature Specification\n")
    assert _is_spec_lite_target(feature_dir) is False
    assert _is_spec_lite_target(feature_dir / "spec.md") is False


def test_does_not_detect_overview_file(tmp_path: Path) -> None:
    _make_record(tmp_path, title="Record for overview fixture")
    overview = tmp_path / ".specify/orca/spec-lite/00-overview.md"
    assert overview.is_file()
    assert _is_spec_lite_target(overview) is False


def test_detects_misplaced_record_via_header(tmp_path: Path) -> None:
    misplaced = tmp_path / "specs" / "SL-007-elsewhere" / "spec.md"
    misplaced.parent.mkdir(parents=True)
    misplaced.write_text(
        "# Spec-Lite SL-007: Misplaced record\n\n"
        "**Source Name**: operator\n"
        "**Created**: 2026-04-15\n"
        "**Status**: open\n\n"
        "## Problem\np\n"
    )
    assert _is_spec_lite_target(misplaced) is True


def test_compute_spec_lite_state_returns_expected_view(tmp_path: Path) -> None:
    record = _make_record(
        tmp_path,
        title="Round trip view",
        files_affected=["a.py", "b.py"],
        source_name="codex",
    )
    view = compute_spec_lite_state(record.path)
    assert isinstance(view, SpecLiteFlowState)
    assert view.kind == "spec-lite"
    assert view.record_id == record.record_id
    assert view.slug == record.slug
    assert view.title == "Round trip view"
    assert view.source_name == "codex"
    assert view.status == "open"
    assert view.files_affected == ["a.py", "b.py"]
    assert view.has_verification_evidence is False
    assert view.review_state == "unreviewed"


def test_view_reflects_status_transitions(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="Transition target")
    update_status(
        repo_root=tmp_path,
        record_id=record.record_id,
        new_status="implemented",
        verification_evidence="pytest green",
    )
    view = compute_spec_lite_state(record.path)
    assert view.status == "implemented"
    assert view.has_verification_evidence is True


def test_review_state_unreviewed_by_default(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="Unreviewed default")
    view = compute_spec_lite_state(record.path)
    assert view.review_state == "unreviewed"


def test_review_state_self_reviewed_when_sibling_present(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="Self-reviewed")
    sibling = record.path.parent / f"{record.record_id}-{record.slug}.self-review.md"
    sibling.write_text("# self review\n\nlooks fine\n")
    view = compute_spec_lite_state(record.path)
    assert view.review_state == "self-reviewed"
    # The sibling file itself must NOT be detected as a spec-lite target.
    assert _is_spec_lite_target(sibling) is False


def test_review_state_cross_reviewed_takes_precedence(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="Cross-reviewed")
    stem = f"{record.record_id}-{record.slug}"
    self_path = record.path.parent / f"{stem}.self-review.md"
    cross_path = record.path.parent / f"{stem}.cross-review.md"
    self_path.write_text("self\n")
    cross_path.write_text("cross\n")
    view = compute_spec_lite_state(record.path)
    assert view.review_state == "cross-reviewed"
    # Neither sibling review file should be detected as a spec-lite target.
    assert _is_spec_lite_target(self_path) is False
    assert _is_spec_lite_target(cross_path) is False


def test_is_spec_lite_target_rejects_nested_subdirectory(tmp_path: Path) -> None:
    """Path match requires the file IMMEDIATELY inside `spec-lite/`.

    A file one level deeper (e.g., in an `archive/` subdir) must NOT
    satisfy the path-match rule. A valid header WOULD still match via
    the defensive header-fallback — so this test uses content without
    a valid header to isolate the path-check behavior.
    """
    nested = tmp_path / ".specify" / "orca" / "spec-lite" / "archive"
    nested.mkdir(parents=True)
    archived = nested / "SL-001-old.md"
    # Non-header content so the header-match fallback doesn't catch
    # this file — we're testing path rejection specifically.
    archived.write_text("Just a note about SL-001. Not a real record.\n")
    assert _is_spec_lite_target(archived) is False


def test_compute_spec_lite_state_on_malformed_returns_invalid(tmp_path: Path) -> None:
    directory = tmp_path / ".specify/orca/spec-lite"
    directory.mkdir(parents=True)
    bad = directory / "SL-042-broken.md"
    bad.write_text("# Spec-Lite SL-042: Broken\n\nsome garbage\n")
    view = compute_spec_lite_state(bad)
    # Per 013 contract: malformed records carry kind "spec-lite"
    # with status "invalid", NOT a separate "spec-lite-invalid" kind.
    assert view.kind == "spec-lite"
    assert view.status == "invalid"
    assert view.record_id == "SL-042"
    # JSON serialization must emit "id", not "record_id".
    payload = view.to_dict()
    assert payload["kind"] == "spec-lite"
    assert payload["status"] == "invalid"
    assert payload["id"] == "SL-042"
    assert "record_id" not in payload


def test_full_spec_flow_unchanged_for_feature_directory(tmp_path: Path) -> None:
    """Regression: spec-lite changes do not break full-spec interpretation."""
    feature_dir = tmp_path / "specs" / "020-full-spec"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(
        "# Feature Specification: Full Spec Example\n\n"
        "## User Scenarios & Testing\n"
        "Scenario text.\n"
    )
    result = compute_flow_state(feature_dir)
    assert result.feature_id == "020-full-spec"
    assert isinstance(result.review_milestones, list)
    # Should NOT have the SpecLiteFlowState fields
    assert not hasattr(result, "has_verification_evidence")


def test_cli_dispatches_to_spec_lite_for_record_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = _make_record(tmp_path, title="CLI target")
    rc = flow_state_main([str(record.path), "--format", "json"])
    assert rc == 0
    captured = capsys.readouterr()
    assert '"kind": "spec-lite"' in captured.out
    assert record.record_id in captured.out


def test_cli_text_format_for_spec_lite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = _make_record(tmp_path, title="Plain text output")
    rc = flow_state_main([str(record.path), "--format", "text"])
    assert rc == 0
    captured = capsys.readouterr()
    assert f"Spec-lite: {record.record_id}-{record.slug}" in captured.out
    assert "Status: open" in captured.out
    assert "Review state: unreviewed" in captured.out


def test_cli_still_works_for_feature_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    feature_dir = tmp_path / "specs" / "020-regression"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Feature Specification: Regression\n")
    rc = flow_state_main([str(feature_dir), "--format", "json"])
    assert rc == 0
    captured = capsys.readouterr()
    # Full-spec output has feature_id + current_stage keys
    assert '"feature_id"' in captured.out
    assert '"current_stage"' in captured.out


def test_is_spec_lite_target_requires_contiguous_subpath(tmp_path: Path) -> None:
    """Defensive: paths containing all three dir names non-contiguously must NOT match.

    e.g. a file at `.specify/unrelated/orca/elsewhere/spec-lite-notes/SL-001.md`
    technically has `.specify`, `orca`, and `spec-lite` as path
    segments (as substrings within segment names), but not as a
    contiguous `.specify/orca/spec-lite` prefix. Only the canonical
    layout should match.
    """
    misleading = tmp_path / ".specify" / "other" / "orca" / "spec-lite-notes"
    misleading.mkdir(parents=True)
    # Note: this path has `.specify`, `orca` parts AND a dir called
    # `spec-lite-notes` (whose name contains "spec-lite" as a substring
    # but not as an exact part). Write a SL-NNN-looking file.
    f = misleading / "SL-001-note.md"
    f.write_text("# Spec-Lite SL-001: Note\n\n")  # header match would still catch
    # But with contiguous subpath fix, path match should miss.
    # Header match will rescue it IF the header is valid — we
    # wrote a minimal header so it matches. Test the path check
    # itself by writing content that WOULDN'T match the header.
    f.write_text("Not a spec-lite header\n")
    assert _is_spec_lite_target(f) is False


def test_spec_lite_view_emits_id_key_not_record_id(tmp_path: Path) -> None:
    """The 013 contract uses `id` as the JSON key, not `record_id`."""
    record = _make_record(tmp_path, title="Key shape check")
    view = compute_spec_lite_state(record.path)
    payload = view.to_dict()
    assert payload["id"] == record.record_id
    assert "record_id" not in payload
