# Feature Specification: Orca Capability Packs

**Feature Branch**: `008-orca-capability-packs`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "Create a simpler Orca equivalent to Spex traits so optional workflow behaviors can be enabled intentionally without hard-coding every concern into the base command set."

## Context

Repomix showed that optional capability layering is one of Spex's biggest
architectural advantages. Orca should not copy traits directly, but it still
needs a composition model better than growing every command forever.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Optional Workflow Capabilities Stay Explicit (Priority: P1)

A maintainer wants to enable or evolve cross-cutting Orca behaviors such as
brainstorm memory, flow state, worktrees, review layers, or yolo orchestration
without rewriting every base command.

**Why this priority**: Without a composition model, Orca will keep accumulating
hard-coded behavior and become unreadable.

**Independent Test**: Define one optional capability pack and verify Orca can
document and reason about that behavior separately from the base workflow
surface.

### Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Orca MUST define a composition model for optional workflow
  capabilities.
- **FR-002**: The composition model MUST remain simpler and more inspectable
  than Spex traits-as-implemented.
- **FR-003**: Capability packs MUST be compatible with provider-agnostic Orca
  behavior.
- **FR-004**: Core commands MUST remain understandable even as optional
  capability packs are introduced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Orca can describe optional workflow behavior without hard-coding
  every concern into the core command set.
- **SC-002**: New cross-cutting behavior can be modeled with less command drift.
- **SC-003**: Orca can inspect effective pack activation for a repo without reading command prose manually.
