"""Concurrent-write race coverage for `orca-cli wt new`.

Two writer threads invoke `wt new` against a shared repo; both lanes
must land in the registry under fcntl-protected layout.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        **os.environ,
    }
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "commit",
            "--no-verify",
            "--allow-empty",
            "-m",
            "init",
        ],
        check=True,
        env=env,
    )
    return tmp_path


@pytest.mark.integration
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX fcntl")
def test_two_writers_both_lanes_land(tmp_path: Path) -> None:
    """Two concurrent wt new processes both get their lanes registered."""
    repo = _init_repo(tmp_path)
    errors: list[str] = []

    def run_one(branch: str) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "orca.python_cli",
                "wt",
                "new",
                branch,
                "--no-tmux",
                "--no-setup",
            ],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            errors.append(f"{branch}: {result.stderr}")

    t1 = threading.Thread(target=run_one, args=("feat-a",))
    t2 = threading.Thread(target=run_one, args=("feat-b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert errors == [], errors
    reg_path = repo / ".orca" / "worktrees" / "registry.json"
    reg = json.loads(reg_path.read_text())
    lane_ids = sorted(l["lane_id"] for l in reg["lanes"])
    assert lane_ids == ["feat-a", "feat-b"]
