# completion-gate

Decides whether an SDD-managed feature has cleared gates for a target stage. Pure Python, no LLM.

## Stages

- `plan-ready` — `spec.md` exists and has no `[NEEDS CLARIFICATION]` markers.
- `implement-ready` — `plan-ready` gates + `plan.md` exists.
- `pr-ready` — `implement-ready` gates + `tasks.md` exists.
- `merge-ready` — `pr-ready` gates + `evidence.ci_green=true`.

## Status

- `pass` — all gates for the target stage are green AND no stale artifacts in evidence.
- `blocked` — at least one gate failed; `blockers[]` lists gate names.
- `stale` — `evidence.stale_artifacts[]` is non-empty (takes precedence over `blocked`). Used by hosts with revision tracking (perf-lab integration shim) to surface "prior review went stale because the artifact changed." V1 trusts the caller to populate this; orca itself does not compute staleness.

  An empty `evidence.stale_artifacts: []` is equivalent to omitting the key — neither produces a `stale` status.

## Input

See `schema/input.json`. `evidence.ci_green` and `evidence.stale_artifacts[]` are the documented fields; other evidence keys pass through but aren't read by gates today.

## Output

See `schema/output.json`. `gates_evaluated[]` reports each gate's outcome regardless of overall status — useful for diagnostics. `blockers[]` is the subset of gate names that failed. `stale_artifacts[]` mirrors the evidence input.

## Errors

- `INPUT_INVALID`: `target_stage` not in the enum, or `feature_dir` does not exist.

## CLI

`orca-cli completion-gate --feature-dir specs/001-foo --target-stage plan-ready`

With evidence:
`orca-cli completion-gate --feature-dir specs/001 --target-stage merge-ready --evidence-json '{"ci_green": true}'`
