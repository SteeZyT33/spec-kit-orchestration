# Contract: Run Stage Model

## Purpose

Define the minimum stage vocabulary `orca-yolo` uses for full-cycle workflow
execution, and the durable upstream contracts each stage consumes or emits.

## Required Stages

Each stage names its corresponding flow-state transition (005), its review
or handoff artifact (012/007), and any upward report expected in supervised
mode.

### Happy-path stage sequence

```text
brainstorm → specify → clarify → review-spec
           → plan → tasks → assign (optional) → implement
           → review-code (phase-level + overall)
           → pr-ready [→ pr-create]
           → review-pr (after merge)
```

### Stage definitions

- **brainstorm**
  - flow state: advances to `brainstormed`
  - emits: brainstorm memory artifact consumed by later stages
  - handoff (007): brainstorm → specify
- **specify**
  - flow state: advances to `specified`
  - emits: spec.md
  - handoff (007): specify → clarify
- **clarify**
  - flow state: advances to `clarified`
  - emits: `## Clarifications` section in spec.md per `012` clarify-integration contract
  - gate: mandatory before review-spec — spec-kit's `/speckit.clarify`
  - handoff (007): clarify → review-spec
- **review-spec** (012 cross-only)
  - flow state: advances to `spec-reviewed`
  - emits: `012` review-spec.md artifact (cross-pass only, adversarial)
  - gate: must pass or be stale-cleared before advancing to plan
  - handoff (007): review-spec → plan
- **plan**
  - flow state: advances to `planned`
  - emits: plan.md
  - handoff (007): plan → tasks
- **tasks**
  - flow state: advances to `tasks-ready`
  - emits: tasks.md
  - handoff (007): tasks → assign
- **assign** (optional)
  - flow state: advances to `assigned` if agents are assigned
  - emits: assignment metadata in tasks.md
  - handoff (007): assign → implement
- **implement**
  - flow state: advances to `implementing` then `implemented`
  - emits: code changes; updates linked artifact paths in run state
  - handoff (007): implement → review-code
- **review-code** (012 self+cross per phase)
  - flow state: advances to `code-reviewed`
  - emits: `012` review-code.md artifact (self-pass then cross-pass
    per user-story phase, append-only across rounds)
  - gate: overall verdict must be `ready-for-pr` before advancing
- **pr-ready**
  - flow state: advances to `pr-ready`
  - emits: branch state suitable for PR creation
  - default terminal point unless `pr-create` is opted in

### Optional Stages

- **pr-create** (requires explicit opt-in per Orchestration Policies)
  - flow state: advances to `pr-published`
  - emits: PR identifier recorded in run state
- **review-pr** (012 narrow, runs after PR exists)
  - flow state: advances to `pr-reviewed`
  - emits: `012` review-pr.md artifact (PR comment disposition +
    required retro note)
  - gate: processes external reviewer comments post-merge

## Valid Start Artifacts

`orca-yolo` accepts the following as run start anchors:

- Durable brainstorm record (`.specify/orca/brainstorms/`)
- Feature spec directory (`specs/NNN-feature-name/`)
- Spec-lite record (`.specify/orca/spec-lite/SL-NNN-*.md`) — **excluded in v1**, reserved for future support

The following are **never** valid yolo start artifacts:

- Adoption records (`AR-NNN-*.md`) — reference-only, never drivable per 015 contract
- Chat history or session transcripts

## Behavior

- Stages must align with existing Orca workflow language where possible.
- `orca-yolo` must not skip required prerequisite stages unless the user starts
  from a later stage with the needed durable artifacts already present.
- Every stage transition must be inspectable through durable run state.
- Stage transitions MUST write into `005-orca-flow-state` and MUST link to
  `012-review-model` outputs rather than maintaining parallel
  stage or review records inside yolo run state.
- Stage-to-stage context MUST use `007-orca-context-handoffs` rather than
  implicit session-carried state.
- In matriarch-supervised mode, stage advancement MUST be observable via
  the Lane Mailbox event envelope so matriarch can track progress without
  inspecting `009`'s internal run state.
