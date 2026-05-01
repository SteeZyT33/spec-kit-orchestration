"""WorktreeManager: orchestrates create/remove against the state cube.

This task implements only the happy path (state-cube row 1: nothing
exists yet). Subsequent tasks layer in the other 7 rows.
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from orca.core.worktrees.config import WorktreesConfig
from orca.core.worktrees.events import emit_event
from orca.core.worktrees.identifiers import derive_lane_id
from orca.core.worktrees.layout import resolve_worktree_path
from orca.core.worktrees.protocol import CreateRequest, CreateResult
from orca.core.worktrees.registry import (
    LaneRow, Sidecar, acquire_registry_lock, read_registry, write_registry,
    write_sidecar, registry_path,
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_branch(repo_root: Path) -> str:
    """Try origin HEAD, then main, then master, then current symbolic-ref,
    then init.defaultBranch. Works on empty repos (no commits) — important
    because operators run `git init && orca-cli wt new feat` and we must not
    crash on that path."""
    # 1. Remote HEAD (most authoritative on cloned repos)
    result = subprocess.run(
        ["git", "-C", str(repo_root), "symbolic-ref",
         "refs/remotes/origin/HEAD"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode == 0:
        return result.stdout.strip().split("/")[-1]
    # 2. Local main / master refs
    for branch in ("main", "master"):
        check = subprocess.run(
            ["git", "-C", str(repo_root), "show-ref", "--verify", "--quiet",
             f"refs/heads/{branch}"],
            check=False,
        )
        if check.returncode == 0:
            return branch
    # 3. Current HEAD via symbolic-ref (works on empty repo: returns the
    #    unborn branch like 'main' even with zero commits)
    sym = subprocess.run(
        ["git", "-C", str(repo_root), "symbolic-ref", "--short", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if sym.returncode == 0 and sym.stdout.strip():
        return sym.stdout.strip()
    # 4. init.defaultBranch (git ≥ 2.28)
    cfg = subprocess.run(
        ["git", "-C", str(repo_root), "config", "--get",
         "init.defaultBranch"],
        capture_output=True, text=True, check=False,
    )
    if cfg.returncode == 0 and cfg.stdout.strip():
        return cfg.stdout.strip()
    # 5. Final fallback
    return "main"


class WorktreeManager:
    def __init__(
        self,
        *,
        repo_root: Path,
        cfg: WorktreesConfig,
        host_system: str,
        run_tmux: bool = True,
        run_setup: bool = True,
    ) -> None:
        self.repo_root = repo_root
        self.cfg = cfg
        self.host_system = host_system
        self.run_tmux = run_tmux
        self.run_setup = run_setup
        self.worktree_root = repo_root / ".orca" / "worktrees"

    def create(self, req: CreateRequest) -> CreateResult:
        lane_id = derive_lane_id(
            branch=req.branch, mode=self.cfg.lane_id_mode,
            feature=req.feature, lane=req.lane,
        )
        wt_path = resolve_worktree_path(self.repo_root, self.cfg, lane_id=lane_id)
        from_branch = req.from_branch or _default_branch(self.repo_root)

        with acquire_registry_lock(self.worktree_root):
            self.worktree_root.mkdir(parents=True, exist_ok=True)
            # State-cube row 1 only this task: assume nothing exists.
            # Later tasks will branch on the 8-row table here.

            # git worktree add -b <branch> <path> <from>
            subprocess.run(
                ["git", "-C", str(self.repo_root), "worktree", "add",
                 "-b", req.branch, str(wt_path), from_branch],
                check=True, capture_output=True,
            )

            sidecar = Sidecar(
                schema_version=2,
                lane_id=lane_id,
                lane_mode="lane" if (req.feature and req.lane) else "branch",
                feature_id=req.feature,
                lane_name=req.lane,
                branch=req.branch,
                base_branch=from_branch,
                worktree_path=str(wt_path),
                created_at=_now_utc(),
                tmux_session=self.cfg.tmux_session,
                tmux_window=lane_id[:32],
                agent=req.agent,
                setup_version="",
                last_attached_at=None,
                host_system=self.host_system,
            )
            write_sidecar(self.worktree_root, sidecar)

            # Append to registry
            view = read_registry(self.worktree_root)
            new_lanes = list(view.lanes) + [LaneRow(
                lane_id=lane_id, branch=req.branch,
                worktree_path=str(wt_path), feature_id=req.feature,
            )]
            write_registry(self.worktree_root, new_lanes)

            emit_event(self.worktree_root, event="lane.created",
                       lane_id=lane_id, branch=req.branch)

        return CreateResult(
            lane_id=lane_id,
            worktree_path=wt_path,
            branch=req.branch,
            tmux_session=None,
            tmux_window=None,
        )
