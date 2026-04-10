# Feature Specification: Orca Workflow System Upgrade

**Feature Branch**: `004-orca-workflow-system-upgrade`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "Upgrade Orca from a command bundle into a coherent workflow system using the repomix harvest: durable brainstorm memory, stronger cross-review agent support, flow state, review artifacts, context handoffs, capability packs, yolo orchestration, multi-spec management, and self-evolution."

## Context

The repomix analysis of `cc-spex` clarified that Orca's next upgrade is not one
feature. It is a coordinated application-level evolution:

- memory
- state
- review architecture
- handoffs
- composable capabilities
- orchestration
- multi-spec management
- self-evolution

This umbrella spec exists to define the whole upgrade program so the individual
specs remain parts of one system instead of drifting into unrelated command
patches. The later program now also includes a supervised multi-spec manager
(`010-orca-matriarch`) and a self-upgrade/adoption system (`011-orca-evolve`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Orca Feels Like One Workflow System (Priority: P1)

A developer uses Orca across ideation, planning, implementation, and review and
expects the system to preserve context, expose next steps, and keep artifacts
linked instead of behaving like disconnected commands.

**Why this priority**: This is the actual product upgrade. Without this, Orca
remains a command bundle with scattered improvements.

**Independent Test**: Starting from a rough idea, a developer can trace the
workflow through brainstorm memory, spec artifacts, review artifacts, and flow
state without depending on chat history.

**Acceptance Scenarios**:

1. **Given** a brainstorm becomes a feature, **When** the user later returns,
   **Then** Orca can expose the chain from idea to spec to implementation
   review artifacts.
2. **Given** workflow execution is interrupted, **When** the user resumes,
   **Then** Orca can determine current stage and useful next actions from
   durable artifacts.

---

### User Story 2 - Orca Supports Parallel And Multi-Agent Execution Safely (Priority: P1)

A developer wants to implement Orca upgrades with parallel agents and later use
Orca itself in parallel lanes without losing state or review quality.

**Why this priority**: Parallel execution is part of the intended delivery
model, so the upgrade needs clean subsystem boundaries and durable handoffs.

**Independent Test**: Separate Orca subsystems can be implemented in parallel
from their specs without conflicting on hidden runtime assumptions.

**Acceptance Scenarios**:

1. **Given** multiple child specs are in flight, **When** agents work in
   parallel, **Then** the shared upgrade program still has clear system
   boundaries and integration order.
2. **Given** one subsystem is incomplete, **When** another subsystem is
   implemented, **Then** the incomplete area is represented through explicit
   contracts rather than hidden assumptions.

---

### User Story 3 - Orca Gains Full-Cycle Orchestration On Stable Foundations (Priority: P2)

A developer eventually wants `orca-yolo`, but only after memory, state, review,
and handoffs are real enough to support it.

**Why this priority**: The upgrade should sequence dependencies correctly and
avoid building orchestration on weak primitives.

**Independent Test**: The umbrella spec defines a program order where `orca-yolo`
is downstream of the supporting workflow layers instead of preceding them.

**Acceptance Scenarios**:

1. **Given** the upgrade program is followed, **When** `orca-yolo` is later
   implemented, **Then** it depends on durable memory/state/review primitives
   instead of inventing them.

### Edge Cases

- What happens if one child spec changes direction? The umbrella upgrade MUST
  keep explicit subsystem boundaries and integration contracts.
- What happens if implementation order changes? The umbrella upgrade MUST define
  dependency order based on actual prerequisites, not only numeric sequence.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Orca MUST define the workflow-system upgrade as a coordinated set
  of child specs rather than an unstructured list of ideas.
- **FR-002**: The upgrade MUST include durable brainstorm memory.
- **FR-003**: The upgrade MUST include expanded cross-review agent selection and
  support tiers.
- **FR-004**: The upgrade MUST include persistent flow state.
- **FR-005**: The upgrade MUST include explicit review artifacts.
- **FR-006**: The upgrade MUST include context handoff behavior between stages
  and worktrees.
- **FR-007**: The upgrade MUST include a capability-pack or equivalent
  composition model for optional workflow behavior.
- **FR-008**: The upgrade MUST treat `orca-yolo` as a downstream orchestration
  layer, not the foundation.
- **FR-009**: The upgrade MUST include a carefully-scoped multi-spec
  orchestration layer for coordinating multiple feature implementations.
- **FR-010**: The upgrade MUST include an Orca self-evolution capability for
  harvesting and adopting desired patterns from external repos such as Spex.
- **FR-011**: The upgrade program MUST preserve provider-agnostic behavior
  across all child features.
- **FR-012**: The upgrade program MUST be structured so parallel implementation
  can be coordinated through explicit subsystem contracts.

### Key Entities *(include if feature involves data)*

- **Upgrade Program**: The umbrella application upgrade spanning multiple Orca
  subsystem specs.
- **Child Spec**: A feature spec representing one upgrade subsystem such as
  brainstorm memory, flow state, or capability packs.
- **Integration Contract**: The explicit boundary between child specs so they
  can be implemented independently and later composed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every major subsystem required by the repomix harvest is captured
  in an explicit Orca spec.
- **SC-002**: The upgrade program defines a coherent dependency order for later
  implementation.
- **SC-003**: The resulting spec tree is sufficient to support parallel
  implementation planning without inventing hidden subsystem behavior.

## Documentation Impact *(mandatory)*

- **README Impact**: Required
- **Why**: This umbrella feature changes Orca's public product shape and roadmap-visible status by organizing shipped foundations and pending workflow-system waves.
- **Expected Updates**: `README.md`, `docs/orca-roadmap.md`, `docs/orca-harvest-matrix.md`

## Assumptions

- `002-brainstorm-memory` and `003-cross-review-agent-selection` are already
  part of this upgrade program.
- Remaining upgrade features can start at draft-spec fidelity first and be
  refined before implementation.
