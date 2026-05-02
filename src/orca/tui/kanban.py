"""Kanban lifecycle binning for the TUI board view.

A pure function of the filesystem state under a feature directory.
Reuses orca.flow_state for the review-completeness check; everything
else is straight file existence.
"""
from __future__ import annotations

import enum
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from orca import flow_state as _flow_state

logger = logging.getLogger(__name__)


class KanbanColumn(str, enum.Enum):
    SPEC = "Spec"
    PLAN = "Plan"
    TASKS = "Tasks"
    REVIEW = "Review"
    MERGED = "Merged"


COMPLETE_REVIEW_STATUSES = frozenset({"complete", "overall_complete", "present"})


def _branch_merged_to_main(repo_root: Path, feature_id: str) -> bool:
    """True if any branch named `feature_id` (or starting with `feature_id-`)
    is reachable from main. Returns False on any git failure.
    """
    try:
        completed = subprocess.run(
            [
                "git", "-C", str(repo_root),
                "for-each-ref",
                "--merged=main",
                "--format=%(refname:short)",
                "refs/heads/",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2.0,
        )
    except Exception:  # noqa: BLE001
        return False
    for line in completed.stdout.splitlines():
        name = line.strip()
        if name == feature_id or name.startswith(f"{feature_id}-"):
            return True
    return False


def bin_feature(repo_root: Path, feature_dir: Path,
                feature_id: str | None = None,
                layout=None) -> KanbanColumn:
    """Place a feature into one of the five lifecycle columns.

    Handles two host conventions:

    - Directory-form (spec-kit / openspec): `<feature_dir>/{spec,plan,
      tasks}.md` substructure with review-*.md artifacts.
    - File-form (superpowers): single spec file at
      `<root>/specs/<id>-design.md`, plan at `<root>/plans/<id>.md`.

    `layout` and `feature_id` are optional; when provided the function
    can locate file-form artifacts via the layout adapter.
    """
    fid = feature_id or feature_dir.name
    if _branch_merged_to_main(repo_root, fid):
        return KanbanColumn.MERGED

    # Directory-form check: feature_dir exists and has spec.md substructure.
    if feature_dir.is_dir():
        spec_md = feature_dir / "spec.md"
        plan_md = feature_dir / "plan.md"
        tasks_md = feature_dir / "tasks.md"
        _ = spec_md  # presence of any of these implies dir-form is in use

        if not plan_md.exists():
            return KanbanColumn.SPEC
        if not tasks_md.exists():
            return KanbanColumn.PLAN

        try:
            state = _flow_state.compute_flow_state(feature_dir, repo_root=repo_root)
        except Exception:  # noqa: BLE001
            logger.debug("flow_state failed for %s", feature_dir, exc_info=True)
            return KanbanColumn.TASKS

        rms = list(state.review_milestones)
        if not rms:
            return KanbanColumn.TASKS
        statuses = {rm.status for rm in rms}
        all_done = statuses.issubset(COMPLETE_REVIEW_STATUSES)
        any_done = any(s in COMPLETE_REVIEW_STATUSES for s in statuses)
        if all_done:
            return KanbanColumn.MERGED
        if any_done:
            return KanbanColumn.REVIEW
        return KanbanColumn.TASKS

    # File-form (superpowers): inspect spec / plan files via the layout.
    if layout is not None and hasattr(layout, "spec_path") and hasattr(layout, "plan_path"):
        spec_file = layout.spec_path(fid)
        plan_file = layout.plan_path(fid)
        if not spec_file.exists():
            return KanbanColumn.SPEC  # nothing to show; defensive
        if not plan_file.exists():
            return KanbanColumn.SPEC
        # Plan exists. Without a tasks-layer concept in superpowers,
        # treat plan-present-but-not-merged as Tasks (in-progress).
        return KanbanColumn.TASKS

    # Fallback: feature_dir doesn't exist as a dir and no file-form
    # layout. Place it in Spec so the operator can see it surface.
    return KanbanColumn.SPEC


@dataclass(frozen=True)
class CardData:
    """The data a kanban card needs to render."""
    feature_id: str
    column: KanbanColumn
    branch: str = ""
    worktree_path: str = ""
    worktree_status: str = "(no worktree)"
    review_summary: str = ""


def _resolve_layout(repo_root: Path):
    """Return a HostLayout for `repo_root` — manifest-driven if adopted,
    detection-driven otherwise. Falls back to a bare layout if both fail."""
    from orca.core.host_layout import from_manifest, detect
    from orca.core.host_layout.bare import BareLayout
    try:
        return from_manifest(repo_root)
    except Exception:  # noqa: BLE001 — adoption.toml absent or invalid
        try:
            return detect(repo_root)
        except Exception:  # noqa: BLE001
            return BareLayout(repo_root=repo_root)


def collect_kanban(repo_root: Path) -> dict[KanbanColumn, list[CardData]]:
    """Bin every feature in the host's feature root by lifecycle column.

    Host-agnostic: uses `orca.core.host_layout` to find features so
    spec-kit, superpowers, openspec, and bare repos all work.
    Worktree info attached when available.
    """
    from orca.tui.worktrees import worktree_status  # local to avoid cycle

    result: dict[KanbanColumn, list[CardData]] = {col: [] for col in KanbanColumn}
    layout = _resolve_layout(repo_root)
    for feature_id in layout.list_features():
        feat = layout.resolve_feature_dir(feature_id)
        try:
            col = bin_feature(repo_root, feat, feature_id=feature_id, layout=layout)
        except Exception:  # noqa: BLE001
            logger.debug("bin_feature failed for %s", feat, exc_info=True)
            continue
        try:
            info = worktree_status(repo_root, feature_id)
        except Exception:  # noqa: BLE001
            logger.debug("worktree_status failed for %s", feat, exc_info=True)
            info = None
        result[col].append(CardData(
            feature_id=feature_id,
            column=col,
            branch=info.branch if info else "",
            worktree_path=info.path if info else "",
            worktree_status=info.status if info else "(no worktree)",
        ))
    return result
