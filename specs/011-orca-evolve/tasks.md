# Tasks: Orca Evolve

## Phase 1: Lock The Adoption Model

- [x] T001 Re-read [spec.md](./spec.md), [brainstorm.md](./brainstorm.md), [plan.md](./plan.md), [data-model.md](./data-model.md), and contracts to confirm Evolve stays an adoption-control system rather than a vague research notebook.
- [x] T002 Cross-check [docs/orca-harvest-matrix.md](../../docs/orca-harvest-matrix.md) and capture which current Spex-derived ideas should seed initial Evolve entries.
- [x] T003 Cross-check [004-orca-workflow-system-upgrade/spec.md](../004-orca-workflow-system-upgrade/spec.md) and confirm how Evolve maps new adoption candidates into existing specs or future feature slots.
- [x] T004 Lock how Evolve represents thin Orca wrapper capabilities over external specialist systems.
- [x] T005 Update planning artifacts if the target mapping, wrapper-capability model, or decision vocabulary needs refinement before implementation.

## Phase 2: Harvest Entry Storage

- [x] T006 Define the on-disk storage layout for harvest entries and the overview/index.
- [x] T007 Implement the canonical harvest-entry schema from [data-model.md](./data-model.md).
- [x] T008 Implement validation for decision values, target mappings, wrapper-capability fields, and required source attribution.
- [x] T009 Implement deterministic read/write helpers for entry files.
- [x] T010 Add tests for valid entries, malformed entries, and safe parse failures.

## Phase 3: Index And Inventory

- [x] T011 Implement the overview/index surface for open, mapped, implemented, deferred, and rejected entries.
- [x] T012 Ensure the overview stays consistent with the underlying entry set.
- [x] T013 Add tests for overview generation, filtering, state counts, and wrapper-capability visibility.

## Phase 4: Adoption Workflow

- [x] T014 Implement entry creation flow with required source attribution and initial decision state.
- [x] T015 Implement entry update flow for decision changes, rationale updates, target remapping, and wrapper-capability metadata.
- [x] T016 Implement target mapping to existing specs, future feature slots, capability packs, or roadmap placeholders.
- [x] T017 Ensure deferred and rejected items remain visible and inspectable.
- [x] T018 Add tests for decision transitions, target-mapping updates, and wrapper-capability ownership-boundary fields.

## Phase 5: Seed Real Spex-Derived Entries

- [x] T019 Seed initial Evolve entries from the current Spex harvest queue captured in [docs/orca-harvest-matrix.md](../../docs/orca-harvest-matrix.md).
- [x] T020 Map already-accounted-for ideas to their current Orca specs where appropriate.
- [x] T021 Record the remaining worthwhile piecemeal Spex ideas that are still not represented by an existing Orca spec. (EV-011 Drift Reconciliation, EV-012 Reviewer Brief Artifact, EV-013 Spec-Compliance-First Code Review)
- [x] T022 Add explicit wrapper-capability entries for `deep-optimize`, `deep-research`, and `deep-review` with external dependency and ownership-boundary notes. (EV-008, EV-009, EV-010)
- [x] T023 Add explicit harvest entries for portable team/worker patterns such as state-first mailbox coordination, durable ACK/report queues, and claim-safe delegated work, while marking OMX-specific runtime details as excluded. (EV-007)
- [x] T024 Verify that each seeded entry has clear source attribution, decision rationale, destination mapping or explicit defer state, and adoption-scope labeling.
- [x] T024a Migrate the remaining ad-hoc harvest docs ([docs/spex-harvest-list.md](../../docs/spex-harvest-list.md) and [docs/spex-adoption-notes.md](../../docs/spex-adoption-notes.md)) into Evolve entries so the durable store becomes the single source of truth rather than living alongside prose notes.
- [x] T024b Once migration is confirmed (T019, T024a), retire the ad-hoc harvest docs by replacing them with short stubs pointing at the Evolve overview, so the parallel system cannot rot silently.

## Phase 6: Operator Docs And Verification

- [x] T025 Update `README.md` and adoption docs to explain the Evolve workflow, wrapper capabilities, portable-principle harvest entries, and where to find harvest records.
- [x] T026 Run manual verification on a small real set of Spex-derived entries, wrapper-capability entries, and portable-principle entries to confirm the workflow is useful, not just structurally valid.
- [x] T027 Run `self-review` and `cross-review`, apply valid findings, and confirm Evolve remains disciplined and provider-agnostic.

## Validation Notes

- Implemented runtime: `src/speckit_orca/evolve.py`
- Implemented tests: `tests/test_evolve.py`
- Seeded inventory: `.specify/orca/evolve/`
- Review artifacts:
  - `review-code.md`
  - `review-cross.md`
  - `review.md`
  - `self-review.md`
- Merged via PR #13
