"""Tests for the kanban lifecycle binning."""
from __future__ import annotations

from pathlib import Path


def _spec_only(root: Path, fid: str) -> Path:
    d = root / "specs" / fid
    d.mkdir(parents=True)
    (d / "spec.md").write_text("# spec\n")
    return d


def test_bin_feature_spec_when_only_spec(tmp_path: Path):
    from orca.tui.kanban import KanbanColumn, bin_feature

    feat = _spec_only(tmp_path, "001-foo")
    assert bin_feature(tmp_path, feat) == KanbanColumn.SPEC


def test_bin_feature_plan_when_plan_exists(tmp_path: Path):
    from orca.tui.kanban import KanbanColumn, bin_feature

    feat = _spec_only(tmp_path, "001-foo")
    (feat / "plan.md").write_text("# plan\n")
    assert bin_feature(tmp_path, feat) == KanbanColumn.PLAN


def test_bin_feature_tasks_when_tasks_exists(tmp_path: Path):
    from orca.tui.kanban import KanbanColumn, bin_feature

    feat = _spec_only(tmp_path, "001-foo")
    (feat / "plan.md").write_text("# plan\n")
    (feat / "tasks.md").write_text("# tasks\n")
    assert bin_feature(tmp_path, feat) == KanbanColumn.TASKS
