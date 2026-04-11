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
- mailbox events MUST use the shared envelope in
  [event-envelope.md](./event-envelope.md)
- tmux nudges may prompt a re-check, but they MUST NOT be the canonical message
  delivery mechanism
- every launched lane agent MUST emit a deterministic startup acknowledgment
  before beginning substantive work. Absence of a startup ACK MUST be treated
  as `unknown`, never as `healthy`
- messages remain inspectable until explicitly archived per the Archival
  Model in [event-envelope.md](./event-envelope.md)
- mailbox operations should be safe under concurrent readers/writers

## Lane ID Constraints

- `lane_id` MUST be filesystem-safe. Validators MUST enforce a full-string
  match against the anchored pattern `^[A-Za-z0-9._-]+$` — partial-match
  validators (e.g. Python's default `re.search`) MUST NOT be used to
  validate `lane_id`, so mailbox and report queue paths remain deterministic
  across operators and shells
- v1 defaults `lane_id` to the primary `spec_id` per spec FR-025, which
  already satisfies this constraint for standard Orca spec naming

## Recommended V1 Shape

- `.specify/orca/matriarch/mailbox/<lane-id>/`
- append-only `inbound.jsonl` and `outbound.jsonl` files using the shared event
  envelope
- short deterministic ACK messages for startup and instruction receipt
- archival is performed in the append-only log (see
  [event-envelope.md](./event-envelope.md) Archival Model), not by moving
  events to a separate file

## Mailbox vs Reports

- **Mailbox** (`mailbox/<lane-id>/`) carries bidirectional lane-local messaging:
  instructions from Matriarch, acknowledgments and questions from the lane
  agent. Used for coordination and approval traffic.
- **Reports** (`reports/<lane-id>/`, see
  [tmux-deployment.md](./tmux-deployment.md) Report-Back Protocol) carries
  unidirectional status events from the lane agent to Matriarch. Used for
  progress and health.
- Both use the shared event envelope. The distinction is directional intent,
  not event format.

## Non-Goals

- recreating OMX mailbox paths or CLI contracts
- requiring tmux for message visibility
- opaque realtime-only transport
- defining a separate archive file; archival happens in the append-only log
