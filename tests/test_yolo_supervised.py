"""Tests for yolo supervised mode — matriarch dual-write and lane reconciliation.

Scope: 009 PR D (from runtime-plan §13).
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _init_repo(tmp_path: Path) -> None:
    """Give tmp_path a minimal .specify/ so matriarch can locate repo root."""
    (tmp_path / ".specify").mkdir(exist_ok=True)


def _setup_supervised_run(tmp_path: Path, feature_id: str = "020-example"):
    """Create a feature dir, register a matriarch lane, start a supervised yolo run.

    Returns (run_id, lane_id).
    """
    from speckit_orca.matriarch import register_lane
    from speckit_orca.yolo import start_run

    _init_repo(tmp_path)

    # Feature dir needed for matriarch lane registration
    feature_dir = tmp_path / "specs" / feature_id
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(f"# {feature_id}\n")

    # Register the matriarch lane (lane_id defaults to feature_id per 010 FR-025)
    lane = register_lane(
        spec_id=feature_id,
        repo_root=tmp_path,
        branch=feature_id,
        owner_type="agent",
        owner_id="claude",
        title="test lane",
    )

    # Start yolo run in supervised mode
    run_id = start_run(
        repo_root=tmp_path,
        feature_id=feature_id,
        actor="claude",
        branch=feature_id,
        head_commit_sha="abc1234",
        mode="matriarch-supervised",
        lane_id=lane.spec_id,
    )
    return run_id, lane.spec_id


# ---------------------------------------------------------------------------
# Dual-write: yolo events in supervised mode mirror to matriarch mailbox
# ---------------------------------------------------------------------------


class TestDualWrite:
    def test_supervised_start_run_emits_startup_ack(self, tmp_path):
        """A supervised run_started event is emitted as a startup ACK on the
        reports queue per 010 lane-agent.md §Startup Acknowledgment, with
        sender=lane_agent:<lane_id> (not yolo:<run_id>)."""
        from speckit_orca.matriarch import MatriarchPaths

        run_id, lane_id = _setup_supervised_run(tmp_path)
        paths = MatriarchPaths(tmp_path)
        reports_path = paths.reports_path(lane_id)
        assert reports_path.exists(), "reports queue should exist for supervised lane"

        import json

        lines = [
            json.loads(ln) for ln in reports_path.read_text().splitlines() if ln
        ]
        # Should find an ack with lane_agent sender
        ack_events = [
            e for e in lines
            if e.get("type") == "ack"
            and e.get("sender") == f"lane_agent:{lane_id}"
        ]
        assert len(ack_events) >= 1
        payload = ack_events[0]["payload"]
        # Traceability: run_id referenced via context_refs
        refs = payload.get("context_refs", [])
        assert any(f"yolo:{run_id}" in r for r in refs)

    def test_standalone_mode_does_not_mirror(self, tmp_path):
        """A standalone run should NOT write to any matriarch mailbox."""
        from speckit_orca.yolo import start_run

        # No matriarch lane, no supervision
        feature_id = "021-standalone"
        feature_dir = tmp_path / "specs" / feature_id
        feature_dir.mkdir(parents=True)
        (feature_dir / "spec.md").write_text(f"# {feature_id}\n")

        start_run(
            repo_root=tmp_path,
            feature_id=feature_id,
            actor="claude",
            branch=feature_id,
            head_commit_sha="abc1234",
            mode="standalone",
        )

        # No matriarch lane was registered; matriarch dir should not exist
        matriarch_dir = tmp_path / ".specify" / "orca" / "matriarch"
        assert not matriarch_dir.exists(), "standalone mode should not touch matriarch paths"

    def test_dual_write_maps_block_to_blocker(self, tmp_path):
        """yolo.block event should appear as matriarch 'blocker' event type."""
        from speckit_orca.matriarch import list_mailbox_events
        from speckit_orca.yolo import next_run

        run_id, lane_id = _setup_supervised_run(tmp_path)

        # Emit a block via next_run(blocked)
        next_run(
            tmp_path, run_id,
            result="blocked",
            reason="missing dependency X",
            head_commit_sha="abc1234",
        )

        events = list_mailbox_events(lane_id, repo_root=tmp_path)
        inbound = events["inbound"]
        block_events = [e for e in inbound if e.get("type") == "blocker"]
        assert len(block_events) == 1
        assert block_events[0]["sender"] == f"lane_agent:{lane_id}"
        payload = block_events[0]["payload"]
        assert isinstance(payload, dict)
        assert payload.get("yolo_event_type") == "block"
        assert "missing dependency X" in (payload.get("reason") or "")

    def test_dual_write_maps_decision_required_to_question(self, tmp_path):
        """yolo decision_required → matriarch 'question'."""
        from speckit_orca.matriarch import list_mailbox_events
        from speckit_orca.yolo import (
            Event, EventType, append_event, generate_ulid,
        )

        run_id, lane_id = _setup_supervised_run(tmp_path)

        # Emit a decision_required event directly
        event = Event(
            event_id=generate_ulid(),
            run_id=run_id,
            event_type=EventType.DECISION_REQUIRED,
            timestamp="2026-04-16T13:00:00Z",
            lamport_clock=99,
            actor="claude",
            feature_id="020-example",
            lane_id=lane_id,
            branch="020-example",
            head_commit_sha="abc1234",
            from_stage="clarify",
            to_stage="clarify",
            reason="clarification needed",
            evidence=None,
        )
        append_event(tmp_path, run_id, event)

        events = list_mailbox_events(lane_id, repo_root=tmp_path)
        inbound = events["inbound"]
        question_events = [e for e in inbound if e.get("type") == "question"]
        assert len(question_events) == 1

    def test_mirror_failure_sets_matriarch_sync_failed_flag(self, tmp_path):
        """When the mirror write fails, matriarch_sync_failed must flip
        so a supervised run with zero matriarch visibility is NOT
        indistinguishable from a healthy one (codex BLOCKER 1)."""
        from speckit_orca.matriarch import MatriarchPaths
        from speckit_orca.yolo import next_run, run_status

        run_id, lane_id = _setup_supervised_run(tmp_path)

        # Break the lane by deleting its record, so subsequent mirror writes fail
        paths = MatriarchPaths(tmp_path)
        paths.lane_path(lane_id).unlink()

        # Emit an event that would mirror — should not raise, but should
        # set the sync-failed marker
        next_run(
            tmp_path, run_id,
            result="blocked", reason="check-sync", head_commit_sha="abc1234",
        )

        state = run_status(tmp_path, run_id)
        assert state.matriarch_sync_failed is True, (
            "A supervised run whose mirror write failed MUST surface "
            "matriarch_sync_failed=True so operators see the lost visibility."
        )

    def test_decision_required_at_review_stage_maps_to_approval_needed(self, tmp_path):
        """DECISION_REQUIRED at a review gate should be 'approval_needed'
        (not just 'question'). The two are distinct in 010."""
        from speckit_orca.matriarch import list_mailbox_events
        from speckit_orca.yolo import (
            Event, EventType, append_event, generate_ulid,
        )

        run_id, lane_id = _setup_supervised_run(tmp_path)

        event = Event(
            event_id=generate_ulid(),
            run_id=run_id,
            event_type=EventType.DECISION_REQUIRED,
            timestamp="2026-04-16T13:00:00Z",
            lamport_clock=99,
            actor="claude",
            feature_id="020-example",
            lane_id=lane_id,
            branch="020-example",
            head_commit_sha="abc1234",
            from_stage="review-code",
            to_stage="review-code",
            reason="cross-pass needed",
            evidence=None,
        )
        append_event(tmp_path, run_id, event)

        events = list_mailbox_events(lane_id, repo_root=tmp_path)
        approvals = [e for e in events["inbound"] if e.get("type") == "approval_needed"]
        assert len(approvals) == 1

    def test_dual_write_graceful_when_lane_not_registered(self, tmp_path):
        """If the lane_id doesn't correspond to a registered matriarch lane,
        yolo should still function — mirroring is best-effort, not required."""
        from speckit_orca.yolo import Event, EventType, append_event, generate_ulid

        # Don't register a lane. Emit an event with lane_id set anyway.
        feature_dir = tmp_path / "specs" / "020-example"
        feature_dir.mkdir(parents=True)
        (feature_dir / "spec.md").write_text("# 020-example\n")

        event = Event(
            event_id=generate_ulid(),
            run_id="run-no-lane",
            event_type=EventType.BLOCK,
            timestamp="2026-04-16T13:00:00Z",
            lamport_clock=1,
            actor="claude",
            feature_id="020-example",
            lane_id="020-example",  # lane not registered
            branch="020-example",
            head_commit_sha="abc1234",
            from_stage=None,
            to_stage=None,
            reason="unreachable lane",
            evidence=None,
        )
        # Should not raise
        append_event(tmp_path, "run-no-lane", event)

        # The yolo event log still has the event
        from speckit_orca.yolo import load_events

        events = load_events(tmp_path, "run-no-lane")
        assert len(events) == 1


# ---------------------------------------------------------------------------
# Resume reconciliation: supervised resume consults lane registry
# ---------------------------------------------------------------------------


class TestResumeReconciliation:
    def test_supervised_resume_succeeds_when_lane_matches(self, tmp_path):
        """Normal supervised resume — lane owner unchanged — works."""
        from speckit_orca.yolo import resume_run

        run_id, _ = _setup_supervised_run(tmp_path)
        decision = resume_run(tmp_path, run_id)
        assert decision.kind == "step"

    def test_supervised_resume_raises_if_lane_reassigned(self, tmp_path):
        """If matriarch has reassigned the lane to a different agent since
        the run started, resume_run should raise ValueError (per FR-018
        ownership reconciliation)."""
        from speckit_orca.matriarch import assign_lane
        from speckit_orca.yolo import resume_run

        run_id, lane_id = _setup_supervised_run(tmp_path)

        # Reassign the lane to a different agent
        assign_lane(
            lane_id,
            repo_root=tmp_path,
            owner_type="agent",
            owner_id="codex",  # different from "claude"
        )

        # Resume should refuse — the run started under claude but the lane
        # is now owned by codex. Operator must explicitly recover.
        with pytest.raises(ValueError, match=r"(?i)(lane|ownership|reassigned)"):
            resume_run(tmp_path, run_id)

    def test_supervised_resume_standalone_mode_ignores_lane_check(self, tmp_path):
        """Standalone-mode runs don't consult the lane registry."""
        from speckit_orca.yolo import resume_run, start_run

        feature_dir = tmp_path / "specs" / "020-example"
        feature_dir.mkdir(parents=True)
        (feature_dir / "spec.md").write_text("# 020-example\n")

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
            mode="standalone",
        )

        decision = resume_run(tmp_path, run_id)
        assert decision.kind == "step"

    def test_recover_run_requires_confirm_flag_when_lane_changed(self, tmp_path):
        """recover_run must require explicit confirm_reassignment=True + reason
        when the matriarch lane state has changed. No silent bypass."""
        from speckit_orca.matriarch import assign_lane
        from speckit_orca.yolo import recover_run

        run_id, lane_id = _setup_supervised_run(tmp_path)
        assign_lane(
            lane_id,
            repo_root=tmp_path,
            owner_type="agent",
            owner_id="codex",
        )

        # Without confirm flag → refuse
        with pytest.raises(ValueError, match=r"(?i)confirm_reassignment"):
            recover_run(tmp_path, run_id)

        # With confirm but no reason → refuse
        with pytest.raises(ValueError, match=r"(?i)reason"):
            recover_run(tmp_path, run_id, confirm_reassignment=True)

        # With both → succeed
        decision = recover_run(
            tmp_path, run_id,
            confirm_reassignment=True,
            reason="operator inspected lane; continuing under new ownership",
        )
        assert decision.kind in {"step", "decision_required", "blocked", "terminal"}

    def test_recover_run_works_without_confirm_when_lane_unchanged(self, tmp_path):
        """If the lane hasn't changed, confirm_reassignment is not required."""
        from speckit_orca.yolo import recover_run

        run_id, _ = _setup_supervised_run(tmp_path)
        decision = recover_run(tmp_path, run_id)
        assert decision.kind in {"step", "decision_required", "blocked", "terminal"}

    def test_resume_raises_on_unregistered_lane(self, tmp_path):
        """A supervised run whose lane has been deleted should NOT resume
        silently — this is the codex BLOCKER 2 'fail-closed on missing lane' case."""
        from speckit_orca.matriarch import MatriarchPaths
        from speckit_orca.yolo import resume_run

        run_id, lane_id = _setup_supervised_run(tmp_path)

        # Simulate lane removal: delete the lane record file that _load_lane reads.
        paths = MatriarchPaths(tmp_path)
        lane_file = paths.lane_path(lane_id)
        assert lane_file.exists()
        lane_file.unlink()

        with pytest.raises(ValueError, match=r"(?i)(registry|unknown|unregistered)"):
            resume_run(tmp_path, run_id)
