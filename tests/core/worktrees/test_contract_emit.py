import json
import subprocess
from pathlib import Path

import pytest

from orca.core.worktrees.contract_emit import emit_contract, propose_candidates


def _init_git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


class TestProposeCandidates:
    def test_picks_dot_dirs_under_5mb(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".tools").mkdir()
        (repo / ".tools" / "config.json").write_text("{}")
        (repo / ".omx").mkdir()
        (repo / ".omx" / "settings.toml").write_text("")
        proposal = propose_candidates(repo, host_system="bare")
        assert ".tools" in proposal.symlink_paths
        assert ".omx" in proposal.symlink_paths

    def test_skips_excluded_names(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".venv").mkdir()
        (repo / "node_modules").mkdir()
        (repo / "__pycache__").mkdir()
        proposal = propose_candidates(repo, host_system="bare")
        assert ".venv" not in proposal.symlink_paths
        assert "node_modules" not in proposal.symlink_paths
        assert "__pycache__" not in proposal.symlink_paths

    def test_skips_host_layout_overlap(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".specify").mkdir()
        (repo / "specs").mkdir()
        proposal = propose_candidates(repo, host_system="spec-kit")
        # host_layout for spec-kit covers .specify and specs already
        assert ".specify" not in proposal.symlink_paths
        assert "specs" not in proposal.symlink_paths

    def test_skips_nested_host_layout_for_superpowers(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / "docs" / "superpowers").mkdir(parents=True)
        (repo / "docs" / "superpowers" / "spec.md").write_text("")
        (repo / "docs" / "other.md").write_text("")
        proposal = propose_candidates(repo, host_system="superpowers")
        assert "docs" not in proposal.symlink_paths

    def test_skips_nested_host_layout_for_bare(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / "docs" / "orca-specs").mkdir(parents=True)
        proposal = propose_candidates(repo, host_system="bare")
        assert "docs" not in proposal.symlink_paths

    def test_picks_env_files(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".env").write_text("")
        (repo / ".env.local").write_text("")
        proposal = propose_candidates(repo, host_system="bare")
        assert ".env" in proposal.symlink_files
        assert ".env.local" in proposal.symlink_files

    def test_skips_worktree_dirs(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".worktrees").mkdir()
        (repo / ".orca" / "worktrees").mkdir(parents=True)
        proposal = propose_candidates(repo, host_system="bare")
        assert ".worktrees" not in proposal.symlink_paths
        assert ".orca" not in proposal.symlink_paths


class TestEmitContract:
    def test_writes_json_file(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".tools").mkdir()
        (repo / ".tools" / "f.json").write_text("{}")
        path = emit_contract(repo, host_system="bare", force=False)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["schema_version"] == 1
        assert ".tools" in data["symlink_paths"]

    def test_refuses_overwrite_without_force(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1, "symlink_paths": [], "symlink_files": []
        }))
        with pytest.raises(FileExistsError):
            emit_contract(repo, host_system="bare", force=False)

    def test_overwrites_with_force(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".worktree-contract.json").write_text("old content")
        (repo / ".tools").mkdir()
        (repo / ".tools" / "f.json").write_text("{}")
        path = emit_contract(repo, host_system="bare", force=True)
        data = json.loads(path.read_text())
        assert ".tools" in data["symlink_paths"]


class TestSizeCap:
    def test_dot_dir_too_large_skipped(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        big = repo / ".tools"
        big.mkdir()
        # Write a 6 MB blob — exceeds 5 MB cap
        (big / "blob.bin").write_bytes(b"\0" * (6 * 1024 * 1024))
        proposal = propose_candidates(repo, host_system="bare")
        assert ".tools" not in proposal.symlink_paths
