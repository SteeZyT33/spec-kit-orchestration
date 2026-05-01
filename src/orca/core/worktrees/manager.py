"""WorktreeManager: orchestrates create/remove against the state cube."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from orca.core.worktrees import tmux
from orca.core.worktrees.agent_launch import write_launcher
from orca.core.worktrees.auto_symlink import run_stage1
from orca.core.worktrees.config import WorktreesConfig
from orca.core.worktrees.events import emit_event
from orca.core.worktrees.hooks import HookEnv, hook_sha, run_hook
from orca.core.worktrees.identifiers import derive_lane_id
from orca.core.worktrees.layout import resolve_worktree_path
from orca.core.worktrees.protocol import CreateRequest, CreateResult, RemoveRequest
from orca.core.worktrees.registry import (
    LaneRow, Sidecar, acquire_registry_lock, read_registry, read_sidecar,
    sidecar_path, write_registry, write_sidecar, registry_path,
)
from orca.core.worktrees.trust import (
    TrustDecision, TrustOutcome, check_or_prompt, resolve_repo_key,
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
    """Orchestrates create/remove against the registry/sidecar state cube.

    State (registry/sidecars/events/lock/hooks) lives at
    ``<repo>/.orca/worktrees/`` regardless of ``cfg.base``. ``cfg.base``
    controls only where individual worktree CHECKOUTS land — the actual
    checkout path is computed via ``resolve_worktree_path`` from
    ``layout.py``, which DOES honor ``cfg.base``.
    """
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
        # State directory: registry/sidecars/events/lock/hooks. NOT cfg.base.
        self.state_root = repo_root / ".orca" / "worktrees"

    def _trust_or_skip(
        self,
        *,
        env: HookEnv,
        script_path: Path,
        decision: TrustDecision,
        interactive: bool,
        stage_name: str,
    ) -> bool:
        """Return True if hook is trusted/bypassed, False if declined.

        Caller decides what False means. Stage 2 raises (revert);
        Stage 3/4 logs and skips (emits setup.<stage>.skipped_untrusted).
        """
        sha = hook_sha(script_path)
        outcome = check_or_prompt(
            repo_key=resolve_repo_key(env.repo_root),
            script_path=str(script_path),
            sha=sha,
            script_text=script_path.read_text(encoding="utf-8"),
            decision=decision,
            interactive=interactive,
        )
        return outcome not in (
            TrustOutcome.DECLINED, TrustOutcome.REFUSED_NONINTERACTIVE,
        )

    def _run_setup_stages(self, *, lane_id: str, wt_path: Path,
                          req: CreateRequest, base_branch: str) -> str:
        """Run Stage 1 (auto-symlink) + Stage 2 (after_create) + Stage 3
        (before_run). Returns the after_create SHA (used for setup_version)
        or '' if no after_create hook ran. Raises on Stage 2 failure."""
        # Stage 1: also pass manifest's constitution_path / agents_md_path
        # if a manifest is present, so the host's canonical files get
        # symlinked alongside the host-derived directories.
        constitution_path = None
        agents_md_path = None
        manifest_path = self.repo_root / ".orca" / "adoption.toml"
        if manifest_path.exists():
            try:
                from orca.core.adoption.manifest import load_manifest
                m = load_manifest(manifest_path)
                constitution_path = m.host.constitution_path
                agents_md_path = m.host.agents_md_path
            except Exception:
                # Bad manifest — Stage 1 still proceeds with host_system defaults
                pass

        from orca.core.worktrees.contract import load_contract, ContractError
        try:
            contract = load_contract(self.repo_root)
        except ContractError as exc:
            # Bad contract — proceed with no contract (orca should not fail
            # worktree creation just because the contract is malformed) but
            # surface the failure: stderr warning + structured event so an
            # operator who fat-fingers their contract gets a clear signal.
            contract = None
            print(
                f"warning: .worktree-contract.json invalid: {exc}",
                file=sys.stderr,
            )
            emit_event(
                self.state_root,
                event="contract.load_failed",
                lane_id=lane_id,
                error=str(exc),
            )

        run_stage1(
            primary_root=self.repo_root, worktree_dir=wt_path,
            cfg=self.cfg, host_system=self.host_system,
            constitution_path=constitution_path,
            agents_md_path=agents_md_path,
            contract=contract,
        )

        env = HookEnv(
            repo_root=self.repo_root, worktree_dir=wt_path,
            branch=req.branch, lane_id=lane_id,
            lane_mode="lane" if (req.feature and req.lane) else "branch",
            feature_id=req.feature, host_system=self.host_system,
        )

        ac_path = self.state_root / self.cfg.after_create_hook
        setup_sha = ""
        if req.no_setup:
            return ""
        decision = TrustDecision(
            trust_hooks=req.trust_hooks, record=req.record_trust,
        )
        interactive = os.isatty(0)
        if ac_path.exists():
            sha = hook_sha(ac_path)
            if not self._trust_or_skip(
                env=env, script_path=ac_path, decision=decision,
                interactive=interactive, stage_name="after_create",
            ):
                raise RuntimeError(
                    "after_create hook untrusted. "
                    "Use --no-setup to skip or --trust-hooks to bypass."
                )

            emit_event(self.state_root,
                       event="setup.after_create.started",
                       lane_id=lane_id)
            result = run_hook(script_path=ac_path, env=env)
            event = ("setup.after_create.completed"
                     if result.status == "completed"
                     else "setup.after_create.failed")
            emit_event(self.state_root, event=event,
                       lane_id=lane_id, exit_code=result.exit_code,
                       duration_ms=result.duration_ms)
            if result.status == "failed":
                raise RuntimeError(
                    f"after_create failed (exit {result.exit_code})"
                )
            setup_sha = sha

        # Stage 2.5: contract.init_script (after orca's after_create hook,
        # trust-gated like other hooks). A single trust-yes for after_create
        # also covers the contract script via the same TrustDecision.
        if contract is not None and contract.init_script:
            contract_script = self.repo_root / contract.init_script
            if (contract_script.is_file()
                    and os.access(contract_script, os.X_OK)):
                if not self._trust_or_skip(
                    env=env, script_path=contract_script,
                    decision=decision, interactive=interactive,
                    stage_name="contract.init_script",
                ):
                    emit_event(
                        self.state_root,
                        event="setup.after_create.skipped_untrusted",
                        lane_id=lane_id,
                    )
                else:
                    emit_event(self.state_root,
                               event="setup.after_create.started",
                               lane_id=lane_id)
                    cs_result = run_hook(
                        script_path=contract_script, env=env,
                    )
                    cs_event = ("setup.after_create.completed"
                                if cs_result.status == "completed"
                                else "setup.after_create.failed")
                    emit_event(self.state_root, event=cs_event,
                               lane_id=lane_id,
                               exit_code=cs_result.exit_code,
                               duration_ms=cs_result.duration_ms)
                    if cs_result.status == "failed":
                        raise RuntimeError(
                            "contract.init_script failed "
                            f"(exit {cs_result.exit_code})"
                        )

        # Stage 3: before_run (failures log but don't abort; untrusted skips)
        br_path = self.state_root / self.cfg.before_run_hook
        if br_path.exists():
            if not self._trust_or_skip(
                env=env, script_path=br_path, decision=decision,
                interactive=interactive, stage_name="before_run",
            ):
                emit_event(self.state_root,
                           event="setup.before_run.skipped_untrusted",
                           lane_id=lane_id)
            else:
                emit_event(self.state_root,
                           event="setup.before_run.started", lane_id=lane_id)
                result = run_hook(script_path=br_path, env=env)
                event = ("setup.before_run.completed"
                         if result.status == "completed"
                         else "setup.before_run.failed")
                emit_event(self.state_root, event=event,
                           lane_id=lane_id, exit_code=result.exit_code,
                           duration_ms=result.duration_ms)
                # Note: before_run failures are non-fatal per spec

        return setup_sha

    def create(self, req: CreateRequest) -> CreateResult:
        lane_id = derive_lane_id(
            branch=req.branch, mode=self.cfg.lane_id_mode,
            feature=req.feature, lane=req.lane,
        )
        wt_path = resolve_worktree_path(self.repo_root, self.cfg, lane_id=lane_id)
        from_branch = req.from_branch or _default_branch(self.repo_root)

        with acquire_registry_lock(self.state_root):
            self.state_root.mkdir(parents=True, exist_ok=True)

            branch_exists = _branch_exists(self.repo_root, req.branch)
            existing_wt = _worktree_for_branch(self.repo_root, req.branch)
            worktree_exists = existing_wt is not None and existing_wt.exists()
            scp = sidecar_path(self.state_root, lane_id)
            sidecar_exists = scp.exists()
            view = read_registry(self.state_root)
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
                emit_event(self.state_root, event="lane.attached",
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
                view = read_registry(self.state_root)
                view_lanes = [l for l in view.lanes if l.lane_id != lane_id]
                write_registry(self.state_root, view_lanes)

            # Row 7 — no branch, sidecar/registry orphan
            if not branch_exists and (sidecar_exists or registry_exists):
                if not req.recreate_branch:
                    raise IdempotencyError(
                        f"orphan sidecar/registry for {lane_id}; pass "
                        f"--recreate-branch to clean up and recreate "
                        f"{req.branch}."
                    )
                # Operator opted in — clean stale, then proceed
                if scp.exists():
                    scp.unlink()
                view2 = read_registry(self.state_root)
                write_registry(self.state_root,
                               [l for l in view2.lanes if l.lane_id != lane_id])

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

            # Stage 1+2+3 setup hooks with revert-on-failure
            if self.run_setup:
                try:
                    setup_sha = self._run_setup_stages(
                        lane_id=lane_id, wt_path=wt_path, req=req,
                        base_branch=from_branch,
                    )
                except Exception:
                    # Revert: remove worktree and (newly created) branch
                    subprocess.run(
                        ["git", "-C", str(self.repo_root), "worktree", "remove",
                         "--force", str(wt_path)],
                        check=False, capture_output=True,
                    )
                    if not branch_exists:
                        subprocess.run(
                            ["git", "-C", str(self.repo_root), "branch", "-D",
                             req.branch],
                            check=False, capture_output=True,
                        )
                    raise
            else:
                setup_sha = ""

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
                setup_version=setup_sha,
                last_attached_at=None,
                host_system=self.host_system,
            )
            write_sidecar(self.state_root, sidecar)

            view4 = read_registry(self.state_root)
            new_lanes = [l for l in view4.lanes if l.lane_id != lane_id]
            new_lanes.append(LaneRow(
                lane_id=lane_id, branch=req.branch,
                worktree_path=str(wt_path), feature_id=req.feature,
            ))
            write_registry(self.state_root, new_lanes)

            event = "lane.attached" if adopting_existing else "lane.created"
            emit_event(self.state_root, event=event,
                       lane_id=lane_id, branch=req.branch)

            tmux_session: str | None = None
            tmux_window: str | None = None
            if self.run_tmux:
                tmux_session = tmux.resolve_session_name(
                    self.cfg.tmux_session, repo_root=self.repo_root,
                )
                tmux.ensure_session(tmux_session, cwd=wt_path)
                tmux_window = lane_id[:32]
                if not tmux.has_window(tmux_session, tmux_window):
                    tmux.new_window(session=tmux_session, window=tmux_window,
                                    cwd=wt_path)
                    emit_event(self.state_root, event="tmux.window.created",
                               lane_id=lane_id, session=tmux_session,
                               window=tmux_window)

                if req.agent != "none":
                    cmd = self.cfg.agents.get(req.agent)
                    if cmd:
                        write_launcher(
                            worktree_dir=wt_path, lane_id=lane_id,
                            agent_cmd=cmd, prompt=req.prompt,
                            extra_args=list(req.extra_args),
                        )
                        tmux.send_keys(
                            session=tmux_session, window=tmux_window,
                            keys=f"bash .orca/.run-{lane_id}.sh",
                        )
                        emit_event(self.state_root, event="agent.launched",
                                   lane_id=lane_id, agent=req.agent)

        return CreateResult(
            lane_id=lane_id, worktree_path=wt_path, branch=req.branch,
            tmux_session=tmux_session, tmux_window=tmux_window,
        )

    def remove(self, req: RemoveRequest) -> None:
        with acquire_registry_lock(self.state_root):
            view = read_registry(self.state_root)
            # Find lane by branch
            target_row = next(
                (l for l in view.lanes if l.branch == req.branch), None,
            )

            existing_wt = _worktree_for_branch(self.repo_root, req.branch)
            sidecar_exists = (
                target_row is not None
                and sidecar_path(self.state_root, target_row.lane_id).exists()
            )

            # No-op short-circuit
            if target_row is None and not sidecar_exists and existing_wt is None:
                return

            # External worktree refusal
            if existing_wt is not None and target_row is None and not req.force:
                raise IdempotencyError(
                    f"external worktree at {existing_wt} not registered with "
                    f"orca; pass --force to remove anyway."
                )

            lane_id = target_row.lane_id if target_row else None

            # Stage 4: before_remove hook (run while worktree still exists).
            # Skipped entirely when req.no_setup; trust-gated otherwise.
            br_path = self.state_root / self.cfg.before_remove_hook
            if (not req.no_setup and lane_id is not None and br_path.exists()
                    and existing_wt is not None):
                env = HookEnv(
                    repo_root=self.repo_root, worktree_dir=existing_wt,
                    branch=req.branch, lane_id=lane_id, lane_mode="branch",
                    feature_id=None, host_system=self.host_system,
                )
                decision = TrustDecision(
                    trust_hooks=req.trust_hooks, record=req.record_trust,
                )
                if not self._trust_or_skip(
                    env=env, script_path=br_path, decision=decision,
                    interactive=os.isatty(0), stage_name="before_remove",
                ):
                    emit_event(self.state_root,
                               event="setup.before_remove.skipped_untrusted",
                               lane_id=lane_id)
                else:
                    emit_event(self.state_root,
                               event="setup.before_remove.started",
                               lane_id=lane_id)
                    result = run_hook(script_path=br_path, env=env)
                    emit_event(
                        self.state_root,
                        event=("setup.before_remove.completed"
                               if result.status == "completed"
                               else "setup.before_remove.failed"),
                        lane_id=lane_id, exit_code=result.exit_code,
                        duration_ms=result.duration_ms,
                    )

            # Remove worktree (if present)
            if existing_wt is not None:
                subprocess.run(
                    ["git", "-C", str(self.repo_root), "worktree", "remove",
                     "--force", str(existing_wt)],
                    check=False, capture_output=True,
                )

            # Tmux teardown (after worktree removed, before branch delete)
            if self.run_tmux and lane_id is not None:
                session = tmux.resolve_session_name(
                    self.cfg.tmux_session, repo_root=self.repo_root,
                )
                window = lane_id[:32]
                tmux.kill_window(session=session, window=window)
                tmux.kill_session_if_empty(session)
                emit_event(self.state_root, event="tmux.window.killed",
                           lane_id=lane_id)

            # Remove branch (unless --keep-branch)
            if not req.keep_branch:
                subprocess.run(
                    ["git", "-C", str(self.repo_root), "branch", "-D", req.branch],
                    check=False, capture_output=True,
                )

            # Clean sidecar + registry
            if lane_id is not None:
                scp = sidecar_path(self.state_root, lane_id)
                if scp.exists():
                    scp.unlink()
                new_lanes = [l for l in view.lanes if l.lane_id != lane_id]
                write_registry(self.state_root, new_lanes)
                emit_event(self.state_root, event="lane.removed",
                           lane_id=lane_id, branch_kept=req.keep_branch)
