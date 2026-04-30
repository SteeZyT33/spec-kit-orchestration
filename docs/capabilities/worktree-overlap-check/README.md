# worktree-overlap-check

Detects path conflicts between active worktrees and against proposed writes. Pure Python; no git invocation, no LLM. Caller passes pre-collected worktree info.

## Use case

Perf-lab's `lease.sh` shells out here instead of reimplementing overlap detection. Returns `safe: false` when any two worktrees claim overlapping paths, or when a `proposed_writes` entry is already claimed.

## Path matching

Exact path equality OR directory-prefix containment. `src/foo/` overlaps `src/foo/bar.py`. Comparison uses POSIX path semantics (`PurePosixPath`).

**Path traversal (`..`) is rejected as INPUT_INVALID** since legitimate worktree claims should be repo-relative without traversal.

**All paths are interpreted as POSIX.** Windows callers must normalize before invoking.

## Input

See `schema/input.json`. Each `worktree` has `path` (required), optional `branch`, `feature_id`, `claimed_paths`. A worktree with `claimed_paths: []` is implicitly safe (nothing to conflict with).

## Output

See `schema/output.json`.

- `conflicts[].paths` lists ALL distinct paths involved in the overlap. For exact equality, length 1. For prefix containment, length 2 with broader path first, more-specific second.
- `conflicts[].worktrees` lists the two worktrees with overlapping claims.
- `proposed_overlaps[].blocked_by` lists ALL worktrees blocking each proposed write (not just the first).

## CLI

`orca-cli worktree-overlap-check` (reads JSON from stdin or `--input <file>`)

## Library

`from orca.capabilities.worktree_overlap_check import worktree_overlap_check, WorktreeOverlapInput, WorktreeInfo`
