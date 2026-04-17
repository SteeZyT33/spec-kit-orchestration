# Implementation Plan: Orca Matriarch

**Branch**: `010-orca-matriarch` | **Date**: 2026-04-09 | **Spec**: [spec.md](./spec.md)

## Summary

Build `orca-matriarch` as a conservative multi-lane control plane for Orca. The
first version focuses on durable lane registration, dependency tracking,
assignment metadata, worktree/checkout coordination, and readiness visibility
from existing workflow artifacts. It does not attempt autonomous scheduling or
exclusive repository control. Tmux-based agent deployment is treated as an
optional supervised runtime attachment, not the center of the design.

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

**Supervision substrate**:

- durable lane registry under Orca-owned metadata
- optional tmux session attachment for lane-local execution
- optional direct interactive session attachment for non-tmux worker CLIs
- durable lane mailbox/report files under Orca-owned metadata
- explicit checkout resolution before any shell or session mutation

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

V1 constraint:

- one lane owns one primary spec
- Matriarch coordinates many lanes to manage many specs
- if related specs need to move together later, that should become a higher
  grouping concept above lanes rather than changing lane semantics

### 3. Use A Durable Lane Registry

Matriarch needs explicit registry data rather than attempting to reconstruct
everything from git and feature files each time. Git and workflow artifacts
remain inputs, but lane-management metadata must be durable and authoritative
for orchestration. Because multiple agents or operator sessions may write lane
state concurrently, v1 must also define a concrete write-safety model instead
of relying on implicit last-write-wins behavior.

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
silently relocate the operator or mutate unrelated work. Because a command
cannot safely rewrite the parent shell context invisibly, `--exec` should mean
"perform the narrow attach/switch action now" rather than "teleport the user"
through hidden shell mutation.

### 7. Tmux Is A Deployment Option, Not The Control Plane

The user is right that multi-lane supervision becomes much more useful once
there is a real agent deployment substrate. For v1, tmux should fill that role
conservatively:

- each lane may optionally point at one tmux session
- Matriarch may launch, attach, or inspect that session explicitly
- Matriarch must record deployment health separately from workflow readiness
- tmux deployment must remain optional so manual and non-tmux lanes behave
  normally
- owner/session mismatch must be surfaced explicitly after reassignment rather
  than silently rebinding the old session
- launched lane agents should report blockers and questions back to Matriarch
  rather than bypassing supervision by default

The first report-back mechanism should be file-backed and durable so it
survives tmux detach, session loss, or operator re-entry.

The same coordination model should also work for non-tmux interactive worker
CLIs such as Claude Code. Those should be represented as `direct-session`
deployments rather than as missing deployment.

### 9. State-First Coordination Beats Tmux-First Coordination

Useful lessons from tmux-driven team systems should be harvested carefully:

- durable mailbox, task, and report state should be the source of truth
- tmux attach/send-keys behavior should be a nudge or transport detail, not the
  coordination contract
- acknowledgments and delegated-work lifecycle changes should be visible from
  durable artifacts alone

Orca should copy the state-first principle, not the OMX-specific runtime.

### 10. Delegated Work Needs Claim-Safe Lifecycle Rules

If Matriarch later delegates discrete sub-work inside a lane, the lifecycle
should be explicit:

- pending
- claimed / in_progress
- completed
- failed
- released back to pending

That prevents duplicate work and keeps delegation auditable without requiring
tmux to be the durable authority.

### 11. Lane ID Should Equal Spec ID In V1

Because v1 enforces one lane per primary spec, `lane_id` should simply equal
the primary `spec_id`. That keeps mailbox paths, deployment naming, and
registry lookup deterministic without adding another identifier layer.

### 8. Lane Lifecycle Must Be Supervisory And Explicit

Matriarch needs its own lane lifecycle rather than trying to reuse feature
stage state as if they were the same thing. The likely v1 lifecycle is:

- `registered`
- `active`
- `blocked`
- `review_ready`
- `pr_ready`
- `archived`

Feature flow stage from `005` remains an input, not a substitute for lane
supervision state. Hard dependency blockers and explicit operator blocks should
override "ready" lifecycle states until cleared.

## Scope

### In Scope

- lane registry and metadata
- lane creation/registration from specs
- dependency tracking
- assignment tracking
- worktree/branch linkage tracking
- checkout target resolution
- optional tmux deployment attachment and inspection
- optional direct-session deployment attachment and inspection
- durable lane mailbox/report queue
- claim-safe delegated work records when delegation is used
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
- broad tmux orchestration beyond one session attachment per lane
- wholesale adoption of OMX team/worker runtime contracts or file layout
- introducing a separate lane id scheme before v1 proves it needs one

## Risks And Mitigations

### Risk: Matriarch Reimplements Existing Orca Subsystems

Mitigation: treat `005`, `006`, `007`, and `001` as owned contracts and only
consume them.

### Risk: Worktree/checkout behavior becomes destructive or confusing

Mitigation: default to explicit operator commands, dry resolution, and durable
metadata verification before mutation.

### Risk: Tmux deployment gets confused with orchestration authority

Mitigation: track deployment state separately from readiness/state, keep
tmux optional, and make launch/attach operations explicit.

### Risk: Delegated workers duplicate or stomp one another's work

Mitigation: use claim-safe delegated-work records and durable acknowledgments
instead of informal ownership changes.

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
- define mailbox/report and delegated-work records

### Phase 2: Coordination Commands

- register/create lane
- show/list lanes
- assign owner/agent
- attach/record worktree
- resolve checkout target
- optionally attach/inspect tmux deployment

### Phase 3: Derived State And Readiness

- read flow/review/handoff artifacts
- compute lane status and blockers
- expose operator-facing summary

### Phase 4: Deployment And Hook Surface

- define tmux deployment attachment model
- define supported lane lifecycle hooks
- add transparent execution/logging contract
- keep actual hook and deployment surface intentionally small

### Phase 5: Delegation And Mailbox Surface

- define lane mailbox/report queue behavior
- define delegated-work claim lifecycle
- keep state-first coordination separate from deployment transport

## Verification Strategy

- deterministic unit tests for lane registry and dependency resolution
- deterministic tests for lock or stale-write handling in the registry
- deterministic tests for shared event-envelope parsing and ordering
- command-level smoke tests for lane registration and checkout resolution
- tmux deployment smoke tests where tmux is available
- direct-session smoke tests for Claude Code or other non-tmux worker CLIs
- report-back protocol smoke tests using synthetic lane-agent events
- mailbox and claim-lifecycle tests without tmux dependency
- manual repo-level verification across at least two simultaneous lanes
- explicit drift tests where branch/worktree metadata does not match registry

## Open Planning Questions

- should `checkout` execute by default or require `--exec`/equivalent? Current
  direction: require explicit opt-in.
- should lane creation be allowed before a spec exists, or only after a spec is
  real?
- what is the minimal useful hook set for v1?
- should tmux launch behavior live directly in Matriarch or through a narrower
  deployment adapter layer?
- should future multi-spec grouping be called `program`, `initiative`, or
  `bundle` once needed above lanes?
