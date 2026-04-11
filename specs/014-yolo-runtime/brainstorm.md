# Brainstorm: Orca YOLO Runtime — Single-Lane Execution Driver

**Feature Branch**: `014-yolo-runtime`
**Created**: 2026-04-11
**Status**: Brainstorm
**Relationship to 009**: `009-orca-yolo` is the **contract layer**
(spec, run-stage-model, run-state, orchestration-policies, Lane Agent
Binding). `014-yolo-runtime` is the **implementation** on top of those
contracts. 009 stays as the authoritative contract; 014 adds the
runtime module, tests, and durable event log.
**Informed by**:
- `docs/research/spec-kitty-execution-loop.md` (deep-dive on spec-kitty's execution loop)
- `specs/009-orca-yolo/` (contracts, data-model, tasks — 0/29 tasks completed, runtime unbuilt)
- `docs/refinement-reviews/2026-04-11-product-surface.md` (GPT Pro: finish execution before more governance)

---

## Problem

`009-orca-yolo` has shipped its contracts and vocabulary — stage
model, run state, orchestration policies, Lane Agent Binding for
supervised mode — but **zero runtime code exists**. The
`specs/009-orca-yolo/tasks.md` shows 0 of 29 tasks completed. Every
other major spec (001, 002, 005, 006, 007, 008, 010, 011) has
shipped runtime. 009 is the last gap, and the roadmap calls it out
as the next high-leverage move.

The refinement review explicitly prioritized this: *"finish the
everyday execution story before adding more meta-layers."*

## Proposed Approach

Build `src/speckit_orca/yolo.py` (or similar) as a resumable
single-lane execution runner that:

1. **Implements 009's contracts faithfully** — run state, stage
   model, orchestration policies, Lane Agent Binding. No new
   vocabulary unless 009 needs amendment.
2. **Harvests spec-kitty's execution-loop primitives** where they
   genuinely fit (see "Harvest from spec-kitty" below). Where they
   don't fit, builds fresh.
3. **Writes its own durable event log** (append-only JSONL) — this
   is Orca's first event-sourced state and will set the pattern for
   later event-log work in other subsystems if that ever happens.
4. **Works in both standalone mode AND matriarch-supervised mode**
   per 009 FR-013 through FR-019. Matriarch integration is via Lane
   Agent Binding when supervised, direct operator commands when
   standalone.
5. **Stops on clear signals** — failed review gates, unresolved
   clarification, missing prerequisites — and records why. No
   unbounded fix loops.

## The execution loop shape

Modeled on spec-kitty's `next` pattern but with Orca vocabulary and
Orca's existing primitives.

### Core loop

```
yolo start <feature> [--mode standalone|matriarch]
  → read spec + plan + tasks + current run state
  → compute next stage per run-stage-model
  → return decision payload:
      kind: step (execute next) |
            decision_required (human input) |
            blocked (cannot proceed) |
            terminal (run complete)
  → caller executes the step (agent or human)
  → yolo next --result success|failure|blocked
  → append event to run log
  → loop
```

**Key design point: the loop is read-only-decision, not
blocking-execution.** `yolo next` returns what should happen and
waits for the caller to report back. This matches spec-kitty's
pattern and is critical for:

- Async-friendly operation (agents can be slow)
- Multi-agent handoff (one agent executes, another reports)
- Easy testability (the decision logic is a pure function of state)
- Crash resilience (if the agent dies mid-execution, the event log
  still has the last authoritative state)

### Stages (from 009's run-stage-model)

Happy path (unchanged from 009 contract):

```
brainstorm → specify → plan → tasks → implement
  → self-review → code-review → cross-review → pr-ready [→ pr-create]
```

**Note on review stage collapse**: if `012-review-model` ships before
014 runtime, the review stages collapse to `review-spec → review-code
→ review-pr` per 012. 014 runtime must consume 009's current
vocabulary at brainstorm time but be prepared to adopt 012's
vocabulary once 012 lands. Sequencing section below covers this.

## Durable event log shape

**File**: `.specify/orca/yolo/runs/<run-id>/events.jsonl`
**Shape**: append-only JSONL, one event per line

### Event envelope (harvested from spec-kitty, adapted)

Required fields:
- `event_id` — ULID, 26 chars, monotonic, lex-sortable
- `run_id` — the run this event belongs to
- `event_type` — enum: `stage_entered` | `stage_completed` | `stage_failed` | `pause` | `resume` | `block` | `unblock` | `decision_required` | `terminal`
- `timestamp` — RFC3339 UTC (`Z` offset, per 010 event-envelope.md)
- `lamport_clock` — integer, monotonic per writer
- `actor` — agent or human identifier (`claude`, `codex`, `user`, etc.)

Routing fields:
- `feature_id` — spec id being run (e.g., `014-yolo-runtime`)
- `lane_id` — matriarch lane id if supervised, else empty
- `branch` — current git branch
- `head_commit_sha` — current HEAD commit

Payload:
- `from_stage`, `to_stage` — stage transition (may be equal for in-stage events)
- `reason` — free-text rationale, especially for pause/block/failed
- `evidence` — optional list of artifact paths proving the transition (test output, review file, etc.)

**Deduplication**: events with the same `event_id` are deduplicated
at read time. Single-writer-per-run in v1, so collisions shouldn't
happen, but the dedup rule protects against double-commit bugs.

### Reducer

Single pure function: `reduce(events) → RunState`

- Reads the event log in `(lamport_clock, timestamp, event_id)` order
- Applies each event to a `RunState` dataclass
- Returns the current state
- Same events always produce the same state (deterministic)

**The materialized `status.json` snapshot is derived, not
authoritative.** It can be regenerated from the event log at any
time. Readers prefer the snapshot for speed, but the event log is
the source of truth.

## Worktree isolation

**Rule**: one worktree per yolo run, created at the `implement`
stage, not at `start`.

- **Before `implement`**: yolo runs in the main repo or wherever
  the operator started it. Spec / plan / tasks are in the feature
  dir, not in a worktree.
- **At `implement`**: yolo creates (or delegates to
  `scripts/bash/orca-worktree.sh`) a feature worktree and writes
  its path into the run state. The run's implement stage executes
  inside the worktree.
- **At `pr-ready` or `pr-create`**: the worktree is marked for
  cleanup but not eagerly removed. Matches spec-kitty's
  "cleanup-at-merge-not-eager" rule — preserves evidence if the run
  is blocked or rolled back.
- **At `terminal`**: worktree is cleaned up if the operator opts in
  explicitly. Default is to leave it and let the operator decide.

**Orphaned worktrees**: if a run is canceled or blocked while the
worktree exists, the worktree stays. Doctor command detects and
flags.

## Resumability

**Read path** on `yolo resume <run-id>`:

1. Read `events.jsonl` from disk
2. Replay through the reducer to compute current `RunState`
3. Compare against materialized `status.json` — if they disagree,
   event log wins and `status.json` is regenerated with a warning
4. Validate the worktree state (if `implement` stage): branch
   matches expected, head commit matches last recorded, no
   uncommitted changes unless last event was `pause`
5. Return the current decision payload

**Stale-run detection**: if the last event timestamp is older than a
threshold (configurable, default 7 days for `claimed`-equivalent
stages, 14 days for `in_progress`-equivalent stages), yolo warns
before resuming and asks the operator to confirm. This is the
spec-kitty stale-claim heuristic adapted to Orca vocabulary.

**Idempotence**: resume never re-executes completed stages. The
reducer produces the correct current stage from the event history,
and `yolo next` returns the decision for that stage — not the
previous stage.

**What resume does NOT do**:
- No heartbeat mechanism. Dead agents are detected by absence of
  events, not by an active liveness check
- No automatic recovery of stale claims. Operator must explicitly
  `yolo recover <run-id>` if they want to override the stale warning
- No code validation inside the worktree. If the worktree's branch
  diverged since the last event, yolo warns but does not try to
  reconcile — the operator inspects and decides

## Matriarch supervised-mode integration

Per 009 FR-013 through FR-019, when yolo runs in matriarch-supervised
mode:

- The yolo run carries a `Lane Agent Binding` linking it to a
  matriarch lane (`lane_id` defaults to the primary `spec_id` per
  010 FR-025)
- Blockers, questions, and approval needs route through the Lane
  Mailbox (`specs/010-orca-matriarch/contracts/lane-mailbox.md`)
  rather than prompting the user directly
- Stage advancement emits a matriarch event-envelope entry in
  addition to the yolo event log, so matriarch's readiness
  aggregation stays current
- Resume in supervised mode consults matriarch's lane registry
  before acting on local run state alone (FR-018 ownership
  reconciliation)

**Standalone mode** skips all of the above. Direct operator
interaction, no mailbox, no lane registry.

The mode is **explicit at `yolo start`** (`--mode standalone |
matriarch`) and recorded in the first event. Changing mode
mid-run requires an explicit `yolo reassign` operation that emits
a lane ownership change event.

## Harvest from spec-kitty (the adopt/adapt/reject summary)

From `docs/research/spec-kitty-execution-loop.md`:

### Adopt verbatim

1. **Append-only JSONL event log** — canonical, git-friendly,
   auditable, already aligned with Orca's 010 event-envelope.md
2. **Deterministic merge algorithm** — concat → dedupe → sort →
   reduce. Critical for resume correctness and multi-agent safety
3. **Lamport clock + ULID event IDs** — deterministic ordering, no
   manual clock assignment
4. **Stale-claim detection via timestamp heuristic** — simple, no
   heartbeat overhead; configurable thresholds

### Adapt

1. **State machine enforcement** — spec-kitty uses a centralized
   reducer with guards. Orca's 009 run-stage-model is already a
   state machine; 014 runtime wires it up with explicit guards and
   clear error messages for invalid transitions
2. **Worktree-at-implement isolation** — spec-kitty creates
   worktrees at `claimed → in_progress`. Orca creates at `implement`
   stage entry. Same intent, different vocabulary
3. **Resume via event-log replay** — same pattern, but Orca's
   replay also reconciles with `status.json` snapshot and with
   matriarch lane state in supervised mode

### Reject

1. **Charter / doctrine governance** — spec-kitty-specific surface
   that conflicts with Orca's product-surface simplification
2. **Dashboard kanban** — platform feature, not a runtime primitive
3. **Acceptance gates on a mission integration branch** — out of
   scope for Orca's single-lane runner. Orca's reviews run against
   the feature branch directly, not a mission branch

## Downstream impact

### `src/speckit_orca/yolo.py` (new file)

Main runtime module. Core classes and functions:

- `RunState` (dataclass, matches 009 run-state.md contract)
- `YoloRun` (higher-level wrapper with lane binding, policies)
- `Event` (event envelope dataclass)
- `reduce(events: list[Event]) → RunState` — pure function
- `next_decision(state: RunState) → Decision` — pure function
- `append_event(run_id, event) → None` — I/O
- `load_run(run_id) → (RunState, events)` — I/O
- `start_run(feature_id, mode, ...) → run_id` — I/O
- `resume_run(run_id) → Decision` — I/O with validation
- `cli_main(argv) → int` — argparse-based CLI

**Target size**: ~800-1200 LOC. Comparable to 011 evolve (783 LOC)
and 007 context_handoffs (633 LOC), smaller than 010 matriarch
(1462 LOC) because yolo is single-lane and delegates coordination
to matriarch.

### `tests/test_yolo.py` (new file)

Coverage targets:
- Event envelope validation
- Reducer determinism (same events → same state)
- Reducer idempotence (duplicate events have no effect)
- Stage transitions (each allowed, each forbidden)
- Resume correctness (replay event log → current state matches)
- Stale detection (timestamp heuristic)
- Standalone mode (no matriarch)
- Supervised mode (lane binding, mailbox events)
- Blocked / terminal stopping conditions

### `src/speckit_orca/flow_state.py`

- New `run_status` field reporting yolo run state for features that
  have an active yolo run
- Reads from `.specify/orca/yolo/runs/*/status.json` (snapshot,
  regenerated by yolo runtime)

### `src/speckit_orca/matriarch.py`

- New consumer for yolo run events in supervised mode
- When a yolo run emits a `block` event, matriarch updates the
  lane's blocker state
- When a yolo run transitions into `review-ready` stages, matriarch
  updates readiness aggregation

### `commands/yolo.md` (new)

- `yolo start <feature>` — begin a new run
- `yolo next [--result]` — advance or report
- `yolo resume <run-id>` — resume from event log
- `yolo status [<run-id>]` — show current state
- `yolo recover <run-id>` — override stale warning
- `yolo cancel <run-id>` — terminate
- `yolo list` — list all runs
- Prompt rewrite happens after brainstorm and plan are approved.

### `specs/009-orca-yolo/tasks.md`

- Walk through the 29 tasks and check off the ones that 014 runtime
  satisfies. Some will be genuinely completed by 014; others (manual
  verification, quickstart validation) need follow-through.

### Integration with 012-review-model

If `012-review-model` merges before 014 runtime ships, the 014
runtime consumes the new three-review vocabulary
(`review-spec`, `review-code`, `review-pr`) instead of 009's
current four-review names. Open question covered in the sequencing
section below.

## Open questions (to resolve before plan.md)

1. **New file vs extend 009**: should this be `014-yolo-runtime/` as
   a new spec, or a runtime phase added to `009-orca-yolo/`? My
   lean: new 014 spec because 009 is contract-only and the runtime
   is a substantial implementation deserving its own
   spec+plan+tasks. 014 depends on 009 but is not a replacement.

2. **Event log location**: `.specify/orca/yolo/runs/<run-id>/events.jsonl`
   per run, or `.specify/orca/yolo/events.jsonl` global and
   `run_id`-tagged? My lean: per-run directory, matches spec-kitty's
   per-feature layout, easier to inspect one run at a time.

3. **ULID library vs implement**: Orca has no ULID dependency. Do
   we add one (small, pure-Python, e.g. `python-ulid`), or implement
   a minimal ULID generator inline? My lean: implement inline —
   ULID is ~40 lines of Python, adding a dependency for 40 lines is
   wrong.

4. **Stale-run thresholds**: spec-kitty uses 7 days / 14 days. Is
   that right for Orca's single-operator use case, or should it be
   shorter (1 day / 3 days)? My lean: configurable with a default
   of 3 days for claimed-equivalent, 7 days for in-progress. Most
   Orca operators come back within a session.

5. **Review vocabulary**: if 012-review-model lands before 014
   runtime, yolo adopts the new vocabulary. If not, yolo uses 009's
   four-review names initially. Which do we assume? My lean: design
   014 plan/contracts assuming 012 has landed. If the sequencing
   slips, rewrite 014's plan. Cleaner than building for 009's
   vocabulary and then migrating.

6. **Cross-mode selection**: when yolo enters a review stage that
   supports cross-mode (per 012's model), does yolo automatically
   pick a different agent than the one that ran the implement
   stage? My lean: yes, automatic but with explicit override, same
   as spec-kitty's implicit routing plus Orca's agent-selection
   contract from 003-cross-review-agent-selection.

7. **Matriarch delegation**: in supervised mode, does yolo write
   events to BOTH the yolo event log AND matriarch's lane mailbox?
   My lean: yes, dual-write with yolo's event log as the primary.
   Matriarch reads from its own mailbox; yolo reads from its own
   event log. Dual-writes are cheap and avoid coupling.

8. **Resume after manual intervention**: if an operator manually
   edits the worktree or the event log between yolo sessions, does
   resume detect the drift and warn? My lean: yes — compare the
   recorded `head_commit_sha` against current, warn if different,
   let the operator decide.

## Explicit non-goals

- Not building a mission-integration-branch model (spec-kitty has
  one; Orca does not need one for single-lane)
- Not building acceptance gates on top of review gates (reviews are
  the gates; "acceptance" is a spec-kitty concept)
- Not building a dashboard or live kanban UI
- Not building a charter / doctrine governance surface
- Not building multi-agent orchestration in the runtime — that's
  matriarch's job
- Not replacing `flow_state.py`'s "where is this feature now?"
  query. yolo is *one* data source for flow-state; flow-state stays
  the visible aggregator
- Not building yolo for `spec-lite` records in v1 — 013 spec-lite
  is intentionally out of yolo's scope
- Not rewriting `commands/yolo.md` in this brainstorm — prompt
  rewrite after plan and contracts land

## Sequencing with other in-flight work

This is important because 014 has more dependencies than 012 or 013.

### Hard prerequisites (must merge before 014 plan.md)

- **PR #23** (deployment-readiness cleanup) — provides
  lane_id/spec_id path-traversal validators that yolo will use
- **PR #24** (product-surface refinement) — establishes the
  "intake, state, review, lanes" framing yolo must fit under
- **PR #25** (012-review-model brainstorm approved and spec'd) —
  014 plan assumes the new review vocabulary is decided. If 012 is
  rejected or reshaped, 014 plan needs a rewrite

### Soft prerequisites (nice-to-have before 014 plan.md)

- **PR #26** (013-spec-lite brainstorm approved) — 014 can
  explicitly opt spec-lite out of yolo in v1
- **010-matriarch partial-v1 refinements** — drift flag, explicit
  `CheckoutTarget`, etc. — 014 runtime will exercise these
  interfaces and may surface gaps

### Independent of 014 timing

- PR #2 (ci/add-pytest-step) — provides pytest in CI, which 014's
  ~800-1200 LOC and test file will benefit from
- v1.4.1 tag — unrelated

**Recommended sequence**:

1. PR #23, #24, #25, #26 all merged (cleanup + refinement + 012 + 013
   brainstorms approved)
2. 012-review-model plan and contracts drafted (breaking change to
   006 and 009's review vocabulary)
3. 014 plan drafted, consuming 012's new vocabulary
4. 014 contracts and data-model drafted
5. 014 runtime implementation (this is the big module)
6. 014 tests
7. 012 and 014 ship together as a breaking wave (atomic)
8. Post-ship: matriarch v1.1 refinements, any 013 implementation work

This sequencing puts 014 runtime at roughly two waves out — probably
3-5 sessions of focused work after the brainstorms merge, depending
on how 012 and 013 land.

## Suggested next steps

1. Review this brainstorm and answer the eight open questions
2. Review the `docs/research/spec-kitty-execution-loop.md` research
   notes shipped in this same PR for context grounding
3. Merge PR #23, #24, #25, #26 in sequence so the 014 plan has a
   stable base
4. Write `specs/012-review-model/plan.md` and contracts so 014 can
   consume them
5. Write `specs/014-yolo-runtime/plan.md` with the runtime shape,
   event log contract, and sequencing. Reference the research notes
   for spec-kitty harvest decisions
6. Write `specs/014-yolo-runtime/data-model.md` and contract files
7. Implement `src/speckit_orca/yolo.py`
8. Write `tests/test_yolo.py`
9. Rewrite `commands/yolo.md` prompt
10. Walk 009's tasks.md and check off what 014 runtime satisfies
