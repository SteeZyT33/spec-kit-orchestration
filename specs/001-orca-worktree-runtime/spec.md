# Feature Specification: Orca Worktree Runtime Helpers

**Feature Branch**: `001-orca-worktree-runtime`  
**Created**: 2026-04-09  
**Status**: Implemented  
**Input**: User description: "Implement Orca worktree runtime helpers and metadata-backed lifecycle"

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Create And Track Orca Worktrees (Priority: P1)

As an Orca maintainer working on a feature in parallel lanes, I want to create a
worktree through Orca tooling so that the worktree exists in git and is also
registered in Orca metadata as the source of truth.

**Why this priority**: Without runtime-backed worktree creation, Orca’s current
worktree protocol remains a documentation-only concept. This story turns the
protocol into something the workflow can actually use.

**Independent Test**: From a feature branch in this repository, a maintainer can
run the Orca worktree create flow and observe that:
- a git worktree is created at the resolved path
- a lane record is written under `.specify/orca/worktrees/`
- the registry is updated consistently
- the original repository is restored to the default branch when required

**Acceptance Scenarios**:

1. **Given** a valid feature branch and no conflicting lane record, **When** the maintainer runs Orca worktree creation, **Then** a new git worktree is created and registered in Orca metadata.
2. **Given** a target path conflict or invalid worktree destination, **When** the maintainer runs Orca worktree creation, **Then** Orca reports a clear error and does not create partial metadata.
3. **Given** the feature branch is currently checked out in the main repository, **When** Orca creates a worktree, **Then** it restores the main repository to the default branch before creating the new worktree.

---

### User Story 2 - Inspect Active Orca Worktrees (Priority: P2)

As an Orca maintainer, I want to list and inspect active worktrees through Orca
metadata so I can understand which lanes exist, where they live, and whether
their status is consistent.

**Why this priority**: Once worktrees exist, they need to be visible. Without a
stable listing/status view, the metadata model is hard to trust and hard to
debug.

**Independent Test**: After one or more worktrees exist, a maintainer can run
the Orca listing/status flow and see lane ID, feature, branch, path, and status
without needing to inspect raw JSON files manually.

**Acceptance Scenarios**:

1. **Given** one or more valid lane records, **When** the maintainer runs the Orca list flow, **Then** Orca prints a readable summary of active lanes.
2. **Given** registry metadata and git reality have diverged, **When** the maintainer inspects worktrees, **Then** Orca surfaces warnings instead of silently trusting broken state.

---

### User Story 3 - Clean Up Merged Or Retired Worktrees (Priority: P3)

As an Orca maintainer, I want Orca to identify and clean up merged or retired
worktrees so lane state stays accurate and old worktrees do not accumulate
indefinitely.

**Why this priority**: Cleanup is lower priority than creation and visibility,
but without it the registry will decay and command behavior will become noisy.

**Independent Test**: After a lane branch is merged or explicitly retired, a
maintainer can run Orca cleanup and verify that the worktree is safely removed
and metadata is updated consistently.

**Acceptance Scenarios**:

1. **Given** a lane whose branch is already merged, **When** the maintainer runs Orca cleanup, **Then** the worktree is removed safely and the lane metadata is updated.
2. **Given** a lane that is still active or ambiguous, **When** the maintainer runs Orca cleanup, **Then** Orca does not remove it silently.

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right edge cases.
-->

- What happens when the registry exists but a referenced lane file is missing?
- What happens when a lane record exists but the worktree path has been manually deleted?
- What happens when a branch name does not match the intended Orca feature/lane pattern?
- What happens when the configured worktree base path resolves inside the main repository?
- What happens when a cleanup candidate is merged in git but still marked `active` in Orca metadata?

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: Orca MUST provide a runtime helper layer for worktree operations rather than relying only on protocol documentation.
- **FR-002**: Orca MUST support a create flow that creates a git worktree and writes a lane record plus registry update under `.specify/orca/worktrees/`.
- **FR-003**: Orca MUST validate the target worktree path before creation and reject paths that resolve inside the main repository or collide with existing filesystem entries.
- **FR-004**: Orca MUST detect when the current repository is already inside a worktree and avoid unsupported nested worktree creation.
- **FR-005**: Orca MUST restore the main repository to the default branch before creating a worktree for the currently checked-out feature branch when git requires that separation.
- **FR-006**: Orca MUST provide a list or status flow that reports lane ID, feature, branch, path, and status using Orca metadata as the primary source of truth.
- **FR-007**: Orca MUST surface metadata drift warnings when registry state and git worktree state disagree.
- **FR-008**: Orca MUST support a cleanup flow for merged or retired worktrees and MUST update metadata consistently when cleanup succeeds.
- **FR-009**: Orca MUST avoid silently deleting active or ambiguous worktrees during cleanup.
- **FR-010**: Orca MUST expose the worktree runtime through shell helpers first; a higher-level Orca command wrapper may be added later but is not required in this feature.
- **FR-011**: Existing Orca commands are NOT required to consume runtime metadata in this feature; that integration may be delivered as a follow-on feature once the runtime layer is stable.

### Key Entities *(include if feature involves data)*

- **Worktree Registry**: Repo-local index of known Orca lanes, including schema version, lane IDs, and update timestamp.
- **Lane Record**: One metadata document describing a single Orca lane, including feature, branch, path, role, task scope, and lifecycle status.
- **Worktree Operation Result**: The outcome of a create, list, status, or cleanup action, including warnings about drift or invalid state.

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: A maintainer can create a new Orca worktree for a valid feature branch in one explicit Orca flow without manually editing registry JSON.
- **SC-002**: Orca list/status output shows all active lanes for the repository from metadata in a single command execution.
- **SC-003**: Cleanup removes only lanes that are clearly merged or retired and leaves active or ambiguous lanes intact with explicit warnings.
- **SC-004**: The runtime helper layer is sufficient for a follow-on feature to wire `assign`, `code-review`, `cross-review`, and `self-review` to real worktree metadata without redesigning the schema.

## Documentation Impact *(mandatory)*

- **README Impact**: Required
- **Why**: This feature adds operator-visible worktree runtime helpers, lane metadata behavior, and workflow/runtime expectations.
- **Expected Updates**: `README.md`, `docs/worktree-protocol.md`

## Assumptions

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right assumptions based on reasonable defaults
  chosen when the feature description did not specify certain details.
-->

- Orca will continue using `.specify/orca/worktrees/` as the metadata source of truth rather than agent-specific directories.
- The initial implementation may use shell scripts as the runtime surface before adding a dedicated `speckit.orca.worktree` command.
- Worktree base path may need configuration later, but this feature can begin with a sane default and a validated computed path.
- Manual verification is acceptable for the first implementation pass, but the design should leave room for automated tests around helper behavior later.
