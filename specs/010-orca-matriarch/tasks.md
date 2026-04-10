# Tasks: Orca Matriarch

## Phase 1: Validate And Lock The Coordination Contracts

- [ ] T001 Re-read [spec.md](./spec.md), [brainstorm.md](./brainstorm.md), [plan.md](./plan.md), [data-model.md](./data-model.md), and all contracts to confirm Matriarch remains a supervisory lane system rather than a hidden execution engine.
- [ ] T002 Cross-check `010` against [005-orca-flow-state/spec.md](../005-orca-flow-state/spec.md) and record the final rule that `005` owns stage semantics while `010` only consumes them.
- [ ] T003 Cross-check `010` against [006-orca-review-artifacts/spec.md](../006-orca-review-artifacts/spec.md) and record the final rule that `006` owns review artifact evidence while `010` only aggregates readiness.
- [ ] T004 Cross-check `010` against [007-orca-context-handoffs/spec.md](../007-orca-context-handoffs/spec.md) and record the final rule that `007` owns handoff semantics while `010` consumes lane continuity outputs.
- [ ] T005 Update any `010` planning artifacts if the final `005`, `006`, or `007` contracts materially shift Matriarch assumptions.

## Phase 2: Lane Registry And Data Model

- [ ] T006 Define the on-disk storage location and file layout for Matriarch lane metadata.
- [ ] T007 Implement the canonical managed-lane schema from [data-model.md](./data-model.md).
- [ ] T008 Implement dependency-record schema and validation.
- [ ] T009 Implement assignment-record schema and validation.
- [ ] T010 Implement checkout-target resolution schema and drift-flag representation.
- [ ] T011 Implement read/write helpers for the lane registry with deterministic serialization.
- [ ] T012 Add tests for lane creation, update, archive, and readback behavior.
- [ ] T013 Add tests for malformed or incomplete registry data and safe failure behavior.

## Phase 3: Lane Supervision Commands

- [ ] T014 Implement a primary Matriarch status surface that summarizes active lanes from durable lane metadata plus derived evidence.
- [ ] T015 Implement lane listing with status, owner, branch, worktree, and blocker summary.
- [ ] T016 Implement lane detail inspection with linked artifacts, dependency state, and readiness evidence.
- [ ] T017 Implement lane registration/creation from a spec id or existing feature lane.
- [ ] T018 Implement lane assignment/reassignment commands for human or agent ownership.
- [ ] T019 Implement lane dependency add/remove/update commands with rationale capture.
- [ ] T020 Add tests for lane registration, assignment, dependency mutation, and archive visibility.

## Phase 4: Worktree And Checkout Coordination

- [ ] T021 Integrate Matriarch with the `001` worktree runtime as the preferred path for worktree creation/attachment.
- [ ] T022 Implement lane-to-branch/worktree linkage recording without duplicating worktree runtime ownership logic.
- [ ] T023 Implement checkout-target resolution that prefers explicit lane metadata, then verified worktree/runtime evidence, then safe fallback guidance.
- [ ] T024 Ensure checkout behavior defaults to safe resolution/output and only mutates git state on explicit operator invocation.
- [ ] T025 Add drift detection when registry branch/worktree intent differs from live git/worktree state.
- [ ] T026 Add tests for worktree-attached lanes, branch-only lanes, repo-only lanes, and drift scenarios.

## Phase 5: Readiness Aggregation

- [ ] T027 Consume `005` flow-state outputs to derive per-lane stage and next-action visibility without redefining stage semantics.
- [ ] T028 Consume `006` review artifact outputs to derive review readiness, missing gates, and PR readiness without treating summaries as sufficient proof.
- [ ] T029 Consume `007` handoff outputs where available to show continuity and reassignment context for a lane.
- [ ] T030 Implement explicit blocked/unknown/missing-evidence states so Matriarch does not over-claim readiness.
- [ ] T031 Add tests for mixed-ready, blocked, ambiguous, and evidence-missing lane states.

## Phase 6: Hook Model

- [ ] T032 Implement the minimal hook event model defined in [hook-model.md](./contracts/hook-model.md).
- [ ] T033 Add transparent hook execution logging with per-lane event records.
- [ ] T034 Ensure hook failure is surfaced clearly without corrupting lane registry state.
- [ ] T035 Add tests for hook success, hook failure, and no-op hook scenarios.

## Phase 7: Operator Documentation And Verification

- [ ] T036 Update `README.md` with the Matriarch operator model, supervisory boundaries, and command surface.
- [ ] T037 Add or update command documentation for Matriarch status, lane management, checkout, and assignment flows.
- [ ] T038 Run a two-or-three-lane manual verification scenario covering dependency blocking, worktree attachment, checkout guidance, and readiness aggregation.
- [ ] T039 Record the manual verification evidence and any follow-up constraints in the feature review artifacts.
- [ ] T040 Run `self-review` and `cross-review`, apply valid findings, and confirm the final implementation still preserves Matriarch's conservative scope.
