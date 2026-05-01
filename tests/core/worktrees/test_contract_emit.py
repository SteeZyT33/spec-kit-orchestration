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

    def test_skips_tracked_non_dot_dirs(self, tmp_path):
        """Tracked non-dot-dirs (src, tests, specs etc.) MUST NOT be proposed.
        Symlinking branch-specific tracked code defeats the entire point of
        git worktrees. See dogfood report 2026-05-01.
        """
        repo = _init_git_repo(tmp_path)
        (repo / "src").mkdir()
        (repo / "src" / "main.py").write_text("print(1)\n")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_x.py").write_text("def test_x(): pass\n")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.email=t@e", "-c", "user.name=t",
             "-c", "core.hooksPath=", "commit", "-q", "-m", "init"], check=True,
        )
        proposal = propose_candidates(repo, host_system="bare")
        assert "src" not in proposal.symlink_paths
        assert "tests" not in proposal.symlink_paths

    def test_picks_untracked_non_dot_dirs(self, tmp_path):
        """Untracked non-dot-dirs (local-cache, output, etc.) are valid
        candidates — shared state that lives outside git but should be
        consistent across worktrees.
        """
        repo = _init_git_repo(tmp_path)
        (repo / "local-cache").mkdir()
        (repo / "local-cache" / "data.bin").write_bytes(b"x" * 1024)
        proposal = propose_candidates(repo, host_system="bare")
        assert "local-cache" in proposal.symlink_paths

    def test_skips_tracked_dot_dirs(self, tmp_path):
        """Tracked dot-dirs (`.github/`, `.specify/`, etc.) MUST NOT be
        proposed for the same reason tracked non-dot-dirs are skipped:
        git owns them per-branch, symlinking would shadow the checkout.
        """
        repo = _init_git_repo(tmp_path)
        (repo / ".github" / "workflows").mkdir(parents=True)
        (repo / ".github" / "workflows" / "ci.yml").write_text("on: push\n")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.email=t@e", "-c", "user.name=t",
             "-c", "core.hooksPath=", "commit", "-q", "-m", "init"], check=True,
        )
        proposal = propose_candidates(repo, host_system="bare")
        assert ".github" not in proposal.symlink_paths

    def test_skips_tracked_env_files(self, tmp_path):
        """A tracked `.env.example` (committed convention) is git's job; do
        not propose as a symlink_files candidate.
        """
        repo = _init_git_repo(tmp_path)
        (repo / ".env.example").write_text("FOO=bar\n")
        subprocess.run(["git", "-C", str(repo), "add", ".env.example"],
                       check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.email=t@e", "-c", "user.name=t",
             "-c", "core.hooksPath=", "commit", "-q", "-m", "init"], check=True,
        )
        # And an untracked .env alongside.
        (repo / ".env").write_text("SECRET=1\n")
        proposal = propose_candidates(repo, host_system="bare")
        assert ".env.example" not in proposal.symlink_files
        assert ".env" in proposal.symlink_files

    def test_skips_partially_tracked_non_dot_dir(self, tmp_path):
        """If ANY file under a non-dot-dir is tracked, the dir is not a
        symlink candidate — git owns part of it, so symlinking would shadow
        per-branch differences.
        """
        repo = _init_git_repo(tmp_path)
        (repo / "mixed").mkdir()
        (repo / "mixed" / "tracked.md").write_text("tracked")
        subprocess.run(["git", "-C", str(repo), "add", "mixed/tracked.md"],
                       check=True)
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.email=t@e", "-c", "user.name=t",
             "-c", "core.hooksPath=", "commit", "-q", "-m", "init"], check=True,
        )
        # Add an untracked file too — still partially tracked.
        (repo / "mixed" / "untracked.bin").write_bytes(b"u" * 100)
        proposal = propose_candidates(repo, host_system="bare")
        assert "mixed" not in proposal.symlink_paths


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
