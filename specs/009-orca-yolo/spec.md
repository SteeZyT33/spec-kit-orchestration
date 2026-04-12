# Feature Specification: Orca YOLO

**Feature Branch**: `009-orca-yolo`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "Add a full-cycle Orca runner that can take work from brainstorm or spec through implementation, review, and PR completion using the durable workflow system."

## Context

Repomix showed that end-to-end orchestration is valuable, but only after the
supporting workflow primitives are real. `orca-yolo` is intentionally late in
the upgrade program.

Since `009` was first drafted, `010-orca-matriarch` has landed as the
multi-spec supervisor. That changes how `009` must be scoped. `orca-yolo` is
now the single-lane worker that `010` may delegate to — not an independent
top-level runner. In v1, `009` MUST work in both a *standalone* mode (no
matriarch, direct user interaction) and a *matriarch-supervised* mode (running
as a Lane Agent under `010`'s supervision), and it MUST NOT assume a specific
deployment substrate. When supervised, `009` consumes `010`'s lane identity,
mailbox, and event-envelope contracts rather than inventing parallel
coordination state.

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
  brainstorm, specify, plan, tasks, assign, implement, review-spec,
  review-code, review-pr, and PR-ready completion.
- **FR-008**: `orca-yolo` MUST integrate with `005-orca-flow-state` rather than
  inventing a conflicting stage representation.
- **FR-009**: `orca-yolo` MUST integrate with `012-review-model` for
  review outputs and gate tracking (supersedes 006).
- **FR-010**: `orca-yolo` MUST integrate with `007-orca-context-handoffs` when
  moving between stages or recovering from interruption.
- **FR-011**: `orca-yolo` MUST remain provider-agnostic and express agent
  execution choices through explicit runner configuration rather than
  provider-specific logic in the workflow contract.
- **FR-012**: `orca-yolo` SHOULD support optional PR creation or PR-ready
  completion, but it MUST keep PR publication as an explicit final-stage policy
  rather than an implicit side effect.
- **FR-013**: When running under `010-orca-matriarch` supervision, a yolo run
  MUST behave as a Lane Agent per matriarch's spec FR-020 and MUST report
  blockers, questions, and approval needs upward via the Lane Mailbox rather
  than prompting the user directly or bypassing supervision.
- **FR-014**: `orca-yolo` MUST support both a *standalone* and a
  *matriarch-supervised* run mode, expressed explicitly in Run Policy rather
  than inferred at runtime from environment or CLI wiring.
- **FR-015**: In supervised mode, a Yolo Run MUST link to a `lane_id` matching
  matriarch's lane identity (defaulting to the primary `spec_id` per matriarch
  spec FR-025) so the run is discoverable and inspectable by matriarch.
- **FR-016**: `orca-yolo` MUST express `deployment_kind` explicitly
  (`standalone`, `direct-session`, or `tmux`) to align with matriarch spec
  FR-026, and MUST NOT assume tmux is the only execution substrate.
- **FR-017**: Stage transitions MUST record evidence into `005-orca-flow-state`
  and MUST link to `012-review-model` outputs rather than maintaining
  parallel stage or review records inside yolo run state.
- **FR-018**: Stage-to-stage context continuity MUST use
  `007-orca-context-handoffs` rather than implicit session-carried context, so
  resume after interruption does not depend on chat memory.
- **FR-019**: When yolo pauses for clarification, the pause reason MUST be
  inspectable from durable run state, and in supervised mode MUST also be
  emitted as a mailbox event using matriarch's shared event envelope before
  the pause takes effect.

### Key Entities *(include if feature involves data)*

- **Yolo Run**: A durable orchestration record representing one end-to-end Orca
  workflow attempt.
- **Run Stage**: One defined step in the full-cycle workflow, such as plan,
  implement, or review-code.
- **Run Policy**: Ask-level, retry, worktree, and PR-completion settings that
  govern how a run behaves.
- **Run Outcome**: The final completed, blocked, failed, or paused state plus
  links to durable artifacts.
- **Lane Agent Binding**: Optional link between a Yolo Run and a matriarch
  lane identity, present when the run is matriarch-supervised. Carries the
  `lane_id`, `mailbox_path`, and `deployment_kind` so supervision context is
  discoverable from run state without reaching into matriarch internals.

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
- `005-orca-flow-state`, `012-review-model` (supersedes
  `006-orca-review-artifacts`), and `007-orca-context-handoffs` define
  the durable upstream contracts `orca-yolo` consumes.
- `008-orca-capability-packs` may later classify `yolo` as a downstream pack,
  but this feature still needs a complete standalone orchestration contract.
- `010-orca-matriarch` is the multi-spec supervisor that may delegate a
  single-lane run to `orca-yolo` as a Lane Agent. `009` must remain useful in
  standalone mode when matriarch is not in use, and must consume `010`'s lane
  identity, mailbox, and event-envelope contracts when it is.
- `010`'s lane, mailbox, event-envelope, and deployment contracts are
  authoritative for supervised-mode behavior. `009` MUST NOT redefine those
  contracts and MUST reference them by name when expressing supervised-mode
  expectations.
