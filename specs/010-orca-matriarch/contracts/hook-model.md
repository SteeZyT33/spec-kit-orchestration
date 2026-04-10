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
