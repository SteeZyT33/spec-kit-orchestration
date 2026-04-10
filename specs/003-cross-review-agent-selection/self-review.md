# Process Self-Review: 003 Cross-Review Agent Selection

**Date**: 2026-04-09  
**Feature**: `003-cross-review-agent-selection-impl`

## Scores

| Dimension | Score | Key Evidence |
|---|---:|---|
| Spec Fidelity | 4/5 | Runtime now supports canonical `--agent`, legacy `--harness`, support tiers, `opencode`, structured metadata, and adjacent doc consistency. |
| Plan Accuracy | 4/5 | The adapter-registry direction held. The main miss was that config migration had been documented more completely than it was initially wired. |
| Task Decomposition | 4/5 | Runtime-first then docs/schema was the right order. Verification exposed the missing config loader before closeout. |
| Review Effectiveness | 4/5 | Manual review caught a real config gap and it was fixed immediately. External `opencode` smoke checks were useful, but the full-diff adversarial pass did not finish cleanly. |
| Workflow Friction | 3/5 | Separate worktree/branch discipline worked well. The main friction was that the implementation branch did not initially contain the `003` feature artifacts, which made the review phase more awkward than it needed to be. |

## What Worked

- Creating a dedicated implementation worktree prevented interference with the
  dirty planning branch.
- Runtime verification against real installed CLIs produced better signal than
  spec-only reasoning.
- Treating unsupported and runtime-failure paths as first-class outputs kept
  the feature honest.

## What Didn’t

- The first implementation pass normalized config and docs before actually
  loading persisted config at runtime.
- The implementation branch started from committed `HEAD`, so the `003` spec
  files had to be copied into the worktree during review instead of already
  being present.
- The long-form `opencode` adversarial pass was too unconstrained at first and
  did not produce a bounded result.

## Process Improvements

1. When implementing from a clean worktree against uncommitted feature specs,
   bring the feature spec directory into the worktree at the start rather than
   only during review.
2. For cross-review validation, use attached-file prompts and explicit
   “do not explore” constraints from the start when the goal is a bounded
   adversarial pass rather than open-ended analysis.
3. Treat “documented config migration” as incomplete until a real config loader
   or parser path is verified.

## Extension Improvements

1. `cross-review` should eventually persist reviewer-memory instead of relying
   only on environment-driven advisory state.
2. `cross-review` could benefit from a small, repo-local review prompt template
   for backend smoke checks so adapter verification is more repeatable.

## Deferred Improvements

1. `ask_on_ambiguous` is documented in config, but the current backend remains
   deterministic and non-interactive. If Orca later wants true ambiguity
   escalation, it needs a workflow-level prompt/ask mechanism rather than a
   backend-only branch.
