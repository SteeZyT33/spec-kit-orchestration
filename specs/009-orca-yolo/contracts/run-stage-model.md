# Contract: Run Stage Model

## Purpose

Define the minimum stage vocabulary `orca-yolo` uses for full-cycle workflow
execution, and the durable upstream contracts each stage consumes or emits.

## Required Stages

Each stage names its corresponding flow-state transition (005), its review
or handoff artifact (006/007), and any upward report expected in supervised
mode.

- **brainstorm**
  - flow state: advances to `brainstormed`
  - emits: brainstorm memory artifact consumed by later stages
  - handoff (007): brainstorm → specify
- **specify**
  - flow state: advances to `specified`
  - emits: spec.md; review artifact from `006` spec-review when enabled
  - handoff (007): specify → plan
- **plan**
  - flow state: advances to `planned`
  - emits: plan.md; `006` plan-review artifact when enabled
  - handoff (007): plan → tasks
- **tasks**
  - flow state: advances to `tasks-ready`
  - emits: tasks.md
  - handoff (007): tasks → implement
- **implement**
  - flow state: advances to `implementing` then `implemented`
  - emits: code changes; updates linked artifact paths in run state
  - handoff (007): implement → self-review
- **self-review**
  - flow state: advances to `self-reviewed`
  - emits: `006` self-review artifact
  - gate: must pass or record blocker before advancing
- **code-review**
  - flow state: advances to `code-reviewed`
  - emits: `006` code-review artifact
  - gate: must pass or record blocker before advancing
- **cross-review**
  - flow state: advances to `cross-reviewed`
  - emits: `006` cross-review artifact
  - gate: must pass or record blocker before advancing
- **pr-ready**
  - flow state: advances to `pr-ready`
  - emits: final run summary linked to all prior durable artifacts

## Optional Final Stage

- **pr-create**
  - flow state: advances to `pr-published`
  - requires explicit opt-in per Orchestration Policies
  - emits: PR identifier recorded in run state

## Behavior

- Stages must align with existing Orca workflow language where possible.
- `orca-yolo` must not skip required prerequisite stages unless the user starts
  from a later stage with the needed durable artifacts already present.
- Every stage transition must be inspectable through durable run state.
- Stage transitions MUST write into `005-orca-flow-state` and MUST link to
  `006-orca-review-artifacts` outputs rather than maintaining parallel
  stage or review records inside yolo run state.
- Stage-to-stage context MUST use `007-orca-context-handoffs` rather than
  implicit session-carried state.
- In matriarch-supervised mode, stage advancement MUST be observable via
  the Lane Mailbox event envelope so matriarch can track progress without
  inspecting `009`'s internal run state.
