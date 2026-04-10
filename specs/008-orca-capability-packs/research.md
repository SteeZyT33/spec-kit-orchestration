# Research: Orca Capability Packs

## Decision 1: Use capability packs, not traits-as-implemented

### Decision

Create a lightweight Orca capability-pack model instead of copying Spex traits.

### Rationale

- repomix showed the value of optional behavior layering
- Orca still needs a simpler, more inspectable approach

### Alternatives Considered

- keep everything in core commands: leads to sprawl
- copy traits closely: too complex

## Decision 2: Core vs pack boundaries must be explicit

### Decision

The feature must define which behavior is always core and which behavior belongs
to optional packs.

### Rationale

- otherwise packs are just labels with no architectural value

### Alternatives Considered

- defer the boundary question: too vague and likely to drift

## Decision 3: Start model-first, activation-second

### Decision

Define the pack model and activation semantics before building more runtime
machinery.

### Rationale

- avoids another opaque system
- keeps the feature aligned with Orca's simple runtime philosophy

### Alternatives Considered

- runtime-first activation: overbuild risk

### Outcome In This Feature

The first runtime surface stays intentionally small:

- built-in pack registry in Python
- repo-local JSON override manifest
- list/show/validate/scaffold inspection commands

This makes activation inspectable without building a trait engine.

## Decision 4: Initial packs should map to Orca subsystem boundaries

### Decision

Use the existing subsystem set as the initial pack candidate set:

- brainstorm-memory
- flow-state
- worktrees
- review
- yolo

### Rationale

- matches the upgrade program
- grounds the model in real Orca boundaries
