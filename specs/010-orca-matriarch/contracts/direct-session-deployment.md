# Contract: Direct-Session Deployment

## Purpose

Define the non-tmux interactive execution mode for supervised lanes. A
direct-session deployment represents a single interactive worker CLI — such as
Claude Code, Codex, Cursor, or Gemini — holding a lane without running inside
a tmux session.

This is the non-tmux companion to [tmux-deployment.md](./tmux-deployment.md).
`direct-session` is the deployment kind named in spec FR-026.

## V1 Scope

- one interactive worker CLI per deployed lane
- explicit worker registration before substantive work
- deployment state tracked separately from workflow readiness
- reuse of the Lane Mailbox and report-back protocol owned by
  [lane-mailbox.md](./lane-mailbox.md) and [tmux-deployment.md](./tmux-deployment.md)

## Requirements

- direct-session deployment is an explicit deployment kind in the lane model,
  not an inferred fallback when tmux is absent
- the worker MUST register itself with Matriarch by emitting a startup
  acknowledgment event (see [lane-mailbox.md](./lane-mailbox.md) and
  [event-envelope.md](./event-envelope.md)) before beginning lane-local work
- absence of a registration event MUST NOT be treated as evidence of an active
  direct-session deployment
- a lane with a direct-session deployment MUST expose the worker kind
  explicitly (e.g. `claude-code`, `codex`, `cursor-agent`, `gemini`) so
  operators can distinguish deployments at a glance
- direct-session workers MUST report blockers, questions, and approval needs
  via the Lane Mailbox rather than prompting the user directly, matching the
  reporting rules in [tmux-deployment.md](./tmux-deployment.md)
- reassignment MUST NOT silently steal or rebind an existing direct-session
  deployment; ownership changes MUST be surfaced through the same mismatch
  flag used for tmux deployments
- Matriarch MUST NOT launch a direct-session worker implicitly; the operator
  starts the interactive CLI, and the CLI registers itself

## Recommended Deployment Metadata

- lane id
- deployment kind (`direct-session`)
- worker kind (e.g. `claude-code`, `codex`, `cursor-agent`, `gemini`)
- launch timestamp
- last observed registration event id
- owner/launcher
- current ownership match or mismatch flag

## Health Signals

Unlike tmux deployments, direct-session deployments have no process Matriarch
can inspect directly. Health is derived from durable evidence only:

- presence of a recent registration event in the Lane Mailbox
- presence of recent report events in the lane report queue
- absence of an unresolved `blocker` event
- absence of a `shutdown` event since the last registration

Missing signals MUST NOT be interpreted as health. A direct-session deployment
with no recent events is `unknown`, not `healthy`.

## Reassignment Rules

- when lane ownership changes, Matriarch MUST surface whether the existing
  direct-session deployment still belongs to the old owner, using the same
  mismatch flag as tmux-deployment.md
- the system MAY recommend retire or replace actions, but MUST NOT perform
  them implicitly — Matriarch has no guaranteed process-control handle on
  the interactive CLI holding the lane, so automatic termination is never
  assumed
- a deployment in mismatch state MUST NOT be presented as the canonical
  active execution context without an explicit warning

## Non-Goals

- supervising multiple interactive workers in one lane
- replacing tmux deployment for workers that prefer tmux
- automating launch of interactive CLIs — launch is explicit operator action
- inferring deployment kind from environment or CLI wiring
