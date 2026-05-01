import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from orca.core.worktrees.contract_shim import install_cmux_shim


class TestInstallCmuxShim:
    def test_writes_executable_shim(self, tmp_path):
        path = install_cmux_shim(tmp_path, force=False)
        assert path.exists()
        # Executable bit set
        assert path.stat().st_mode & stat.S_IXUSR
        body = path.read_text()
        assert "#!/usr/bin/env bash" in body
        assert "command -v python3" in body
        assert "ORCA_SHIM_NO_PROMPT" in body
        assert "WARNING:" in body

    def test_refuses_overwrite_without_force(self, tmp_path):
        (tmp_path / ".cmux").mkdir()
        (tmp_path / ".cmux" / "setup").write_text("# existing\n")
        with pytest.raises(FileExistsError):
            install_cmux_shim(tmp_path, force=False)

    def test_overwrites_with_force(self, tmp_path):
        (tmp_path / ".cmux").mkdir()
        (tmp_path / ".cmux" / "setup").write_text("# old\n")
        path = install_cmux_shim(tmp_path, force=True)
        body = path.read_text()
        assert "#!/usr/bin/env bash" in body
        assert "# old" not in body

    def test_shim_runs_against_real_contract(self, tmp_path):
        """End-to-end: install shim, lay down a contract, run shim,
        verify symlinks are created (skips if python3 not on PATH)."""
        if not _has_python3():
            pytest.skip("python3 not on PATH")

        # Set up a fake repo + worktree
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        (tmp_path / ".env").write_text("FOO=1")
        wt = tmp_path / "wt"
        wt.mkdir()

        # Contract at repo root
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": [],
            "symlink_files": [".env"],
        }))

        # Install shim, then run from the worktree dir
        install_cmux_shim(tmp_path, force=False)
        shim_path = tmp_path / ".cmux" / "setup"

        env = {**os.environ, "ORCA_SHIM_NO_PROMPT": "1"}
        result = subprocess.run(
            ["bash", str(shim_path)],
            cwd=str(wt),
            env=env,
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr
        assert (wt / ".env").is_symlink()


def _has_python3() -> bool:
    try:
        rc = subprocess.run(
            ["command", "-v", "python3"], shell=False, check=False,
            capture_output=True,
        ).returncode
    except (FileNotFoundError, OSError):
        rc = 1
    return rc == 0 or _which("python3")


def _which(name: str) -> bool:
    import shutil
    return shutil.which(name) is not None
