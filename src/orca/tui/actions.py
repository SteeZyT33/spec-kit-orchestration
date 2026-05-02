"""Shell-out helpers for TUI v2 worktree actions.

Each function returns an ActionResult with rc/stdout/stderr. None
ever raises — exceptions become rc=-1 with stderr populated.
"""
from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActionResult:
    rc: int
    stdout: str
    stderr: str


def close_worktree(repo_root: Path, feature_or_branch: str) -> ActionResult:
    """Run `orca-cli wt rm <branch>` and capture the result.

    The wt capability calls the verb `rm`; we keep this Python helper
    name `close_worktree` because it reads better as an operator
    action (close/finish a worktree) than as a verb (rm).
    """
    try:
        completed = subprocess.run(
            ["orca-cli", "wt", "rm", feature_or_branch],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30.0,
        )
    except (FileNotFoundError, OSError) as exc:
        logger.debug("orca-cli wt rm failed", exc_info=True)
        return ActionResult(rc=-1, stdout="", stderr=str(exc))
    return ActionResult(
        rc=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _split_command(cmdline: str) -> list[str]:
    """Split a command-line into argv, handling EDITOR=`code --wait`.

    Falls back to single-arg if shlex can't parse.
    """
    try:
        parts = shlex.split(cmdline)
    except ValueError:
        return [cmdline]
    return parts or [cmdline]


def open_shell(worktree_path: Path) -> ActionResult:
    """Spawn $SHELL in the worktree dir (caller manages app.suspend)."""
    shell_env = os.environ.get("SHELL") or shutil.which("bash") or "/bin/sh"
    argv = _split_command(shell_env)
    try:
        completed = subprocess.run(argv, cwd=str(worktree_path))
    except (FileNotFoundError, OSError) as exc:
        return ActionResult(rc=-1, stdout="", stderr=str(exc))
    return ActionResult(rc=completed.returncode, stdout="", stderr="")


def open_editor(worktree_path: Path) -> ActionResult:
    """Spawn $EDITOR in the worktree dir (caller manages app.suspend).

    Handles compound editor commands like `code --wait` or `vim -p`
    by shlex-splitting before passing to subprocess.
    """
    editor_env = os.environ.get("EDITOR") or shutil.which("vi") or "/usr/bin/vi"
    argv = _split_command(editor_env) + [str(worktree_path)]
    try:
        completed = subprocess.run(argv)
    except (FileNotFoundError, OSError) as exc:
        return ActionResult(rc=-1, stdout="", stderr=str(exc))
    return ActionResult(rc=completed.returncode, stdout="", stderr="")
