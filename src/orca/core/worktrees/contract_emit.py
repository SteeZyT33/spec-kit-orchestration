"""Discovery scan for `wt contract emit`.

Per docs/superpowers/specs/2026-05-01-orca-worktree-contract-design.md
§"Discovery (orca-cli wt contract emit)".

Heuristic:
1. Always include `.env*` files at repo root.
2. Always include top-level dot-dirs that exist on disk, are <5 MB
   (via os.walk early-bail), and have only text-shaped content (no
   build-artifact name patterns).
3. Always include top-level non-dot-dirs that are tracked in git
   (via `git ls-files <dir>` size budget) and <50 MB and not in
   excluded-name list.
4. Skip anything covered by host_layout.
5. Skip worktree dirs.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from orca.core.worktrees.auto_symlink import derive_host_paths

DEFAULT_DOT_DIR_CAP_MB = 5
DEFAULT_NON_DOT_DIR_CAP_MB = 50

EXCLUDED_NAMES = frozenset({
    "node_modules", "__pycache__", ".venv", "venv", "target",
    "dist", "build", "out", "coverage", ".pytest_cache",
    ".next", ".cache", "tmp", ".tmp",
})

WORKTREE_NAMES = frozenset({".worktrees", "worktrees", ".orca"})


@dataclass(frozen=True)
class ContractProposal:
    schema_version: int
    symlink_paths: list[str]
    symlink_files: list[str]
    init_script: str | None = None


def _dot_dir_size_under_cap(path: Path, cap_bytes: int) -> bool:
    """Walk `path` summing sizes; bail early when cap is exceeded."""
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
            if total > cap_bytes:
                return False
    return True


def _git_tracked_dir_size_under_cap(
    repo_root: Path, rel_dir: str, cap_bytes: int,
) -> bool:
    """Sum tracked-file sizes under rel_dir using `git ls-files`."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "-z", "--", rel_dir],
            capture_output=True, check=False,
        )
    except OSError:
        return False
    if result.returncode != 0:
        return False
    total = 0
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            total += (repo_root / raw.decode("utf-8")).stat().st_size
        except (OSError, UnicodeDecodeError):
            continue
        if total > cap_bytes:
            return False
    return True


def _is_excluded(name: str) -> bool:
    return name in EXCLUDED_NAMES or name in WORKTREE_NAMES


def propose_candidates(
    repo_root: Path,
    *,
    host_system: str,
    dot_dir_cap_mb: int = DEFAULT_DOT_DIR_CAP_MB,
    non_dot_dir_cap_mb: int = DEFAULT_NON_DOT_DIR_CAP_MB,
) -> ContractProposal:
    host_paths = derive_host_paths(host_system)
    # Top-level dir names that contain host_layout content. We must exclude
    # these entirely from contract proposals: proposing the parent dir as
    # a symlink would shadow per-worktree subpaths under it (e.g. proposing
    # `docs` when host_layout owns `docs/superpowers`).
    host_skip_top = {Path(p).parts[0] for p in host_paths if p}
    paths: list[str] = []
    files: list[str] = []

    for entry in sorted(repo_root.iterdir()):
        name = entry.name
        if name in host_skip_top:
            continue
        if _is_excluded(name):
            continue
        if name == ".git" or name.startswith(".git/"):
            continue

        if entry.is_file() and name.startswith(".env"):
            files.append(name)
            continue

        if not entry.is_dir():
            continue

        if name.startswith("."):
            cap_bytes = dot_dir_cap_mb * 1024 * 1024
            if _dot_dir_size_under_cap(entry, cap_bytes):
                paths.append(name)
        else:
            cap_bytes = non_dot_dir_cap_mb * 1024 * 1024
            if _git_tracked_dir_size_under_cap(repo_root, name, cap_bytes):
                paths.append(name)

    return ContractProposal(
        schema_version=1,
        symlink_paths=paths,
        symlink_files=files,
        init_script=None,
    )


def emit_contract(
    repo_root: Path,
    *,
    host_system: str,
    force: bool,
    init_script: str | None = None,
) -> Path:
    """Write `.worktree-contract.json` with discovered candidates.

    Refuses to overwrite an existing file unless `force=True`.
    """
    out = repo_root / ".worktree-contract.json"
    if out.exists() and not force:
        raise FileExistsError(
            f"{out} already exists; pass force=True to overwrite"
        )
    proposal = propose_candidates(repo_root, host_system=host_system)
    payload = {
        "schema_version": proposal.schema_version,
        "symlink_paths": proposal.symlink_paths,
        "symlink_files": proposal.symlink_files,
    }
    if init_script:
        payload["init_script"] = init_script
    elif proposal.init_script:
        payload["init_script"] = proposal.init_script
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return out
