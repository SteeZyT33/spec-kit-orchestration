"""Orca YOLO — single-lane execution runtime.

Implements the 009-orca-yolo contracts: event-sourced run state,
deterministic reducer, read-only-decision loop. Standalone mode only
in this module; matriarch supervised mode is a later integration.

Runtime-plan: specs/009-orca-yolo/runtime-plan.md
Contracts: specs/009-orca-yolo/contracts/
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal


# ---------------------------------------------------------------------------
# EventType enum — all 12 types from runtime-plan section 6
# ---------------------------------------------------------------------------


class EventType(Enum):
    """All 12 event types for the yolo event log per runtime-plan section 6."""

    RUN_STARTED = "run_started"
    STAGE_ENTERED = "stage_entered"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"
    PAUSE = "pause"
    RESUME = "resume"
    BLOCK = "block"
    UNBLOCK = "unblock"
    DECISION_REQUIRED = "decision_required"
    CROSS_PASS_REQUESTED = "cross_pass_requested"
    CROSS_PASS_COMPLETED = "cross_pass_completed"
    TERMINAL = "terminal"


# ---------------------------------------------------------------------------
# Event dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Event:
    """A single yolo event. Immutable. Written to append-only JSONL log."""

    # Required fields (all events)
    event_id: str
    run_id: str
    event_type: EventType
    timestamp: str  # RFC3339 UTC, Z offset required
    lamport_clock: int
    actor: str
    # Routing fields
    feature_id: str
    lane_id: str | None
    branch: str
    head_commit_sha: str
    # Payload fields (event-type dependent)
    from_stage: str | None
    to_stage: str | None
    reason: str | None
    evidence: list[str] | None

    def __post_init__(self) -> None:
        """Validate timestamp uses RFC3339 UTC Z offset per 010 contract."""
        if not self.timestamp.endswith("Z"):
            raise ValueError(
                f"Timestamp must use UTC Z offset, got: {self.timestamp!r}"
            )

    def to_json(self) -> str:
        """Serialize this event to a single-line JSON string for JSONL storage."""
        d = {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "lamport_clock": self.lamport_clock,
            "actor": self.actor,
            "feature_id": self.feature_id,
            "lane_id": self.lane_id,
            "branch": self.branch,
            "head_commit_sha": self.head_commit_sha,
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "reason": self.reason,
            "evidence": self.evidence,
        }
        return json.dumps(d, separators=(",", ":"))

    @classmethod
    def from_json(cls, json_str: str) -> Event:
        """Deserialize an Event from a JSON line produced by `to_json()`."""
        d = json.loads(json_str)
        return cls(
            event_id=d["event_id"],
            run_id=d["run_id"],
            event_type=EventType(d["event_type"]),
            timestamp=d["timestamp"],
            lamport_clock=d["lamport_clock"],
            actor=d["actor"],
            feature_id=d["feature_id"],
            lane_id=d.get("lane_id"),
            branch=d["branch"],
            head_commit_sha=d["head_commit_sha"],
            from_stage=d.get("from_stage"),
            to_stage=d.get("to_stage"),
            reason=d.get("reason"),
            evidence=d.get("evidence"),
        )


# ---------------------------------------------------------------------------
# Inline ULID generator — ~40 LOC, no external dependency
# ---------------------------------------------------------------------------

# Crockford's Base32 alphabet
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# Monotonic state: last timestamp_ms and last random component
_ulid_last_ts: int = 0
_ulid_last_rand: int = 0


def generate_ulid() -> str:
    """Generate a ULID (Universally Unique Lexicographically Sortable ID).

    26 characters, Crockford Base32, monotonic within the same millisecond.

    NOT thread-safe. Uses module-level globals for monotonic state. The 009
    runtime is single-writer-per-run by contract (runtime-plan section 6),
    so concurrent invocation is out of scope for v1. If multi-threaded use
    becomes necessary, wrap the global state in a lock.
    """
    global _ulid_last_ts, _ulid_last_rand

    ts_ms = int(time.time() * 1000)

    if ts_ms == _ulid_last_ts:
        # Same millisecond — increment random component for monotonicity
        _ulid_last_rand += 1
    else:
        _ulid_last_ts = ts_ms
        _ulid_last_rand = random.getrandbits(80)

    rand = _ulid_last_rand

    # Encode: 10 chars for 48-bit timestamp, 16 chars for 80-bit random
    chars = []
    # Timestamp (48 bits → 10 base32 chars, most significant first)
    for _ in range(10):
        chars.append(_CROCKFORD[ts_ms & 0x1F])
        ts_ms >>= 5
    chars.reverse()

    # Random (80 bits → 16 base32 chars, most significant first)
    rand_chars = []
    for _ in range(16):
        rand_chars.append(_CROCKFORD[rand & 0x1F])
        rand >>= 5
    rand_chars.reverse()

    chars.extend(rand_chars)
    return "".join(chars)


# ---------------------------------------------------------------------------
# Event log I/O
# ---------------------------------------------------------------------------


def _run_dir(repo_root: Path, run_id: str) -> Path:
    """Directory for a run's artifacts (events.jsonl, status.json)."""
    return repo_root / ".specify" / "orca" / "yolo" / "runs" / run_id


def _events_path(repo_root: Path, run_id: str) -> Path:
    """Path to a run's append-only event log."""
    return _run_dir(repo_root, run_id) / "events.jsonl"


def append_event(repo_root: Path, run_id: str, event: Event) -> None:
    """Append an event to the run's JSONL log. UTF-8 encoded."""
    path = _events_path(repo_root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(event.to_json() + "\n")


def load_events(repo_root: Path, run_id: str) -> list[Event]:
    """Load and deduplicate events from a run's JSONL log.

    Returns events sorted by (lamport_clock, timestamp, event_id).
    Duplicate event_ids are dropped (first occurrence wins).
    """
    path = _events_path(repo_root, run_id)
    if not path.exists():
        return []

    seen_ids: set[str] = set()
    events: list[Event] = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if not line:
            continue
        event = Event.from_json(line)
        if event.event_id not in seen_ids:
            seen_ids.add(event.event_id)
            events.append(event)

    events.sort(key=lambda e: (e.lamport_clock, e.timestamp, e.event_id))
    return events


# ---------------------------------------------------------------------------
# RunState dataclass — runtime-plan section 7
# ---------------------------------------------------------------------------


@dataclass
class RunState:
    """Materialized state of a yolo run, derived by the reducer from events.

    This dataclass is the "current view" of a run. It is NOT a source of
    truth — the event log is. Snapshots of RunState are written to
    status.json for fast reads, but can always be regenerated from events.
    """

    run_id: str
    feature_id: str
    mode: Literal["standalone", "matriarch-supervised"]
    lane_id: str | None
    current_stage: str
    outcome: Literal["running", "paused", "blocked", "completed", "failed", "canceled"]
    block_reason: str | None
    last_event_id: str
    last_event_timestamp: str
    branch: str
    head_commit_sha_at_last_event: str
    deployment_kind: Literal["standalone", "direct-session", "tmux"] | None
    # Review status: derived projections from cross-pass events, not
    # sources of truth. The 012-review-model artifacts are authoritative.
    review_spec_status: Literal["pending", "in_progress", "complete", "stale"] | None
    review_code_status: Literal["pending", "in_progress", "complete", "stale"] | None
    review_pr_status: Literal["pending", "in_progress", "complete", "stale"] | None
    mailbox_path: str | None
    last_mailbox_event_id: str | None
    # Retry tracking per-stage (orchestration-policies default: 2 attempts)
    retry_counts: dict[str, int]


# ---------------------------------------------------------------------------
# Stage model — from run-stage-model.md contract
# ---------------------------------------------------------------------------

# Canonical stage order. assign is optional (skipped by default).
STAGES = [
    "brainstorm", "specify", "clarify", "review-spec",
    "plan", "tasks", "assign", "implement",
    "review-code", "pr-ready", "pr-create", "review-pr",
]
STAGES_SET = frozenset(STAGES)

# Default next-stage map. assign skips to implement by default.
_NEXT_STAGE: dict[str, str | None] = {
    "brainstorm": "specify",
    "specify": "clarify",
    "clarify": "review-spec",
    "review-spec": "plan",
    "plan": "tasks",
    "tasks": "implement",  # skip assign by default
    "assign": "implement",
    "implement": "review-code",
    "review-code": "pr-ready",
    "pr-ready": None,  # default terminal
    "pr-create": "review-pr",
    "review-pr": None,
}

# Review gates: stages that require a review artifact to be complete
# before the run can advance to the next stage.
_REVIEW_GATE: dict[str, str] = {
    # After review-spec, review_spec_status MUST be "complete" before plan
    "review-spec": "review_spec_status",
    # After review-code, review_code_status MUST be "complete" before pr-ready
    "review-code": "review_code_status",
}

# Default retry bound per orchestration-policies.md: 2 attempts per fix-loop stage.
DEFAULT_RETRY_BOUND = 2

# ---------------------------------------------------------------------------
# Reducer — pure function: reduce(events) → RunState
# ---------------------------------------------------------------------------


def _deduplicate(events: list[Event]) -> list[Event]:
    """Drop events with duplicate event_ids, keeping first occurrence.

    Protects against double-commit bugs and future multi-writer scenarios.
    """
    seen: set[str] = set()
    result: list[Event] = []
    for e in events:
        if e.event_id not in seen:
            seen.add(e.event_id)
            result.append(e)
    return result


def reduce(events: list[Event]) -> RunState:
    """Deterministic reducer: derives RunState from an event sequence.

    Pure function — no I/O, no side effects. Same input always
    produces same output.
    """
    if not events:
        raise ValueError("No events to reduce")

    # Sort and deduplicate
    unique = _deduplicate(events)
    unique.sort(key=lambda e: (e.lamport_clock, e.timestamp, e.event_id))

    # Seed state from first event
    first = unique[0]
    state = RunState(
        run_id=first.run_id,
        feature_id=first.feature_id,
        mode="matriarch-supervised" if first.lane_id else "standalone",
        lane_id=first.lane_id,
        current_stage=first.to_stage or "",
        outcome="running",
        block_reason=None,
        last_event_id=first.event_id,
        last_event_timestamp=first.timestamp,
        branch=first.branch,
        head_commit_sha_at_last_event=first.head_commit_sha,
        deployment_kind=None,
        review_spec_status=None,
        review_code_status=None,
        review_pr_status=None,
        mailbox_path=None,
        last_mailbox_event_id=None,
        retry_counts={},
    )

    terminated = False
    for event in unique:
        if terminated:
            # After terminal, ignore all subsequent events
            break

        # Track metadata from every event
        state.last_event_id = event.event_id
        state.last_event_timestamp = event.timestamp
        state.head_commit_sha_at_last_event = event.head_commit_sha
        if event.lane_id:
            state.lane_id = event.lane_id
            state.mode = "matriarch-supervised"

        match event.event_type:
            case EventType.RUN_STARTED:
                state.current_stage = event.to_stage or state.current_stage
                state.outcome = "running"

            case EventType.STAGE_ENTERED:
                # Reject invalid transitions per runtime-plan section 7.
                # Only allow: (1) moving forward via _NEXT_STAGE,
                # (2) re-entering current stage (retry),
                # (3) back to a prior stage when unblocking/redirecting.
                to_stage = event.to_stage
                if to_stage and to_stage not in STAGES_SET:
                    # Unknown stage — silently ignore
                    continue
                allowed_next = _NEXT_STAGE.get(state.current_stage)
                same = to_stage == state.current_stage
                forward = to_stage == allowed_next
                backward = (
                    to_stage in STAGES and state.current_stage in STAGES
                    and STAGES.index(to_stage) < STAGES.index(state.current_stage)
                )
                if not (same or forward or backward):
                    # Illegal forward jump (e.g. brainstorm -> pr-create) — ignore
                    continue
                state.current_stage = to_stage or state.current_stage
                state.outcome = "running"

            case EventType.STAGE_COMPLETED:
                # Stage stays at current (completed), outcome still running
                state.outcome = "running"

            case EventType.STAGE_FAILED:
                # retry_counts tracks failure attempts only (not reentries).
                # A deliberate same-stage re-enter without a prior failure is
                # not a retry. This aligns with orchestration-policies.md's
                # "2 attempts per fix-loop stage" — fix-loops imply failures.
                state.outcome = "failed"
                state.block_reason = event.reason
                stage = event.from_stage or state.current_stage
                state.retry_counts[stage] = (
                    state.retry_counts.get(stage, 0) + 1
                )

            case EventType.PAUSE:
                state.outcome = "paused"
                state.block_reason = event.reason

            case EventType.RESUME:
                state.outcome = "running"
                state.block_reason = None

            case EventType.BLOCK:
                state.outcome = "blocked"
                state.block_reason = event.reason

            case EventType.UNBLOCK:
                state.outcome = "running"
                state.block_reason = None

            case EventType.DECISION_REQUIRED:
                state.outcome = "paused"
                state.block_reason = event.reason

            case EventType.CROSS_PASS_REQUESTED:
                _track_review(state, event.from_stage, "in_progress")

            case EventType.CROSS_PASS_COMPLETED:
                _track_review(state, event.from_stage, "complete")

            case EventType.TERMINAL:
                if event.reason and "canceled" in event.reason.lower():
                    state.outcome = "canceled"
                else:
                    state.outcome = "completed"
                terminated = True

    return state


def _track_review(
    state: RunState,
    stage: str | None,
    status: Literal["pending", "in_progress", "complete", "stale"],
) -> None:
    """Update the appropriate review_* status field on RunState.

    These are derived projections; the 012-review-model artifacts
    are the authoritative record.
    """
    if stage == "review-spec":
        state.review_spec_status = status
    elif stage == "review-code":
        state.review_code_status = status
    elif stage == "review-pr":
        state.review_pr_status = status


# ---------------------------------------------------------------------------
# Decision dataclass + next_decision() ��� runtime-plan section 8
# ---------------------------------------------------------------------------


@dataclass
class Decision:
    """The result of `next_decision()`: what the caller should do next.

    - kind=step: execute the named stage, then report back via `next_run`
    - kind=decision_required: human input needed (e.g., review gate not met)
    - kind=blocked: cannot proceed (missing dep, retry bound, failed gate)
    - kind=terminal: run complete, no further action
    """

    kind: Literal["step", "decision_required", "blocked", "terminal"]
    next_stage: str | None
    prompt_text: str
    machine_payload: dict
    requires_confirmation: bool


def next_decision(state: RunState) -> Decision:
    """Pure function: compute the next action from current RunState."""
    # Terminal outcomes
    if state.outcome == "completed":
        return Decision(
            kind="terminal",
            next_stage=None,
            prompt_text="Run complete.",
            machine_payload={"stage": state.current_stage},
            requires_confirmation=False,
        )

    if state.outcome == "blocked":
        return Decision(
            kind="blocked",
            next_stage=None,
            prompt_text=f"Blocked: {state.block_reason or 'unknown reason'}",
            machine_payload={"block_reason": state.block_reason},
            requires_confirmation=False,
        )

    if state.outcome == "failed":
        return Decision(
            kind="blocked",
            next_stage=None,
            prompt_text=f"Failed: {state.block_reason or 'unknown reason'}",
            machine_payload={"block_reason": state.block_reason},
            requires_confirmation=False,
        )

    if state.outcome == "paused":
        return Decision(
            kind="decision_required",
            next_stage=None,
            prompt_text=f"Paused: {state.block_reason or 'awaiting operator input'}",
            machine_payload={"reason": state.block_reason},
            requires_confirmation=True,
        )

    # outcome == "running" — compute next stage
    next_stage = _NEXT_STAGE.get(state.current_stage)

    if next_stage is None:
        # At a terminal stage (pr-ready or review-pr)
        return Decision(
            kind="terminal",
            next_stage=None,
            prompt_text=f"Run reached terminal stage: {state.current_stage}",
            machine_payload={"stage": state.current_stage},
            requires_confirmation=False,
        )

    # Enforce review gates: review-spec must be complete before advancing
    # past plan/tasks, review-code must be complete before pr-ready.
    gate_field = _REVIEW_GATE.get(state.current_stage)
    if gate_field is not None:
        status = getattr(state, gate_field, None)
        if status != "complete":
            return Decision(
                kind="decision_required",
                next_stage=None,
                prompt_text=(
                    f"Cannot advance from {state.current_stage} to "
                    f"{next_stage}: {gate_field} is "
                    f"{status or 'pending'}, must be 'complete'."
                ),
                machine_payload={
                    "required_gate": gate_field,
                    "current_status": status,
                    "from_stage": state.current_stage,
                },
                requires_confirmation=True,
            )

    # Enforce retry bound per orchestration-policies.md (default 2 attempts).
    attempts = state.retry_counts.get(state.current_stage, 0)
    if attempts >= DEFAULT_RETRY_BOUND:
        return Decision(
            kind="blocked",
            next_stage=None,
            prompt_text=(
                f"Retry bound exceeded for stage '{state.current_stage}' "
                f"({attempts} attempts, limit {DEFAULT_RETRY_BOUND}). "
                "Operator intervention required."
            ),
            machine_payload={
                "stage": state.current_stage,
                "attempts": attempts,
                "limit": DEFAULT_RETRY_BOUND,
            },
            requires_confirmation=False,
        )

    # PR creation is explicit policy — pr-ready is the default terminal.
    # Advancing from pr-ready to pr-create requires opt-in via an explicit
    # stage_entered event to "pr-create"; the default next_decision from
    # pr-ready returns terminal (handled above).

    return Decision(
        kind="step",
        next_stage=next_stage,
        prompt_text=f"Proceed to {next_stage}",
        machine_payload={"from_stage": state.current_stage, "to_stage": next_stage},
        requires_confirmation=False,
    )


# ---------------------------------------------------------------------------
# Status snapshot I/O
# ---------------------------------------------------------------------------


def _snapshot_path(repo_root: Path, run_id: str) -> Path:
    """Path to a run's materialized status.json snapshot."""
    return _run_dir(repo_root, run_id) / "status.json"


def _write_snapshot(repo_root: Path, run_id: str, state: RunState) -> None:
    """Write a materialized status.json snapshot from RunState.

    The snapshot is derived, not authoritative. The event log is always
    the source of truth; snapshots are for fast reads.
    """
    path = _snapshot_path(repo_root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "run_id": state.run_id,
        "feature_id": state.feature_id,
        "mode": state.mode,
        "lane_id": state.lane_id,
        "current_stage": state.current_stage,
        "outcome": state.outcome,
        "block_reason": state.block_reason,
        "last_event_id": state.last_event_id,
        "last_event_timestamp": state.last_event_timestamp,
        "branch": state.branch,
        "head_commit_sha_at_last_event": state.head_commit_sha_at_last_event,
        "deployment_kind": state.deployment_kind,
        "review_spec_status": state.review_spec_status,
        "review_code_status": state.review_code_status,
        "review_pr_status": state.review_pr_status,
        "mailbox_path": state.mailbox_path,
        "last_mailbox_event_id": state.last_mailbox_event_id,
        "retry_counts": state.retry_counts,
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Start artifact validation
# ---------------------------------------------------------------------------

_SPEC_LITE_RE = re.compile(r"^SL-\d{3}")
_ADOPTION_RE = re.compile(r"^AR-\d{3}")


def _validate_start_artifact(feature_id: str) -> None:
    """Reject excluded start artifacts per orchestration-policies contract.

    Spec-lite (SL-NNN) is excluded in v1. Adoption records (AR-NNN) are
    never valid yolo start artifacts — they are reference-only per 015.
    """
    if _SPEC_LITE_RE.match(feature_id):
        raise ValueError(
            f"Spec-lite records are excluded as yolo start artifacts in v1: {feature_id}"
        )
    if _ADOPTION_RE.match(feature_id):
        raise ValueError(
            f"Adoption records are never valid yolo start artifacts: {feature_id}"
        )


# ---------------------------------------------------------------------------
# Run lifecycle operations
# ---------------------------------------------------------------------------


def _now_utc() -> str:
    """Current time as RFC3339 UTC with Z offset."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def start_run(
    *,
    repo_root: Path,
    feature_id: str,
    actor: str,
    branch: str,
    head_commit_sha: str,
    start_stage: str = "brainstorm",
    mode: Literal["standalone", "matriarch-supervised"] = "standalone",
    lane_id: str | None = None,
) -> str:
    """Start a new yolo run. Returns the run_id.

    Per orchestration-policies.md, mode MUST be set explicitly at start,
    not inferred from environment. In matriarch-supervised mode, a lane_id
    is required.
    """
    _validate_start_artifact(feature_id)

    # Validate start_stage against the stage model
    if start_stage not in STAGES_SET:
        raise ValueError(
            f"Invalid start_stage: {start_stage!r}. Must be one of {STAGES}."
        )

    # Mode/lane_id consistency check
    if mode == "matriarch-supervised" and lane_id is None:
        raise ValueError(
            "matriarch-supervised mode requires an explicit lane_id."
        )
    if mode == "standalone" and lane_id is not None:
        raise ValueError(
            "standalone mode cannot have a lane_id; use matriarch-supervised."
        )

    run_id = f"run-{generate_ulid()}"
    event = Event(
        event_id=generate_ulid(),
        run_id=run_id,
        event_type=EventType.RUN_STARTED,
        timestamp=_now_utc(),
        lamport_clock=1,
        actor=actor,
        feature_id=feature_id,
        lane_id=lane_id,
        branch=branch,
        head_commit_sha=head_commit_sha,
        from_stage=None,
        to_stage=start_stage,
        reason=None,
        evidence=None,
    )
    append_event(repo_root, run_id, event)

    # Write initial snapshot
    state = reduce(load_events(repo_root, run_id))
    _write_snapshot(repo_root, run_id, state)

    return run_id


def resume_run(repo_root: Path, run_id: str) -> Decision:
    """Resume a run from its event log. Returns the current Decision."""
    events = load_events(repo_root, run_id)
    if not events:
        raise ValueError(f"No events found for run {run_id}")

    state = reduce(events)

    # Regenerate snapshot (may have been deleted or stale)
    _write_snapshot(repo_root, run_id, state)

    return next_decision(state)


def next_run(
    repo_root: Path,
    run_id: str,
    *,
    result: Literal["success", "failure", "blocked", None] = None,
    reason: str | None = None,
    evidence: list[str] | None = None,
    actor: str = "claude",
    head_commit_sha: str = "",
) -> Decision:
    """Advance a yolo run: report the previous step's result and get the
    next decision.

    This is the authoritative driver for the yolo execution loop per
    runtime-plan section 5. The caller runs the step returned by
    `next_decision`, then calls `next_run` with the result. The runtime
    appends the corresponding event and returns the next Decision.

    - result=None: read-only (query current decision without mutation)
    - result="success": emit stage_completed for the current stage
      and stage_entered for the next stage (if one exists)
    - result="failure": emit stage_failed with reason
    - result="blocked": emit block with reason
    """
    events = load_events(repo_root, run_id)
    if not events:
        raise ValueError(f"No events found for run {run_id}")

    state = reduce(events)
    max_clock = max(e.lamport_clock for e in events)

    # Read-only query
    if result is None:
        return next_decision(state)

    # Resolve missing metadata from state
    head_sha = head_commit_sha or state.head_commit_sha_at_last_event

    def _mk(etype: EventType, clock: int, **fields) -> Event:
        defaults = dict(
            event_id=generate_ulid(),
            run_id=run_id,
            event_type=etype,
            timestamp=_now_utc(),
            lamport_clock=clock,
            actor=actor,
            feature_id=state.feature_id,
            lane_id=state.lane_id,
            branch=state.branch,
            head_commit_sha=head_sha,
            from_stage=state.current_stage,
            to_stage=state.current_stage,
            reason=None,
            evidence=None,
        )
        defaults.update(fields)
        return Event(**defaults)

    if result == "success":
        # Stage completed + enter next stage (if any)
        append_event(repo_root, run_id, _mk(
            EventType.STAGE_COMPLETED,
            max_clock + 1,
            reason=reason,
            evidence=evidence,
        ))
        next_stage = _NEXT_STAGE.get(state.current_stage)
        if next_stage is not None:
            append_event(repo_root, run_id, _mk(
                EventType.STAGE_ENTERED,
                max_clock + 2,
                from_stage=state.current_stage,
                to_stage=next_stage,
            ))
    elif result == "failure":
        append_event(repo_root, run_id, _mk(
            EventType.STAGE_FAILED,
            max_clock + 1,
            reason=reason or "stage failed",
            evidence=evidence,
        ))
    elif result == "blocked":
        append_event(repo_root, run_id, _mk(
            EventType.BLOCK,
            max_clock + 1,
            reason=reason or "blocked",
            evidence=evidence,
        ))
    else:
        raise ValueError(
            f"Invalid result: {result!r}. Expected 'success', 'failure', "
            f"'blocked', or None."
        )

    # Recompute state and return next decision
    new_state = reduce(load_events(repo_root, run_id))
    _write_snapshot(repo_root, run_id, new_state)
    return next_decision(new_state)


def recover_run(
    repo_root: Path,
    run_id: str,
    *,
    actor: str = "claude",
) -> Decision:
    """Explicit override for stale-run warnings and head-commit drift.

    Emits a `resume` event that acknowledges the operator has inspected
    the run and explicitly approves continuing despite staleness or drift.
    """
    events = load_events(repo_root, run_id)
    if not events:
        raise ValueError(f"No events found for run {run_id}")

    state = reduce(events)
    max_clock = max(e.lamport_clock for e in events)

    event = Event(
        event_id=generate_ulid(),
        run_id=run_id,
        event_type=EventType.RESUME,
        timestamp=_now_utc(),
        lamport_clock=max_clock + 1,
        actor=actor,
        feature_id=state.feature_id,
        lane_id=state.lane_id,
        branch=state.branch,
        head_commit_sha=state.head_commit_sha_at_last_event,
        from_stage=state.current_stage,
        to_stage=state.current_stage,
        reason="operator recovery override",
        evidence=None,
    )
    append_event(repo_root, run_id, event)
    new_state = reduce(load_events(repo_root, run_id))
    _write_snapshot(repo_root, run_id, new_state)
    return next_decision(new_state)


def cancel_run(
    repo_root: Path,
    run_id: str,
    *,
    actor: str,
    head_commit_sha: str,
) -> None:
    """Cancel a run by emitting a terminal event with reason='canceled by operator'.

    Raises ValueError if the run does not exist (no events). Consistent with
    resume_run, next_run, run_status, and recover_run.
    """
    events = load_events(repo_root, run_id)
    if not events:
        raise ValueError(f"No events found for run {run_id}")

    state = reduce(events)
    max_clock = max(e.lamport_clock for e in events)

    event = Event(
        event_id=generate_ulid(),
        run_id=run_id,
        event_type=EventType.TERMINAL,
        timestamp=_now_utc(),
        lamport_clock=max_clock + 1,
        actor=actor,
        feature_id=state.feature_id,
        lane_id=state.lane_id,
        branch=state.branch,
        head_commit_sha=head_commit_sha,
        from_stage=state.current_stage,
        to_stage=state.current_stage,
        reason="canceled by operator",
        evidence=None,
    )
    append_event(repo_root, run_id, event)

    new_state = reduce(load_events(repo_root, run_id))
    _write_snapshot(repo_root, run_id, new_state)


def run_status(repo_root: Path, run_id: str) -> RunState:
    """Get current RunState for a run from the event log."""
    events = load_events(repo_root, run_id)
    if not events:
        raise ValueError(f"No events found for run {run_id}")
    return reduce(events)


def list_runs(repo_root: Path) -> list[str]:
    """List all run IDs found under .specify/orca/yolo/runs/."""
    runs_dir = repo_root / ".specify" / "orca" / "yolo" / "runs"
    if not runs_dir.exists():
        return []
    return sorted(
        d.name for d in runs_dir.iterdir()
        if d.is_dir() and (d / "events.jsonl").exists()
    )


# ---------------------------------------------------------------------------
# CLI — python -m speckit_orca.yolo
# ---------------------------------------------------------------------------

def cli_main(argv: list[str] | None = None) -> int:
    """Entry point for `python -m speckit_orca.yolo <subcommand>`.

    Subcommands: start, next, resume, recover, status, cancel, list.
    Returns 0 on success, 1 on error (prints to stderr).
    """
    parser = argparse.ArgumentParser(
        prog="yolo",
        description="Orca YOLO single-lane execution runtime",
    )
    parser.add_argument(
        "--root", type=Path, default=Path("."),
        help="Repository root (default: current directory)",
    )
    sub = parser.add_subparsers(dest="command")

    # -- start --
    p_start = sub.add_parser("start", help="Begin a new yolo run")
    p_start.add_argument("feature_id", help="Feature ID (e.g. 020-example)")
    p_start.add_argument("--actor", default="claude")
    p_start.add_argument("--branch", default="")
    p_start.add_argument("--sha", default="")
    p_start.add_argument("--stage", default="brainstorm", help="Start stage")
    p_start.add_argument(
        "--mode", default="standalone",
        choices=["standalone", "matriarch-supervised"],
        help="Run mode (explicit, not inferred)",
    )
    p_start.add_argument("--lane-id", default=None)

    # -- next --
    p_next = sub.add_parser(
        "next",
        help="Advance the run: report last step's result, get next decision",
    )
    p_next.add_argument("run_id")
    p_next.add_argument(
        "--result", default=None,
        choices=["success", "failure", "blocked"],
        help="Result of the previous step (omit for read-only query)",
    )
    p_next.add_argument("--reason", default=None)
    p_next.add_argument("--evidence", default=None, nargs="*")
    p_next.add_argument("--actor", default="claude")
    p_next.add_argument("--sha", default="")

    # -- resume --
    p_resume = sub.add_parser("resume", help="Resume an existing run")
    p_resume.add_argument("run_id")

    # -- recover --
    p_recover = sub.add_parser(
        "recover",
        help="Explicitly override stale-warning or head-commit drift",
    )
    p_recover.add_argument("run_id")
    p_recover.add_argument("--actor", default="claude")

    # -- status --
    p_status = sub.add_parser("status", help="Show run status")
    p_status.add_argument("run_id")

    # -- cancel --
    p_cancel = sub.add_parser("cancel", help="Cancel a run")
    p_cancel.add_argument("run_id")
    p_cancel.add_argument("--actor", default="claude")
    p_cancel.add_argument("--sha", default="")

    # -- list --
    sub.add_parser("list", help="List all runs")

    args = parser.parse_args(argv)
    root = args.root

    if args.command == "start":
        try:
            run_id = start_run(
                repo_root=root,
                feature_id=args.feature_id,
                actor=args.actor,
                branch=args.branch,
                head_commit_sha=args.sha,
                start_stage=args.stage,
                mode=args.mode,
                lane_id=args.lane_id,
            )
            print(f"Started run: {run_id}")
            return 0
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "next":
        try:
            decision = next_run(
                root, args.run_id,
                result=args.result,
                reason=args.reason,
                evidence=args.evidence,
                actor=args.actor,
                head_commit_sha=args.sha,
            )
            print(f"Decision: {decision.kind}")
            if decision.next_stage:
                print(f"Next stage: {decision.next_stage}")
            print(f"Prompt: {decision.prompt_text}")
            return 0
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "resume":
        try:
            decision = resume_run(root, args.run_id)
            print(f"Decision: {decision.kind}")
            if decision.next_stage:
                print(f"Next stage: {decision.next_stage}")
            print(f"Prompt: {decision.prompt_text}")
            return 0
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "recover":
        try:
            decision = recover_run(root, args.run_id, actor=args.actor)
            print(f"Recovered. Decision: {decision.kind}")
            if decision.next_stage:
                print(f"Next stage: {decision.next_stage}")
            print(f"Prompt: {decision.prompt_text}")
            return 0
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "status":
        try:
            state = run_status(root, args.run_id)
            print(f"Run: {state.run_id}")
            print(f"Feature: {state.feature_id}")
            print(f"Stage: {state.current_stage}")
            print(f"Outcome: {state.outcome}")
            if state.block_reason:
                print(f"Block reason: {state.block_reason}")
            return 0
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "cancel":
        try:
            cancel_run(root, args.run_id, actor=args.actor, head_commit_sha=args.sha)
            print(f"Canceled: {args.run_id}")
            return 0
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "list":
        runs = list_runs(root)
        if not runs:
            print("No runs found.")
        else:
            for r in runs:
                print(r)
        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(cli_main())
