# Tasks: Orca Brainstorm Memory

**Input**: Design documents from `/specs/002-brainstorm-memory/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: This feature uses verification-driven development. Add deterministic helper smoke checks where practical and use the manual quickstart scenarios as the primary end-to-end verification path.

**Organization**: Tasks are grouped by user story so brainstorm memory can be delivered incrementally: durable save first, overview usability second, parked-session handling third, revisit handling fourth, and downstream linking last.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g. US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the repo artifacts and stable templates for brainstorm memory work.

- [x] T001 Review `specs/002-brainstorm-memory/spec.md`, `specs/002-brainstorm-memory/plan.md`, and `specs/002-brainstorm-memory/contracts/` for implementation readiness before editing code
- [x] T002 [P] Add a brainstorm record seed template in `templates/brainstorm-record-template.md`
- [x] T003 [P] Review `commands/brainstorm.md`, `README.md`, and `docs/orca-harvest-matrix.md` against the brainstorm-memory plan and note any contract mismatches to address during implementation

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the deterministic helper surface all brainstorm-memory flows depend on

**⚠️ CRITICAL**: No user story work should begin until these tasks are complete

- [x] T004 Create `src/speckit_orca/brainstorm_memory.py` with record path, numbering, and slug-normalization helpers
- [x] T005 Implement stable record header parsing and serialization helpers in `src/speckit_orca/brainstorm_memory.py`
- [x] T006 Implement overview regeneration helpers in `src/speckit_orca/brainstorm_memory.py`
- [x] T007 Implement lightweight overlap-detection helpers in `src/speckit_orca/brainstorm_memory.py`
- [x] T008 Add a minimal smoke-test entrypoint or callable verification surface in `src/speckit_orca/brainstorm_memory.py` for numbering, parsing, and overview regeneration checks

**Checkpoint**: Brainstorm-memory runtime helpers exist and can support command-level workflow behavior deterministically.

---

## Phase 3: User Story 1 - Saved Brainstorms Become Durable Project Memory (Priority: P1) 🎯 MVP

**Goal**: Allow Orca to save a meaningful brainstorm session into stable project-local memory with the required structure.

**Independent Test**: Save a brainstorm in a repo without an existing `brainstorm/` directory and verify `brainstorm/NN-*.md` is created with the required header and sections.

### Implementation for User Story 1

- [x] T009 [US1] Update `commands/brainstorm.md` to define `brainstorm/` as the durable memory target for saved brainstorm sessions while preserving the existing ideation and handoff contract
- [x] T010 [US1] Implement new-record creation flow in `src/speckit_orca/brainstorm_memory.py` for directory bootstrap, next-number allocation, fallback slug generation, and record writes
- [x] T011 [US1] Wire the brainstorm record structure in `commands/brainstorm.md` to the stable header and required sections defined in `specs/002-brainstorm-memory/contracts/brainstorm-memory-files.md`
- [x] T012 [US1] Update `README.md` to describe durable brainstorm memory behavior and the `brainstorm/` artifact location
- [x] T013 [US1] Run helper smoke verification for new-record creation via `uv run python -m py_compile src/speckit_orca/brainstorm_memory.py` and direct helper checks in `src/speckit_orca/brainstorm_memory.py`
- [x] T014 [US1] Manually verify quickstart Scenario 1 using `specs/002-brainstorm-memory/quickstart.md`

**Checkpoint**: Orca can save a brainstorm as durable memory with a consistent record format.

---

## Phase 4: User Story 2 - Overview View Shows the Current Idea Landscape (Priority: P1)

**Goal**: Give users a generated overview that makes brainstorm memory navigable without opening every record manually.

**Independent Test**: Save multiple brainstorms with different states, regenerate the overview, and verify the index plus aggregated open threads are correct.

### Implementation for User Story 2

- [x] T015 [US2] Implement deterministic `00-overview.md` generation in `src/speckit_orca/brainstorm_memory.py` from current brainstorm records only
- [x] T016 [US2] Ensure `commands/brainstorm.md` requires overview regeneration after every brainstorm write or update
- [x] T017 [US2] Add parked-ideas and open-threads aggregation behavior in `src/speckit_orca/brainstorm_memory.py`
- [x] T018 [US2] Add overview recovery behavior in `src/speckit_orca/brainstorm_memory.py` for the missing-overview edge case
- [x] T019 [US2] Manually verify quickstart Scenarios 1 and 5 using `specs/002-brainstorm-memory/quickstart.md`

**Checkpoint**: Users can scan brainstorm state from `brainstorm/00-overview.md` and recover it safely from source records.

---

## Phase 5: User Story 3 - Incomplete Or Parked Brainstorms Can Still Be Saved Intentionally (Priority: P2)

**Goal**: Preserve meaningful incomplete brainstorms without cluttering the repo with trivial sessions.

**Independent Test**: End a brainstorm without moving to spec, save it intentionally as parked, and verify the saved record plus overview reflect that state.

### Implementation for User Story 3

- [x] T020 [US3] Update `commands/brainstorm.md` to distinguish meaningful incomplete saves from trivial sessions and to require explicit save intent for parked or abandoned outcomes
- [x] T021 [US3] Implement parked and abandoned status handling in `src/speckit_orca/brainstorm_memory.py`
- [x] T022 [US3] Ensure `templates/brainstorm-record-template.md` and `commands/brainstorm.md` both reflect the allowed brainstorm statuses and required open-question fields
- [x] T023 [US3] Manually verify quickstart Scenario 2 using `specs/002-brainstorm-memory/quickstart.md`

**Checkpoint**: Orca can preserve worthwhile incomplete ideation without auto-saving noise.

---

## Phase 6: User Story 4 - Revisiting A Topic Updates Existing Memory Intentionally (Priority: P2)

**Goal**: Help users avoid fragmented brainstorm history by surfacing related prior brainstorms and supporting additive updates.

**Independent Test**: Start a related brainstorm, choose `update existing`, and verify the earlier record is preserved with an additive update plus refreshed overview.

### Implementation for User Story 4

- [x] T024 [US4] Implement related-brainstorm candidate discovery in `src/speckit_orca/brainstorm_memory.py` using normalized title and slug overlap
- [x] T025 [US4] Update `commands/brainstorm.md` to require update-versus-new choice handling when likely matches exist
- [x] T026 [US4] Implement additive record update behavior in `src/speckit_orca/brainstorm_memory.py` that preserves prior authored content and appends dated revision material
- [x] T027 [US4] Manually verify quickstart Scenario 3 using `specs/002-brainstorm-memory/quickstart.md`

**Checkpoint**: Brainstorm revisits are intentional and non-destructive instead of noisy or fragmenting.

---

## Phase 7: User Story 5 - Brainstorm Memory Links Forward Into Later Workflow Artifacts (Priority: P3)

**Goal**: Let brainstorm memory act as workflow input by recording where an idea became a spec or feature identity.

**Independent Test**: Mark a brainstorm as `spec-created` with a spec reference and verify both the record and the overview show the downstream link.

### Implementation for User Story 5

- [x] T028 [US5] Implement downstream-link parsing and serialization in `src/speckit_orca/brainstorm_memory.py`
- [x] T029 [US5] Update `commands/brainstorm.md` to capture and preserve brainstorm-to-spec forward-link metadata without requiring reverse links
- [x] T030 [US5] Ensure `src/speckit_orca/brainstorm_memory.py` renders downstream links in the overview sessions table
- [x] T031 [US5] Manually verify quickstart Scenario 4 using `specs/002-brainstorm-memory/quickstart.md`

**Checkpoint**: Brainstorm memory can point forward into formal Orca workflow artifacts.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency, documentation, and full verification across the feature

- [x] T032 [P] Review `docs/orca-harvest-matrix.md` and leave it unchanged unless the implemented helper/runtime approach materially changes the harvest recommendation language
- [x] T033 Update `specs/002-brainstorm-memory/contracts/brainstorm-command.md` and `specs/002-brainstorm-memory/contracts/brainstorm-memory-files.md` if implementation details shifted during delivery
- [x] T034 Run the full quickstart validation flow in `specs/002-brainstorm-memory/quickstart.md` and record the verification evidence in `specs/002-brainstorm-memory/tasks.md` or commit notes
- [x] T035 [P] Run final syntax and packaging verification for touched code via `uv run python -m py_compile src/speckit_orca/brainstorm_memory.py`, `uv run --with build python -m build`, and `git diff --check`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on User Story 1 because overview generation needs real saved records
- **User Story 3 (Phase 5)**: Depends on User Story 1 and benefits from User Story 2 overview behavior
- **User Story 4 (Phase 6)**: Depends on User Story 1 and Foundational matching helpers; overview behavior from User Story 2 should already be present
- **User Story 5 (Phase 7)**: Depends on User Stories 1 and 2 because links must appear in records and overview
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Starts after Foundational and delivers the MVP
- **User Story 2 (P1)**: Builds on US1 saved records
- **User Story 3 (P2)**: Builds on US1 save behavior and US2 overview behavior
- **User Story 4 (P2)**: Builds on US1 save behavior and Foundational helper parsing
- **User Story 5 (P3)**: Builds on US1 record format and US2 overview rendering

### Within Each User Story

- Helper support before command-doc wiring when both are needed
- Record-write behavior before overview/display work
- Status handling before quickstart verification
- Additive update behavior before revisit verification
- Downstream link serialization before overview rendering

### Parallel Opportunities

- T002 and T003 can run in parallel during Setup
- T005 and T007 can run in parallel after T004 creates `src/speckit_orca/brainstorm_memory.py`
- T006 depends on T005 because overview regeneration relies on stable header parsing
- T012 and T013 can run in parallel near the end of US1
- T032 and T035 can run in parallel during Polish

---

## Parallel Example: User Story 1

```bash
# Parallel near the end of US1:
Task: "Update README.md to describe durable brainstorm memory behavior and the brainstorm/ artifact location"
Task: "Run helper smoke verification for new-record creation via uv run python -m py_compile src/speckit_orca/brainstorm_memory.py and direct helper checks"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup
2. Complete Foundational helper layer
3. Complete User Story 1 durable save flow
4. Stop and validate that Orca can save a brainstorm into `brainstorm/NN-*.md`

### Incremental Delivery

1. Deliver durable brainstorm save behavior
2. Add overview generation and recovery
3. Add parked/abandoned intentional-save behavior
4. Add revisit/update handling
5. Add downstream workflow links
6. Finish with docs and full verification

### Out Of Scope In This Feature

- `orca-yolo` orchestration
- reverse links from specs back into brainstorm records
- semantic search or embeddings for brainstorm recall
- flow-state or review-artifact runtime integration beyond the forward-link contract

---

## Notes

- This feature should stay provider-agnostic and file-first
- Use deterministic helpers for numbering, parsing, and overview regeneration rather than burying those rules only in prompt text
- Preserve manual edits and prior brainstorm history; do not treat records as disposable generated output

## Verification Evidence

- `uv run python -m py_compile src/speckit_orca/brainstorm_memory.py`
- `uv run --with pytest pytest tests/test_brainstorm_memory.py`
- `uv run --with build python -m build`
- `git diff --check`
- Direct helper smoke checks covered create, inspect, match discovery, additive update, `spec-created` downstream links, parked sessions, and overview regeneration/recovery
- Quickstart scenarios validated manually against disposable temp directories for first save, parked save, revisit/update, downstream link, and overview recovery
