"""Snapshot files into backup_dir before modification.

Snapshot is the foundation of revertibility. Each modified file is
copied byte-for-byte to <backup_dir>/<rel_path> before any edit.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from orca.core.adoption.state import FileEntry


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def snapshot_files(
    paths: list[Path], backup_dir: Path, *, repo_root: Path
) -> list[FileEntry]:
    """Copy each existing path under `backup_dir` (mirroring rel paths).

    Non-existent paths are skipped (returned list is shorter than input).
    Returns FileEntry per snapshotted file with pre_hash populated.
    post_hash is empty string; caller fills it after applying changes.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    entries: list[FileEntry] = []
    for path in paths:
        if not path.exists():
            continue
        rel = path.relative_to(repo_root)
        target = backup_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        entries.append(
            FileEntry(rel_path=str(rel), pre_hash=_hash_file(path), post_hash="")
        )
    return entries


def restore_file(backup_path: Path, target: Path) -> None:
    """Copy `backup_path` -> `target`, preserving mtime."""
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, target)
