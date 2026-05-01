import pytest
from pathlib import Path
import textwrap

from orca.core.worktrees.config import (
    WorktreesConfig,
    load_config,
    write_default_config,
    ConfigError,
)


def _make_repo(tmp_path: Path, committed: str = "", local: str = "") -> Path:
    (tmp_path / ".orca").mkdir()
    if committed:
        (tmp_path / ".orca" / "worktrees.toml").write_text(committed)
    if local:
        (tmp_path / ".orca" / "worktrees.local.toml").write_text(local)
    return tmp_path


class TestLoadConfig:
    def test_missing_files_returns_defaults(self, tmp_path):
        repo = _make_repo(tmp_path)
        cfg = load_config(repo)
        assert cfg.base == ".orca/worktrees"
        assert cfg.lane_id_mode == "auto"
        assert cfg.tmux_session == "orca"
        assert cfg.default_agent == "claude"

    def test_committed_overrides_defaults(self, tmp_path):
        committed = textwrap.dedent("""
            [worktrees]
            schema_version = 1
            base = ".worktrees"
            lane_id_mode = "branch"
        """)
        repo = _make_repo(tmp_path, committed=committed)
        cfg = load_config(repo)
        assert cfg.base == ".worktrees"
        assert cfg.lane_id_mode == "branch"

    def test_local_overrides_committed(self, tmp_path):
        committed = '[worktrees]\nschema_version = 1\nbase = ".worktrees"\n'
        local = '[worktrees]\nbase = "/tmp/wt"\n'
        repo = _make_repo(tmp_path, committed=committed, local=local)
        cfg = load_config(repo)
        assert cfg.base == "/tmp/wt"

    def test_invalid_schema_version_raises(self, tmp_path):
        committed = '[worktrees]\nschema_version = 99\n'
        repo = _make_repo(tmp_path, committed=committed)
        with pytest.raises(ConfigError, match="schema_version"):
            load_config(repo)

    def test_scalar_where_list_expected_raises(self, tmp_path):
        committed = '[worktrees]\nschema_version = 1\nsymlink_paths = "specs"\n'
        repo = _make_repo(tmp_path, committed=committed)
        with pytest.raises(ConfigError, match="symlink_paths"):
            load_config(repo)

    def test_explicit_empty_symlink_files_respected(self, tmp_path):
        """`symlink_files = []` in TOML must produce [], not the defaults."""
        committed = textwrap.dedent("""
            [worktrees]
            schema_version = 1
            symlink_files = []
        """)
        repo = _make_repo(tmp_path, committed=committed)
        cfg = load_config(repo)
        assert cfg.symlink_files == []

    def test_omitted_symlink_files_uses_defaults(self, tmp_path):
        """If the operator omits the key entirely, defaults still apply."""
        committed = '[worktrees]\nschema_version = 1\n'
        repo = _make_repo(tmp_path, committed=committed)
        cfg = load_config(repo)
        assert cfg.symlink_files == [".env", ".env.local", ".env.secrets"]

    def test_agent_command_template_loaded(self, tmp_path):
        committed = textwrap.dedent("""
            [worktrees]
            schema_version = 1
            [worktrees.agents]
            claude = "claude --custom-flag"
            codex = "codex --yolo"
        """)
        repo = _make_repo(tmp_path, committed=committed)
        cfg = load_config(repo)
        assert cfg.agents["claude"] == "claude --custom-flag"
        assert cfg.agents["codex"] == "codex --yolo"


class TestWriteDefaultConfig:
    def test_writes_committed_only_when_missing(self, tmp_path):
        repo = _make_repo(tmp_path)
        write_default_config(repo)
        assert (repo / ".orca" / "worktrees.toml").exists()
        # local is gitignored; not auto-written
        assert not (repo / ".orca" / "worktrees.local.toml").exists()

    def test_idempotent_does_not_overwrite_existing(self, tmp_path):
        committed = '[worktrees]\nschema_version = 1\nbase = "/custom"\n'
        repo = _make_repo(tmp_path, committed=committed)
        write_default_config(repo)
        # Existing committed file preserved
        assert "/custom" in (repo / ".orca" / "worktrees.toml").read_text()
