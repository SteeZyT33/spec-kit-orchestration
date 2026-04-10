# Contract: Implementation Waves

## Wave 1: Foundations

- `003-cross-review-agent-selection`
- `002-brainstorm-memory`
- `005-orca-flow-state`

## Wave 2: Integration Quality

- `006-orca-review-artifacts`
- `007-orca-context-handoffs`

## Wave 3: Composition And Orchestration

- `008-orca-capability-packs`
- `009-orca-yolo`

## Wave 4: Program Supervision And Self-Evolution

- `010-orca-matriarch`
- `011-orca-evolve`

## Program Checkpoints

### Checkpoint A: Foundation Ready

Before Wave 2 is considered stable:

- cross-review agent selection is trustworthy
- brainstorm memory is durable
- flow state can express current feature stage

### Checkpoint B: Orchestration Ready

Before `009-orca-yolo` starts implementation:

- review artifacts are explicit and durable
- context handoffs are explicit
- lower-layer workflow primitives no longer depend on active chat memory

### Checkpoint C: Supervision Ready

Before `010-orca-matriarch` is considered stable:

- `009-orca-yolo` is mature enough to act as an optional single-lane worker
- lane-level flow and review state can be consumed without chat reconstruction
- the system can distinguish coordination from execution responsibility

### Checkpoint D: Evolution Ready

Before `011-orca-evolve` is considered stable:

- the current workflow-system upgrade is explicit enough to map new adoption
  candidates into concrete Orca destinations
- harvest/adoption records can point at durable specs, roadmap entries, or
  future feature slots
