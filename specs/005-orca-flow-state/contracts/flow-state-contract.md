# Contract: Flow State Result

## Purpose

Define the stable output Orca should provide when computing feature workflow
state.

## Required Result Fields

- feature identifier
- current stage, when determinable
- completed milestones
- incomplete milestones
- review milestones
- ambiguity notes
- next-step hint, when responsibly inferable
- evidence summary

## Output Shape

The current runtime returns:

- `feature_id`: feature directory name
- `current_stage`: highest completed canonical stage, or `null`
- `completed_milestones`: flow milestones with `stage`, `status`, `evidence_sources`, and optional `notes`
- `incomplete_milestones`: the remaining canonical stage milestones
- `review_milestones`: review milestones with `review_type`, `status`, `evidence_sources`, and optional `notes`
- `ambiguities`: explicit conflicts or missing-predecessor notes
- `next_step`: the next responsible command or artifact action, or `null`
- `evidence_summary`: compact artifact, task, review, lane, and resume-metadata notes

## Behavioral Rules

- artifact truth is primary
- ambiguity is allowed and must be surfaced explicitly
- review progress is separate from implementation progress
- worktree/lane metadata is contextual only
- resume metadata is advisory and must never override recomputed artifact truth

## Consumer Expectation

Later Orca systems should be able to consume this result without redefining the
stage model or inventing hidden assumptions.
