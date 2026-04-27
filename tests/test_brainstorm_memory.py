from __future__ import annotations

from pathlib import Path

import pytest

from orca.brainstorm_memory import (
    _brainstorm_files,
    _significant_length,
    append_revision,
    create_record,
    parse_record,
    regenerate_overview,
    root_from_record_path,
)


def _sections(**overrides: str) -> dict[str, str]:
    base = {
        "Problem": "Need durable brainstorm history.",
        "Desired Outcome": "Save meaningful ideation without losing context.",
        "Constraints": "",
        "Existing Context": "",
        "Options Considered": "- Inbox only\n- Durable brainstorm memory",
        "Recommendation": "Use durable brainstorm records.",
        "Open Questions": "- Should status be visible in overview?",
        "Ready For Spec": "",
        "Revisions": "",
    }
    base.update(overrides)
    return base


def test_create_record_allows_partial_meaningful_sections(tmp_path: Path) -> None:
    record = create_record(tmp_path, "Workflow Upgrade", "parked", _sections())
    parsed = parse_record(record.path)

    assert parsed.status == "parked"
    assert parsed.sections["Constraints"] == ""
    assert parsed.sections["Ready For Spec"] == ""


def test_append_revision_rejects_illegal_state_regression(tmp_path: Path) -> None:
    record = create_record(
        tmp_path,
        "Workflow Upgrade",
        "spec-created",
        _sections(**{"Ready For Spec": "Recommend /speckit.plan"}),
        downstream="spec:004-orca-workflow-system-upgrade",
    )

    with pytest.raises(ValueError, match="Illegal brainstorm status transition"):
        append_revision(record.path, "Tried to reopen as raw idea.", status="active")


def test_root_from_record_path_requires_brainstorm_parent(tmp_path: Path) -> None:
    invalid = tmp_path / "notes" / "01-random.md"
    invalid.parent.mkdir(parents=True)
    invalid.write_text("# not a brainstorm file\n", encoding="utf-8")

    with pytest.raises(ValueError, match="brainstorm/"):
        root_from_record_path(invalid)


def test_regenerate_overview_uses_existing_records(tmp_path: Path) -> None:
    record = create_record(
        tmp_path,
        "Agent Selection",
        "spec-created",
        _sections(**{"Ready For Spec": "Recommend /speckit.specify"}),
        downstream="spec:003-cross-review-agent-selection",
    )
    overview = regenerate_overview(tmp_path)

    text = overview.read_text(encoding="utf-8")
    assert "Agent Selection" in text
    assert "spec:003-cross-review-agent-selection" in text
    assert record.path.exists()


def test_significant_length_ignores_all_whitespace() -> None:
    sections = _sections(
        **{
            "Problem": "word\tone\nword two",
            "Desired Outcome": "",
            "Options Considered": "",
            "Recommendation": "",
            "Open Questions": "",
        }
    )

    assert _significant_length(sections) == len("wordonewordtwo")


def test_parse_record_rejects_header_filename_number_mismatch(tmp_path: Path) -> None:
    record = create_record(tmp_path, "Workflow Upgrade", "active", _sections())
    record.path.write_text(
        record.path.read_text(encoding="utf-8").replace(
            "# Brainstorm 01: Workflow Upgrade",
            "# Brainstorm 99: Workflow Upgrade",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not match filename prefix"):
        parse_record(record.path)


def test_brainstorm_files_sort_by_numeric_prefix(tmp_path: Path) -> None:
    directory = tmp_path / "brainstorm"
    directory.mkdir()
    for name in ("100-last.md", "11-middle.md", "2-first.md"):
        (directory / name).write_text("", encoding="utf-8")

    assert [path.name for path in _brainstorm_files(tmp_path)] == [
        "2-first.md",
        "11-middle.md",
        "100-last.md",
    ]


def test_regenerate_overview_escapes_table_cells(tmp_path: Path) -> None:
    create_record(
        tmp_path,
        "Agent | Selection",
        "spec-created",
        _sections(**{"Ready For Spec": "Recommend /speckit.specify"}),
        downstream="spec:003|cross-review-agent-selection",
    )

    overview = regenerate_overview(tmp_path)
    text = overview.read_text(encoding="utf-8")

    assert "Agent \\| Selection" in text
    assert "spec:003\\|cross-review-agent-selection" in text
