# Tasks: Orca Context Handoffs

**Input**: Design documents from `/specs/007-orca-context-handoffs/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: This feature uses verification-driven development focused on transition-contract validation and manual fresh-session/worktree continuity checks.

**Organization**: Tasks are grouped by user story so handoff behavior can be delivered incrementally: explicit transitions first, then worktree-aware resolution, then downstream orchestration alignment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g. US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Align the feature with related subsystem specs and define the handoff problem cleanly before implementation.

- [x] T001 Review `specs/007-orca-context-handoffs/spec.md`, `specs/007-orca-context-handoffs/brainstorm.md`, and `specs/007-orca-context-handoffs/plan.md` for scope clarity before editing contracts
- [x] T002 [P] Review `specs/002-brainstorm-memory/`, `specs/005-orca-flow-state/`, and `specs/006-orca-review-artifacts/` against `007` to identify boundary assumptions
- [x] T003 [P] Review `specs/004-orca-workflow-system-upgrade/contracts/subsystem-integration.md` so `007` stays aligned with the umbrella program

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the stable handoff contract and transition model all later work depends on

**⚠️ CRITICAL**: No user story work should begin until the handoff contract and stage transitions are coherent

- [x] T004 Refine `specs/007-orca-context-handoffs/contracts/handoff-contract.md` to define the minimum durable handoff shape
- [x] T005 Implement the supported transition map in `specs/007-orca-context-handoffs/contracts/stage-transitions.md`
- [x] T006 Implement the resolution-order contract in `specs/007-orca-context-handoffs/contracts/handoff-resolution.md`
- [x] T007 Update `specs/007-orca-context-handoffs/data-model.md` so handoff entities and resolution results match the contracts exactly

**Checkpoint**: `007` has a stable handoff artifact, transition set, and resolution model.

---

## Phase 3: User Story 1 - Move Between Workflow Stages Without Losing Intent (Priority: P1) 🎯 MVP

**Goal**: Make stage-to-stage continuity explicit enough that later stages can resolve upstream context without chat replay.

**Independent Test**: Move through brainstorm -> specify -> plan and verify the next stage can resolve the intended upstream artifact set and summary.

### Implementation for User Story 1

- [x] T008 [US1] Refine `specs/007-orca-context-handoffs/spec.md` so the main stage transitions and continuity goals are explicit
- [x] T009 [US1] Update `specs/007-orca-context-handoffs/contracts/stage-transitions.md` with the minimum required inputs for each supported transition
- [x] T010 [US1] Update `specs/007-orca-context-handoffs/quickstart.md` to verify brainstorm -> specify and specify -> plan continuity
- [x] T011 [US1] Manually validate that the `007` artifacts make upstream context resolvable for the main stage transitions

**Checkpoint**: Orca has an explicit stage handoff model for the core workflow path.

---

## Phase 4: User Story 2 - Worktree And Fresh-Session Continuity (Priority: P1)

**Goal**: Ensure context handoffs survive fresh sessions and worktree-based execution without relying on active chat memory.

**Independent Test**: Re-enter a feature from a fresh session or worktree and verify Orca can still resolve the correct upstream context.

### Implementation for User Story 2

- [x] T012 [US2] Update `specs/007-orca-context-handoffs/contracts/handoff-resolution.md` so branch and worktree/lane context are used intentionally and only when present
- [x] T013 [US2] Refine `specs/007-orca-context-handoffs/plan.md` and `specs/007-orca-context-handoffs/research.md` to make worktree context explicitly additive rather than mandatory
- [x] T014 [US2] Update `specs/007-orca-context-handoffs/quickstart.md` to validate fresh-session and worktree continuity
- [x] T015 [US2] Manually verify that missing lane metadata degrades safely while still preserving feature-level context resolution

**Checkpoint**: `007` supports context continuity across fresh sessions and worktrees without hard dependency on lane state.

---

## Phase 5: User Story 3 - Feed Later Review And Orchestration Stages (Priority: P2)

**Goal**: Make `007` a real upstream provider for review/runtime consumers such as `006` and `009`.

**Independent Test**: Review the `007` contracts and verify later review/orchestration stages can name what they are allowed to assume from handoffs.

### Implementation for User Story 3

- [x] T016 [US3] Update `specs/007-orca-context-handoffs/contracts/handoff-contract.md` and `specs/007-orca-context-handoffs/contracts/handoff-resolution.md` to expose the minimum fields later consumers need
- [x] T017 [US3] Reconcile `specs/007-orca-context-handoffs/` with `specs/004-orca-workflow-system-upgrade/contracts/subsystem-integration.md` so downstream assumptions are explicit
- [x] T018 [US3] Update `specs/007-orca-context-handoffs/quickstart.md` to include implement -> review continuity checks
- [x] T019 [US3] Manually verify that the `007` contract set is strong enough to support later `006` and `009` planning

**Checkpoint**: Context handoffs are now a usable upstream contract for later workflow subsystems.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency work across the handoff feature and adjacent subsystem specs

- [x] T020 [P] Update `specs/007-orca-context-handoffs/research.md` and `specs/007-orca-context-handoffs/plan.md` if contract decisions shifted during refinement
- [x] T021 Update `specs/004-orca-workflow-system-upgrade/contracts/subsystem-integration.md` only if `007` changes its promised outputs materially
- [x] T022 Run the full transition validation flow in `specs/007-orca-context-handoffs/quickstart.md` and record the evidence in `specs/007-orca-context-handoffs/tasks.md` or commit notes
- [x] T023 [P] Run final consistency checks across `specs/007-orca-context-handoffs/`, `specs/002-brainstorm-memory/`, `specs/005-orca-flow-state/`, and `git diff --check`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on User Story 1 because worktree/fresh-session continuity depends on explicit transition and resolution rules
- **User Story 3 (Phase 5)**: Depends on User Stories 1 and 2 because downstream assumptions require stable handoff contracts
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Establishes the MVP handoff model
- **User Story 2 (P1)**: Extends the handoff model to fresh-session and worktree continuity
- **User Story 3 (P2)**: Makes the handoff model consumable by later review/orchestration layers

### Within Each User Story

- Contract shape before resolution semantics
- Resolution semantics before fresh-session/worktree validation
- Downstream consumer assumptions before orchestration-readiness claims

### Parallel Opportunities

- T002 and T003 can run in parallel during Setup
- T005 and T006 can run in parallel once T004 establishes the minimum handoff shape
- T020 and T023 can run in parallel during Polish

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup
2. Complete Foundational handoff contracts
3. Complete User Story 1 core stage transitions
4. Stop and validate that upstream context can be resolved without chat replay

### Incremental Delivery

1. Define handoff contract and stage transition model
2. Add worktree/fresh-session continuity
3. Tighten downstream review/orchestration assumptions
4. Finish with cross-spec consistency validation

### Out Of Scope In This Feature

- replacing `002` brainstorm memory
- replacing `005` flow state
- replacing `006` review artifacts
- implementing `009-orca-yolo`

---

## Notes

- `007` owns stage continuity, not general memory
- `007` should remain lightweight and artifact-first
- the value of this feature is making transitions explicit enough that later tooling does not have to guess

## Verification Notes

- Added deterministic runtime helper: `src/speckit_orca/context_handoffs.py`
- Added tests: `tests/test_context_handoffs.py`
- Verified with:
  - `uv run pytest tests/test_context_handoffs.py tests/test_brainstorm_memory.py`
  - `uv run python -m py_compile src/speckit_orca/context_handoffs.py src/speckit_orca/brainstorm_memory.py src/speckit_orca/flow_state.py src/speckit_orca/cli.py`
  - `git diff --check`
- `T021` required no change to `004`; the promised outputs remained materially aligned after implementation.
