from __future__ import annotations

from pathlib import Path

import pytest

from speckit_orca.evolve import (
    create_entry,
    list_entries,
    main,
    parse_entry,
    regenerate_overview,
    seed_initial_entries,
    update_entry,
)


def test_create_entry_and_regenerate_overview(tmp_path: Path) -> None:
    entry = create_entry(
        tmp_path,
        title="Resume Controls",
        source_name="cc-spex",
        source_ref="docs/orca-harvest-matrix.md",
        summary="Persisted resume and start-from controls.",
        decision="direct-take",
        rationale="Needed for orchestration reliability.",
        target_kind="existing-spec",
        target_ref="009-orca-yolo",
        current_date="2026-04-10",
    )

    overview = regenerate_overview(tmp_path)
    text = overview.read_text(encoding="utf-8")

    assert entry.entry_id == "EV-001"
    assert "Resume Controls" in text
    assert "existing-spec:009-orca-yolo" in text


def test_wrapper_capability_requires_dependency_and_boundary(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="external_dependency"):
        create_entry(
            tmp_path,
            title="Deep Optimize",
            source_name="autoresearch",
            source_ref="notes",
            summary="Thin wrapper.",
            decision="adapt-heavily",
            rationale="Wrapper only.",
            entry_kind="wrapper-capability",
            target_kind="future-feature",
            target_ref="deep-optimize",
            current_date="2026-04-10",
        )


def test_update_entry_can_map_open_item(tmp_path: Path) -> None:
    entry = create_entry(
        tmp_path,
        title="Flow Status Line",
        source_name="cc-spex",
        source_ref="docs/orca-harvest-matrix.md",
        summary="Persistent flow state.",
        decision="adapt-heavily",
        rationale="Good principle, needs Orca adaptation.",
        current_date="2026-04-10",
    )

    updated = update_entry(
        entry.path,
        target_kind="existing-spec",
        target_ref="005-orca-flow-state",
        status="mapped",
        mapping_notes="Maps into the flow-state runtime and docs.",
        current_date="2026-04-11",
    )

    assert updated.target_kind == "existing-spec"
    assert updated.target_ref == "005-orca-flow-state"
    assert updated.status == "mapped"


def test_parse_entry_rejects_mapped_entry_without_target(tmp_path: Path) -> None:
    entry = create_entry(
        tmp_path,
        title="Portable Principle",
        source_name="external",
        source_ref="source",
        summary="Summary",
        decision="adapt-heavily",
        rationale="Rationale",
        current_date="2026-04-10",
    )
    entry.path.write_text(
        entry.path.read_text(encoding="utf-8").replace("**Status**: open", "**Status**: mapped"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires a target mapping"):
        parse_entry(entry.path)


def test_seed_initial_entries_is_idempotent(tmp_path: Path) -> None:
    first = seed_initial_entries(tmp_path, current_date="2026-04-10")
    first_ids = [entry.entry_id for entry in first]
    entries_path = tmp_path / ".specify" / "orca" / "evolve"
    first_snapshot = {
        str(path.relative_to(entries_path)): path.read_text(encoding="utf-8")
        for path in sorted(entries_path.rglob("*.md"))
    }
    second = seed_initial_entries(tmp_path, current_date="2026-04-10")
    second_ids = [entry.entry_id for entry in second]
    second_snapshot = {
        str(path.relative_to(entries_path)): path.read_text(encoding="utf-8")
        for path in sorted(entries_path.rglob("*.md"))
    }

    assert first_ids == second_ids
    assert len(list_entries(tmp_path)) == len(first)
    assert first_snapshot == second_snapshot
    assert (tmp_path / ".specify" / "orca" / "evolve" / "00-overview.md").exists()


def test_parse_entry_normalizes_empty_mapping_notes(tmp_path: Path) -> None:
    entry = create_entry(
        tmp_path,
        title="Empty Mapping Notes",
        source_name="cc-spex",
        source_ref="docs/orca-harvest-matrix.md",
        summary="Summary",
        decision="adapt-heavily",
        rationale="Rationale",
        current_date="2026-04-10",
    )

    parsed = parse_entry(entry.path)

    assert parsed.mapping_notes == ""


def test_update_entry_clears_stale_terminal_status(tmp_path: Path) -> None:
    entry = create_entry(
        tmp_path,
        title="Deferred Wrapper",
        source_name="external",
        source_ref="source",
        summary="Summary",
        decision="defer",
        rationale="Not ready yet.",
        current_date="2026-04-10",
    )

    updated = update_entry(
        entry.path,
        decision="adapt-heavily",
        current_date="2026-04-11",
    )

    assert updated.status == "open"
    assert updated.updated_at == "2026-04-11"


def test_parse_entry_rejects_invalid_date_metadata(tmp_path: Path) -> None:
    entry = create_entry(
        tmp_path,
        title="Bad Dates",
        source_name="external",
        source_ref="source",
        summary="Summary",
        decision="adapt-heavily",
        rationale="Rationale",
        current_date="2026-04-10",
    )
    entry.path.write_text(
        entry.path.read_text(encoding="utf-8").replace("**Created**: 2026-04-10", "**Created**: not-a-date"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid Created date"):
        parse_entry(entry.path)


def test_parse_entry_rejects_updated_before_created(tmp_path: Path) -> None:
    entry = create_entry(
        tmp_path,
        title="Backwards Dates",
        source_name="external",
        source_ref="source",
        summary="Summary",
        decision="adapt-heavily",
        rationale="Rationale",
        current_date="2026-04-10",
    )
    entry.path.write_text(
        entry.path.read_text(encoding="utf-8").replace("**Updated**: 2026-04-10", "**Updated**: 2026-04-09"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not be earlier than Created"):
        parse_entry(entry.path)


def test_update_cli_rejects_paths_outside_inventory(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text(
        "\n".join(
            [
                "# Evolve Entry EV-001: Outside",
                "",
                "**Source Name**: external",
                "**Source Ref**: source",
                "**Decision**: direct-take",
                "**Status**: open",
                "**Entry Kind**: pattern",
                "**Target Kind**: none",
                "**Target Ref**: none",
                "**Follow Up Ref**: none",
                "**Adoption Scope**: portable-principle",
                "**External Dependency**: none",
                "**Ownership Boundary**: none",
                "**Created**: 2026-04-10",
                "**Updated**: 2026-04-10",
                "",
                "## Summary",
                "Summary",
                "",
                "## Rationale",
                "Rationale",
                "",
                "## Mapping Notes",
                "(none)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "update",
            str(outside),
            "--date",
            "2026-04-11",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "update path must live under" in captured.err


def test_parse_entry_rejects_rejected_status_without_reject_decision(tmp_path: Path) -> None:
    entry = create_entry(
        tmp_path,
        title="Mismatched Rejected Status",
        source_name="external",
        source_ref="source",
        summary="Summary",
        decision="adapt-heavily",
        rationale="Rationale",
        current_date="2026-04-10",
    )
    entry.path.write_text(
        entry.path.read_text(encoding="utf-8").replace("**Status**: open", "**Status**: rejected"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="status 'rejected' must use decision 'reject'"):
        parse_entry(entry.path)


def test_parse_entry_rejects_entry_id_mismatch(tmp_path: Path) -> None:
    entry = create_entry(
        tmp_path,
        title="Wrong Entry Id",
        source_name="external",
        source_ref="source",
        summary="Summary",
        decision="adapt-heavily",
        rationale="Rationale",
        current_date="2026-04-10",
    )
    entry.path.write_text(
        entry.path.read_text(encoding="utf-8").replace("# Evolve Entry EV-001:", "# Evolve Entry EV-999:"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not match entry number"):
        parse_entry(entry.path)
