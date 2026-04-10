# Implementation Plan: Orca Matriarch

**Branch**: `010-orca-matriarch` | **Date**: 2026-04-09 | **Spec**: [spec.md](./spec.md)

## Summary

Build `orca-matriarch` as a conservative multi-lane control plane for Orca. The
first version focuses on durable lane registration, dependency tracking,
assignment metadata, worktree/checkout coordination, and readiness visibility
from existing workflow artifacts. It does not attempt autonomous scheduling or
exclusive repository control.

## Technical Context

**Primary runtime**: Python 3.10+ for deterministic registry/state helpers,
Bash wrappers for repo-local operator commands, Markdown artifacts for durable
lane summaries.

**Inputs consumed**:

- `001-orca-worktree-runtime` for worktree metadata and safe worktree actions
- `005-orca-flow-state` for per-lane stage/next-step visibility
- `006-orca-review-artifacts` for review/readiness evidence
- `007-orca-context-handoffs` for lane continuity across sessions/worktrees
- optional `009-orca-yolo` for future single-lane execution delegation

## Design Decisions

### 1. Matriarch Is A Supervisor, Not A Global Autonomous Engine

Matriarch owns coordination, not underlying implementation logic. It should:

- register and track lanes
- surface dependencies and blockers
- coordinate worktree/branch attachment
- provide checkout guidance
- aggregate readiness and next actions

It should not:

- invent flow-state semantics
- mutate review artifacts directly
- schedule opaque autonomous loops
- take destructive git actions without explicit operator intent

### 2. The Canonical Unit Is A Managed Lane

The core object is a lane, not just a branch. A lane represents:

- spec/feature identity
- branch identity
- optional worktree attachment
- current owner/agent
- dependency set
- derived state/readiness
- linked artifacts

### 3. Use A Durable Lane Registry

Matriarch needs explicit registry data rather than attempting to reconstruct
everything from git and feature files each time. Git and workflow artifacts
remain inputs, but lane-management metadata must be durable and authoritative
for orchestration.

### 4. Delegate Git/Worktree Operations To Lower-Level Helpers Where Possible

Matriarch should not reimplement worktree creation/cleanup if the existing Orca
runtime already owns that behavior. The preferred model is:

- Matriarch decides what lane/worktree relationship should exist
- lower-level worktree helpers perform the safe operation
- Matriarch records and verifies the resulting linkage

### 5. Hooks Must Be Explicit And Inspectable

Hooks are useful only when they remain understandable. V1 should support a
small, declared hook surface around lane lifecycle events, with transparent
execution and no hidden mutation chains.

### 6. Checkout Should Be Safe By Default

`checkout` in v1 should primarily resolve and print the intended target, and
may optionally execute a controlled switch when invoked explicitly. It must not
silently relocate the operator or mutate unrelated work.

## Scope

### In Scope

- lane registry and metadata
- lane creation/registration from specs
- dependency tracking
- assignment tracking
- worktree/branch linkage tracking
- checkout target resolution
- lane summary/status surface
- readiness aggregation from durable artifacts
- hook model for lane lifecycle events

### Out Of Scope

- full autonomous multi-agent scheduling
- optimization of agent allocation
- replacing git/GitHub workflows
- deep UI/TUI/dashboard rendering
- mandatory `009-orca-yolo` integration in v1
- multi-worktree-per-lane support unless proven necessary later

## Risks And Mitigations

### Risk: Matriarch Reimplements Existing Orca Subsystems

Mitigation: treat `005`, `006`, `007`, and `001` as owned contracts and only
consume them.

### Risk: Worktree/checkout behavior becomes destructive or confusing

Mitigation: default to explicit operator commands, dry resolution, and durable
metadata verification before mutation.

### Risk: Hooks turn into hidden automation

Mitigation: small hook surface, explicit registration, visible logging, and no
implicit mutation of unrelated lanes.

### Risk: `010` depends too hard on unfinished `009`

Mitigation: make `009` optional for v1. Matriarch is useful even as a pure
coordination system.

## Delivery Strategy

### Phase 1: Registry And Lane Model

- define lane data model
- define registry storage layout
- define dependency and assignment records

### Phase 2: Coordination Commands

- register/create lane
- show/list lanes
- assign owner/agent
- attach/record worktree
- resolve checkout target

### Phase 3: Derived State And Readiness

- read flow/review/handoff artifacts
- compute lane status and blockers
- expose operator-facing summary

### Phase 4: Hook Surface

- define supported lane lifecycle hooks
- add transparent execution/logging contract
- keep actual hook set intentionally small

## Verification Strategy

- deterministic unit tests for lane registry and dependency resolution
- command-level smoke tests for lane registration and checkout resolution
- manual repo-level verification across at least two simultaneous lanes
- explicit drift tests where branch/worktree metadata does not match registry

## Open Planning Questions

- should lane ids be spec ids by default, or a separate generated identifier?
- should `checkout` execute by default or require `--exec`/equivalent?
- should lane creation be allowed before a spec exists, or only after a spec is
  real?
- what is the minimal useful hook set for v1?
