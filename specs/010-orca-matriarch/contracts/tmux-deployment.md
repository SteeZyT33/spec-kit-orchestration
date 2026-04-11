# Contract: Tmux Deployment

## Purpose

Define the optional tmux-backed deployment model for supervised lanes.

## V1 Scope

- one optional tmux session per lane
- explicit launch, inspect, attach, and mark-missing behavior
- deployment state tracked separately from workflow readiness
- one primary execution agent per deployed lane session
- compatibility with non-tmux interactive workers through a separate
  `direct-session` deployment type, specified in
  [direct-session-deployment.md](./direct-session-deployment.md)

## Requirements

- tmux deployment is optional, not mandatory
- Matriarch must not assume a running tmux session means the lane is healthy or
  complete
- missing or dead sessions must be surfaced explicitly
- session naming must be deterministic enough to reconnect safely
- deployment commands must be explicit; Matriarch must not launch or attach
  silently
- deployment ownership must be visible so reassignment does not leave a ghost
  session that looks authoritative
- reassignment must not silently steal, kill, or rebind an existing tmux
  session without explicit operator intent
- a lane may be reassigned while a previous deployment record remains
  inspectable; deployment history and current ownership must stay distinct

## Recommended Session Metadata

- lane id
- session name
- launch timestamp
- owner/launcher
- last observed state
- current ownership match or mismatch flag

## Reassignment Rules

- when lane ownership changes, Matriarch must surface whether the existing tmux
  deployment still belongs to the old owner
- the system may recommend detach, retire, or replace actions, but must not
  perform them implicitly
- a deployment in mismatch state must not be presented as the canonical active
  execution context without warning

## Reporting Rules

- a lane agent launched by Matriarch MUST treat Matriarch as its coordination
  authority
- blockers, questions, and approval needs MUST be reported back to Matriarch
  first
- Matriarch may then decide whether to answer from current context, block the
  lane, or escalate the question to the user
- the deployment model MUST NOT assume lane agents are free to bypass the
  supervisory layer by default

## Report-Back Protocol

V1 should use a file-backed report-back protocol under an Orca-owned runtime
directory, for example:

- `.specify/orca/matriarch/reports/<lane-id>/`

Each report event should be an append-only structured record containing at
minimum:

- the shared fields from [event-envelope.md](./event-envelope.md)
- `deployment_id`
- `context_refs`: optional links to artifacts or files

Protocol rules:

- lane agents write reports; Matriarch reads and reconciles them
- Matriarch remains the authority that decides whether a report changes lane
  lifecycle or needs user escalation
- report records must be durable enough to survive tmux detach or session loss
- missing reports must not be treated as proof of health
- tmux transport details must not replace the durable report queue as the
  source of truth

## Non-Goals

- general tmux fleet management
- arbitrary pane choreography
- replacing existing team/worker orchestration systems wholesale
