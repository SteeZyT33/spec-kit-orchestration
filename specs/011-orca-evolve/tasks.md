# Tasks: Orca Evolve

## Phase 1: Lock The Adoption Model

- [ ] T001 Re-read [spec.md](./spec.md), [brainstorm.md](./brainstorm.md), [plan.md](./plan.md), [data-model.md](./data-model.md), and contracts to confirm Evolve stays an adoption-control system rather than a vague research notebook.
- [ ] T002 Cross-check [docs/orca-harvest-matrix.md](../../docs/orca-harvest-matrix.md) and capture which current Spex-derived ideas should seed initial Evolve entries.
- [ ] T003 Cross-check [004-orca-workflow-system-upgrade/spec.md](../004-orca-workflow-system-upgrade/spec.md) and confirm how Evolve maps new adoption candidates into existing specs or future feature slots.
- [ ] T004 Lock how Evolve represents thin Orca wrapper capabilities over external specialist systems.
- [ ] T005 Update planning artifacts if the target mapping, wrapper-capability model, or decision vocabulary needs refinement before implementation.

## Phase 2: Harvest Entry Storage

- [ ] T006 Define the on-disk storage layout for harvest entries and the overview/index.
- [ ] T007 Implement the canonical harvest-entry schema from [data-model.md](./data-model.md).
- [ ] T008 Implement validation for decision values, target mappings, wrapper-capability fields, and required source attribution.
- [ ] T009 Implement deterministic read/write helpers for entry files.
- [ ] T010 Add tests for valid entries, malformed entries, and safe parse failures.

## Phase 3: Index And Inventory

- [ ] T011 Implement the overview/index surface for open, mapped, implemented, deferred, and rejected entries.
- [ ] T012 Ensure the overview stays consistent with the underlying entry set.
- [ ] T013 Add tests for overview generation, filtering, state counts, and wrapper-capability visibility.

## Phase 4: Adoption Workflow

- [ ] T014 Implement entry creation flow with required source attribution and initial decision state.
- [ ] T015 Implement entry update flow for decision changes, rationale updates, target remapping, and wrapper-capability metadata.
- [ ] T016 Implement target mapping to existing specs, future feature slots, capability packs, or roadmap placeholders.
- [ ] T017 Ensure deferred and rejected items remain visible and inspectable.
- [ ] T018 Add tests for decision transitions, target-mapping updates, and wrapper-capability ownership-boundary fields.

## Phase 5: Seed Real Spex-Derived Entries

- [ ] T019 Seed initial Evolve entries from the current Spex harvest queue captured in [docs/orca-harvest-matrix.md](../../docs/orca-harvest-matrix.md).
- [ ] T020 Map already-accounted-for ideas to their current Orca specs where appropriate.
- [ ] T021 Record the remaining worthwhile piecemeal Spex ideas that are still not represented by an existing Orca spec.
- [ ] T022 Add explicit wrapper-capability entries for `deep-optimize`, `deep-research`, and `deep-review` with external dependency and ownership-boundary notes.
- [ ] T023 Add explicit harvest entries for portable team/worker patterns such as state-first mailbox coordination, durable ACK/report queues, and claim-safe delegated work, while marking OMX-specific runtime details as excluded.
- [ ] T024 Verify that each seeded entry has clear source attribution, decision rationale, destination mapping or explicit defer state, and adoption-scope labeling.

## Phase 6: Operator Docs And Verification

- [ ] T025 Update `README.md` and adoption docs to explain the Evolve workflow, wrapper capabilities, portable-principle harvest entries, and where to find harvest records.
- [ ] T026 Run manual verification on a small real set of Spex-derived entries, wrapper-capability entries, and portable-principle entries to confirm the workflow is useful, not just structurally valid.
- [ ] T027 Run `self-review` and `cross-review`, apply valid findings, and confirm Evolve remains disciplined and provider-agnostic.
