# Contract: Lane Registry

## Purpose

Define the durable metadata layer Matriarch owns.

## Required Properties

- one canonical lane record per active supervised lane
- one primary spec identity per lane
- explicit mapping from lane to spec/branch/worktree where known
- explicit lifecycle state per lane
- explicit dependency relationships
- explicit ownership/assignment records
- optional deployment attachment records
- durable timestamps for creation and latest update

## Registry Rules

- registry metadata is authoritative for orchestration intent
- live git/worktree state is authoritative for observed runtime reality
- live tmux/session state is authoritative for observed deployment reality
- in v1, `lane_id` should equal the primary `spec_id`
- Matriarch must detect and surface drift between registry intent and live
  state
- archived lanes remain inspectable but are excluded from default active views
- a lane must not own multiple primary specs in v1
- if related specs need coordination, they should be represented as separate
  lanes plus dependency or grouping metadata, not collapsed into one lane

## Concurrency Rules

- registry writes must be serialized through an explicit file-lock mechanism in
  v1
- v1 should use advisory file locking with a short timeout plus stale-lock
  handling rather than implicit last-write-wins
- a lock older than 60 seconds should be treated as stale only after a
  re-check that the owning process is no longer active when that evidence is
  available
- each successful write must update a registry revision or updated-at value so
  stale writers can be detected
- lane-level updates must fail clearly when the caller is operating on stale
  registry data
- silent last-write-wins behavior is not acceptable for lane metadata
- Matriarch should prefer narrow lane-level mutation where possible instead of
  rewriting unrelated lane records

## Lifecycle Rules

- lifecycle state is supervisory and must not be inferred only from feature
  flow stage
- `registered` means the lane exists but is not yet actively supervised or
  deployed
- `active` means the lane has an owner or operator responsibility and is in
  progress
- `blocked` means the lane cannot progress because of declared dependency,
  missing evidence, or explicit operator block
- `review_ready` and `pr_ready` are explicit supervisory states derived from
  readiness evidence, not just prose annotations
- `archived` means the lane is no longer active but remains inspectable
- `blocked` takes precedence over `review_ready` and `pr_ready` when a hard
  dependency or explicit operator block is still active
- readiness-derived lifecycle transitions must remain explainable from durable
  evidence and recorded reasoning
- assignment loss or deployment loss alone must not silently archive a lane;
  those conditions should surface as warnings, mismatch flags, or explicit
  blocked/attention-needed states
- effective state precedence in v1 should be:
  `archived` > `blocked` > `pr_ready` > `review_ready` > `active` > `registered`

## Transition Authority

| Transition | Allowed Authority | Notes |
|---|---|---|
| create -> `registered` | operator or Matriarch command | explicit lane creation/register action |
| `registered` -> `active` | operator or Matriarch command | requires owner or explicit operator responsibility |
| any -> `blocked` | Matriarch derived state or operator | hard dependency, missing evidence, or explicit block |
| `active` -> `review_ready` | Matriarch derived state with recorded evidence | lane agent may report readiness signals, but does not authoritatively set state |
| `review_ready` -> `pr_ready` | Matriarch derived state or operator confirmation | depends on review and readiness evidence |
| any active state -> `archived` | operator only | archival is explicit in v1 |

Lane agents may report events upward, but they do not own authoritative
lifecycle mutation in v1.
