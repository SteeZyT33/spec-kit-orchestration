# Adoption Record: AR-003: Templates infrastructure

**Status**: adopted
**Adopted-on**: 2026-04-15
**Baseline Commit**: cad775f

## Summary
Directory of spec templates, command templates, and review templates consumed by the speckit-orca toolchain. Central to both ext install (copied into user workspaces) and runtime (read on-demand by command prompts).

## Location
- templates/
- templates/review-spec-template.md
- templates/review-code-template.md
- templates/review-pr-template.md

## Key Behaviors
- Install time: bootstrap copies templates to target workspace so command prompts can render from them
- Runtime: command prompts reference these paths when guiding an operator through spec/plan/tasks drafting
- Review templates align with 012's three-artifact model (review-spec / review-code / review-pr)

## Known Gaps
No automated drift check between spec templates and the contracts they implement — template rot is detected only at next use
