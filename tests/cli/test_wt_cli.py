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


def _run_with_setup(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Like _run but does NOT pass --no-setup; for tests that exercise hooks."""
    return subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "wt", *args, "--no-tmux"],
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


class TestWtStartConfigVersion:
    def test_start_refuses_when_no_lane(self, repo):
        result = _run(repo, "start", "missing")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["error"]["kind"] == "input_invalid"

    def test_start_runs_before_run_hook(self, repo):
        _run(repo, "new", "feat-s")
        out = repo / "ran.txt"
        ldir = repo / ".orca" / "worktrees"
        br = ldir / "before_run"
        br.write_text(f'#!/usr/bin/env bash\necho "x" > "{out}"\n')
        br.chmod(0o755)
        result = _run(repo, "start", "feat-s", "--trust-hooks")
        assert result.returncode == 0
        assert out.read_text().strip() == "x"

    def test_rerun_setup_executes_when_after_create_changes(self, repo):
        # Create with an initial after_create hook; lane records its SHA.
        ldir = repo / ".orca" / "worktrees"
        ldir.mkdir(parents=True, exist_ok=True)
        ac = ldir / "after_create"
        ac.write_text('#!/usr/bin/env bash\nexit 0\n')
        ac.chmod(0o755)

        # Run wt new WITH setup so the sidecar records the SHA
        result = _run_with_setup(repo, "new", "feat-rr", "--trust-hooks")
        assert result.returncode == 0

        # Mutate the script content; SHA changes.
        out = repo / "rerun_ran.txt"
        ac.write_text(f'#!/usr/bin/env bash\necho "rerun" > "{out}"\nexit 0\n')

        # Without --rerun-setup, Stage 2 is NOT re-executed
        result = _run(repo, "start", "feat-rr", "--trust-hooks")
        assert result.returncode == 0
        assert not out.exists()

        # With --rerun-setup AND SHA changed, Stage 2 runs again
        result = _run(repo, "start", "feat-rr", "--rerun-setup", "--trust-hooks")
        assert result.returncode == 0, result.stderr
        assert out.read_text().strip() == "rerun"

    def test_rerun_setup_noop_when_sha_unchanged(self, repo):
        ldir = repo / ".orca" / "worktrees"
        ldir.mkdir(parents=True, exist_ok=True)
        ac = ldir / "after_create"
        out = repo / "ran_count.txt"
        ac.write_text(
            '#!/usr/bin/env bash\n'
            f'COUNT=$(cat "{out}" 2>/dev/null || echo 0); '
            f'echo $((COUNT + 1)) > "{out}"\n'
        )
        ac.chmod(0o755)

        _run_with_setup(repo, "new", "feat-noop", "--trust-hooks")
        assert out.read_text().strip() == "1"

        # SHA unchanged → --rerun-setup is a no-op for Stage 2
        _run(repo, "start", "feat-noop", "--rerun-setup", "--trust-hooks")
        assert out.read_text().strip() == "1"  # still 1, not 2

    def test_config_json_shape(self, repo):
        result = _run(repo, "config", "--json")
        assert result.returncode == 0
        envelope = json.loads(result.stdout)
        assert envelope["schema_version"] == 1
        assert "effective" in envelope
        assert "sources" in envelope

    def test_version(self, repo):
        result = _run(repo, "version")
        assert result.returncode == 0
        # Format: "<orca version> wt-schema=<version>"
        assert "wt-schema=" in result.stdout


class TestWtInitMerge:
    def test_init_writes_after_create(self, repo):
        (repo / "pyproject.toml").write_text("[project]\nname='x'\n")
        (repo / "uv.lock").write_text("")
        result = _run(repo, "init")
        assert result.returncode == 0, result.stderr
        ac = repo / ".orca" / "worktrees" / "after_create"
        assert ac.exists()
        assert "uv sync" in ac.read_text()

    def test_init_refuses_overwrite_without_replace(self, repo):
        ldir = repo / ".orca" / "worktrees"
        ldir.mkdir(parents=True)
        (ldir / "after_create").write_text("# existing\n")
        result = _run(repo, "init")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert "exists" in envelope["error"]["message"].lower()

    def test_merge_invokes_git_merge(self, repo):
        # Create + commit on a feature branch
        _run(repo, "new", "feat-merge")
        wt_path = repo / ".orca" / "worktrees" / "feat-merge"
        (wt_path / "f.txt").write_text("x")
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
               **os.environ}
        subprocess.run(["git", "-C", str(wt_path), "add", "f.txt"], check=True, env=env)
        subprocess.run(["git", "-C", str(wt_path), "commit", "--no-verify",
                        "-m", "x"], check=True, env=env)

        result = _run(repo, "merge", "feat-merge")
        assert result.returncode == 0, result.stderr
        # File now in primary main
        assert (repo / "f.txt").exists()
