# Implementation Plan: Orca Flow State

**Branch**: `005-orca-flow-state` | **Date**: 2026-04-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-orca-flow-state/spec.md`

## Summary

Add a computed-first Orca flow-state model that derives workflow progress from
durable artifacts, exposes current stage, review milestones, ambiguity, and
next-step guidance, and uses only thin persisted metadata where resume/start-from
or cached guidance truly needs it.

The feature should establish the canonical workflow stage model and state result
contract for later systems such as review artifacts, context handoffs, status
surfaces, and `orca-yolo`. It should not build a heavyweight hidden registry as
the primary truth.

## Technical Context

**Language/Version**: Markdown command docs, Bash helpers where needed, Python 3.10+ for deterministic flow-state computation  
**Primary Dependencies**: existing Spec Kit feature artifacts, Orca command docs, current review artifact shapes, worktree metadata when present, Python standard library  
**Storage**: durable workflow artifacts under `specs/<feature>/`, optional thin flow-state metadata under `.specify/orca/` or feature-local state files if justified  
**Testing**: manual artifact-state validation, `bash -n` for touched shell wrappers, `uv run python -m py_compile` for helper/runtime code, direct flow-state smoke checks  
**Target Platform**: local developer workstations using Orca on Linux/WSL2 first  
**Project Type**: workflow extension / state-model plus helper-runtime repository  
**Performance Goals**: flow-state resolution should feel effectively instant on typical Orca repos with small-to-moderate artifact sets  
**Constraints**: provider-agnostic, artifacts remain primary truth, explicit ambiguity reporting, no Claude-specific statusline substrate, no premature full orchestration engine  
**Scale/Scope**: feature-level workflow state across pre-spec, implementation, and review stages for Orca-managed projects

## Constitution Check

### Pre-design gates

1. **Provider-agnostic orchestration**: pass. The design resolves state from
   Orca artifacts and avoids provider-specific session infrastructure.
2. **Spec-driven delivery**: pass. This feature now has a refined spec and is
   being planned before implementation.
3. **Safe parallel work**: pass. Flow state may consume worktree/lane context,
   but must treat that as contextual evidence rather than hidden exclusive truth.
4. **Verification before convenience**: pass. The design requires explicit
   ambiguity handling and smoke-checkable state computation.
5. **Small, composable runtime surfaces**: pass. The design prefers computed
   state plus thin metadata over a large primary-truth registry.

### Post-design check

The chosen design stays aligned with the constitution because it:

- keeps artifacts as primary workflow truth
- avoids opaque provider-specific state
- keeps persisted metadata secondary and narrow
- favors explicit uncertainty over false certainty

No constitution violations need justification.

## Project Structure

### Documentation (this feature)

```text
specs/005-orca-flow-state/
├── spec.md
├── brainstorm.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── flow-state-contract.md
│   ├── stage-model.md
│   └── state-evidence.md
└── tasks.md
```

### Source Code (repository root)

```text
commands/
├── assign.md
├── cross-review.md
├── pr-review.md
└── self-review.md

scripts/
└── bash/
    └── ...                      # wrappers only if flow-state needs shell entrypoints

src/
└── speckit_orca/
    └── flow_state.py            # NEW deterministic flow-state computation helper

docs/
├── orca-harvest-matrix.md
└── worktree-protocol.md         # contextual evidence only when relevant
```

**Structure Decision**: Put the canonical state-computation logic in a small
Python helper under `src/speckit_orca/` because artifact inspection, ambiguity
classification, and next-step inference are easier to keep deterministic there
than in command prose or shell pipelines. Keep user-facing command expectations
in contracts/docs, and wire adjacent commands to consume the shared state model
later rather than duplicating logic immediately.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Python helper for flow-state computation | Artifact parsing, stage resolution, and ambiguity reporting need deterministic behavior | Prompt-only inference would be inconsistent and hard to verify |
| Thin optional persisted state artifact | Resume/start-from and cached guidance may need durable hints | Forcing a full primary-truth registry now would create premature hidden state |

## Research Decisions

### 1. Computed-first over registry-first

Decision: derive flow state from durable artifacts first, and only persist thin
state metadata where resumability or cached guidance truly benefits.

Rationale:

- keeps artifact truth primary
- avoids early drift between runtime state and actual workflow evidence
- matches Orca's preference for small runtime surfaces

Alternatives considered:

- primary flow-state registry: easier reads, but too much hidden state too soon
- UX/statusline first: visible, but built on weak foundations

### 2. Review progress is parallel to build progress, not equivalent to it

Decision: model review milestones separately from stage/build progress.

Rationale:

- implementation completion is not the same thing as review completion
- later commands and orchestration need both signals

Alternatives considered:

- collapse review into one terminal done/not-done flag: too coarse and contrary
  to the repomix findings

### 3. Canonical stage model must include pre-spec and post-implement stages

Decision: the first version should support at least:

- brainstorm
- specify
- plan
- tasks
- assign
- implement
- code-review
- cross-review
- pr-review
- self-review

Rationale:

- this keeps the state model broad enough for the full Orca workflow
- it matches the intended future consumers

Alternatives considered:

- implement-only state: too narrow
- full yolo run-state now: too much orchestration too early

### 4. Worktree data is contextual evidence, not primary truth

Decision: worktree/lane metadata can enrich flow state, but it must not replace
feature artifact truth.

Rationale:

- lanes are execution topology, not the entire workflow story
- feature state must still be meaningful outside any one lane

Alternatives considered:

- make lane state primary: too narrow and brittle

### 5. Ambiguity is a valid output

Decision: flow state must explicitly represent ambiguous or conflicting signals.

Rationale:

- avoids false precision
- improves trust in later automation

Alternatives considered:

- force a single inferred state always: easier to display, but misleading

## Design Decisions

### 1. Define canonical state result before wiring consumers

The first implementation should define a stable `FlowStateResult` contract
before updating commands to consume it widely.

### 2. Separate evidence inventory from interpretation

The runtime should conceptually do two things:

- collect workflow evidence from artifacts
- interpret that evidence into stage, review milestones, ambiguity, and next
  step

This keeps the model inspectable and easier to evolve when review artifacts
change in `006`.

### 3. Thin persisted metadata is secondary and safely ignorable

If a persisted flow-state file exists, it should help with resume or caching,
but the system must still be able to recompute meaningful state from artifacts
alone.

### 4. `005` defines the state model, not the full status UI

Phase 3 consumer alignment must keep this feature's contracts usable by later
workflow subsystems without translation layers. This includes making the stage
vocabulary and evidence contract explicit enough that
`007-orca-context-handoffs` can consume them directly instead of defining a
parallel transition model.

This feature should stop at state-model truth and consumable outputs. Visible
statusline/dashboard rendering can follow later once the state model is stable.

## Implementation Phases

### Phase 0: State model and evidence contract

Define:

- canonical stage model
- review milestone model
- evidence inventory rules
- ambiguity categories
- next-step inference rules

### Phase 1: Deterministic state computation helper

Add a Python helper that can:

- inspect feature artifacts
- compute flow-state results
- surface ambiguity explicitly
- emit a stable machine-readable and human-readable result

### Phase 2: Thin persisted metadata boundary

Add only the minimum persisted metadata shape needed for:

- resume/start-from support later
- cached next-step guidance if justified

This phase should not create a large primary-truth registry.
The implemented boundary uses `.specify/orca/flow-state/<feature>.json` when a
repo root is available and falls back to `<feature>/.flow-state.json` only for
detached feature paths.

### Phase 3: Consumer and documentation alignment

Update docs and any immediate command touchpoints so later Orca systems have a
clear contract to consume.

## Verification Strategy

### Primary verification

Manual feature-state checks:

1. feature with only `spec.md`
2. feature with `spec.md`, `plan.md`, and no `tasks.md`
3. feature with implementation evidence but missing review evidence
4. feature with conflicting/missing artifact signals
5. feature with worktree metadata present

For each case, verify:

- current stage
- completed milestones
- incomplete milestones
- ambiguity reporting
- next-step guidance

### Secondary verification

- `uv run python -m py_compile src/speckit_orca/flow_state.py`
- direct helper smoke checks over fixture-like feature directories
- `git diff --check`
- `bash -n` for any touched shell wrappers

## Risks

### 1. Premature hidden state

If persisted metadata becomes the main truth too early, flow state will drift
from actual workflow artifacts.

Mitigation:

- keep computed-first behavior
- treat persisted metadata as secondary

### 2. Review artifact instability

`006-orca-review-artifacts` may change how review evidence is represented.

Mitigation:

- separate evidence collection from interpretation
- define review-milestone contracts at the right abstraction level

### 3. Ambiguity overload

If everything becomes "ambiguous," the model will be unusable.

Mitigation:

- distinguish recoverable partial state from true conflict
- reserve ambiguity for materially conflicting evidence

## Non-goals

- full `orca-yolo` run-state or orchestration control
- visible statusline/dashboard UX as the main output of this feature
- redesigning all review artifacts inside this feature
- making worktree metadata the primary workflow truth
