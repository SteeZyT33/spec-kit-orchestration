---
description: PR review command that manages GitHub review feedback, comment dispositions, thread resolution, and post-merge verification after code review is complete.
scripts:
  sh: scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks
  ps: scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks
tools:
  - 'github/github-mcp-server/issue_write'
  - 'github/github-mcp-server/create_pull_request'
  - 'github/github-mcp-server/pull_request_review_write'
handoffs:
  - label: Run Code Review
    agent: speckit.orca.code-review
    prompt: Re-run implementation review before handling external PR feedback
  - label: Cross-Harness Code Review (optional)
    agent: speckit.orca.cross-review
    prompt: Run a cross-harness adversarial review before responding to PR feedback
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

Use `/speckit.orca.pr-review` after implementation has already been reviewed.

This command owns:

- PR creation and update flow
- GitHub tool availability checks
- external reviewer comment processing
- comment disposition tracking
- review thread resolution
- post-merge verification

This command does **not** replace `/speckit.orca.code-review`. Run code review
first unless the task is explicitly `--comments-only` or `--post-merge`.

## Outline

1. Run `{SCRIPT}` from repo root and parse `FEATURE_DIR` and `AVAILABLE_DOCS`.

2. Parse arguments:
   - `--comments-only`: skip code-quality review work and process only new PR comments
   - `--post-merge`: run post-merge verification only
   - `--phase N`: target a specific phase
   - any remaining text: additional PR review focus

3. Load the existing review context:
   - read `review.md` if it exists
   - read `tasks.md` for phase boundaries and target phase
   - prefer shared flow-state output for artifact-first stage and review-milestone context when available
   - detect Orca lane context from `.specify/orca/worktrees/registry.json` if present
   - note whether the current work is lane-associated or feature-wide

4. Check GitHub tool availability.
   - If unavailable, report that PR review automation cannot proceed and stop after writing local notes.

## PR Lifecycle

### Step 1: Ensure PR Context Exists

- Check for an existing PR for the current phase or branch
- If none exists and the code is review-ready, create one
- Avoid duplicate PRs for the same phase/branch

Suggested shape:

- title: `Phase N: [phase name] — [feature branch name]`
- body: summary from the latest code review section
- labels: phase number and review status if supported

### Step 2: Verify Delivery Hygiene

Before pushing any follow-up changes:

- run pre-commit hooks locally
- verify the same checks CI will run
- never bypass hooks with `--no-verify`
- never “fix” CI by weakening CI configuration

### Step 3: Comment Response Protocol

Every PR comment gets exactly one disposition:

| Status | Format | When to Use |
|--------|--------|-------------|
| ADDRESSED | `ADDRESSED in [commit SHA] — [brief description of fix]` | Fix applied and pushed |
| REJECTED | `REJECTED — [reason with evidence from spec/plan/review]` | Comment is incorrect or conflicts with intended design |
| ISSUED | `ISSUED #[issue number] — [why deferred]` | Valid but intentionally deferred |
| CLARIFY | `CLARIFY — [specific question]` | Comment is ambiguous |

Rules:

- no silent fixes
- prefer fixing now over deferring
- every deferment needs a real issue or equivalent recorded follow-up
- every `CLARIFY` must later resolve into one of the other three statuses

### Step 4: Batch-Reject Detection

If 3 or more rejections share the same exclusion path pattern, offer a batch
rejection path.

If `FEATURE_DIR/review-exclusions.md` exists, use it to auto-reject comments on
declared exclusion paths.

### Step 5: Reviewer Profile Awareness

Track reviewer tendencies so false positives are contextualized, but still give
every comment an explicit disposition.

### Step 6: Deferred Fix Protocol

For each `ISSUED` comment:

- create a GitHub issue when tools are available
- otherwise record the same information in `review.md`

### Step 7: Conversation Thread Resolution

After all comments are dispositioned, resolve review threads when possible via:

```bash
bash scripts/bash/resolve-pr-threads.sh
```

Leave `CLARIFY` threads open.

## Post-Merge Verification

When `--post-merge` is passed, or when explicitly running post-merge checks:

1. Diff merged `main` against the last reviewed commit
2. Detect silent reversions of reviewed fixes
3. Record the result under `### Post-Merge Verification` in `review.md`
4. Create an issue immediately for critical reversions

## Output Contract

Update or append to `FEATURE_DIR/review.md` with PR-focused sections such as:

```markdown
### PR: #[number] — [status]
- Comments: [total] | Addressed: [n] | Rejected: [n] | Issued: [n] | Clarify: [n]

### External Comment Responses
| # | Reviewer | File | Status | Detail |
|---|---------|------|--------|--------|

### Post-Merge Verification
- REVERTED: [count] | OK: [count] | Issues created: [issue numbers]
```

When lane metadata exists, also note:

- lane ID
- lane branch
- whether the PR is lane-local or feature-wide

## Completion

Output:

- PR number and URL if available
- comment disposition counts
- whether any review threads remain open
- post-merge verification result when applicable
- path to `review.md`
