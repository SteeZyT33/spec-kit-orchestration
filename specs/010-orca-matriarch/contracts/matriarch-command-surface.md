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
- lane deployment inspection

## V1 Expectations

- commands must be explicit and inspectable
- destructive git/worktree mutation must require explicit invocation
- checkout must resolve-and-print by default
- `checkout --exec` may execute a narrow, explicit switch/attach action, but it
  must not mutate the parent shell environment invisibly
- status surfaces must distinguish derived state from declared metadata
- missing evidence must be reported as missing, not guessed

## Narrow V1 Surface

The preferred v1 command family should stay small:

- `matriarch status`
- `matriarch lane list`
- `matriarch lane show <lane>`
- `matriarch lane register <spec-or-lane>`
- `matriarch lane assign <lane> ...`
- `matriarch lane depend <lane> ...`
- `matriarch lane checkout <lane> [--exec]`
- `matriarch lane worktree <lane> ...`
- `matriarch lane deploy <lane> ...`

Anything broader should be deferred until lifecycle, dependency, and registry
behavior are proven stable.

## Authority Rules

- Matriarch is the supervisory authority for launched lane agents
- a lane-local execution session should be modeled as subordinate to one lane,
  not as a peer coordinator
- lane agents should report blockers and questions upward instead of treating
  the user as the default first-hop authority once launched

## Checkout Output Rules

- default checkout output should tell the operator exactly where to go and why
- when execution is requested explicitly, the command should perform only the
  narrow attach/switch action it reports beforehand
- checkout must distinguish repo path resolution, git branch switching, and
  tmux session attachment rather than collapsing them into one opaque action
