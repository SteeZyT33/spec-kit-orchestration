"""Hook execution with the env contract documented in the spec.

Stage 2 (after_create), Stage 3 (before_run), Stage 4 (before_remove).
This module is purely about running ONE hook script with the right env;
trust verification is a separate concern (trust.py).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class HookEnv:
    repo_root: Path
    worktree_dir: Path
    branch: str
    lane_id: str
    lane_mode: Literal["branch", "lane"]
    feature_id: str | None
    host_system: str


@dataclass(frozen=True)
class HookOutcome:
    status: Literal["skipped", "completed", "failed"]
    exit_code: int
    duration_ms: int
    stdout: str = ""
    stderr: str = ""


def hook_sha(script_path: Path) -> str:
    """SHA-256 hex of the script content. Used by the trust ledger."""
    h = hashlib.sha256()
    h.update(script_path.read_bytes())
    return h.hexdigest()


def _build_env(env: HookEnv) -> dict[str, str]:
    out = dict(os.environ)
    out["ORCA_REPO_ROOT"] = str(env.repo_root.resolve())
    out["ORCA_WORKTREE_DIR"] = str(env.worktree_dir.resolve())
    out["ORCA_BRANCH"] = env.branch
    out["ORCA_LANE_ID"] = env.lane_id
    out["ORCA_LANE_MODE"] = env.lane_mode
    if env.feature_id is not None:
        out["ORCA_FEATURE_ID"] = env.feature_id
    out["ORCA_HOST_SYSTEM"] = env.host_system
    return out


def run_hook(*, script_path: Path, env: HookEnv) -> HookOutcome:
    """Execute one hook script.

    Returns HookOutcome with status:
      - "skipped"  if script doesn't exist
      - "completed" if exit 0
      - "failed"   if non-zero
    """
    if not script_path.exists():
        return HookOutcome(status="skipped", exit_code=0, duration_ms=0)

    started = time.monotonic()
    proc = subprocess.run(
        [str(script_path)],
        cwd=str(env.worktree_dir),
        env=_build_env(env),
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = int((time.monotonic() - started) * 1000)
    status = "completed" if proc.returncode == 0 else "failed"
    return HookOutcome(
        status=status,
        exit_code=proc.returncode,
        duration_ms=elapsed,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
