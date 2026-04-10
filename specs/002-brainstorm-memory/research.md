# Research: Orca Brainstorm Memory

## Decision 1: Use `brainstorm/` as the durable project-local memory root

### Decision

Store durable brainstorm memory in a project-local `brainstorm/` directory with
numbered records and a generated `00-overview.md`.

### Rationale

- This is the most reusable piece from Spex and the cleanest provider-agnostic
  storage model.
- It makes brainstorm artifacts discoverable without depending on chat/session
  state.
- It gives later Orca stages a canonical path convention.

### Alternatives Considered

- `.specify/orca/inbox/` only: useful for transient inbox artifacts, but weak as
  durable project memory.
- `specs/<feature>/brainstorm.md` only: helpful for active feature refinement,
  but insufficient for pre-spec idea capture and cross-feature memory.

## Decision 2: Add a deterministic helper instead of relying only on prompt text

### Decision

Use a small Python helper module for deterministic filesystem behavior:
numbering, slug normalization, lightweight overlap matching, metadata parsing,
and overview regeneration.

### Rationale

- These operations are easier to test and reason about in Python stdlib than in
  shell snippets or command prose.
- The command remains the UX surface; the helper just makes file behavior
  stable.
- This aligns with the constitution's preference for small, composable runtime
  surfaces.

### Alternatives Considered

- Prompt-only behavior: lower code cost, but too inconsistent across providers.
- Bash-only helper: possible, but parsing and regeneration will be more brittle.

## Decision 3: Rebuild the overview from records every time

### Decision

Treat `brainstorm/00-overview.md` as a generated file rebuilt from current
brainstorm records whenever Orca writes or updates memory.

### Rationale

- Idempotent regeneration is simpler than incremental patching.
- It keeps the overview auditable and reduces drift risk.
- Missing overview files can be recovered cleanly from records.

### Alternatives Considered

- Incremental overview mutation only: smaller writes but far more drift-prone.

## Decision 4: Preserve record history on revisit

### Decision

When a user updates an existing brainstorm, preserve prior context and append a
new dated update section or equivalent additive content rather than rewriting
the whole file.

### Rationale

- Manual edits must not be destroyed.
- Brainstorm memory should act as a durable idea history.
- Future review or workflow tools may need the evolution trail.

### Alternatives Considered

- Replace the entire file on each revisit: simpler implementation, but violates
  trust and preservation requirements.

## Decision 5: Use lightweight overlap heuristics in v1

### Decision

Detect likely related brainstorms using normalized title/slug overlap and simple
keyword matching against existing record metadata.

### Rationale

- Good enough for the first version.
- Fast, explainable, and provider-neutral.
- Keeps the helper simple.

### Alternatives Considered

- Embeddings or semantic search: too heavy and out of scope.
- No overlap detection: would make memory fragmentation worse immediately.

## Decision 6: Keep downstream linking narrow in this feature

### Decision

Support a forward link from brainstorm record to spec path or feature identity,
but defer reverse links and deeper flow-state integration.

### Rationale

- Satisfies the workflow-bridge requirement without overloading this feature.
- Keeps the contract narrow and lets later specs build on it.

### Alternatives Considered

- Full bidirectional linking with flow-state now: valuable, but too broad for
  the first memory feature.
