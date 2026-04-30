"""Snapshot + state.json round-trip + integrity checks."""
from __future__ import annotations

from pathlib import Path

from orca.core.adoption.snapshot import snapshot_files, restore_file
from orca.core.adoption.state import (
    AdoptionState,
    FileEntry,
    load_state,
    write_state,
)


def test_snapshot_copies_files(tmp_path: Path) -> None:
    backup_dir = tmp_path / ".orca" / "adoption-backup" / "20260429T120000Z"
    f1 = tmp_path / "CLAUDE.md"
    f1.write_text("hello\n")
    f2 = tmp_path / "constitution.md"
    f2.write_text("# c\n")

    entries = snapshot_files([f1, f2], backup_dir, repo_root=tmp_path)

    assert len(entries) == 2
    assert (backup_dir / "CLAUDE.md").read_text() == "hello\n"
    assert (backup_dir / "constitution.md").read_text() == "# c\n"
    assert entries[0].rel_path == "CLAUDE.md"
    assert entries[0].pre_hash != ""


def test_snapshot_skips_nonexistent(tmp_path: Path) -> None:
    backup_dir = tmp_path / ".orca" / "adoption-backup" / "ts"
    f = tmp_path / "missing.md"
    entries = snapshot_files([f], backup_dir, repo_root=tmp_path)
    assert entries == []


def test_restore_file(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "CLAUDE.md").write_text("original\n")
    target = tmp_path / "CLAUDE.md"
    target.write_text("modified\n")
    restore_file(backup_dir / "CLAUDE.md", target)
    assert target.read_text() == "original\n"


def test_state_round_trip(tmp_path: Path) -> None:
    state = AdoptionState(
        manifest_hash="abc123",
        applied_at="2026-04-29T12:00:00Z",
        backup_timestamp="20260429T120000Z",
        files=[
            FileEntry(rel_path="CLAUDE.md", pre_hash="x", post_hash="y"),
            FileEntry(rel_path="constitution.md", pre_hash="a", post_hash="b"),
        ],
    )
    p = tmp_path / "state.json"
    write_state(state, p)
    loaded = load_state(p)
    assert loaded == state
