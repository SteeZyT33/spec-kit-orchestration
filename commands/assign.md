---
description: Assign the best-fit agent to each task in tasks.md based on available agent capabilities, task descriptions, and phase context.
scripts:
  sh: scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks
  ps: scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Pre-Execution Checks

**Check for extension hooks (before assignment)**:
- Check if `.specify/extensions.yml` exists in the project root.
- If it exists, read it and look for entries under the `hooks.before_assign` key
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
   When shared flow-state output is available, treat it as the canonical feature-level workflow truth. Lane metadata may enrich assignment decisions, but it does not replace artifact-derived feature state.

2. **Parse flags from user input**:
   - `--reassign-all`: Set REASSIGN_ALL = true (clear all existing annotations, reassign from scratch)
   - `--human-tasks "T003-T009,T015"`: Pre-mark specific tasks for `[@Human Lead]` assignment. Supports ranges (T003-T009) and comma-separated lists. These tasks skip agent matching entirely.
   - `--force`: Bypass context detection and proceed with assignment regardless of task count or worktree status.
   - Any remaining text: Additional context or instruction for the assignment heuristic (e.g., "focus on security-heavy assignments")

3. **Spec readiness gate** — verify spec and plan are reviewed before assigning work:

   Check whether spec.md and plan.md have been merged to the default branch:
   ```bash
   DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
   SPEC_MERGED=$(git cat-file -e "origin/${DEFAULT_BRANCH}:$(realpath --relative-to=. ${FEATURE_DIR}/spec.md)" 2>/dev/null && echo "yes" || echo "no")
   PLAN_MERGED=$(git cat-file -e "origin/${DEFAULT_BRANCH}:$(realpath --relative-to=. ${FEATURE_DIR}/plan.md)" 2>/dev/null && echo "yes" || echo "no")
   ```

   - If BOTH are merged: proceed silently.
   - If EITHER is not merged AND `--force` was NOT passed:
     ```
     ## Spec Readiness Warning

     The following artifacts have not been merged to ${DEFAULT_BRANCH}:
     - [ ] spec.md (${SPEC_MERGED})
     - [ ] plan.md (${PLAN_MERGED})

     Assigning agents to unreviewed specs risks building against requirements
     that may change during review. Consider merging spec+plan first, or
     use `--force` to proceed anyway.
     ```
     Then STOP and wait for user decision. Do not proceed to assignment.
   - If `--force` was passed: output a one-line warning and proceed.

4. **Execution-shape detection — should this feature run sequentially or with Orca lanes?**

   Before running the scoring logic, evaluate the execution shape for this feature.
   Shared flow-state output is the canonical feature-level workflow source of truth when available. Orca lane metadata is contextual execution evidence, and agent-specific directories are not workflow truth.

   a. **Count tasks**: Read tasks.md and count lines matching `- [ ] T\d+`.
   b. **Check for active Orca lanes**:
      - Read `.specify/orca/worktrees/registry.json` if it exists
      - Filter lane records for the current feature
      - Treat lanes with status `planned`, `active`, or `blocked` as live workflow context
      - Use `git worktree list` only as secondary validation of lane paths, not as the source of truth
   c. **Evaluate**:
      - If `--force` was passed: skip context detection entirely, proceed to step 4.
      - If live Orca lanes exist for this feature: proceed to step 4 in `parallel-lane` mode. Do NOT recommend skipping assignment, even if task count is low.
      - If task count >= 30 OR phases >= 4: proceed to step 4 in `sequential` mode unless lanes already exist.
      - If task count < 15 AND no live Orca lanes AND no `--force`:
        ```
        ## Skip Recommendation

        This spec has [N] tasks in [M] phases with no active Orca lanes.
        Agent assignment adds overhead without value for single-agent sequential execution.

        **Recommendation**: Skip `/speckit.orca.assign` and proceed directly to `/speckit.implement`.

        To override: `/speckit.orca.assign --force`
        ```
        Then stop. Do not proceed to scoring.

4. **Read configuration**: Read `.specify/init-options.json` from the project root.
   - Extract the `ai` field (identifies the active AI harness — e.g., "claude", "codex", "cursor")
   - Extract the external agent path: check for `agent_source` field first, then fall back to `ai_commands_dir` for backward compatibility. This is a filesystem path to an external agent definition directory.
   - If `init-options.json` does not exist or cannot be parsed, use defaults: ai = "generic", agent_source = null

5. **Discover available agents** using a two-tier approach:

   ### Tier 1: Internal Agents (zero-config, always available)

   Based on the `ai` field, use the following built-in agent type mappings. These represent common specialist roles available in most AI harnesses:

   | Agent Name | Specialization Keywords |
   |------------|------------------------|
   | Human Lead | triage, decide, evaluate, choose between, audit for value, salvage or discard, merge vs close, keep or delete, review conflicting, resolve conflict, approve, sign off, judgment, manual, subjective, ambiguous |
   | Backend Architect | backend, API, database, server, endpoint, REST, GraphQL, migration, schema, model, service, middleware |
   | Frontend Developer | frontend, UI, component, React, Vue, Angular, CSS, HTML, page, layout, form, button, modal, responsive |
   | Security Engineer | security, auth, authentication, authorization, OAuth, OWASP, encryption, secrets, RBAC, permissions, CORS, CSRF, XSS, SQL injection, input validation |
   | DevOps Automator | CI/CD, Docker, infrastructure, deployment, pipeline, Kubernetes, terraform, monitoring, logging, environment, config, nginx |
   | AI Engineer | ML, AI, LLM, model, embeddings, vector, training, inference, prompt, fine-tune, RAG, NLP |
   | Mobile App Builder | mobile, iOS, Android, Swift, Kotlin, React Native, Flutter, app, touch, gesture, notification |
   | Database Optimizer | database, SQL, query, index, migration, schema, ORM, performance, normalization, join, transaction |
   | Evidence Collector | test, testing, jest, vitest, pytest, spec, assertion, mock, stub, fixture, coverage, E2E, integration test, unit test, QA, quality, verify, validate |
   | Technical Writer | documentation, README, docs, guide, tutorial, API docs, changelog, comment |
   | UX Architect | design, UX, wireframe, prototype, user flow, accessibility, a11y, WCAG |
   | Data Engineer | data pipeline, ETL, stream, Kafka, Spark, data lake, warehouse, analytics, batch |
   | SRE | reliability, SLO, SLI, observability, incident, alert, chaos, toil, on-call |

   These are the **internal agents**. They are always available regardless of configuration.

   > **`[@Human Lead]`** is a special agent type representing tasks that require human judgment. It is assigned **only** when its keyword phrases are detected in the task description. Phase-context bonuses (step 8a) can boost `[@Human Lead]`'s score when keywords are already present, but cannot independently trigger assignment — at least one keyword phrase match is required.
   >
   > **Multi-word keywords** (e.g., "choose between", "sign off", "merge vs close") must be matched as phrases, not individual words. "sign off" matches "sign off on the design" but not "sign the certificate".

   ### Tier 2: External Agents (configured, richer definitions)

   If `agent_source` (or `ai_commands_dir` fallback) is set in init-options.json:

   a. Validate the path exists and is a directory. If not:
      - Output a warning: "Agent source path '{path}' not found or not a directory. Falling back to internal agents only."
      - Continue with internal agents only.

   b. Scan the directory **recursively** for markdown files (`.md`):
      - For each file, attempt to parse YAML frontmatter
      - Extract these fields from frontmatter:
        - `name` (required — skip file if missing)
        - `description` (required — skip file if missing)
        - `tools` (optional — used as capabilities/keywords)
      - Use the **parent directory name** as a division/category signal (e.g., a file in `engineering/` gets category "engineering", a file in `testing/` gets category "testing")
      - If a file cannot be parsed (no frontmatter, invalid YAML, missing required fields): skip it with a warning and continue

   c. Build the external agent catalog: a list of agents with name, description, tools/capabilities, and division.

   **Priority**: Evaluate external agents first. Use internal agents only if no external agent achieves a non-zero keyword match score.

6. **Read and parse tasks.md**:
   - Load tasks.md from FEATURE_DIR
   - Identify task lines: lines matching the pattern `- [ ] T\d+` (checkbox + task ID)
   - For each task line, extract:
     - Task ID (e.g., T001, T012)
     - Existing markers: `[P]`, `[US1]`, `[US2]`, etc.
     - Whether an `[@` annotation already exists
     - The task description text (everything after the markers)
     - The phase/section the task belongs to (from the heading structure)

7. **Determine which tasks need assignment**:
   - If REASSIGN_ALL is true: strip all existing `[@...]` annotations from all unchecked task lines — every unchecked task gets reassigned
   - If REASSIGN_ALL is false: skip any unchecked task that already has an `[@...]` annotation (preserve manual edits and previous assignments)
   - Among unchecked tasks, those without `[@...]` annotations are candidates for assignment
   - Completed tasks (`- [x]` / `- [X]`) are never modified by this command

8. **Apply `--human-tasks` pre-assignments** (if flag was provided):
   - Parse the task ID list (ranges like `T003-T009` and comma-separated like `T003,T015`)
   - For each task ID: if it exists in the candidate list, assign `[@Human Lead]` immediately. If it does not exist in tasks.md (typo or wrong ID), warn: `"Warning: T099 not found in tasks.md — skipping"`
   - Remove successfully assigned tasks from the candidate list — they skip agent matching entirely

9. **Match agents to tasks** using heuristic keyword matching:

   For each remaining candidate task:

   a. **Extract matching signals**:
      - Keywords from the task description (split into meaningful terms)
      - Phase context from the section heading — apply **phase context weighting**:
        - "Setup" or "Foundational" → +2 bonus for infrastructure/DevOps agents
        - "Audit", "Triage", "Content Review" → +3 bonus for `[@Human Lead]`
        - "User Story" phases → favor domain-appropriate agents based on task content
        - "Polish", "Cross-Cutting", "Verification" → +2 bonus for QA/documentation agents
      - File paths mentioned in the task (e.g., `src/frontend/` → frontend, `tests/` → testing, `src/api/` → backend)

   b. **Score candidates** (keyword overlap + phase weighting):
      - For each available agent, count how many of the agent's specialization keywords appear in the task description + file path + phase context
      - Apply phase context bonus from step (a)
      - External agents: also check the agent's `description` and `tools` fields for keyword matches
      - External agents: give a small bonus (+1) if the agent's division matches the task's domain
      - Normalize the score to a 0.0–1.0 **confidence** range: `confidence = min(raw_score / 10, 1.0)`

   c. **Select the best match**:
      - First, check `[@Human Lead]` phrase triggers. If any keyword phrase matches the task description, assign `[@Human Lead]` directly and skip external/internal scoring (unless the task was already pre-assigned via `--human-tasks`)
      - Compute scores for external agents first
      - If any external agent has confidence > 0.0, pick the highest-scoring external agent
      - Otherwise, compute scores for internal agents and pick the highest-scoring one
      - If the best match has **confidence < 0.3** (weak match), assign `[@Unassigned]` instead and flag for manual review
      - If no agent has any keyword overlap, assign `[@Unassigned]`

9. **Lane and dependency analysis** (post-assignment):

   After all tasks are assigned, scan the dependency chain in tasks.md:
   - For each task that depends on another (sequential ordering, explicit "depends on" notes, or same-file constraints)
   - If dependent tasks are assigned to **different agent types**, flag the handoff:
     ```
     ### Dependency Handoff Warnings
     - T004 [@Backend Architect] → T005 [@Frontend Developer]: handoff across agent types (shared file: src/api/routes.ts)
     - T012 [@Human Lead] → T013 [@DevOps Automator]: human decision gates automation work
     ```
   - This is advisory — no reassignment is made, but it surfaces coupling for manual review

   If Orca lane metadata exists for this feature, also check:
   - whether a task appears to be already claimed by another live lane
   - whether two live lanes imply overlapping work on the same files or task scope
   - whether a lane exists without bounded `task_scope`

   Report these as `### Lane Coordination Warnings`:
   - task owned by multiple lanes
   - lane scope missing or stale
   - shared-file risk across active lanes

10. **Write annotations back to tasks.md**:
   - For each assigned task, insert the `[@Agent Name]` annotation into the task line
   - Placement: after existing markers (`[P]`, `[US1]`, etc.) and before the task description text
   - Example transformation:
     - Before: `- [ ] T012 [P] [US1] Create React component in src/components/Auth.tsx`
     - After: `- [ ] T012 [P] [US1] [@Frontend Developer] Create React component in src/components/Auth.tsx`
   - Preserve all existing formatting, checkboxes, markers, and descriptions exactly
   - Write the updated tasks.md back to disk

11. **Create implementation handoff context**:
   - After writing assignments, create or refresh the `assign -> implement`
     handoff for the feature:
     ```bash
     uv run python -m speckit_orca.context_handoffs create \
       --feature-dir "$FEATURE_DIR" \
       --source-stage assign \
       --target-stage implement \
       --summary "Assignments complete; implementation should use the selected task scope and annotations in tasks.md." \
       --artifact "$FEATURE_DIR/tasks.md"
     ```
   - If assignment is intentionally skipped or `tasks.md` was not modified, do
     not fabricate a handoff.

12. **Report results**:

   Output a summary table with confidence scores:

   ```text
   ## Agent Assignment Report

   **Feature**: [feature name]
   **Execution Mode**: sequential | parallel-lane
   **Detected Lanes**: none | [lane IDs]
   **Agent Source**: Internal only | Internal + External ({path})
   **Mode**: Fresh assignment | Reassign all
   **Human-tasks pre-assigned**: T003-T009 (or "none")

   | Task | Agent | Confidence | Source | Note |
   |------|-------|-----------|--------|------|
   | T001 | [@DevOps Automator] | 0.80 | internal | |
   | T003 | [@Human Lead] | — | pre-assigned | --human-tasks flag |
   | T012 | [@Security Engineer] | 0.92 | external | |
   | T015 | [@Unassigned] | 0.18 | — | weak match — manual review |

   ### Summary
   **Total**: X tasks | Assigned: Y | Human: H | Skipped (existing): Z | Unassigned: W

   Tasks.md updated at: {absolute path}
   ```

   If any tasks were unassigned or low-confidence, list them:
   ```text
   ### Low-Confidence & Unassigned Tasks (manual review recommended)
   - T015 (0.18): "Implement custom analytics dashboard" — best match was [@Frontend Developer] but confidence too low
   - T042 (0.00): "Decide whether to merge or close PR #124" — no matching specialist
   ```

   If dependency handoff warnings exist, include them (from step 9).

   If any agent definition files were skipped during discovery, list warnings:
   ```text
   ### Discovery Warnings
   - Skipped: /path/to/file.md — missing 'name' in frontmatter
   ```

12. **Check for extension hooks**: After reporting, check if `.specify/extensions.yml` exists in the project root.
    - If it exists, read it and look for entries under the `hooks.after_assign` key
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

## Review Integration (Spec 001)

When `/speckit.orca.code-review` runs after implementation, it can read the `[@Agent Name]` annotations in tasks.md to understand which agent was assigned to each task. This enables:

- **"Don't review your own work"**: If `[@Backend Architect]` was assigned to implement a task, the review command can suggest a different agent (e.g., Security Engineer, Evidence Collector) for reviewing that task's output.
- **Review pass matching**: The security review pass can reference whether a security specialist was assigned to security-related tasks.

The `@` annotations are informational hints — the review command works identically with or without them. Agent assignment is purely additive.

## Agent Annotation Convention

The `[@Agent Name]` format is the standard convention for agent role annotations in tasks.md:

- **Prefix**: `[@` distinguishes agent annotations from other markers (`[P]`, `[US1]`)
- **Closing**: `]` closes the annotation
- **Content**: The agent's display name exactly as discovered (e.g., `Frontend Developer`, `Backend Architect`)
- **Platform-neutral**: The annotation is a role name, not tied to any specific AI harness. Any harness can interpret it.
- **Manual override**: Users can edit `[@...]` annotations directly in tasks.md. Re-running `/speckit.orca.assign` without `--reassign-all` preserves manual edits.
- **Special value**: `[@Unassigned]` indicates no matching agent was found. The user should manually assign these tasks.

## Quick Reference

```bash
# Assign agents to tasks (will recommend skipping for small single-agent specs)
/speckit.orca.assign

# Force assignment even when context detection recommends skipping
/speckit.orca.assign --force

# Pre-mark human judgment tasks before auto-assignment
/speckit.orca.assign --human-tasks "T003-T009,T015"

# Combine: force + human pre-marks
/speckit.orca.assign --force --human-tasks "T003-T009"

# Reassign all tasks from scratch (clears existing annotations)
/speckit.orca.assign --reassign-all

# Pre-mark human judgment tasks before auto-assignment
/speckit.orca.assign --human-tasks "T003-T009,T015"

# Combine: reassign all with human pre-marks
/speckit.orca.assign --reassign-all --human-tasks "T003-T009"

# Assign with specific context
/speckit.orca.assign focus on security-heavy assignments for this feature
```
