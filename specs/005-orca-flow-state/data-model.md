# Data Model: Orca Flow State

## Flow Stage

Represents one canonical stage in the Orca workflow lifecycle.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | enum | yes | e.g. `brainstorm`, `specify`, `plan`, `tasks`, `assign`, `implement`, `code-review`, `cross-review`, `pr-review`, `self-review` |
| `ordinal` | integer | yes | Ordering position in the canonical workflow |
| `kind` | enum | yes | `build`, `review`, or `meta` |

### Validation Rules

- stage names must be stable across Orca consumers
- ordinals define recommended workflow order, not an absolute guarantee that all
  earlier evidence exists

## Flow Milestone

Represents durable evidence that a stage or review gate has been reached.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `stage` | enum | yes | Canonical stage name |
| `status` | enum | yes | `complete`, `incomplete`, `unknown`, `ambiguous` |
| `evidence_sources` | string[] | yes | Artifact paths or evidence labels |
| `notes` | string[] | no | Human-readable ambiguity or inference notes |

### Validation Rules

- `ambiguous` requires at least one explanatory note
- `complete` must cite at least one evidence source

## Review Milestone

Represents review completion separately from build progress.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `review_type` | enum | yes | `spec`, `plan`, `code`, `cross`, `pr`, `self` |
| `status` | enum | yes | `complete`, `incomplete`, `unknown`, `ambiguous` |
| `evidence_sources` | string[] | yes | Artifact paths or evidence labels |
| `notes` | string[] | no | Human-readable clarification or ambiguity notes; serialized in `FlowStateResult.to_dict()` via `asdict()` |

### Validation Rules

- review milestones are independent of implementation stage
- a later review milestone may coexist with missing earlier build milestones, but
  that should usually produce ambiguity notes

## Flow State Result

Represents the computed feature-level workflow state.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `feature_id` | string | yes | Feature directory or identifier |
| `current_stage` | enum/null | no | Best current stage when determinable |
| `completed_milestones` | object[] | yes | Flow milestones marked complete |
| `incomplete_milestones` | object[] | yes | Flow milestones marked incomplete |
| `review_milestones` | object[] | yes | Review milestone states |
| `ambiguities` | string[] | yes | Conflicting or uncertain signals |
| `next_step` | string/null | no | Best next action hint |
| `evidence_summary` | string[] | yes | Compact explanation of why the result was chosen |

### Validation Rules

- `next_step` may be null when ambiguity is too high
- `current_stage` may be null when the evidence is materially conflicting

## Resume Metadata

Optional thin persisted metadata for resumability or cached guidance.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `feature_id` | string | yes | Feature identifier |
| `last_computed_stage` | enum/null | no | Last computed stage when determinable; may be null when the computed result is materially ambiguous |
| `last_next_step` | string | no | Cached next-step hint |
| `updated_at` | datetime | yes | Last refresh timestamp |

### Validation Rules

- resume metadata must be safely ignorable
- it must never be treated as the only workflow truth
- readers and writers must preserve a null `last_computed_stage` without coercing it to another stage
