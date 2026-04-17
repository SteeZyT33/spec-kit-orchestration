# Contract: Hook Model

## Purpose

Define how Matriarch exposes transparent lane lifecycle hooks.

## Supported V1 Event Classes

- lane-created
- lane-assigned
- worktree-attached
- checkout-resolved
- lane-blocked
- review-ready
- pr-ready
- lane-archived

## Requirements

- hook execution must be explicit and inspectable
- each hook event must be logged with result
- hooks must not silently mutate unrelated lanes
- hook failure must be surfaced without corrupting lane registry state

## Registration And Safety Rules

- hook registration must be file-backed and visible to the operator
- hook payload must include lane id, lifecycle state, and relevant checkout or
  deployment context
- hooks may emit guidance, refresh metadata, or trigger explicit helper flows,
  but must not silently rewrite unrelated lane records
- a failed hook may block a transition only when the hook is marked mandatory

## Registration Format

V1 should use a file-backed registration document under an Orca-owned path such
as:

- `.specify/orca/matriarch/hooks.yml`

Each hook registration should define:

- `event`
- `name`
- `command`
- `optional`
- `enabled`

The registration format should stay simple and inspectable. Hidden or dynamic
hook discovery is out of scope for v1.

## Tmux-Related Events

- deployment-requested
- deployment-started
- deployment-attached
- deployment-missing
- deployment-stopped
