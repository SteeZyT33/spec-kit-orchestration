# Runtime Plan: Orca YOLO Single-Lane Execution Driver

**Feature Branch**: `009-orca-yolo` (runtime phase)
**Created**: 2026-04-11
**Status**: Draft
**Relationship to 009's existing plan**: `009-orca-yolo/plan.md` is
the **contract-phase plan** (covers spec, run-stage-model, run-state,
orchestration-policies, Lane Agent Binding). This file,
`runtime-plan.md`, is the **runtime-phase plan** layered on top of
those contracts. Both plans live in `specs/009-orca-yolo/` because 009
owns both the contract and runtime scope. Runtime-phase code lives at
`src/speckit_orca/yolo.py` (new) plus test and integration work.
**Historical brainstorm**: `specs/014-yolo-runtime/brainstorm.md`
(superseded — content preserved for context, runtime plan now
lives here)
**Research inputs**:
- [`docs/research/spec-kitty-execution-loop.md`](../../docs/research/spec-kitty-execution-loop.md)
  (deep-dive research that grounds the harvest decisions)
- [`specs/012-review-model/plan.md`](../012-review-model/plan.md)
  (new review vocabulary the runtime must consume)
- [`docs/refinement-reviews/2026-04-11-product-surface.md`](../../docs/refinement-reviews/2026-04-11-product-surface.md)
  (finish execution before more governance)

---

## 1. Why this is in 009 and not in 014

The original brainstorm (`specs/014-yolo-runtime/brainstorm.md`)
proposed a new 014 spec for the runtime, with 009 staying contract-
only. Per the 2026-04-11 session, that split is rejected: 009's
contracts have never been implemented, so there's no reason to
preserve a contract/runtime separation. Consolidating into 009
keeps the spec directory layout flat and the runtime traceable to
the contracts it implements without an indirection.

The 014 brainstorm doc stays on disk as historical context for
the design discussion, but the authoritative runtime plan is this
file.

## 2. Summary

Build `src/speckit_orca/yolo.py` as the single-lane execution
runtime implementing 009's contracts. The runtime is a **read-only-
decision loop** modeled on spec-kitty's `next` pattern: `yolo next`
computes the next decision from an event-sourced state and returns
a payload to the caller. The caller executes the step and reports
back via `yolo next --result`. Events are appended to a durable
JSONL log; state is materialized by a deterministic reducer.

The runtime supports **both standalone and matriarch-supervised
modes** per 009 FR-013 through FR-019. Standalone = direct operator
interaction. Supervised = Lane Agent Binding active, events dual-
written to the yolo log and the matriarch lane mailbox.

The plan consumes **012's new review vocabulary** (`review-spec`,
`review-code`, `review-pr`) since 012 plan is on main. 009's
existing `run-stage-model.md` contract names the old four-review
vocabulary; that gets collapsed as part of 012's runtime rewrite
and the yolo runtime targets the new vocabulary from day one.

## 3. Resolved answers (from 2026-04-11 session)

The 014 brainstorm's 8 open questions were answered by the user
inline. Binding answers captured here so the plan remains self-
contained:

| # | Question | Resolution |
|---|---|---|
| 1 | New 014 spec vs extend 009 | **Update 009.** 014 does not exist as a separate spec. Runtime lives in 009. |
| 2 | Event log layout | **Per-run directory**: `.specify/orca/yolo/runs/<run-id>/events.jsonl`. |
| 3 | ULID library vs inline | **Inline.** ~40 lines of Python, no new dependency. |
| 4 | Stale-run thresholds | **Configurable with defaults: 3 days `claimed` / 7 days `in-progress`.** |
| 5 | Review vocabulary | **Align with 012's three-review model** (`review-spec`, `review-code`, `review-pr`). Verified against 012 plan section 6. |
| 6 | Cross-mode auto-selection | **Yes.** Call matriarch's cross-pass agent routing per 012's policy (always different agent, prefer highest tier, downgrade only on timeout, no same-agent fallback, no operator override). |
| 7 | Matriarch dual-write | **Yes.** yolo event log is the yolo-local source of truth; matriarch mailbox events are the supervision channel. |
| 8 | Resume drift detection | **Yes, warn on `head_commit_sha` mismatch.** Require operator confirmation, never auto-reconcile. |

**Answer 1 is the structural resolution** that puts this plan in
009's directory rather than 014. Everything else is runtime design.

## 4. Scope

### In scope

- Amend `specs/009-orca-yolo/run-stage-model.md` to use the new
  three-review vocabulary (or confirm it's already updated by the
  012 runtime rewrite when that lands — this plan lands AFTER
  012's runtime rewrite to avoid duplicating the vocabulary
  collapse work)
- New `src/speckit_orca/yolo.py` runtime module
- New `tests/test_yolo.py` test file
- Durable event log at `.specify/orca/yolo/runs/<run-id>/events.jsonl`
- Inline ULID generator (no dependency)
- Deterministic reducer: `reduce(events) → RunState`
- Decision logic: `next_decision(state) → Decision`
- State machine enforcement with explicit transition guards
- Worktree creation at the `implement` stage, cleanup-at-terminal-opt-in
- Resume via event-log replay with snapshot reconciliation
- Stale-run detection via timestamp heuristic (configurable)
- Standalone mode (no matriarch)
- Matriarch-supervised mode with Lane Agent Binding + dual writes
- Cross-pass routing via 012's policy (calls matriarch for agent
  selection)
- `flow_state.py` extension to read yolo run state for features
  that have an active yolo run
- `matriarch.py` extension to consume yolo events in supervised
  mode
- New `commands/yolo.md` stub (prompt body deferred)
- CLI: `yolo start`, `yolo next`, `yolo resume`, `yolo status`,
  `yolo recover`, `yolo cancel`, `yolo list`
- `specs/009-orca-yolo/tasks.md` walk-through: check off the
  tasks the runtime satisfies (T001 spec, T002 run-stage-model,
  T003 run-state, etc.)

### Explicitly out of scope

- **Command prompt body for `commands/yolo.md`.** Stub file only.
  Full prompt written in a follow-up task after the plan and
  contracts land. Same deferral rule as 012 and 013.
- Mission integration branch model — spec-kitty has one, Orca
  does not need it for single-lane
- Acceptance gates on top of review gates — reviews ARE the gates
- Dashboard / kanban UI — platform feature, not a runtime primitive
- Charter / doctrine governance — spec-kitty-specific
- Multi-agent orchestration in yolo — matriarch's job
- Replacing flow-state as the "where is this feature now?"
  aggregator — yolo writes into its event log; flow-state
  continues to be the visible aggregator
- Supporting spec-lite as a yolo start artifact — explicitly
  excluded from v1 per 013 plan
- Supporting adoption records as a yolo start artifact — AR records
  are reference-only per 015 contract, never drivable by any runner
- Heartbeat-based liveness detection — timestamp heuristic only
- **Creating a separate 014 spec directory.** All work lives
  under `specs/009-orca-yolo/`.

## 5. The execution loop shape

### Read-only-decision pattern

```text
yolo start <feature> [--mode standalone|matriarch]
  → read spec + plan + tasks + current run state (from event log)
  → compute next stage per 009's run-stage-model
  → return Decision payload:
      kind: step (execute next) |
            decision_required (human input) |
            blocked (cannot proceed) |
            terminal (run complete)
  → caller executes the step (agent or human)
  → yolo next --result success|failure|blocked [--evidence path]
  → append event to run log (dual-write in supervised mode)
  → loop
```

**Critical**: `yolo next` does NOT dispatch to an agent directly.
It returns what should happen and waits for the caller to report
back. This is the spec-kitty pattern and it's load-bearing for:

- Async operation (agents can be slow, humans can be interrupted)
- Multi-agent handoff (one agent executes, another reports)
- Testability (the decision logic is a pure function of state)
- Crash resilience (if the agent dies mid-execution, the event
  log still has the last authoritative state)

### Stages (009 + 012 vocabulary)

Happy path after 012's review vocabulary collapse:

```text
brainstorm → specify → clarify → review-spec
           → plan → tasks → assign (optional) → implement
           → review-code (phase-level + overall)
           → pr-ready [→ pr-create]
           → review-pr (after merge)
```

**Notable vocabulary changes from 009's original run-stage-model:**

- **Added `clarify`** between `specify` and `review-spec` — spec-
  kit's `/speckit.clarify` is mandatory per the clarify
  integration contract (012 clarify-integration.md)
- **Added `review-spec`** between `clarify` and `plan` — sharpening
  happens, then adversarial cross-pass, then plan
- **`assign` retained as optional** between `tasks` and `implement`
  — aligns with 009's original contract and the `assign` command
- **Collapsed `self-review`/`code-review`/`cross-review`** into
  `review-code` with self/cross as in-artifact subsections
- **`review-pr`** moved to AFTER `pr-create` (not before) because
  it's about processing external PR comments, not gating merge

012's runtime rewrite updates 009's `run-stage-model.md` contract
to match. This runtime plan assumes that update is already
landed — runtime-plan lands AFTER 012's runtime rewrite.

## 6. Event log shape

**File path**: `.specify/orca/yolo/runs/<run-id>/events.jsonl`

**One event per line**, append-only, deterministically ordered by
`(lamport_clock, timestamp, event_id)`.

### Event envelope

Required fields (all events):

- `event_id` — ULID, 26 chars, lex-sortable, generated inline
  (no dependency)
- `run_id` — the yolo run this event belongs to
- `event_type` — enum (see below)
- `timestamp` — RFC3339 UTC, `Z` offset required per
  `010-orca-matriarch/contracts/event-envelope.md`
- `lamport_clock` — integer, monotonic per writer
- `actor` — agent or human identifier (`claude`, `codex`,
  `user:<handle>`, etc.)

Routing fields (populated at run start, copied into every event):

- `feature_id` — spec id being run (e.g., `020-example-feature`)
- `lane_id` — matriarch lane id if supervised mode, else null
- `branch` — git branch the run is on
- `head_commit_sha` — git HEAD at event emission

Payload fields (event-type dependent):

- `from_stage`, `to_stage` — stage transition, may be equal for
  in-stage events
- `reason` — free-text rationale, especially for pause/block/failed
- `evidence` — optional list of artifact paths (test output,
  review artifact, etc.)

### Event type enum

- `run_started` — first event, records mode and initial state
- `stage_entered` — transition into a new stage
- `stage_completed` — successful exit from a stage
- `stage_failed` — exit with failure reason
- `pause` — operator or agent paused the run
- `resume` — operator resumed
- `block` — hard block (missing prereqs, failed gate)
- `unblock` — explicit unblock event, records resolution
- `decision_required` — human input needed (e.g., clarification
  missing, ambiguous spec)
- `cross_pass_requested` — cross-review requested for a review
  artifact, includes requested agent tier
- `cross_pass_completed` — cross-review returned, includes agent
  that actually ran it
- `terminal` — run complete; no further events allowed

### Deduplication

Events with the same `event_id` are deduplicated at read time.
Single-writer-per-run in v1 (the operator), so collisions should
not happen. The dedup rule protects against double-commit bugs
and future multi-writer scenarios.

## 7. State reducer

`reduce(events: list[Event]) → RunState`

**Pure function.** No I/O, no side effects, no external state.
Same input always produces same output.

### RunState shape

```python
@dataclass
class RunState:
    run_id: str
    feature_id: str
    mode: Literal["standalone", "matriarch"]
    lane_id: str | None
    current_stage: str  # e.g. "implement", "review-code"
    outcome: Literal["running", "paused", "blocked", "completed", "failed", "canceled"]
    block_reason: str | None
    last_event_id: str
    last_event_timestamp: str
    branch: str
    head_commit_sha_at_last_event: str
    # Review artifact state derived from events
    review_spec_status: Literal["pending", "in_progress", "complete", "stale"] | None
    review_code_status: Literal["pending", "in_progress", "complete", "stale"] | None
    review_pr_status: Literal["pending", "in_progress", "complete"] | None
    # Supervised-mode fields
    mailbox_path: str | None
    last_mailbox_event_id: str | None
```

### Reduction rules

- Events sorted by `(lamport_clock, timestamp, event_id)`
- Duplicate event_ids dropped
- Each event updates exactly one field group, enforced by a
  match statement per event_type
- Invalid transitions (e.g., `terminal → stage_entered`) silently
  ignored with a warning logged — the reducer never errors, it
  just rejects nonsense
- Stale-mode detection is a post-reduce pass comparing
  `last_event_timestamp` against current wall-clock time

## 8. Decision logic

`next_decision(state: RunState) → Decision`

**Pure function.** Computes what should happen next from the
current state. The caller (agent or human) then executes and
reports back.

### Decision shape

```python
@dataclass
class Decision:
    kind: Literal["step", "decision_required", "blocked", "terminal"]
    next_stage: str | None  # for kind=step
    prompt_text: str  # human-readable instruction
    machine_payload: dict  # structured data for agent consumption
    requires_confirmation: bool  # operator must ack before execution
```

### Decision rules (simplified)

- `outcome == "completed"` → `terminal`
- `outcome == "blocked"` → `blocked` with `block_reason`
- `outcome == "paused"` → `paused` (caller decides to resume or
  cancel)
- Stage == `implement` and `review_code_status == "pending"` →
  `step` pointing at review-code
- Stage == `review-code` and cross pass missing → `step` pointing
  at cross-pass with agent selected via 012's policy (call into
  matriarch)
- Stage == `plan` and `review_spec_status != "complete"` →
  `decision_required` with prompt "review-spec must run before
  plan"
- Stage == `specify` and spec.md has no `## Clarifications` →
  `decision_required` with prompt pointing at `/speckit.clarify`
- Stage == `pr-create` and all reviews complete → `step` pointing
  at PR creation
- All other transitions follow the 009 + 012 run-stage-model

The rules are not exhaustive here; full coverage lives in the
contract file `specs/009-orca-yolo/contracts/decision-rules.md`
(written during the contract-phase follow-up task).

## 9. Worktree isolation

**Rule**: one worktree per yolo run, created at the `implement`
stage, not at `start`.

- **Before `implement`**: yolo runs in the main repo or wherever
  the operator started it. Spec / plan / tasks are in the feature
  dir, not in a worktree.
- **At `implement` stage entry**: yolo calls into
  `scripts/bash/orca-worktree.sh` (or directly into a future
  worktree runtime module) to create a worktree for the feature
  branch and writes its path into the run state. Implement-stage
  events record the worktree path.
- **At `pr-ready` or `pr-create`**: worktree is marked for cleanup
  but NOT eagerly removed. Matches spec-kitty's
  "cleanup-at-merge-not-eager" rule. Preserves evidence if the
  run is blocked or rolled back.
- **At `terminal`**: worktree cleanup is opt-in, not automatic.
  Operator runs `yolo clean <run-id>` or deletes manually.

### Orphan handling

If a run is canceled or blocked while the worktree exists, the
worktree stays on disk. A future `doctor` command detects orphans
and flags them. **No automatic cleanup** — same principle as
spec-kitty, preserves evidence for debugging.

### Stale-claim gotcha

The spec-kitty research flagged stale-claim false positives: a
legitimately-paused agent (waiting for human input) can get
flagged as stale. The runtime mitigates by:

1. **Thresholds are configurable**, not hardcoded
2. **Warn before auto-recovery** — `yolo resume` warns when the
   run is past the threshold, operator must confirm with
   `yolo recover <run-id>` to override
3. **`decision_required` state pauses the stale timer** — runs
   waiting for human input don't age

## 10. Resumability

### `yolo resume <run-id>` read path

1. Read `events.jsonl` from disk
2. Replay through the reducer → compute current `RunState`
3. Compare against materialized `status.json` snapshot — if they
   disagree, event log wins and snapshot is regenerated with a
   warning
4. Validate worktree state (if `implement` stage active):
   - Branch matches expected
   - `head_commit_sha` matches last recorded
   - If mismatch → warn and require operator confirmation
5. Run stale-mode detection against wall-clock
6. Return current `Decision` payload

### Preventing re-execution of completed stages

The reducer produces the correct current stage from event history.
`next_decision` returns the next stage, not the current or previous.
Idempotence is guaranteed by the reducer's determinism.

### What resume does NOT do

- **No heartbeat.** Dead agents are detected by absence of events,
  not by active health check.
- **No automatic recovery of stale claims.** Operator must
  `yolo recover <run-id>` explicitly.
- **No automatic branch reconciliation.** If the worktree branch
  has diverged since the last event, yolo warns but does not
  auto-rebase or auto-merge. Drift is the operator's call.
- **No automatic code validation inside the worktree.** The
  worktree is trusted as-is; if the operator modified code
  outside a yolo event, that modification is preserved and
  carried into the next event.

## 11. Matriarch supervised mode

Per 009 FR-013 through FR-019, when yolo runs in matriarch mode:

- The run carries a **Lane Agent Binding** linking it to a
  matriarch lane (`lane_id` defaults to the primary `spec_id` per
  010 FR-025)
- Blockers, questions, and approval needs route through the Lane
  Mailbox (`specs/010-orca-matriarch/contracts/lane-mailbox.md`)
  rather than prompting the user directly
- Stage advancement emits a matriarch event-envelope entry in
  addition to the yolo event log (**dual write** per answer 7),
  so matriarch's readiness aggregation stays current
- Resume in supervised mode consults matriarch's lane registry
  before acting on local run state alone (FR-018 ownership
  reconciliation). If matriarch says the lane has been reassigned
  to a different agent, yolo refuses to resume without explicit
  operator confirmation.

### Dual-write semantics

When yolo emits an event in supervised mode:

1. Write to `.specify/orca/yolo/runs/<run-id>/events.jsonl` (yolo's
   own log, source of truth for yolo state)
2. Write to matriarch's lane mailbox/report path per 010's
   event-envelope contract (source of truth for matriarch lane state)

**Both writes must succeed** or the event is considered not
emitted. If the yolo log write succeeds but the matriarch write
fails (filesystem error, path doesn't exist, permission issue),
yolo logs a warning and continues but flags the run as
`matriarch_sync_failed`. A future `yolo repair --run <id>`
command replays the missing matriarch writes; not in v1 scope.

### Standalone mode

Standalone mode skips everything in this section. No lane
binding, no mailbox, no dual writes, no lane registry
consultation on resume. `mode` is recorded in the first
`run_started` event and is immutable for the run's lifetime.

## 12. File-by-file change list

### New files

- **`src/speckit_orca/yolo.py`** — main runtime module. Target
  size ~800-1200 LOC. Exports: `RunState`, `Event`, `Decision`,
  `EventType` enum, `reduce()`, `next_decision()`,
  `append_event()`, `load_run()`, `start_run()`, `resume_run()`,
  `cli_main()`.

- **`tests/test_yolo.py`** — test file covering reducer
  determinism, event envelope validation, stage transitions,
  decision rules, resume correctness, stale detection, standalone
  vs supervised mode, cross-pass routing integration.

- **`specs/009-orca-yolo/contracts/event-envelope.md`** —
  runtime event shape contract (separate from 010's event-envelope
  contract which governs matriarch-lane events; this one governs
  yolo-run events but follows the same envelope structure for
  dual-write compatibility)

- **`specs/009-orca-yolo/contracts/decision-rules.md`** — full
  decision rule table mapping (state, context) → Decision

- **`specs/009-orca-yolo/contracts/worktree-lifecycle.md`** —
  when worktrees are created, cleaned up, marked orphan

- **`specs/009-orca-yolo/contracts/resume-protocol.md`** — the
  resume read path, drift detection, stale handling

- **`specs/009-orca-yolo/contracts/supervised-mode.md`** —
  dual-write protocol, matriarch reconciliation rules, failure
  handling

- **`commands/yolo.md`** — **stub only** in this wave. Full
  prompt body deferred.

### Modified files

- **`specs/009-orca-yolo/run-stage-model.md`** — collapses to 012's
  three-review vocabulary. Probably already done as part of 012's
  runtime-rewrite PR; this runtime-plan lands AFTER that.

- **`specs/009-orca-yolo/data-model.md`** — updated with RunState,
  Event, Decision entities

- **`specs/009-orca-yolo/tasks.md`** — check off tasks satisfied
  by the runtime implementation

- **`src/speckit_orca/flow_state.py`** — add reading of yolo run
  status from `.specify/orca/yolo/runs/*/status.json` snapshot.
  Flow-state returns a new optional field `yolo_run` when an
  active run exists for the feature.

- **`src/speckit_orca/matriarch.py`** — add consumer for yolo's
  dual-written events in supervised mode. When yolo writes a
  `block` event to the lane mailbox, matriarch updates the lane's
  blocker state. When yolo transitions to a review stage,
  matriarch updates readiness aggregation.

- **`extension.yml`** — register `speckit.orca.yolo` command
  pointing at the new `commands/yolo.md` stub.

- **`.gitignore`** — add `.specify/orca/yolo/runs/` if runs should
  not be committed (they probably should NOT be committed;
  machine-local ephemeral state). Open question about whether
  `status.json` snapshots are worth committing for collaborator
  resumability.

- **`specs/014-yolo-runtime/brainstorm.md`** — add superseded
  pointer at the top directing future readers to
  `specs/009-orca-yolo/runtime-plan.md`. Don't delete the
  brainstorm content; preserve it as historical context. (This
  edit is in the runtime-plan wave's first commit.)

### Unchanged files (explicitly noted)

- `commands/*.md` (except the new `commands/yolo.md` stub) —
  command prompts unchanged
- `templates/*` — no new templates needed
- `specs/014-yolo-runtime/` — kept as historical context, only
  edited to add the superseded pointer at the top of the
  brainstorm

## 13. Rollout sequence

The runtime implementation is the biggest wave yet. The rollout
is sequenced across multiple PRs because no single PR should
touch all of yolo.py plus flow-state plus matriarch plus tests
plus contracts plus commands.

**Suggested PR sequence:**

### PR A — Contracts and data-model

All new contract files under `specs/009-orca-yolo/contracts/`
that aren't already present, plus updates to `data-model.md`. No
code changes. This is the "lock the shape before writing the
code" PR.

### PR B — Core runtime

New `src/speckit_orca/yolo.py` with `RunState`, `Event`,
`Decision`, event log I/O, reducer, and `next_decision`. No
flow-state or matriarch integration yet. New `tests/test_yolo.py`
covers the core logic in isolation. Runs standalone mode only.

### PR C — flow-state integration

Add the yolo-run-status reading to `flow_state.py`. Doesn't
change yolo.py. Keeps the change surface narrow.

### PR D — matriarch supervised mode

Add dual-write support to yolo.py, add yolo-event consumer to
matriarch.py. Integration tests for the supervised-mode path.

### PR E — worktree lifecycle

Wire yolo.py into `scripts/bash/orca-worktree.sh`. Implement
worktree creation at `implement`, orphan detection, cleanup-at-
terminal-opt-in.

### PR F — commands/yolo.md prompt

The actual command prompt body. Separate PR because prompts are
deferred until contracts are locked, same rule as 012 and 013.

### PR G — 009 tasks reconciliation

Walk 009's 29 tasks and check off what the runtime satisfies.
Small PR, doc-only.

**Six or seven PRs over a few sessions.** Each is reviewable
independently. The core runtime PR (B) is the biggest; the
others are narrower.

## 14. Testing approach

### Unit tests for reducer and decision logic

Reducer and `next_decision` are pure functions → trivially
testable. Target coverage: every event type, every stage, every
transition rule, every edge case (duplicate events, out-of-order
events, invalid transitions, stale state).

### Integration tests for I/O paths

- Event log write/read round-trip
- Resume from event log matches materialized snapshot
- Drift detection triggers warning on head_commit_sha mismatch
- Stale detection fires past configurable thresholds
- Supervised-mode dual writes succeed when mailbox path exists,
  fail gracefully when it doesn't

### Tests specifically NOT in scope for v1

- No multi-writer collision tests — single-writer-per-run in v1
- No network fault injection — runtime is local-only
- No performance benchmarks — correctness first
- No full end-to-end yolo runs against real agents — that's
  manual verification, not automated

## 15. Dependencies and sequencing

### Hard prerequisites

- **012 plan merged** ✅ (PR #29 on main) — provides the review
  vocabulary the runtime consumes
- **`docs/research/spec-kitty-execution-loop.md` on main** ✅
  (PR #28) — research grounding for harvest decisions
- **014 brainstorm on main** ✅ (PR #27) — design discussion
  preserved as historical context, with superseded pointer
  added in this plan's PR

### Soft prerequisites

- **012 contracts merged** — the runtime's review-code event
  integration is cleaner if the artifact shape is locked. Can
  proceed without by stubbing to 012 plan section 6, but
  contracts make it tighter.
- **013 plan merged** — only matters for documentation. 013 does
  not gate the runtime.

### What the runtime blocks

- **Nothing external.** The runtime is the final wave in the
  current upgrade program.

### Suggested sequencing across waves

1. 012 contracts (PR #33 already open, needs review)
2. 013 contracts (independent task, queued)
3. **009 runtime PR A** — contracts + data-model updates under
   `specs/009-orca-yolo/` (needs 012 contracts ideally but not
   strictly)
4. **009 runtime PR B** — core runtime
5. 012 runtime rewrite (flow-state + matriarch + 009 vocabulary
   update)
6. **009 runtime PR C** — flow-state integration (depends on 012
   runtime)
7. **009 runtime PR D** — matriarch integration (depends on 012
   runtime)
8. **009 runtime PR E** — worktree lifecycle
9. **009 runtime PR F** — command prompt
10. **009 runtime PR G** — 009 tasks reconciliation

Realistic timeline: 4-6 sessions of focused work across PRs B
through F. PR A and PR G are quick.

## 16. Success criteria

- `src/speckit_orca/yolo.py` exports a clean public API with
  typed dataclasses for `RunState`, `Event`, `Decision`
- Reducer is deterministic: same event sequence → same state,
  proven by tests
- Duplicate events are deduplicated by `event_id` at read time
- Stage transitions match 009's run-stage-model (updated to
  012's review vocabulary)
- Standalone mode works end-to-end against a real feature
- Supervised mode dual-writes successfully into both yolo's log
  and matriarch's mailbox
- Resume reproduces the correct current state from event log
  replay, regardless of whether `status.json` snapshot is stale
  or missing
- Stale detection fires at configurable thresholds without
  heartbeats
- Cross-pass routing calls into matriarch's agent selection per
  012's policy (no same-agent fallback, highest tier first,
  timeout downgrade recorded)
- Head-commit drift detection warns operator and requires
  confirmation before resume continues
- `yolo recover <run-id>` exists as an explicit override
- All existing tests still pass after the runtime lands
- New tests cover reducer determinism, decision rules, stale
  detection, dual-write paths
- `flow_state.py` reports yolo run status without breaking the
  non-yolo feature-state path
- `matriarch.py` consumes yolo events without breaking the
  non-yolo lane-state path
- 009 tasks.md has its relevant tasks checked off
- `specs/014-yolo-runtime/brainstorm.md` has the superseded
  pointer at the top directing readers to this plan

## 17. Explicit non-goals

- Not creating a separate 014 spec directory for the runtime
- Not supporting multiple concurrent runs per feature — single-
  writer-per-run
- Not supporting multi-agent cross-write to the same event log
- Not heartbeat-based liveness — timestamp heuristic only
- Not auto-recovery of stale claims — explicit operator override
- Not auto-reconciliation of head_commit drift — warn and
  require confirmation
- Not building a dashboard or live kanban
- Not building charter/doctrine governance
- Not building mission integration branch handling
- Not implementing spec-lite as a valid yolo start artifact in v1
- Not implementing adoption records as yolo start artifacts — ever
  (reference-only per 015 contract)
- Not rewriting `commands/yolo.md` prompt body in this plan
  (deferred)
- Not pre-fetching or caching external data for any stage
- Not running yolo itself as a long-lived daemon — each
  `yolo next` is a short-lived command invocation
- Not deleting or rewriting `specs/014-yolo-runtime/brainstorm.md`
  content — only adding a superseded pointer

## 18. Open questions for the contract-writing task

These surface during plan drafting but are properly answered
during PR A (contracts + data-model):

1. **`.specify/orca/yolo/runs/` gitignore**: machine-local or
   committed? My lean: gitignore the directory, but commit the
   `status.json` snapshots so collaborators can resume each
   other's runs if needed. Or just gitignore everything and
   accept runs are local-only.
2. **Event envelope fields list**: the section 6 list is the
   strawman. Any additional required fields? My lean: hold at
   the current list; new fields go into `payload` dict until
   they earn promotion.
3. **Stale threshold defaults in config vs hardcoded**: 3/7 days
   as defaults, but where does the operator configure? My lean:
   a new `.specify/orca/yolo/config.json` file per repo, with a
   documented schema.
4. **Cross-pass agent selection caching**: if matriarch picks
   `codex` for a cross-pass, should yolo cache the choice for
   subsequent passes in the same run? My lean: no caching. Each
   cross-pass goes through the 012 policy fresh. Caching
   introduces a coupling between runs and routing state that
   isn't worth the minor speedup.
5. **Resume across branch checkouts**: if the operator changes
   git branches mid-run (outside yolo), can yolo detect and
   reject the resume? My lean: yes via `head_commit_sha` drift
   detection (answer 8). If the SHA doesn't match, the resume
   warns and requires confirmation.

## 19. Suggested next steps

1. Merge this plan PR (after review)
2. Start **PR A** — contracts + data-model updates under
   `specs/009-orca-yolo/` (new contract files for event envelope,
   decision rules, worktree lifecycle, resume protocol,
   supervised mode; updates to `data-model.md` for the new
   entities)
3. Start **PR B** — core runtime in `src/speckit_orca/yolo.py`
   plus `tests/test_yolo.py`
4. Continue through PRs C-G per the rollout sequence above
5. After PR G merges, 009 tasks.md should be mostly checked off
   and the runtime is live
