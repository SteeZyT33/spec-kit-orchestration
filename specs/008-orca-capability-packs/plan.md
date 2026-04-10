# Implementation Plan: Orca Capability Packs

**Branch**: `008-orca-capability-packs` | **Date**: 2026-04-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-orca-capability-packs/spec.md`

## Summary

Define a lightweight Orca capability-pack model for optional cross-cutting
workflow behavior so the core command set stops absorbing every subsystem
concern directly. The feature should establish:

- what a capability pack is
- how packs differ from core behavior
- how packs declare affected commands, prerequisites, and activation semantics
- a simpler composition model than Spex traits-as-implemented

This feature is primarily an architecture and configuration/contract feature,
but the first implementation also ships a small deterministic runtime helper so
packs are inspectable in practice. It improves how Orca reasons about optional
subsystems without requiring a heavy trait engine.

## Technical Context

**Language/Version**: Markdown architecture artifacts, command docs, config/manifest concepts, and lightweight runtime/config plumbing if needed  
**Primary Dependencies**: `004-orca-workflow-system-upgrade`, current Orca command set, planned subsystem specs (`002`, `005`, `007`, `009`), extension metadata in `extension.yml`  
**Storage**: pack definitions in durable repo artifacts and possibly config/manifest surfaces if activation becomes runtime-visible  
**Testing**: document-level validation, config/contract validation, and lightweight activation checks if runtime support is introduced  
**Target Platform**: Orca repository architecture and later runtime/config usage  
**Project Type**: workflow composition architecture feature  
**Performance Goals**: pack understanding and activation should remain simple and near-zero overhead compared with actual workflow execution  
**Constraints**: simpler than Spex traits, provider-agnostic, inspectable, should not hide the core workflow behind opaque layering  
**Scale/Scope**: a small set of first-class packs for major Orca subsystems rather than a general-purpose extension platform

## Constitution Check

### Pre-design gates

1. **Provider-agnostic orchestration**: pass. Packs are meant to describe or
   activate provider-agnostic workflow behavior, not provider-specific hacks.
2. **Spec-driven delivery**: pass. This feature now has a real planning set.
3. **Safe parallel work**: pass. Clear pack boundaries help reduce hidden
   subsystem overlap during later parallel implementation.
4. **Verification before convenience**: pass. Pack semantics should be explicit
   and documented before any runtime activation behavior is trusted.
5. **Small, composable runtime surfaces**: pass with emphasis. This feature
   exists specifically to keep Orca composable without importing trait bloat.

### Post-design check

The design remains constitution-aligned because it:

- keeps optional behavior explicit
- avoids overbuilding a trait engine
- supports composability without hiding core command behavior

No constitution violations need justification.

## Project Structure

### Documentation (this feature)

```text
specs/008-orca-capability-packs/
├── spec.md
├── brainstorm.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── capability-pack-model.md
│   ├── pack-activation.md
│   └── core-vs-pack-boundaries.md
└── tasks.md
```

### Source Code (repository root)

```text
extension.yml
config-template.yml
commands/
├── brainstorm.md
├── cross-review.md
├── code-review.md
└── ...

docs/
├── orca-harvest-matrix.md
└── orca-roadmap.md
```

**Structure Decision**: Start with an explicit pack model and boundary rules in
docs/contracts first. Only add runtime/config activation support if a minimal,
inspectable activation path is clearly beneficial.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New composition model for optional behavior | Orca needs a cleaner answer than command sprawl | Keeping everything in core commands recreates the exact architectural drift repomix exposed |
| Possible docs-first before runtime activation | Pack semantics need to be correct before adding machinery | Immediate runtime activation without a stable model would create another opaque system |

## Research Decisions

### 1. Capability packs should be simpler than traits

Decision: design a lightweight pack model rather than copying Spex traits.

Rationale:

- preserves inspectability
- fits Orca's current scale
- avoids Claude/Spex substrate baggage

Alternatives considered:

- copy traits closely: too much complexity
- no pack model: command sprawl continues

### 2. Core versus pack boundary must be explicit

Decision: define what behavior is core workflow versus pack-scoped optional
behavior.

Rationale:

- without this, packs become a relabeling exercise
- core command readability depends on this line being clear

Alternatives considered:

- classify later during implementation: too vague

### 3. Start with pack declarations before strong runtime activation

Decision: the first version should prioritize pack model, affected-command
mapping, and activation semantics before building a larger runtime system.

Rationale:

- keeps the feature honest
- lets later runtime support build on a stable contract

Alternatives considered:

- runtime-first pack activation: too easy to overbuild

### 4. Candidate packs come from existing subsystem boundaries

Decision: initial packs should map to already-identified Orca subsystem
boundaries, such as:

- brainstorm-memory
- flow-state
- worktrees
- review
- yolo

Rationale:

- matches the repomix harvest
- aligns with `004` subsystem thinking

## Design Decisions

### 1. A capability pack needs explicit ownership metadata

Each pack should describe:

- its purpose
- affected commands
- required artifacts/runtime prerequisites
- activation mode
- maturity/status

### 2. Packs must not make the core command set unreadable

If a command cannot be understood without understanding three packs, the model
has failed.

### 3. `009-orca-yolo` should be a downstream pack consumer, not the pack model itself

The pack model should exist before orchestration uses it.

## Implementation Phases

### Phase 0: Pack model and boundary design

Define:

- the pack data model
- core vs optional behavior boundaries
- candidate initial pack set

### Phase 1: Activation semantics

Define:

- how packs are declared
- how activation is represented
- what "installed", "enabled", and "experimental" mean

Implement:

- built-in pack registry
- repo-local manifest override support
- deterministic inspection commands

### Phase 2: Alignment with Orca commands and upgrade program

Define:

- which commands each pack influences
- how `004` and later `009` may assume pack behavior exists

## Verification Strategy

### Primary verification

1. define at least one realistic capability pack
2. verify its boundaries and affected commands are explicit
3. verify the core command set remains understandable without hidden pack logic
4. verify the pack model is clearly simpler than Spex traits-as-implemented

### Secondary verification

- consistency checks against `004`, `002`, `005`, `007`, and `009`
- `git diff --check`
- config/manifest checks if runtime activation is introduced

## Risks

### 1. Pack model becomes trait-clone complexity

Mitigation:

- keep the pack contract narrow
- prefer docs/model clarity before runtime machinery

### 2. Pack model becomes purely decorative

Mitigation:

- require affected-command and activation semantics
- tie packs to real subsystem boundaries

### 3. Core versus optional drift remains unclear

Mitigation:

- explicit boundary contract
- examples using real Orca subsystems

## Non-goals

- copying Spex trait architecture
- building a general-purpose plugin platform
- hiding all advanced Orca behavior behind pack indirection
- implementing `009-orca-yolo` in this feature
