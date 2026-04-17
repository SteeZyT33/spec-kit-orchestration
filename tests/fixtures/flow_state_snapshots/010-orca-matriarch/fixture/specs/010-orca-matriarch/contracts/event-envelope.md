# Contract: Event Envelope

## Purpose

Define one durable event shape shared by lane mailbox messages and lane report
events.

## V1 Format

- JSON Lines (`.jsonl`)
- one event per line
- file append order is canonical event order

## Required Fields

- `id`: unique event id within the lane (see construction rules below)
- `timestamp`: RFC3339 creation time in UTC (`Z` offset)
- `lane_id`: filesystem-safe lane identifier; validators MUST enforce a
  full-string match against the anchored pattern `^[A-Za-z0-9._-]+$`
- `sender`: tagged identity string, format `<role>` or `<role>:<identity>`
  (e.g. `matriarch`, `lane_agent:009-orca-yolo`, `user`)
- `recipient`: tagged identity string using the same format as `sender`
- `type`: `instruction` | `ack` | `status` | `blocker` | `question` | `approval_needed` | `handoff` | `shutdown` | `archived` | `resolved`
- `payload`: string or structured object
- `ack_status`: `new` | `acknowledged` | `resolved` — emission-time snapshot
  only (see Acknowledgment Model below)
- `references`: optional list of prior event ids this event responds to or
  supersedes. Required on events of type `ack`, `resolved`, and `archived`,
  which MUST carry at least one referenced id

## V1 Rules

- mailbox and report queues must use this same envelope
- worker CLIs must be able to emit valid events with simple shell writes
- no Python SDK is required for event emission
- append-only writes are preferred; later acknowledgment, resolution, or
  archival must be recorded as a new event referencing the original event id
  via the `references` field rather than as a destructive rewrite
- timestamps MUST use UTC (`Z` offset) so multi-writer ordering remains
  comparable without timezone reconciliation

## ID Construction

Event ids MUST be unique within the lane's event stream. V1 recommended
construction is shell-friendly and collision-resistant:

```
<UTC timestamp to millisecond>-<sender>-<short random>
```

For example: `20260410T183045123Z-lane_agent-a3f1`. The short random component
MUST be at least 4 hex characters drawn from `/dev/urandom` or an equivalent
entropy source. Implementations MAY substitute `uuidgen` output when
available. The construction MUST remain writable from a POSIX shell without
calling into Python.

## Acknowledgment Model

`ack_status` on an event is the **emission-time snapshot only**. An event
emitted with `ack_status: new` retains that field value forever in the
append-only log. The *current* acknowledgment state of an event is derived
by scanning the lane's event stream for later events of type `ack` or
`resolved` whose `references` field contains the original event id.

Readers MUST NOT mutate the `ack_status` field in place. Readers that need
the current state MUST scan for referencing events.

## Archival Model

Archival is performed by emitting a new event of `type: archived` whose
`references` field lists the event ids being archived. Archived events
remain physically present in the append-only log — "archived" is a state
projection, not a deletion. Implementations MAY filter archived events from
default views but MUST preserve them on disk.

## Recommended Paths

- `.specify/orca/matriarch/mailbox/<lane-id>/inbound.jsonl`
- `.specify/orca/matriarch/mailbox/<lane-id>/outbound.jsonl`
- `.specify/orca/matriarch/reports/<lane-id>/events.jsonl`
