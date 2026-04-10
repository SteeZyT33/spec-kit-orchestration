# Feature Specification: Orca Evolve

**Feature Branch**: `011-orca-evolve`  
**Created**: 2026-04-09  
**Status**: Draft  
**Input**: User description: "Add an Orca self-evolution system that can harvest desired patterns from Spex and other repos, track adoption decisions, and implement the remaining worthwhile piecemeal upgrades intentionally."

## Context

The repomix review made it clear that Orca still has valuable patterns left to
harvest from `cc-spex`, especially around self-upgrade discipline and modular
workflow evolution. So far Orca has adopted pieces through ad hoc planning.
`orca-evolve` makes that process first-class.

This feature is not only a research notebook. It is the mechanism by which
Orca tracks desired external capabilities, decides what to adopt, and records
how those capabilities should map into the Orca workflow system.

That should include thin Orca-facing wrappers over strong external specialist
skills when that is the better product move than owning the underlying engine.
Current examples are `deep-optimize`, `deep-research`, and `deep-review`,
which should be treated as adopted entrypoints and workflow contracts, not
Orca-owned research or optimization cores.

It should also capture portable workflow patterns harvested from provider- or
runtime-specific systems, as long as Orca adopts the principle rather than the
host-specific machinery. Current examples include state-first coordination,
durable mailbox/report queues, and claim-safe delegated work drawn from
tmux-based team systems.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Track What Orca Still Wants To Adopt (Priority: P1)

A maintainer wants a durable way to record which external ideas or features are
still under consideration so good patterns are not lost between sessions.

**Why this priority**: Orca is already mid-upgrade. Missing adoption tracking
would force repeated rediscovery work.

**Independent Test**: Record multiple candidate external patterns and verify
Orca can show their status, rationale, and intended destination in the upgrade
program.

**Acceptance Scenarios**:

1. **Given** an external repo contains a useful workflow pattern,
   **When** the maintainer captures it through Evolve,
   **Then** Orca records the source, summary, adoption status, and target Orca
   subsystem.
2. **Given** an adoption idea is deferred or rejected,
   **When** the maintainer revisits the harvest log,
   **Then** Orca preserves the decision and reasoning instead of forcing
   rediscovery.

---

### User Story 2 - Convert Harvested Ideas Into Actionable Orca Work (Priority: P1)

A maintainer wants harvested ideas to turn into concrete specs, upgrades, or
packaged follow-up work rather than sitting as loose notes.

**Why this priority**: Adoption tracking only matters if it influences actual
product evolution.

**Independent Test**: Take a harvested pattern and verify Evolve can link it to
an Orca spec, roadmap item, or capability-pack follow-up.

**Acceptance Scenarios**:

1. **Given** a harvested pattern belongs inside an existing Orca feature,
   **When** Evolve records the mapping,
   **Then** the adoption entry links to the target spec or subsystem.
2. **Given** a harvested pattern does not fit any current Orca spec,
   **When** Evolve records the mapping,
   **Then** the system can mark it as a future feature candidate instead of
   losing it.

---

### User Story 3 - Implement Remaining Piecemeal Spex Features Intentionally (Priority: P2)

A maintainer wants Orca to absorb the remaining worthwhile Spex-style features
without blindly cloning the whole system.

**Why this priority**: This is the balance between product discipline and
continued harvest value.

**Independent Test**: Review the Evolve inventory and verify it distinguishes
direct takes, heavy adaptations, and rejected patterns, with explicit follow-up
actions for the adopted items.

**Acceptance Scenarios**:

1. **Given** Orca still wants selected Spex ideas after the initial workflow
   upgrade,
   **When** those ideas are logged in Evolve,
   **Then** each entry shows whether it should be taken directly, adapted
   heavily, or avoided.
2. **Given** a desired piecemeal feature is approved,
   **When** implementation planning begins,
   **Then** Evolve can point to the adoption artifact and destination spec.

### Edge Cases

- What happens if a source repo changes significantly? Evolve MUST preserve the
  snapshot reasoning that led to prior adoption decisions.
- What happens if multiple sources propose overlapping ideas? Evolve MUST allow
  duplicate or competing patterns to be compared intentionally.
- What happens if a harvested pattern is useful but out of scope for the
  current Orca wave? Evolve MUST support deferral without losing the reasoning.
- What happens if a feature is copied directly from another repo? Evolve MUST
  still require explicit adoption rationale and target mapping rather than
  silent copy/paste.
- What happens if Orca wants to expose an external skill behind an Orca-native
  command or skill name? Evolve MUST be able to record that Orca owns the
  wrapper contract while the external system remains the underlying engine.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Orca MUST define a durable self-evolution/adoption workflow.
- **FR-002**: `orca-evolve` MUST track external source patterns, summaries,
  adoption status, and rationale.
- **FR-003**: `orca-evolve` MUST record the intended Orca destination for each
  adopted or candidate pattern, such as an existing spec, future feature, or
  capability pack.
- **FR-004**: The system MUST distinguish at least direct-take, adapt-heavily,
  defer, and reject outcomes for harvested patterns.
- **FR-005**: `orca-evolve` MUST support the remaining worthwhile piecemeal
  Spex adoption work rather than treating the current upgrade as exhaustive.
- **FR-006**: `orca-evolve` MUST remain provider-agnostic and repo-agnostic so
  it can harvest from sources beyond Spex later.
- **FR-007**: The first version SHOULD integrate with existing Orca roadmap and
  spec artifacts rather than inventing a disconnected planning system.
- **FR-008**: The first version MUST preserve enough source attribution and
  local reasoning for maintainers to revisit prior adoption decisions
  intentionally.
- **FR-009**: `orca-evolve` MUST support adoption records for thin Orca-native
  wrappers over external specialist systems, including the wrapper purpose, the
  external dependency, and the boundary of what Orca does or does not own.
- **FR-010**: The first version SHOULD be able to record external specialist
  wrappers such as `deep-optimize`, `deep-research`, and `deep-review` as
  first-class adoption candidates or approved follow-on work.
- **FR-011**: `orca-evolve` SHOULD support harvest records for portable
  workflow principles taken from provider-specific systems, while explicitly
  excluding host-specific runtime contracts, CLI wiring, and filesystem layout.

### Key Entities *(include if feature involves data)*

- **Harvest Entry**: One durable record of an external idea, pattern, or
  feature being evaluated for Orca adoption.
- **Adoption Decision**: The status and rationale for whether Orca takes,
  adapts, defers, or rejects a harvested idea.
- **Target Mapping**: The Orca subsystem, spec, or future feature that the
  harvested idea maps into.
- **Wrapper Capability**: An Orca-native entrypoint that delegates to an
  external specialist skill or system while preserving Orca-specific workflow
  expectations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Maintainers can inspect a durable inventory of external patterns
  Orca still wants to adopt.
- **SC-002**: Adopted patterns can be traced to an Orca destination instead of
  remaining disconnected notes.
- **SC-003**: Orca can continue harvesting worthwhile Spex ideas without
  re-running the same repo analysis from scratch each time.
- **SC-004**: Maintainers can distinguish between capabilities Orca owns
  directly and Orca-native wrapper capabilities that depend on external
  specialist systems.
- **SC-005**: Maintainers can distinguish between portable workflow principles
  Orca intends to adopt and provider- or runtime-specific implementation
  details Orca intentionally leaves behind.

## Documentation Impact *(mandatory)*

- **README Impact**: Required
- **Why**: This feature adds a visible self-evolution workflow and changes how Orca explains ongoing harvest, adoption, and future upgrade work.
- **Expected Updates**: `README.md`, harvest/adoption docs, future Evolve workflow docs

## Assumptions

- `docs/orca-harvest-matrix.md` is an initial input, not a sufficient long-term
  adoption system.
- Spex is the immediate harvest source, but future sources may also feed
  `orca-evolve`.
- Some adoption work will remain piecemeal even after the current workflow
  upgrade program is complete.
