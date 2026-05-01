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


def _run_wt_contract(repo: Path, *args: str):
    return subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "wt", "contract", *args],
        cwd=str(repo), capture_output=True, text=True, check=False,
    )


@pytest.fixture
def repo(tmp_path):
    return _init_repo(tmp_path)


class TestWtContractEmit:
    def test_emit_creates_contract_file(self, repo):
        (repo / ".tools").mkdir()
        (repo / ".tools" / "f.json").write_text("{}")
        result = _run_wt_contract(repo, "emit")
        assert result.returncode == 0, result.stderr
        contract = repo / ".worktree-contract.json"
        assert contract.exists()
        data = json.loads(contract.read_text())
        assert ".tools" in data["symlink_paths"]

    def test_emit_dry_run_writes_to_stdout(self, repo):
        (repo / ".tools").mkdir()
        result = _run_wt_contract(repo, "emit", "--dry-run")
        assert result.returncode == 0
        assert not (repo / ".worktree-contract.json").exists()
        data = json.loads(result.stdout)
        assert ".tools" in data["symlink_paths"]

    def test_emit_refuses_overwrite_without_force(self, repo):
        (repo / ".worktree-contract.json").write_text("{}")
        result = _run_wt_contract(repo, "emit")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["error"]["kind"] == "input_invalid"

    def test_unknown_subverb_returns_input_invalid(self, repo):
        result = _run_wt_contract(repo, "exterminate")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["error"]["kind"] == "input_invalid"

    def test_emit_rejects_init_script_traversal(self, repo):
        result = _run_wt_contract(repo, "emit", "--init-script",
                                  "../escape.sh")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["error"]["kind"] == "input_invalid"

    def test_emit_rejects_init_script_absolute(self, repo):
        result = _run_wt_contract(repo, "emit", "--init-script",
                                  "/etc/escape.sh")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["error"]["kind"] == "input_invalid"


class TestWtContractFromCmux:
    def test_from_cmux_rejects_path_traversal(self, repo):
        result = _run_wt_contract(repo, "from-cmux", "--cmux-script",
                                  "../etc/passwd")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["error"]["kind"] == "input_invalid"

    def test_from_cmux_rejects_absolute_path(self, repo):
        result = _run_wt_contract(repo, "from-cmux", "--cmux-script",
                                  "/etc/passwd")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["error"]["kind"] == "input_invalid"

    def test_writes_contract_from_perflab_setup(self, repo):
        (repo / ".cmux").mkdir()
        (repo / ".cmux" / "setup").write_text(
            "for f in .env .env.local; do\n"
            '  [ -e "$REPO_ROOT/$f" ] && ln -sf "$REPO_ROOT/$f" "$f"\n'
            "done\n"
        )
        result = _run_wt_contract(repo, "from-cmux")
        assert result.returncode == 0, result.stderr
        contract = repo / ".worktree-contract.json"
        assert contract.exists()
        import json
        data = json.loads(contract.read_text())
        assert sorted(data["symlink_files"]) == [".env", ".env.local"]


class TestWtContractInstallCmuxShim:
    def test_writes_shim(self, repo):
        result = _run_wt_contract(repo, "install-cmux-shim")
        assert result.returncode == 0, result.stderr
        shim = repo / ".cmux" / "setup"
        assert shim.exists()
        body = shim.read_text()
        assert "WARNING:" in body
        assert "ORCA_SHIM_NO_PROMPT" in body
