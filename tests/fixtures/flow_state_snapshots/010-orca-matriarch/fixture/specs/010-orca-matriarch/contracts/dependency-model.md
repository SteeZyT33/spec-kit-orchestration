# Contract: Dependency Model

## Purpose

Define how Matriarch represents lane-to-lane blockers without relying on
numbering conventions or prose guesses.

## Required Dependency Targets

- `lane_exists`
- `stage_reached`
- `review_ready`
- `pr_ready`
- `merged`

## Required Strengths

- `soft`
- `hard`

## Rules

- hard dependencies block forward lifecycle transitions until satisfied or
  explicitly waived
- soft dependencies surface warnings and operator guidance but do not
  automatically block all movement
- every waived dependency must record rationale
- dependency evaluation must remain readable from durable metadata alone

## Target Values

- `lane_exists`: no `target_value`
- `stage_reached`: `brainstorm` | `specify` | `plan` | `tasks` | `assign` |
  `implement` | `code-review` | `cross-review` | `pr-review` | `self-review`
- `review_ready`: no `target_value`
- `pr_ready`: no `target_value`
- `merged`: no `target_value`

## Examples

- lane `010` hard-depends on lane `009` reaching `review_ready`
- lane `011` soft-depends on lane `010` existing as a stable destination
- lane `007` hard-depends on lane `006` being merged
