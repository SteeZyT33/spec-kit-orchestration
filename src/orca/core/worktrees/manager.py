"""WorktreeManager: orchestrates create/remove against the state cube."""
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
    LaneRow, Sidecar, acquire_registry_lock, read_registry, read_sidecar,
    sidecar_path, write_registry, write_sidecar, registry_path,
)


class IdempotencyError(RuntimeError):
    """Raised when wt new encounters a state-cube row that requires an
    explicit flag (--reuse-branch or --recreate-branch)."""


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


def _branch_exists(repo_root: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show-ref", "--verify", "--quiet",
         f"refs/heads/{branch}"],
        check=False,
    )
    return result.returncode == 0


def _worktree_for_branch(repo_root: Path, branch: str) -> Path | None:
    """Return the worktree path for a branch, or None if not checked out."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    current_path: Path | None = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line[len("worktree "):].strip())
        elif line.startswith("branch "):
            ref = line[len("branch "):].strip()
            if ref == f"refs/heads/{branch}":
                return current_path
    return None


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

            branch_exists = _branch_exists(self.repo_root, req.branch)
            existing_wt = _worktree_for_branch(self.repo_root, req.branch)
            worktree_exists = existing_wt is not None and existing_wt.exists()
            scp = sidecar_path(self.worktree_root, lane_id)
            sidecar_exists = scp.exists()
            view = read_registry(self.worktree_root)
            registry_exists = any(l.lane_id == lane_id for l in view.lanes)

            # Row 8 — sidecar branch mismatch: existing sidecar's branch
            # disagrees with --branch arg (operator wants to reuse a lane-id
            # for a different branch). Refuse rather than silently overwrite.
            if sidecar_exists:
                existing_sc = read_sidecar(scp)
                if (existing_sc is not None and
                        existing_sc.branch != req.branch):
                    raise IdempotencyError(
                        f"lane-id {lane_id!r} is already registered for "
                        f"branch {existing_sc.branch!r}; cannot reuse for "
                        f"{req.branch!r}. Run `wt rm {lane_id}` first."
                    )

            # Fully-registered attach (row 5 + sidecar branch matches)
            if (worktree_exists and sidecar_exists and registry_exists
                    and existing_wt == wt_path):
                emit_event(self.worktree_root, event="lane.attached",
                           lane_id=lane_id)
                return CreateResult(
                    lane_id=lane_id, worktree_path=wt_path, branch=req.branch,
                    tmux_session=None, tmux_window=None,
                )

            # Row 4 — worktree at non-canonical path
            if worktree_exists and existing_wt != wt_path:
                raise IdempotencyError(
                    f"worktree for {req.branch} exists at unexpected path "
                    f"{existing_wt}; expected {wt_path}. Run `wt rm` first."
                )

            # Row 6 — sidecar/registry stale, branch exists, no worktree
            if branch_exists and not worktree_exists and (sidecar_exists or registry_exists):
                if not req.reuse_branch:
                    raise IdempotencyError(
                        f"sidecar+registry stale for {lane_id}; branch "
                        f"{req.branch} still exists. Pass --reuse-branch "
                        f"to attach a fresh worktree."
                    )
                # Clean stale, then proceed
                if scp.exists():
                    scp.unlink()
                view = read_registry(self.worktree_root)
                view_lanes = [l for l in view.lanes if l.lane_id != lane_id]
                write_registry(self.worktree_root, view_lanes)

            # Row 7 — no branch, sidecar/registry orphan
            if not branch_exists and (sidecar_exists or registry_exists):
                if not req.recreate_branch:
                    # Auto-clean stale entries first, then refuse
                    if scp.exists():
                        scp.unlink()
                    view2 = read_registry(self.worktree_root)
                    write_registry(self.worktree_root,
                                   [l for l in view2.lanes if l.lane_id != lane_id])
                    raise IdempotencyError(
                        f"orphan sidecar/registry for {lane_id} cleaned. "
                        f"Pass --recreate-branch to recreate {req.branch}."
                    )
                # Clean + recreate
                if scp.exists():
                    scp.unlink()
                view3 = read_registry(self.worktree_root)
                write_registry(self.worktree_root,
                               [l for l in view3.lanes if l.lane_id != lane_id])

            # Row 2 — branch exists locally but no worktree, no sidecar
            if branch_exists and not worktree_exists and not sidecar_exists and not req.reuse_branch:
                raise IdempotencyError(
                    f"branch {req.branch} exists but has no worktree. "
                    f"Pass --reuse-branch to adopt it into a new worktree."
                )

            # Row 3 — worktree at expected path, no sidecar (operator created
            # via `git worktree add` directly): adopt it.
            adopting_existing = worktree_exists and existing_wt == wt_path and not sidecar_exists

            # Now create or adopt
            if not worktree_exists:
                if branch_exists:
                    # --reuse-branch path: adopt existing branch
                    subprocess.run(
                        ["git", "-C", str(self.repo_root), "worktree", "add",
                         str(wt_path), req.branch],
                        check=True, capture_output=True,
                    )
                else:
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

            view4 = read_registry(self.worktree_root)
            new_lanes = [l for l in view4.lanes if l.lane_id != lane_id]
            new_lanes.append(LaneRow(
                lane_id=lane_id, branch=req.branch,
                worktree_path=str(wt_path), feature_id=req.feature,
            ))
            write_registry(self.worktree_root, new_lanes)

            event = "lane.attached" if adopting_existing else "lane.created"
            emit_event(self.worktree_root, event=event,
                       lane_id=lane_id, branch=req.branch)

        return CreateResult(
            lane_id=lane_id, worktree_path=wt_path, branch=req.branch,
            tmux_session=None, tmux_window=None,
        )
