# Tasks: Orca Worktree Runtime Helpers

**Input**: Design documents from `/specs/001-orca-worktree-runtime/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: Manual verification is the primary test method for this feature. Add lightweight validation checks in the scripts where useful, but do not expand scope into a full shell test harness in this feature.

**Organization**: Tasks are grouped by user story so the runtime can be delivered incrementally: create/track first, inspect second, cleanup third.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the feature scaffolding and align templates/docs with the runtime worktree feature.

- [X] T001 Create `templates/worktree-registry.example.json` with the initial Orca registry schema
- [X] T002 Update `templates/worktree-record.example.json` to match the runtime lane record schema exactly
- [X] T003 [P] Review `docs/worktree-protocol.md` and `docs/delivery-protocol.md` against the runtime scope; note any mismatches to address during implementation

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared helper logic that all worktree operations depend on

**⚠️ CRITICAL**: No user story work should begin until these helpers exist

- [X] T004 Create `scripts/bash/orca-worktree-lib.sh` with repo-root, default-branch, branch-name, and path-resolution helpers
- [X] T005 Implement registry and lane-record read/write helpers in `scripts/bash/orca-worktree-lib.sh`
- [X] T006 Implement validation helpers in `scripts/bash/orca-worktree-lib.sh` for required fields, duplicate lane IDs, duplicate branches, and invalid target paths
- [X] T007 Implement current-lane and feature-lane discovery helpers in `scripts/bash/orca-worktree-lib.sh`

**Checkpoint**: Runtime helper layer exists and is ready to support concrete worktree operations

---

## Phase 3: User Story 1 - Create And Track Orca Worktrees (Priority: P1) 🎯 MVP

**Goal**: Allow Orca to create a git worktree and register it in Orca metadata as the workflow source of truth

**Independent Test**: On branch `001-orca-worktree-runtime`, run the create flow and verify that a worktree is created, registry metadata is written, and the original repo is restored to the default branch when required

### Implementation for User Story 1

- [X] T008 [US1] Create `scripts/bash/orca-worktree.sh` with argument parsing and subcommand routing for `create`, `list`, `status`, and `cleanup`
- [X] T009 [US1] Implement nested-worktree detection and git repository safety checks in `scripts/bash/orca-worktree.sh`
- [X] T010 [US1] Implement path computation and target-path validation for worktree creation in `scripts/bash/orca-worktree.sh`
- [X] T011 [US1] Implement default-branch restoration logic before worktree creation in `scripts/bash/orca-worktree.sh`
- [X] T012 [US1] Implement git worktree creation plus lane-record and registry updates in `scripts/bash/orca-worktree.sh`
- [X] T013 [US1] Add clear create-flow output and next-step instructions in `scripts/bash/orca-worktree.sh`
- [X] T014 [US1] Manually verify create flow in this repository and record any runtime adjustments needed

**Checkpoint**: Orca can create and register a worktree with metadata-backed state

---

## Phase 4: User Story 2 - Inspect Active Orca Worktrees (Priority: P2)

**Goal**: Allow maintainers to inspect active Orca lanes from metadata without reading raw JSON directly

**Independent Test**: After at least one Orca worktree exists, run `list` and `status` and verify that lane ID, feature, branch, path, status, and drift warnings are reported correctly

### Implementation for User Story 2

- [X] T015 [US2] Implement metadata-first `list` output in `scripts/bash/orca-worktree.sh`
- [X] T016 [US2] Implement `status` output in `scripts/bash/orca-worktree.sh` for current lane, sibling lanes, and registry drift warnings
- [X] T017 [US2] Add drift detection between registry metadata and `git worktree list` in `scripts/bash/orca-worktree.sh`
- [X] T018 [US2] Update `README.md` with a short worktree runtime section and example usage for `list` and `status`
- [X] T019 [US2] Manually verify list/status behavior against valid metadata and intentionally drifted metadata

**Checkpoint**: Maintainers can inspect Orca lane state and drift through the runtime helper surface

---

## Phase 5: User Story 3 - Clean Up Merged Or Retired Worktrees (Priority: P3)

**Goal**: Allow safe cleanup of merged or retired worktrees without silently removing active or ambiguous lanes

**Independent Test**: After marking or merging a lane branch, run cleanup and verify that only safe candidates are removed and metadata is updated consistently

### Implementation for User Story 3

- [X] T020 [US3] Implement merged/retired cleanup candidate detection in `scripts/bash/orca-worktree.sh`
- [X] T021 [US3] Implement safe worktree removal and metadata update logic in `scripts/bash/orca-worktree.sh`
- [X] T022 [US3] Implement warnings for ambiguous or active cleanup candidates in `scripts/bash/orca-worktree.sh`
- [X] T023 [US3] Manually verify cleanup behavior with merged, retired, and ambiguous lane states

**Checkpoint**: Orca cleanup removes only safe candidates and preserves active or ambiguous lanes

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency and documentation work for the runtime layer

- [X] T024 [P] Ensure `scripts/bash/orca-worktree-lib.sh` and `scripts/bash/orca-worktree.sh` are executable and documented consistently
- [X] T025 Update `docs/worktree-protocol.md` and `docs/delivery-protocol.md` if runtime behavior changed the protocol details
- [ ] T026 [P] Update `docs/spex-harvest-list.md` or `docs/spex-adoption-notes.md` only if implementation choices materially differ from the planned harvest approach
- [X] T027 Run the full manual verification flow one more time and summarize the evidence in the feature artifacts or commit notes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion
- **User Story 1 (Phase 3)**: Depends on foundational helpers
- **User Story 2 (Phase 4)**: Depends on User Story 1 because list/status need real metadata and at least one valid lane
- **User Story 3 (Phase 5)**: Depends on User Story 1 and benefits from User Story 2 visibility
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### Within Each User Story

- Helper logic before operation-specific logic
- Create flow before inspection and cleanup
- Drift visibility before cleanup finalization
- Manual verification at the end of each story

### Parallel Opportunities

- T001 and T002 can run in parallel
- T005, T006, and T007 can run in parallel once T004 establishes the helper file
- T024 and T026 can run in parallel during polish

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup
2. Complete Foundational helper layer
3. Complete User Story 1 create-and-track flow
4. Stop and manually verify worktree creation plus metadata registration

### Incremental Delivery

1. Add creation and registration
2. Add inspection and drift reporting
3. Add cleanup
4. Finish with documentation and verification polish

### Out Of Scope In This Feature

- wiring `assign`, `code-review`, `cross-review`, or `self-review` to the runtime metadata
- adding a `speckit.orca.worktree` command wrapper
- building a full shell test harness
- introducing traits or deep automation

---

## Notes

- Metadata-first behavior matters more than clever git inference
- Fail loudly on invalid state rather than silently repairing it
- Borrow from `cc-spex` operational worktree behavior where it saves legwork, but do not import Claude-specific workflow assumptions

## Verification Notes

- `scripts/bash/orca-worktree.sh help` returned the expected subcommand surface for `create`, `list`, `status`, and `cleanup`.
- `scripts/bash/orca-worktree.sh create --lane smoke --task-scope T014` created a disposable lane branch and wrote matching registry plus lane metadata under `.specify/orca/worktrees/`.
- `scripts/bash/orca-worktree.sh list --all` and `scripts/bash/orca-worktree.sh status` reported the created lane from metadata without raw JSON inspection.
- Cleanup verification exposed a stale-admin edge case after path removal; the implementation was tightened to prune git worktree admin state and to stop warning on already-cleaned retired lanes.
- Re-running the lifecycle with a second disposable lane confirmed that `cleanup --apply` removed the worktree, pruned stale state, and left no further cleanup candidates.
- Disposable verification metadata and throwaway branches were removed after validation so the repo was left with only the implementation changes.
