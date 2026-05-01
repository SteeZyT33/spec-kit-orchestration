"""Dogfood: orca uses its own wt manager against a temp clone of itself.

Exercises the full lane lifecycle (new -> ls -> cd -> doctor -> rm)
against a freshly initialized git repo. Gated by the `integration`
marker so it doesn't run in the default unit-test pass.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


def _make_repo_with_history(tmp_path: Path) -> Path:
    """Set up a repo with a couple of commits to exercise wt new + wt rm."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        **os.environ,
    }
    (tmp_path / "README.md").write_text("# Test\n")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "."], check=True, env=env
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "commit",
            "--no-verify",
            "-m",
            "init",
        ],
        check=True,
        env=env,
    )
    return tmp_path


def _run_wt(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "orca.python_cli",
            "wt",
            *args,
            "--no-tmux",
            "--no-setup",
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.integration
def test_full_lifecycle(tmp_path: Path) -> None:
    repo = _make_repo_with_history(tmp_path)

    # 1. wt new
    r = _run_wt(repo, "new", "demo")
    assert r.returncode == 0, r.stderr
    wt = Path(r.stdout.strip())
    assert wt.is_dir()

    # 2. wt ls includes the lane
    r = _run_wt(repo, "ls", "--json")
    assert r.returncode == 0, r.stderr
    rows = json.loads(r.stdout)["lanes"]
    assert any(l["lane_id"] == "demo" for l in rows)

    # 3. wt cd resolves to the worktree
    r = _run_wt(repo, "cd", "demo")
    assert r.returncode == 0, r.stderr
    assert Path(r.stdout.strip()) == wt

    # 4. wt doctor reports clean
    r = _run_wt(repo, "doctor")
    assert r.returncode == 0, r.stderr

    # 5. wt rm cleans up
    r = _run_wt(repo, "rm", "demo")
    assert r.returncode == 0, r.stderr
    assert not wt.exists()
