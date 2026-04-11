# Contract: Implementation Waves

## Dependency-Driven Waves

| Wave | Specs | Purpose | Current State |
|---|---|---|---|
| Wave 1 | `001`, `002`, `003`, `005`, `006`, `007`, `008` | Workflow foundations: memory, review architecture, state, handoffs, and composition | merged |
| Wave 2 | `009` | Full-cycle single-lane orchestration | planned |
| Wave 3 | `010` | Multi-lane supervision over durable workflow evidence | merged |
| Wave 4 | `011` | Self-evolution and adoption tracking | merged |

## Merge Chronology Note

The repo's merge chronology is not identical to the dependency-driven wave
order.

- `010-orca-matriarch` merged before `009-orca-yolo`
- `011-orca-evolve` also merged before `009-orca-yolo`

That is acceptable because `010` was intentionally designed to supervise manual
and direct-session lanes without requiring `009`, and `011` depends on stable
destination specs and runtime surfaces rather than on `009` being present.

## Program Checkpoints

### Checkpoint A: Foundation Ready

Before Wave 2 is considered stable:

- cross-review agent selection is trustworthy
- brainstorm memory is durable
- flow state can express current feature stage
- review artifacts, context handoffs, and capability packs are merged enough to
  act as stable workflow primitives

Current status: met

### Checkpoint B: Orchestration Ready

Before `009-orca-yolo` starts implementation:

- review artifacts are explicit and durable
- context handoffs are explicit
- lower-layer workflow primitives no longer depend on active chat memory
- capability activation can be inspected without command-prose guesswork

Current status: met

### Checkpoint C: Supervision Ready

Before `010-orca-matriarch` is considered stable:

- `009-orca-yolo` is mature enough to act as an optional single-lane worker
- lane-level flow and review state can be consumed without chat reconstruction
- the system can distinguish coordination from execution responsibility

Current status: partial

Note: `010` is already merged, but its optional `009` worker relationship is
still incomplete because `009` remains pending. This is an allowed partial
state, not a contradiction in the program design.

### Checkpoint D: Evolution Ready

Before `011-orca-evolve` is considered stable:

- the current workflow-system upgrade is explicit enough to map new adoption
  candidates into concrete Orca destinations
- harvest/adoption records can point at durable specs, roadmap entries, or
  future feature slots

Current status: met
