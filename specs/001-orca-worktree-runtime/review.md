# Review — 001-orca-worktree-runtime

## Cross-Harness Review — 2026-04-09

**Requested scope**: code  
**Effective review input**: working-tree diff plus untracked implementation files  
**Harness attempts**:

- `claude` via `scripts/bash/crossreview.sh`: invocation hung and did not produce a JSON artifact in a reasonable time window.
- `gemini` via `scripts/bash/crossreview.sh`: produced a structured failure artifact at `.shared/crossreview-gemini-2026-04-09T10-37-56.json`.

### Summary

No substantive external code findings were returned because the initial
cross-harness tooling failed before a real review completed. That failure
exposed reliability issues in the review pipeline itself. The Gemini launcher
and working-tree review guidance have since been patched, but a full successful
external adversarial review has still not been completed for this feature.

### Blocking

- Fixed in current working tree: [scripts/bash/crossreview-backend.py](/home/taylor/spec-kit-orca/scripts/bash/crossreview-backend.py#L99) The Gemini launcher was broken. It now uses the installed CLI contract and returns a structured timeout payload during smoke verification instead of a usage error.
- Fixed in current working tree: [commands/cross-review.md](/home/taylor/spec-kit-orca/commands/cross-review.md#L51) The code-scope logic was merge-base-only and missed dirty working-tree implementation. The command guidance now explicitly includes working-tree diffs and untracked files in code scope.

### Non-Blocking

- [commands/cross-review.md](/home/taylor/spec-kit-orca/commands/cross-review.md#L35) The default review harness remains `codex`, which is not cross-harness when the active integration is already Codex. The command should prefer a different installed harness by default or warn when the selected harness matches the current provider.
- [commands/cross-review.md](/home/taylor/spec-kit-orca/commands/cross-review.md#L49) The command assumes the backend will resolve CLI behavior differences cleanly, but current launcher behavior varies materially by provider. The command needs an explicit fallback path when the backend returns a structured harness failure.

### Follow-Up Verification

- `python3 scripts/bash/crossreview-backend.py --harness gemini --timeout 1 ...` now returns a structured timeout payload rather than the previous Gemini CLI usage error.
- A full successful external review is still pending because provider runtime availability and rate limits remain outside this patch.

### Outcome

- External adversarial review of the worktree runtime implementation was not completed.
- The review attempt still produced actionable findings about the reliability of Orca's own cross-review tooling.
