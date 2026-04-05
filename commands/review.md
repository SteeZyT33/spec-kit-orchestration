---
description: Post-implementation review command that validates code against spec artifacts, applies tiered fixes, creates phase PRs, and manages the GitHub review cycle.
scripts:
  sh: scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks
  ps: scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks
tools:
  - 'github/github-mcp-server/issue_write'
  - 'github/github-mcp-server/create_pull_request'
  - 'github/github-mcp-server/pull_request_review_write'
handoffs:
  - label: Continue Implementation
    agent: speckit.implement
    prompt: Continue to the next implementation phase
  - label: Cross-Harness Code Review (optional)
    agent: speckit.crossreview
    prompt: Run a cross-harness adversarial review of the implemented code
  - label: Re-Analyze Artifacts
    agent: speckit.analyze
    prompt: Re-analyze spec artifacts after review changes
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

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

1. Run `{SCRIPT}` from repo root and parse FEATURE_DIR and AVAILABLE_DOCS list. All paths must be absolute. For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot").

2. **Parse arguments** from user input:
   - `--security`: Force security pass regardless of spec content
   - `--parallel`: Run review as background agent (see Parallel Mode section)
   - `--phase N`: Review a specific phase (default: current/latest completed phase)
   - `--comments-only`: Skip all review passes (spec compliance, code quality, security). Jump directly to the Comment Response Protocol for new PR comments. Use when self-review already passed and only external reviewer comments need responses.
   - `--post-merge`: Run post-merge verification only — diff merged main against last reviewed commit to detect silent reversions by linters, auto-formatters, or post-merge hooks.
   - Any remaining text: Additional context or focus area for the review

3. **Load review context** — read from FEATURE_DIR:
   - **REQUIRED**: Read `spec.md` for acceptance scenarios, functional requirements, and success criteria
   - **REQUIRED**: Read `plan.md` for architecture decisions, file structure, and project organization
   - **REQUIRED**: Read `tasks.md` for phase boundaries, task dependencies, and current phase status
   - **IF EXISTS**: Read `contracts/` for API specifications, data formats, and interface contracts
   - **IF EXISTS**: Read `data-model.md` for entity definitions and relationships
   - **IF EXISTS**: Read `research.md` for technical decisions and constraints
   - **IF EXISTS**: Read `review.md` for previous phase review history (will be appended to)
   - If any REQUIRED artifact is missing, report which artifacts are missing. Still run passes against available artifacts but clearly note reduced coverage in the output.

4. **Determine current phase** from tasks.md:
   - Scan task checkboxes to identify the most recently completed phase
   - If `--phase N` is specified, use that phase instead
   - Identify which tasks belong to the target phase and what code they produced

5. **Check for agent assignments** (Spec 002 integration — conditional):
   - If tasks.md contains `[@agent-name]` markers on task lines, note which agent implemented each task
   - This provides context for review feedback (e.g., "The frontend task assigned to [@Frontend Developer] has...")
   - If no agent markers are present, proceed without this context

6. **Check for merge conflicts** against the target branch:

   Run a dry-run merge to detect conflicts. The working tree must be clean first (this command modifies the index):
   ```bash
   # Stash any uncommitted changes before the dry-run
   git stash --include-untracked -q 2>/dev/null
   STASHED=$?

   git merge --no-commit --no-ff main 2>&1
   MERGE_STATUS=$?
   git merge --abort 2>/dev/null

   # Restore stashed changes
   [[ $STASHED -eq 0 ]] && git stash pop -q 2>/dev/null
   ```

   **If no conflicts** (`MERGE_STATUS == 0`): proceed silently (no output needed).

   **If conflicts exist** (`MERGE_STATUS != 0`): classify each conflicting file using the Merge Conflict Resolution Protocol below, then continue with review passes.

   **Skip this check when**:
   - `--comments-only` is passed (no review passes run)
   - `--post-merge` is passed (already merged)

### Merge Conflict Resolution Protocol

When conflicts are detected, classify each conflicting file into one of four tiers. Apply tiers in order — check Tier 1 first, then Tier 2, etc.

#### Tier 1: Auto-Regenerate (regenerate from source — never manually merge)

These files are derived artifacts. Merging their text is meaningless — regenerate them after resolving all other conflicts.

| Pattern | Action |
|---------|--------|
| `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml` | Delete the file, run the package manager install command (`npm install`, `yarn install`, `pnpm install`) to regenerate |
| `poetry.lock`, `Pipfile.lock` | Delete the file, run `poetry lock` or `pipenv lock` to regenerate |
| `*.schema.json` (generated), `*.min.js`, `*.min.css` | Rebuild from source (`npm run build` or equivalent) |
| `go.sum` | Run `go mod tidy` |

**Commit message**: `fix(merge): regenerate [filename] after conflict resolution`

#### Tier 2: Auto-Resolve by Owner (one side always wins)

These files have a clear owner. No manual inspection needed.

| Pattern | Strategy | Rationale |
|---------|----------|-----------|
| `.specify/scripts/*` | Accept **theirs** (main) | Vendor code — upstream owns it |
| `.specify/templates/*` | Accept **theirs** (main) | Upstream templates are canonical |
| `specs/NNN-*/*` (our feature dir) | Accept **ours** (branch) | Our feature artifacts — we own them |
| Files that exist only on our branch | Accept **ours** | New files we created |
| `CHANGELOG.md`, `VERSION`, `pyproject.toml` (version only) | Accept **theirs**, then append/update ours on top | Upstream version is the base; our additions go after |

**Resolution commands**:
```bash
# Accept theirs for a file:
git checkout --theirs <file> && git add <file>

# Accept ours for a file:
git checkout --ours <file> && git add <file>
```

**Commit message**: `fix(merge): resolve [filename] — accept [theirs|ours] ([rationale])`

#### Tier 3: Auto-Merge with Verification (both sides changed, but in different regions)

When git reports a conflict but the changes are in **non-overlapping regions** of the file (e.g., we added a function at line 50, they modified a function at line 200):

- Apply both changes (accept the union)
- Run the file through its linter/formatter to verify syntax
- Run relevant tests to verify correctness
- If tests pass: commit
- If tests fail: escalate to Tier 4

**Commit message**: `fix(merge): merge non-overlapping changes in [filename]`

#### Tier 4: Flag for Human Review (overlapping logic, judgment required)

Conflicts that require human judgment. **Never auto-resolve these.**

| Condition | Why |
|-----------|-----|
| Same function/method modified on both sides | Intent may conflict |
| Conflicting imports or dependency versions | Compatibility unknown |
| Auth, security, or permissions code | Risk too high for auto-resolve |
| Database schemas or migrations | Data integrity at stake |
| CI/CD configuration files | Could break the pipeline for everyone |
| Test assertions that contradict each other | Indicates divergent intent |
| Any file where both sides changed the same line range | Can't determine correct merge without understanding context |

**Output for Tier 4 conflicts**:
```
### Merge Conflicts Requiring Human Review

| File | Lines | Ours | Theirs | Risk |
|------|-------|------|--------|------|
| src/api/auth.py | 42-58 | Added rate limiting | Changed token format | HIGH — security code |
| src/models/user.py | 10-15 | Added email field | Renamed username field | MEDIUM — data model |

**Action required**: Resolve these conflicts manually, then re-run `/speckit.review`.
```

#### Conflict Resolution Output

After classifying all conflicts, output a summary and record in review.md:

```
## Merge Conflict Report

**Branch**: [branch] ↔ main
**Total conflicts**: N files

| File | Tier | Resolution | Status |
|------|------|------------|--------|
| package-lock.json | 1 — Regenerate | `npm install` | RESOLVED |
| .specify/scripts/check.sh | 2 — Accept theirs | Upstream owns | RESOLVED |
| specs/004-feature/tasks.md | 2 — Accept ours | Our feature | RESOLVED |
| src/utils/helpers.py | 3 — Auto-merge | Non-overlapping regions | RESOLVED |
| src/api/auth.py | 4 — Human review | Overlapping security code | PENDING |

**Auto-resolved**: X files | **Pending human review**: Y files
```

- If any Tier 4 conflicts remain PENDING: add `### Merge Conflicts: FAIL` to the review output. Mark findings against those files as `[CONFLICT ZONE]` in the review passes. Warn in PR Lifecycle that the PR will not be mergeable.
- If all conflicts are resolved (Tiers 1-3 only): add `### Merge Conflicts: PASS (N conflicts auto-resolved)` and proceed normally. Create a single merge resolution commit before running review passes.
- If no conflicts existed: `### Merge Conflicts: PASS`

## Comments-Only Mode

If `--comments-only` was passed, skip the Review Passes section entirely. Continue with **PR Lifecycle Step 1 (GitHub tool availability check)**, then proceed to **Step 4: Comment Response Protocol**. Load the existing PR (from the current branch or specified in arguments) and process only new, unresponded comments. If GitHub tools are unavailable, output "GitHub tools not available — cannot process PR comments in comments-only mode." and stop.

This mode exists because the common pattern after initial self-review is: external reviewers (Copilot, CodeRabbit, human reviewers) leave comments that need responses without re-reviewing the entire implementation.

## Review Passes

If `--comments-only` was NOT passed, execute these three passes sequentially. For each pass, produce findings with file:line references.

### Pass 1 — Spec Compliance (always runs)

Review the implemented code against spec.md:

- **Acceptance scenarios**: For each user story acceptance scenario in spec.md, verify the implementation satisfies it. Report any scenario that is not met, quoting the specific scenario.
- **Functional requirements**: For each FR-### in spec.md, verify the implementation addresses it. Report unimplemented or partially implemented requirements.
- **Contracts alignment**: If contracts/ exists, verify the implementation matches the defined interfaces (endpoints, schemas, formats).
- **Data model alignment**: If data-model.md exists, verify entities, fields, and relationships match the implementation.
- **Scope creep detection**: Identify any implemented features or behaviors that are NOT specified in spec.md. Report them as potential scope creep.

Output: `### Spec Compliance: PASS` or `### Spec Compliance: FAIL` with itemized findings.

### Pass 2 — Code Quality (always runs)

Review the implemented code against plan.md:

- **Architecture alignment**: Verify the code structure matches plan.md's project structure and architecture decisions.
- **File organization**: Verify files are in the locations specified by plan.md.
- **Obvious bugs**: Identify clear bugs, dead code, or missing error handling that the spec required.
- **Plan deviations**: Report any deviations from plan.md's technical decisions (e.g., different framework, different data storage).

Output: `### Code Quality: PASS` or `### Code Quality: FAIL` with itemized findings.

### Pass 3 — Security (conditional)

Runs when ANY of these conditions are met:
- `--security` flag is passed
- spec.md mentions authentication, authorization, login, password, token, OAuth, API key
- spec.md mentions payment, billing, credit card, financial
- spec.md mentions personal data, PII, GDPR, privacy, user data
- spec.md mentions external API, webhook, third-party integration

When this pass runs, check:

- **OWASP top 10**: Scan for common vulnerabilities (injection, broken auth, sensitive data exposure, etc.)
- **Auth/authz**: Verify authentication and authorization match spec requirements
- **Input validation**: Verify all system boundary inputs are validated
- **Secrets handling**: Verify no hardcoded secrets, API keys, or credentials. Verify environment variables are used properly.

When this pass is skipped, output: `### Security: SKIPPED`

Output: `### Security: PASS` or `### Security: FAIL` with itemized findings.

## Tiered Fix Behavior

After all three passes complete, process findings by tier:

### Tier 1: Auto-Fix (trivial, unambiguous, low risk)

For each finding that is trivial and unambiguous:
- Apply the fix
- Create a separate commit with message: `fix(review): [brief description] — auto-fix from /speckit.review`
- Record in review.md: the finding, the fix, and the commit SHA

Examples of auto-fixable issues:
- Missing error handling that the spec explicitly required
- Import cleanup (unused imports, missing imports)
- Naming inconsistencies with the plan (e.g., function named `getUser` but plan says `fetchUser`)
- Missing type annotations that the plan specified

### Tier 2: Suggest-Fix (medium complexity, clear solution)

For each finding with a clear but non-trivial solution:
- Present the finding and a proposed diff to the user
- **Wait for explicit approval** before applying
- If approved: apply, commit, record in review.md
- If rejected: record as flagged in review.md, no code change

Examples of suggest-fix issues:
- Restructuring a function to match plan architecture
- Adding missing validation logic
- Refactoring to match specified patterns

### Tier 3: Flag-Only (judgment call needed)

For each finding that requires human judgment:
- Report in review.md with full context
- Do NOT make any code changes
- These may become PR comments for discussion

Examples of flag-only issues:
- Missing feature or user story
- Architectural drift from plan
- Security concerns requiring design decisions
- Performance issues requiring tradeoff decisions

## Review Report Output

After all passes and fixes, write to `FEATURE_DIR/review.md`. If the file exists, **append** a new section. Never overwrite previous phase reviews.

Use this structure for each phase section:

```markdown
## Phase N Review — YYYY-MM-DD

### Merge Conflicts: PASS | FAIL
- [conflict report — files, tiers, resolution status]

### Spec Compliance: PASS | FAIL
- [findings with file:line references]

### Code Quality: PASS | FAIL
- [findings with file:line references]

### Security: PASS | FAIL | SKIPPED
- [findings with file:line references]

### Actions Taken
- AUTO-FIXED: [count] issues ([commit SHAs])
- SUGGESTED: [count] issues ([accepted/pending/rejected])
- FLAGGED: [count] issues
- ISSUED: [count] issues ([issue numbers])

### PR: #[number] — [status]
- Comments: [total] | Addressed: [n] | Rejected: [n] | Issued: [n] | Clarify: [n]
- Batch-rejected: [count] ([path pattern])

### External Comment Responses
| # | Reviewer | File | Status | Detail |
|---|---------|------|--------|--------|
| 1 | copilot-pull-request-reviewer | src/api.py:42 | ADDRESSED | Fixed in abc1234 |
| 2 | coderabbitai[bot] | .specify/scripts/common.sh | REJECTED | Vendor code (batch) |

### Post-Merge Verification
- REVERTED: [count] | OK: [count] | Issues created: [issue numbers]
```

If no issues are found in a pass, report: `- No issues found.`

## PR Lifecycle

After review.md is written and all fixes are committed:

**Step 1: Check GitHub tool availability**

Attempt to use GitHub MCP tools. If unavailable, output: "GitHub tools not available — review.md produced, PR creation skipped." Skip to the extension hooks section.

**Step 2: Create phase PR** (one per phase, not per feature)

- **Check for existing PR**: If a PR already exists for this phase/branch, update it instead of creating a duplicate.
- **Title**: `Phase N: [phase name from tasks.md] — [feature branch name]`
- **Body**: Include review.md summary for this phase, pass/fail table, list of auto-fixes with commit SHAs.
- **Labels**: Add phase number and review status labels if the repository supports them.

**Step 3: Verify pre-commit hooks and CI locally**

Before pushing any fix commits:
- Run all pre-commit hooks locally and verify they pass
- If hooks fail, fix the issue and re-commit — do NOT skip hooks with `--no-verify`

After pushing:
- Monitor CI pipeline status
- If CI fails:
  1. Pull CI logs and diagnose the failure
  2. Fix the issue **locally**
  3. Verify the fix passes **locally** (run the same checks CI runs)
  4. Push the corrected fix
  5. Repeat until CI passes
- **NON-NEGOTIABLE**: Never modify CI configuration, workflow files, or hook configuration to achieve a pass. Fix the actual code problem.

**Step 4: Comment Response Protocol**

When processing PR comments (from other contributors, reviewers, or automated systems), respond to **every** comment with exactly one status:

| Status | Format | When to Use |
|--------|--------|-------------|
| ADDRESSED | `ADDRESSED in [commit SHA] — [brief description of fix]` | Fix applied and pushed |
| REJECTED | `REJECTED — [reason with evidence from spec/plan]` | Comment conflicts with spec/plan or is incorrect |
| ISSUED | `ISSUED #[issue number] — [why deferred, with actual reason]` | Valid but out of scope for current phase |
| CLARIFY | `CLARIFY — [specific question]` | Comment is ambiguous, needs more context |

**Rules**:
- Every comment gets exactly one response. No exceptions. No silent fixes.
- Always prefer fixing immediately over deferring. If the fix is clear, just do it (ADDRESSED).
- Never say "noted for later" without creating an issue. If deferring, always use ISSUED with a real GitHub issue.
- After a CLARIFY response is answered, follow up with ADDRESSED, REJECTED, or ISSUED.

**Batch-Reject Detection**:

When processing comments, if **3 or more rejections share a file path pattern** (e.g., `.specify/scripts/*`, `docs/research/*`), offer batch rejection:

```
Detected pattern: 6 comments target .specify/scripts/* (vendor code)
Batch reject all with: "REJECTED — vendor code managed upstream by spec-kit"? [y/N]
```

If `FEATURE_DIR/review-exclusions.md` exists, read it for pre-declared exclusion paths:
```markdown
<!-- review-exclusions.md -->
- .specify/scripts/* — vendor code, upstream responsibility
- docs/research/* — salvaged reference material, not production code
```

Comments targeting files matching a declared exclusion path are auto-rejected with the documented reason. The user is informed but not prompted.

**Reviewer Profile Awareness**:

Track which external reviewer submitted each comment and note their typical focus areas to contextualize responses:

| Reviewer | Typical Focus | Common False Positives |
|----------|--------------|----------------------|
| copilot-pull-request-reviewer | Error handling, input validation, type safety | Vendor code, reference material |
| coderabbitai[bot] | Architecture, documentation, naming conventions | Salvaged historical content, generated files |

When a comment matches a reviewer's known false-positive pattern AND targets an exclusion path, this strengthens the batch-reject case. Reviewer profiles are advisory — every comment still gets an individual response.

**Step 5: Deferred Fix Protocol**

For every ISSUED response, create a GitHub issue containing:
- Title: descriptive of the deferred issue
- Body:
  - Link to the original PR comment
  - Which spec and phase it relates to
  - Why it was deferred (an actual reason — not "noted for later")
  - Suggested approach if known
- When GitHub tools are unavailable: record the same information in review.md under the Actions Taken section with `ISSUED:` prefix.

**Step 6: Conversation Thread Resolution**

If branch protection requires conversation resolution before merge, all review threads must be resolved. After responding to all comments, invoke the thread resolution script:

```bash
bash scripts/bash/resolve-pr-threads.sh
```

This script:
1. Gets the current branch's PR number via `gh pr view --json number`
2. Queries all unresolved threads via GraphQL
3. For each thread, checks if the last reply starts with ADDRESSED, REJECTED, or ISSUED
4. Batch-resolves matching threads via `resolveReviewThread` mutation
5. Leaves CLARIFY threads open — those await answers
6. Reports: "Resolved X/Y threads. Z CLARIFY threads left open."

**Options**:
- `--pr NUMBER`: Specify PR number explicitly (auto-detects from branch by default)
- `--dry-run`: Preview what would be resolved without acting

**If `gh` is unavailable**: instruct the user to resolve threads manually in the GitHub UI.

**When to run**: After every Comment Response Protocol pass — both during full review and `--comments-only` mode. Can also be run standalone at any time.

## Post-Merge Verification

After a PR is merged to main, run a verification diff:

1. **Diff merged main against the last reviewed commit**: `git diff <last-reviewed-sha>..main -- <files-in-phase>`
2. **Flag silent reversions**: Any change that undoes a reviewed fix (auto-fix commit, suggest-fix commit) is a reversion. Report:
   ```
   Post-merge verification:
     REVERTED: .github/workflows/ci.yml:3 — permissions moved back to workflow-level
     REVERTED: scripts/query-index.py:166 — nosec comment removed by linter
     OK: 42 files unchanged since review
   ```
3. **Common causes**: Auto-formatters, linters with `--fix`, post-merge hooks, rebasing that drops commits
4. **Action**: Reversions are reported in review.md under a `### Post-Merge Verification` section. If critical (security fixes reverted), create a GitHub issue immediately.

This step runs only when explicitly invoked (`/speckit.review --post-merge`) or when the review command detects it's running on a branch that has already been merged.

## CI Debug Structure for New Integrations

When CI fails due to a newly added tool (scanner, linter, formatter), use this structured approach instead of generic "fix and push again":

1. **Enable one scanner at a time** — don't add Semgrep + Gitleaks + Bandit + Trivy in a single commit
2. **Run locally first** to identify all findings before pushing: `semgrep --config auto .` or equivalent
3. **Commit triage per-scanner** — create ignore/baseline files (`.semgrepignore`, `.secrets.baseline`, `nosec` annotations) with documented justifications
4. **Push and verify one scanner passes** before adding the next
5. **Expect 3-5 CI rounds** for a multi-scanner setup — this is normal, not a failure

This guidance appears in the CI verification step (Step 3) when the failing check is a security scanner or linter that was added in the current phase.

## Inbox Integration (Spec 003 — conditional)

If a shared inbox exists at `FEATURE_DIR/inbox/`:

- During `--parallel` mode, post critical and flag-only findings as REVIEW messages to the inbox
- Message format: individual file named `{timestamp}-REVIEW-review-command.md`
- Message content: `REVIEW | Phase N | [severity] | [category] | See review.md Phase N [section] for details`
- The inbox message is a **notification** referencing review.md (the authoritative record), not a duplicate of the full finding

If no inbox exists, skip silently. The inbox is additive, not required.

## Parallel Mode (`--parallel`)

When `--parallel` is passed:

1. **Detect active agent**: Read `.specify/init-options.json` and check the `ai` field.

2. **Dispatch based on agent**:
   - **`claude`** (Claude Code): Launch the review as a subagent using the Agent tool, or in a new tmux session. Return control to the user immediately.
   - **`codex`** (Codex): Launch the review as a background sandbox task.
   - **All other agents** or unrecognized values: Output message: "Parallel mode is not supported for [agent name]. Running review in blocking mode." Then proceed with normal blocking review.

3. **Async completion**: When the parallel review completes:
   - Write review.md
   - Create PR (if GitHub tools available)
   - Post inbox notification (if inbox available)
   - If critical issues found, write a prominent summary to review.md

When `--parallel` is NOT passed, the review runs in blocking mode (default).

## Completion

After all steps complete:

1. Output a summary:
   - Pass/fail status for each review pass
   - Count of auto-fixes, suggest-fixes, and flagged issues
   - PR number and URL (if created)
   - Path to review.md

2. **Check for extension hooks**: After completion, check if `.specify/extensions.yml` exists in the project root.
   - If it exists, read it and look for entries under the `hooks.after_review` key
   - If the YAML cannot be parsed or is invalid, skip hook checking silently and continue normally
   - Filter out hooks where `enabled` is explicitly `false`. Treat hooks without an `enabled` field as enabled by default.
   - For each remaining hook, do **not** attempt to interpret or evaluate hook `condition` expressions:
     - If the hook has no `condition` field, or it is null/empty, treat the hook as executable
     - If the hook defines a non-empty `condition`, skip the hook and leave condition evaluation to the HookExecutor implementation
   - For each executable hook, output the following based on its `optional` flag:
     - **Optional hook** (`optional: true`):
       ```
       ## Extension Hooks

       **Optional Hook**: {extension}
       Command: `/{command}`
       Description: {description}

       Prompt: {prompt}
       To execute: `/{command}`
       ```
     - **Mandatory hook** (`optional: false`):
       ```
       ## Extension Hooks

       **Automatic Hook**: {extension}
       Executing: `/{command}`
       EXECUTE_COMMAND: {command}
       ```
   - If no hooks are registered or `.specify/extensions.yml` does not exist, skip silently
