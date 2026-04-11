# Implementation Plan: Orca Workflow System Upgrade

**Branch**: `004-orca-workflow-system-upgrade` | **Date**: 2026-04-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-orca-workflow-system-upgrade/spec.md`

## Summary

Define Orca's application-level workflow upgrade as a coordinated program of
subsystem features rather than a loose set of command improvements. This plan
turns the repomix harvest into an executable upgrade architecture with:

- an explicit subsystem inventory
- dependency-ordered implementation waves
- integration contracts between child specs
- program-level checkpoints before later orchestration work such as
  `orca-yolo`

This feature does not implement the subsystem runtimes itself. It defines how
the subsystem specs fit together, reconciles that design with the repo's
current merged state, and gives future implementation work one authoritative
system map.

## Technical Context

**Language/Version**: Markdown program artifacts, Spec Kit feature specs, plan/task docs, and repo docs
**Primary Dependencies**: existing Orca specs (`001` through `011`), repomix harvest findings, current worktree/runtime/review direction in this repo
**Storage**: feature docs under `specs/004-orca-workflow-system-upgrade/` plus references to child feature directories
**Testing**: document-level consistency checks, dependency ordering review, and later child-spec planning alignment
**Target Platform**: Orca repository workflow planning and later multi-agent implementation coordination
**Project Type**: application-upgrade program spec / integration architecture
**Performance Goals**: planning artifacts should make implementation order and boundaries immediately legible to maintainers and parallel agents
**Constraints**: provider-agnostic system direction, no monolithic fake implementation plan, must support safe parallel work, must preserve clear system boundaries for later `orca-yolo` adoption
**Scale/Scope**: whole-application upgrade spanning multiple subsystem specs and multiple later implementation waves

## Constitution Check

### Pre-design gates

1. **Provider-agnostic orchestration**: pass. The upgrade program keeps
   provider-agnostic behavior as a system-level requirement across child specs.
2. **Spec-driven delivery**: pass. The workflow-system upgrade is now explicitly
   represented as a spec with planning artifacts.
3. **Safe parallel work**: pass with emphasis. A core purpose of this feature is
   to make parallel implementation safe through explicit boundaries and
   integration contracts.
4. **Verification before convenience**: pass. This feature uses artifact-level
   verification and program checkpoints rather than pretending all subsystem
   work can be verified in one runtime.
5. **Small, composable runtime surfaces**: pass. The upgrade explicitly
   decomposes the workflow system into smaller subsystem specs rather than one
   monolithic implementation.

### Post-design check

The chosen design remains constitution-aligned because it:

- keeps the system decomposed into composable child features
- defines explicit rather than hidden integration contracts
- sequences orchestration after lower-level workflow primitives exist
- improves safety for future parallel agent work

No constitution violations need justification.

## Project Structure

### Documentation (this feature)

```text
specs/004-orca-workflow-system-upgrade/
├── spec.md
├── brainstorm.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── upgrade-program.md
│   ├── subsystem-integration.md
│   └── implementation-waves.md
└── tasks.md
```

### Source Code (repository root)

```text
specs/
├── 001-orca-worktree-runtime/
├── 002-brainstorm-memory/
├── 003-cross-review-agent-selection/
├── 005-orca-flow-state/
├── 006-orca-review-artifacts/
├── 007-orca-context-handoffs/
├── 008-orca-capability-packs/
├── 009-orca-yolo/
├── 010-orca-matriarch/
└── 011-orca-evolve/

docs/
├── orca-harvest-matrix.md
├── orca-roadmap.md
└── orca-v1.4-design.md
```

**Structure Decision**: Treat `004` as the integration and sequencing layer for
the entire application upgrade. It should primarily modify planning artifacts,
integration contracts, and child-spec coordination rather than introducing
runtime code directly.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Umbrella spec plus child specs | The upgrade spans multiple independent subsystems with real dependencies | A flat roadmap note would not constrain implementation drift or parallel-agent assumptions |
| Program-level contracts without direct runtime code | Needed to make later implementation safe and ordered | Jumping straight to implementation would cause subsystem drift and weak orchestration foundations |

## Research Decisions

### 1. The upgrade needs an umbrella integration layer

Decision: use `004` as the program-level integration spec for the workflow
system upgrade.

Rationale:

- keeps the repomix harvest coherent
- gives child specs one explicit system context
- prevents implementation order from drifting into numbering-by-default

Alternatives considered:

- separate child specs only: too loose
- one monolithic Orca v2 spec: too heavy and not parallel-friendly

### 2. Child specs remain the implementation units

Decision: child specs own subsystem detail and later implementation work.

Current child set:

- `002` brainstorm-memory
- `003` cross-review-agent-selection
- `005` flow-state
- `006` review-artifacts
- `007` context-handoffs
- `008` capability-packs
- `009` yolo
- `010` matriarch
- `011` evolve

Rationale:

- preserves modularity
- enables later parallel execution
- keeps each subsystem independently reviewable

Alternatives considered:

- fold subsystem details back into `004`: would make the program spec too large

### 3. Implementation should proceed in waves, not numeric order

Decision: define implementation waves by dependency and leverage rather than
feature-number order.

Wave 1:

- `001` worktree-runtime
- `003` cross-review-agent-selection
- `002` brainstorm-memory
- `005` flow-state
- `006` review-artifacts
- `007` context-handoffs
- `008` capability-packs

Wave 2:

- `009` yolo

Wave 3:

- `010` matriarch

Wave 4:

- `011` evolve

Rationale:

- review infrastructure helps later work immediately
- memory and state are prerequisites for later orchestration
- yolo should remain downstream
- matriarch is a supervision layer, not the foundation
- evolve needs stable Orca destinations to map against

Alternatives considered:

- strict numeric order: simpler mechanically, but architecturally weak

### 4. `004` should define checkpoints before `orca-yolo`

Decision: the umbrella plan must define readiness checkpoints that later child
work must satisfy before `009` is implemented.

Minimum checkpoints:

- durable brainstorm memory exists
- cross-review agent selection is trustworthy
- flow state can express current stage
- review artifacts are durable and discoverable
- context handoffs are explicit enough for fresh-session continuity

Rationale:

- prevents orchestration from inventing missing primitives at runtime

### 5. Merge chronology and dependency order must both be documented

Decision: `004` should describe the ideal dependency-driven wave model and the
repo's current merged state separately when they diverge.

Rationale:

- `010-orca-matriarch` is already merged while `009-orca-yolo` remains pending
- that is acceptable because `010` degrades safely to manual and direct-session
  lane supervision
- maintainers still need one accurate architecture story

## Design Decisions

### 1. Program-level contracts are first-class artifacts

`004` should define:

- what child specs exist
- what each child spec owns
- what each child spec may assume about the others
- what checkpoints govern later implementation waves

### 2. Parallel-safe boundaries matter more than fake implementation detail

This feature should be specific about subsystem boundaries and integration
rules, but should not pretend to know child runtime details that belong in the
child specs and plans.

### 3. `004` coordinates, it does not subsume

The umbrella upgrade should not swallow the child features. It should remain the
integration and sequencing layer that keeps them coherent.

## Implementation Phases

### Phase 0: Subsystem inventory and ownership

Define:

- the subsystem list
- ownership boundaries
- dependency map

### Phase 1: Integration contracts

Define:

- shared assumptions between child specs
- what outputs each subsystem provides to the next
- what readiness means between waves

### Phase 2: Wave planning and checkpoints

Define:

- implementation waves
- parallel-safe work sets
- program-level checkpoints before later orchestration work

## Verification Strategy

### Primary verification

Document-level verification:

1. confirm each repomix-derived subsystem exists as an explicit spec
2. confirm each child spec has a clear place in the upgrade waves
3. confirm `orca-yolo` is downstream of its prerequisites
4. confirm parallel implementation can be reasoned about without hidden
   subsystem assumptions

### Secondary verification

- cross-check child-spec references and integration contracts for drift
- ensure wave ordering reflects actual dependencies rather than numbering
- later self-review should validate whether implementation followed the upgrade
  program cleanly

## Risks

### 1. Umbrella spec becomes a duplicate roadmap

If `004` only restates the roadmap, it will not actually constrain delivery.

Mitigation:

- define real contracts and checkpoints
- make wave membership explicit

### 2. Child specs drift away from the program

If `004` is not kept aligned with child planning, the program will decay.

Mitigation:

- explicit child inventory
- integration contract artifacts
- later review against wave checkpoints

### 3. Parallel implementation outruns planning

If agents start implementing child specs before the subsystem contracts are
clear, drift will reappear immediately.

Mitigation:

- plan `004` before broad parallel implementation
- use `004` as the reference point for work assignment

## Non-goals

- direct runtime implementation of memory, state, review, or yolo behavior in
  this feature
- replacing child subsystem specs with one giant umbrella artifact
- finalizing every child implementation detail before the child plans exist
