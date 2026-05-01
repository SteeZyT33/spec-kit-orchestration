import os
import stat
from pathlib import Path

import pytest

from orca.core.worktrees.agent_launch import (
    write_launcher, prompt_path, launcher_path,
)


class TestWriteLauncher:
    def test_creates_launcher_and_prompt(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        write_launcher(
            worktree_dir=wt,
            lane_id="015-wiz",
            agent_cmd="claude --dangerously-skip-permissions",
            prompt="Build the thing",
            extra_args=[],
        )
        ldir = wt / ".orca"
        assert ldir.exists()
        # Launcher script
        launcher = ldir / ".run-015-wiz.sh"
        assert launcher.exists()
        mode = launcher.stat().st_mode & 0o777
        assert mode == 0o700
        # Prompt file
        pfile = ldir / ".run-015-wiz.prompt"
        assert pfile.exists()
        pmode = pfile.stat().st_mode & 0o777
        assert pmode == 0o600
        assert pfile.read_text() == "Build the thing"

    def test_no_prompt_skips_prompt_file(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        write_launcher(
            worktree_dir=wt,
            lane_id="x",
            agent_cmd="claude",
            prompt=None,
            extra_args=[],
        )
        assert (wt / ".orca" / ".run-x.sh").exists()
        assert not (wt / ".orca" / ".run-x.prompt").exists()

    def test_extra_args_quoted_safely(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        write_launcher(
            worktree_dir=wt,
            lane_id="x",
            agent_cmd="claude",
            prompt=None,
            extra_args=["--model", "opus", "weird arg with 'quotes'"],
        )
        script = (wt / ".orca" / ".run-x.sh").read_text()
        # shlex.quote ensures the dangerous arg is wrapped safely
        assert "'weird arg with '\"'\"'quotes'\"'\"''" in script

    def test_launcher_invokes_via_exec_after_reading_prompt(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        write_launcher(
            worktree_dir=wt,
            lane_id="x",
            agent_cmd="claude --dangerously-skip-permissions",
            prompt="hello",
            extra_args=[],
        )
        script = (wt / ".orca" / ".run-x.sh").read_text()
        # Prompt is read from the prompt file then deleted before exec
        assert 'PROMPT_FILE=".orca/.run-x.prompt"' in script
        assert "rm -f" in script
        assert "exec claude" in script


class TestAgentCmdSanitization:
    def test_agent_cmd_with_metacharacters_rejected(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        with pytest.raises(ValueError, match="metacharacters"):
            write_launcher(
                worktree_dir=wt, lane_id="x",
                agent_cmd="rm -rf $HOME",
                prompt=None, extra_args=[],
            )

    def test_agent_cmd_with_semicolon_rejected(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        with pytest.raises(ValueError, match="metacharacters"):
            write_launcher(
                worktree_dir=wt, lane_id="x",
                agent_cmd="claude; curl evil.example.com",
                prompt=None, extra_args=[],
            )

    def test_agent_cmd_with_legitimate_args_quoted(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        write_launcher(
            worktree_dir=wt, lane_id="x",
            agent_cmd="claude --model opus",
            prompt=None, extra_args=[],
        )
        script = (wt / ".orca" / ".run-x.sh").read_text()
        # shlex.quote on safe tokens leaves them as-is
        assert "exec claude --model opus" in script

    def test_default_agent_cmds_pass(self, tmp_path):
        """Sanity: shipped defaults must satisfy the new rule."""
        from orca.core.worktrees.config import _DEFAULT_AGENTS
        for name, cmd in _DEFAULT_AGENTS.items():
            wt = tmp_path / f"wt-{name}"
            wt.mkdir()
            write_launcher(
                worktree_dir=wt, lane_id=name, agent_cmd=cmd,
                prompt=None, extra_args=[],
            )


class TestPromptFileSecrecy:
    def test_prompt_file_mode_0600(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        write_launcher(
            worktree_dir=wt,
            lane_id="x",
            agent_cmd="claude",
            prompt="secret",
            extra_args=[],
        )
        pfile = wt / ".orca" / ".run-x.prompt"
        assert (pfile.stat().st_mode & 0o077) == 0  # No group/other access
