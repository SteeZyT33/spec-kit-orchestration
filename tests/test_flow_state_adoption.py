from __future__ import annotations

from pathlib import Path

import pytest

from speckit_orca.adoption import create_record, retire_record, supersede_record
from speckit_orca.flow_state import (
    AdoptionFlowState,
    _is_adoption_target,
    compute_adoption_state,
    compute_flow_state,
    compute_spec_lite_state,
    main as flow_state_main,
)


def _make_ar(
    tmp_path: Path,
    *,
    title: str = "CLI entrypoint",
    summary: str = "Arg routing and dispatch.",
    location: list[str] | None = None,
    key_behaviors: list[str] | None = None,
):
    return create_record(
        repo_root=tmp_path,
        title=title,
        summary=summary,
        location=list(location) if location else ["src/foo/cli.py"],
        key_behaviors=list(key_behaviors) if key_behaviors else [
            "Dispatches to subcommands",
            "Loads config",
        ],
        baseline_commit=None,  # skip git lookup in tests
    )


def _make_full_spec(tmp_path: Path, spec_id: str) -> Path:
    feature_dir = tmp_path / "specs" / spec_id
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Feature Specification: Test\n")
    return feature_dir


# ---------------------------------------------------------------------------
# _is_adoption_target
# ---------------------------------------------------------------------------


def test_detects_canonical_adoption_path(tmp_path: Path) -> None:
    record = _make_ar(tmp_path, title="Detect me")
    assert _is_adoption_target(record.path) is True


def test_does_not_detect_feature_directory(tmp_path: Path) -> None:
    feature_dir = tmp_path / "specs" / "020-something"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Feature Specification\n")
    assert _is_adoption_target(feature_dir) is False
    assert _is_adoption_target(feature_dir / "spec.md") is False


def test_does_not_detect_overview_file(tmp_path: Path) -> None:
    _make_ar(tmp_path, title="Record for overview")
    overview = tmp_path / ".specify/orca/adopted/00-overview.md"
    assert overview.is_file()
    assert _is_adoption_target(overview) is False


def test_does_not_detect_nested_subdirectory(tmp_path: Path) -> None:
    """Parent chain check rejects files one level below adopted/."""
    nested = tmp_path / ".specify" / "orca" / "adopted" / "archive"
    nested.mkdir(parents=True)
    archived = nested / "AR-001-old.md"
    archived.write_text("Just a note, no header.\n")
    assert _is_adoption_target(archived) is False


def test_does_not_detect_spec_lite_record(tmp_path: Path) -> None:
    """A spec-lite record must not be detected as an AR target."""
    sl_dir = tmp_path / ".specify" / "orca" / "spec-lite"
    sl_dir.mkdir(parents=True)
    (sl_dir / "SL-001-unrelated.md").write_text(
        "# Spec-Lite SL-001: Unrelated\n"
    )
    assert _is_adoption_target(sl_dir / "SL-001-unrelated.md") is False


def test_detects_misplaced_ar_via_header(tmp_path: Path) -> None:
    misplaced = tmp_path / "specs" / "AR-007-elsewhere" / "spec.md"
    misplaced.parent.mkdir(parents=True)
    misplaced.write_text(
        "# Adoption Record: AR-007: Misplaced record\n\n"
        "**Status**: adopted\n"
        "**Adopted-on**: 2026-04-15\n\n"
        "## Summary\ns\n"
    )
    assert _is_adoption_target(misplaced) is True


def test_header_fallback_rejects_titleless_headers(tmp_path: Path) -> None:
    """Header regex requires `: <title>` — stubs must not match."""
    for bad_header in (
        "# Adoption Record: AR-007\n",           # no colon, no title
        "# Adoption Record: AR-007:\n",          # colon, no title
        "# Adoption Record: AR-007:   \n",       # colon with spaces only
    ):
        misplaced = tmp_path / f"note_{hash(bad_header) & 0xffff}.md"
        misplaced.write_text(bad_header)
        assert _is_adoption_target(misplaced) is False, (
            f"Header {bad_header!r} should not match"
        )


# ---------------------------------------------------------------------------
# compute_adoption_state
# ---------------------------------------------------------------------------


def test_compute_adoption_state_returns_expected_view(tmp_path: Path) -> None:
    record = _make_ar(
        tmp_path,
        title="Round trip view",
        location=["a.py", "b.py"],
        key_behaviors=["alpha", "beta"],
    )
    view = compute_adoption_state(record.path)
    assert isinstance(view, AdoptionFlowState)
    assert view.kind == "adoption"
    assert view.record_id == record.record_id
    assert view.slug == record.slug
    assert view.title == "Round trip view"
    assert view.status == "adopted"
    assert view.location == ["a.py", "b.py"]
    assert view.key_behaviors == ["alpha", "beta"]
    assert view.review_state == "not-applicable"
    assert view.superseded_by is None
    assert view.retirement_reason is None


def test_view_reflects_supersede_and_retire_transitions(tmp_path: Path) -> None:
    record = _make_ar(tmp_path, title="Transition me")
    _make_full_spec(tmp_path, "020-replacement")
    supersede_record(
        repo_root=tmp_path,
        record_id=record.record_id,
        superseded_by="020-replacement",
    )
    superseded_view = compute_adoption_state(record.path)
    assert superseded_view.status == "superseded"
    assert superseded_view.superseded_by == "020-replacement"

    retire_record(
        repo_root=tmp_path,
        record_id=record.record_id,
        reason="Feature removed",
    )
    retired_view = compute_adoption_state(record.path)
    assert retired_view.status == "retired"
    assert retired_view.retirement_reason == "Feature removed"


def test_review_state_is_always_not_applicable(tmp_path: Path) -> None:
    """Hard invariant per 015 contract — regardless of record state."""
    record = _make_ar(tmp_path, title="Review invariant")
    _make_full_spec(tmp_path, "020-replacement")
    assert compute_adoption_state(record.path).review_state == "not-applicable"
    supersede_record(
        repo_root=tmp_path, record_id=record.record_id,
        superseded_by="020-replacement",
    )
    assert compute_adoption_state(record.path).review_state == "not-applicable"
    retire_record(repo_root=tmp_path, record_id=record.record_id)
    assert compute_adoption_state(record.path).review_state == "not-applicable"


def test_compute_adoption_state_on_malformed_returns_invalid(
    tmp_path: Path,
) -> None:
    directory = tmp_path / ".specify/orca/adopted"
    directory.mkdir(parents=True)
    bad = directory / "AR-042-broken.md"
    bad.write_text(
        "# Adoption Record: AR-042: Broken\n\n"
        "**Status**: adopted\n\nnot enough metadata\n"
    )
    view = compute_adoption_state(bad)
    # Per 015 contract: malformed records carry kind "adoption" with
    # status "invalid", NOT a separate "adoption-invalid" kind.
    assert view.kind == "adoption"
    assert view.status == "invalid"
    assert view.record_id == "AR-042"
    payload = view.to_dict()
    assert payload["kind"] == "adoption"
    assert payload["status"] == "invalid"
    assert payload["id"] == "AR-042"
    assert "record_id" not in payload


def test_compute_adoption_state_wraps_unreadable_file(tmp_path: Path) -> None:
    """Non-UTF-8 files degrade to invalid view, not a crash."""
    directory = tmp_path / ".specify/orca/adopted"
    directory.mkdir(parents=True)
    bad = directory / "AR-099-binary.md"
    bad.write_bytes(b"\xff\xfe\x00binary\x80\x81")
    view = compute_adoption_state(bad)
    assert view.kind == "adoption"
    assert view.status == "invalid"


# ---------------------------------------------------------------------------
# Regression — full-spec and spec-lite paths unchanged
# ---------------------------------------------------------------------------


def test_full_spec_flow_unchanged_for_feature_directory(tmp_path: Path) -> None:
    feature_dir = tmp_path / "specs" / "020-full-spec"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(
        "# Feature Specification: Full Spec Example\n"
    )
    result = compute_flow_state(feature_dir)
    assert result.feature_id == "020-full-spec"
    assert isinstance(result.review_milestones, list)
    assert not hasattr(result, "key_behaviors")


def test_spec_lite_flow_still_works(tmp_path: Path) -> None:
    """Regression: adoption additions did not break 013 spec-lite path."""
    from speckit_orca.spec_lite import create_record as create_sl

    record = create_sl(
        repo_root=tmp_path,
        title="Spec-lite round-trip",
        problem="p",
        solution="s",
        acceptance="given/when/then",
        files_affected=["foo.py"],
    )
    view = compute_spec_lite_state(record.path)
    assert view.kind == "spec-lite"


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------


def test_cli_dispatches_to_adoption_for_ar_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = _make_ar(tmp_path, title="CLI target")
    rc = flow_state_main([str(record.path), "--format", "json"])
    assert rc == 0
    captured = capsys.readouterr()
    assert '"kind": "adoption"' in captured.out
    assert record.record_id in captured.out
    assert '"review_state": "not-applicable"' in captured.out
    # Contract-aligned JSON key: `id`, not `record_id`.
    assert '"id":' in captured.out
    assert '"record_id"' not in captured.out


def test_cli_text_format_for_adoption(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = _make_ar(tmp_path, title="Text mode")
    rc = flow_state_main([str(record.path), "--format", "text"])
    assert rc == 0
    captured = capsys.readouterr()
    stem = f"{record.record_id}-{record.slug}"
    assert f"Adoption record: {stem}" in captured.out
    assert "Status: adopted" in captured.out
    assert "Review state: not-applicable" in captured.out


def test_cli_still_dispatches_spec_lite_for_sl_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Adoption additions must not break spec-lite CLI dispatch."""
    from speckit_orca.spec_lite import create_record as create_sl

    record = create_sl(
        repo_root=tmp_path,
        title="SL dispatch",
        problem="p", solution="s",
        acceptance="given/when/then",
        files_affected=["foo.py"],
    )
    rc = flow_state_main([str(record.path), "--format", "json"])
    assert rc == 0
    captured = capsys.readouterr()
    assert '"kind": "spec-lite"' in captured.out
