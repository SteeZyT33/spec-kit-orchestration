"""Base path resolution + worktree path layout."""
from __future__ import annotations

from pathlib import Path

from orca.core.worktrees.config import WorktreesConfig


def resolve_base_dir(repo_root: Path, cfg: WorktreesConfig) -> Path:
    """Resolve the base directory that holds worktrees.

    Absolute paths in cfg.base pass through; relative paths are resolved
    against the repo root.
    """
    base = Path(cfg.base)
    if base.is_absolute():
        return base
    return repo_root / base


def resolve_worktree_path(
    repo_root: Path, cfg: WorktreesConfig, *, lane_id: str
) -> Path:
    """Resolve the absolute worktree path for a given lane-id."""
    return resolve_base_dir(repo_root, cfg) / lane_id
