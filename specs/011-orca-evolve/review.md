# Cross Review: Orca Evolve

## Review Artifacts

| Stage | Artifact | Status | Notes |
|---|---|---|---|
| Code Review | [review-code.md](./review-code.md) | PRESENT | Local implementation review found no blocking issues. |
| Cross-Review | [review-cross.md](./review-cross.md) | PRESENT | External `opencode` pass timed out after inspection and verification; no substantive verdict returned. |
| PR Review | [review-pr.md](./review-pr.md) | OPEN | PR #13 is open: https://github.com/SteeZyT33/spec-kit-orca/pull/13 |
| Self-Review | [self-review.md](./self-review.md) | PRESENT | v1 shape is intentionally narrow and acceptable. |

## Latest Review Status

- Current blockers: none from local code review; external cross-review did not return substantive findings before timeout
- Delivery readiness: ready for PR review
- Latest review update: 2026-04-10 via [review-code.md](./review-code.md) and [review-cross.md](./review-cross.md)

## Requested Reviewer

- agent: `opencode`
- model: `github-copilot/claude-opus-4.6`
- variant: `high`
- scope: design, with provider-agnostic and Claude Code compatibility emphasis
- date: 2026-04-10

## Verdict

`011` is directionally strong. The wrapper-capability and portable-principle
distinction is the right product move. The main remaining issue is not the
conceptual model; it is that the spec should validate itself with at least one
real entry early rather than staying purely structural.

## Findings

1. **High**: `011` should create at least one concrete wrapper-capability
   harvest entry early, preferably `deep-optimize`, so the model is validated
   against a real adoption decision rather than only abstract schema.
2. **Medium**: portable-principle entries should be labeled explicitly enough
   that host-specific runtime details can be excluded without ambiguity.
3. **Medium**: the current direction is compatible with Claude Code because it
   adopts principles, not Codex/OMX runtime contracts.

## Claude Code Compatibility

The reviewer’s opinion was that `011` is compatible with mixed worker CLIs,
including Claude Code, because it is preserving adoption boundaries rather than
encoding one host runtime as Orca’s default. The important rule is to keep:

- portable coordination principles
- explicit ownership boundaries
- rejection of host-specific env vars, CLI wiring, and filesystem layout

## Recommended Changes

1. Seed a real `deep-optimize` wrapper-capability entry in the first real
   implementation pass.
2. Keep adoption-scope labeling explicit for portable-principle entries.
3. Continue rejecting tmux/OMX/Codex-specific runtime contracts as direct Orca
   imports.

## Implementation Resolution

The implementation now validates the review's main concern:

- seeded real harvest entries under `.specify/orca/evolve/entries/`
- included a real `deep-optimize` wrapper-capability entry
- labeled portable-principle versus mixed adoption scope explicitly
- kept host-specific runtime details out of the seeded adoption set

So the design is no longer only structural. `011` now ships with a real
inventory, a generated overview, and deterministic helper behavior.
