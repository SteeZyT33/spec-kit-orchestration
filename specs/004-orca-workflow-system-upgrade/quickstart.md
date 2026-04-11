# Quickstart: Orca Workflow System Upgrade

## Goal

Validate that the application upgrade program is coherent enough to guide later
parallel implementation and accurately describe the current merged workflow
system.

## Scenario 1: Child inventory exists

1. Inspect the upgrade program artifacts.
2. Verify every major subsystem from the repomix harvest exists as a child spec.
3. Verify `010-orca-matriarch` and `011-orca-evolve` are represented as child
   specs instead of living outside the umbrella program.

## Scenario 2: Wave order is dependency-driven

1. Inspect the implementation waves contract.
2. Verify wave sequencing follows actual prerequisites rather than spec number.
3. Verify the contract also explains where the actual merge chronology diverges
   from the ideal wave order.

## Scenario 3: `orca-yolo` is downstream

1. Inspect the upgrade checkpoints and `009` role.
2. Verify `orca-yolo` is gated behind memory, state, review, and handoff
   readiness.
3. Verify the documents still allow `010-orca-matriarch` to provide value
   without claiming that `009` is already merged.

## Scenario 4: Parallel implementation is safe

1. Compare child specs against the subsystem integration contract.
2. Verify the child specs can be assigned in parallel without hidden subsystem
   assumptions.

## Scenario 5: Repo-facing docs agree with `004`

1. Inspect `README.md`, `docs/orca-harvest-matrix.md`, and `docs/orca-roadmap.md`.
2. Verify they describe one workflow-system story instead of competing roadmap
   fragments.
