# Research: Orca Flow State

## Decision 1: Computed-first flow state

### Decision

Derive Orca flow state primarily from durable workflow artifacts, with thin
persisted metadata allowed only where resumability or cached guidance benefits.

### Rationale

- keeps artifacts as truth
- prevents early hidden-state drift
- matches the repomix lesson that visible state should sit on durable workflow
  evidence

### Alternatives Considered

- primary flow-state registry: easier reads, but too much hidden truth too soon
- statusline-first implementation: visible but built on weak foundations

## Decision 2: Review milestones must remain distinct

### Decision

Model review milestones separately from build/implementation progress.

### Rationale

- implementation is not equivalent to review completion
- later resume/orchestration needs both signals

### Alternatives Considered

- single progress state only: too coarse

## Decision 3: Use a canonical stage model broad enough for the full Orca workflow

### Decision

Define a stage model that includes pre-spec, implementation, and review stages,
not only implementation phases.

### Rationale

- flow state is foundational for later Orca systems
- a too-narrow stage model would be rewritten immediately

### Alternatives Considered

- implementation-only stage tracking: too limited
- full orchestration state machine now: too broad

## Decision 4: Worktree metadata is contextual evidence

### Decision

Allow worktree/lane metadata to enrich feature state, but do not let it replace
artifact truth.

### Rationale

- lane state describes execution topology, not the entire workflow lifecycle
- feature state must remain meaningful even without active worktrees

### Alternatives Considered

- lane-first state: too brittle and execution-specific

## Decision 5: Ambiguity is part of the contract

### Decision

Flow state should explicitly represent ambiguous or conflicting evidence rather
than forcing a single overconfident answer.

### Rationale

- improves trust
- creates safer future automation behavior

### Alternatives Considered

- always infer one best state: simpler UX, but misleading
