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
