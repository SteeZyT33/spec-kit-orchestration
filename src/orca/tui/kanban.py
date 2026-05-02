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


def bin_feature(repo_root: Path, feature_dir: Path) -> KanbanColumn:
    """Place a feature into one of the five lifecycle columns."""
    spec_md = feature_dir / "spec.md"
    plan_md = feature_dir / "plan.md"
    tasks_md = feature_dir / "tasks.md"

    if _branch_merged_to_main(repo_root, feature_dir.name):
        return KanbanColumn.MERGED

    if not plan_md.exists():
        # Spec column also catches feature dirs that have neither file.
        _ = spec_md
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


@dataclass(frozen=True)
class CardData:
    """The data a kanban card needs to render."""
    feature_id: str
    column: KanbanColumn
    branch: str = ""
    worktree_path: str = ""
    worktree_status: str = "(no worktree)"
    review_summary: str = ""


def collect_kanban(repo_root: Path) -> dict[KanbanColumn, list[CardData]]:
    """Bin every feature directory under `specs/` by lifecycle column.

    Worktree info attached when available (Task 1.4 wires it in).
    """
    from orca.tui.worktrees import worktree_status  # local to avoid cycle

    result: dict[KanbanColumn, list[CardData]] = {col: [] for col in KanbanColumn}
    specs_dir = repo_root / "specs"
    if not specs_dir.is_dir():
        return result
    for feat in sorted(specs_dir.iterdir()):
        if not feat.is_dir():
            continue
        try:
            col = bin_feature(repo_root, feat)
        except Exception:  # noqa: BLE001
            logger.debug("bin_feature failed for %s", feat, exc_info=True)
            continue
        try:
            info = worktree_status(repo_root, feat.name)
        except Exception:  # noqa: BLE001
            logger.debug("worktree_status failed for %s", feat, exc_info=True)
            info = None
        result[col].append(CardData(
            feature_id=feat.name,
            column=col,
            branch=info.branch if info else "",
            worktree_path=info.path if info else "",
            worktree_status=info.status if info else "(no worktree)",
        ))
    return result
