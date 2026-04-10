# Feature Specification: Orca Flow State

**Feature Branch**: `005-orca-flow-state`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "Add durable flow state so Orca can show where a feature is in the workflow, what reviews have happened, and what the next step should be."

## Context

Repomix showed that persistent workflow state is one of the missing foundations
between brainstorm memory and later orchestration. Orca currently relies too
much on branch inference, ad hoc artifact presence, and human memory to answer
basic workflow questions.

The right first version is not a heavy hidden state machine. It is a
computed-first model:

- durable artifacts are primary truth
- flow state is derived from those artifacts
- thin persisted metadata is allowed only where resumability or cached
  next-step guidance genuinely needs it

This feature should establish the state model first. It should not try to ship
full `orca-yolo`, a statusline-first UI, or a complete review-artifact redesign
inside the same scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resume A Feature Reliably (Priority: P1)

A developer returns to a feature and wants Orca to determine current stage,
completed milestones, and the next likely action without opening every file or
replaying prior chat context.

**Why this priority**: This is the main value of flow state and a prerequisite
for later resume/start-from behavior.

**Independent Test**: Create a feature with a partial set of durable artifacts
such as `spec.md`, `plan.md`, `tasks.md`, and one or more review artifacts, then
verify Orca can compute current stage and next-step guidance from those
artifacts alone.

**Acceptance Scenarios**:

1. **Given** a feature with `spec.md` and `plan.md` but no `tasks.md`,
   **When** Orca inspects flow state, **Then** it reports planning as complete,
   task decomposition as incomplete, and identifies the next likely step as task
   generation.
2. **Given** a feature with implementation artifacts and review evidence,
   **When** Orca computes flow state, **Then** it includes both build progress
   and review-stage progress in the result.
3. **Given** a feature is revisited from a fresh session, **When** Orca resolves
   flow state, **Then** it does not require access to the original chat history.

---

### User Story 2 - Track Review Completion Separately From Build Progress (Priority: P1)

A developer wants to know not only whether implementation happened, but whether
spec review, plan review, code review, cross-review, and PR review stages are
complete or still missing.

**Why this priority**: Repomix showed that review evidence is part of workflow
state, not just supplemental notes.

**Independent Test**: Record review evidence separately from implementation
progress and verify Orca can report review completion without conflating it with
coding progress.

**Acceptance Scenarios**:

1. **Given** implementation work is present but code review has not happened,
   **When** Orca computes flow state, **Then** it marks implementation progress
   ahead of review progress rather than treating the feature as simply "done."
2. **Given** spec and plan review evidence exists but implementation has not
   started, **When** Orca computes flow state, **Then** it reports early-stage
   review completion separately from later review milestones.
3. **Given** cross-review or PR review has not happened,
   **When** Orca reports current state, **Then** those missing stages remain
   visible as incomplete review milestones.

---

### User Story 3 - Gracefully Handle Partial Or Ambiguous Artifact Sets (Priority: P2)

A developer has a feature with missing, hand-edited, or partially complete
artifacts and needs Orca to degrade safely instead of inventing certainty.

**Why this priority**: Flow state will be untrustworthy if it only works on
perfect artifact sets.

**Independent Test**: Remove or partially edit expected artifacts and verify
Orca reports ambiguity or incomplete state explicitly rather than over-claiming
progress.

**Acceptance Scenarios**:

1. **Given** expected artifacts are missing,
   **When** Orca computes flow state, **Then** it reports incomplete or unknown
   state explicitly instead of assuming hidden completion.
2. **Given** artifact signals conflict with each other,
   **When** Orca computes flow state, **Then** it surfaces that ambiguity rather
   than silently choosing a misleading status.
3. **Given** only early-stage artifacts exist,
   **When** Orca computes flow state, **Then** it still returns a useful partial
   state and next-step hint.

---

### User Story 4 - Provide A Stable State Model For Later Orca Systems (Priority: P2)

A maintainer wants later Orca systems such as context handoffs, status surfaces,
review architecture, and `orca-yolo` to consume a shared workflow-state model
instead of inventing their own.

**Why this priority**: This feature is foundational, so its contract matters as
much as its first implementation.

**Independent Test**: Inspect the flow-state model and verify it exposes enough
structure for later systems to consume current stage, review milestones,
ambiguity, and next-step information.

**Acceptance Scenarios**:

1. **Given** another Orca subsystem needs workflow progress,
   **When** it reads flow state, **Then** it can discover current stage and next
   likely action through a stable contract.
2. **Given** resumability is introduced later,
   **When** `orca-yolo` or a future resume surface uses flow state, **Then** it
   can build on the state model rather than redefining workflow stages.

### Edge Cases

- What happens when no review artifacts exist yet? The system MUST still report
  useful build-stage flow state without pretending review completion.
- What happens when review evidence exists for a later stage but a prior stage
  artifact is missing? The system MUST surface ambiguous or inconsistent state.
- What happens when a feature has brainstorm memory but no spec yet? The system
  MUST represent that pre-spec state as the canonical `brainstorm` stage rather
  than inventing a second pre-spec enum.
- What happens when the current branch does not match the latest artifact set?
  The system MUST prefer durable artifact evidence and report branch ambiguity
  rather than assuming one hidden truth.
- What happens when worktree lane metadata exists? The system MUST be able to
  incorporate it as contextual evidence without making lane state the only truth.
- What happens when resumability metadata is absent? The system MUST still be
  able to compute state from durable workflow artifacts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Orca MUST maintain a durable feature-level flow-state model.
- **FR-002**: Flow state MUST be derivable from durable workflow artifacts
  rather than chat/session history.
- **FR-003**: Flow state MUST expose at minimum: current stage, completed
  milestones, incomplete milestones, and next likely step.
- **FR-004**: Flow state MUST track review completion separately from
  implementation completion.
- **FR-005**: Flow state MUST remain provider-agnostic and MUST NOT rely on
  Claude-specific statusline or session substrate.
- **FR-006**: Flow state MUST degrade safely when artifacts are partial,
  ambiguous, or conflicting.
- **FR-007**: Flow state MUST define a canonical stage model for Orca features.
- **FR-008**: The canonical stage model MUST be stable enough for later Orca
  systems such as review artifacts, context handoffs, and `orca-yolo` to reuse.
- **FR-009**: Flow state MUST support pre-implementation stages as well as
  implementation and review stages.
- **FR-009a**: When pre-spec evidence exists, Orca MUST represent that state as
  the canonical `brainstorm` stage. `current_stage` MAY be `null` only when the
  evidence is materially conflicting rather than merely early.
- **FR-010**: Flow state MUST allow review milestones to be represented as
  distinct progress signals rather than only as a single terminal status.
- **FR-011**: Orca MUST be able to compute a useful partial state even when not
  all expected workflow artifacts exist.
- **FR-012**: If thin persisted metadata is used for resume/start-from or cached
  next-step guidance, that metadata MUST remain secondary to durable artifact
  truth and MUST be safely regenerable or ignorable.
- **FR-013**: Flow state MUST be compatible with worktree-aware execution, but
  worktree metadata MUST NOT be the only workflow truth.
- **FR-014**: Flow state MUST be usable later by `orca-yolo`, status surfaces,
  and adjacent Orca commands without requiring those systems to redefine stage
  semantics.

### Key Entities *(include if feature involves data)*

- **Flow Stage**: A canonical Orca workflow stage such as brainstorm, specify,
  plan, tasks, assign, implement, code-review, cross-review, pr-review, or
  self-review.
- **Pre-Spec State**: The early workflow condition where brainstorm evidence
  exists but `spec.md` does not. In this feature it is represented by the
  canonical `brainstorm` stage, not a separate enum.
- **Flow Milestone**: A durable completion signal for a stage or review gate
  derived from artifacts rather than inferred only from recent chat context.
- **Flow State Result**: The computed view of a feature's workflow progress,
  including current stage, completed milestones, ambiguous signals, and next
  likely step.
- **Review Milestone**: A flow-state sub-signal representing review completion
  separately from build progress.
- **Resume Metadata**: Optional thin persisted metadata used to assist
  resumability or cached next-step guidance without replacing artifact truth.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can identify the current feature stage from durable Orca
  artifacts without manually opening every workflow file.
- **SC-002**: A user can identify unfinished review stages separately from
  implementation progress.
- **SC-003**: Orca can return a useful next-step hint from partial but valid
  artifact sets.
- **SC-004**: Orca reports ambiguity explicitly when workflow signals conflict
  instead of inventing false certainty.
- **SC-005**: Later Orca systems can consume the flow-state contract without
  redefining the core workflow stage model.

## Assumptions

- The first version should be computed-first rather than centered on a heavy
  persisted state registry.
- Review artifacts may still evolve in `006-orca-review-artifacts`, so `005`
  should define the state model and evidence expectations cleanly without trying
  to redesign all review artifacts itself.
- Resume/start-from behavior may use thin persisted metadata later, but `005`
  should not force full orchestration semantics into the first implementation.
- A visible statusline or dashboard may come later, but UX rendering is not the
  foundation of this feature.
