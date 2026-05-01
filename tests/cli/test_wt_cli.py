"""CLI tests for `orca-cli wt <verb>`."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           **os.environ}
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--no-verify",
         "--allow-empty", "-m", "init"],
        check=True, env=env,
    )
    return tmp_path


@pytest.fixture
def repo(tmp_path):
    return _init_repo(tmp_path)


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "wt", *args,
         "--no-tmux", "--no-setup"],
        cwd=str(repo),
        capture_output=True, text=True, check=False,
    )


class TestWtNew:
    def test_creates_worktree_via_cli(self, repo):
        result = _run(repo, "new", "feature-foo")
        assert result.returncode == 0, result.stderr
        # Worktree path printed on stdout
        path = result.stdout.strip()
        assert Path(path).is_dir()
        assert path.endswith("feature-foo")

    def test_emits_json_envelope_on_failure(self, repo):
        # Bad branch name (path-safety rejects)
        result = _run(repo, "new", "..")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is False
        assert envelope["error"]["kind"] == "input_invalid"

    def test_unknown_subverb_returns_input_invalid(self, repo):
        result = subprocess.run(
            [sys.executable, "-m", "orca.python_cli", "wt", "exterminate"],
            cwd=str(repo), capture_output=True, text=True, check=False,
        )
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["error"]["kind"] == "input_invalid"


class TestWtRm:
    def test_removes_lane(self, repo):
        result = _run(repo, "new", "feat-rm")
        assert result.returncode == 0
        wt_path = Path(result.stdout.strip())

        result = _run(repo, "rm", "feat-rm")
        assert result.returncode == 0, result.stderr
        assert not wt_path.exists()

    def test_no_op_when_lane_missing(self, repo):
        result = _run(repo, "rm", "never-existed")
        assert result.returncode == 0


class TestWtCd:
    def test_no_arg_prints_repo_root(self, repo):
        result = _run(repo, "cd")
        assert result.returncode == 0
        assert Path(result.stdout.strip()).resolve() == repo.resolve()

    def test_branch_arg_prints_worktree_path(self, repo):
        _run(repo, "new", "feat-cd")
        result = _run(repo, "cd", "feat-cd")
        assert result.returncode == 0
        assert result.stdout.strip().endswith("feat-cd")

    def test_lane_id_arg_resolves(self, repo):
        _run(repo, "new", "feature/123-xyz")  # lane-id "feature-123-xyz"
        result = _run(repo, "cd", "feature-123-xyz")
        assert result.returncode == 0
        assert result.stdout.strip().endswith("feature-123-xyz")


class TestWtLs:
    def test_human_table(self, repo):
        _run(repo, "new", "feat-a")
        _run(repo, "new", "feat-b")
        result = _run(repo, "ls")
        assert result.returncode == 0
        assert "feat-a" in result.stdout
        assert "feat-b" in result.stdout

    def test_json_shape(self, repo):
        _run(repo, "new", "feat-x")
        result = _run(repo, "ls", "--json")
        assert result.returncode == 0
        envelope = json.loads(result.stdout)
        assert envelope["schema_version"] == 1
        lanes = envelope["lanes"]
        assert len(lanes) == 1
        # Required keys per spec
        for key in ("lane_id", "branch", "worktree_path", "feature_id",
                    "tmux_state", "agent", "last_attached_at",
                    "setup_version"):
            assert key in lanes[0]


class TestTmuxStateComputation:
    """Pure-function tests for the three documented tmux_state values."""
    def test_session_missing_when_no_live_windows(self):
        from orca.python_cli import _compute_tmux_state
        assert _compute_tmux_state("any-window", set()) == "session-missing"

    def test_attached_when_window_in_live_set(self):
        from orca.python_cli import _compute_tmux_state
        assert _compute_tmux_state("feat-x", {"feat-x", "other"}) == "attached"

    def test_stale_when_session_alive_window_missing(self):
        from orca.python_cli import _compute_tmux_state
        assert _compute_tmux_state("feat-x", {"other"}) == "stale"
