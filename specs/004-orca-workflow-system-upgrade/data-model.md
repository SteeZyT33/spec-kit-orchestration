# Data Model: Orca Workflow System Upgrade

## Upgrade Program

Represents the whole application-level Orca upgrade.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | `004-orca-workflow-system-upgrade` |
| `purpose` | string | yes | System-level goal for Orca evolution |
| `child_specs` | list | yes | Ordered subsystem inventory |
| `implementation_waves` | list | yes | Dependency-ordered work sets |
| `readiness_checkpoints` | list | yes | Gating conditions for later waves |

## Child Spec

Represents one subsystem within the upgrade program.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | e.g. `002-brainstorm-memory` |
| `role` | string | yes | What subsystem problem it owns |
| `dependencies` | list | no | Other child specs or runtime prerequisites |
| `wave` | string | yes | Assigned implementation wave |
| `current_state` | string | yes | `merged`, `planned`, or `in-progress` |
| `owned_outputs` | list | yes | Durable artifacts or runtime capabilities provided |

### Validation Rules

- each child spec must belong to exactly one wave
- dependencies must not create cycles
- owned outputs must be explicit enough for later specs to reference
- each child spec must declare current state separately from ideal wave order

## Integration Contract

Represents an explicit boundary between child specs.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `producer_spec` | string | yes | Upstream child spec |
| `consumer_spec` | string | yes | Downstream child spec |
| `provided_capability` | string | yes | Artifact or runtime behavior supplied |
| `assumption_limit` | string | yes | What the downstream spec may safely assume |

### Validation Rules

- integration contracts must not rely on chat/session state
- contracts must describe durable artifacts, explicit runtime behavior, or both

## Program Checkpoint

Represents a gating readiness condition for later waves.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | e.g. `yolo-foundation-ready` |
| `required_specs` | list | yes | Specs that must be substantively ready |
| `criterion` | string | yes | Human-readable gating rule |
| `current_status` | string | yes | `met`, `partial`, or `pending` |

### Validation Rules

- later waves may not claim readiness if required checkpoints are unmet
- checkpoint status must be legible against the actual merged repo state
