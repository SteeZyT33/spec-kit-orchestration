# tests/integration/test_wt_contract_dogfood.py
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           **os.environ}
    (tmp_path / "README.md").write_text("init")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, env=env)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "--no-verify",
                    "-m", "init"], check=True, env=env)
    return tmp_path


def _run_wt(repo: Path, *args: str):
    # Note: deliberately omit --no-setup so Stage 1 (symlink creation) runs.
    # --no-setup short-circuits the entire setup pipeline including Stage 1
    # in WorktreeManager, which would defeat these tests.
    return subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "wt", *args,
         "--no-tmux"],
        cwd=str(repo), capture_output=True, text=True, check=False,
    )


def test_emit_then_new_applies_contract_symlinks(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / ".tools").mkdir()
    (repo / ".tools" / "f.json").write_text("{}")

    # 1. Emit contract
    r = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "wt", "contract", "emit"],
        cwd=str(repo), capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr
    contract = json.loads((repo / ".worktree-contract.json").read_text())
    assert ".tools" in contract["symlink_paths"]

    # 2. wt new — contract symlinks should be applied
    r = _run_wt(repo, "new", "feat-c")
    assert r.returncode == 0, r.stderr
    wt = Path(r.stdout.strip())
    assert (wt / ".tools").is_symlink()


def test_contract_and_worktrees_toml_union(tmp_path):
    """Both contract and worktrees.toml symlink_paths land in worktree."""
    repo = _init_repo(tmp_path)
    (repo / ".tools").mkdir()
    (repo / ".tools" / "f.json").write_text("{}")
    (repo / "agents").mkdir()
    (repo / "agents" / "g.md").write_text("")
    (repo / "shared").mkdir()
    (repo / "shared" / "x").write_text("")

    # Contract lists ".tools" and "agents"
    (repo / ".worktree-contract.json").write_text(json.dumps({
        "schema_version": 1,
        "symlink_paths": [".tools", "agents"],
        "symlink_files": [],
    }))
    # Operator-local worktrees.toml lists "shared"
    (repo / ".orca").mkdir()
    (repo / ".orca" / "worktrees.toml").write_text(
        '[worktrees]\nschema_version = 1\nsymlink_paths = ["shared"]\n'
    )

    r = _run_wt(repo, "new", "feat-union")
    assert r.returncode == 0, r.stderr
    wt = Path(r.stdout.strip())

    # All three sources represented under union semantics
    assert (wt / ".tools").is_symlink()
    assert (wt / "agents").is_symlink()
    assert (wt / "shared").is_symlink()
