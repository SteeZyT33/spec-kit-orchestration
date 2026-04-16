# Tasks: Orca YOLO — Runtime Implementation

**Input**: `specs/009-orca-yolo/runtime-plan.md`, contracts/, data-model.md
**Prerequisites**: spec.md, plan.md, runtime-plan.md, all contracts aligned with 012/013/015
**TDD**: All runtime code follows red-green-refactor. Tests before implementation.

**Organization**: Tasks follow the runtime-plan's PR sequence. Phase 1 (contracts
cleanup) is complete. This file covers Phase 2 (core runtime) through Phase 7.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)

---

## Phase 1: Contract Alignment (Complete)

**Purpose**: Align 009 contracts with shipped 012/013/015 product surface.

- [x] T001 Update `contracts/run-stage-model.md` — add clarify stage, move review-spec before plan, update 006→012 refs, add start artifact restrictions
- [x] T002 [P] Update `spec.md` — replace micro-spec with spec-lite in FR-006, add adoption record exclusion, update FR-007 stage list
- [x] T003 [P] Update `plan.md` — replace 006 dependency with 012, update stage model in Design Decisions, fix verification refs
- [x] T004 [P] Update `contracts/orchestration-policies.md` — add Start Artifact Restrictions section
- [x] T005 [P] Update `data-model.md` — add clarify to Run Stage entity, update review refs to 012
- [x] T006 Update `runtime-plan.md` — add assign back to stage sequence, add adoption exclusion to non-goals
- [x] T007 [P] Update `tasks.md`, `brainstorm.md`, `quickstart.md` — replace remaining 006 and micro-spec refs

**Checkpoint**: All 009 contracts aligned with current product surface. ✓

---

## Phase 2: Core Runtime — Event System (TDD)

**Purpose**: Event envelope, ULID generator, event log I/O. Foundation for everything else.

**Target file**: `src/speckit_orca/yolo.py`
**Test file**: `tests/test_yolo.py`

- [x] T008 RED: Write tests for `EventType` enum (all 12 event types) and `Event` dataclass (required fields, validation, serialization to/from JSON)
- [x] T009 GREEN: Implement `EventType` enum and `Event` dataclass — minimal code to pass T008
- [x] T010 RED: Write tests for inline ULID generator — monotonic, 26-char, lex-sortable, no external dependency
- [x] T011 GREEN: Implement `generate_ulid()` — minimal ~40 LOC inline ULID
- [x] T012 RED: Write tests for event log I/O — `append_event()` writes JSONL, `load_events()` reads back, round-trip fidelity, deduplication by event_id
- [x] T013 GREEN: Implement `append_event()` and `load_events()` — per-run directory at `.specify/orca/yolo/runs/<run-id>/events.jsonl`

**Checkpoint**: Event system works in isolation. Events can be written, read, deduplicated.

---

## Phase 3: Core Runtime — State Reducer (TDD)

**Purpose**: Pure-function reducer that derives RunState from events. The heart of the runtime.

- [x] T014 RED: Write tests for `RunState` dataclass (all fields from runtime-plan section 7)
- [x] T015 GREEN: Implement `RunState` dataclass
- [x] T016 RED: Write reducer determinism tests — same event sequence always produces same RunState
- [x] T017 RED: Write reducer idempotence tests — duplicate events (same event_id) have no effect
- [x] T018 RED: Write stage transition tests — every allowed transition succeeds, every forbidden transition is rejected with warning
- [x] T019 GREEN: Implement `reduce(events) → RunState` — pure function, match statement per event_type, sort by (lamport_clock, timestamp, event_id)
- [x] T020 REFACTOR: Clean up reducer, extract transition guard helpers if needed

**Checkpoint**: Reducer is deterministic and correct. Same events → same state, proven by tests.

---

## Phase 4: Core Runtime — Decision Logic (TDD)

**Purpose**: Pure-function decision engine that computes next step from current state.

- [x] T021 RED: Write tests for `Decision` dataclass (kind enum, fields)
- [x] T022 RED: Write decision rule tests — each (state, context) → expected Decision per runtime-plan section 8
- [x] T023 GREEN: Implement `Decision` dataclass and `next_decision(state) → Decision`
- [x] T024 REFACTOR: Extract decision rules into a table-driven structure if cleaner

**Checkpoint**: Decision logic covers all stage transitions and stop conditions.

---

## Phase 5: Core Runtime — Run Lifecycle (TDD)

**Purpose**: Start, resume, recover, cancel, status, list operations.

- [x] T025 RED: Write tests for `start_run()` — creates run directory, emits `run_started` event, records mode/policies, rejects excluded start artifacts (spec-lite, adoption records)
- [x] T026 GREEN: Implement `start_run()`
- [x] T027 RED: Write tests for `resume_run()` — replays event log, regenerates status.json snapshot if missing. (Drift detection and stale-threshold tests are DEFERRED to the stale-detection PR; what shipped here is replay + snapshot reconciliation only.)
- [x] T028 GREEN: Implement `resume_run()` — event log replay + snapshot regeneration. Head-commit drift detection and stale thresholds (3d/7d) are DEFERRED to the stale-detection PR, not shipped in this PR.
- [ ] T029 RED: Write tests for `recover_run()` — explicit override of stale warning (deferred to stale-detection PR)
- [ ] T030 GREEN: Implement `recover_run()` (deferred to stale-detection PR)
- [x] T031 [P] RED: Write tests for `cancel_run()` — emits terminal event, no further events allowed
- [x] T032 [P] GREEN: Implement `cancel_run()`
- [x] T033 [P] RED: Write tests for `run_status()` and `list_runs()` — reads snapshot, lists all runs
- [x] T034 [P] GREEN: Implement `run_status()` and `list_runs()`
- [x] T035 RED: Write tests for status.json snapshot — materialized from reducer, regenerated on resume if stale
- [x] T036 GREEN: Implement snapshot write/read with staleness detection

**Checkpoint**: Full standalone-mode lifecycle works. Start → next → resume → recover → cancel all tested.

---

## Phase 6: CLI Interface

**Purpose**: Argparse-based CLI for `python -m speckit_orca.yolo`.

- [x] T037 RED: Write tests for CLI arg parsing — `start`, `next`, `resume`, `status`, `recover`, `cancel`, `list` subcommands
- [x] T038 GREEN: Implement `cli_main(argv) → int`

**Checkpoint**: CLI works for standalone mode. All subcommands dispatch correctly.

---

## Phase 7: Command Stub and Registration

**Purpose**: Register yolo in the extension and create command stub.

- [x] T039 Create `commands/yolo.md` stub (prompt body deferred per runtime-plan)
- [x] T040 Register `speckit.orca.yolo` in `extension.yml`
- [x] T041 Verify all existing tests still pass after the runtime lands — 249/249 passed

**Checkpoint**: 009 runtime is integrated into Orca's command surface.

---

### Post-cross-review BLOCKER fixes (codex cross-pass 2026-04-16)

- [x] T042 Add `next_run()` — the authoritative driver loop with `--result success/failure/blocked`
- [x] T043 Add `recover_run()` — explicit operator override for stale/drift
- [x] T044 Add review gates to `next_decision` — block review-spec→plan and review-code→pr-ready until cross_pass_completed
- [x] T045 Fix mode vocabulary — `"matriarch"` → `"matriarch-supervised"`, explicit `mode` parameter in `start_run`
- [x] T046 Reducer rejects illegal stage transitions — only same/forward/backward allowed, unknown stages ignored
- [x] T047 Add retry bound enforcement — `DEFAULT_RETRY_BOUND = 2`, `retry_counts` tracked per stage
- [x] T048 Validate `start_stage` against `STAGES_SET`
- [x] T049 Governance: rewrite `commands/review-code.md` to make cross-harness pass mandatory via `scripts/bash/crossreview.sh`
- [x] T050 Governance: add `before_pr` hook for `scripts/bash/orca-coderabbit-pre-pr.sh`

### Post-Copilot-review fixes (round 4, 2026-04-16)

- [x] T051 `next_decision` semantics fixed — returns decision to execute current_stage (not its successor). Review gate map inverted to stage prerequisites.
- [x] T052 `next_decision` handles `outcome == "canceled"` as terminal (prevents resume of canceled runs)
- [x] T053 `next_run(success)` auto-emits TERMINAL when advancing into a terminal stage (pr-ready, review-pr); keeps snapshot outcome and next_decision in agreement

### Post-verification additions

- [x] T054 Reconcile `context_handoffs.py:CANONICAL_STAGE_IDS` with 012/009 vocabulary. Added `clarify`, `review-spec`, `review-code`, `pr-ready`, `pr-create`, `review-pr`. Legacy 006 names (self-review, code-review, cross-review, pr-review) kept for backward compat so pre-012 handoffs still parse. Updated `TRANSITION_ORDER`, `TRANSITION_REQUIRED_INPUTS`, and `_embedded_search_paths` for the new stages. Added cross-module invariant test: `set(yolo.STAGES) ⊆ set(context_handoffs.CANONICAL_STAGE_IDS)`.

---

## Phase 8: flow-state Integration (PR C from runtime-plan §13)

**Purpose**: Make yolo runs visible through the "state" primitive. flow_state
should discover active runs under `.specify/orca/yolo/runs/*` and report them
as part of the per-feature view.

**Branch**: `009-yolo-integrations` (continuation of 009, not a new spec)

- [x] T055 RED: Tests for `YoloRunSummary` dataclass and `list_yolo_runs_for_feature(repo_root, feature_id)` — finds all runs whose RUN_STARTED event carries the feature_id, returns summaries
- [x] T056 GREEN: Implement `YoloRunSummary` + `list_yolo_runs_for_feature` in `src/speckit_orca/flow_state.py`
- [x] T057 RED: Tests that `FlowStateResult.yolo_runs` is populated when a run exists for the feature; empty list otherwise
- [x] T058 GREEN: Add `yolo_runs: list[YoloRunSummary]` field to `FlowStateResult`; populate in `compute_flow_state`
- [x] T059 GREEN: Update `to_dict` and `to_text` to surface yolo run status in output
- [x] T060 Verify: canceled/failed/completed yolo runs report their terminal state correctly

**Checkpoint**: `uv run python -m speckit_orca.flow_state specs/NNN-feature --format json` includes `yolo_runs` with current stage/outcome.

---

## Phase 9: matriarch Supervised Mode (PR D from runtime-plan §13)

**Purpose**: In `matriarch-supervised` mode, yolo events dual-write to the
lane mailbox, matriarch consumes yolo events to update lane state, and
`resume_run` consults the lane registry before acting on local state alone
(per 009 FR-018).

- [x] T061 RED: Test for `append_event` dual-write — supervised mode events land in matriarch's inbound mailbox
- [x] T062 GREEN: Implement dual-write via `_mirror_event_to_matriarch`; `_YOLO_TO_MATRIARCH_TYPE` maps 9 yolo event types to matriarch's `status`/`blocker`/`question` vocabulary
- [x] T063 RED: Test `append_event` never raises when lane not registered
- [x] T064 GREEN: Graceful degradation via `try/except Exception` in mirror path. Yolo event log is always authoritative.
- [x] T065/T067 Matriarch consumer: NO new code needed. Existing `list_mailbox_events` / `summarize_lane` reads show yolo events alongside operator events. Readiness aggregation derives from mailbox + reports.
- [x] T069 RED: Test `resume_run` raises ValueError when lane owner reassigned
- [x] T070 GREEN: Added `_check_lane_ownership_unchanged` helper; `resume_run` calls it in supervised mode. Standalone mode skipped. `recover_run` bypasses the check (explicit operator override).

**Checkpoint**: Supervised-mode yolo run with a matriarch lane shows
coherent state across both subsystems; resume is safe across ownership
changes.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** (Contract Alignment): Complete ✓
- **Phase 2** (Event System): Complete ✓
- **Phase 3** (Reducer): Complete ✓ — depends on Phase 2 (Event dataclass)
- **Phase 4** (Decision Logic): Complete ✓ — depends on Phase 3 (RunState)
- **Phase 5** (Run Lifecycle): Complete ✓ — depends on Phases 2-4
- **Phase 6** (CLI): Complete ✓ — depends on Phase 5
- **Phase 7** (Command Stub + Registration): Complete ✓ — depends on Phase 6
- **Phase 8** (flow-state Integration, PR C): Complete ✓ — depends on Phase 5
- **Phase 9** (matriarch Supervised Mode, PR D): Complete ✓ — depends on Phase 5 + 010 lane/mailbox contracts

### Parallel Opportunities

- T002-T005 and T007 ran in parallel (Phase 1) ✓
- T031-T034 can run in parallel (cancel and status are independent)
- T010 and T014 can overlap if Event dataclass is extracted early
- Phases 8 and 9 shipped together in a single PR (`009-yolo-integrations`)
  since they share event data, though they could have been separated

### TDD Execution Rule

Every implementation task (GREEN) MUST have its corresponding test task (RED) completed
and verified failing FIRST. No production code without a failing test.

---

## Out of Scope (Deferred to Later PRs)

- Worktree lifecycle + head_commit_sha drift detection (PR E)
- Full operator-facing prompt body in `commands/yolo.md` (PR F)
- Tasks reconciliation pass (PR G)
- Stale-run threshold warnings (3d/7d) in `resume_run`
- Spec-lite as a valid start artifact (permanently out of scope in v1)
