# Feature Specification: Orca Review Artifacts

**Feature Branch**: `006-orca-review-artifacts`  
**Created**: 2026-04-09  
**Status**: Implemented  
**Input**: User description: "Split Orca review evidence into clearer durable artifacts for spec, plan, code, cross-review, and PR review so workflow state and later orchestration have clean review boundaries."

## Context

Repomix highlighted split review artifacts as one of Spex's strongest ideas.
Orca currently relies too heavily on a single `review.md` shape and command
memory.

The right first version is additive rather than destructive:

- keep `review.md` as the umbrella summary/index
- introduce stage-specific review artifacts as the durable source of truth
- keep `self-review.md` separate from implementation review artifacts

This feature is adjacent to `003-cross-review-agent-selection`,
`005-orca-flow-state`, `007-orca-context-handoffs`, and `009-orca-yolo`, so
its main job is to make review evidence explicit enough for later systems to
consume without inventing their own semantics.

Current repo reality is still pre-migration:

- existing review command docs still point primarily at `review.md`
- the stage-specific artifact contract in this spec is a target state, not a
  completed implementation
- FR-007, FR-008, and FR-009 are only satisfied after the corresponding
  command-doc and template updates land

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review Stages Leave Clear Durable Evidence (Priority: P1)

A developer wants separate durable review artifacts for code review,
cross-review, and PR review so later users and tools can see exactly what was
reviewed and when.

**Why this priority**: Review architecture only becomes real when stage
evidence is explicit and durable.

**Independent Test**: Run or simulate `code-review`, `cross-review`, and
`pr-review`, then verify each stage creates or updates its intended primary
artifact instead of collapsing everything into one ambiguous file.

**Acceptance Scenarios**:

1. **Given** `speckit.orca.code-review` is run for a feature,
   **When** the review completes,
   **Then** `review-code.md` exists or is updated as the primary durable record
   for implementation review.
2. **Given** `speckit.orca.cross-review` is run for a feature,
   **When** the review completes,
   **Then** `review-cross.md` exists or is updated as the primary durable record
   for alternate-agent or adversarial review.
3. **Given** `speckit.orca.pr-review` is run for a feature,
   **When** the review completes,
   **Then** `review-pr.md` exists or is updated as the primary durable record
   for PR lifecycle review evidence.

---

### User Story 2 - A Reader Can Understand Review Status From One Entry Point (Priority: P1)

A developer wants one human-friendly review entrypoint without losing the
separate durable stage artifacts underneath it.

**Why this priority**: Orca should gain durable structure without making review
navigation worse.

**Independent Test**: Open only `review.md` for a feature and verify it shows
which stage artifacts exist, which review stages are complete or missing, and
where to find detailed findings.

**Acceptance Scenarios**:

1. **Given** one or more stage-specific review artifacts exist,
   **When** a user opens `review.md`,
   **Then** it summarizes available review stages and points to the relevant
   stage artifact files.
2. **Given** a stage artifact is missing,
   **When** a user opens `review.md`,
   **Then** the summary reflects that gap instead of implying the stage
   happened.
3. **Given** multiple review stages have findings,
   **When** `review.md` is updated,
   **Then** it captures high-level blockers and status without duplicating the
   full detailed findings from every stage artifact.

---

### User Story 3 - Later Orca Systems Can Consume Review Evidence Reliably (Priority: P1)

A maintainer wants `005-orca-flow-state` and later systems such as context
handoffs and `orca-yolo` to determine review progress from stable artifact
contracts instead of parsing one generic review note.

**Why this priority**: Review artifacts are not only for humans. They are part
of Orca's workflow substrate.

**Independent Test**: Inspect the artifact set for a feature and verify a later
consumer can identify completed and missing review stages from stage artifacts
alone, using `review.md` only as an overview layer.

**Acceptance Scenarios**:

1. **Given** `review-code.md` exists and `review-cross.md` does not,
   **When** a later Orca system evaluates review state,
   **Then** it can distinguish completed code review from missing cross-review.
2. **Given** `review.md` exists but no stage artifact exists for a claimed
   stage,
   **When** a later Orca system evaluates review state,
   **Then** it does not treat the summary file alone as sufficient durable
   proof of stage completion.
3. **Given** review artifacts are hand-inspected without prior chat context,
   **When** a maintainer checks the feature directory,
   **Then** the review stage boundaries remain discoverable and interpretable.

---

### User Story 4 - Cross-Review, PR Review, And Self-Review Stay Distinct (Priority: P2)

A developer wants alternate-agent review, PR lifecycle review, and personal
retrospective review to remain clearly separated so findings are not conflated.

**Why this priority**: The review model will stay ambiguous if all late-stage
review activity merges back together.

**Independent Test**: Produce or simulate `cross-review`, `pr-review`, and
`self-review` outputs and verify the resulting artifact set makes the source and
purpose of each review obvious.

**Acceptance Scenarios**:

1. **Given** `cross-review` is run on implementation work,
   **When** artifacts are inspected later,
   **Then** alternate-agent findings are stored in `review-cross.md` rather than
   mixed into `review-code.md`.
2. **Given** PR comments are reviewed and resolved,
   **When** artifacts are inspected later,
   **Then** that lifecycle evidence is stored in `review-pr.md` rather than
   mixed into `review-cross.md`.
3. **Given** `self-review` is run,
   **When** artifacts are inspected later,
   **Then** the retrospective remains in `self-review.md` and is not treated as
   a substitute for code review or cross-review evidence.

### Edge Cases

- What happens when only `review.md` exists from older Orca behavior? The
  system MUST support additive migration without pretending that all stage
  artifacts already exist.
- What happens when a stage artifact exists but `review.md` is stale or
  missing? The system MUST preserve the stage artifact as primary durable
  evidence and treat the summary layer as secondary.
- What happens when `cross-review` is code-scoped? The system MUST still keep
  alternate-agent findings distinct from primary implementation review evidence.
- What happens when no PR exists yet? The system MUST allow `review-pr.md` to
  remain absent without blocking earlier review-stage artifacts.
- What happens when future spec or plan review artifacts are not yet in active
  use? The system MUST allow `review-spec.md` and `review-plan.md` to remain
  optional extension points rather than required files in the first version.
- What happens when a human edits review files manually? The system MUST prefer
  explicit artifact ownership rules over ambiguous inference from prose alone.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Orca MUST define explicit durable review artifacts for major
  review stages rather than relying only on a single generic review file.
- **FR-002**: `review-code.md`, `review-cross.md`, and `review-pr.md` MUST be
  treated as the primary durable artifacts for code review, cross-review, and
  PR review respectively.
- **FR-003**: `self-review.md` MUST remain a distinct process artifact and MUST
  NOT be treated as the primary durable record for code review, cross-review,
  or PR review.
- **FR-004**: Orca MUST retain `review.md` as a human-facing summary/index in
  the first version rather than forcing an abrupt migration away from the
  current entrypoint.
- **FR-005**: `review.md` MUST summarize review-stage status and point to the
  relevant stage artifacts, but MUST NOT be the only durable evidence of stage
  completion.
- **FR-006**: Each review command MUST have a clear primary artifact ownership
  model so review findings are not ambiguously split across multiple durable
  files.
- **FR-007**: `speckit.orca.code-review` MUST own `review-code.md` as its
  primary durable artifact.
- **FR-008**: `speckit.orca.cross-review` MUST own `review-cross.md` as its
  primary durable artifact.
- **FR-009**: `speckit.orca.pr-review` MUST own `review-pr.md` as its primary
  durable artifact.
- **FR-010**: Orca MUST keep cross-review and PR review evidence distinguishable
  from code review evidence.
- **FR-011**: The review artifact model MUST be consumable by `005-orca-flow-state`
  and later Orca systems without requiring them to parse one ambiguous
  umbrella file as the sole source of truth.
- **FR-012**: The first implementation MUST support additive migration from
  legacy `review.md`-centric behavior without requiring historical backfill of
  every existing feature.
- **FR-013**: The artifact model MUST remain provider-agnostic and MUST NOT
  encode Claude-specific review semantics.
- **FR-014**: Orca SHOULD reserve `review-spec.md` and `review-plan.md` as
  future-ready extension points for dedicated design-stage review flows.
- **FR-015**: Later consumers MUST be able to detect missing review stages from
  artifact presence and ownership rules without needing the original chat
  session.
- **FR-016**: The first version MUST define a concrete detection contract for
  how later consumers such as `005-orca-flow-state` determine whether a review
  stage is present, missing, or summary-only.
- **FR-017**: The first version MUST define a minimal structural contract for
  stage artifacts so later systems and humans can distinguish summary/index
  files from stage evidence without inventing ad hoc formats.

### Key Entities *(include if feature involves data)*

- **Review Artifact**: A durable file representing the evidence for one review
  stage or the summary/index layer of the review system.
- **Stage Artifact**: A primary review artifact for a specific review boundary,
  such as `review-code.md`, `review-cross.md`, or `review-pr.md`.
- **Summary Index**: The umbrella `review.md` artifact that summarizes stage
  status, blockers, and links without replacing stage-specific evidence.
- **Review Stage**: A workflow review boundary such as `spec`, `plan`, `code`,
  `cross`, `pr`, or `self`.
- **Ownership Rule**: The contract that maps an Orca review command to the
  primary artifact it is responsible for producing or updating.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reader can determine which major Orca review stages were
  completed from durable artifacts alone without reading prior chat history.
- **SC-002**: A reader can open `review.md` and identify the available stage
  artifacts and high-level review status without losing access to detailed
  stage-specific findings.
- **SC-003**: `005-orca-flow-state` and later Orca systems can consume review
  stage evidence without treating `review.md` as the only authoritative review
  record.
- **SC-004**: Cross-review, PR review, and self-review evidence remain
  durably distinguishable from each other and from primary code review
  findings.
- **SC-005**: Orca can introduce the new artifact model additively without
  requiring immediate migration of every historical `review.md` file in the
  repository.
- **SC-006**: A maintainer can determine the presence or absence of code review,
  cross-review, and PR review by applying the documented artifact detection
  rules without consulting hidden runtime state.

## Documentation Impact *(mandatory)*

- **README Impact**: Required
- **Why**: This feature changes the durable review file model and therefore alters operator-visible review workflow and artifact expectations.
- **Expected Updates**: `README.md`, `commands/code-review.md`, `commands/cross-review.md`, `commands/pr-review.md`

## Assumptions

- The first implementation should solve artifact architecture and ownership, not
  every review-behavior problem in the same feature.
- `005-orca-flow-state` is a direct consumer of this artifact model, so summary
  vs stage-artifact semantics must stay explicit.
- `003-cross-review-agent-selection` may change who performs cross-review, but
  it should not redefine where cross-review evidence lives.
- Dedicated spec and plan review commands may arrive later, so this feature
  should leave a clean extension path without requiring those commands now.
- Until the review commands are updated, current command docs remain a known
  contradiction to the desired end state and should be treated as migration
  debt rather than proof that the artifact contract is already live.
