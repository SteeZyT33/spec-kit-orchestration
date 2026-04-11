# Research: spec-kitty Execution Loop

**Date**: 2026-04-11
**Purpose**: Input research for `014-yolo-runtime` brainstorm. Captures
spec-kitty's execution-loop patterns so Orca's single-lane runner can
harvest the primitives that fit and reject the ones that don't.
**Source**: `/home/taylor/spec-kitty/repomix-output.xml` (not in Orca's repo)
**Scope**: Targeted deep-dive only. Not a full spec-kitty audit —
that was done in the earlier "spec-kitty vs Orca" architectural comparison.

---

## The `next` command

**Behavior**: `spec-kitty next --agent <name>` is the canonical
single-entrypoint loop command (per spec-kitty ADR 2026-02-17-1). It
auto-completes the previously issued step as success unless
`--result` override is supplied. Output includes both a machine JSON
decision payload and human-readable prompt text.

**Dispatch model**: `next` does **not** dispatch to an agent directly.
It returns a decision payload and the caller (agent or human)
executes the step, then calls `next` again to report the result. This
is a **read-only, async-friendly loop**, not a blocking execution
call. That's an important design point for Orca to preserve.

**Decision payload kinds**: `step` (execute next), `decision_required`
(human input needed), `blocked` (cannot proceed), `terminal` (run
complete).

**Ordering**: Determined by the mission DAG and lane computation
upfront, frozen at run start. `next` does not rank or select from a
pending queue at call time — it follows the pre-computed sequence.

## Work package state machine

**Canonical 9 lanes** (expanded from an earlier 7):
`planned`, `claimed`, `in_progress`, `for_review`, `in_review`,
`approved`, `done`, `blocked`, `canceled`.

`in_review` was promoted from an alias to a first-class lane to
resolve concurrency blind spots for parallel review workflows
(spec-kitty ADR 2026-04-06-1).

**Allowed transitions**:
- `planned → claimed → in_progress → for_review → in_review → approved → done`
- `for_review → blocked | canceled` allowed
- `in_review → in_progress` allowed (reviewer rollback / changes requested)
- Backward moves other than reviewer rollback are rejected

**Trigger mechanism**: Transitions are triggered by events appended to
`status.events.jsonl`. Each event carries `actor`, `from_lane`,
`to_lane`, and optional `review_ref` for reviewer rollbacks.

**Precedence**: Reviewer rollback events (with `review_ref` set)
outrank concurrent forward progression. Semantic rule, not positional
— review feedback is authoritative.

**Enforcement**: Centralized reducer applied during event merge
(spec-kitty ADR 2026-02-09-3). Per-event validation at emission time
via `status emit`. Invalid transitions flagged in CI by
`status validate`.

## Event shape (JSONL event-sourced state)

**Envelope**:
- `event_id` (ULID, required — 26 chars, monotonic, lex-sortable)
- `event_type`
- `aggregate_id` (WP ID or feature slug)
- `aggregate_type` (`WorkPackage` | `Feature`)
- `timestamp` (ISO 8601)
- `lamport_clock` (integer)
- `node_id`
- `causation_id` (optional)

**Routing fields**:
- `team_slug`, `project_uuid`, `project_slug`, `git_branch`,
  `head_commit_sha`, `repo_slug`

**Payload**: object with `wp_id`, `from_lane`, `to_lane`, `actor`.
Review events include optional `review_ref`. Evidence events include
`repos[]`, `verification[]`, `review{}` (spec-kitty ADR 2026-02-09-4).

**Composition (reducer)**: Events are deterministic — a function
reads sorted events from `status.events.jsonl` and materializes
current state to `status.json`. Replayable: same event sequence
always produces the same state.

**Conflict resolution (4-step merge algorithm from spec-kitty ADR
2026-02-09-3)**:
1. Concatenate logs from merged branches
2. Deduplicate by `event_id`
3. Sort by `(logical_clock, timestamp, event_id)`
4. Reduce through state machine

Reviewer rollback events outrank concurrent forward events.

**File paths** (per-feature):
- `kitty-specs/<feature>/status.events.jsonl` — canonical append-only log
- `kitty-specs/<feature>/status.json` — materialized snapshot (derived, regeneratable)
- `tasks.md` and WP front-matter `lane` fields — generated views,
  **never edited as authority**

## Worktree isolation model

**Creation timing**: Worktree is created at the
`claimed → in_progress` transition — when an agent claims and starts
the work. Not at `claimed`, not at `planned`.

**Lane/worktree relationship**: One worktree per **execution lane**
(not per WP). Multiple sequential WPs may execute inside the same
lane branch/worktree. Lane computation is done by the planner and
emitted as `lanes.json` (spec-kitty ADR 2026-04-03-1). Lane branch
naming: `kitty/mission-<feature-slug>-lane-<id>`.

**Inside worktree**: Implementation code and worktree-local state.
Specs, status files, and mission config live in the main repo.
Worktree has a symlink to `.kittify/memory/` (shared with main repo).

**Cleanup**: At `done` or `approved` (not at merge). When a lane's
WPs are all terminal, the worktree is marked for cleanup. Actual
cleanup happens during `merge` or via `spec-kitty cleanup` (per
spec-kitty ADR 2026-01-26-9: *"worktree-cleanup-at-merge-not-eager"*).

**Orphaning**: If a WP is `canceled` or `blocked` while its worktree
exists, the worktree is orphaned. `spec-kitty doctor` detects
orphaned worktrees and flags them. No automatic cleanup — manual
intervention with `--force` required. **Preserves evidence.**

**Ownership conflicts**: Lane branches are claimed by the first
agent to move a WP from `claimed → in_progress`. Stale claims
(no activity for 7-14 days) are detected by `doctor` and recoverable
with `--recover`, which re-emits `in_progress` without creating a
new worktree.

## Resumability

**Reads from disk**: Two sources when resuming:
1. `status.events.jsonl` (canonical state — event log replay)
2. `.kittify/merge-state.json` (if a merge was interrupted)

Resume replays the event log to reconstruct state. No snapshot-read
fallback — the materialized `status.json` is treated as derived, not
authoritative.

**Dead vs paused detection**: `spec-kitty doctor` compares the
timestamp of the last event against current time. Claims older than
7 days in `claimed` or 14 days in `in_progress` are flagged as stale.
**Heuristic, not a heartbeat** — no active health-check mechanism.

**Stale-claim recovery**: If an agent claims a WP but crashes before
emitting the first `in_progress` event, the WP stays in `claimed`
indefinitely. `doctor` flags it. Recovery via
`implement WP02 --recover` re-emits the transition without creating
a duplicate worktree.

**Preventing re-runs**: The reducer ensures idempotence. Same
`event_id` sent twice → deduplicated at merge time. The response
marks duplicates as successful and removes from the offline queue.

**Merge resume**: `spec-kitty merge --resume` reads
`.kittify/merge-state.json`, skips completed WPs, and continues from
the current one. Strategy and target branch are preserved.

## Agent attribution and routing

**Attribution**: Each event includes an `actor` field (agent name or
human identifier). **No pre-auth tokens or registered identity
required** — the actor field is trust-based at emission time.

**Selection**: Deterministic per the mission template + lane
computation. The planner assigns WPs to lanes; the runtime does
**not** select agents. If an agent is unavailable, **no automatic
fallback** — the WP stays in `claimed` until claimed by another
agent.

**Cross-review**: `next` does not automatically assign a different
agent for review. Review is typically claimed by a different human
or a dedicated review agent, but **not automatic**. The planner can
emit `lanes.json` specifying a review team or role, but the runtime
enforces no agent-swapping policy.

**Disagreement handling**: No validation of agent intent. Invalid
transitions (e.g., `in_progress → approved` skipping `for_review`)
are rejected by the state machine guard, not by agent authorization.
Error returned in the event emission response.

## `for_review` → `merged` handoff

**Flow**: `for_review` is a queued-for-review lane. An agent claims
it by moving to `in_review` (analogous to `planned → claimed → in_progress`
for implementation). The reviewer provides a verdict — approved or
changes-requested. If approved, the WP moves to `approved`.

**`review` is a command/action**, not a state. `for_review` and
`in_review` are the states.

**Merge authorship**: `approved` WPs are merged by a separate `merge`
command or agent. The merge agent can differ from the reviewer. Merge
happens from the lane branch into the mission integration branch,
then mission into target.

**Merge-readiness**: No automatic gate. Approval directly transitions
to `approved`. Merge is a separate, explicit command. An `approved`
WP may be **blocked from merging** if the mission integration branch
has drifted and the lane has overlapping file changes (stale-lane
merge guard, spec-kitty ADR 2026-04-03-1).

**Parallel merge conflicts**: Handled via the event merge algorithm.
If two lanes try to merge simultaneously, only one succeeds; the
other sees the conflict on the next mission-branch pull. Manual
resolution or rebase required.

---

## Verdict on harvest candidates

### Adopt verbatim

1. **Append-only JSONL event log** (spec-kitty ADR 2026-02-09-1) —
   canonical, git-friendly, fully auditable
2. **Deterministic merge algorithm** (spec-kitty ADR 2026-02-09-3) —
   concatenate → dedupe → sort → reduce, with reviewer rollback
   precedence. Critical for offline-first multi-agent safety
3. **Lamport clock + ULID event IDs** — deterministic ordering,
   conflict-free deduplication
4. **Stale-claim detection via timestamp heuristic** — simple,
   effective, no heartbeat overhead

### Adapt

1. **State machine design** — Orca 009 already has a run-stage model
   and lane registry. Extend with explicit state machine guards
   matching spec-kitty's transition rules. Orca's existing lane
   boundaries map cleanly to the 9-lane model; no breaking change
2. **Worktree isolation per lane** (not per WP) — Orca's existing
   worktree runtime is per-lane already, but the lane-vs-WP distinction
   may need sharpening in 009's contracts
3. **Resume/recovery flow** — Orca's session persistence needs
   stale-claim detection and a `--recover` equivalent; reuse the
   spec-kitty pattern

### Reject

1. **Charter + doctrine governance** — spec-kitty-specific surface;
   conflicts with Orca's post-refinement "simpler product surface"
   direction
2. **Dashboard kanban UI** — platform feature, not a runtime
   primitive. Orca's lane registry is internal
3. **Acceptance gates / QA evidence** (spec-kitty ADR 2026-04-03-3) —
   mission integration-branch acceptance is out of scope for Orca's
   single-lane runner

## Gotchas and landmines

1. **Stale-claim false positives** — 7-14 day heuristic is wall-clock,
   not event-based. Legitimately-paused agents (waiting for human
   decision) get flagged. Orca should make thresholds configurable
   and **always warn before auto-recovery**.
2. **Stale-lane merge guard complexity** — preventing merges when
   the mission branch has drifted and the lane has overlapping file
   changes requires conflict-aware lane computation by the planner.
   If the planner gets this wrong, safe parallelism is lost and
   merges block unpredictably.
3. **Event deduplication race** — if two agents emit the same event
   with the same `event_id` but different `lamport_clock` values,
   dedup succeeds but the logical clock becomes inconsistent. Orca
   should enforce **globally unique event_id at emission time** (ULID
   handles this) and never allow manual clock assignment.
4. **Reviewer rollback precedence is implicit** — the rule is
   hardcoded in the reducer. Error messages for invalid transitions
   are generic. Orca should make state machine error messages
   explicit about guard violations so operators can debug failed
   transitions.
5. **No circuit-breaker on stale-worktree loops** — if a worktree is
   orphaned but not cleaned up, a new agent claiming the same lane
   gets the stale worktree. `--recover` re-emits state but does not
   validate the worktree is on the correct branch or that its code
   matches expected state. **Recovery must pair with branch
   inspection.**
