# Process Self-Review — 001-orca-worktree-runtime

**Date**: 2026-04-09  
**Feature**: `001-orca-worktree-runtime`  
**Duration**: `97daf4f` → working tree on `001-orca-worktree-runtime`

## Scores

| Dimension | Score | Key Evidence |
|-----------|-------|-------------|
| Spec Fidelity | 5/5 | The implementation stayed within the declared shell-runtime scope and met the feature requirements without adding command integration work. |
| Plan Accuracy | 5/5 | The delivered files match the planned shape: shared shell library, runtime entrypoint, metadata templates, and protocol/README updates. |
| Task Decomposition | 4/5 | The task breakdown was usable and incremental, but the cleanup bug surfaced only during late manual verification rather than as an earlier explicit risk test. |
| Review Effectiveness | 3/5 | Manual verification found and fixed a real cleanup edge case, and the broken cross-review backend/guidance were patched, but a full external code critique still has not completed successfully. |
| Workflow Friction | 3/5 | The implementation itself was straightforward; most friction came from review-tooling drift, working-tree-vs-merge-base mismatch, and harness instability. |

## What Worked

- The feature boundary held. The implementation stayed at the runtime-helper layer rather than drifting into command integration.
- The repo-scoped registry decision was validated during implementation and aligned with the broader Orca command direction.
- Manual lifecycle verification was high-value. It caught the stale worktree admin-state cleanup issue before anything was committed.
- The branch and lane naming model stayed coherent with the delivery protocol. Disposable verification lanes followed the intended `<feature>-<lane>` pattern.

## What Didn't

- Cross-review did not function as intended on the first pass. Claude hung and Gemini failed because the backend CLI invocation was wrong.
- The documented `cross-review` scope detection was too commit-centric and missed active working-tree implementation unless the code was already committed.
- Reviewability of untracked implementation files is weaker than it should be. The stock flow does not naturally include them in code review.
- Self-review currently assumes it can dispatch improvement agents and commit follow-up fixes automatically. That is too aggressive for an in-progress dirty worktree.

## Lane And Delivery Evidence

- Lane boundaries were clear during verification. Two disposable lanes were created and retired without overlap.
- Lane metadata was treated as runtime truth during testing, then intentionally removed so the repo was left clean.
- No PR or lane-level delivery artifacts exist yet for this feature, so delivery evidence is limited to branch naming and local verification behavior.

## Process Improvements

- Keep manual lifecycle verification as a required gate for new runtime protocols, especially before the first commit of implementation code.
- Add an explicit "working tree review" step when code is intentionally uncommitted, rather than relying only on merge-base diff review.
- Treat cross-harness review as a real dependency with provider-specific smoke tests, not just as a downstream command doc.

## Extension Improvements

- Applied in current working tree: `commands/cross-review.md` now includes dirty working-tree and untracked-file review behavior in code scope.
- Applied in current working tree: `scripts/bash/crossreview-backend.py` now uses the installed Gemini CLI contract and returns structured timeout failures.
- Applied in current working tree: `commands/cross-review.md` and `config-template.yml` now push toward a non-current provider by default when possible.
- `commands/self-review.md`: require explicit opt-in before auto-dispatching improvement agents and commits in a dirty or unmerged feature branch.  
  Why: retrospective automation should not silently mutate the extension while the feature itself is still in flight.  
  Risk: HIGH.

## Deferred Improvements

- Add provider capability probes and timeout policy to the cross-review runtime before depending on it as a gating workflow step.
- Decide whether self-review should ever auto-commit command changes, or whether it should stop at actionable recommendations by default.

## Verification Update

- Medium-risk retrospective fixes were applied immediately after the first review pass.
- Backend smoke verification confirmed Gemini invocation now reaches the provider correctly and fails structurally on timeout instead of argument parsing.

## Community Extension Opportunities

- None identified from the current catalog evidence. The main friction points were inside Orca's own review tooling rather than missing third-party extensions.
