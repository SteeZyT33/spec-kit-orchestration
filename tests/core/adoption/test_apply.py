"""Tests for orca.core.adoption.apply."""
from __future__ import annotations

import subprocess
from pathlib import Path


def test_apply_seeds_worktrees_config(tmp_path: Path) -> None:
    # Set up a minimal adopted repo; v1 always seeds the worktrees config.
    # The "enabled_features" gate is forward-compatible (post-Phase 2 schema bump);
    # for v1 the seed is unconditional.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)

    from orca.core.adoption.apply import apply
    from orca.core.adoption.manifest import write_manifest
    from orca.core.adoption.wizard import build_default_manifest

    manifest = build_default_manifest(tmp_path, host_override="bare")
    (tmp_path / ".orca").mkdir(parents=True, exist_ok=True)
    write_manifest(manifest, tmp_path / ".orca" / "adoption.toml")

    apply(repo_root=tmp_path)
    # worktrees.toml should exist after apply
    assert (tmp_path / ".orca" / "worktrees.toml").exists()
