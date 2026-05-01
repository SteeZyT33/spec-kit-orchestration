"""TOCTOU-safe symlink helper using atomic-rename pattern.

Algorithm:
  1. lstat the final path (does NOT follow symlinks)
  2. If it's a real file or directory: refuse with SymlinkConflict
  3. If it's a symlink already pointing at target: no-op
  4. Otherwise: create symlink at <final>.tmp-<pid>-<rand>, then os.replace
     to final path (atomic, immune to concurrent-replace race)

On Windows where developer-mode is unavailable, falls back to mklink /J
(directory junction) for paths; file symlinks emit a warning and skip.
"""
from __future__ import annotations

import logging
import os
import secrets
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class SymlinkConflict(RuntimeError):
    """Raised when a real file or directory blocks the desired symlink path."""


def _link_targets_match(link: Path, target: Path) -> bool:
    try:
        readlink = os.readlink(str(link))
    except OSError:
        return False
    payload_path = Path(readlink)
    resolved_payload = (
        payload_path.resolve()
        if payload_path.is_absolute()
        else (link.parent / payload_path).resolve()
    )
    return resolved_payload == target.resolve()


def _atomic_symlink(target: Path, link: Path) -> None:
    tmp_name = f"{link.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}"
    tmp_path = link.parent / tmp_name
    try:
        os.symlink(str(target), str(tmp_path))
        os.replace(str(tmp_path), str(link))
    except OSError:
        if tmp_path.exists() or tmp_path.is_symlink():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def _windows_junction(target: Path, link: Path) -> None:
    """Windows fallback: mklink /J via cmd; only valid for directories."""
    import subprocess
    if not target.is_dir():
        logger.warning(
            "windows file-symlink unavailable for %s -> %s; skipping",
            link, target,
        )
        return
    tmp_name = f"{link.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}"
    tmp_path = link.parent / tmp_name
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(tmp_path), str(target)],
        check=True, capture_output=True,
    )
    os.replace(str(tmp_path), str(link))


def safe_symlink(*, target: Path, link: Path) -> None:
    """Create or replace a symlink at `link` pointing at `target`.

    Idempotent: existing-and-correct symlinks are no-op. Existing real
    files or directories raise SymlinkConflict (refuse to clobber).
    Atomic via tmp-rename to avoid TOCTOU.
    """
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        if _link_targets_match(link, target):
            return  # idempotent no-op
        # Wrong symlink target: replace via atomic rename
        if sys.platform == "win32":
            _windows_junction(target, link)
        else:
            _atomic_symlink(target, link)
        return
    # Not a symlink — could be a real file/dir, or absent
    if link.exists():
        raise SymlinkConflict(
            f"won't clobber unmanaged content at {link}"
        )
    if sys.platform == "win32":
        _windows_junction(target, link)
    else:
        _atomic_symlink(target, link)
