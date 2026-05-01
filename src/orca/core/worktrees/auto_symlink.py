"""Stage 1 host-aware auto-symlink: build the symlink list from manifest
host_system + cfg, then create symlinks via the safe atomic-rename helper.
"""
from __future__ import annotations

from pathlib import Path

from orca.core.worktrees.config import WorktreesConfig
from orca.core.worktrees.symlinks import safe_symlink

_HOST_DEFAULTS: dict[str, list[str]] = {
    "spec-kit": [".specify", "specs"],
    "superpowers": ["docs/superpowers"],
    "openspec": ["openspec"],
    "bare": ["docs/orca-specs"],
}


def derive_host_paths(host_system: str) -> list[str]:
    """Return the auto-derived symlink paths for a host system."""
    return list(_HOST_DEFAULTS.get(host_system, []))


def run_stage1(
    *,
    primary_root: Path,
    worktree_dir: Path,
    cfg: WorktreesConfig,
    host_system: str,
    constitution_path: str | None = None,
    agents_md_path: str | None = None,
) -> list[Path]:
    """Create auto-symlinks. Returns the list of links created/verified.

    Symlink list precedence:
      - cfg.symlink_paths (if non-empty) overrides host defaults
      - else: host defaults from `derive_host_paths`
      - cfg.symlink_files (env-style files) always layered in addition
      - manifest's host.constitution_path and host.agents_md_path are
        always layered when set (per spec §"Auto-derived symlinks per
        host.system")
    """
    explicit = list(cfg.symlink_paths)
    paths = explicit if explicit else derive_host_paths(host_system)

    created: list[Path] = []
    for rel in paths:
        target = primary_root / rel
        if not target.exists():
            continue
        link = worktree_dir / rel
        safe_symlink(target=target, link=link)
        created.append(link)

    for rel in cfg.symlink_files:
        target = primary_root / rel
        if not target.exists():
            continue
        link = worktree_dir / rel
        safe_symlink(target=target, link=link)
        created.append(link)

    # Manifest-driven additions
    for rel in (constitution_path, agents_md_path):
        if not rel:
            continue
        target = primary_root / rel
        if not target.exists():
            continue
        link = worktree_dir / rel
        safe_symlink(target=target, link=link)
        created.append(link)

    return created
