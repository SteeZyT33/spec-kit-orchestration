# Implementation Plan: Orca Worktree Runtime Helpers

**Branch**: `001-orca-worktree-runtime` | **Date**: 2026-04-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-orca-worktree-runtime/spec.md`

## Summary

Implement a metadata-backed Orca worktree runtime layer that can create, list,
inspect, and clean up worktrees while treating `.specify/orca/worktrees/` as the
workflow source of truth. The implementation will borrow the operational shape
from `cc-spex` worktree handling, but will store and reason about state using
Orca lane metadata rather than agent-specific folders.

This feature stops at runtime helpers and shell entrypoints. Existing Orca
commands will consume the runtime metadata in a follow-on feature after the
helper layer is proven.

## Technical Context

**Language/Version**: Bash (POSIX-ish with Bash features), Python 3.10+ available for existing tooling  
**Primary Dependencies**: `git`, existing Spec Kit repo layout, `python3` already used in existing scripts where needed  
**Storage**: JSON files under `.specify/orca/worktrees/`  
**Testing**: Manual shell verification in the Orca repo, plus lightweight script-level validation where practical  
**Target Platform**: Linux/WSL2 development environment first  
**Project Type**: Spec Kit extension / CLI helper tooling  
**Performance Goals**: Worktree operations should complete with normal local git latency; status/list operations should remain effectively instant on small-to-medium repos  
**Constraints**: Must not rely on `.claude` or other provider-specific folders; must not silently destroy active worktrees; should preserve current Orca naming and metadata model  
**Scale/Scope**: Single-repo local worktree lifecycle for Orca itself and future Orca-managed projects

## Constitution Check

The repository constitution has not been authored yet; `.specify/memory/constitution.md`
is still the stock template. Because of that, this feature uses the following
interim gates:

1. **Provider-agnostic gate**: no runtime dependency on Claude-specific paths or plugin mechanics.
2. **Metadata-first gate**: `.specify/orca/worktrees/` remains the workflow source of truth.
3. **Safety gate**: creation and cleanup flows must fail loudly rather than leave partial or destructive state.
4. **Scope gate**: this feature implements runtime helpers only, not command integration or full automation.

These gates must pass before implementation is considered complete.

## Project Structure

### Documentation (this feature)

```text
specs/001-orca-worktree-runtime/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
scripts/
└── bash/
    ├── crossreview.sh
    ├── resolve-pr-threads.sh
    ├── orca-worktree-lib.sh      # NEW
    └── orca-worktree.sh          # NEW

templates/
├── crossreview.schema.json
├── quicktask-template.md
├── review-template.md
├── worktree-record.example.json
└── worktree-registry.example.json # NEW

docs/
├── worktree-protocol.md
├── delivery-protocol.md
└── spex-harvest-list.md

commands/
├── assign.md
├── code-review.md
├── cross-review.md
├── self-review.md
└── ...
```

**Structure Decision**: Use `scripts/bash/` for the runtime implementation so it
matches existing Orca operational tooling. Keep the metadata contract visible in
`templates/` and `docs/`, but avoid wiring command docs to runtime behavior in
this feature. That integration will be easier and safer once the shell helpers
exist and are manually validated.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Manual shell runtime before command wrapper | Lowest-risk first implementation | Adding a `speckit.orca.worktree` command now would couple UX decisions to an unproven runtime |
| Manual verification as primary test method | Existing repo does not yet have a shell test harness | Building a full automated harness now would expand scope beyond runtime lifecycle delivery |

## Design Decisions

### 1. Runtime surface first, command wrapper later

The first implementation will expose:

- `scripts/bash/orca-worktree-lib.sh`
- `scripts/bash/orca-worktree.sh`

This keeps the logic testable and reusable. A future `speckit.orca.worktree`
command can become a thin wrapper over the shell runtime rather than inventing
its own semantics.

### 2. Orca metadata remains the source of truth

The shell runtime may inspect:

- `git worktree list`
- current branch
- filesystem paths

But these are secondary signals only. The primary runtime model is:

- `.specify/orca/worktrees/registry.json`
- `.specify/orca/worktrees/<lane-id>.json`

### 3. Adopt spex behavior, not spex substrate

The implementation should copy the useful operational logic from the `cc-spex`
worktree skill:

- default branch restoration
- nested worktree checks
- target path validation
- create/list/cleanup lifecycle

It should not adopt:

- `.claude` assumptions
- Claude restart/session instructions
- plugin-specific runtime behavior

### 4. Follow-on command integration is explicitly deferred

`assign`, `code-review`, `cross-review`, and `self-review` already describe the
future metadata-aware behavior, but they do not need to consume live runtime
state in this feature. That is a separate increment once helper behavior is
stable.

## Implementation Phases

### Phase 0: Runtime Foundations

Add shared runtime helpers in `scripts/bash/orca-worktree-lib.sh`.

Expected responsibilities:

- resolve repo root and default branch
- resolve registry and lane paths
- read and validate registry/lane JSON
- compute worktree paths
- detect current branch and current lane
- update registry safely

### Phase 1: Create/List/Status

Add `scripts/bash/orca-worktree.sh` with:

- `create`
- `list`
- `status`

`create` must:

- verify git repo state
- detect unsupported nested worktree usage
- validate target path
- restore default branch if required
- create the git worktree
- write lane metadata
- update the registry

`list` and `status` must:

- read Orca metadata first
- present lane summaries
- surface drift warnings when git state disagrees

### Phase 2: Cleanup

Add cleanup logic to `scripts/bash/orca-worktree.sh`.

Cleanup must:

- detect merged or retired candidate lanes
- avoid deleting ambiguous or active lanes silently
- remove worktrees safely
- update metadata consistently

### Phase 3: Documentation And Examples

Update:

- `templates/worktree-record.example.json`
- add `templates/worktree-registry.example.json`
- `README.md` worktree section if needed

This phase documents the actual runtime behavior rather than just the intended
protocol.

## Verification Strategy

### Primary verification

Manual script-level verification in this repository:

1. create a test feature branch
2. run Orca worktree create
3. verify git worktree exists
4. verify registry and lane record exist
5. run list/status
6. simulate merged or retired lane
7. run cleanup

### Secondary verification

Where practical, add lightweight validation helpers for:

- required registry fields
- required lane record fields
- impossible path conditions
- duplicate lane IDs or duplicate branches

### Non-goals for this feature

- no full automated shell test suite
- no command wrapper
- no command-doc runtime wiring
- no deep-review or ship integration

## Risks

### 1. Metadata drift

Git and Orca metadata may disagree.

Mitigation:

- make drift visible in `list`/`status`
- prefer warnings over silent repair

### 2. Unsafe cleanup

Cleanup could remove a live worktree if merge detection is too naive.

Mitigation:

- require clear merged or retired state
- treat ambiguous cases as warnings, not deletion candidates

### 3. Path mistakes

Computed paths may accidentally resolve inside the repo or to an existing path.

Mitigation:

- explicit path validation before any git worktree creation

### 4. Over-expansion of scope

It is tempting to wire all Orca commands immediately.

Mitigation:

- keep this feature strictly focused on runtime helpers and lifecycle operations

## Future Follow-On

This feature is intentionally the foundation for later work, not the full Orca
worktree story. Follow-on work should include:

- command integration for `assign`, `code-review`, `cross-review`, and `self-review`
- possible `speckit.orca.worktree` wrapper command
- delivery-aware PR and lane checks
- optional trait/module extraction around `worktrees`
