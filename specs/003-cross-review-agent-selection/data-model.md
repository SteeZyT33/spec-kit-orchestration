# Data Model: Orca Cross-Review Agent Selection

## Review Agent

Represents a named runtime Orca can attempt to use for cross-review.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | Canonical agent identifier, e.g. `codex`, `opencode` |
| `tier` | enum | yes | `tier1`, `tier2`, `tier3` |
| `selectable` | boolean | yes | Whether the user may request this agent explicitly |
| `auto_selectable` | boolean | yes | Whether Orca may choose it automatically |
| `adapter_name` | string/null | no | Backend adapter binding |
| `supported` | boolean | yes | Whether Orca can claim substantive review support |

### Validation Rules

- Tier 1 agents must be selectable and auto-selectable.
- Tier 3 agents must not be auto-selectable.
- A supported agent must have an adapter binding.

## Agent Resolution Result

Represents the outcome of reviewer resolution before invocation.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `requested_agent` | string/null | no | CLI or config request |
| `resolved_agent` | string | yes | Final selected reviewer |
| `active_agent` | string/null | no | Current active agent/provider context |
| `selection_reason` | string | yes | Human-readable reason |
| `is_cross_agent` | boolean | yes | True when resolved reviewer differs materially from active provider |
| `support_tier` | enum | yes | Support tier of resolved agent |
| `used_legacy_input` | boolean | yes | True when `--harness` or `crossreview.harness` was used |

### Validation Rules

- `resolved_agent` must always be present, even on structured unsupported-agent
  outcomes.
- `is_cross_agent` must be false when the resolved agent matches the active
  provider.

## Review Agent Adapter

Represents the runtime contract for invoking a specific review agent.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `agent_name` | string | yes | Canonical agent identifier |
| `invocation_mode` | enum | yes | `native-cli`, `wrapped-cli`, or `unsupported` |
| `model_override_supported` | boolean | yes | Whether Orca may pass a model override |
| `effort_supported` | boolean | yes | Whether Orca may pass effort/reasoning controls |
| `structured_output_supported` | boolean | yes | Whether the adapter can reliably return normalized review JSON |

### Validation Rules

- Tier 1 adapters must support structured output.
- Unsupported adapters must still produce structured failure output.

## Reviewer Memory Entry

Optional stored context about the last successful reviewer.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `scope_key` | string | yes | Repo or feature scope identifier |
| `agent_name` | string | yes | Last successful reviewer |
| `timestamp` | datetime | yes | Last successful run |
| `result_kind` | enum | yes | `success`, `unsupported`, `runtime-failure` |

### Validation Rules

- Only successful entries should influence auto-selection.
- Missing or stale memory must be ignored safely.
