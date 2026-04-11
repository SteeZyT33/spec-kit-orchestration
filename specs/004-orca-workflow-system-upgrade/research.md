# Research: Orca Workflow System Upgrade

## Decision 1: Use an umbrella program spec

### Decision

Represent the whole application upgrade through one umbrella program spec plus
child subsystem specs.

### Rationale

- captures the repomix harvest as a system, not a chat note
- keeps subsystem implementation modular
- supports later parallel-agent execution

### Alternatives Considered

- roadmap only: too weak
- one giant monolithic spec: too rigid and not parallel-friendly

## Decision 2: Sequence by dependency, not by number

### Decision

Define upgrade waves by actual prerequisites:

- Wave 1: `001`, `002`, `003`, `005`, `006`, `007`, `008`
- Wave 2: `009`
- Wave 3: `010`
- Wave 4: `011`

### Rationale

- review infrastructure helps all later work
- memory and state are prerequisites for orchestration
- yolo should remain downstream
- evolve should arrive only after there are stable Orca destinations to map

### Alternatives Considered

- numeric order only: simpler but architecturally weaker

## Decision 3: Program-level contracts are necessary

### Decision

The umbrella feature should define integration contracts between child specs,
not just list them.

### Rationale

- parallel implementation needs explicit subsystem expectations
- prevents hidden assumptions across child features

### Alternatives Considered

- let child specs coordinate ad hoc: too much drift risk

## Decision 4: `orca-yolo` must remain a checkpointed downstream layer

### Decision

`009-orca-yolo` should only advance after memory, state, review artifacts, and
context handoffs reach defined readiness.

### Rationale

- avoids building orchestration on weak primitives
- aligns with the repomix lesson that `ship` is not the foundation

### Alternatives Considered

- start yolo early: attractive, but structurally wrong

## Decision 5: Describe the current merged state explicitly

### Decision

`004` should record that the repo already includes `010-orca-matriarch` and
`011-orca-evolve` even though the ideal dependency order still leaves
`009-orca-yolo` as the major downstream subsystem.

### Rationale

- maintainers need a truthful picture of what is shipped
- `010` was designed to work without `009` by supervising manual and
  direct-session lanes
- `011` depends on stable destination specs and runtime surfaces, not on `009`
  being merged first

### Alternatives Considered

- pretend merge order and dependency order are identical: inaccurate and
  confusing
