# Data Model: Orca Matriarch

## Managed Lane

Represents one supervised feature/spec lane.

Fields:

- `lane_id`: canonical lane identifier
- `spec_id`: linked feature spec id when available
- `title`: human-readable lane label
- `branch`: branch name for the lane
- `worktree_path`: optional attached worktree path
- `owner_type`: `human` | `agent` | `shared` | `unassigned`
- `owner_id`: optional owner identifier
- `stage`: derived workflow stage from `005`
- `readiness`: derived lane readiness summary
- `dependency_ids`: declared upstream lane ids
- `status`: `active` | `blocked` | `paused` | `review_ready` | `pr_ready` | `archived`
- `created_at`
- `updated_at`

## Lane Dependency

Represents one lane-to-lane relationship.

Fields:

- `lane_id`
- `depends_on_lane_id`
- `strength`: `soft` | `hard`
- `state`: `active` | `satisfied` | `waived`
- `rationale`

## Lane Assignment

Represents ownership of a lane.

Fields:

- `lane_id`
- `owner_type`
- `owner_id`
- `assigned_at`
- `notes`

## Checkout Target

Represents the best current place to continue work for a lane.

Fields:

- `lane_id`
- `target_kind`: `worktree` | `branch` | `repo`
- `target_ref`: worktree path or branch name
- `resolved_from`: `registry` | `worktree_metadata` | `git_state`
- `drift_flags`: zero or more warnings when registry and live state differ

## Hook Event

Represents one lane lifecycle event that may trigger transparent automation.

Fields:

- `event_name`
- `lane_id`
- `hook_name`
- `result`
- `recorded_at`
- `notes`
