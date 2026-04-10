# Feature Specification: Orca Matriarch

**Feature Branch**: `010-orca-matriarch`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "Add a careful multi-spec orchestration layer so Orca can manage multiple feature implementations, agents, worktrees, and review gates without requiring manual human coordination for every lane."

## Context

The current workflow upgrade is already exercising a coordination problem:
multiple specs can be active at once, dependencies matter, and humans are still
manually tracking which lane owns what. `orca-yolo` targets one feature run.
`orca-matriarch` is the higher-level supervisor that coordinates multiple
feature runs safely.

This feature must be treated conservatively. A weak implementation would create
automation theater and hide real blockers. The first version should emphasize
visibility, dependency awareness, lane assignment, and gate tracking over
aggressive autonomous control.

The user also wants a real agent deployment substrate for multi-lane work.
That means `orca-matriarch` needs an explicit answer for supervised lane
deployment, not just passive metadata. In v1, that answer should be narrow:
tmux-backed lane sessions may be launched, attached, resumed, or inspected
explicitly, but Matriarch must not turn into an uncontrolled swarm manager.

In the same spirit, v1 lane semantics should stay narrow: one lane should own
one spec. Multi-spec supervision should come from Matriarch coordinating many
lanes, not from letting one lane become a grab bag of unrelated or loosely
related specs.

For the same reason, v1 should not hide Claude Code or other non-tmux workers
behind a fake absence of deployment. The deployment model should explicitly
support direct interactive CLI sessions as a first-class non-tmux case.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Coordinate Multiple Spec Implementations Without Manual Juggling (Priority: P1)

A maintainer is running several Orca feature lanes in parallel and wants one
system to track ownership, dependencies, and next actions so they do not have
to manage every spec manually.

**Why this priority**: This is the direct operational pain the feature exists
to solve.

**Independent Test**: Start multiple feature lanes with distinct dependencies
and verify Orca can show which lanes are active, blocked, review-ready, or
waiting on another spec.

**Acceptance Scenarios**:

1. **Given** multiple feature specs exist with implementation work in flight,
   **When** the maintainer inspects Matriarch state,
   **Then** Orca can show each lane's current stage, owner/agent, and blocker
   state from durable records.
2. **Given** one feature depends on another,
   **When** the upstream feature is incomplete,
   **Then** Matriarch marks the downstream lane as blocked instead of pretending
   it can progress independently.

---

### User Story 2 - Assign Worktrees And Agents Deliberately (Priority: P1)

A maintainer wants Orca to coordinate agent and worktree assignment so parallel
execution is structured instead of ad hoc.

**Why this priority**: Parallel work without explicit assignment is where lane
drift and duplicate effort begin.

**Independent Test**: Create multiple feature lanes and verify Matriarch can
record or recommend agent/worktree assignment without overwriting lane
boundaries.

**Acceptance Scenarios**:

1. **Given** a feature lane requires isolated implementation,
   **When** Matriarch assigns or records a worktree,
   **Then** the lane metadata links the feature, branch, and worktree identity.
2. **Given** multiple agents are available,
   **When** Matriarch records assignments,
   **Then** each active lane has a clear responsible agent or lane owner.

---

### User Story 3 - Aggregate Review Gates And Merge Readiness (Priority: P2)

A maintainer wants one place to see which active specs are implementation-ready,
review-ready, PR-ready, or blocked by findings.

**Why this priority**: Coordination only becomes truly useful when it exposes
quality gates rather than just task lists.

**Independent Test**: Update multiple features through implementation and
review, then verify Matriarch can summarize per-lane readiness from durable
artifacts instead of chat memory.

**Acceptance Scenarios**:

1. **Given** one lane has passing review artifacts and another does not,
   **When** Matriarch computes readiness,
   **Then** it distinguishes PR-ready work from blocked work using durable
   evidence.
2. **Given** a review stage is missing,
   **When** Matriarch summarizes the lane,
   **Then** it records the missing gate explicitly instead of inferring success.

### Edge Cases

- What happens if a lane is manually edited outside Matriarch? The system MUST
  detect or tolerate drift rather than assuming exclusive control.
- What happens if one agent abandons a lane? Matriarch MUST preserve durable
  lane state so reassignment is possible.
- What happens if dependencies change mid-stream? Matriarch MUST reflect the
  updated graph instead of preserving stale assumptions.
- What happens if a user wants to keep full manual control? The first version
  MUST support visibility and structured coordination without requiring
  autonomous execution.
- What happens if a tmux-backed lane session dies or detaches unexpectedly?
  Matriarch MUST preserve lane ownership and deployment state without claiming
  the lane is healthy or complete.
- What happens if a lane has enough artifact state to be "review-ready" but no
  active assignee or session? Matriarch MUST surface that mismatch explicitly.
- What happens if an execution agent inside a lane hits ambiguity or needs
  approval? The lane agent MUST report back to Matriarch instead of silently
  bypassing supervision or treating itself as user-facing authority.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Orca MUST define a multi-spec orchestration model for coordinating
  multiple feature lanes.
- **FR-001a**: In v1, one lane MUST correspond to exactly one primary spec.
  Multi-spec coordination MUST happen across lanes rather than by assigning
  multiple specs to one lane.
- **FR-002**: `orca-matriarch` MUST track lane identity, stage, ownership, and
  blocker state from durable artifacts.
- **FR-003**: `orca-matriarch` MUST support explicit dependency relationships
  between feature lanes.
- **FR-004**: `orca-matriarch` MUST integrate with worktree-aware execution
  without requiring every lane to use a worktree.
- **FR-005**: `orca-matriarch` MUST integrate with `005-orca-flow-state` for
  per-lane stage visibility.
- **FR-006**: `orca-matriarch` MUST integrate with `006-orca-review-artifacts`
  for review and readiness tracking.
- **FR-007**: `orca-matriarch` MUST integrate with `007-orca-context-handoffs`
  when lane ownership or session context changes.
- **FR-008**: `orca-matriarch` SHOULD integrate with `009-orca-yolo` as a
  single-lane execution worker, but MUST NOT require `009` for the first
  version's coordination value.
- **FR-009**: The first version MUST prioritize observability and safe
  coordination over aggressive autonomy.
- **FR-010**: The system MUST remain provider-agnostic and represent agent
  choices explicitly rather than encoding provider-specific behavior.
- **FR-011**: `orca-matriarch` MUST define an explicit lane lifecycle separate
  from but compatible with feature-level flow state.
- **FR-012**: `orca-matriarch` MUST define dependency semantics that can target
  at least lane existence, lane stage, review readiness, and merge readiness.
- **FR-013**: `orca-matriarch` MUST define ownership and reassignment semantics
  clearly enough that abandoned or reassigned lanes remain auditable.
- **FR-014**: `checkout` behavior MUST default to resolution-only and require
  explicit opt-in before mutating shell, git, or tmux state.
- **FR-015**: The first version MAY support tmux-backed lane deployment, but
  only as an explicit supervised session model with visible state and safe
  failure handling.
- **FR-016**: Tmux deployment MUST NOT be the only execution mode; manual and
  non-tmux lanes must remain first-class.
- **FR-017**: The first version MUST define a minimum supervisory command
  surface and avoid expanding into a broad command family before lifecycle and
  registry behavior are stable.
- **FR-018**: If lane ownership changes while a tmux deployment still exists,
  Matriarch MUST surface that ownership mismatch explicitly and MUST NOT treat
  the old deployment as authoritative without operator confirmation.
- **FR-019**: Lifecycle precedence rules MUST be explicit enough that a lane
  cannot appear simultaneously blocked and unconditionally review-ready without
  a visible explanation.
- **FR-020**: If Matriarch launches a lane agent, that agent MUST report
  blockers, questions, and approval needs back to Matriarch rather than
  bypassing the supervisory layer by default.
- **FR-021**: The first version SHOULD reserve a future grouping concept above
  lanes for coordinating related specs, rather than overloading lane semantics
  to support multi-spec ownership.
- **FR-022**: If Matriarch delegates discrete sub-work inside a lane, that
  delegated work MUST use a claim-safe lifecycle rather than ad hoc ownership
  mutation.
- **FR-023**: Matriarch SHOULD support a durable lane mailbox or report queue
  so launched agents and delegated workers can acknowledge instructions and
  report progress without relying on tmux keystrokes as the source of truth.
- **FR-024**: The first version MUST keep deployment runtime concerns separate
  from coordination state so tmux remains an optional adapter, not the
  canonical data plane.
- **FR-025**: In v1, `lane_id` MUST default to the primary `spec_id` so lane
  metadata, mailbox paths, and deployment naming stay deterministic.
- **FR-026**: The deployment model MUST support a non-tmux `direct-session`
  case for interactive worker CLIs such as Claude Code.
- **FR-027**: Lane metadata MUST expose enough discovery information, including
  mailbox location, that launched worker CLIs do not need hardcoded Orca
  runtime paths.

### Key Entities *(include if feature involves data)*

- **Managed Lane**: One active feature/spec lane under Matriarch supervision.
- **Lane Assignment**: The responsible agent, worktree, and branch metadata for
  one managed lane.
- **Lane Dependency**: A durable relationship indicating one lane cannot
  advance until another reaches a required state.
- **Lane Readiness**: The summarized implementation/review/PR state derived
  from durable artifacts.
- **Lane Lifecycle State**: The supervisory state of a lane such as registered,
  active, blocked, review-ready, or archived.
- **Lane Deployment**: The optional execution attachment for a lane, such as a
  tmux session or direct interactive CLI session, including health and
  attach/resume metadata.
- **Lane Agent**: The execution worker attached to one lane, launched or
  supervised by Matriarch and expected to report blockers upward.
- **Lane Mailbox Event**: A durable message or acknowledgment exchanged between
  Matriarch and a lane-local worker or agent.
- **Lane Task Claim**: A record that one delegated worker has safely claimed a
  unit of lane-local work.
- **Program Group**: A future higher-level grouping for coordinating multiple
  related lanes without changing the one-lane-one-spec rule.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can inspect one durable view and understand the
  state of multiple active feature lanes.
- **SC-002**: Downstream lanes can be marked blocked by explicit dependencies
  instead of relying on human memory.
- **SC-003**: Lane assignment and review-readiness are discoverable without
  reconstructing chat history.
- **SC-004**: A maintainer can determine whether a lane is only registered,
  actively owned, blocked, review-ready, or archived without inferring that
  state from prose.
- **SC-005**: If tmux deployment is enabled for a lane, Matriarch can show the
  deployment state explicitly without confusing deployment health with workflow
  completion.
- **SC-006**: A maintainer can tell when a running tmux session belongs to a
  stale or previous owner rather than the current lane assignee.
- **SC-007**: A maintainer can determine which single spec a lane owns without
  reading surrounding prose or guessing from branch names.
- **SC-008**: A maintainer can inspect durable lane messages or acknowledgments
  without depending on live tmux interaction.

## Documentation Impact *(mandatory)*

- **README Impact**: Required
- **Why**: This feature adds a new supervisory workflow layer for multi-spec coordination, lane ownership, and readiness tracking.
- **Expected Updates**: `README.md`, program/coordination docs, future Matriarch command docs

## Assumptions

- `004-orca-workflow-system-upgrade` remains the umbrella dependency and wave
  authority.
- `005-orca-flow-state`, `006-orca-review-artifacts`, and
  `007-orca-context-handoffs` provide the lower-layer contracts Matriarch
  consumes.
- `009-orca-yolo` may later serve as a worker/runtime for one lane, but this
  feature should deliver coordination value even before YOLO is fully mature.
