from __future__ import annotations

from pathlib import Path

import pytest

from speckit_orca.adoption import (
    AdoptionError,
    AdoptionParseError,
    create_record,
    get_record,
    list_records,
    parse_record,
    regenerate_overview,
    retire_record,
    supersede_record,
)


def _make_record(
    tmp_path: Path,
    *,
    title: str = "CLI entrypoint",
    summary: str = "Arg routing and dispatch.",
    location: list[str] | None = None,
    key_behaviors: list[str] | None = None,
    known_gaps: str | None = None,
    baseline_commit: str | None = None,
    adopted_on: str | None = None,
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
        known_gaps=known_gaps,
        baseline_commit=baseline_commit,
        adopted_on=adopted_on,
    )


def _make_full_spec(tmp_path: Path, spec_id: str) -> Path:
    """Create a minimal full spec so `supersede_record` validation passes."""
    feature_dir = tmp_path / "specs" / spec_id
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Feature Specification: Test\n")
    return feature_dir


def test_create_assigns_sequential_id_and_writes_file(tmp_path: Path) -> None:
    first = _make_record(tmp_path, title="First feature")
    second = _make_record(tmp_path, title="Second feature")

    assert first.record_id == "AR-001"
    assert second.record_id == "AR-002"
    assert first.path.name == "AR-001-first-feature.md"
    assert second.status == "adopted"
    assert first.path.read_text().startswith(
        "# Adoption Record: AR-001: First feature"
    )


def test_create_rejects_empty_required_fields(tmp_path: Path) -> None:
    with pytest.raises(AdoptionError):
        create_record(
            repo_root=tmp_path, title="Empty summary",
            summary="   ",
            location=["foo.py"], key_behaviors=["b"],
        )
    with pytest.raises(AdoptionError):
        create_record(
            repo_root=tmp_path, title="Empty location",
            summary="s", location=[" ", ""],
            key_behaviors=["b"],
        )
    with pytest.raises(AdoptionError):
        create_record(
            repo_root=tmp_path, title="Empty behaviors",
            summary="s", location=["foo.py"],
            key_behaviors=["  "],
        )


def test_create_rejects_invalid_adopted_on(tmp_path: Path) -> None:
    with pytest.raises(AdoptionError):
        _make_record(tmp_path, title="Non-dash date", adopted_on="20260415")
    with pytest.raises(AdoptionError):
        _make_record(tmp_path, title="Bad calendar", adopted_on="2026-02-30")


def test_create_omits_baseline_commit_when_none(tmp_path: Path) -> None:
    record = _make_record(
        tmp_path, title="No baseline", baseline_commit=None
    )
    assert record.baseline_commit is None
    text = record.path.read_text()
    assert "**Baseline Commit**" not in text


def test_create_persists_explicit_baseline_commit(tmp_path: Path) -> None:
    record = _make_record(
        tmp_path, title="Pinned baseline", baseline_commit="abc1234"
    )
    assert record.baseline_commit == "abc1234"
    assert "**Baseline Commit**: abc1234" in record.path.read_text()


def test_baseline_sentinel_falls_back_gracefully_without_git(
    tmp_path: Path,
) -> None:
    """`baseline_commit` sentinel triggers `git rev-parse`; if the
    workspace isn't a git repo, the field is omitted without crashing.
    """
    # tmp_path is NOT a git repo — the sentinel should gracefully
    # return None and the record writes without Baseline Commit.
    record = _make_record(
        tmp_path, title="No git here", baseline_commit="__HEAD__"
    )
    assert record.baseline_commit is None


def test_round_trip_parse_matches_create(tmp_path: Path) -> None:
    created = _make_record(
        tmp_path,
        title="Round trip",
        summary="A short description.",
        location=["a.py", "b.py"],
        key_behaviors=["first", "second"],
        known_gaps="Not yet migrated to new auth.",
    )
    parsed = parse_record(created.path)
    assert parsed.record_id == created.record_id
    assert parsed.title == created.title
    assert parsed.summary == created.summary
    assert parsed.location == ["a.py", "b.py"]
    assert parsed.key_behaviors == ["first", "second"]
    assert parsed.known_gaps == "Not yet migrated to new auth."
    assert parsed.superseded_by is None
    assert parsed.retirement_reason is None


def test_supersede_validates_target_spec_exists(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="To be replaced")
    with pytest.raises(AdoptionError) as exc_info:
        supersede_record(
            repo_root=tmp_path,
            record_id=record.record_id,
            superseded_by="020-missing",
        )
    assert "does not exist" in str(exc_info.value)


def test_supersede_writes_section_and_updates_status(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="Will be superseded")
    _make_full_spec(tmp_path, "020-new-auth")
    updated = supersede_record(
        repo_root=tmp_path,
        record_id=record.record_id,
        superseded_by="020-new-auth",
    )
    assert updated.status == "superseded"
    assert updated.superseded_by == "020-new-auth"
    reparsed = parse_record(record.path)
    assert reparsed.status == "superseded"
    assert reparsed.superseded_by == "020-new-auth"


def test_retire_with_reason_writes_section(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="To retire with reason")
    updated = retire_record(
        repo_root=tmp_path,
        record_id=record.record_id,
        reason="Feature removed in v3.0",
    )
    assert updated.status == "retired"
    assert updated.retirement_reason == "Feature removed in v3.0"
    assert "## Retirement Reason" in record.path.read_text()


def test_retire_without_reason_omits_section(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="To retire without reason")
    updated = retire_record(repo_root=tmp_path, record_id=record.record_id)
    assert updated.status == "retired"
    assert updated.retirement_reason is None
    # Section header must not appear — presence of Status: retired
    # is enough per plan open question 5.
    assert "## Retirement Reason" not in record.path.read_text()


def test_retire_with_whitespace_reason_omits_section(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="Whitespace reason")
    updated = retire_record(
        repo_root=tmp_path, record_id=record.record_id, reason="   \n  "
    )
    assert updated.retirement_reason is None
    assert "## Retirement Reason" not in record.path.read_text()


def test_list_filters_by_status(tmp_path: Path) -> None:
    a = _make_record(tmp_path, title="Still adopted")
    b = _make_record(tmp_path, title="Will retire")
    retire_record(repo_root=tmp_path, record_id=b.record_id)

    adopted = list_records(repo_root=tmp_path, status="adopted")
    retired = list_records(repo_root=tmp_path, status="retired")
    all_records = list_records(repo_root=tmp_path)

    assert [r.record_id for r in adopted] == [a.record_id]
    assert [r.record_id for r in retired] == [b.record_id]
    assert {r.record_id for r in all_records} == {a.record_id, b.record_id}


def test_list_rejects_invalid_status_filter(tmp_path: Path) -> None:
    with pytest.raises(AdoptionError):
        list_records(repo_root=tmp_path, status="bogus")


def test_get_record_resolves_id_without_slug(tmp_path: Path) -> None:
    record = _make_record(tmp_path, title="Lookup target")
    by_stem = get_record(repo_root=tmp_path, record_id=record.record_id)
    full_id = f"{record.record_id}-{record.slug}"
    by_full = get_record(repo_root=tmp_path, record_id=full_id)
    assert by_stem.title == record.title
    assert by_full.title == record.title


def test_get_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(AdoptionError):
        get_record(repo_root=tmp_path, record_id="AR-999")


def test_regenerate_overview_groups_records_by_status(
    tmp_path: Path,
) -> None:
    _make_full_spec(tmp_path, "020-replacement")
    a = _make_record(tmp_path, title="Stays adopted")
    b = _make_record(tmp_path, title="Gets superseded")
    c = _make_record(tmp_path, title="Gets retired")
    supersede_record(
        repo_root=tmp_path, record_id=b.record_id,
        superseded_by="020-replacement",
    )
    retire_record(repo_root=tmp_path, record_id=c.record_id)

    overview = regenerate_overview(tmp_path)
    text = overview.read_text()
    assert "# Adoption Records Overview" in text
    adopted_section, rest = text.split("## Superseded", 1)
    superseded_section, retired_section = rest.split("## Retired", 1)
    assert a.record_id in adopted_section
    assert b.record_id in superseded_section
    assert "020-replacement" in superseded_section
    assert c.record_id in retired_section


def test_regenerate_overview_on_empty_registry(tmp_path: Path) -> None:
    overview = regenerate_overview(tmp_path)
    text = overview.read_text()
    assert "_No adopted records._" in text
    assert "_No superseded records._" in text
    assert "_No retired records._" in text


def test_parse_rejects_missing_title_header(tmp_path: Path) -> None:
    directory = tmp_path / ".specify/orca/adopted"
    directory.mkdir(parents=True)
    bad = directory / "AR-001-broken.md"
    bad.write_text("# Not an adoption record header\n\n")
    with pytest.raises(AdoptionParseError):
        parse_record(bad)


def test_parse_rejects_missing_required_section(tmp_path: Path) -> None:
    directory = tmp_path / ".specify/orca/adopted"
    directory.mkdir(parents=True)
    bad = directory / "AR-001-no-location.md"
    bad.write_text(
        "# Adoption Record: AR-001: Missing Location\n\n"
        "**Status**: adopted\n"
        "**Adopted-on**: 2026-04-15\n\n"
        "## Summary\ntext\n\n"
        "## Key Behaviors\n- b\n"
    )
    with pytest.raises(AdoptionParseError):
        parse_record(bad)


def test_parse_rejects_duplicate_section(tmp_path: Path) -> None:
    directory = tmp_path / ".specify/orca/adopted"
    directory.mkdir(parents=True)
    bad = directory / "AR-001-dup.md"
    bad.write_text(
        "# Adoption Record: AR-001: Dup\n\n"
        "**Status**: adopted\n"
        "**Adopted-on**: 2026-04-15\n\n"
        "## Summary\nfirst\n\n"
        "## Summary\nsecond\n\n"
        "## Location\n- foo.py\n\n"
        "## Key Behaviors\n- b\n"
    )
    with pytest.raises(AdoptionParseError):
        parse_record(bad)


def test_parse_rejects_out_of_order_recognized_sections(tmp_path: Path) -> None:
    directory = tmp_path / ".specify/orca/adopted"
    directory.mkdir(parents=True)
    bad = directory / "AR-001-order.md"
    # Location before Summary violates recognized-section order.
    bad.write_text(
        "# Adoption Record: AR-001: Order\n\n"
        "**Status**: adopted\n"
        "**Adopted-on**: 2026-04-15\n\n"
        "## Location\n- foo.py\n\n"
        "## Summary\ntext\n\n"
        "## Key Behaviors\n- b\n"
    )
    with pytest.raises(AdoptionParseError):
        parse_record(bad)


def test_parse_tolerates_unknown_sections(tmp_path: Path) -> None:
    """Unknown headings land in the `extra` bucket per the tolerant-parser posture."""
    directory = tmp_path / ".specify/orca/adopted"
    directory.mkdir(parents=True)
    good = directory / "AR-001-with-extras.md"
    good.write_text(
        "# Adoption Record: AR-001: With extras\n\n"
        "**Status**: adopted\n"
        "**Adopted-on**: 2026-04-15\n\n"
        "## Summary\ns\n\n"
        "## Location\n- foo.py\n\n"
        "## Key Behaviors\n- b\n\n"
        "## Author Notes\nThis is operator-authored and unknown to the parser.\n\n"
        "## Unrelated\nAlso extra.\n"
    )
    record = parse_record(good)
    assert record.record_id == "AR-001"
    assert "Author Notes" in record.extra
    assert "operator-authored" in record.extra["Author Notes"]
    assert "Unrelated" in record.extra


def test_parse_tolerates_status_section_mismatch(tmp_path: Path) -> None:
    """A hand-edited AR with Status: adopted plus a Superseded By section still parses."""
    directory = tmp_path / ".specify/orca/adopted"
    directory.mkdir(parents=True)
    mismatched = directory / "AR-001-weird.md"
    mismatched.write_text(
        "# Adoption Record: AR-001: Weird mix\n\n"
        "**Status**: adopted\n"
        "**Adopted-on**: 2026-04-15\n\n"
        "## Summary\ns\n\n"
        "## Location\n- foo.py\n\n"
        "## Key Behaviors\n- b\n\n"
        "## Superseded By\n020-something-else\n"
    )
    record = parse_record(mismatched)
    assert record.status == "adopted"
    assert record.superseded_by == "020-something-else"


def test_parse_rejects_empty_optional_section(tmp_path: Path) -> None:
    """An optional section present with empty body is invalid."""
    directory = tmp_path / ".specify/orca/adopted"
    directory.mkdir(parents=True)
    bad = directory / "AR-001-empty-opt.md"
    bad.write_text(
        "# Adoption Record: AR-001: Empty opt\n\n"
        "**Status**: adopted\n"
        "**Adopted-on**: 2026-04-15\n\n"
        "## Summary\ns\n\n"
        "## Location\n- foo.py\n\n"
        "## Key Behaviors\n- b\n\n"
        "## Known Gaps\n\n"
    )
    with pytest.raises(AdoptionParseError):
        parse_record(bad)


def test_parse_wraps_unreadable_file_in_adoption_error(tmp_path: Path) -> None:
    """Non-UTF-8 files raise AdoptionError (not bare OSError/UnicodeDecodeError)."""
    directory = tmp_path / ".specify/orca/adopted"
    directory.mkdir(parents=True)
    bad = directory / "AR-001-binary.md"
    bad.write_bytes(b"\xff\xfe\x00binary garbage\x80\x81")
    with pytest.raises(AdoptionError):
        parse_record(bad)


def test_list_skips_unreadable_and_malformed_records(tmp_path: Path) -> None:
    good = _make_record(tmp_path, title="Good record")
    directory = good.path.parent
    (directory / "AR-099-broken.md").write_text("garbage\n")
    (directory / "AR-098-binary.md").write_bytes(b"\xff\xfe\x00")
    records = list_records(repo_root=tmp_path)
    # Bad files silently skipped; only good record listed.
    assert [r.record_id for r in records] == [good.record_id]


def test_create_record_is_atomic_under_concurrent_calls(tmp_path: Path) -> None:
    """Concurrent create_record calls must not allocate the same AR-NNN."""
    import threading

    results: list[str] = []
    errors: list[Exception] = []

    def _create(n: int) -> None:
        try:
            record = create_record(
                repo_root=tmp_path,
                title=f"Concurrent {n}",
                summary="s",
                location=[f"src/foo{n}.py"],
                key_behaviors=["b"],
                baseline_commit=None,
            )
            results.append(record.record_id)
        except Exception as exc:  # noqa: BLE001 - collect worker failures for main-thread assertion
            errors.append(exc)

    threads = [threading.Thread(target=_create, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent create raised: {errors}"
    assert len(set(results)) == 10, f"Duplicate ids allocated: {results}"


def test_id_allocation_skips_gaps(tmp_path: Path) -> None:
    _make_record(tmp_path, title="First")
    second = _make_record(tmp_path, title="Second")
    # Delete AR-001; next create should pick AR-003, not backfill.
    (tmp_path / ".specify/orca/adopted" / "AR-001-first.md").unlink()
    third = _make_record(tmp_path, title="Third")
    assert second.record_id == "AR-002"
    assert third.record_id == "AR-003"
