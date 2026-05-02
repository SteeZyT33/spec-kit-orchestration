"""Build FleetRows from sidecars + events + flow_state + git + tmux probes.

Probes (tmux_alive, branch_merged, last_event, last_setup_failed) are
injected callables so collect_fleet stays unit-testable without a real
git/tmux environment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from orca.core.host_layout import from_manifest
from orca.core.worktrees.registry import (
    RegistryView, read_registry, read_sidecar, sidecar_path,
)
from orca.flow_state import FlowMilestone, compute_flow_state
from orca.tui.flow_strip import plain_strip
from orca.tui.health import HealthInputs, derive_health
from orca.tui.models import FleetRow
from orca.tui.state import StateInputs, derive_state
from orca.tui.timefmt import format_age


_STATE_RANK = {"live": 0, "stale": 1, "merged": 2, "failed": 3, "idle": 4}


def collect_fleet(
    repo_root: Path,
    *,
    tmux_alive: Callable[[str], bool],
    branch_merged: Callable[[str, str], bool],
    last_event: Callable[[str], str | None] | None = None,
    last_setup_failed: Callable[[str], bool] | None = None,
    now: datetime | None = None,
) -> list[FleetRow]:
    """Build FleetRows for every lane in the registry. Empty list when
    no .orca/worktrees/registry.json exists."""
    cur = now or datetime.now(timezone.utc)
    wt_root = repo_root / ".orca" / "worktrees"
    if not (wt_root / "registry.json").exists():
        return []

    view: RegistryView = read_registry(wt_root)
    if not view.lanes:
        return []

    rows: list[FleetRow] = []
    for lane in view.lanes:
        sc = read_sidecar(sidecar_path(wt_root, lane.lane_id))
        if sc is None:
            continue

        evt = (last_event or (lambda _l: None))(lane.lane_id)
        setup_fail = (last_setup_failed or (lambda _l: False))(lane.lane_id)
        tmux = tmux_alive(sc.tmux_session)
        merged = branch_merged(sc.branch, sc.base_branch)

        state = derive_state(StateInputs(
            last_attached_at=sc.last_attached_at,
            last_event=evt,
            tmux_alive=tmux,
            branch_merged=merged,
            last_setup_failed=setup_fail,
        ), now=cur)

        health = derive_health(HealthInputs(
            last_attached_at=sc.last_attached_at,
            last_setup_failed=setup_fail,
            branch_merged=merged,
            tmux_alive=tmux,
            sidecar_active=(sc.status == "active"),
            doctor_warnings=[],
        ), now=cur)

        strip = _stage_strip_for(repo_root, sc.feature_id)
        done = _done_shorthand(repo_root, sc.feature_id)

        rows.append(FleetRow(
            lane_id=sc.lane_id,
            feature_id=sc.feature_id,
            branch=sc.branch,
            worktree_path=sc.worktree_path,
            agent=sc.agent,
            state=state,
            stage_strip=strip,
            last_seen=format_age(sc.last_attached_at, now=cur),
            done=done,
            health=health,
        ))

    rows.sort(key=lambda r: (_STATE_RANK.get(r.state, 99), r.lane_id))
    return rows


def _stage_strip_for(repo_root: Path, feature_id: str | None) -> str:
    """Compute the 8-char strip; returns all-not_started if no feature_id
    or if compute_flow_state can't read the feature dir for any reason."""
    if not feature_id:
        return _empty_strip()
    try:
        layout = from_manifest(repo_root)
    except Exception:
        return _empty_strip()
    feat_dir = layout.resolve_feature_dir(feature_id)
    try:
        result = compute_flow_state(feat_dir, repo_root=repo_root)
    except Exception:
        return _empty_strip()
    all_milestones = result.completed_milestones + result.incomplete_milestones
    return plain_strip(all_milestones)


def _empty_strip() -> str:
    return plain_strip([
        FlowMilestone(stage=s, status="not_started")
        for s in ["brainstorm", "specify", "plan", "tasks", "implement",
                  "review-spec", "review-code", "review-pr"]
    ])


def _done_shorthand(repo_root: Path, feature_id: str | None) -> str:
    """Three-glyph 'spec X code Y pr Z' shorthand."""
    if not feature_id:
        return "·  ·  · "
    try:
        layout = from_manifest(repo_root)
        result = compute_flow_state(layout.resolve_feature_dir(feature_id),
                                     repo_root=repo_root)
    except Exception:
        return "·  ·  · "

    by_type = {r.review_type: r.status for r in result.review_milestones}

    def glyph(status: str | None) -> str:
        if status == "complete":
            return "✓"
        if status == "in_progress":
            return "⏵"
        if status == "blocked":
            return "✕"
        return "·"

    return f"{glyph(by_type.get('review-spec'))}  {glyph(by_type.get('review-code'))}  {glyph(by_type.get('review-pr'))}"
