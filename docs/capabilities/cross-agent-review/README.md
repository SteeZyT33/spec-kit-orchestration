# cross-agent-review

Bundles a review subject (spec, diff, pr, or claim-output), dispatches to one or more reviewer backends (claude, codex, or cross), and returns structured findings with stable dedupe IDs.

## Status: Findings, Not Proof

This capability produces **findings and hypotheses**, not formal proof. Reviewer output reflects model judgment at a point in time and is sensitive to prompt, model version, and reasoning effort. Hosts decide how findings affect downstream actions (block, warn, ignore). Do not treat a clean cross-review as a guarantee of correctness.

## Input
See `schema/input.json`.

## Output
See `schema/output.json`. Findings have stable 16-char `id` derived from `category`, `severity`, normalized `summary`, and sorted `evidence`. Identical findings from multiple reviewers merge by `id` with combined `reviewers[]`.

In cross mode, `missing_reviewers` lists ALL reviewers whose calls failed (sorted); the surviving reviewers' findings still return with `partial: true`. If every reviewer fails, the capability returns `Err(Error(kind=BACKEND_FAILURE))` rather than an Ok envelope with empty findings.

## CLI
`orca-cli cross-agent-review --kind diff --target src/foo.py --reviewer cross --feature-id 001-foo`

## Library
`from orca.capabilities.cross_agent_review import cross_agent_review, CrossAgentReviewInput`
