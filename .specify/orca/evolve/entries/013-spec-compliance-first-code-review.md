# Evolve Entry EV-013: Spec-Compliance-First Code Review

**Source Name**: cc-spex
**Source Ref**: docs/spex-harvest-list.md (retired; original workflow section migrated to Evolve entry)
**Decision**: adapt-heavily
**Status**: open
**Entry Kind**: pattern
**Target Kind**: existing-spec
**Target Ref**: review-code
**Follow Up Ref**: commands/review-code.md
**Adoption Scope**: portable-principle
**External Dependency**: none
**Ownership Boundary**: none
**Created**: 2026-04-10
**Updated**: 2026-04-10

## Summary
Adopt spex's spec-compliance-first framing for code review: explicit deviations from spec, compliance matrix, and a clean distinction between deviations and improvements.

## Rationale
The current Orca code-review command covers implementation quality and merge readiness but does not explicitly frame itself around spec compliance the way spex does. Adopting the posture makes deviation tracking a first-class review output rather than prose.

## Mapping Notes
Adopt the posture and the deviation vs improvement distinction without importing deep-review trait assumptions. Keep PR-specific concerns in pr-review.
