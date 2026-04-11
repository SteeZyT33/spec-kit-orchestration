# Implementation Plan: Orca YOLO

**Branch**: `009-orca-yolo` | **Date**: 2026-04-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-orca-yolo/spec.md`

## Summary

Define a downstream Orca orchestration layer that can run a feature from durable
brainstorm/spec inputs through implementation, review, and PR-ready completion.
This feature should establish:

- the end-to-end `orca-yolo` stage model
- durable run-state and outcome records
- ask/resume/start-from policy
- stop conditions and bounded retry behavior
- how `orca-yolo` consumes memory, flow state, review artifacts, context
  handoffs, and capability packs without replacing them

This feature is primarily a workflow-orchestration architecture and runtime
contract feature. It should make end-to-end execution explicit without
recentralizing the whole system into one opaque command.

## Technical Context

**Language/Version**: Markdown architecture artifacts, command docs, Bash launcher surfaces, Python 3.10+ helper/runtime concepts if deterministic run-state logic is introduced  
**Primary Dependencies**: `004-orca-workflow-system-upgrade`, `002-orca-brainstorm-memory`, `005-orca-flow-state`, `006-orca-review-artifacts`, `007-orca-context-handoffs`, `008-orca-capability-packs`, `010-orca-matriarch` (supervised-mode lane/mailbox/event-envelope contracts), current Orca command surfaces  
**Storage**: durable run-state and orchestration artifacts under `.specify/orca/` or equivalent repo-local workflow storage plus links to existing spec/review artifacts  
**Testing**: contract validation, document-level workflow checks, and later lightweight resume/start-from/runtime validation if helper code is introduced  
**Target Platform**: Orca repository workflow system and later provider-agnostic runner surfaces  
**Project Type**: orchestration architecture feature with likely thin runtime support  
**Performance Goals**: run-state resolution should be fast and deterministic relative to actual agent work; orchestration bookkeeping must stay low overhead  
**Constraints**: downstream of prior workflow primitives, provider-agnostic, bounded autonomy, explicit stop conditions, no hidden dependency invention at runtime  
**Scale/Scope**: one conservative first-version orchestration contract that can later support richer autonomy

## Constitution Check

### Pre-design gates

1. **Provider-agnostic orchestration**: pass. The workflow contract is not tied
   to a single provider and must express agent choice explicitly.
2. **Spec-driven delivery**: pass. `009` is being fully specified before
   implementation.
3. **Safe parallel work**: pass with care. `009` consumes multiple upstream
   features and therefore must keep boundaries explicit.
4. **Verification before convenience**: pass. The design favors durable state
   and explicit gates over "just keep going" automation.
5. **Small, composable runtime surfaces**: pass with emphasis. `orca-yolo`
   should orchestrate existing surfaces, not absorb them.

### Post-design check

The design remains constitution-aligned if it:

- treats upstream artifacts as authoritative
- records run state durably
- stops safely when dependencies or review gates fail
- keeps provider-specific behavior out of the orchestration contract

No constitution violations currently need justification.

## Project Structure

### Documentation (this feature)

```text
specs/009-orca-yolo/
├── spec.md
├── brainstorm.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── run-stage-model.md
│   ├── run-state.md
│   └── orchestration-policies.md
└── tasks.md
```

### Source Code (repository root)

```text
commands/
├── brainstorm.md
├── specify.md
├── plan.md
├── assign.md
├── code-review.md
├── cross-review.md
└── pr-review.md

scripts/
├── bash/
└── ...

src/
└── speckit_orca/

.specify/
└── orca/
```

**Structure Decision**: Start with a stable orchestration contract and durable
run-state model. Add thin runtime/helpers only where deterministic stage or
state handling clearly cannot remain doc-only.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New run-state layer | Resume and stop conditions require durable orchestration state | Chat-memory-only orchestration would fail the whole point of the upgrade |
| Downstream orchestration contract | Orca needs an explicit full-cycle runner | Leaving `yolo` as an implicit wrapper around existing commands would create hidden assumptions |
| Possible thin runtime helpers | Stage and resume logic may need deterministic handling | Pure prompt-driven orchestration would drift and be hard to verify |

## Research Decisions

### 1. `orca-yolo` must be downstream, not foundational

Decision: `009` consumes upstream workflow primitives rather than replacing
them.

Rationale:

- preserves the value of `002`, `005`, `006`, `007`, and `008`
- avoids recreating a monolith
- aligns with `004` implementation waves

Alternatives considered:

- build `yolo` as the main workflow engine from the start: too much hidden logic
- treat `yolo` as a prompt-only alias: too weak and not resumable

### 2. The first version should favor bounded autonomy

Decision: define explicit stops, resume behavior, and conservative retry
semantics before richer autonomous fix loops.

Rationale:

- better safety
- easier reviewability
- less chance of building a runaway pipeline

Alternatives considered:

- full autonomous fix loops immediately: too risky and hard to verify

### 3. Run state must be durable and inspectable

Decision: `orca-yolo` needs a durable run record with stage, policy, artifact
links, and outcome.

Rationale:

- resume depends on it
- users need inspectability
- downstream PR readiness depends on explicit outcomes

Alternatives considered:

- infer everything from branch state and files each time: too ambiguous

### 4. PR creation should be explicit policy, not mandatory behavior

Decision: the first version should support PR-ready completion and optionally PR
creation when policy allows it.

Rationale:

- not every run should publish a PR
- keeps the workflow safer and more inspectable

Alternatives considered:

- always create a PR: too forceful
- never include PR concerns: underdelivers on the full-cycle promise

## Design Decisions

### 1. `orca-yolo` stage model should align with existing workflow vocabulary

The orchestration stages should mirror current Orca workflow language:

- brainstorm
- specify
- plan
- tasks
- implement
- self-review
- code-review
- cross-review
- pr-ready or pr-create

### 2. Ask policy and stop policy are part of the run contract

Each run must express:

- ask level
- retry behavior
- start mode
- worktree expectations
- PR completion policy

### 3. Run outcomes must be explicit

The first version should distinguish at minimum:

- completed
- paused
- blocked
- failed
- canceled

## Implementation Phases

### Phase 0: Orchestration contract and run-state design

Define:

- run stages
- run-state shape
- policy surface

### Phase 1: Stage transitions and resume model

Define:

- how a run starts
- how it resumes
- what stops it
- what artifacts it must link

### Phase 2: Upgrade-program and downstream alignment

Define:

- how `009` depends on `004` through `008`
- whether `yolo` is represented as a downstream capability pack
- what PR-ready completion means for later implementation

## Verification Strategy

### Primary verification

1. define a realistic end-to-end run from brainstorm/spec to PR-ready completion
2. verify each stage consumes durable upstream artifacts rather than chat memory
3. verify resume/start-from behavior is explicit and inspectable
4. verify stop conditions are conservative and bounded

### Secondary verification

1. verify `009` does not redefine stage/state/review primitives already owned by
   `005`, `006`, or `007`
2. verify orchestration policy stays provider-agnostic
3. verify PR creation remains an explicit policy choice

## Resolved Questions

The three original open questions were resolved during the post-`010`
tightening pass:

- **PR creation default**: the first version defaults to `pr-ready` (stop at a
  PR-ready branch state). `pr-create` requires explicit opt-in per
  `contracts/orchestration-policies.md`.
- **Bounded retry shape**: retry behavior is policy-shaped with a documented
  numeric default of **2 attempts** per fix-loop stage before stopping with an
  explicit blocker. Runtime configuration can override the default, but MUST
  remain bounded.
- **Minimum run-state shape**: defined in `contracts/run-state.md` —
  `run id`, anchor artifact, current stage, outcome, ask/retry/worktree
  policies, supervision mode, deployment kind, linked artifact paths, stop
  reason, and (in supervised mode) `lane_id`, `mailbox_path`, and last
  emitted upward report reference.

## Open Questions

- Whether `009` should eventually publish a capability-pack manifest under
  `008-orca-capability-packs` once its runtime surface stabilizes, or remain
  a standalone orchestration contract. Deferred to a later wave.
