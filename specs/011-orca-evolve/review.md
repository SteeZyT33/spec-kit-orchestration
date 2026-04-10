# Cross Review: Orca Evolve

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
