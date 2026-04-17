# Tasks: Orca Flow State

**Input**: Design documents from `/specs/005-orca-flow-state/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), brainstorm.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: This feature uses verification-driven development. Add deterministic helper smoke checks and use the quickstart scenarios as the primary end-to-end validation path.

**Organization**: Tasks are grouped by user story so flow state can be delivered incrementally: state computation first, review-stage separation second, ambiguity handling third, and reusable system contracts fourth.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g. US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the feature artifacts and align the repo on the flow-state scope.

- [X] T001 Review `specs/005-orca-flow-state/spec.md`, `specs/005-orca-flow-state/plan.md`, and `specs/005-orca-flow-state/contracts/` for implementation readiness before editing code
- [X] T002 [P] Review `docs/orca-harvest-matrix.md`, `specs/004-orca-workflow-system-upgrade/spec.md`, and `specs/006-orca-review-artifacts/spec.md` against the flow-state contract and note any assumptions that must stay explicit during implementation
- [X] T003 [P] Create or identify fixture-like feature states for quickstart validation under `specs/005-orca-flow-state/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the deterministic state model and evidence interpretation layer all consumer behavior depends on

**⚠️ CRITICAL**: No user story work should begin until this phase is complete

- [X] T004 Create `src/speckit_orca/flow_state.py` with canonical stage definitions and core state-model types
- [X] T005 Implement evidence inventory helpers in `src/speckit_orca/flow_state.py` for `spec.md`, `plan.md`, `tasks.md`, review artifacts, brainstorm links, and contextual worktree metadata
- [X] T006 Implement milestone and review-milestone interpretation helpers in `src/speckit_orca/flow_state.py`
- [X] T007 Implement ambiguity classification and next-step inference helpers in `src/speckit_orca/flow_state.py`
- [X] T008 Add a direct smoke-test entrypoint or callable verification surface in `src/speckit_orca/flow_state.py` for computing state over representative feature directories

**Checkpoint**: Orca has a deterministic flow-state computation helper with stable stage, milestone, ambiguity, and next-step semantics.

---

## Phase 3: User Story 1 - Resume A Feature Reliably (Priority: P1) 🎯 MVP

**Goal**: Allow Orca to compute current stage and next-step guidance from durable workflow artifacts without depending on chat history.

**Independent Test**: Use features with partial artifact sets and verify Orca can compute current stage plus next likely step from artifact evidence alone.

### Implementation for User Story 1

- [X] T009 [US1] Implement feature-level flow-state computation in `src/speckit_orca/flow_state.py` using durable artifacts as primary truth
- [X] T010 [US1] Implement current-stage resolution and next-step guidance in `src/speckit_orca/flow_state.py` for pre-spec, planning, tasking, implementation, and review-adjacent states
- [X] T011 [US1] Define the machine-readable and human-readable `FlowStateResult` output contract in `src/speckit_orca/flow_state.py` and `specs/005-orca-flow-state/contracts/flow-state-contract.md`
- [X] T012 [US1] Run helper smoke verification for early-stage and partial-state scenarios via `uv run python -m py_compile src/speckit_orca/flow_state.py` and direct helper checks in `src/speckit_orca/flow_state.py`
- [X] T013 [US1] Manually verify quickstart Scenario 1 using `specs/005-orca-flow-state/quickstart.md`

**Checkpoint**: Orca can resolve current stage and next-step guidance from durable feature artifacts.

---

## Phase 4: User Story 2 - Track Review Completion Separately From Build Progress (Priority: P1)

**Goal**: Report review progress as its own signal rather than folding it into generic implementation progress.

**Independent Test**: Use features with review evidence separate from build progress and verify Orca reports review milestones independently.

### Implementation for User Story 2

- [X] T014 [US2] Implement review-milestone resolution in `src/speckit_orca/flow_state.py` for spec, plan, code, cross, PR, and self-review stages
- [X] T015 [US2] Update `specs/005-orca-flow-state/contracts/stage-model.md` and `specs/005-orca-flow-state/contracts/state-evidence.md` to reflect the implemented review-milestone interpretation rules exactly
- [X] T016 [US2] Ensure `src/speckit_orca/flow_state.py` keeps implementation progress and review progress as separate outputs in the computed state result
- [X] T017 [US2] Manually verify quickstart Scenarios 2 and 4 using `specs/005-orca-flow-state/quickstart.md`

**Checkpoint**: Review completion is visible as a first-class part of workflow state instead of being conflated with build completion.

---

## Phase 5: User Story 3 - Gracefully Handle Partial Or Ambiguous Artifact Sets (Priority: P2)

**Goal**: Keep flow state trustworthy when artifact sets are incomplete, conflicting, or only partially informative.

**Independent Test**: Remove or conflict expected evidence and verify Orca reports partial or ambiguous state explicitly instead of inventing certainty.

### Implementation for User Story 3

- [X] T018 [US3] Implement partial-state handling in `src/speckit_orca/flow_state.py` for missing workflow artifacts
- [X] T019 [US3] Implement explicit ambiguity output in `src/speckit_orca/flow_state.py` for conflicting workflow signals and later-stage evidence with earlier-stage gaps
- [X] T020 [US3] Ensure `src/speckit_orca/flow_state.py` treats worktree metadata as contextual evidence rather than primary truth
- [X] T021 [US3] Manually verify quickstart Scenarios 3 and 5 using `specs/005-orca-flow-state/quickstart.md`

**Checkpoint**: Flow state degrades safely and transparently when the artifact picture is incomplete or conflicted.

---

## Phase 6: User Story 4 - Provide A Stable State Model For Later Orca Systems (Priority: P2)

**Goal**: Establish a reusable state-model contract that later Orca systems can consume without redefining workflow semantics.

**Independent Test**: Inspect the implemented contract and verify it exposes stable stage, milestone, ambiguity, and next-step semantics for later consumers.

### Implementation for User Story 4

- [X] T022 [US4] Add thin optional resume/cached-guidance metadata support in `src/speckit_orca/flow_state.py` only where it can remain secondary to artifact truth
- [X] T023 [US4] Document the persisted-metadata boundary and recomputation rules in `specs/005-orca-flow-state/contracts/state-evidence.md` and `specs/005-orca-flow-state/plan.md`
- [X] T024 [US4] Update immediate consumer-facing docs or references in `commands/assign.md`, `commands/cross-review.md`, `commands/pr-review.md`, or `commands/self-review.md` only where the shared flow-state contract needs to be acknowledged
- [X] T025 [US4] Update `docs/orca-harvest-matrix.md` and `specs/004-orca-workflow-system-upgrade/spec.md` if the implemented flow-state contract sharpens the program-level dependency wording materially
- [X] T026 [US4] Align `specs/007-orca-context-handoffs/spec.md` references to the implemented flow-state stage vocabulary if the final contract clarifies transition semantics

**Checkpoint**: Orca has a reusable flow-state contract with a narrow persisted-metadata boundary ready for later consumers.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency, validation, and documentation across the feature

- [X] T027 [P] Reconcile `specs/005-orca-flow-state/contracts/` with the final implemented helper behavior in `src/speckit_orca/flow_state.py`
- [X] T028 Run the full quickstart validation flow in `specs/005-orca-flow-state/quickstart.md` and record verification evidence in `specs/005-orca-flow-state/tasks.md` or commit notes
- [X] T029 [P] Run final syntax and packaging verification for touched code via `uv run python -m py_compile src/speckit_orca/flow_state.py`, `uv run --with build python -m build`, and `git diff --check`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on User Story 1 because review-stage separation sits inside the computed state result
- **User Story 3 (Phase 5)**: Depends on User Story 1 and benefits from User Story 2 milestone structure
- **User Story 4 (Phase 6)**: Depends on User Stories 1 through 3 because it codifies the stable reusable contract
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Starts after Foundational and delivers the MVP
- **User Story 2 (P1)**: Builds on the computed state result from US1
- **User Story 3 (P2)**: Builds on US1 state computation and US2 milestone separation
- **User Story 4 (P2)**: Builds on the implemented state model from prior stories

### Within Each User Story

- Evidence collection before interpretation
- Stage resolution before next-step guidance
- Review-milestone separation before review-state validation
- Ambiguity handling before final contract stabilization
- Thin persisted metadata only after computed-first behavior is working

### Parallel Opportunities

- T002 and T003 can run in parallel during Setup
- T005, T006, and T007 can run in parallel once T004 establishes `src/speckit_orca/flow_state.py`
- T027 and T029 can run in parallel during Polish

---

## Parallel Example: User Story 1

```bash
# Parallel near the end of US1:
Task: "Define the machine-readable and human-readable FlowStateResult output contract"
Task: "Run helper smoke verification for early-stage and partial-state scenarios"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup
2. Complete Foundational helper layer
3. Complete User Story 1 state computation and next-step guidance
4. Stop and validate that Orca can resolve flow state from durable artifacts

### Incremental Delivery

1. Deliver computed stage and next-step resolution
2. Add review-milestone separation
3. Add ambiguity-safe handling for partial/conflicting artifacts
4. Add thin persisted metadata boundaries and consumer-facing contract updates
5. Finish with docs and full verification

### Out Of Scope In This Feature

- full `orca-yolo` run orchestration
- a visible statusline/dashboard as the main deliverable
- redesigning all review artifacts inside this feature
- making worktree metadata the primary workflow truth

---

## Notes

- Artifact truth matters more than runtime convenience
- Ambiguity is a valid output, not a failure to think hard enough
- This feature should define the shared workflow vocabulary that later Orca systems reuse

## Verification Evidence

- `uv run python -m py_compile src/speckit_orca/flow_state.py`
- `uv run python -m speckit_orca.flow_state specs/005-orca-flow-state/fixtures/repo/specs/101-early-stage --repo-root specs/005-orca-flow-state/fixtures/repo --format text`
- `uv run python -m speckit_orca.flow_state specs/005-orca-flow-state/fixtures/repo/specs/102-implementation-ahead --repo-root specs/005-orca-flow-state/fixtures/repo --format text`
- `uv run python -m speckit_orca.flow_state specs/005-orca-flow-state/fixtures/repo/specs/103-ambiguous --repo-root specs/005-orca-flow-state/fixtures/repo --format text`
- `uv run python -m speckit_orca.flow_state specs/005-orca-flow-state/fixtures/repo/specs/104-review-separated --repo-root specs/005-orca-flow-state/fixtures/repo --format text`
- `uv run python -m speckit_orca.flow_state specs/005-orca-flow-state/fixtures/repo/specs/105-worktree-aware --repo-root specs/005-orca-flow-state/fixtures/repo --format text --write-resume-metadata`
- `uv run --with build python -m build`
- `git diff --check`

## Consumer Alignment Notes

- Reviewed `docs/orca-harvest-matrix.md`, `specs/004-orca-workflow-system-upgrade/spec.md`, `specs/006-orca-review-artifacts/spec.md`, and `specs/007-orca-context-handoffs/spec.md` from the planning worktree while implementing this isolated lane.
- No additional wording changes were required there to keep `005` aligned. The implemented stage vocabulary and persisted-metadata boundary fit the existing umbrella and handoff direction without redefining their scope.
