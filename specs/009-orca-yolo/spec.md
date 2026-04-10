# Feature Specification: Orca YOLO

**Feature Branch**: `009-orca-yolo`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "Add a full-cycle Orca runner that can take work from brainstorm or spec through implementation, review, and PR completion using the durable workflow system."

## Context

Repomix showed that end-to-end orchestration is valuable, but only after the
supporting workflow primitives are real. `orca-yolo` is intentionally late in
the upgrade program.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run A Full Feature Pipeline With Controlled Intervention (Priority: P1)

A developer wants Orca to take a well-scoped feature from brainstorm or spec
through implementation and review, pausing only when human input is materially
needed.

**Why this priority**: This is the orchestration outcome the rest of the
upgrade program is building toward.

**Independent Test**: Start a run from a durable brainstorm or spec artifact and
verify Orca can proceed through documented stages, pause when needed, and
record run state.

**Acceptance Scenarios**:

1. **Given** a brainstorm or spec already exists, **When** a user starts
   `orca-yolo`, **Then** Orca can resolve the starting artifact, determine the
   next stage, and begin a tracked workflow run.
2. **Given** the run reaches a stage that requires clarification or explicit
   approval, **When** the ask policy requires intervention, **Then** Orca
   pauses and records why it stopped.

---

### User Story 2 - Resume Or Redirect An Interrupted Run (Priority: P1)

A developer wants to restart work after interruption, failure, or context loss
without re-deriving the workflow from chat history.

**Why this priority**: Resumability is a core promise of a full-cycle runner.
Without it, the runner is just a long macro.

**Independent Test**: Interrupt a run after at least one completed stage and
verify Orca can resume from durable run state or intentionally restart from a
requested stage.

**Acceptance Scenarios**:

1. **Given** a prior `orca-yolo` run exists with durable state, **When** the
   user resumes it, **Then** Orca can recover stage, artifacts, and outstanding
   blockers from run records.
2. **Given** a user wants to restart from a later stage such as plan or review,
   **When** the required upstream artifacts exist, **Then** Orca can start from
   that stage without pretending earlier stages ran in the current session.

---

### User Story 3 - Finish With Review And PR Readiness On Stable Foundations (Priority: P2)

A developer wants Orca to complete implementation only if review gates pass and
the resulting branch is PR-ready.

**Why this priority**: The value of full-cycle orchestration is not just speed.
It is controlled completion against durable quality gates.

**Independent Test**: Run `orca-yolo` across implementation and review stages
and verify it stops on failed review gates, records review artifacts, and can
produce a PR-ready outcome when the gates pass.

**Acceptance Scenarios**:

1. **Given** implementation is complete, **When** `orca-yolo` enters review,
   **Then** it must use the durable review architecture instead of improvising a
   one-off finish step.
2. **Given** review gates pass and PR creation is enabled, **When** the run
   finishes, **Then** Orca can produce a PR-ready branch state and final run
   summary linked to durable artifacts.

### Edge Cases

- What happens if required upstream features are missing? `orca-yolo` MUST stop
  with an explicit dependency error instead of simulating absent primitives.
- What happens if the selected stage start is incompatible with available
  artifacts? `orca-yolo` MUST reject the request and explain which artifacts are
  missing.
- What happens if review repeatedly fails? `orca-yolo` MUST stop after the
  configured or documented retry limit instead of looping indefinitely.
- What happens if worktree or branch context changes mid-run? `orca-yolo` MUST
  record the context drift and resolve it through durable handoff and run-state
  rules rather than silently continuing.

### Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Orca MUST support a resumable full-cycle workflow runner.
- **FR-002**: `orca-yolo` MUST depend on durable upstream artifacts such as
  brainstorm memory, flow state, and review artifacts.
- **FR-003**: `orca-yolo` MUST support explicit ask levels or equivalent human
  intervention controls.
- **FR-004**: `orca-yolo` MUST record run state durably enough to resume.
- **FR-005**: `orca-yolo` MUST stop on unresolved clarification, failing review
  gates, or missing required dependencies.
- **FR-006**: `orca-yolo` MUST support starting from a durable brainstorm,
  micro-spec/spec artifact, or explicitly requested downstream stage when the
  prerequisites exist.
- **FR-007**: `orca-yolo` MUST define an explicit stage model spanning
  brainstorm, specify, plan, tasks, implement, self-review, code-review,
  cross-review, and PR-ready completion.
- **FR-008**: `orca-yolo` MUST integrate with `005-orca-flow-state` rather than
  inventing a conflicting stage representation.
- **FR-009**: `orca-yolo` MUST integrate with `006-orca-review-artifacts` for
  review outputs and gate tracking.
- **FR-010**: `orca-yolo` MUST integrate with `007-orca-context-handoffs` when
  moving between stages or recovering from interruption.
- **FR-011**: `orca-yolo` MUST remain provider-agnostic and express agent
  execution choices through explicit runner configuration rather than
  provider-specific logic in the workflow contract.
- **FR-012**: `orca-yolo` SHOULD support optional PR creation or PR-ready
  completion, but it MUST keep PR publication as an explicit final-stage policy
  rather than an implicit side effect.

### Key Entities *(include if feature involves data)*

- **Yolo Run**: A durable orchestration record representing one end-to-end Orca
  workflow attempt.
- **Run Stage**: One defined step in the full-cycle workflow, such as plan,
  implement, or cross-review.
- **Run Policy**: Ask-level, retry, worktree, and PR-completion settings that
  govern how a run behaves.
- **Run Outcome**: The final completed, blocked, failed, or paused state plus
  links to durable artifacts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Orca can run a full workflow from durable inputs without relying
  on active session memory alone.
- **SC-002**: Interrupted runs can be resumed from durable state.
- **SC-003**: `orca-yolo` does not need to invent missing workflow primitives at
  runtime because they already exist in earlier upgrade features.
- **SC-004**: A completed run can expose its stage history, current outcome,
  and linked artifacts without relying on chat transcript reconstruction.
- **SC-005**: `orca-yolo` can stop safely on blocked states rather than forcing
  completion when quality or dependency gates are not satisfied.

## Documentation Impact *(mandatory)*

- **README Impact**: Required
- **Why**: This feature introduces a major user-facing orchestration mode with new lifecycle, controls, and expectations.
- **Expected Updates**: `README.md`, orchestration docs, command docs for `orca-yolo`

## Assumptions

- `004-orca-workflow-system-upgrade` remains the authoritative dependency and
  wave-order reference for `orca-yolo`.
- `005-orca-flow-state`, `006-orca-review-artifacts`, and
  `007-orca-context-handoffs` define the durable upstream contracts `orca-yolo`
  consumes.
- `008-orca-capability-packs` may later classify `yolo` as a downstream pack,
  but this feature still needs a complete standalone orchestration contract.
