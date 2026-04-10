# Review: 003 Cross-Review Agent Selection

**Date**: 2026-04-09  
**Branch**: `003-cross-review-agent-selection-impl`

## Code Review

### Final Findings

No remaining blocking implementation findings.

### Issue Found And Corrected During Review

1. **Persisted cross-review config was documented but not actually loaded**
   - Impact: `crossreview.agent`, legacy `crossreview.harness`, and config-level
     model/effort settings would not influence runtime selection unless the user
     manually exported environment variables.
   - Correction applied:
     - backend now loads `orchestration-config.yml` and
       `.specify/orchestration-config.yml` when present
     - backend also reads legacy review settings from
       `.specify/init-options.json`
     - launcher no longer hard-codes `effort=high` before the backend can apply
       config defaults

### Residual Risks

1. `cursor-agent` is intentionally Tier 2 and explicit-only, but on this
   machine it still falls into an interactive sign-in path. Orca now reports
   that honestly as a runtime failure, which is the correct current behavior.
2. Reviewer memory is advisory only via environment today. There is still no
   persisted reviewer-memory store, which is acceptable for this feature
   because the spec made memory optional.

## Cross-Review

### Adapter Verification

- `opencode`: explicit `--agent opencode` path succeeded and returned the new
  structured metadata shape.
- config-driven selection succeeded when `crossreview.agent: opencode` was set
  in `orchestration-config.yml`.
- unsupported selection (`copilot`) returned a structured unsupported-agent
  result.
- explicit `cursor-agent` selection returned a structured runtime blocker
  instead of a false-positive review result.
- auto-selection preferred a non-current Tier 1 agent over the active provider.

### External Adversarial Pass

An `opencode` full-diff adversarial review was attempted twice. The adapter
path itself is healthy, but the long-form review invocation did not return a
bounded final verdict in the available time, so no substantive external
findings are recorded here.

## Verification

- `bash -n scripts/bash/crossreview.sh`
- `uv run python -m py_compile scripts/bash/crossreview-backend.py`
- explicit `--agent opencode` smoke run
- config-backed `crossreview.agent: opencode` smoke run
- explicit unsupported-agent result (`copilot`)
- explicit Tier 2 runtime-failure result (`cursor-agent`)

## Verdict

Feature `003` is implementation-complete and behaviorally aligned with the
spec after the config-loading fix applied during review.
