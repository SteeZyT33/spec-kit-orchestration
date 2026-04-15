from __future__ import annotations

from pathlib import Path

import pytest

from speckit_orca.spec_lite import (
    SpecLiteError,
    SpecLiteParseError,
    create_record,
    get_record,
    list_records,
    parse_record,
    regenerate_overview,
    update_status,
)


def _make_record(
    tmp_path: Path,
    *,
    title: str = "Fix thing",
    problem: str = "A thing is broken.",
    solution: str = "We fix it.",
    acceptance: str = "Given X when Y then Z.",
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


def test_create_assigns_sequential_id_and_writes_file(tmp_path: Path) -> None:
    first = _make_record(tmp_path, title="First work")
    second = _make_record(tmp_path, title="Second work")

    assert first.record_id == "SL-001"
    assert second.record_id == "SL-002"
    assert first.path.name == "SL-001-first-work.md"
    assert second.path.name == "SL-002-second-work.md"
    assert first.status == "open"
    assert first.path.read_text().startswith("# Spec-Lite SL-001: First work")


def test_create_rejects_empty_files_affected(tmp_path: Path) -> None:
    with pytest.raises(SpecLiteError):
        create_record(
            repo_root=tmp_path,
            title="No files",
            problem="p",
            solution="s",
            acceptance="a",
            files_affected=[],
        )


def test_id_allocation_with_gap(tmp_path: Path) -> None:
    _make_record(tmp_path, title="One")
    two = _make_record(tmp_path, title="Two")
    # Delete SL-001 file; next create should pick SL-003, not backfill.
    (tmp_path / ".specify/orca/spec-lite" / "SL-001-one.md").unlink()
    three = _make_record(tmp_path, title="Three")
    assert two.record_id == "SL-002"
    assert three.record_id == "SL-003"


def test_round_trip_parse_matches_create(tmp_path: Path) -> None:
    created = _make_record(
        tmp_path,
        title="Round trip",
        files_affected=["a.py", "b.py"],
    )
    parsed = parse_record(created.path)
    assert parsed.record_id == created.record_id
    assert parsed.title == created.title
    assert parsed.problem == created.problem
    assert parsed.files_affected == ["a.py", "b.py"]
    assert parsed.verification_evidence is None


def test_update_status_transitions_and_attaches_evidence(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="Implement me")
    updated = update_status(
        repo_root=tmp_path,
        record_id=record.record_id,
        new_status="implemented",
        verification_evidence="pytest passed: 3 / 3",
    )
    assert updated.status == "implemented"
    assert updated.verification_evidence == "pytest passed: 3 / 3"
    reparsed = parse_record(record.path)
    assert reparsed.status == "implemented"
    assert reparsed.verification_evidence == "pytest passed: 3 / 3"


def test_update_status_without_evidence_preserves_existing(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="Preserve evidence")
    update_status(
        repo_root=tmp_path,
        record_id=record.record_id,
        new_status="implemented",
        verification_evidence="first run",
    )
    update_status(
        repo_root=tmp_path,
        record_id=record.record_id,
        new_status="abandoned",
    )
    reparsed = parse_record(record.path)
    assert reparsed.status == "abandoned"
    assert reparsed.verification_evidence == "first run"


def test_update_status_rejects_invalid_status(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="Bad status")
    with pytest.raises(SpecLiteError):
        update_status(
            repo_root=tmp_path,
            record_id=record.record_id,
            new_status="bogus",
        )


def test_list_filters_by_status(tmp_path: Path) -> None:
    a = _make_record(tmp_path, title="Open one")
    b = _make_record(tmp_path, title="Will be done")
    update_status(
        repo_root=tmp_path, record_id=b.record_id, new_status="implemented"
    )
    open_records = list_records(repo_root=tmp_path, status="open")
    done_records = list_records(repo_root=tmp_path, status="implemented")
    all_records = list_records(repo_root=tmp_path)

    assert [r.record_id for r in open_records] == [a.record_id]
    assert [r.record_id for r in done_records] == [b.record_id]
    assert {r.record_id for r in all_records} == {a.record_id, b.record_id}


def test_list_rejects_invalid_status_filter(tmp_path: Path) -> None:
    with pytest.raises(SpecLiteError):
        list_records(repo_root=tmp_path, status="bogus")


def test_get_record_resolves_id_without_slug(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="Lookup me")
    by_stem = get_record(repo_root=tmp_path, record_id=record.record_id)
    by_id_with_slug = get_record(
        repo_root=tmp_path, record_id=f"{record.record_id}-{record.slug}"
    )
    assert by_stem.title == record.title
    assert by_id_with_slug.title == record.title


def test_get_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(SpecLiteError):
        get_record(repo_root=tmp_path, record_id="SL-999")


def test_regenerate_overview_groups_records_by_status(tmp_path: Path) -> None:
    a = _make_record(tmp_path, title="Stays open")
    b = _make_record(tmp_path, title="Becomes implemented")
    c = _make_record(tmp_path, title="Becomes abandoned")
    update_status(
        repo_root=tmp_path, record_id=b.record_id, new_status="implemented"
    )
    update_status(
        repo_root=tmp_path, record_id=c.record_id, new_status="abandoned"
    )

    overview = regenerate_overview(tmp_path)
    text = overview.read_text()
    assert "# Spec-Lite Overview" in text

    active_section, rest = text.split("## Implemented records", 1)
    implemented_section, abandoned_section = rest.split(
        "## Abandoned records", 1
    )

    assert a.record_id in active_section
    assert b.record_id not in active_section
    assert b.record_id in implemented_section
    assert c.record_id in abandoned_section
    # 00-overview.md itself excluded from record listing.
    assert "00-overview" not in text


def test_regenerate_overview_on_empty_registry(tmp_path: Path) -> None:
    overview = regenerate_overview(tmp_path)
    text = overview.read_text()
    assert "_No active records._" in text
    assert "_No implemented records._" in text
    assert "_No abandoned records._" in text


def test_parse_malformed_record_raises(tmp_path: Path) -> None:
    directory = tmp_path / ".specify/orca/spec-lite"
    directory.mkdir(parents=True)
    bad = directory / "SL-001-broken.md"
    bad.write_text("# Not a spec-lite header\n\ntext\n")
    with pytest.raises(SpecLiteParseError):
        parse_record(bad)


def test_parse_missing_required_section(tmp_path: Path) -> None:
    directory = tmp_path / ".specify/orca/spec-lite"
    directory.mkdir(parents=True)
    bad = directory / "SL-001-no-solution.md"
    bad.write_text(
        "# Spec-Lite SL-001: Missing section\n\n"
        "**Source Name**: operator\n"
        "**Created**: 2026-04-15\n"
        "**Status**: open\n\n"
        "## Problem\nsomething\n\n"
        "## Acceptance Scenario\nwhen X then Y\n\n"
        "## Files Affected\n- foo.py\n"
    )
    with pytest.raises(SpecLiteParseError):
        parse_record(bad)


def test_parse_empty_verification_evidence_section_is_invalid(
    tmp_path: Path,
) -> None:
    directory = tmp_path / ".specify/orca/spec-lite"
    directory.mkdir(parents=True)
    bad = directory / "SL-001-empty-ve.md"
    bad.write_text(
        "# Spec-Lite SL-001: Empty VE\n\n"
        "**Source Name**: operator\n"
        "**Created**: 2026-04-15\n"
        "**Status**: open\n\n"
        "## Problem\np\n\n"
        "## Solution\ns\n\n"
        "## Acceptance Scenario\na\n\n"
        "## Files Affected\n- foo.py\n\n"
        "## Verification Evidence\n\n"
    )
    with pytest.raises(SpecLiteParseError):
        parse_record(bad)


def test_list_skips_malformed_records(tmp_path: Path) -> None:
    good = _make_record(tmp_path, title="Good record")
    bad = good.path.parent / "SL-999-broken.md"
    bad.write_text("garbage content\n")
    records = list_records(repo_root=tmp_path)
    assert [r.record_id for r in records] == [good.record_id]


def test_create_respects_source_name_and_date(tmp_path: Path) -> None:
    record = _make_record(
        tmp_path,
        title="Custom meta",
        source_name="codex",
        created="2025-12-01",
    )
    parsed = parse_record(record.path)
    assert parsed.source_name == "codex"
    assert parsed.created == "2025-12-01"


def test_create_rejects_invalid_date(tmp_path: Path) -> None:
    directory = tmp_path / ".specify/orca/spec-lite"
    directory.mkdir(parents=True)
    bad = directory / "SL-001-bad-date.md"
    bad.write_text(
        "# Spec-Lite SL-001: Bad date\n\n"
        "**Source Name**: operator\n"
        "**Created**: not-a-date\n"
        "**Status**: open\n\n"
        "## Problem\np\n\n"
        "## Solution\ns\n\n"
        "## Acceptance Scenario\na\n\n"
        "## Files Affected\n- foo.py\n"
    )
    with pytest.raises(SpecLiteParseError):
        parse_record(bad)
