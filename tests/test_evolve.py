from __future__ import annotations

from pathlib import Path

import pytest

from speckit_orca.evolve import (
    create_entry,
    list_entries,
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
    )

    updated = update_entry(
        entry.path,
        target_kind="existing-spec",
        target_ref="005-orca-flow-state",
        status="mapped",
        mapping_notes="Maps into the flow-state runtime and docs.",
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
    )
    entry.path.write_text(
        entry.path.read_text(encoding="utf-8").replace("**Status**: open", "**Status**: mapped"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires a target mapping"):
        parse_entry(entry.path)


def test_seed_initial_entries_is_idempotent(tmp_path: Path) -> None:
    first = seed_initial_entries(tmp_path)
    second = seed_initial_entries(tmp_path)

    assert len(first) == len(second)
    assert len(list_entries(tmp_path)) == len(first)
    assert (tmp_path / ".specify" / "orca" / "evolve" / "00-overview.md").exists()
