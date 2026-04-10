# Contract: Canonical Stage Model

## Canonical Stages

The first Orca flow-state stage model should include:

1. `brainstorm`
2. `specify`
3. `plan`
4. `tasks`
5. `assign`
6. `implement`
7. `code-review`
8. `cross-review`
9. `pr-review`
10. `self-review`

## Interpretation Rules

- Stages represent recommended workflow order.
- Completion of a later stage does not automatically erase ambiguity about an
  earlier missing stage.
- Review stages may be represented both as stages and as review milestones,
  depending on the consumer's need.
- `assign` is optional workflow coordination state. Missing assignment evidence
  does not block `implement` once real implementation evidence exists.
- `brainstorm` may remain incomplete when a feature starts directly at
  specification.

## Non-goal

This contract does not define a full orchestration state machine. It defines
the shared workflow vocabulary.
