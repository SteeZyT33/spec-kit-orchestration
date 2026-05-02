"""Per-feature worktree status helper for the kanban cards.

Reads from `git worktree list --porcelain`. Pure read; mutating
actions live in `actions.py`.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorktreeInfo:
    branch: str = ""
    path: str = ""
    status: str = "(no worktree)"


def _list_worktrees(repo_root: Path) -> list[tuple[str, str]]:
    """Return [(branch, path)] for every worktree, including main."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2.0,
        )
    except Exception:  # noqa: BLE001
        return []
    rows: list[tuple[str, str]] = []
    cur_path = ""
    for line in completed.stdout.splitlines():
        if line.startswith("worktree "):
            cur_path = line[len("worktree "):].strip()
        elif line.startswith("branch "):
            ref = line[len("branch "):].strip()
            short = ref.split("/")[-1] if ref.startswith("refs/heads/") else ref
            rows.append((short, cur_path))
    return rows


def _dirty_count(worktree_path: Path) -> int:
    try:
        completed = subprocess.run(
            ["git", "-C", str(worktree_path), "status", "--porcelain"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2.0,
        )
    except Exception:  # noqa: BLE001
        return 0
    return sum(1 for line in completed.stdout.splitlines() if line.strip())


def worktree_status(repo_root: Path, feature_id: str) -> WorktreeInfo:
    """Find the worktree for a feature and report its dirty/clean status.

    Matching: branch name == feature_id or starts with feature_id + '-'.
    """
    candidates = _list_worktrees(repo_root)
    for branch, path in candidates:
        if branch == feature_id or branch.startswith(f"{feature_id}-"):
            n = _dirty_count(Path(path))
            status = "clean" if n == 0 else f"dirty ({n} files)"
            return WorktreeInfo(branch=branch, path=path, status=status)
    return WorktreeInfo()
