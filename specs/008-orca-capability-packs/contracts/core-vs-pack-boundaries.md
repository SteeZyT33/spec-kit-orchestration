# Contract: Core Vs Pack Boundaries

## Purpose

Define what belongs in core Orca behavior versus optional capability packs.

## Rules

- Core workflow behavior must remain understandable without reading multiple
  pack definitions first.
- Packs should capture optional or cross-cutting behavior that would otherwise
  sprawl across commands.
- Downstream orchestration behaviors such as `yolo` must not be treated as
  foundational core behavior.

## Initial Candidate Packs

- `brainstorm-memory`
- `flow-state`
- `worktrees`
- `review`
- `yolo`

## Initial Classification

- `brainstorm-memory`: optional, config-enabled
- `flow-state`: optional, config-enabled
- `worktrees`: optional, config-enabled
- `review`: core, always-on
- `yolo`: downstream, experimental-only
