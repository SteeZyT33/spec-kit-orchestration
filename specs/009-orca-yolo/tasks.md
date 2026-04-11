# Tasks: Orca YOLO

**Input**: Design documents from `/specs/009-orca-yolo/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: This feature uses contract validation, document-level workflow checks, and later runtime validation if thin orchestration helpers are introduced.

**Organization**: Tasks are grouped by user story so `orca-yolo` can be delivered incrementally: first the stage and run-state model, then resume/start policy, then downstream completion and PR-ready orchestration.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g. US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Align `009` with the upgrade program and all upstream workflow primitives before refining orchestration behavior.

- [ ] T001 Review `specs/009-orca-yolo/spec.md`, `specs/009-orca-yolo/brainstorm.md`, and `specs/009-orca-yolo/plan.md` for scope and dependency clarity
- [ ] T002 [P] Review `specs/004-orca-workflow-system-upgrade/` and `docs/orca-harvest-matrix.md` so `009` stays aligned with the repomix-driven program
- [ ] T003 [P] Review `specs/005-orca-flow-state/`, `specs/006-orca-review-artifacts/`, `specs/007-orca-context-handoffs/`, and `specs/008-orca-capability-packs/` for upstream contracts `009` must consume

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the stage model, run-state model, and orchestration policy surface all later work depends on

**⚠️ CRITICAL**: No user story work should begin until the core orchestration contracts are coherent

- [ ] T004 Refine `specs/009-orca-yolo/contracts/run-stage-model.md` to define the minimum stage vocabulary and progression rules
- [ ] T005 Implement `specs/009-orca-yolo/contracts/run-state.md` so resume and outcomes have a durable contract
- [ ] T006 Implement `specs/009-orca-yolo/contracts/orchestration-policies.md` so ask/start/resume/retry/PR behavior is explicit
- [ ] T007 Update `specs/009-orca-yolo/data-model.md` so run entities and policy entities match the contracts exactly
- [ ] T007a Cross-check `specs/009-orca-yolo/` against `specs/010-orca-matriarch/contracts/lane-mailbox.md`, `event-envelope.md`, `tmux-deployment.md`, and `matriarch-command-surface.md` to confirm supervised-mode fields and behavior match matriarch vocabulary exactly.
- [ ] T007b Confirm the Lane Agent Binding entity in `specs/009-orca-yolo/data-model.md` carries no state that duplicates matriarch's lane registry, so supervised-mode state is referenced by id, not copied.

**Checkpoint**: `009` has a stable stage model, run-state contract, and orchestration-policy contract, and supervised-mode behavior references `010` contracts by name rather than redefining them.

---

## Phase 3: User Story 1 - Run A Full Feature Pipeline With Controlled Intervention (Priority: P1) 🎯 MVP

**Goal**: Let a user start from a durable brainstorm or spec artifact and run through the full workflow with explicit pauses when needed.

**Independent Test**: Start from a durable upstream artifact and verify `009` can define a legal run path, current stage, and intervention behavior.

### Implementation for User Story 1

- [ ] T008 [US1] Refine `specs/009-orca-yolo/spec.md` so the first-version full-cycle path is explicit and conservative
- [ ] T009 [US1] Populate `specs/009-orca-yolo/contracts/run-stage-model.md` with realistic stage-entry and stage-skip rules
- [ ] T010 [US1] Update `specs/009-orca-yolo/quickstart.md` to validate a full feature path from durable input to PR-ready completion
- [ ] T011 [US1] Manually verify that `orca-yolo` consumes upstream workflow primitives rather than replacing them
- [ ] T011a [US1] Walk the updated `specs/009-orca-yolo/contracts/run-stage-model.md` stage-by-stage and confirm every required stage names its `005-orca-flow-state` transition, its `006-orca-review-artifacts` output, and its `007-orca-context-handoffs` handoff, so the stage contract cannot quietly drift back into a bare list of names.

**Checkpoint**: `orca-yolo` now has an explicit first-version full-cycle contract.

---

## Phase 4: User Story 2 - Resume Or Redirect An Interrupted Run (Priority: P1)

**Goal**: Ensure interrupted work can resume safely and later-stage starts remain honest about prerequisites.

**Independent Test**: Interrupt a run and verify durable run state and orchestration policies support resume or reject incompatible start-from requests clearly.

### Implementation for User Story 2

- [ ] T012 [US2] Refine `specs/009-orca-yolo/contracts/run-state.md` so stop reasons and recoverable outcomes are explicit
- [ ] T013 [US2] Refine `specs/009-orca-yolo/contracts/orchestration-policies.md` so start-from and resume behavior are conservative and inspectable
- [ ] T014 [US2] Update `specs/009-orca-yolo/plan.md` and `specs/009-orca-yolo/research.md` to clarify bounded retry and resume assumptions
- [ ] T015 [US2] Add realistic resume and redirected-start examples to `specs/009-orca-yolo/quickstart.md`
- [ ] T016 [US2] Manually verify that resume behavior depends on durable state rather than chat-memory reconstruction
- [ ] T016a [US2] Verify that supervised-mode resume consults matriarch's lane registry before acting on local run state alone, so ownership changes recorded by matriarch are not silently overridden by a resuming yolo run. Covers spec FR-013 through FR-019 and the Supervised-Mode Behavior section of `contracts/orchestration-policies.md`.

**Checkpoint**: `orca-yolo` now has a conservative resume and redirected-start model.

---

## Phase 5: User Story 3 - Finish With Review And PR Readiness On Stable Foundations (Priority: P2)

**Goal**: Make full-cycle orchestration end in explicit review outcomes and PR-ready completion without forcing unsafe publication.

**Independent Test**: Review the `009` contracts and verify review gates, final outcomes, and PR policy are explicit and downstream of review artifacts.

### Implementation for User Story 3

- [ ] T017 [US3] Update `specs/009-orca-yolo/contracts/orchestration-policies.md` to classify PR-ready versus PR-create behavior explicitly
- [ ] T018 [US3] Reconcile `specs/009-orca-yolo/` with `specs/004-orca-workflow-system-upgrade/contracts/subsystem-integration.md` so downstream orchestration assumptions are explicit
- [ ] T019 [US3] Reconcile `specs/009-orca-yolo/` with `specs/006-orca-review-artifacts/` and `specs/007-orca-context-handoffs/` so review and handoff dependencies remain explicit
- [ ] T020 [US3] Update `specs/009-orca-yolo/quickstart.md` to validate PR-ready completion and explicit stop behavior
- [ ] T021 [US3] Manually verify that `orca-yolo` stays bounded and does not collapse the workflow system back into one opaque command

**Checkpoint**: `009` is now a usable downstream orchestration contract for the Orca workflow system.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency and alignment work across the orchestration contracts and the upgrade program

- [ ] T022 [P] Update `specs/009-orca-yolo/research.md` and `specs/009-orca-yolo/plan.md` if contract assumptions changed during refinement
- [ ] T023 Update `specs/004-orca-workflow-system-upgrade/contracts/subsystem-integration.md` only if `009` changes its promised downstream role materially
- [ ] T024 Run the full document-level validation flow in `specs/009-orca-yolo/quickstart.md` and record the evidence in `specs/009-orca-yolo/tasks.md` or commit notes
- [ ] T025 [P] Run final consistency checks across `specs/009-orca-yolo/`, related upgrade artifacts, and `git diff --check`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on User Story 1 because resume/start behavior needs a stable stage and run-state model
- **User Story 3 (Phase 5)**: Depends on User Stories 1 and 2 because final review/PR behavior needs stable orchestration and resume semantics
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Establishes the MVP full-cycle orchestration contract
- **User Story 2 (P1)**: Adds durable resume and redirected-start behavior
- **User Story 3 (P2)**: Adds explicit final review/PR-ready completion behavior

### Within Each User Story

- Stage model before resume behavior
- Resume behavior before final review and PR behavior
- Manual validation at the end of each story

### Parallel Opportunities

- T002 and T003 can run in parallel during Setup
- T005 and T006 can run in parallel once T004 establishes the minimum stage vocabulary
- T022 and T025 can run in parallel during Polish

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup
2. Complete Foundational orchestration contracts
3. Complete User Story 1 full-cycle path
4. Stop and validate that `orca-yolo` is consuming durable workflow primitives rather than replacing them

### Incremental Delivery

1. Define the stage and run-state model
2. Define conservative resume and policy behavior
3. Align final review and PR-ready completion
4. Finish with consistency validation

### Out Of Scope In This Feature

- rebuilding upstream memory/state/review/handoff primitives inside `009`
- unbounded autonomous fix loops
- provider-specific workflow contracts
- hiding PR publication behind implicit behavior

---

## Notes

- `009` is the downstream orchestrator, not the workflow-system foundation
- keep autonomy bounded and inspectable
- the value of this feature is trustworthy full-cycle execution, not maximum automation
