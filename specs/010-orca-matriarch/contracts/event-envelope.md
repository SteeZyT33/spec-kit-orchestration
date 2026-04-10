# Contract: Event Envelope

## Purpose

Define one durable event shape shared by lane mailbox messages and lane report
events.

## V1 Format

- JSON Lines (`.jsonl`)
- one event per line
- file append order is canonical event order

## Required Fields

- `id`: unique event id within the lane
- `timestamp`: RFC3339 creation time
- `lane_id`
- `sender`
- `recipient`
- `type`: `instruction` | `ack` | `status` | `blocker` | `question` | `approval_needed` | `handoff` | `shutdown`
- `payload`: string or structured object
- `ack_status`: `new` | `acknowledged` | `resolved`

## V1 Rules

- mailbox and report queues must use this same envelope
- worker CLIs must be able to emit valid events with simple shell writes
- no Python SDK is required for event emission
- event ids must be deterministic enough to avoid collision within one lane
- append-only writes are preferred; later acknowledgment or resolution should be
  recorded as a new event or explicit state update rather than destructive
  rewrite when possible

## Recommended Paths

- `.specify/orca/matriarch/mailbox/<lane-id>/inbound.jsonl`
- `.specify/orca/matriarch/mailbox/<lane-id>/outbound.jsonl`
- `.specify/orca/matriarch/reports/<lane-id>/events.jsonl`
