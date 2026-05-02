"""Subprocess wrappers + filesystem probes used by collect_fleet.

Phase 2 ships only the read-only probes (tmux_alive, branch_merged,
last_event, last_setup_failed). Mutating actions land in Phase 4.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path


def tmux_alive(session: str) -> bool:
    """True if `tmux has-session -t <session>` succeeds."""
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session],
            capture_output=True, timeout=2.0,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def branch_merged(repo_root: Path, branch: str, base: str) -> bool:
    """True if `branch` is reachable from `base` via git --merged."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "branch", "--merged", base,
             "--format", "%(refname:short)"],
            capture_output=True, text=True, timeout=5.0,
        )
        if out.returncode != 0:
            return False
        return branch in {ln.strip() for ln in out.stdout.splitlines()}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def last_event(repo_root: Path, lane_id: str) -> str | None:
    """Most recent event type for `lane_id` from .orca/worktrees/events.jsonl.
    Returns None if no events for this lane."""
    path = repo_root / ".orca" / "worktrees" / "events.jsonl"
    if not path.exists():
        return None
    found: str | None = None
    with path.open() as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("lane_id") == lane_id:
                found = entry.get("event")
    return found


def last_setup_failed(repo_root: Path, lane_id: str) -> bool:
    """True if the most recent setup.* event for the lane was a .failed."""
    path = repo_root / ".orca" / "worktrees" / "events.jsonl"
    if not path.exists():
        return False
    last_setup: str | None = None
    with path.open() as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("lane_id") != lane_id:
                continue
            evt = entry.get("event", "")
            if evt.startswith("setup."):
                last_setup = evt
    return bool(last_setup and last_setup.endswith(".failed"))


@dataclass(frozen=True)
class ActionResult:
    rc: int
    stdout: str
    stderr: str


def close_lane(repo_root: Path, *, branch: str, force: bool = True) -> ActionResult:
    cmd = ["orca-cli", "wt", "rm", "--branch", branch]
    if force:
        cmd.append("--force")
    out = subprocess.run(cmd, cwd=str(repo_root), capture_output=True,
                         text=True, timeout=30)
    return ActionResult(out.returncode, out.stdout, out.stderr)


def new_lane(
    repo_root: Path, *, feature: str, agent: str = "claude",
    from_branch: str | None = None,
) -> ActionResult:
    cmd = ["orca-cli", "wt", "new", "--feature", feature, "--agent", agent]
    if from_branch:
        cmd += ["--from", from_branch]
    out = subprocess.run(cmd, cwd=str(repo_root), capture_output=True,
                         text=True, timeout=120)
    return ActionResult(out.returncode, out.stdout, out.stderr)


def doctor(repo_root: Path) -> ActionResult:
    cmd = ["orca-cli", "wt", "doctor", "--reap"]
    out = subprocess.run(cmd, cwd=str(repo_root), capture_output=True,
                         text=True, timeout=30)
    return ActionResult(out.returncode, out.stdout, out.stderr)


def open_shell(worktree_path: Path) -> int:
    """Spawn $SHELL -i in the worktree. Caller suspends Textual first."""
    shell = os.environ.get("SHELL", "/bin/sh")
    return subprocess.call([shell, "-i"], cwd=str(worktree_path))


def open_editor(worktree_path: Path) -> int:
    """Spawn $EDITOR (split via shlex) on the worktree. Caller suspends."""
    editor = os.environ.get("EDITOR", "vi")
    parts = shlex.split(editor)
    return subprocess.call([*parts, str(worktree_path)],
                            cwd=str(worktree_path))
