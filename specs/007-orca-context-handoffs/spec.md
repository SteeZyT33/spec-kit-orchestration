# Feature Specification: Orca Context Handoffs

**Feature Branch**: `007-orca-context-handoffs`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "Add explicit context handoff behavior between brainstorm, specify, plan, worktrees, implementation, and review so Orca can preserve continuity without depending on active chat state."

## Context

Repomix showed that branch-based artifact resolution and explicit handoff
artifacts are key to reliable context isolation. Orca still leaves many stage
transitions implicit.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Move Between Workflow Stages Without Losing Intent (Priority: P1)

A developer moves from brainstorm to spec to planning to implementation and
wants Orca to preserve the key framing and decisions without replaying the
whole conversation.

**Why this priority**: This is what makes workflow state usable across tools,
worktrees, and fresh sessions.

**Independent Test**: Move across multiple workflow stages and verify the next
stage can resolve the intended upstream artifacts and context summary.

### Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Orca MUST define explicit context handoff behavior between major
  workflow stages.
- **FR-002**: Handoffs MUST prefer durable artifacts and branch/worktree context
  over transient chat memory.
- **FR-003**: Handoffs MUST be compatible with worktree-based execution.
- **FR-004**: Handoffs MUST expose enough context for later review and
  orchestration stages.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A later stage can identify its relevant upstream artifacts without
  human re-explanation.
- **SC-002**: Moving into a new worktree or fresh session does not destroy
  workflow continuity.

## Documentation Impact *(mandatory)*

- **README Impact**: Required
- **Why**: This feature changes how Orca instructs users and agents to resume work across sessions, owners, or worktrees.
- **Expected Updates**: `README.md`, handoff-related command docs, protocol docs
