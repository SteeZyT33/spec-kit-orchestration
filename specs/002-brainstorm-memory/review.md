# Review — 002-brainstorm-memory

## Cross-Review — 2026-04-09

**Requested scope**: implementation  
**Effective review input**: `src/speckit_orca/brainstorm_memory.py`,
`commands/brainstorm.md`, `README.md`,
`templates/brainstorm-record-template.md`, and the `002` spec artifacts  
**Reviewer**: `opencode` (manual run) plus local code review

### Summary

The implementation is now in good shape. The first cross-review pass found two
real helper bugs and one real command/runtime gap:

- partial brainstorm saves were blocked by overly strict validation
- illegal state regressions were not enforced
- the brainstorm command did not explicitly tell agents to use the deterministic
  helper

Those issues were fixed in the worktree and re-verified.

### Findings Applied

- `HIGH` [brainstorm_memory.py](/home/taylor/spec-kit-orca-002-brainstorm-memory-impl/src/speckit_orca/brainstorm_memory.py):
  relaxed validation so records require canonical headings and metadata, not
  fully populated content in every section. This restores support for
  meaningful-but-incomplete parked sessions.
- `MEDIUM` [brainstorm_memory.py](/home/taylor/spec-kit-orca-002-brainstorm-memory-impl/src/speckit_orca/brainstorm_memory.py):
  added explicit state-transition validation so forbidden regressions such as
  `spec-created -> active` are rejected.
- `MEDIUM` [brainstorm_memory.py](/home/taylor/spec-kit-orca-002-brainstorm-memory-impl/src/speckit_orca/brainstorm_memory.py):
  replaced fragile overview-root derivation with `root_from_record_path()`,
  which validates that records live under `brainstorm/`.
- `HIGH` [brainstorm.md](/home/taylor/spec-kit-orca-002-brainstorm-memory-impl/commands/brainstorm.md):
  documented the concrete helper invocation path for `create`, `matches`,
  `update`, and `regenerate-overview`.
- `LOW` [README.md](/home/taylor/spec-kit-orca-002-brainstorm-memory-impl/README.md):
  added direct helper CLI examples for contributors and local verification.
- `MEDIUM` [test_brainstorm_memory.py](/home/taylor/spec-kit-orca-002-brainstorm-memory-impl/tests/test_brainstorm_memory.py):
  added automated regression coverage for partial saves, illegal transitions,
  root validation, and overview rendering.

### Residual Risks

- Feature-refinement mode (`specs/<feature>/brainstorm.md`) and the inbox
  fallback remain command-driven rather than helper-driven. That matches the
  current plan, but it means only durable `brainstorm/` memory has deterministic
  runtime enforcement in `002`.
- Overlap detection is still simple slug-token matching. That is acceptable for
  first version but should not be treated as semantic recall.

### Verification

- `uv run python -m py_compile src/speckit_orca/brainstorm_memory.py`
- `uv run --with pytest pytest tests/test_brainstorm_memory.py`
- `uv run --with build python -m build`
- `git diff --check`
- manual temp-dir smoke checks for create, inspect, update, downstream link,
  partial parked save, and overview recovery

### Outcome

- No blocking findings remain for `002` in this worktree.
- The feature is ready for commit after final status cleanup.
