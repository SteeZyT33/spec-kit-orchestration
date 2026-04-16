"""Tests for the orca-yolo single-lane execution runtime.

Follows TDD: every test written before the corresponding implementation.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _event(clock: int, etype: str, **kw):
    """Shorthand event builder for reducer/decision tests."""
    from speckit_orca.yolo import Event, EventType

    defaults = {
        "event_id": f"01JTEST{clock:020d}",
        "run_id": "run-001",
        "event_type": EventType(etype),
        "timestamp": f"2026-04-16T12:{clock:02d}:00Z",
        "lamport_clock": clock,
        "actor": "claude",
        "feature_id": "020-example",
        "lane_id": None,
        "branch": "020-example",
        "head_commit_sha": "abc1234",
        "from_stage": None,
        "to_stage": None,
        "reason": None,
        "evidence": None,
    }
    defaults.update(kw)
    return Event(**defaults)

# ---------------------------------------------------------------------------
# Phase 2: Event System
# ---------------------------------------------------------------------------


class TestCrossModuleStageContract:
    """yolo's STAGES must be a subset of context_handoffs' canonical stages
    so handoffs created during a yolo run are not rejected as unknown.

    This closes the divergence Copilot flagged (round 4 #21) where yolo's
    new vocabulary (clarify, review-spec, review-code, pr-ready, pr-create,
    review-pr) was absent from 007's CANONICAL_STAGE_IDS.
    """

    def test_yolo_stages_all_recognized_by_context_handoffs(self):
        from speckit_orca.context_handoffs import CANONICAL_STAGE_IDS
        from speckit_orca.yolo import STAGES

        missing = set(STAGES) - set(CANONICAL_STAGE_IDS)
        assert missing == set(), (
            f"yolo STAGES not in context_handoffs CANONICAL_STAGE_IDS: "
            f"{sorted(missing)}. Divergence causes handoff creation to fail."
        )


class TestEventType:
    """EventType enum covers all 12 event types from runtime-plan section 6."""

    def test_all_event_types_exist(self):
        from speckit_orca.yolo import EventType

        expected = {
            "run_started",
            "stage_entered",
            "stage_completed",
            "stage_failed",
            "pause",
            "resume",
            "block",
            "unblock",
            "decision_required",
            "cross_pass_requested",
            "cross_pass_completed",
            "terminal",
        }
        actual = {e.value for e in EventType}
        assert actual == expected

    def test_event_type_from_string(self):
        from speckit_orca.yolo import EventType

        assert EventType("run_started") == EventType.RUN_STARTED
        assert EventType("terminal") == EventType.TERMINAL

    def test_event_type_invalid_raises(self):
        from speckit_orca.yolo import EventType

        with pytest.raises(ValueError):
            EventType("nonexistent_type")


class TestEvent:
    """Event dataclass: required fields, validation, JSON round-trip."""

    def _make_event(self, **overrides):
        from speckit_orca.yolo import Event, EventType

        defaults = {
            "event_id": "01JTEST000000000000000000A",
            "run_id": "run-001",
            "event_type": EventType.RUN_STARTED,
            "timestamp": "2026-04-16T12:00:00Z",
            "lamport_clock": 1,
            "actor": "claude",
            "feature_id": "009-orca-yolo",
            "lane_id": None,
            "branch": "009-orca-yolo",
            "head_commit_sha": "abc1234",
            "from_stage": None,
            "to_stage": "brainstorm",
            "reason": None,
            "evidence": None,
        }
        defaults.update(overrides)
        return Event(**defaults)

    def test_event_creation(self):
        event = self._make_event()
        assert event.event_id == "01JTEST000000000000000000A"
        assert event.run_id == "run-001"
        assert event.actor == "claude"

    def test_event_to_json_roundtrip(self):
        from speckit_orca.yolo import Event

        event = self._make_event()
        json_str = event.to_json()
        parsed = json.loads(json_str)
        assert parsed["event_id"] == "01JTEST000000000000000000A"
        assert parsed["event_type"] == "run_started"
        assert parsed["lamport_clock"] == 1

        restored = Event.from_json(json_str)
        assert restored.event_id == event.event_id
        assert restored.event_type == event.event_type
        assert restored.lamport_clock == event.lamport_clock
        assert restored.to_stage == event.to_stage

    def test_event_json_preserves_none_fields(self):
        event = self._make_event(lane_id=None, reason=None, evidence=None)
        json_str = event.to_json()
        parsed = json.loads(json_str)
        assert parsed["lane_id"] is None
        assert parsed["reason"] is None
        assert parsed["evidence"] is None

    def test_event_json_preserves_evidence_list(self):
        event = self._make_event(evidence=["review-code.md", "test-output.txt"])
        json_str = event.to_json()
        parsed = json.loads(json_str)
        assert parsed["evidence"] == ["review-code.md", "test-output.txt"]

    def test_event_timestamp_must_be_utc_z(self):
        """Per 010 event-envelope contract: Z offset required."""
        from speckit_orca.yolo import Event

        event = self._make_event(timestamp="2026-04-16T12:00:00Z")
        assert event.timestamp.endswith("Z")

        # Non-Z timestamps should be rejected
        with pytest.raises((ValueError, TypeError)):
            self._make_event(timestamp="2026-04-16T12:00:00+05:00")


# ---------------------------------------------------------------------------
# Phase 2: ULID Generator
# ---------------------------------------------------------------------------


class TestULID:
    """Inline ULID generator: monotonic, 26-char, lex-sortable."""

    def test_ulid_is_26_chars(self):
        from speckit_orca.yolo import generate_ulid

        ulid = generate_ulid()
        assert len(ulid) == 26

    def test_ulid_is_uppercase_crockford_base32(self):
        from speckit_orca.yolo import generate_ulid

        ulid = generate_ulid()
        valid_chars = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
        assert all(c in valid_chars for c in ulid), f"Invalid chars in {ulid}"

    def test_ulid_monotonic_ordering(self):
        from speckit_orca.yolo import generate_ulid

        ulids = [generate_ulid() for _ in range(100)]
        assert ulids == sorted(ulids), "ULIDs must be lex-sortable"

    def test_ulid_uniqueness(self):
        from speckit_orca.yolo import generate_ulid

        ulids = [generate_ulid() for _ in range(1000)]
        assert len(set(ulids)) == 1000, "ULIDs must be unique"


# ---------------------------------------------------------------------------
# Phase 2: Event Log I/O
# ---------------------------------------------------------------------------


class TestEventLogIO:
    """Event log: append-only JSONL, round-trip, deduplication."""

    def _make_event(self, **overrides):
        from speckit_orca.yolo import Event, EventType

        defaults = {
            "event_id": "01JTEST000000000000000000A",
            "run_id": "run-001",
            "event_type": EventType.RUN_STARTED,
            "timestamp": "2026-04-16T12:00:00Z",
            "lamport_clock": 1,
            "actor": "claude",
            "feature_id": "009-orca-yolo",
            "lane_id": None,
            "branch": "009-orca-yolo",
            "head_commit_sha": "abc1234",
            "from_stage": None,
            "to_stage": "brainstorm",
            "reason": None,
            "evidence": None,
        }
        defaults.update(overrides)
        return Event(**defaults)

    def test_append_and_load_roundtrip(self, tmp_path):
        from speckit_orca.yolo import append_event, load_events

        run_id = "run-001"
        event = self._make_event()

        append_event(tmp_path, run_id, event)
        events = load_events(tmp_path, run_id)

        assert len(events) == 1
        assert events[0].event_id == event.event_id
        assert events[0].event_type == event.event_type

    def test_append_multiple_events(self, tmp_path):
        from speckit_orca.yolo import EventType, append_event, load_events

        run_id = "run-001"
        e1 = self._make_event(
            event_id="01JTEST000000000000000000A",
            lamport_clock=1,
        )
        e2 = self._make_event(
            event_id="01JTEST000000000000000000B",
            event_type=EventType.STAGE_ENTERED,
            lamport_clock=2,
            from_stage="brainstorm",
            to_stage="specify",
        )

        append_event(tmp_path, run_id, e1)
        append_event(tmp_path, run_id, e2)
        events = load_events(tmp_path, run_id)

        assert len(events) == 2
        assert events[0].lamport_clock == 1
        assert events[1].lamport_clock == 2

    def test_load_deduplicates_by_event_id(self, tmp_path):
        from speckit_orca.yolo import append_event, load_events

        run_id = "run-001"
        event = self._make_event()

        # Write same event twice (simulating double-commit bug)
        append_event(tmp_path, run_id, event)
        append_event(tmp_path, run_id, event)
        events = load_events(tmp_path, run_id)

        assert len(events) == 1

    def test_load_returns_empty_for_missing_run(self, tmp_path):
        from speckit_orca.yolo import load_events

        events = load_events(tmp_path, "nonexistent-run")
        assert events == []

    def test_events_sorted_by_lamport_timestamp_id(self, tmp_path):
        """Events sorted by (lamport_clock, timestamp, event_id)."""
        from speckit_orca.yolo import EventType, append_event, load_events

        run_id = "run-001"
        # Write out of order
        e2 = self._make_event(
            event_id="01JTEST000000000000000000B",
            lamport_clock=2,
            timestamp="2026-04-16T12:01:00Z",
        )
        e1 = self._make_event(
            event_id="01JTEST000000000000000000A",
            lamport_clock=1,
            timestamp="2026-04-16T12:00:00Z",
        )

        append_event(tmp_path, run_id, e2)
        append_event(tmp_path, run_id, e1)
        events = load_events(tmp_path, run_id)

        assert events[0].lamport_clock == 1
        assert events[1].lamport_clock == 2

    def test_event_log_file_location(self, tmp_path):
        from speckit_orca.yolo import append_event

        run_id = "run-001"
        event = self._make_event()
        append_event(tmp_path, run_id, event)

        expected_path = tmp_path / ".specify" / "orca" / "yolo" / "runs" / run_id / "events.jsonl"
        assert expected_path.exists()
        lines = expected_path.read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["event_id"] == event.event_id


# ---------------------------------------------------------------------------
# Phase 3: State Reducer
# ---------------------------------------------------------------------------

# The canonical stage order for transition validation
STAGE_ORDER = [
    "brainstorm", "specify", "clarify", "review-spec",
    "plan", "tasks", "assign", "implement",
    "review-code", "pr-ready", "pr-create", "review-pr",
]


class TestRunState:
    """RunState dataclass matches runtime-plan section 7."""

    def test_runstate_fields(self):
        from speckit_orca.yolo import RunState

        state = RunState(
            run_id="run-001",
            feature_id="020-example",
            mode="standalone",
            lane_id=None,
            current_stage="brainstorm",
            outcome="running",
            block_reason=None,
            last_event_id="01JTEST1",
            last_event_timestamp="2026-04-16T12:00:00Z",
            branch="020-example",
            head_commit_sha_at_last_event="abc1234",
            deployment_kind=None,
            review_spec_status=None,
            review_code_status=None,
            review_pr_status=None,
            mailbox_path=None,
            last_mailbox_event_id=None,
            retry_counts={},
        )
        assert state.run_id == "run-001"
        assert state.mode == "standalone"
        assert state.outcome == "running"
        assert state.deployment_kind is None
        assert state.review_spec_status is None


class TestReducer:
    """reduce(events) → RunState: deterministic, idempotent, correct."""

    def test_reduce_run_started(self):
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
        ]
        state = reduce(events)
        assert state.run_id == "run-001"
        assert state.feature_id == "020-example"
        assert state.mode == "standalone"
        assert state.current_stage == "brainstorm"
        assert state.outcome == "running"

    def test_reduce_stage_progression(self):
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
            _event(2, "stage_completed", from_stage="brainstorm", to_stage="brainstorm"),
            _event(3, "stage_entered", from_stage="brainstorm", to_stage="specify"),
        ]
        state = reduce(events)
        assert state.current_stage == "specify"
        assert state.outcome == "running"

    def test_reduce_full_happy_path(self):
        """Walk through brainstorm → ... → pr-ready."""
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
            _event(2, "stage_completed", from_stage="brainstorm", to_stage="brainstorm"),
            _event(3, "stage_entered", from_stage="brainstorm", to_stage="specify"),
            _event(4, "stage_completed", from_stage="specify", to_stage="specify"),
            _event(5, "stage_entered", from_stage="specify", to_stage="clarify"),
            _event(6, "stage_completed", from_stage="clarify", to_stage="clarify"),
            _event(7, "stage_entered", from_stage="clarify", to_stage="review-spec"),
            _event(8, "stage_completed", from_stage="review-spec", to_stage="review-spec"),
            _event(9, "stage_entered", from_stage="review-spec", to_stage="plan"),
            _event(10, "stage_completed", from_stage="plan", to_stage="plan"),
            _event(11, "stage_entered", from_stage="plan", to_stage="tasks"),
            _event(12, "stage_completed", from_stage="tasks", to_stage="tasks"),
            _event(13, "stage_entered", from_stage="tasks", to_stage="implement"),
            _event(14, "stage_completed", from_stage="implement", to_stage="implement"),
            _event(15, "stage_entered", from_stage="implement", to_stage="review-code"),
            _event(16, "stage_completed", from_stage="review-code", to_stage="review-code"),
            _event(17, "stage_entered", from_stage="review-code", to_stage="pr-ready"),
            _event(18, "terminal"),
        ]
        state = reduce(events)
        assert state.current_stage == "pr-ready"
        assert state.outcome == "completed"

    def test_reduce_determinism(self):
        """Same events always produce same state."""
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
            _event(2, "stage_completed", from_stage="brainstorm", to_stage="brainstorm"),
            _event(3, "stage_entered", from_stage="brainstorm", to_stage="specify"),
        ]
        state1 = reduce(events)
        state2 = reduce(events)
        assert state1 == state2

    def test_reduce_idempotent_duplicate_events(self):
        """Duplicate event_ids have no effect."""
        from speckit_orca.yolo import reduce

        e1 = _event(1, "run_started", to_stage="brainstorm")
        events_with_dup = [e1, e1, e1]
        events_without_dup = [e1]
        assert reduce(events_with_dup) == reduce(events_without_dup)

    def test_reduce_pause_and_resume(self):
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
            _event(2, "pause", reason="waiting for human input"),
        ]
        state = reduce(events)
        assert state.outcome == "paused"
        assert state.block_reason == "waiting for human input"

        events.append(_event(3, "resume"))
        state = reduce(events)
        assert state.outcome == "running"
        assert state.block_reason is None

    def test_reduce_block_and_unblock(self):
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
            _event(2, "block", reason="missing dependency"),
        ]
        state = reduce(events)
        assert state.outcome == "blocked"
        assert state.block_reason == "missing dependency"

        events.append(_event(3, "unblock", reason="dependency resolved"))
        state = reduce(events)
        assert state.outcome == "running"
        assert state.block_reason is None

    def test_reduce_stage_failed(self):
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="implement"),
            _event(2, "stage_failed", from_stage="implement", reason="tests failing"),
        ]
        state = reduce(events)
        assert state.outcome == "failed"
        assert state.block_reason == "tests failing"

    def test_reduce_terminal_prevents_further_events(self):
        """After terminal, reducer ignores subsequent events."""
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
            _event(2, "terminal"),
            _event(3, "stage_entered", from_stage="brainstorm", to_stage="specify"),
        ]
        state = reduce(events)
        assert state.outcome == "completed"
        # Stage should NOT have advanced past terminal
        assert state.current_stage == "brainstorm"

    def test_reduce_decision_required(self):
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="specify"),
            _event(2, "decision_required", reason="clarification needed"),
        ]
        state = reduce(events)
        assert state.outcome == "paused"
        assert state.block_reason == "clarification needed"

    def test_reduce_review_spec_tracking(self):
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="review-spec"),
            _event(2, "cross_pass_requested", from_stage="review-spec"),
        ]
        state = reduce(events)
        assert state.review_spec_status == "in_progress"

        events.append(_event(3, "cross_pass_completed", from_stage="review-spec"))
        state = reduce(events)
        assert state.review_spec_status == "complete"

    def test_reduce_review_code_tracking(self):
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="review-code"),
            _event(2, "cross_pass_requested", from_stage="review-code"),
            _event(3, "cross_pass_completed", from_stage="review-code"),
        ]
        state = reduce(events)
        assert state.review_code_status == "complete"

    def test_reduce_review_pr_tracking(self):
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="review-pr"),
            _event(2, "cross_pass_requested", from_stage="review-pr"),
        ]
        state = reduce(events)
        assert state.review_pr_status == "in_progress"

        events.append(_event(3, "cross_pass_completed", from_stage="review-pr"))
        state = reduce(events)
        assert state.review_pr_status == "complete"

    def test_reduce_tracks_last_event(self):
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
            _event(2, "stage_completed", from_stage="brainstorm", to_stage="brainstorm"),
        ]
        state = reduce(events)
        assert state.last_event_id == f"01JTEST{2:020d}"
        assert state.last_event_timestamp == "2026-04-16T12:02:00Z"

    def test_reduce_tracks_head_commit(self):
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm", head_commit_sha="aaa"),
            _event(2, "stage_completed", from_stage="brainstorm", to_stage="brainstorm", head_commit_sha="bbb"),
        ]
        state = reduce(events)
        assert state.head_commit_sha_at_last_event == "bbb"

    def test_reduce_empty_events_raises(self):
        from speckit_orca.yolo import reduce

        with pytest.raises(ValueError, match=r"[Nn]o events"):
            reduce([])

    def test_reduce_matriarch_mode_from_started_event(self):
        """Supervised mode detected from run_started event metadata."""
        from speckit_orca.yolo import reduce

        events = [
            _event(
                1, "run_started", to_stage="brainstorm",
                lane_id="020-example",
            ),
        ]
        state = reduce(events)
        assert state.mode == "matriarch-supervised"
        assert state.lane_id == "020-example"


# ---------------------------------------------------------------------------
# Phase 4: Decision Logic
# ---------------------------------------------------------------------------


class TestDecision:
    """Decision dataclass and next_decision() pure function."""

    def test_decision_fields(self):
        from speckit_orca.yolo import Decision

        d = Decision(
            kind="step",
            next_stage="specify",
            prompt_text="Proceed to specify",
            machine_payload={"stage": "specify"},
            requires_confirmation=False,
        )
        assert d.kind == "step"
        assert d.next_stage == "specify"

    def test_terminal_outcome_yields_terminal_decision(self):
        from speckit_orca.yolo import next_decision, reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
            _event(2, "terminal"),
        ]
        state = reduce(events)
        decision = next_decision(state)
        assert decision.kind == "terminal"

    def test_blocked_outcome_yields_blocked_decision(self):
        from speckit_orca.yolo import next_decision, reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
            _event(2, "block", reason="missing dep"),
        ]
        state = reduce(events)
        decision = next_decision(state)
        assert decision.kind == "blocked"
        assert "missing dep" in decision.prompt_text

    def test_paused_outcome_yields_decision_required(self):
        from speckit_orca.yolo import next_decision, reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
            _event(2, "pause", reason="operator pause"),
        ]
        state = reduce(events)
        decision = next_decision(state)
        assert decision.kind == "decision_required"

    def test_step_at_brainstorm_says_execute_brainstorm(self):
        """After start_run, next_decision says execute the CURRENT stage.

        The caller is at brainstorm and should execute it before advancing.
        """
        from speckit_orca.yolo import next_decision, reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
        ]
        state = reduce(events)
        decision = next_decision(state)
        assert decision.kind == "step"
        assert decision.next_stage == "brainstorm"

    def test_step_at_specify_says_execute_specify(self):
        from speckit_orca.yolo import next_decision, reduce

        events = [
            _event(1, "run_started", to_stage="specify"),
        ]
        state = reduce(events)
        decision = next_decision(state)
        assert decision.kind == "step"
        assert decision.next_stage == "specify"

    def test_step_at_clarify_says_execute_clarify(self):
        from speckit_orca.yolo import next_decision, reduce

        events = [
            _event(1, "run_started", to_stage="clarify"),
        ]
        state = reduce(events)
        decision = next_decision(state)
        assert decision.kind == "step"
        assert decision.next_stage == "clarify"

    def test_step_at_plan_allowed_when_review_spec_complete(self):
        """To execute plan, review_spec_status must be complete."""
        from speckit_orca.yolo import next_decision, reduce

        events = [
            _event(1, "run_started", to_stage="review-spec"),
            _event(2, "cross_pass_requested", from_stage="review-spec"),
            _event(3, "cross_pass_completed", from_stage="review-spec"),
            _event(4, "stage_completed", from_stage="review-spec", to_stage="review-spec"),
            _event(5, "stage_entered", from_stage="review-spec", to_stage="plan"),
        ]
        state = reduce(events)
        decision = next_decision(state)
        assert decision.kind == "step"
        assert decision.next_stage == "plan"

    def test_step_blocked_at_plan_if_review_spec_not_complete(self):
        """Executing plan is blocked until review-spec cross-pass completes."""
        from speckit_orca.yolo import next_decision, reduce

        events = [
            _event(1, "run_started", to_stage="review-spec"),
            _event(2, "stage_completed", from_stage="review-spec", to_stage="review-spec"),
            _event(3, "stage_entered", from_stage="review-spec", to_stage="plan"),
        ]
        state = reduce(events)
        decision = next_decision(state)
        assert decision.kind == "decision_required"
        assert "review_spec_status" in decision.prompt_text

    def test_step_at_implement_from_tasks(self):
        """Assign is optional — next_run(success) on tasks advances to implement."""
        from speckit_orca.yolo import next_decision, reduce

        events = [
            _event(1, "run_started", to_stage="tasks"),
            _event(2, "stage_completed", from_stage="tasks", to_stage="tasks"),
            _event(3, "stage_entered", from_stage="tasks", to_stage="implement"),
        ]
        state = reduce(events)
        decision = next_decision(state)
        assert decision.kind == "step"
        assert decision.next_stage == "implement"

    def test_step_at_pr_ready_blocked_if_review_code_not_complete(self):
        """Executing pr-ready is blocked until review-code cross-pass completes."""
        from speckit_orca.yolo import next_decision, reduce

        events = [
            _event(1, "run_started", to_stage="review-code"),
            _event(2, "stage_completed", from_stage="review-code", to_stage="review-code"),
            _event(3, "stage_entered", from_stage="review-code", to_stage="pr-ready"),
        ]
        state = reduce(events)
        decision = next_decision(state)
        assert decision.kind == "decision_required"
        assert "review_code_status" in decision.prompt_text

    def test_failed_outcome_yields_blocked(self):
        from speckit_orca.yolo import next_decision, reduce

        events = [
            _event(1, "run_started", to_stage="implement"),
            _event(2, "stage_failed", from_stage="implement", reason="tests broke"),
        ]
        state = reduce(events)
        decision = next_decision(state)
        assert decision.kind == "blocked"

    def test_running_with_canceled_outcome_yields_terminal(self):
        """A canceled run cannot be resumed as if running."""
        from speckit_orca.yolo import next_decision, reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
            _event(2, "terminal", reason="canceled by operator"),
        ]
        state = reduce(events)
        assert state.outcome == "canceled"
        decision = next_decision(state)
        assert decision.kind == "terminal"
        assert "canceled" in decision.prompt_text.lower()


# ---------------------------------------------------------------------------
# Phase 5: Run Lifecycle
# ---------------------------------------------------------------------------


class TestStartRun:
    """start_run() creates a run directory and emits run_started event."""

    def test_start_run_creates_directory_and_event(self, tmp_path):
        from speckit_orca.yolo import load_events, start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )

        assert run_id  # non-empty
        events = load_events(tmp_path, run_id)
        assert len(events) == 1
        assert events[0].event_type.value == "run_started"
        assert events[0].feature_id == "020-example"
        assert events[0].to_stage == "brainstorm"

    def test_start_run_with_start_stage(self, tmp_path):
        from speckit_orca.yolo import load_events, start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
            start_stage="plan",
        )

        events = load_events(tmp_path, run_id)
        assert events[0].to_stage == "plan"

    def test_start_run_standalone_mode(self, tmp_path):
        from speckit_orca.yolo import load_events, reduce, start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )

        state = reduce(load_events(tmp_path, run_id))
        assert state.mode == "standalone"
        assert state.lane_id is None

    def test_start_run_with_lane_id(self, tmp_path):
        from speckit_orca.yolo import load_events, reduce, start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
            mode="matriarch-supervised",
            lane_id="020-example",
        )

        state = reduce(load_events(tmp_path, run_id))
        assert state.mode == "matriarch-supervised"
        assert state.lane_id == "020-example"

    def test_start_run_rejects_lane_id_in_standalone_mode(self, tmp_path):
        from speckit_orca.yolo import start_run

        with pytest.raises(ValueError, match=r"[Ss]tandalone"):
            start_run(
                repo_root=tmp_path,
                feature_id="020-example",
                actor="claude",
                branch="020-example",
                head_commit_sha="abc1234",
                mode="standalone",
                lane_id="020-example",
            )

    def test_start_run_requires_lane_id_in_matriarch_mode(self, tmp_path):
        from speckit_orca.yolo import start_run

        with pytest.raises(ValueError, match="matriarch"):
            start_run(
                repo_root=tmp_path,
                feature_id="020-example",
                actor="claude",
                branch="020-example",
                head_commit_sha="abc1234",
                mode="matriarch-supervised",
            )

    def test_start_run_rejects_invalid_stage(self, tmp_path):
        from speckit_orca.yolo import start_run

        with pytest.raises(ValueError, match=r"[Ii]nvalid start_stage"):
            start_run(
                repo_root=tmp_path,
                feature_id="020-example",
                actor="claude",
                branch="020-example",
                head_commit_sha="abc1234",
                start_stage="bogus-stage",
            )

    def test_start_run_rejects_spec_lite(self, tmp_path):
        from speckit_orca.yolo import start_run

        with pytest.raises(ValueError, match=r"[Ss]pec-lite"):
            start_run(
                repo_root=tmp_path,
                feature_id="SL-001-some-feature",
                actor="claude",
                branch="main",
                head_commit_sha="abc1234",
            )

    def test_start_run_rejects_adoption_record(self, tmp_path):
        from speckit_orca.yolo import start_run

        with pytest.raises(ValueError, match=r"[Aa]doption"):
            start_run(
                repo_root=tmp_path,
                feature_id="AR-001-some-feature",
                actor="claude",
                branch="main",
                head_commit_sha="abc1234",
            )

    def test_start_run_writes_status_snapshot(self, tmp_path):
        from speckit_orca.yolo import start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )

        snapshot = tmp_path / ".specify" / "orca" / "yolo" / "runs" / run_id / "status.json"
        assert snapshot.exists()
        data = json.loads(snapshot.read_text())
        assert data["run_id"] == run_id
        assert data["outcome"] == "running"


class TestResumeRun:
    """resume_run() replays event log and returns current Decision."""

    def _start_and_advance(self, tmp_path):
        from speckit_orca.yolo import append_event, start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )
        # Advance past brainstorm
        append_event(
            tmp_path, run_id,
            _event(2, "stage_completed", from_stage="brainstorm", to_stage="brainstorm"),
        )
        return run_id

    def test_resume_returns_decision(self, tmp_path):
        from speckit_orca.yolo import resume_run

        run_id = self._start_and_advance(tmp_path)
        decision = resume_run(tmp_path, run_id)
        assert decision.kind == "step"
        # Resume returns the decision for current_stage (still brainstorm —
        # stage_completed alone doesn't advance; STAGE_ENTERED would).
        assert decision.next_stage == "brainstorm"

    def test_resume_detects_stale_snapshot(self, tmp_path):
        """If status.json is missing, resume still works from event log."""
        from speckit_orca.yolo import resume_run

        run_id = self._start_and_advance(tmp_path)

        # Delete the snapshot
        snapshot = tmp_path / ".specify" / "orca" / "yolo" / "runs" / run_id / "status.json"
        if snapshot.exists():
            snapshot.unlink()

        decision = resume_run(tmp_path, run_id)
        assert decision.kind == "step"

    def test_resume_nonexistent_run_raises(self, tmp_path):
        from speckit_orca.yolo import resume_run

        with pytest.raises(ValueError, match=r"[Nn]o events"):
            resume_run(tmp_path, "nonexistent-run")

    def test_resume_regenerates_snapshot(self, tmp_path):
        from speckit_orca.yolo import resume_run

        run_id = self._start_and_advance(tmp_path)
        snapshot = tmp_path / ".specify" / "orca" / "yolo" / "runs" / run_id / "status.json"
        if snapshot.exists():
            snapshot.unlink()

        resume_run(tmp_path, run_id)
        assert snapshot.exists()


class TestCancelRun:
    """cancel_run() emits terminal event."""

    def test_cancel_nonexistent_run_raises(self, tmp_path):
        from speckit_orca.yolo import cancel_run

        with pytest.raises(ValueError, match=r"[Nn]o events"):
            cancel_run(tmp_path, "nonexistent", actor="claude", head_commit_sha="abc")

    def test_cancel_emits_terminal(self, tmp_path):
        from speckit_orca.yolo import cancel_run, load_events, reduce, start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )

        cancel_run(tmp_path, run_id, actor="claude", head_commit_sha="abc1234")
        events = load_events(tmp_path, run_id)
        assert events[-1].event_type.value == "terminal"
        state = reduce(events)
        assert state.outcome == "canceled"


class TestNextRun:
    """next_run() — the authoritative yolo driver loop."""

    def _start(self, tmp_path):
        from speckit_orca.yolo import start_run

        return start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )

    def test_next_readonly_returns_current_decision(self, tmp_path):
        """A fresh run starts at brainstorm; next_run() (read-only) should
        return a step decision to execute brainstorm (the current stage)."""
        from speckit_orca.yolo import next_run

        run_id = self._start(tmp_path)
        decision = next_run(tmp_path, run_id)
        assert decision.kind == "step"
        assert decision.next_stage == "brainstorm"

    def test_next_success_advances_stage(self, tmp_path):
        from speckit_orca.yolo import load_events, next_run, reduce

        run_id = self._start(tmp_path)
        # Report success on brainstorm
        next_run(tmp_path, run_id, result="success", head_commit_sha="abc1234")

        state = reduce(load_events(tmp_path, run_id))
        assert state.current_stage == "specify"

    def test_next_failure_marks_failed(self, tmp_path):
        from speckit_orca.yolo import load_events, next_run, reduce

        run_id = self._start(tmp_path)
        next_run(
            tmp_path, run_id,
            result="failure", reason="tests broke", head_commit_sha="abc1234",
        )

        state = reduce(load_events(tmp_path, run_id))
        assert state.outcome == "failed"

    def test_next_blocked_marks_blocked(self, tmp_path):
        from speckit_orca.yolo import load_events, next_run, reduce

        run_id = self._start(tmp_path)
        next_run(
            tmp_path, run_id,
            result="blocked", reason="missing dep", head_commit_sha="abc1234",
        )

        state = reduce(load_events(tmp_path, run_id))
        assert state.outcome == "blocked"

    def test_next_success_into_terminal_stage_auto_completes(self, tmp_path):
        """When next_run(success) advances into a terminal stage (pr-ready),
        outcome should become 'completed' (not stuck at 'running')."""
        from speckit_orca.yolo import (
            Event, EventType, append_event, load_events, next_run, reduce,
            start_run,
        )

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
            start_stage="review-code",
        )
        # Complete the cross-pass so review-code gate doesn't block
        events = load_events(tmp_path, run_id)
        max_clock = max(e.lamport_clock for e in events)
        for i, etype in enumerate(("cross_pass_requested", "cross_pass_completed"), start=1):
            append_event(tmp_path, run_id, Event(
                event_id=f"01JTEST{(max_clock + i):020d}",
                run_id=run_id,
                event_type=EventType(etype),
                timestamp=f"2026-04-16T12:{(max_clock + i):02d}:00Z",
                lamport_clock=max_clock + i,
                actor="claude",
                feature_id="020-example",
                lane_id=None,
                branch="020-example",
                head_commit_sha="abc1234",
                from_stage="review-code",
                to_stage=None,
                reason=None,
                evidence=None,
            ))

        # Report success on review-code — should advance to pr-ready AND
        # auto-terminate (pr-ready is a terminal stage).
        next_run(tmp_path, run_id, result="success", head_commit_sha="abc1234")

        state = reduce(load_events(tmp_path, run_id))
        assert state.current_stage == "pr-ready"
        assert state.outcome == "completed", (
            f"Expected outcome=completed after entering terminal stage, got {state.outcome}"
        )

    def test_next_invalid_result_raises(self, tmp_path):
        from speckit_orca.yolo import next_run

        run_id = self._start(tmp_path)
        with pytest.raises(ValueError, match=r"[Ii]nvalid result"):
            next_run(tmp_path, run_id, result="bogus")  # type: ignore[arg-type]

    def test_next_nonexistent_run_raises(self, tmp_path):
        from speckit_orca.yolo import next_run

        with pytest.raises(ValueError, match=r"[Nn]o events"):
            next_run(tmp_path, "nonexistent")


class TestRecoverRun:
    """recover_run() — explicit operator override."""

    def test_recover_emits_resume_event(self, tmp_path):
        from speckit_orca.yolo import load_events, recover_run, start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )
        recover_run(tmp_path, run_id)
        events = load_events(tmp_path, run_id)
        assert events[-1].event_type.value == "resume"
        assert events[-1].reason == "operator recovery override"


class TestReducerInvalidTransitions:
    """Reducer must silently reject impossible stage transitions."""

    def test_illegal_forward_jump_ignored(self):
        """brainstorm → pr-create is not a valid forward move."""
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
            _event(2, "stage_entered", from_stage="brainstorm", to_stage="pr-create"),
        ]
        state = reduce(events)
        # Should still be at brainstorm, illegal jump was rejected
        assert state.current_stage == "brainstorm"

    def test_unknown_stage_ignored(self):
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="brainstorm"),
            _event(2, "stage_entered", from_stage="brainstorm", to_stage="nonexistent-stage"),
        ]
        state = reduce(events)
        assert state.current_stage == "brainstorm"

    def test_same_stage_reentry_without_failure_is_not_a_retry(self):
        """retry_counts tracks failures only, not plain re-entries.

        A deliberate stage re-run (e.g., operator reruns brainstorm) should
        not count against the retry bound. Only STAGE_FAILED events increment
        retry_counts.
        """
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="implement"),
            _event(2, "stage_entered", from_stage="implement", to_stage="implement"),
            _event(3, "stage_entered", from_stage="implement", to_stage="implement"),
        ]
        state = reduce(events)
        assert state.retry_counts.get("implement", 0) == 0

    def test_failure_increments_retry_count(self):
        from speckit_orca.yolo import reduce

        events = [
            _event(1, "run_started", to_stage="implement"),
            _event(2, "stage_failed", from_stage="implement", reason="fail 1"),
        ]
        state = reduce(events)
        assert state.retry_counts.get("implement") == 1


class TestRetryBound:
    """Orchestration-policies default: 2 attempts per fix-loop stage."""

    def test_retry_bound_blocks_further_advancement(self):
        from speckit_orca.yolo import next_decision, reduce

        events = [
            _event(1, "run_started", to_stage="implement"),
            _event(2, "stage_failed", from_stage="implement", reason="fail 1"),
            _event(3, "resume"),
            _event(4, "stage_failed", from_stage="implement", reason="fail 2"),
        ]
        state = reduce(events)
        # Two failures = retry bound reached
        assert state.retry_counts.get("implement") == 2

        # But outcome is failed so we hit the failed branch first.
        # Resume and we should hit the retry bound guard.
        from speckit_orca.yolo import Event, EventType

        # Unblock to running state to exercise retry-bound path
        events.append(_event(5, "resume"))
        state = reduce(events)
        decision = next_decision(state)
        assert decision.kind == "blocked"
        assert "retry bound" in decision.prompt_text.lower() or decision.machine_payload.get("limit") == 2


class TestRunStatus:
    """run_status() returns current state from snapshot or event log."""

    def test_run_status_returns_state(self, tmp_path):
        from speckit_orca.yolo import run_status, start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )

        state = run_status(tmp_path, run_id)
        assert state.run_id == run_id
        assert state.outcome == "running"


class TestListRuns:
    """list_runs() enumerates all run directories."""

    def test_list_runs_empty(self, tmp_path):
        from speckit_orca.yolo import list_runs

        assert list_runs(tmp_path) == []

    def test_list_runs_finds_runs(self, tmp_path):
        from speckit_orca.yolo import list_runs, start_run

        id1 = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )
        id2 = start_run(
            repo_root=tmp_path,
            feature_id="021-another",
            actor="codex",
            branch="021-another",
            head_commit_sha="def5678",
        )

        runs = list_runs(tmp_path)
        assert set(runs) == {id1, id2}


# ---------------------------------------------------------------------------
# Phase 6: CLI
# ---------------------------------------------------------------------------


class TestCLI:
    """cli_main(argv) dispatches subcommands correctly."""

    def test_cli_start(self, tmp_path, monkeypatch):
        from speckit_orca.yolo import cli_main, list_runs

        monkeypatch.chdir(tmp_path)
        # Init a git-like state for branch/sha detection
        (tmp_path / ".git").mkdir()

        rc = cli_main([
            "--root", str(tmp_path),
            "start", "020-example",
            "--actor", "claude",
            "--branch", "020-example",
            "--sha", "abc1234",
        ])
        assert rc == 0
        assert len(list_runs(tmp_path)) == 1

    def test_cli_list_empty(self, tmp_path):
        from speckit_orca.yolo import cli_main

        rc = cli_main(["--root", str(tmp_path), "list"])
        assert rc == 0

    def test_cli_status_missing_run(self, tmp_path):
        from speckit_orca.yolo import cli_main

        rc = cli_main(["--root", str(tmp_path), "status", "nonexistent"])
        assert rc == 1

    def test_cli_cancel(self, tmp_path):
        from speckit_orca.yolo import cli_main, list_runs, load_events, reduce, start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )

        rc = cli_main([
            "--root", str(tmp_path),
            "cancel", run_id,
            "--actor", "claude",
            "--sha", "abc1234",
        ])
        assert rc == 0
        state = reduce(load_events(tmp_path, run_id))
        assert state.outcome == "canceled"

    def test_cli_resume(self, tmp_path):
        from speckit_orca.yolo import cli_main, start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )

        rc = cli_main(["--root", str(tmp_path), "resume", run_id])
        assert rc == 0

    def test_cli_next_readonly(self, tmp_path):
        from speckit_orca.yolo import cli_main, start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )
        rc = cli_main(["--root", str(tmp_path), "next", run_id])
        assert rc == 0

    def test_cli_next_success(self, tmp_path):
        from speckit_orca.yolo import cli_main, load_events, reduce, start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )
        rc = cli_main([
            "--root", str(tmp_path),
            "next", run_id,
            "--result", "success",
            "--sha", "abc1234",
        ])
        assert rc == 0
        state = reduce(load_events(tmp_path, run_id))
        assert state.current_stage == "specify"

    def test_cli_recover(self, tmp_path):
        from speckit_orca.yolo import cli_main, start_run

        run_id = start_run(
            repo_root=tmp_path,
            feature_id="020-example",
            actor="claude",
            branch="020-example",
            head_commit_sha="abc1234",
        )
        rc = cli_main(["--root", str(tmp_path), "recover", run_id])
        assert rc == 0
