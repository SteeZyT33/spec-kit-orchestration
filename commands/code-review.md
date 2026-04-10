---
description: Implementation review command that validates code against spec artifacts, analyzes merge readiness, and records findings before PR feedback handling begins.
scripts:
  sh: scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks
  ps: scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks
handoffs:
  - label: Continue Implementation
    agent: speckit.implement
    prompt: Continue to the next implementation phase
  - label: Cross-Agent Code Review (optional)
    agent: speckit.orca.cross-review
    prompt: Run a cross-agent adversarial review of the implemented code
  - label: PR Review
    agent: speckit.orca.pr-review
    prompt: Process PR comments, review threads, and post-merge checks after code review
  - label: Re-Analyze Artifacts
    agent: speckit.analyze
    prompt: Re-analyze spec artifacts after review changes
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

This is the standard implementation review pass.

Use `/speckit.orca.code-review` to:

- validate implementation against `spec.md`, `plan.md`, and `tasks.md`
- detect merge-readiness and integration risks
- run spec compliance, code quality, security, and optional product critique passes
- apply tiered review actions
- append the result to `FEATURE_DIR/review.md`

This command does **not** own GitHub comment response workflows. External PR
feedback is handled by `/speckit.orca.pr-review`.

## Pre-Execution Checks

**Check for extension hooks (before review)**:
- Check if `.specify/extensions.yml` exists in the project root.
- If it exists, read it and look for entries under the `hooks.before_review` key
- If the YAML cannot be parsed or is invalid, skip hook checking silently and continue normally
- Filter out hooks where `enabled` is explicitly `false`. Treat hooks without an `enabled` field as enabled by default.
- For each remaining hook, do **not** attempt to interpret or evaluate hook `condition` expressions:
  - If the hook has no `condition` field, or it is null/empty, treat the hook as executable
  - If the hook defines a non-empty `condition`, skip the hook and leave condition evaluation to the HookExecutor implementation
- For each executable hook, output the following based on its `optional` flag:
  - **Optional hook** (`optional: true`):
    ```
    ## Extension Hooks

    **Optional Pre-Hook**: {extension}
    Command: `/{command}`
    Description: {description}

    Prompt: {prompt}
    To execute: `/{command}`
    ```
  - **Mandatory hook** (`optional: false`):
    ```
    ## Extension Hooks

    **Automatic Pre-Hook**: {extension}
    Executing: `/{command}`
    EXECUTE_COMMAND: {command}

    Wait for the result of the hook command before proceeding to the Outline.
    ```
- If no hooks are registered or `.specify/extensions.yml` does not exist, skip silently

## Outline

1. Run `{SCRIPT}` from repo root and parse `FEATURE_DIR` and `AVAILABLE_DOCS`.

2. Parse arguments:
   - `--security`: force the security pass
   - `--critique`: add product strategy + engineering risk critique
   - `--evidence`: capture proof artifacts in `FEATURE_DIR/evidence/`
   - `--parallel`: run review as a background agent
   - `--phase N`: review a specific phase
   - any remaining text: additional review focus

3. Load review context from `FEATURE_DIR`:
   - **REQUIRED**: `spec.md`
   - **REQUIRED**: `plan.md`
   - **REQUIRED**: `tasks.md`
   - **IF EXISTS**: `contracts/`
   - **IF EXISTS**: `data-model.md`
   - **IF EXISTS**: `research.md`
   - **IF EXISTS**: existing `review.md`
   - If required artifacts are missing, report reduced coverage and continue.

   Resolve implementation handoff context when available:

   ```bash
   uv run python -m speckit_orca.context_handoffs resolve \
     --feature-dir "$FEATURE_DIR" \
     --source-stage implement \
     --target-stage code-review \
     --format json
   ```

   If no explicit handoff exists, continue using the helper's artifact-only
   fallback and report that review context was inferred.

4. Determine the target phase from `tasks.md`.

5. Detect Orca lane context:
   - read `.specify/orca/worktrees/registry.json` if present
   - capture lane ID, branch, `task_scope`, and status when the current branch or working tree matches
   - otherwise continue as feature-wide review

6. Check for agent assignments in `tasks.md` via `[@agent-name]` markers.

7. Check merge conflicts against the target branch.
   - Skip when the user is not reviewing code yet
   - classify conflicts using the merge protocol below
   - record results in the review output

## Merge Conflict Resolution Protocol

When conflicts are detected, classify each file into one of four tiers.

### Tier 1: Auto-Regenerate

Derived artifacts should be regenerated rather than manually merged.

### Tier 2: Auto-Resolve by Owner

Use ownership rules for vendor files, feature artifacts, and clearly-owned files.

### Tier 3: Auto-Merge with Verification

If changes are non-overlapping, merge the union and verify with tests/formatters.

### Tier 4: Flag for Human Review

Never auto-resolve overlapping business logic, auth/security code, migrations,
or any conflicting logic that requires judgment.

If Tier 4 conflicts remain, mark the review as merge-blocked.

## Lane And Delivery Context

When lane metadata exists, include:

```text
### Lane Context

Lane: {lane_id}
Lane Branch: {lane_branch}
Lane Status: {lane_status}
Task Scope: {task_scope}
Review Scope: feature-wide (lane-aware reporting only)
```

Also flag:

- lane touched files that appear outside declared `task_scope`
- undeclared shared-file edits across multiple active lanes
- lane branch targeting the wrong integration branch

## Review Passes

Run these passes sequentially and produce findings with file:line references.

### Pass 1 — Spec Compliance

- verify acceptance scenarios from `spec.md`
- verify functional requirements and user stories
- verify contracts alignment when contracts exist
- verify data model alignment when `data-model.md` exists
- report scope creep

### Pass 2 — Code Quality

- verify architecture alignment with `plan.md`
- verify file organization and module placement
- report obvious bugs, dead code, and missing error handling
- report plan deviations

### Pass 3 — Security

Run when:

- `--security` is passed
- or the feature clearly touches auth, secrets, PII, payment, privacy, or external APIs

Check:

- OWASP-style boundary risks
- auth/authz correctness
- input validation
- secrets handling

### Pass 4 — Product Critique

Run only with `--critique`.

Evaluate product fit, user value, alternatives, UX edge cases, success metrics,
failure modes, operational burden, dependency risk, migration risk, and testing gaps.

### Evidence Capture

Run only with `--evidence`.

- create `FEATURE_DIR/evidence/`
- capture screenshots, API responses, CLI output, or test output as appropriate
- record an evidence manifest and link it from `review.md`

## Tiered Fix Behavior

After all passes:

### Tier 1: Auto-Fix

Apply trivial, unambiguous, low-risk fixes and record them in `review.md`.

### Tier 2: Suggest-Fix

Present non-trivial but clear fixes and wait for explicit approval.

### Tier 3: Flag-Only

Record judgment-heavy findings without changing code.

## Review Report Output

Append a new section to `FEATURE_DIR/review.md`. Never overwrite previous reviews.

Each section should include:

```markdown
## Phase N Review — YYYY-MM-DD

### Merge Conflicts: PASS | FAIL
- [conflict report]

### Lane Context
- [lane metadata if present]

### Spec Compliance: PASS | FAIL
- [findings]

### Code Quality: PASS | FAIL
- [findings]

### Security: PASS | FAIL | SKIPPED
- [findings]

### Product Critique: PASS | FINDINGS | SKIPPED
- [findings]

### Actions Taken
- AUTO-FIXED: [count]
- SUGGESTED: [count]
- FLAGGED: [count]

### Delivery Readiness
- Merge target: [feature branch | main]
- Ready for PR review: yes | no
```

If no issues are found in a section, write `- No issues found.`

## PR Boundary

This command stops at implementation review and delivery readiness.

After `review.md` is written:

- if the code is not ready, continue implementation
- if the code is ready for external feedback, move to `/speckit.orca.pr-review`

Use `/speckit.orca.pr-review` for:

- PR creation/update workflow
- external reviewer comments
- comment dispositions (`ADDRESSED`, `REJECTED`, `ISSUED`, `CLARIFY`)
- review thread resolution
- post-merge verification

## Parallel Mode (`--parallel`)

When `--parallel` is passed:

1. Detect active agent from `.specify/init-options.json`
2. Dispatch based on agent:
   - `claude`: use a subagent or tmux session
   - `codex`: use a background sandbox task
   - otherwise fall back to blocking mode
3. On completion:
   - write `review.md`
   - post inbox notification if available
   - summarize any critical findings

## Completion

After all steps complete:

1. Output:
   - pass/fail status for each review pass
   - count of auto-fixes, suggest-fixes, and flagged issues
   - path to `review.md`
   - whether the implementation is ready for `/speckit.orca.pr-review`

2. Check `.specify/extensions.yml` for `hooks.after_review` and surface any optional or mandatory hooks.
