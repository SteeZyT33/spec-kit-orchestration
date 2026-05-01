from pathlib import Path

import pytest

from orca.core.worktrees.config import WorktreesConfig
from orca.core.worktrees.auto_symlink import (
    derive_host_paths, run_stage1,
)


class TestDeriveHostPaths:
    def test_spec_kit_paths(self):
        paths = derive_host_paths("spec-kit")
        assert ".specify" in paths
        assert "specs" in paths

    def test_superpowers_paths(self):
        paths = derive_host_paths("superpowers")
        assert "docs/superpowers" in paths

    def test_openspec_paths(self):
        paths = derive_host_paths("openspec")
        assert "openspec" in paths

    def test_bare_paths(self):
        paths = derive_host_paths("bare")
        assert "docs/orca-specs" in paths


class TestRunStage1:
    def _setup_repo(self, tmp_path: Path, host: str) -> tuple[Path, Path]:
        primary = tmp_path / "primary"
        primary.mkdir()
        (primary / ".env").write_text("FOO=1")
        (primary / ".specify").mkdir()
        (primary / "specs").mkdir()
        wt = tmp_path / "wt"
        wt.mkdir()
        return primary, wt

    def test_creates_host_symlinks(self, tmp_path):
        primary, wt = self._setup_repo(tmp_path, "spec-kit")
        cfg = WorktreesConfig()
        run_stage1(primary_root=primary, worktree_dir=wt,
                   cfg=cfg, host_system="spec-kit")
        assert (wt / ".specify").is_symlink()
        assert (wt / "specs").is_symlink()
        assert (wt / ".env").is_symlink()

    def test_explicit_symlink_paths_union_with_host_defaults(self, tmp_path):
        """Phase 2: explicit cfg.symlink_paths now UNIONS with host_layout
        defaults rather than overriding them. See worktree-contract spec
        §"Conflict resolution"."""
        primary, wt = self._setup_repo(tmp_path, "spec-kit")
        (primary / "custom").mkdir()
        cfg = WorktreesConfig(symlink_paths=["custom"])
        run_stage1(primary_root=primary, worktree_dir=wt,
                   cfg=cfg, host_system="spec-kit")
        # BOTH the explicit "custom" AND the host-derived ".specify"
        # are symlinked under union semantics.
        assert (wt / "custom").is_symlink()
        assert (wt / ".specify").is_symlink()

    def test_contract_symlink_paths_join_union(self, tmp_path):
        """Contract's symlink_paths union with host defaults and cfg."""
        from orca.core.worktrees.contract import ContractData
        primary, wt = self._setup_repo(tmp_path, "spec-kit")
        (primary / "agents").mkdir()
        (primary / "tools").mkdir()
        cfg = WorktreesConfig(symlink_paths=["tools"])
        contract = ContractData(
            schema_version=1,
            symlink_paths=["agents"],
            symlink_files=[],
            init_script=None,
        )
        run_stage1(
            primary_root=primary, worktree_dir=wt, cfg=cfg,
            host_system="spec-kit", contract=contract,
        )
        # Host defaults
        assert (wt / ".specify").is_symlink()
        # Contract's "agents"
        assert (wt / "agents").is_symlink()
        # cfg's "tools"
        assert (wt / "tools").is_symlink()

    def test_skips_files_missing_in_primary(self, tmp_path):
        primary, wt = self._setup_repo(tmp_path, "spec-kit")
        # .env.local does not exist in primary
        cfg = WorktreesConfig()
        run_stage1(primary_root=primary, worktree_dir=wt,
                   cfg=cfg, host_system="spec-kit")
        assert not (wt / ".env.local").exists()

    def test_skips_path_when_existing_tracked_content_in_worktree(
        self, tmp_path, capsys,
    ):
        """When the worktree already contains real (non-symlink) content at
        the host-layout path (e.g. orca self-dogfood: docs/superpowers/ is
        tracked in this very repo), run_stage1 must skip rather than raise.

        Lets the orca dev repo run `wt new` against itself without manifest
        gymnastics. Tracked content stays authoritative (git owns it); the
        host symlink layer only fills absent paths.
        """
        primary, wt = self._setup_repo(tmp_path, "spec-kit")
        # Simulate tracked content materialized in the worktree by `git
        # worktree add` (.specify is a host-layout default for spec-kit).
        (wt / ".specify").mkdir()
        (wt / ".specify" / "tracked.md").write_text("real content")

        cfg = WorktreesConfig()
        result = run_stage1(
            primary_root=primary, worktree_dir=wt,
            cfg=cfg, host_system="spec-kit",
        )

        # No symlink created at .specify (skipped); .env still gets symlinked.
        assert (wt / ".specify").is_dir() and not (wt / ".specify").is_symlink()
        assert (wt / ".specify" / "tracked.md").read_text() == "real content"
        assert (wt / ".env").is_symlink()
        # Skipped link not in the created list.
        assert (wt / ".specify") not in result
        # Stderr warning for visibility.
        captured = capsys.readouterr()
        assert ".specify" in captured.err
        assert "skipped" in captured.err.lower()

    def test_skips_manifest_path_when_existing_tracked_content(
        self, tmp_path, capsys,
    ):
        """Same skip semantics for constitution_path / agents_md_path."""
        primary, wt = self._setup_repo(tmp_path, "bare")
        (primary / "AGENTS.md").write_text("# real")
        # Tracked AGENTS.md materialized by git worktree add.
        (wt / "AGENTS.md").write_text("# tracked content")

        cfg = WorktreesConfig()
        result = run_stage1(
            primary_root=primary, worktree_dir=wt,
            cfg=cfg, host_system="bare",
            agents_md_path="AGENTS.md",
        )

        assert (wt / "AGENTS.md").is_file()
        assert not (wt / "AGENTS.md").is_symlink()
        assert (wt / "AGENTS.md").read_text() == "# tracked content"
        assert (wt / "AGENTS.md") not in result
        captured = capsys.readouterr()
        assert "AGENTS.md" in captured.err
