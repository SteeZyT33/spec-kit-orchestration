# Implementation Plan: Orca Context Handoffs

**Branch**: `007-orca-context-handoffs` | **Date**: 2026-04-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-orca-context-handoffs/spec.md`

## Summary

Add an explicit context handoff layer between major Orca workflow stages so
commands can preserve continuity through durable artifacts instead of relying on
active chat/session memory. The feature should define:

- supported stage transitions
- what upstream context each stage should inherit
- a stable handoff artifact or handoff-section contract
- how branch and worktree context participate in handoff resolution

This feature is an integration-quality layer. It should sit on top of durable
artifacts from brainstorm memory, flow state, review artifacts, and worktree
runtime rather than replacing them.

## Technical Context

**Language/Version**: Markdown command docs, Bash/Python runtime helpers where needed, workflow artifacts under `specs/` and `.specify/orca/`  
**Primary Dependencies**: `002-brainstorm-memory`, `005-orca-flow-state`, `006-orca-review-artifacts`, existing `commands/*.md`, worktree/runtime metadata under `.specify/orca/`  
**Storage**: durable handoff artifacts or sections under feature directories, plus branch/worktree context when present  
**Testing**: document-level contract validation, manual transition verification, and runtime smoke checks if helper code is added  
**Target Platform**: Orca repository workflow and later multi-worktree/fresh-session execution  
**Project Type**: workflow integration feature / artifact-contract plus helper-runtime repository  
**Performance Goals**: handoff resolution should be immediate from durable artifacts and must not require replaying prior chat context  
**Constraints**: provider-agnostic, durable-artifact-first, compatible with worktree-based execution, must remain lighter-weight than a full memory graph  
**Scale/Scope**: major workflow stage transitions across brainstorm, specify, plan, tasks, implement, review, and PR flow

## Constitution Check

### Pre-design gates

1. **Provider-agnostic orchestration**: pass. Handoffs are defined through
   durable artifacts and branch/worktree context rather than provider state.
2. **Spec-driven delivery**: pass. This feature now has a real spec and plan.
3. **Safe parallel work**: pass. Handoffs should improve continuity across
   worktrees and parallel lanes without introducing silent state mutation.
4. **Verification before convenience**: pass. The feature will require explicit
   transition validation rather than assuming continuity works.
5. **Small, composable runtime surfaces**: pass. The handoff layer should
   define lightweight contracts, not a giant opaque state system.

### Post-design check

The design remains constitution-aligned because it:

- prefers durable artifacts over hidden context
- integrates with existing Orca layers instead of replacing them
- improves transition safety for parallel and fresh-session workflows

No constitution violations need justification.

## Project Structure

### Documentation (this feature)

```text
specs/007-orca-context-handoffs/
├── spec.md
├── brainstorm.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── handoff-contract.md
│   ├── stage-transitions.md
│   └── handoff-resolution.md
└── tasks.md
```

### Source Code (repository root)

```text
commands/
├── brainstorm.md
├── code-review.md
├── pr-review.md
└── ...

scripts/
└── bash/
    └── ...                  # helper/runtime surface only if needed

src/
└── speckit_orca/
    └── context_handoffs.py  # deterministic handoff create/resolve helper

specs/
├── 002-brainstorm-memory/
├── 005-orca-flow-state/
└── 006-orca-review-artifacts/
```

**Structure Decision**: The feature started with explicit contracts and command
guidance, then added a thin deterministic helper in
`src/speckit_orca/context_handoffs.py` once resolver semantics became concrete.
The main value remains stable transition semantics, not a large new runtime.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Explicit handoff artifacts/contracts | Stage continuity is currently too implicit for fresh sessions and later orchestration | Branch-only inference loses intent and is too weak |
| Cross-spec dependency on `002`, `005`, and `006` | Handoff usefulness depends on durable upstream artifacts and downstream consumers | Making `007` stand alone would force it to invent missing primitives |

## Research Decisions

### 1. Handoffs must be explicit, not inferred only from branch

Decision: define explicit handoff contracts between major workflow stages.

Rationale:

- branch-based lookup helps, but does not capture intent or unresolved context
- later tooling needs explicit upstream context shape

Alternatives considered:

- branch-only resolution: too implicit
- pure prompt guidance: too inconsistent

### 2. Handoff artifacts should stay lightweight

Decision: use lightweight durable handoff artifacts or embedded handoff sections
instead of building a large general-purpose state store.

Rationale:

- preserves inspectability
- keeps the feature aligned with Orca's simple runtime philosophy

Alternatives considered:

- large centralized handoff database: overbuilt

### 3. `007` should integrate, not own, memory and state

Decision: `007` depends on upstream artifact layers such as brainstorm memory
and flow state, but should not redefine them.

Rationale:

- keeps subsystem boundaries clear
- fits the `004` upgrade program contract

Alternatives considered:

- make `007` absorb memory/state roles: too much scope and likely drift

### 4. Worktree context is additive, not mandatory

Decision: handoffs should attach branch/worktree/lane context when present, but
must still work in feature-wide repos without active lane metadata.

Rationale:

- keeps the feature broadly usable
- aligns with Orca's degrade-safely direction

Alternatives considered:

- require worktree metadata for all handoffs: too restrictive

## Design Decisions

### 1. Define the major stage transitions first

The feature should explicitly cover:

- brainstorm -> specify
- specify -> plan
- plan -> tasks
- tasks/assign -> implement
- implement -> code-review
- code-review/cross-review -> pr-review

### 2. Handoff resolution should name source, target, and upstream artifacts

Every handoff needs at least:

- source stage
- target stage
- primary upstream artifact paths
- current intent/summary
- unresolved questions
- branch/worktree context when relevant

### 3. `007` should feed `009-orca-yolo`

The handoff layer is part of what makes orchestration possible later. `009`
should not need to invent transition logic if `007` exists.

## Implementation Phases

### Phase 0: Stage transition and artifact contract design

Define:

- the supported transitions
- the handoff artifact or section shape
- the minimum required fields

### Phase 1: Resolution and command integration design

Define:

- how commands locate prior-stage context
- how branch/worktree context contributes to resolution
- how missing handoffs degrade safely

### Phase 2: Downstream orchestration alignment

Define:

- what `005`, `006`, and `009` may assume about handoff outputs
- how handoffs interact with review and flow-state artifacts

## Verification Strategy

### Primary verification

Manual transition checks:

1. simulate brainstorm -> specify continuity
2. simulate specify -> plan continuity
3. simulate plan -> tasks continuity
4. simulate implement -> review continuity
5. simulate worktree/fresh-session continuation and verify upstream artifacts
   remain resolvable

### Secondary verification

- consistency checks across `007`, `002`, `005`, and `006`
- `git diff --check`
- runtime helper tests and CLI smoke checks now that helper code exists

## Risks

### 1. Handoff sprawl

Too many handoff artifacts could clutter features.

Mitigation:

- keep handoffs lightweight
- focus on major transitions only

### 2. Overlap with flow state

`005` and `007` could drift into overlapping ownership.

Mitigation:

- `005` owns current-stage/state understanding
- `007` owns stage-to-stage continuity and upstream-context resolution

### 3. Overlap with brainstorm memory and review artifacts

`002` and `006` already produce durable artifacts that may include contextual
data.

Mitigation:

- `007` references those artifacts as inputs rather than redefining them

## Non-goals

- replacing flow state
- replacing brainstorm memory
- replacing review artifacts
- building the full `orca-yolo` runner in this feature
