"""End-to-end smoke: drive orca-cli wt new + rm against a throwaway repo.

Marked integration; gated behind ORCA_E2E=1 so CI can choose whether to run.
Uses a separate disposable git repo with .orca scaffolding.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(os.environ.get("ORCA_E2E") != "1",
                    reason="set ORCA_E2E=1 to run e2e action smoke")
def test_e2e_new_then_rm(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    (repo / "README.md").write_text("hi\n")
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@example.com",
                    "-c", "user.name=Test", "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@example.com",
                    "-c", "user.name=Test", "commit", "-qm", "chore: init",
                    "--no-verify"],
                   check=True)
    subprocess.run(["orca-cli", "adopt", "--host", "bare"], cwd=str(repo),
                   check=True)
    subprocess.run(["orca-cli", "apply"], cwd=str(repo), check=True)

    # new lane — branch is positional
    out = subprocess.run(
        ["orca-cli", "wt", "new", "smoke-1", "--agent", "none", "--no-tmux"],
        cwd=str(repo), capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr

    # rm lane — branch is positional
    out = subprocess.run(
        ["orca-cli", "wt", "rm", "smoke-1", "--force"],
        cwd=str(repo), capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
