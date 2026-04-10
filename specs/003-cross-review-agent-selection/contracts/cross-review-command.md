# Contract: `/speckit.orca.cross-review`

## Purpose

Define the user-visible reviewer-selection contract for Orca cross-review.

## Inputs

- `--agent <name>`: canonical reviewer-selection input
- `--harness <name>`: legacy compatibility input
- `--scope design|code`
- `--phase N`
- optional free-form review focus text

## Resolution Order

Orca resolves the reviewer in this order:

1. explicit `--agent` (if provided)
2. legacy `--harness` (if provided)
3. configured `crossreview.agent`
4. legacy configured `crossreview.harness`
5. most recent successful reviewer, if enabled and still valid
6. highest-ranked installed Tier 1 non-current reviewer
7. deterministic same-agent fallback with a warning when no better Tier 1 option exists

## Required Output

Cross-review output must include a top-level `metadata` envelope containing:

- `requested_agent`
- `resolved_agent`
- `active_agent`
- `model`
- `effort`
- `selection_reason`
- `support_tier`
- `status`
- `substantive_review`
- `used_legacy_input`
- `is_cross_agent`
- `same_agent_fallback`

## Required Failure Behavior

- known but unsupported agents must return structured unsupported-agent output
- missing adapters must not be reported as successful review
- runtime invocation failures must be surfaced as operational blockers

## Compatibility

- `--harness` remains accepted for a compatibility window
- `agent` is the canonical term in docs and output
