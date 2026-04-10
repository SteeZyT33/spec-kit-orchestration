# Contract: Matriarch Command Surface

## Purpose

Define the minimal supervisory interface for `orca-matriarch`.

## Required Surfaces

- one top-level status/overview entrypoint
- lane listing
- lane detail inspection
- lane creation/registration
- lane assignment
- lane dependency management
- lane checkout target resolution
- lane worktree attachment/recording

## V1 Expectations

- commands must be explicit and inspectable
- destructive git/worktree mutation must require explicit invocation
- status surfaces must distinguish derived state from declared metadata
- missing evidence must be reported as missing, not guessed
