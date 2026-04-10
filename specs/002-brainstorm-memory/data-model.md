# Data Model: Orca Brainstorm Memory

## Brainstorm Record

Represents one durable brainstorm thread saved in project memory.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `number` | string | yes | Zero-padded sequence, e.g. `01`, `12` |
| `title` | string | yes | Human-readable topic title |
| `slug` | string | yes | Filename-safe normalized topic, fallback allowed |
| `status` | enum | yes | `active`, `parked`, `abandoned`, `spec-created` |
| `created` | date | yes | First save date |
| `updated` | date | yes | Last update date |
| `downstream` | string | yes | Canonical serialized header value: `none` or `<type>:<ref>` |
| `problem` | markdown section | yes | Framing of the problem |
| `desired_outcome` | markdown section | yes | What success looks like |
| `constraints` | markdown section | yes | Technical or process constraints |
| `existing_context` | markdown section | yes | Relevant repo/workflow context |
| `options_considered` | markdown section | yes | Favored path plus alternatives |
| `recommendation` | markdown section | yes | Current recommended direction |
| `open_questions` | markdown list | yes | Remaining unknowns/open threads |
| `ready_for_spec` | markdown section | yes | Handoff guidance for the next stage |
| `revisions` | repeated section | yes | Additive revisit entries, initially empty |

### Validation Rules

- `number` must be derived from the highest existing brainstorm number plus one.
- `slug` must be non-empty even when the topic text is weak or punctuation-only.
- `status` must be one of the allowed enum values.
- `updated` must be greater than or equal to `created`.
- `downstream` must be `none` unless `status = spec-created` or another
  explicit downstream link is known.
- `downstream` must not be `none` when `status = spec-created`.

### State Transitions

| From | To | Allowed | Notes |
|---|---|---|---|
| `active` | `parked` | yes | Idea paused intentionally |
| `active` | `abandoned` | yes | Idea dropped |
| `active` | `spec-created` | yes | Idea moved into formal spec flow |
| `parked` | `active` | yes | Reopened |
| `parked` | `spec-created` | yes | Parked idea later resumed into spec |
| `abandoned` | `parked` | yes | Reframed as intentionally parked |
| `abandoned` | `active` | yes | Revisited explicitly |
| `spec-created` | `active` | no | Create a new brainstorm or append a revision instead |
| `spec-created` | `spec-created` | yes | Link/details may be refined |

## Brainstorm Overview

Generated index file summarizing the current brainstorm landscape.

### Fields / Sections

| Section | Type | Required | Notes |
|---|---|---|---|
| `last_updated` | date | yes | Regeneration timestamp |
| `sessions_index` | table | yes | Number, date, topic, status, downstream link |
| `open_threads` | list | yes | Aggregated unresolved questions from records |
| `parked_ideas` | list | yes | Quick scan of parked brainstorms |

### Validation Rules

- Must be derivable entirely from current brainstorm records.
- Regeneration with unchanged inputs must produce the same content.
- Missing overview file must be recoverable from record scan alone.

## Brainstorm Match Candidate

Represents a likely related existing brainstorm surfaced during revisit checks.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `number` | string | yes | Matching brainstorm number |
| `title` | string | yes | Matching brainstorm title |
| `slug` | string | yes | Existing slug |
| `status` | enum | yes | Current brainstorm status |
| `match_reason` | string | yes | Short explanation for why it matched |

### Validation Rules

- Match candidates are advisory only.
- The user must always retain a `create new` option.

## Downstream Link

Forward reference from brainstorm memory into a later Orca artifact.

### Fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `type` | enum | yes | Initially `spec` or `feature-branch` |
| `ref` | string | yes | Path or identifier |
| `serialized` | string | yes | Canonical header value `<type>:<ref>` |

### Validation Rules

- `type` and `ref` must be written together and serialized as one canonical
  `Downstream` header value.
- Downstream links are optional except for `spec-created` status.
