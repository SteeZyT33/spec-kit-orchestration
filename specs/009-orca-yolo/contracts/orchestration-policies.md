# Contract: Orchestration Policies

## Purpose

Define the minimum policy surface controlling how `orca-yolo` runs.

## Required Policies

- ask level or intervention mode
- start-from behavior
- resume behavior
- worktree behavior
- bounded retry behavior
- PR completion behavior
- supervision mode (`standalone` | `matriarch-supervised`)
- deployment kind (`standalone` | `direct-session` | `tmux`)

## Start Artifact Restrictions

- `orca-yolo` accepts full-spec feature directories and durable brainstorm
  records as run start anchors.
- **Spec-lite records** (`SL-NNN-*.md`) are excluded as start artifacts in v1.
  They are bounded work that does not justify a full yolo run.
- **Adoption records** (`AR-NNN-*.md`) are never valid start artifacts. They are
  reference-only per the `015-brownfield-adoption` contract and are not drivable
  by any runner or lane.
- Chat history or session transcripts are never valid start artifacts.

## Behavior

- Ask policy must control when `orca-yolo` pauses for human input.
- Start-from behavior must reject incompatible stage requests when prerequisites
  are missing.
- Start-from behavior must reject excluded artifact types (spec-lite, adoption
  records) with an explicit error message naming the restriction.
- Retry behavior must be bounded and must not create infinite fix loops.
- Retry bound is policy-shaped with a documented default of **2 attempts** per
  fix-loop stage before stopping with an explicit blocker.
- PR completion must remain an explicit policy choice rather than an implied
  side effect. The first-version default is `pr-ready` (stop at a PR-ready
  branch state); `pr-create` requires explicit opt-in.
- Supervision mode and deployment kind MUST be set explicitly at run start,
  not inferred from environment or CLI wiring.

## Supervised-Mode Behavior

When supervision mode is `matriarch-supervised`:

- Ask policy MUST route upward to matriarch via the Lane Mailbox rather than
  prompting the user directly. Pausing for clarification MUST emit an event
  using matriarch's shared event envelope (see
  `specs/010-orca-matriarch/contracts/event-envelope.md`) before the pause
  takes effect.
- Blockers, approval needs, and stop reasons MUST also be reported upward via
  the same mailbox contract so matriarch can distinguish a lane that is
  genuinely blocked from one that is merely idle.
- Resume behavior MUST consult matriarch's lane state before acting on
  local run state alone, so ownership or assignment changes recorded by
  matriarch are not silently overridden by a resuming yolo run.
- Deployment kind MUST match the deployment the lane is actually running
  under; a mismatch MUST surface as a blocker rather than be silently
  reconciled.
