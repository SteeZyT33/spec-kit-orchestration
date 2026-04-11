# Tasks: Orca Workflow System Upgrade

**Input**: Design documents from `/specs/004-orca-workflow-system-upgrade/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: This feature uses document-level verification rather than runtime tests. Validation should confirm subsystem inventory, integration contracts, implementation-wave ordering, and checkpoint logic.

**Organization**: Tasks are grouped by user story so the umbrella upgrade can deliver program value incrementally: first the system framing, then parallel-safe coordination, then downstream orchestration readiness.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g. US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the umbrella feature artifacts and align existing roadmap notes with the new program-spec role.

- [x] T001 Review `specs/004-orca-workflow-system-upgrade/spec.md`, `specs/004-orca-workflow-system-upgrade/brainstorm.md`, and `specs/004-orca-workflow-system-upgrade/plan.md` for program-level scope alignment before editing child coordination artifacts
- [x] T002 [P] Review `docs/orca-harvest-matrix.md`, `docs/orca-roadmap.md`, and `docs/orca-v1.4-design.md` against the `004` program direction and note conflicts to resolve in this feature
- [x] T003 [P] Confirm the current child-spec inventory in `specs/002-brainstorm-memory/`, `specs/003-cross-review-agent-selection/`, and `specs/005-orca-flow-state/` through `specs/011-orca-evolve/` matches the umbrella program assumptions

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the core upgrade-program contracts all later coordination work depends on

**⚠️ CRITICAL**: No user story work should begin until these program contracts are coherent

- [x] T004 Refine `specs/004-orca-workflow-system-upgrade/contracts/upgrade-program.md` to define the authoritative child-spec inventory and ownership boundaries
- [x] T005 Implement the cross-spec dependency map in `specs/004-orca-workflow-system-upgrade/data-model.md` and `specs/004-orca-workflow-system-upgrade/contracts/subsystem-integration.md`
- [x] T006 Implement the wave model and gating checkpoints in `specs/004-orca-workflow-system-upgrade/contracts/implementation-waves.md`
- [x] T007 Add explicit references in `specs/004-orca-workflow-system-upgrade/research.md` and `specs/004-orca-workflow-system-upgrade/plan.md` that implementation order is dependency-driven rather than feature-number-driven

**Checkpoint**: The umbrella upgrade has an authoritative subsystem inventory, dependency map, and wave/checkpoint model.

---

## Phase 3: User Story 1 - Orca Feels Like One Workflow System (Priority: P1) 🎯 MVP

**Goal**: Make the whole Orca upgrade legible as one coordinated workflow system rather than a pile of separate feature ideas.

**Independent Test**: A maintainer can read the `004` artifacts and trace how brainstorm memory, flow state, review artifacts, handoffs, capability packs, and yolo fit into one system.

### Implementation for User Story 1

- [x] T008 [US1] Refine `specs/004-orca-workflow-system-upgrade/spec.md` so the umbrella feature explicitly describes the system-level role of each child subsystem
- [x] T009 [US1] Update `specs/004-orca-workflow-system-upgrade/contracts/subsystem-integration.md` with the minimum durable outputs each child spec provides to the next
- [x] T010 [US1] Update `specs/004-orca-workflow-system-upgrade/quickstart.md` to validate end-to-end system coherence from brainstorm memory through later orchestration prerequisites
- [x] T011 [US1] Reconcile `docs/orca-harvest-matrix.md` and/or `docs/orca-roadmap.md` with the new umbrella program framing so the repo has one clear system story
- [x] T012 [US1] Manually verify that every repomix-derived subsystem is represented in the umbrella spec and child-spec tree

**Checkpoint**: Orca's upgrade can be understood as one workflow system from the `004` artifacts alone.

---

## Phase 4: User Story 2 - Orca Supports Parallel And Multi-Agent Execution Safely (Priority: P1)

**Goal**: Make the upgrade safe to execute in parallel by defining clear ownership, dependencies, and coordination boundaries.

**Independent Test**: Separate agents can be assigned `002`, `003`, `005`, `006`, or later specs using the `004` contracts without inventing hidden subsystem assumptions.

### Implementation for User Story 2

- [x] T013 [US2] Update `specs/004-orca-workflow-system-upgrade/contracts/subsystem-integration.md` to make producer/consumer assumptions explicit enough for parallel implementation
- [x] T014 [US2] Expand `specs/004-orca-workflow-system-upgrade/contracts/implementation-waves.md` with parallel-safe work sets and wave-entry criteria
- [x] T015 [US2] Update `specs/004-orca-workflow-system-upgrade/data-model.md` so integration contracts and checkpoints are explicit coordination entities, not just narrative concepts
- [x] T016 [US2] Add a coordination section to `specs/004-orca-workflow-system-upgrade/quickstart.md` describing how maintainers should validate child-spec alignment during parallel work
- [x] T017 [US2] Manually verify that `005` and `006` can be planned or implemented in parallel without contradicting the `004` contract set

**Checkpoint**: `004` can act as the coordination anchor for parallel subsystem work.

---

## Phase 5: User Story 3 - Orca Gains Full-Cycle Orchestration On Stable Foundations (Priority: P2)

**Goal**: Prevent premature `orca-yolo` work by making the orchestration prerequisites explicit and reviewable.

**Independent Test**: A maintainer can inspect `004` and determine exactly what must be true before `009-orca-yolo` should start implementation.

### Implementation for User Story 3

- [x] T018 [US3] Update `specs/004-orca-workflow-system-upgrade/contracts/implementation-waves.md` to define explicit pre-`009` readiness checkpoints
- [x] T019 [US3] Refine `specs/004-orca-workflow-system-upgrade/spec.md` and `specs/004-orca-workflow-system-upgrade/plan.md` so `orca-yolo` is consistently treated as downstream of memory, state, review artifacts, and handoffs
- [x] T020 [US3] Update `specs/004-orca-workflow-system-upgrade/contracts/subsystem-integration.md` to show what `009` is allowed to assume from `002`, `003`, `005`, `006`, `007`, and `008`
- [x] T021 [US3] Manually verify that the `004` checkpoint language is strong enough to stop premature orchestration implementation

**Checkpoint**: The upgrade program now has clear system-level gates before `orca-yolo`.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency, alignment, and documentation polish for the umbrella upgrade program

- [x] T022 [P] Update `specs/004-orca-workflow-system-upgrade/research.md` and `specs/004-orca-workflow-system-upgrade/plan.md` if any subsystem or wave assumptions changed during coordination work
- [x] T023 Update `docs/orca-harvest-matrix.md` and `docs/orca-roadmap.md` only as needed so they reflect the umbrella program rather than competing with it
- [x] T024 Run the full document-level validation flow in `specs/004-orca-workflow-system-upgrade/quickstart.md` and record the evidence in `specs/004-orca-workflow-system-upgrade/tasks.md` or commit notes
- [x] T025 [P] Run final consistency checks across `specs/004-orca-workflow-system-upgrade/`, the referenced child specs, and `git diff --check`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on User Story 1 because parallel-safe coordination depends on the system-level framing being explicit
- **User Story 3 (Phase 5)**: Depends on User Stories 1 and 2 because orchestration gates rely on the child-spec system map and parallel-safe contracts
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Establishes the umbrella system framing and is the MVP for this feature
- **User Story 2 (P1)**: Builds on the system framing to make parallel execution safe
- **User Story 3 (P2)**: Builds on both prior stories to define safe downstream orchestration gates

### Within Each User Story

- Program-level contracts before dependent coordination notes
- Child-spec ownership before wave and checkpoint tightening
- Wave/checkpoint definitions before orchestration-readiness claims
- Manual validation at the end of each story

### Parallel Opportunities

- T002 and T003 can run in parallel during Setup
- T005 and T006 can run in parallel once T004 establishes the upgrade-program authority
- T022 and T025 can run in parallel during Polish

---

## Parallel Example: User Story 2

```bash
# Parallel once the umbrella framing is stable:
Task: "Update subsystem-integration.md to make producer/consumer assumptions explicit enough for parallel implementation"
Task: "Expand implementation-waves.md with parallel-safe work sets and wave-entry criteria"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup
2. Complete Foundational program contracts
3. Complete User Story 1 system framing
4. Stop and validate that the whole Orca upgrade reads like one coherent workflow program

### Incremental Delivery

1. Define the umbrella system story
2. Tighten parallel-safe subsystem coordination
3. Add explicit orchestration checkpoints
4. Finish with repo-level alignment and consistency validation

### Out Of Scope In This Feature

- implementing the runtime behavior of `002`, `003`, `005`, `006`, `007`, `008`, or `009`
- collapsing the child specs into the umbrella feature
- pretending the whole application upgrade is one implementation PR

---

## Notes

- `004` is the coordination layer, not the runtime layer
- Use it to assign and sequence work, not to hide subsystem detail
- The value of this feature is reduced implementation drift and safer parallel delivery
