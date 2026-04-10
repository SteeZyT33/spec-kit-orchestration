# Contract: Subsystem Integration

## Purpose

Define what the major subsystem specs provide to one another.

## Initial Integration Contracts

### `001` Worktree Runtime -> `005` Flow State

- provides worktree lane metadata and lane lifecycle context as secondary
  workflow evidence
- `005` may incorporate worktree metadata as contextual input, but must still
  prefer durable workflow artifacts as primary truth

### `001` Worktree Runtime -> `007` Context Handoffs

- provides worktree-aware execution boundaries and lane identity
- `007` may assume worktree metadata exists when worktree-based execution is in
  use, but must degrade safely when a feature is being worked from the primary
  repository checkout

### `002` Brainstorm Memory -> `005` Flow State

- provides durable ideation artifacts
- provides forward links into later feature/spec identity
- `005` may assume brainstorm memory is durable, but not that every feature has
  a brainstorm record yet

### `002` Brainstorm Memory -> `007` Context Handoffs

- provides upstream context artifacts for later stages
- `007` may assume brainstorm records are readable and structured

### `003` Cross-Review Agent Selection -> `006` Review Artifacts

- provides trustworthy reviewer resolution and reporting fields
- `006` may assume requested/resolved reviewer metadata exists once `003` is
  implemented

### `005` Flow State <-> `006` Review Artifacts

- `006` provides the durable review-stage evidence shape that `005` consumes
  when computing review milestones and next-step guidance
- `005` defines the workflow-stage model that interprets `006` review evidence
  as progress rather than isolated notes
- `005` must not treat `review.md` alone as sufficient proof of review-stage
  completion when `006` defines stage artifacts as primary evidence
- `006` must preserve machine-usable stage boundaries so `005` can distinguish
  code review, cross-review, PR review, and self-review without reparsing
  ambiguous prose

### `003` Cross-Review Agent Selection + `006` Review Artifacts

- together they form Orca's review architecture boundary for alternate-agent
  review
- `003` determines who performed cross-review and why
- `006` determines where that evidence lives and how later systems discover it

### `005` Flow State -> `009` Yolo

- provides current-stage and next-step understanding
- `009` may assume flow state exists before attempting resume semantics

### `006` Review Artifacts -> `009` Yolo

- provides durable review-stage evidence
- `009` may assume review completion can be discovered from artifacts, not chat
  memory

### `007` Context Handoffs -> `009` Yolo

- provides stage-to-stage continuity rules
- `009` may assume explicit handoffs exist instead of inventing transition logic

### `008` Capability Packs -> future optional subsystems

- provides a composition model for optional behavior
- provides a deterministic registry and activation-inspection surface
- downstream features may assume optional capability boundaries exist, but core
  workflow behavior must still function without pack sprawl

### `009` Yolo -> `010` Matriarch

- provides a possible single-lane execution worker/runtime
- `010` may supervise or invoke `009`, but must still deliver coordination
  value when lanes are managed manually or semi-manually

### `005` Flow State + `006` Review Artifacts + `007` Context Handoffs -> `010` Matriarch

- together they provide the lane-state substrate Matriarch consumes
- `010` must derive lane stage, blockers, and readiness from durable workflow
  evidence rather than chat memory

### `004` Upgrade Program + existing harvest docs -> `011` Evolve

- provide the current Orca roadmap and adoption targets
- `011` uses them as destination anchors for new harvest entries and adoption
  decisions

### `011` Evolve -> future Orca upgrades

- provides a durable intake and decision system for external patterns
- future specs may assume harvested ideas can be traced to prior source and
  adoption rationale instead of being rediscovered ad hoc
