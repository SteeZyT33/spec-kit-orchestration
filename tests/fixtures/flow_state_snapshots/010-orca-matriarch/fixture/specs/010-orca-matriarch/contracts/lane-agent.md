# Contract: Lane Agent

## Purpose

Define the normative role, authority model, and reporting obligations of a
**Lane Agent** — the execution worker attached to one matriarch-supervised
lane. `Lane Agent` is the Key Entity named in spec FR-020 and the Key
Entities list; until this contract existed, its rules lived scattered
across `tmux-deployment.md`, `lane-mailbox.md`, `event-envelope.md`,
`lane-registry.md`, and `matriarch-command-surface.md`. This file is the
single normative summary those sources now resolve to. It does **not**
duplicate or replace the individual contracts — it references them.

Downstream specs (notably `009-orca-yolo` FR-013) reference "Lane Agent" as
a named contract. Prior to this file, that reference was a vocabulary gap:
the Key Entity was defined but had no normative rule document. This
contract closes that gap without relocating any rules.

## Identity

A Lane Agent is the execution worker that holds one matriarch lane while
it advances through the workflow. In v1, lanes default to one primary
spec per spec FR-001a and FR-025, so a Lane Agent is always bound to
exactly one primary spec at a time.

A Lane Agent is distinct from its deployment substrate:

- a Lane Agent may run **inside a tmux session** per
  [tmux-deployment.md](./tmux-deployment.md)
- a Lane Agent may run as a **direct-session interactive CLI** per
  [direct-session-deployment.md](./direct-session-deployment.md)
- a Lane Agent may be a **launched worker** (Matriarch-initiated) or an
  **operator-owned CLI** (registered by the operator via startup ACK)

In the event envelope (see [event-envelope.md](./event-envelope.md)), a
Lane Agent identifies itself using the tagged sender format
`lane_agent:<lane_id>`.

## Authority Model

Matriarch is the supervisory authority for every lane under its
management. A Lane Agent operates **inside** that authority, not in
parallel to it.

- Matriarch is the coordination authority for all launched lane agents
  per [matriarch-command-surface.md](./matriarch-command-surface.md) and
  [tmux-deployment.md](./tmux-deployment.md) Reporting Rules.
- A Lane Agent MUST treat Matriarch as its coordination authority. It
  MUST NOT prompt the user directly for clarification, approval, or
  resolution when a supervised channel is available.
- A Lane Agent MUST NOT advance or retire its lane without surfacing the
  advancement through the durable report or mailbox channel, so
  Matriarch can reconcile lane state against authoritative evidence
  rather than chat memory.
- Matriarch, not the Lane Agent, authoritatively sets lane lifecycle
  state. Per [lane-registry.md](./lane-registry.md), a Lane Agent may
  **report** readiness signals but does not **set** `active` →
  `review_ready` directly.

## Required Obligations

Every Lane Agent — tmux-backed, direct-session, or otherwise — MUST
satisfy the following obligations. None of these are new rules; they are
the already-binding rules from the individual contracts, gathered here
so downstream callers can reference them in one place.

### Startup Acknowledgment

A Lane Agent MUST emit a deterministic startup acknowledgment event via
the Lane Mailbox before beginning substantive lane-local work, per
[lane-mailbox.md](./lane-mailbox.md) V1 Rules. Absence of a startup ACK
MUST be treated as `unknown`, never as `healthy`.

### Upward Reporting

A Lane Agent MUST report blockers, questions, approval needs, and stop
reasons upward via the Lane Mailbox or the lane report queue, using the
shared envelope in [event-envelope.md](./event-envelope.md). Upward
reporting obligations are normatively defined in:

- [tmux-deployment.md](./tmux-deployment.md) Reporting Rules and
  Report-Back Protocol
- [direct-session-deployment.md](./direct-session-deployment.md)
  Requirements
- [lane-mailbox.md](./lane-mailbox.md) Mailbox vs Reports

Matriarch then decides whether to answer from current context, block
the lane, or escalate to the user.

### Event Emission Shape

All events emitted by a Lane Agent MUST use the shared envelope in
[event-envelope.md](./event-envelope.md), including:

- tagged `sender` in the form `lane_agent:<lane_id>`
- absolute-path anchored `lane_id` matching `^[A-Za-z0-9._-]+$`
- UTC timestamps (`Z` offset)
- `references` field populated on events of type `ack`, `resolved`, or
  `archived`

A Lane Agent MUST be able to emit valid events from a plain POSIX shell
without requiring a Python SDK, matching the event-envelope V1 Rules.

### Claim-Safe Sub-Work

If a Lane Agent internally delegates discrete units of lane-local work
(e.g. to sub-agents or parallel workers), that delegation MUST use the
claim-safe lifecycle defined by [delegated-work.md](./delegated-work.md)
per spec FR-022. A Lane Agent MUST NOT hand out ad-hoc ownership that
cannot be reconciled from durable state.

## Authority Relative to Deployments

When a Lane Agent's deployment state and the Lane Registry disagree —
for example, an existing tmux session whose ownership flag has
mis-matched after reassignment — the Lane Agent MUST NOT act as the
canonical owner until Matriarch reconciles the mismatch. Per spec
FR-018, ownership mismatches are surfaced explicitly and MUST NOT be
treated as authoritative without operator confirmation.

A Lane Agent launched after a reassignment MUST consult matriarch's
lane registry state before acting on its local run state alone, so
stale local assumptions cannot override reconciled authority.

## Non-Goals

- This contract does not define launch semantics for a Lane Agent. That
  is owned by the deployment contracts
  ([tmux-deployment.md](./tmux-deployment.md),
  [direct-session-deployment.md](./direct-session-deployment.md)).
- This contract does not define the Lane Mailbox storage layout. That is
  owned by [lane-mailbox.md](./lane-mailbox.md).
- This contract does not define the event envelope shape. That is owned
  by [event-envelope.md](./event-envelope.md).
- This contract does not define lane lifecycle state transitions. Those
  are owned by [lane-registry.md](./lane-registry.md).
- This contract does not prescribe any provider-specific behavior. Per
  spec FR-010, Lane Agents must remain provider-agnostic; the execution
  worker may be any of Claude Code, Codex, Cursor, Gemini, or any future
  provider, and the rules above apply uniformly.
