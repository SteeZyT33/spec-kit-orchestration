# Implementation Plan: Orca Evolve

**Branch**: `011-orca-evolve` | **Date**: 2026-04-09 | **Spec**: [spec.md](./spec.md)

## Summary

Build `orca-evolve` as a durable adoption-control system for Orca. The first
version focuses on harvest entry storage, adoption-decision tracking, target
mapping into existing or future Orca specs, and an operator-facing inventory of
remaining worthwhile external ideas. It does not attempt fully automated repo
sync or magical source harvesting.

It should also be able to track when the right Orca move is to expose a thin
Orca-native wrapper over an external specialist system instead of rebuilding
that system locally.

## Technical Context

**Primary runtime**: Python 3.10+ for deterministic harvest-entry and index
helpers, Markdown records for human-readable adoption artifacts, existing Orca
docs/spec tree as destination references.

**Primary inputs**:

- `docs/orca-harvest-matrix.md`
- existing `004` through `010` upgrade specs
- future external source analyses such as Spex follow-up reviews

## Design Decisions

### 1. Evolve Owns Adoption Decisions, Not Raw Research

Research may come from chats, manual repo reads, repomix outputs, or future
deep-research tooling. Evolve’s responsibility is to preserve what Orca decided
to do with that research.

### 2. The Canonical Unit Is A Harvest Entry

Each entry should represent one external pattern or upgrade idea under
evaluation.

A harvest entry needs:

- source attribution
- concise summary
- adoption status
- rationale
- target mapping
- follow-up link when one exists

### 3. Keep The Decision Vocabulary Small

The first version should support a small explicit vocabulary:

- direct-take
- adapt-heavily
- defer
- reject

This is enough to preserve decision quality without creating taxonomy sprawl.

### 4. Prefer One Durable Entry Per Idea

A file-per-entry model is easier to inspect, review, update, and link from
future specs than a monolithic registry-only file.

An overview index can then be generated or maintained secondarily.

### 5. Mapping Into Orca Must Be First-Class

The feature is only useful if adopted ideas can be traced to:

- an existing Orca spec
- a future feature slot
- a capability pack
- or a deliberate parking/defer state

### 6. Wrapper Adoption Is Different From Core Ownership

Some worthwhile upgrades should enter Orca as thin wrappers around external
specialist skills rather than as native Orca engines. Evolve should preserve
that distinction explicitly.

Examples currently in view:

- `deep-optimize` -> Orca-facing wrapper over `autoresearch`
- `deep-research` -> future Orca-facing wrapper over external research tooling
- `deep-review` -> future Orca-facing wrapper over external deep-review
  capability when justified
- state-first mailbox and delegated-work patterns -> Orca-native coordination
  principles harvested from tmux-based team systems without importing OMX
  runtime assumptions

For these cases, Evolve should track:

- the Orca wrapper name and purpose
- the external dependency it delegates to
- the part Orca owns, such as scoping, routing, and artifact expectations
- the part Orca intentionally does not own

The same rule applies to provider-specific team runtimes:

- keep portable coordination principles such as durable mailbox state,
  acknowledgments, and claim-safe work lifecycle
- reject host-specific details such as OMX env vars, CLI commands, tmux pane
  wiring, and `.omx` filesystem contracts

## Scope

### In Scope

- harvest entry model
- adoption decision model
- target mapping model
- wrapper-capability adoption model
- overview/index of open and resolved harvest work
- operator workflow for adding/updating entries
- source attribution and rationale preservation

### Out Of Scope

- full automated upstream sync
- auto-generated diffs across arbitrary repos
- giant research warehouse behavior
- forcing every entry into a new spec immediately
- replacing future deep-research or repo-analysis tooling
- absorbing external specialist engines into Orca without an explicit decision

## Risks And Mitigations

### Risk: Evolve becomes a static note graveyard

Mitigation: require target mapping and adoption status, not just summaries.

### Risk: Evolve duplicates roadmap/spec structure

Mitigation: Evolve points into Orca specs and future slots rather than
replacing the roadmap.

### Risk: Source attribution becomes too weak for future revisits

Mitigation: preserve source repo/path references plus local rationale in each
entry.

### Risk: The system overreaches into automated sync too early

Mitigation: keep v1 intentionally manual-but-structured.

## Delivery Strategy

### Phase 1: Harvest Entry Model

- define entry schema
- define storage layout
- define decision vocabulary

### Phase 2: Index And Inventory

- define overview/index structure
- surface open, deferred, adopted, and rejected items

### Phase 3: Mapping Workflow

- link entries to Orca specs, roadmap items, or future slots
- support follow-up references and adoption state changes

### Phase 4: Wrapper Capability Tracking

- represent thin Orca wrappers over external specialist systems
- preserve ownership boundaries and external dependencies
- track approved wrapper candidates such as `deep-optimize`,
  `deep-research`, and `deep-review`

### Phase 5: Operator Surface

- add/update entry workflow
- inspect/list inventory workflow
- document how Evolve interacts with future research inputs

## Verification Strategy

- deterministic tests for entry parsing/serialization
- tests for decision-state transitions and target mappings
- tests for wrapper-capability records and ownership-boundary fields
- tests for harvest entries that distinguish portable principle from rejected
  host-specific runtime detail
- manual validation with a small set of real Spex-derived ideas
- manual validation with wrapper candidates like `deep-optimize`
- verification that the overview/index remains consistent with entry files

## Open Planning Questions

- should the overview be generated or manually maintained?
- what is the best directory layout for harvest entries?
- should target mapping allow multiple destinations or only one canonical
  destination in v1?
- should Evolve directly scaffold future specs or only reference them?
- should wrapper capabilities live as normal harvest entries with extra fields
  or as a dedicated entry subtype in v1?
