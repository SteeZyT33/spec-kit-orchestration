"""Tests for flow_state integration with yolo run status (009 PR C)."""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixture helper: create a feature dir + a yolo run for that feature
# ---------------------------------------------------------------------------


def _make_feature(tmp_path: Path, feature_id: str = "020-example") -> Path:
    feature_dir = tmp_path / "specs" / feature_id
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(f"# {feature_id}\n")
    (feature_dir / "plan.md").write_text("# plan\n")
    (feature_dir / "tasks.md").write_text("# Tasks\n\n- [ ] T001 [US1] first\n")
    return feature_dir


def _start_yolo_run(tmp_path: Path, feature_id: str, **kwargs) -> str:
    from speckit_orca.yolo import start_run

    return start_run(
        repo_root=tmp_path,
        feature_id=feature_id,
        actor="claude",
        branch=feature_id,
        head_commit_sha="abc1234",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# YoloRunSummary dataclass — new in flow_state
# ---------------------------------------------------------------------------


class TestYoloRunSummary:
    def test_yolo_run_summary_fields(self):
        from speckit_orca.flow_state import YoloRunSummary

        summary = YoloRunSummary(
            run_id="run-01JTEST00000000000000000X",
            mode="standalone",
            lane_id=None,
            current_stage="brainstorm",
            outcome="running",
            block_reason=None,
            last_event_timestamp="2026-04-16T12:00:00Z",
        )
        assert summary.run_id.startswith("run-")
        assert summary.mode == "standalone"
        assert summary.outcome == "running"


# ---------------------------------------------------------------------------
# list_yolo_runs_for_feature — find active runs for a feature_id
# ---------------------------------------------------------------------------


class TestListYoloRunsForFeature:
    def test_returns_empty_when_no_runs(self, tmp_path):
        from speckit_orca.flow_state import list_yolo_runs_for_feature

        _make_feature(tmp_path)
        assert list_yolo_runs_for_feature(tmp_path, "020-example") == []

    def test_finds_matching_run(self, tmp_path):
        from speckit_orca.flow_state import list_yolo_runs_for_feature

        _make_feature(tmp_path, "020-example")
        run_id = _start_yolo_run(tmp_path, "020-example")

        summaries = list_yolo_runs_for_feature(tmp_path, "020-example")
        assert len(summaries) == 1
        assert summaries[0].run_id == run_id
        assert summaries[0].current_stage == "brainstorm"
        assert summaries[0].outcome == "running"

    def test_ignores_runs_for_other_features(self, tmp_path):
        from speckit_orca.flow_state import list_yolo_runs_for_feature

        _make_feature(tmp_path, "020-example")
        _make_feature(tmp_path, "021-other")
        _start_yolo_run(tmp_path, "020-example")
        _start_yolo_run(tmp_path, "021-other")

        summaries = list_yolo_runs_for_feature(tmp_path, "020-example")
        assert len(summaries) == 1
        assert summaries[0].current_stage == "brainstorm"

    def test_handles_missing_runs_dir(self, tmp_path):
        from speckit_orca.flow_state import list_yolo_runs_for_feature

        _make_feature(tmp_path, "020-example")
        # No .specify/orca/yolo/runs dir at all
        assert list_yolo_runs_for_feature(tmp_path, "020-example") == []

    def test_skips_runs_with_missing_status_json(self, tmp_path):
        """A run with events but no status.json should still be discoverable."""
        from speckit_orca.flow_state import list_yolo_runs_for_feature

        _make_feature(tmp_path, "020-example")
        run_id = _start_yolo_run(tmp_path, "020-example")

        # Delete the snapshot
        snap = tmp_path / ".specify" / "orca" / "yolo" / "runs" / run_id / "status.json"
        snap.unlink()

        # Should still find the run by replaying events
        summaries = list_yolo_runs_for_feature(tmp_path, "020-example")
        assert len(summaries) == 1
        assert summaries[0].run_id == run_id


# ---------------------------------------------------------------------------
# FlowStateResult now carries yolo_runs list
# ---------------------------------------------------------------------------


class TestFlowStateYoloIntegration:
    def test_flow_state_includes_active_yolo_runs(self, tmp_path):
        from speckit_orca.flow_state import compute_flow_state

        feature_dir = _make_feature(tmp_path, "020-example")
        run_id = _start_yolo_run(tmp_path, "020-example")

        result = compute_flow_state(feature_dir, repo_root=tmp_path)
        assert len(result.yolo_runs) == 1
        assert result.yolo_runs[0].run_id == run_id
        assert result.yolo_runs[0].current_stage == "brainstorm"

    def test_flow_state_empty_yolo_runs_when_no_run(self, tmp_path):
        from speckit_orca.flow_state import compute_flow_state

        feature_dir = _make_feature(tmp_path, "020-example")
        result = compute_flow_state(feature_dir, repo_root=tmp_path)
        assert result.yolo_runs == []

    def test_flow_state_text_output_mentions_active_run(self, tmp_path):
        from speckit_orca.flow_state import compute_flow_state

        feature_dir = _make_feature(tmp_path, "020-example")
        _start_yolo_run(tmp_path, "020-example")

        result = compute_flow_state(feature_dir, repo_root=tmp_path)
        text = result.to_text()
        assert "Active yolo run" in text or "yolo" in text.lower()

    def test_flow_state_json_output_includes_yolo_runs(self, tmp_path):
        from speckit_orca.flow_state import compute_flow_state

        feature_dir = _make_feature(tmp_path, "020-example")
        _start_yolo_run(tmp_path, "020-example")

        result = compute_flow_state(feature_dir, repo_root=tmp_path)
        data = result.to_dict()
        assert "yolo_runs" in data
        assert len(data["yolo_runs"]) == 1
        assert data["yolo_runs"][0]["current_stage"] == "brainstorm"

    def test_canceled_yolo_run_reported_as_terminal(self, tmp_path):
        from speckit_orca.flow_state import compute_flow_state
        from speckit_orca.yolo import cancel_run

        feature_dir = _make_feature(tmp_path, "020-example")
        run_id = _start_yolo_run(tmp_path, "020-example")
        cancel_run(tmp_path, run_id, actor="claude", head_commit_sha="abc1234")

        result = compute_flow_state(feature_dir, repo_root=tmp_path)
        assert result.yolo_runs[0].outcome == "canceled"
