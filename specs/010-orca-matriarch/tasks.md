# Tasks: Orca Matriarch

## Phase 1: Validate And Lock The Coordination Contracts

- [ ] T001 Re-read [spec.md](./spec.md), [brainstorm.md](./brainstorm.md), [plan.md](./plan.md), [data-model.md](./data-model.md), and all contracts to confirm Matriarch remains a supervisory lane system rather than a hidden execution engine.
- [ ] T002 Cross-check `010` against [005-orca-flow-state/spec.md](../005-orca-flow-state/spec.md) and record the final rule that `005` owns stage semantics while `010` only consumes them.
- [ ] T003 Cross-check `010` against [006-orca-review-artifacts/spec.md](../006-orca-review-artifacts/spec.md) and record the final rule that `006` owns review artifact evidence while `010` only aggregates readiness.
- [ ] T004 Cross-check `010` against [007-orca-context-handoffs/spec.md](../007-orca-context-handoffs/spec.md) and record the final rule that `007` owns handoff semantics while `010` consumes lane continuity outputs.
- [ ] T005 Lock the explicit lane lifecycle contract and transition rules in [lane-registry.md](./contracts/lane-registry.md).
- [ ] T006 Lock the dependency target model in [dependency-model.md](./contracts/dependency-model.md).
- [ ] T007 Lock the tmux deployment boundary in [tmux-deployment.md](./contracts/tmux-deployment.md).
- [ ] T008 Lock the one-lane-one-spec rule and record any future grouping concept as a separate layer above lanes.
- [ ] T009 Lock the state-first lane mailbox contract in [lane-mailbox.md](./contracts/lane-mailbox.md).
- [ ] T010 Lock the claim-safe delegated-work contract in [delegated-work.md](./contracts/delegated-work.md).
- [ ] T011 Lock the shared event-envelope contract in [event-envelope.md](./contracts/event-envelope.md).
- [ ] T012 Update any `010` planning artifacts if the final `005`, `006`, or `007` contracts materially shift Matriarch assumptions.

## Phase 2: Lane Registry And Data Model

- [ ] T013 Define the on-disk storage location and file layout for Matriarch lane metadata.
- [ ] T014 Implement the canonical managed-lane schema from [data-model.md](./data-model.md), including one primary spec per lane, lifecycle state, deployment linkage, mailbox events, and delegated-work items.
- [ ] T015 Implement dependency-record schema and validation with target kind/value semantics.
- [ ] T016 Implement assignment-record schema and reassignment history validation.
- [ ] T017 Implement checkout-target resolution schema and drift-flag representation.
- [ ] T018 Implement deployment-attachment schema for optional tmux and direct-session workers.
- [ ] T019 Implement read/write helpers for the lane registry with deterministic serialization plus advisory locking, stale-lock handling, or stale-write detection.
- [ ] T020 Add tests for lane creation, update, archive, readback, and stale-write rejection behavior.
- [ ] T021 Add tests for malformed or incomplete registry data and safe failure behavior.

## Phase 3: Lane Supervision Commands

- [ ] T022 Implement a primary Matriarch status surface that summarizes active lanes from durable lane metadata plus derived evidence.
- [ ] T023 Implement lane listing with lifecycle state, owner, branch, worktree, deployment, and blocker summary.
- [ ] T024 Implement lane detail inspection with linked artifacts, dependency state, readiness evidence, deployment state, and mailbox summary.
- [ ] T025 Implement lane registration/creation from a spec id or existing feature lane.
- [ ] T026 Implement lane assignment/reassignment commands for human or agent ownership with release history.
- [ ] T027 Implement lane dependency add/remove/update commands with rationale capture and target-type validation.
- [ ] T028 Add tests for lane registration, assignment, dependency mutation, and archive visibility.

## Phase 4: Worktree And Checkout Coordination

- [ ] T029 Integrate Matriarch with the `001` worktree runtime as the preferred path for worktree creation/attachment.
- [ ] T030 Implement lane-to-branch/worktree linkage recording without duplicating worktree runtime ownership logic.
- [ ] T031 Implement checkout-target resolution that prefers explicit lane metadata, then verified worktree/runtime evidence, then safe fallback guidance.
- [ ] T032 Ensure checkout behavior defaults to safe resolution/output and only mutates git or shell state on explicit operator invocation.
- [ ] T033 Add drift detection when registry branch/worktree intent differs from live git/worktree state.
- [ ] T034 Add tests for worktree-attached lanes, branch-only lanes, repo-only lanes, and drift scenarios.

## Phase 5: Tmux Deployment Supervision

- [ ] T035 Implement optional tmux deployment attachment for a lane using the contract in [tmux-deployment.md](./contracts/tmux-deployment.md).
- [ ] T036 Implement tmux session inspection and health-state refresh without conflating deployment health with workflow readiness.
- [ ] T037 Implement explicit deploy/attach/inspect flows while keeping tmux optional for all lanes and surfacing owner/session mismatch after reassignment.
- [ ] T038 Implement the file-backed report-back protocol so launched lane agents surface blockers and questions to Matriarch as the default coordination authority.
- [ ] T039 Add tests or smoke checks for tmux-backed lanes where tmux is available, plus safe degradation when tmux is absent.

## Phase 6: Mailbox And Delegated Work

- [ ] T040 Implement the lane mailbox queue defined in [lane-mailbox.md](./contracts/lane-mailbox.md), using the shared envelope in [event-envelope.md](./contracts/event-envelope.md) and including deterministic startup ACK behavior.
- [ ] T041 Implement claim-safe delegated-work records using the lifecycle in [delegated-work.md](./contracts/delegated-work.md).
- [ ] T042 Add tests for ACK delivery, mailbox visibility without tmux attach, event ordering, claim collisions, release-to-pending, and stale completion rejection.

## Phase 7: Readiness Aggregation

- [ ] T043 Consume `005` flow-state outputs to derive per-lane stage and next-action visibility without redefining stage semantics.
- [ ] T044 Consume `006` review artifact outputs to derive review readiness, missing gates, and PR readiness without treating summaries as sufficient proof.
- [ ] T045 Consume `007` handoff outputs where available to show continuity and reassignment context for a lane, especially for long-lived direct-session workers.
- [ ] T046 Implement explicit blocked/unknown/missing-evidence states so Matriarch does not over-claim readiness.
- [ ] T046a Implement lifecycle precedence rules so hard blockers and explicit operator blocks override ready states until cleared.
- [ ] T047 Add tests for mixed-ready, blocked, ambiguous, evidence-missing, deployment-missing, and mailbox-mismatch lane states.

## Phase 8: Hook Model

- [ ] T048 Implement the minimal hook event model defined in [hook-model.md](./contracts/hook-model.md).
- [ ] T049 Add hook registration loading from the file-backed Matriarch hook registry and validate malformed registrations safely.
- [ ] T050 Add transparent hook execution logging with per-lane event records.
- [ ] T051 Ensure hook failure is surfaced clearly without corrupting lane registry state.
- [ ] T052 Add tests for hook success, hook failure, no-op hook scenarios, and malformed hook registration.

## Phase 9: Operator Documentation And Verification

- [ ] T053 Update `README.md` with the Matriarch operator model, supervisory boundaries, command surface, optional tmux/direct-session deployment behavior, and state-first mailbox/delegation model.
- [ ] T054 Add or update command documentation for Matriarch status, lane management, checkout, dependency, deployment, mailbox, and assignment flows.
- [ ] T055 Run a two-or-three-lane manual verification scenario covering dependency blocking, worktree attachment, checkout guidance, tmux deployment inspection, direct-session handling, report-back flow, mailbox ACK flow, delegated-work claiming, and readiness aggregation.
- [ ] T056 Record the manual verification evidence and any follow-up constraints in the feature review artifacts.
- [ ] T057 Run `self-review` and `cross-review`, apply valid findings, and confirm the final implementation still preserves Matriarch's conservative scope.
