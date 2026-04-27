# Orca Worktree Protocol

## Purpose

Define one provider-agnostic worktree model for Orca workflows.

This protocol exists because workflow semantics should not depend on whether the
active integration is Claude, Codex, or another agent. Agent-specific folders
may exist, but they are implementation details. Orca metadata is the workflow
source of truth.

## Scope

This protocol covers:

- how Orca identifies parallel lanes
- where worktree metadata lives
- how lane ownership is expressed
- how status transitions work
- how command docs should reason about active work

This protocol does not cover:

- automatic worktree provisioning in v1.4
- background orchestration engines
- upstream Spec Kit changes

## Core Terms

### Feature

A Spec Kit feature directory such as `specs/004-mneme-viz/`.

### Lane

A bounded unit of parallel work within a feature. A lane may correspond to a
worktree, a task cluster, or a review track, but in v1.4 the default
interpretation is "one lane equals one worktree-backed execution stream."

### Worktree record

A JSON metadata file describing one Orca lane.

### Registry

A repo-local index of lane records used by Orca commands to detect and reason
about parallel work.

## Source Of Truth

The Orca worktree registry under `.specify/orca/worktrees/` is the canonical
workflow source of truth.

Commands may inspect:

- `git worktree list`
- branch names
- current working directory

but those are supporting signals only. If they conflict with Orca metadata,
Orca metadata wins until repaired.

The initial runtime helper surface is:

- `scripts/bash/orca-worktree-lib.sh`
- `scripts/bash/orca-worktree.sh`

This feature does not require a dedicated `speckit.orca.worktree` command yet.

## Filesystem Layout

```text
.specify/orca/
  worktrees/
    registry.json
    <lane-id>.json
  logs/
  inbox/
```

### Required files

- `.specify/orca/worktrees/registry.json`
- one `<lane-id>.json` file for each known lane

### Optional files

- `.specify/orca/logs/` for later operational logs
- `.specify/orca/inbox/` for pre-feature brainstorming artifacts

## Registry Contract

`registry.json` is the index used for lane discovery and consistency checks.

### Example

```json
{
  "schema_version": "1.0",
  "repo_name": "mneme",
  "lanes": [
    "004-mneme-viz-ui",
    "004-mneme-viz-backend"
  ],
  "updated_at": "2026-04-08T20:00:00Z"
}
```

### Rules

1. `registry.json` is repo-scoped, not feature-scoped.
2. Every lane listed in `registry.json` must have a matching `<lane-id>.json`.
3. A lane record may exist before activation with status `planned`.
4. Cleanup should happen by status transition, not by silent metadata deletion.

## Lane Record Schema

Each lane is described by a dedicated JSON file.

### Example

```json
{
  "schema_version": "1.0",
  "id": "004-mneme-viz-ui",
  "feature": "004-mneme-viz",
  "branch": "004-mneme-viz-ui",
  "path": "/path/to/worktrees/004-mneme-viz-ui",
  "agent": "codex",
  "role": "frontend",
  "task_scope": ["T026", "T028", "T029"],
  "status": "active",
  "base_ref": "main",
  "parent_feature_branch": "004-mneme-viz",
  "shared_files": [],
  "notes": "Graph UI lane",
  "created_at": "2026-04-08T20:00:00Z",
  "updated_at": "2026-04-08T20:30:00Z"
}
```

### Required fields

- `schema_version`
- `id`
- `feature`
- `branch`
- `path`
- `agent`
- `role`
- `task_scope`
- `status`
- `base_ref`
- `created_at`
- `updated_at`

### Optional fields

- `parent_feature_branch`
- `shared_files`
- `notes`

### Field semantics

#### `id`

Stable lane identifier. Recommended format:

```text
<feature>-<lane>
```

Examples:

- `004-mneme-viz-ui`
- `004-mneme-viz-backend`
- `005-auth-hardening-migrations`

#### `feature`

Feature identifier matching the owning `specs/<feature>/` directory.

#### `branch`

Git branch associated with the lane.

#### `path`

Absolute filesystem path to the worktree root.

#### `agent`

The active integration or agent family for the lane, such as:

- `codex`
- `claude`
- `gemini`

This field is descriptive. It must not change Orca workflow semantics.

#### `role`

Human-readable specialization label for the lane. Examples:

- `frontend`
- `backend`
- `review`
- `migration`

#### `task_scope`

Explicit list of tasks or task groups owned by the lane.

Rules:

- must be non-empty for `active` lanes
- may be empty for `planned` lanes only if scope is not assigned yet

#### `shared_files`

Optional explicit declaration of files expected to be touched by multiple lanes.
This is an exception list, not the default.

#### `status`

One of:

- `planned`
- `active`
- `blocked`
- `merged`
- `retired`

#### `base_ref`

Default integration base. Usually `main`.

#### `parent_feature_branch`

Optional branch name for a feature-level integration branch if one exists.

## Status Model

### `planned`

Lane is defined but work has not started.

### `active`

Lane is currently being used for implementation or focused review work.

### `blocked`

Lane cannot progress due to dependency, decision, or merge conflict.

### `merged`

Lane work has landed in the parent integration path.

### `retired`

Lane is intentionally closed without active future use.

## Allowed Transitions

```text
planned -> active
planned -> retired
active -> blocked
active -> merged
active -> retired
blocked -> active
blocked -> retired
merged -> retired
```

Disallowed:

- `merged -> active`
- `retired -> active`

If a merged or retired lane needs more work, create a new lane record.

## Naming Rules

### Lane IDs

Use:

```text
<feature>-<short-lane-name>
```

Keep lane names short and meaningful:

- `ui`
- `backend`
- `review`
- `migrations`
- `docs`

Avoid:

- agent-specific names as the primary identity
- timestamps in lane IDs unless necessary for collision resolution

### Worktree paths

Recommended pattern:

```text
<worktree-root>/<lane-id>
```

Example:

```text
/path/to/worktrees/004-mneme-viz-ui
```

The path pattern is a convention, not a requirement. The metadata record is the
authoritative location.

## Collision Rules

### Task ownership

Default rule:

- one task belongs to one active lane

If two active lanes need the same task, that is a protocol smell and should be
resolved by:

1. splitting the task
2. moving ownership to one lane
3. promoting the issue to human review

### Shared files

Default rule:

- avoid shared-file active lanes

If unavoidable:

- declare the file path in `shared_files`
- ensure review calls out cross-lane merge risk

### Branch collisions

Two active lanes must not share the same branch name.

### Path collisions

Two active lanes must not share the same worktree path.

## Command Integration Rules

### `speckit.orca.assign`

`assign` should:

- read `.specify/orca/worktrees/registry.json`
- treat active lane records as the signal for parallel dispatch
- stop using `.claude/worktrees/` as the canonical detection path
- include lane-aware advisory reporting for dependency handoffs

`assign` should not:

- auto-create worktrees in v1.4
- infer lane ownership solely from `git worktree list`

### `speckit.orca.code-review`

`code-review` should:

- mention the active lane when a lane record exists
- record lane context in review artifacts
- flag cross-lane shared-file and dependency risks

`code-review` should not:

- change to lane-local diff review by default in v1.4

### `speckit.orca.pr-review`

`pr-review` should:

- report whether the active PR is lane-local or feature-wide
- preserve lane context when resolving external review comments
- use delivery metadata when assessing merge and thread state

### `speckit.orca.self-review`

`self-review` should:

- use lane metadata as workflow evidence
- identify blocked, abandoned, or noisy lane patterns
- evaluate whether parallelism reduced or increased friction

### Removed: `speckit.orca.spec-lite`

The `spec-lite` intake was removed in the Phase 1 strip alongside the
matriarch supervisor and yolo runner. Bounded work that previously
landed as a `spec-lite` record now goes through `/speckit.specify`
directly to produce a thin `spec.md`, then `/speckit.plan`. See
`docs/archive/orca-roadmap-pre-toolchest.md` for historical context.

## Repair Rules

If Orca metadata and Git reality diverge, commands should prefer safe behavior.

### Example divergences

- lane record says `active`, but worktree path no longer exists
- `git worktree list` shows a path with no lane record
- lane record branch does not match the checked-out branch at its path

### Repair policy

Commands should:

1. warn explicitly
2. avoid destructive assumptions
3. recommend metadata repair or retirement

Commands should not:

- silently rewrite lane metadata in v1.4

## Migration Guidance

Projects that already embed ad hoc worktree paths in artifacts should migrate
gradually.

### Existing artifact references

If a `tasks.md` or `plan.md` already includes a worktree path:

- keep the path for historical continuity
- add a lane record whose `path` matches that existing path
- do not rewrite historical artifacts solely for normalization

### Legacy agent-specific directories

If a project uses:

- `.claude/worktrees/`
- `.codex/...`
- custom external worktree roots

those may continue to exist, but Orca should treat them as secondary evidence.

## Minimal v1.4 Implementation Requirement

The minimum acceptable implementation of this protocol is:

1. a documented schema
2. command docs updated to refer to Orca lane metadata
3. no Claude-specific worktree assumptions in workflow semantics

Automatic provisioning, cleanup tools, and richer repair commands can come later.

## Open Questions

1. Should `registry.json` be feature-scoped or repo-scoped if multiple features
   are active in parallel?
2. Should `task_scope` allow non-task labels like `UI-POLISH` in addition to
   task IDs?
3. Should a dedicated `speckit.orca.worktree` command ship in the same release,
   or follow after the metadata contract stabilizes?

## Recommended Follow-On

After this protocol is accepted:

1. update `commands/assign.md`
2. update `commands/code-review.md`
3. update `commands/pr-review.md`
4. update `commands/self-review.md`
5. then add `brainstorm`
6. then add `quicktask`
