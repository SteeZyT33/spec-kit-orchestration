# completion-gate

Decides whether an SDD-managed feature has cleared gates for a target stage. Pure Python, no LLM.

## Stages

- `plan-ready`: `spec.md` exists and has no `[NEEDS CLARIFICATION]` markers.
- `implement-ready`: `plan-ready` gates + `plan.md` exists.
- `pr-ready`: `implement-ready` gates + `tasks.md` exists.
- `merge-ready`: `pr-ready` gates + `evidence.ci_green=true`.

## Status

- `pass`: all gates for the target stage are green AND no stale artifacts in evidence.
- `blocked`: at least one gate failed; `blockers[]` lists gate names.
- `stale`: `evidence.stale_artifacts[]` is non-empty (takes precedence over `blocked`). Used by hosts with revision tracking (perf-lab integration shim) to surface "prior review went stale because the artifact changed." V1 trusts the caller to populate this; orca itself does not compute staleness.

  An empty `evidence.stale_artifacts: []` is equivalent to omitting the key; neither produces a `stale` status.

## Input

See `schema/input.json`. `evidence.ci_green` and `evidence.stale_artifacts[]` are the documented fields; other evidence keys pass through but aren't read by gates today.

## Output

See `schema/output.json`. `gates_evaluated[]` reports each gate's outcome regardless of overall status - useful for diagnostics. `blockers[]` is the subset of gate names that failed. `stale_artifacts[]` mirrors the evidence input.

## Errors

- `INPUT_INVALID`: `target_stage` not in the enum, or `feature_dir` does not exist.

## CLI

`orca-cli completion-gate --feature-dir specs/001-foo --target-stage plan-ready`

With evidence:
`orca-cli completion-gate --feature-dir specs/001 --target-stage merge-ready --evidence-json '{"ci_green": true}'`

## Design Notes

### Why `plan-ready` only checks 2 gates

`plan-ready` deliberately checks only `spec_exists` + `no_unclarified`. The minimal precondition for `/plan` is a spec.md that the planner can read without ambiguity blockers. Other tempting gates were considered and rejected:

- **`acceptance_criteria_present`**: spec-kit specs use varied conventions (Acceptance Criteria, Success Criteria, embedded in user stories, in plan.md). A rigid heading check is too brittle and produces false-blocks; LLM-aware acceptance-criteria detection is out of v1 rule-based scope.
- **`clarifications_resolved`**: identical in semantics to `no_unclarified`. Already covered.
- **`user_story_present`**: sometimes lives in plan.md, not spec.md; would mis-block specs that defer story breakdown to `/plan`.

Operators who want stricter pre-`/plan` gating can run `/orca:review-spec` before invoking `/plan`; that capability is the right surface for cross-spec consistency, feasibility, and security review (which is what acceptance-criteria checking effectively reduces to).

### Reviewer-backend assumptions

Per `plugins/codex/AGENTS.md` "Live Backend Prerequisites" block: `cross-agent-review` (used by `review-spec`/`review-code`/`review-pr`) calls `api.anthropic.com` for the claude reviewer when `ORCA_LIVE=1` is set. This is API-Claude, not the in-session Claude that may be running the host slash command. The slash-command Round 3 of phase 3 review-code documents this trade-off; an `in-session` reviewer mode that delegates to the host harness is tracked in the Phase 3.2 backlog (item 9) but defers to a future host-orchestration design.
