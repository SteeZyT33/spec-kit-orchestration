"""Stage 1 host-aware auto-symlink: build the symlink list from manifest
host_system + cfg, then create symlinks via the safe atomic-rename helper.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from orca.core.worktrees.config import WorktreesConfig
from orca.core.worktrees.symlinks import safe_symlink

if TYPE_CHECKING:
    from orca.core.worktrees.contract import ContractData

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
    contract: "ContractData | None" = None,
) -> list[Path]:
    """Stage 1 host-aware auto-symlink.

    Symlinks union three sources in order: host_layout defaults, contract
    (team-shared baseline), worktrees.toml (operator-local). dict.fromkeys
    preserves first-insertion order so duplicates land at their host
    position.

    Per docs/superpowers/specs/2026-05-01-orca-worktree-contract-design.md
    §"Conflict resolution".
    """
    from orca.core.worktrees.contract import merge_symlinks

    paths = merge_symlinks(
        host=derive_host_paths(host_system),
        contract=(contract.symlink_paths if contract else None),
        toml=list(cfg.symlink_paths),
    )
    files = merge_symlinks(
        host=[],
        contract=(contract.symlink_files if contract else None),
        toml=list(cfg.symlink_files),
    )

    created: list[Path] = []
    for rel in paths:
        target = primary_root / rel
        if not target.exists():
            continue
        link = worktree_dir / rel
        safe_symlink(target=target, link=link)
        created.append(link)

    for rel in files:
        target = primary_root / rel
        if not target.exists():
            continue
        link = worktree_dir / rel
        safe_symlink(target=target, link=link)
        created.append(link)

    # Manifest-driven additions (constitution_path / agents_md_path
    # additive layer — Phase 1 behavior preserved)
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
