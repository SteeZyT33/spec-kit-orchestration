"""Revert executor: restore from backup if state.json hashes match."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from orca.core.adoption.manifest import load_manifest
from orca.core.adoption.snapshot import restore_file
from orca.core.adoption.state import load_state


class RevertError(RuntimeError):
    """Raised when revert cannot proceed safely."""


def revert(*, repo_root: Path, keep_state: bool = False) -> None:
    """Undo a prior apply per state.json.

    For each file in state.json: verify current hash matches post_hash;
    if so, copy backup over. If not, refuse for that file (user has
    hand-edited; revert proceeds for other files; raises after).

    Removes .orca/ at the end unless keep_state=True (then preserves
    adoption-backup/ as audit trail).
    """
    # NOTE: blanket .orca/ removal may delete unrelated state (flow-state
    # caches, etc.). Future tightening: scope removal to adoption.toml,
    # adoption-state.json, and adoption-backup/ only. Tracked as follow-up.
    state_path = repo_root / ".orca" / "adoption-state.json"
    if not state_path.exists():
        raise RevertError(f"adoption-state.json not found at {state_path}")

    state = load_state(state_path)
    manifest = load_manifest(repo_root / ".orca" / "adoption.toml")
    backup_dir = repo_root / manifest.reversal.backup_dir / state.backup_timestamp

    if not backup_dir.exists():
        raise RevertError(f"backup directory missing: {backup_dir}")

    skipped: list[str] = []
    for entry in state.files:
        target = repo_root / entry.rel_path
        if not target.exists():
            # File was deleted post-apply; restore from backup
            restore_file(backup_dir / entry.rel_path, target)
            continue
        actual_hash = _hash_bytes(target.read_bytes())
        if actual_hash != entry.post_hash:
            skipped.append(entry.rel_path)
            continue
        backup_file = backup_dir / entry.rel_path
        if backup_file.exists():
            restore_file(backup_file, target)
        else:
            # File didn't exist pre-apply; remove
            target.unlink()

    if skipped:
        raise RevertError(
            f"hand-edit detected (post-apply hash mismatch); refused for: "
            f"{', '.join(skipped)}. Other files reverted; manual cleanup required."
        )

    if not keep_state:
        shutil.rmtree(repo_root / ".orca")


def _hash_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()
