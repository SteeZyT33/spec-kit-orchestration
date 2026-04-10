# Contract: Delegated Work

## Purpose

Define the claim-safe lifecycle for discrete units of lane-local delegated work.

## Required Properties

- one worker may hold a claim at a time
- lifecycle transitions are durable and auditable
- failed work is distinguishable from released or unstarted work
- claim identity is explicit enough to prevent stale completion writes

## V1 Lifecycle

- `pending`
- `in_progress`
- `completed`
- `failed`

Allowed supporting action:

- release claim back to `pending`

## V1 Rules

- delegated work must be claimed before execution begins
- claim identity should be explicit, for example
  `<lane_id>:<task_id>:<claimer_id>:<claimed_at_epoch>`
- completion or failure writes must validate the active claim identity
- released work returns to `pending` with durable release context
- workers must not directly mutate unrelated delegated-work items
- delegated-work records should remain lane-local unless a future higher-level
  program layer is introduced

## Non-Goals

- recreating OMX task file layout
- cross-lane scheduling logic
- replacing lane ownership with a fine-grained swarm controller
