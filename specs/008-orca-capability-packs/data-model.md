# Data Model: Orca Capability Packs

## Capability Pack

Represents one optional Orca behavior bundle.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | e.g. `brainstorm-memory`, `review`, `yolo` |
| `purpose` | string | yes | Human-readable pack role |
| `status` | enum | yes | `core`, `optional`, `experimental`, `downstream` |
| `affected_commands` | list | yes | Commands or subsystems influenced |
| `prerequisites` | list | no | Required artifacts or subsystem capabilities |
| `activation_mode` | enum | yes | `always-on`, `config-enabled`, `experimental-only` |
| `owned_behaviors` | list | yes | Cross-cutting behaviors the pack is responsible for |
| `activation_source` | enum | runtime | Effective source after resolution: `core-default`, `config`, `experimental`, `inferred` |

### Validation Rules

- `core` packs must not make the core command set unreadable.
- `downstream` packs must not be treated as foundational.
- `affected_commands` must not be empty.
- `owned_behaviors` must not be empty.

## Pack Activation

Represents how a capability pack is enabled or assumed.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `pack_id` | string | yes | Capability pack identifier |
| `enabled` | boolean | yes | Whether the pack is active |
| `source` | enum | yes | `core-default`, `config`, `experimental`, `inferred` |

### Validation Rules

- `core-default` packs should not require user opt-in.
- `experimental` packs must not be silently enabled.

## Repo Manifest

Repo-local activation overrides live in `.specify/orca/capability-packs.json`.

### Shape

| Field | Type | Required | Notes |
|---|---|---|---|
| `packs` | object | no | Top-level pack override map; the file may also be the map directly |
| `<pack_id>.enabled` | boolean | yes | Explicit on/off state |
| `<pack_id>.reason` | string | no | Human-readable explanation for the override |

### Validation Rules

- Unknown pack ids are invalid.
- `always-on` packs may not be disabled by manifest.
- `experimental-only` packs require an explicit `enabled: true` override to activate.

## Core Boundary Rule

Represents an explicit rule for what remains in core Orca behavior.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `behavior` | string | yes | Workflow behavior under consideration |
| `classification` | enum | yes | `core`, `pack`, `deferred` |
| `reason` | string | yes | Why the classification exists |
