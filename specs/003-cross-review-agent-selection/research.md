# Research: Orca Cross-Review Agent Selection

## Decision 1: Canonicalize on `agent`

### Decision

Use `agent` as the canonical term for reviewer selection in CLI, config, docs,
and review artifacts. Keep `harness` only as a compatibility alias.

### Rationale

- Orca already knows a broader set of agents than the original three review
  runners.
- `agent` better reflects provider-agnostic orchestration.
- It aligns review tooling with the broader repomix finding that optional
  workflow capabilities should be explicit and composable.

### Alternatives Considered

- Keep `harness` forever: simpler short-term, but cements the current mismatch.
- Hard rename with no compatibility: cleaner but unnecessarily disruptive.

## Decision 2: Add `opencode` now, design for more

### Decision

Implement `opencode` as a first-class adapter in the normal cross-review
runtime, and design the backend so future agents such as `cursor-agent` can be
added via adapter registration instead of special-case rewrites.

### Rationale

- `opencode` is already installed and manually usable here.
- It proves the broader selection model with a real new adapter.
- It keeps the feature grounded in actual runtime value.

### Alternatives Considered

- Delay `opencode` until every agent is ready: not necessary.
- Add many unverified agents at once: too much false support risk.

## Decision 3: Use explicit support tiers

### Decision

Model cross-review support in tiers:

- Tier 1: verified and auto-selectable
- Tier 2: selectable or best-effort, but not auto-selected
- Tier 3: known but unsupported

### Rationale

- Orca's installer-known list is broader than the runtime support surface.
- Users need an honest support contract.
- Auto-selection must prefer trustable adapters.

### Alternatives Considered

- Treat all known agents as equal: misleading.
- Hide unsupported agents completely: removes useful future-facing clarity.

## Decision 4: Keep reviewer memory advisory

### Decision

If Orca remembers the most recent successful reviewer, use that only as an
advisory input behind explicit CLI input and config.

### Rationale

- stale memory should not override present intent
- this gives useful continuity without opaque stickiness

### Alternatives Considered

- no memory: simpler, but lower ergonomics
- hard preference for previous reviewer: too opaque and brittle

## Decision 5: Review artifacts must record requested and resolved reviewer separately

### Decision

Cross-review artifacts must capture:

- requested agent
- resolved agent
- selection reason
- support tier
- whether the run was truly cross-agent

### Rationale

- this is necessary to explain same-agent fallback honestly
- it makes retrospective review of reviewer choice possible
- it prevents silent resolution drift

### Alternatives Considered

- record only the final runner: insufficient for understanding why Orca chose it
