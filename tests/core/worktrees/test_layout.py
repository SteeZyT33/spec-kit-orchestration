from pathlib import Path

from orca.core.worktrees.config import WorktreesConfig
from orca.core.worktrees.layout import resolve_worktree_path, resolve_base_dir


class TestResolveBaseDir:
    def test_default_relative_to_repo(self, tmp_path):
        cfg = WorktreesConfig()
        assert resolve_base_dir(tmp_path, cfg) == tmp_path / ".orca" / "worktrees"

    def test_absolute_passes_through(self, tmp_path):
        cfg = WorktreesConfig(base="/abs/path/wt")
        assert resolve_base_dir(tmp_path, cfg) == Path("/abs/path/wt")

    def test_relative_resolved_against_repo(self, tmp_path):
        cfg = WorktreesConfig(base=".worktrees")
        assert resolve_base_dir(tmp_path, cfg) == tmp_path / ".worktrees"


class TestResolveWorktreePath:
    def test_combines_base_and_lane_id(self, tmp_path):
        cfg = WorktreesConfig()
        path = resolve_worktree_path(tmp_path, cfg, lane_id="015-wizard")
        assert path == tmp_path / ".orca" / "worktrees" / "015-wizard"

    def test_with_custom_base(self, tmp_path):
        cfg = WorktreesConfig(base=".worktrees")
        path = resolve_worktree_path(tmp_path, cfg, lane_id="feature-foo")
        assert path == tmp_path / ".worktrees" / "feature-foo"

    def test_with_absolute_base(self, tmp_path):
        cfg = WorktreesConfig(base="/scratch")
        path = resolve_worktree_path(tmp_path, cfg, lane_id="x")
        assert path == Path("/scratch") / "x"
