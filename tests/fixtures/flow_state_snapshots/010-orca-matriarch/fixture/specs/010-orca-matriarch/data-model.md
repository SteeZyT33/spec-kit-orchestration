# Data Model: Orca Matriarch

## Managed Lane

Represents one supervised feature/spec lane.

Fields:

- `lane_id`: canonical lane identifier
- `spec_id`: linked primary feature spec id, equal to `lane_id` in v1
- `title`: human-readable lane label
- `branch`: branch name for the lane
- `worktree_path`: optional attached worktree path
- `registry_revision`: monotonic revision or write token for stale-write detection
- `lifecycle_state`: `registered` | `active` | `blocked` | `review_ready` | `pr_ready` | `archived`
- `owner_type`: `human` | `agent` | `shared` | `unassigned`
- `owner_id`: optional owner identifier
- `stage`: derived workflow stage from `005`
- `readiness`: derived lane readiness summary
- `dependency_ids`: declared upstream lane ids
- `deployment_id`: optional linked deployment attachment
- `mailbox_path`: canonical lane mailbox root for worker discovery
- `status_reason`: operator-facing explanation for current lifecycle state
- `created_at`
- `updated_at`

## Lane Dependency

Represents one lane-to-lane relationship.

Fields:

- `lane_id`
- `depends_on_lane_id`
- `strength`: `soft` | `hard`
- `target_kind`: `lane_exists` | `stage_reached` | `review_ready` | `pr_ready` | `merged`
- `target_value`: optional required stage or readiness target
- `state`: `active` | `satisfied` | `waived`
- `rationale`

## Lane Assignment

Represents ownership of a lane.

Fields:

- `lane_id`
- `owner_type`
- `owner_id`
- `assigned_at`
- `released_at`: optional end timestamp when reassigned or released
- `assignment_state`: `active` | `released` | `abandoned`
- `notes`

## Checkout Target

Represents the best current place to continue work for a lane.

Fields:

- `lane_id`
- `target_kind`: `worktree` | `branch` | `repo`
- `target_ref`: worktree path or branch name
- `resolved_from`: `registry` | `worktree_metadata` | `git_state`
- `drift_flags`: zero or more warnings when registry and live state differ
- `exec_required`: `true` when mutation would be required to reach the target

## Lane Deployment

Represents the optional execution substrate attached to a lane.

Fields:

- `deployment_id`
- `lane_id`
- `deployment_kind`: `tmux` | `direct-session`
- `session_name`
- `state`: `requested` | `running` | `detached` | `missing` | `stopped`
- `launched_by`
- `attached_at`
- `last_seen_at`
- `worker_cli`: optional runtime identity such as `codex` or `claude`
- `notes`
- `reports_to`: `matriarch`

## Lane Report Event

Represents an append-only report emitted by a launched lane agent back to
Matriarch.

Fields:

- `report_id`
- `lane_id`
- `deployment_id`: optional when no tmux deployment is attached
- `event_type`: `status` | `blocker` | `question` | `approval_needed` | `handoff`
- `message`
- `reported_by`
- `created_at`
- `context_refs`: zero or more artifact or file references
- `handled_at`: optional timestamp once Matriarch reconciles the event
- `resolution_state`: `new` | `acknowledged` | `escalated` | `resolved`

## Lane Mailbox Event

Represents a durable message or acknowledgment exchanged between Matriarch and
lane-local workers or agents.

Fields:

- `message_id`
- `lane_id`
- `direction`: `to_lane` | `to_matriarch`
- `sender`
- `recipient`
- `message_type`: `instruction` | `ack` | `status` | `question` | `shutdown`
- `body`
- `created_at`
- `delivered_at`: optional delivery acknowledgment timestamp
- `ack_status`: `new` | `acknowledged` | `resolved`

For v1, mailbox and report queues should converge on the shared event-envelope
shape owned by the runtime. `ack_status` is the visible acknowledgment state
for the message itself, not just a timestamp side effect.

## Lane Delegated Work Item

Represents a discrete unit of lane-local work that may be claimed safely by one
worker at a time.

Fields:

- `task_id`
- `lane_id`
- `title`
- `status`: `pending` | `in_progress` | `completed` | `failed`
- `claimed_by`: optional worker or agent identifier
- `claim_token`: optional write-safe claim identifier
- `claimed_at`
- `released_at`
- `result_ref`: optional artifact or note reference
- `error_ref`: optional failure artifact or note reference

## Hook Event

Represents one lane lifecycle event that may trigger transparent automation.

Fields:

- `event_name`
- `lane_id`
- `hook_name`
- `result`
- `recorded_at`
- `notes`
