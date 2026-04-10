# Contract: Lane Mailbox

## Purpose

Define the durable message and acknowledgment channel between Matriarch and
lane-local workers or agents.

## Required Properties

- state-first and durable
- readable without attaching to tmux
- explicit sender and recipient identity
- visible acknowledgment state
- safe to use for instructions, status, questions, and shutdown notices

## V1 Rules

- the mailbox or report queue is the source of truth for lane-local messaging
- mailbox events must use the shared envelope in
  [event-envelope.md](./event-envelope.md)
- tmux nudges may prompt a re-check, but they must not be the canonical message
  delivery mechanism
- every launched lane agent should emit a deterministic startup acknowledgment
  before beginning substantive work
- messages should remain inspectable until explicitly acknowledged or archived
- mailbox operations should be safe under concurrent readers/writers

## Recommended V1 Shape

- `.specify/orca/matriarch/mailbox/<lane-id>/`
- append-only `inbound.jsonl` and `outbound.jsonl` files using the shared event
  envelope
- short deterministic ACK messages for startup and instruction receipt

## Non-Goals

- recreating OMX mailbox paths or CLI contracts
- requiring tmux for message visibility
- opaque realtime-only transport
