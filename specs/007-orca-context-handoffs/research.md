# Research: Orca Context Handoffs

## Decision 1: Treat handoffs as first-class workflow contracts

### Decision

Define explicit handoff contracts between major workflow stages instead of
relying only on branch inference and prompt reconstruction.

### Rationale

- repomix highlighted explicit handoffs as a key missing layer
- later orchestration and fresh-session continuity need stable transition rules

### Alternatives Considered

- branch-only resolution: too weak
- prompt-only continuity: too inconsistent

## Decision 2: Keep handoffs lightweight and artifact-first

### Decision

Use lightweight durable handoff artifacts or sections rather than a large
centralized state system.

### Rationale

- easier to inspect
- aligned with Orca's simple runtime philosophy
- enough for stage continuity without overbuilding

### Alternatives Considered

- central handoff database: unnecessary complexity

## Decision 3: Integrate with memory, state, and review rather than replacing them

### Decision

`007` should consume outputs from `002`, `005`, and `006` and define stage
continuity on top of them.

### Rationale

- preserves subsystem boundaries from `004`
- avoids role confusion across child specs

### Alternatives Considered

- merge state/memory roles into handoffs: too broad

## Decision 4: Worktree/lane context is additive

### Decision

Handoffs should use branch/worktree/lane context when present, but must still
function without active lane metadata.

### Rationale

- keeps the feature widely usable
- aligns with degrade-safely behavior

### Alternatives Considered

- make lane metadata mandatory: too restrictive

## Decision 5: Use a thin deterministic helper once the contract is stable

### Decision

Implement handoff create/resolve behavior as a small Python helper instead of
leaving the feature as command prose only.

### Rationale

- deterministic parsing and tie-break behavior are hard to keep consistent in
  prompt-only command text
- Orca already uses small Python helpers for brainstorm memory and flow state
- this keeps the runtime inspectable while making the contract executable

### Alternatives Considered

- docs-only handoff behavior: too easy for implementations to drift
- larger centralized runtime: unnecessary for the first version
