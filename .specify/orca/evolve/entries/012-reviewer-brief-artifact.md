# Evolve Entry EV-012: Reviewer Brief Artifact

**Source Name**: cc-spex
**Source Ref**: docs/spex-adoption-notes.md#3-reviewer-facing-summaries
**Decision**: adapt-heavily
**Status**: open
**Entry Kind**: pattern
**Target Kind**: existing-spec
**Target Ref**: 012-review-model
**Follow Up Ref**: specs/012-review-model/contracts/
**Adoption Scope**: portable-principle
**External Dependency**: none
**Ownership Boundary**: none
**Created**: 2026-04-10
**Updated**: 2026-04-10

## Summary
Generate a reviewer-facing brief alongside review.md that answers what changed, where to start, what decisions need human eyes, and what risks matter.

## Rationale
006-orca-review-artifacts splits review outputs into spec/plan/code/cross/pr artifacts but does not own a separate human-facing reviewer brief. Spex's approach is a distinct layer above the raw review artifacts and worth adopting as its own artifact kind rather than silently merging into code-review.

## Mapping Notes
Adopt as an additional review artifact kind under 006, not as a new command. Keep review.md as the authoritative record and treat reviewer-brief.md as a derived human-facing summary.
