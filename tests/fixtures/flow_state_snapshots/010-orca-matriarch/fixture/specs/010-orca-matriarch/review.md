# Cross Review: Orca Matriarch

## Latest Status

Implementation review is now split across:

- [review-code.md](./review-code.md)
- [review-cross.md](./review-cross.md)

- original planning blockers were resolved before implementation started
- the first implementation-focused `opencode` pass found real runtime issues and
  those fixes are now applied on this branch
- the follow-up `opencode` run timed out, so the latest external signal is
  “issues found and fixed,” not a fresh clean pass

## Requested Reviewer

- agent: `opencode`
- model: `github-copilot/claude-opus-4.6`
- variant: `max`
- scope: design
- date: 2026-04-10

## Historical Snapshots

### Original Planning Verdict

`010` is now structurally strong, but it still has two real implementation
blockers at the system seams: registry concurrency and the concrete report-back
protocol from launched lane agents to Matriarch. Several additional issues are
non-blocking but should be resolved before implementation to avoid drift.

## Blocking Findings

1. **No concurrency or conflict model for the lane registry.**
   The registry is file-backed durable state that multiple agents or operator
   sessions may write to concurrently. The current contracts define metadata
   and drift rules, but not locking, optimistic versioning, or conflict
   resolution semantics.
   Affected files:
   - [lane-registry.md](./contracts/lane-registry.md)
   - [data-model.md](./data-model.md)

2. **FR-020 has no concrete report-back mechanism.**
   The spec and tmux deployment contract say launched lane agents must report
   blockers and questions back to Matriarch, but there is no defined protocol,
   file convention, or polling model.
   Affected files:
   - [spec.md](./spec.md)
   - [tmux-deployment.md](./contracts/tmux-deployment.md)
   - [tasks.md](./tasks.md)

## Non-Blocking Findings

1. **Lifecycle transition authority is still underdefined.**
   The docs now define lifecycle states and precedence, but not a full
   authority table for who or what may move a lane into each state.

2. **`checkout --exec` behavior for tmux-attached lanes needs a sharper rule.**
   The contracts distinguish worktree, branch, and tmux actions, but they still
   stop short of specifying exactly what `--exec` should do when more than one
   target is available.

3. **`assignment_state: abandoned` has no trigger rule.**
   The state exists in the data model, but the contracts do not define whether
   it is operator-declared, timeout-derived, or deployment-derived.

4. **Drift detection categories are not enumerated clearly enough.**
   Branch/worktree drift is implied, but owner/session mismatch and
   readiness-evidence mismatch should be listed explicitly.

5. **Hook registration is still file-backed in principle only.**
   The hook contract says hooks must be file-backed and visible, but not yet
   where they live or what schema they use.

6. **Dependency `target_value` needs a closed value set by target kind.**
   `stage_reached`, `review_ready`, and other target kinds should define their
   allowed values precisely.

## Open Questions Worth Deciding Now

1. What is the registry write-safety model: file locks, optimistic versioning,
   single-writer discipline, or something else?
2. What is the exact lane-agent report-back protocol: file drop, queue,
   structured event log, polling path, or another mechanism?
3. Which lifecycle transitions are operator-only, which are Matriarch-derived,
   and which may be agent-reported?
4. For a lane with both a worktree and tmux deployment, what narrow action does
   `checkout --exec` perform by default?

## Recommended Next Changes

1. Add a registry concurrency section to
   [lane-registry.md](./contracts/lane-registry.md).
2. Add a report-back protocol section to
   [tmux-deployment.md](./contracts/tmux-deployment.md).
3. Add a lifecycle transition authority table to
   [lane-registry.md](./contracts/lane-registry.md).
4. Enumerate valid dependency `target_value` sets in
   [dependency-model.md](./contracts/dependency-model.md).
5. Define the hook registration file format and location in
   [hook-model.md](./contracts/hook-model.md).

### Resolution Addendum

The blocking findings from this review have now been addressed in the planning
artifacts:

1. Registry concurrency is now defined in
   [lane-registry.md](./contracts/lane-registry.md) with explicit file
   locking, stale-write rejection, and lane-level mutation guidance, and the
   write token is now reflected in [data-model.md](./data-model.md).
2. Lane-agent report-back is now defined in
   [tmux-deployment.md](./contracts/tmux-deployment.md)
   with a file-backed append-only reporting path and explicit event fields, and
   the report record is now reflected in
   [data-model.md](./data-model.md).

Several earlier non-blocking findings were also tightened:

- lifecycle transition authority is now explicit in
  [lane-registry.md](./contracts/lane-registry.md)
- dependency target values are now enumerated in
  [dependency-model.md](./contracts/dependency-model.md)
- hook registration location and schema are now defined in
  [hook-model.md](./contracts/hook-model.md)

Remaining open design choices are now narrow rather than blocking:

1. whether `checkout --exec` should prefer tmux attach, worktree switch, or a
   reported menu when more than one target is available
2. whether tmux launching should remain a direct Matriarch responsibility or
   sit behind a thinner deployment adapter

### Second External Review Addendum

Reviewer:

- agent: `opencode`
- model: `github-copilot/claude-opus-4.6`
- variant: `high`
- scope: design, with Claude Code compatibility emphasis
- date: 2026-04-10

At the time of the second external review, the design remained sound and should
work with Claude Code as a worker CLI, but two items were still blocking before
implementation:

1. the lane registry still needed a committed write-safety mechanism
2. mailbox/report contracts still needed a single concrete event envelope and
   ordering rule

### New Blocking Findings

1. **No committed lane-registry write-safety mechanism**
   The plan acknowledges concurrent writers, but the contract set still does
   not pin down the actual mechanism. The reviewer recommends committing to
   advisory file locking plus stale-lock handling.

2. **Mailbox/report schema is still split**
   The report-back protocol has concrete event fields, but the mailbox contract
   does not yet commit to the same envelope or a canonical layout. The
   reviewer recommends one JSONL envelope for both mailbox and report events.

### New Non-Blocking Findings

1. lane id should resolve to spec id in v1 rather than remain open
2. lifecycle precedence should be formalized as an enum ordering
3. hook surface should stay extremely small in v1
4. delegated-work claim identity should be concrete
5. `011` should ship at least one real wrapper-capability entry early

### Claude Code Compatibility

The reviewer’s main conclusion was favorable:

- the mailbox/report queue model works with Claude Code
- delegated-work claims work with Claude Code
- tmux should remain optional and not be treated as the canonical runtime for
  Claude Code lanes
- Claude Code lanes would benefit from an explicit non-tmux deployment type
- mailbox path discovery should come from lane metadata, not hardcoded paths
- `007` handoff artifacts become especially important for long-lived Claude
  Code sessions
