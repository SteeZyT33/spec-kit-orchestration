# Quickstart: Orca Flow State

## Goal

Validate that Orca can compute feature workflow state from durable artifacts and
report progress, review milestones, ambiguity, and next-step guidance.

## Setup

1. Work on branch `005-orca-flow-state`.
2. Use representative feature directories with partial and conflicting artifact
   sets. The feature includes fixture states under `specs/005-orca-flow-state/fixtures/repo/specs/`.
3. Ensure any helper code passes `uv run python -m py_compile`.

## Scenario 1: Early-stage feature

1. Use a feature with `spec.md` and `plan.md` but no `tasks.md`.
   Example: `specs/005-orca-flow-state/fixtures/repo/specs/101-early-stage`
2. Compute flow state.
   ```bash
   uv run python -m speckit_orca.flow_state \
     specs/005-orca-flow-state/fixtures/repo/specs/101-early-stage \
     --repo-root specs/005-orca-flow-state/fixtures/repo \
     --format text
   ```
3. Verify:
   - current stage reflects planning completion
   - tasks are incomplete
   - next-step hint points toward task generation

## Scenario 2: Implementation ahead of review

1. Use a feature with implementation evidence but incomplete review artifacts.
   Example: `specs/005-orca-flow-state/fixtures/repo/specs/102-implementation-ahead`
2. Compute flow state.
   ```bash
   uv run python -m speckit_orca.flow_state \
     specs/005-orca-flow-state/fixtures/repo/specs/102-implementation-ahead \
     --repo-root specs/005-orca-flow-state/fixtures/repo \
     --format text
   ```
3. Verify:
   - implementation progress is visible
   - missing review milestones remain visible
   - next-step guidance points toward code review rather than back to assignment

## Scenario 3: Partial or conflicting evidence

1. Remove one expected artifact or create conflicting evidence.
   Example: `specs/005-orca-flow-state/fixtures/repo/specs/103-ambiguous`
2. Compute flow state.
   ```bash
   uv run python -m speckit_orca.flow_state \
     specs/005-orca-flow-state/fixtures/repo/specs/103-ambiguous \
     --repo-root specs/005-orca-flow-state/fixtures/repo \
     --format text
   ```
3. Verify:
   - ambiguity or incomplete state is reported explicitly
   - Orca does not invent false completion

## Scenario 4: Review-stage separation

1. Use a feature with spec/plan review evidence but no implementation.
   Example: `specs/005-orca-flow-state/fixtures/repo/specs/104-review-separated`
2. Compute flow state.
   ```bash
   uv run python -m speckit_orca.flow_state \
     specs/005-orca-flow-state/fixtures/repo/specs/104-review-separated \
     --repo-root specs/005-orca-flow-state/fixtures/repo \
     --format text
   ```
3. Verify:
   - review progress is visible independently
   - build progress is not overstated

## Scenario 5: Worktree-aware but artifact-first

1. Use a feature with worktree metadata present.
   Example: `specs/005-orca-flow-state/fixtures/repo/specs/105-worktree-aware`
2. Compute flow state.
   ```bash
   uv run python -m speckit_orca.flow_state \
     specs/005-orca-flow-state/fixtures/repo/specs/105-worktree-aware \
     --repo-root specs/005-orca-flow-state/fixtures/repo \
     --format text \
     --write-resume-metadata
   ```
3. Verify:
   - worktree context enriches the result
   - artifact truth still governs current stage and ambiguity handling
   - resume metadata is written under `.specify/orca/flow-state/` but remains secondary
