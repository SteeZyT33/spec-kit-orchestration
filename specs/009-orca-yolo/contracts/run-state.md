# Contract: Yolo Run State

## Purpose

Define the minimum durable state `orca-yolo` needs to support resume, stop, and
final outcome reporting.

## Required Fields

- run id
- anchor artifact or feature reference
- current stage
- current outcome
- ask policy
- retry policy
- worktree policy
- supervision mode (`standalone` | `matriarch-supervised`)
- deployment kind (`standalone` | `direct-session` | `tmux`)
- linked artifact paths
- stop reason when not actively progressing

## Supervised-Mode Fields

Required only when `supervision mode` is `matriarch-supervised`:

- `lane_id` matching matriarch lane identity (defaults to primary `spec_id`
  per `010-orca-matriarch` spec FR-025)
- `mailbox_path` pointing at the lane mailbox owned by matriarch (see
  `specs/010-orca-matriarch/contracts/lane-mailbox.md`)
- last emitted upward report reference when yolo has reported a blocker,
  question, or approval need via the Lane Mailbox

## Behavior

- Run state must be durable enough to support resume after session loss.
- Run state must prefer explicit artifact links over reconstructing context from
  chat history.
- Final run state must expose whether the run completed, paused, blocked,
  failed, or was canceled.
- Supervision mode and deployment kind MUST be explicit in run state, not
  inferred at runtime.
- In supervised mode, run state MUST reference matriarch's lane and mailbox
  contracts rather than duplicating lane coordination state inside `009`.
