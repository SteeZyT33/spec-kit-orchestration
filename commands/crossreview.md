---
description: Invoke a cross-harness adversarial review at any pipeline stage — validates design artifacts (post-tasks) or code changes (post-review) using a different AI harness.
scripts:
  sh: scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks
  ps: scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks
handoffs:
  - label: Run Standard Review
    agent: speckit.review
    prompt: Run the standard review passes on the current phase
  - label: Implement Project
    agent: speckit.implement
    prompt: Start the implementation in phases
  - label: Assign Agents
    agent: speckit.assign
    prompt: Assign agents to tasks before implementation
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

1. Run `{SCRIPT}` from repo root and parse FEATURE_DIR and AVAILABLE_DOCS list. All paths must be absolute. For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot").

2. **Parse arguments** from user input:
   - `--scope design|code`: Explicitly set review scope (see step 5 for auto-detection)
   - `--phase N`: Review a specific phase (default: latest completed phase from tasks.md)
   - Any remaining text: Additional review focus or instructions for the reviewer

3. **Read configuration** from `.specify/init-options.json`:
   - `review_harness` (optional, default: `"codex"`): The CLI harness to invoke (`codex`, `claude`, `gemini`)
   - `review_model` (optional, default: `"o4-mini-high"` for codex, `null` for others): Model override for the review session
   - `review_effort` (optional, default: `"high"`): Reasoning effort level
   - If `review_harness` is not set, use default `"codex"` and output a note:
     ```
     No review_harness configured — defaulting to codex (o4-mini-high).
     To customize, add to .specify/init-options.json:
       "review_harness": "codex",
       "review_model": "o4-mini-high",
       "review_effort": "high"
     ```
     Then continue with defaults.

4. **Harness availability**: Do NOT check `command -v` here — the launcher and backend handle CLI resolution (including non-PATH installs like `~/.claude/local/`). If the harness is missing, the backend will return a structured error in the JSON output.

5. **Determine the review scope**:

   If `--scope` was explicitly passed, use that value. Otherwise, auto-detect:

   a. Run `git diff --merge-base --name-only main HEAD` to check for code changes
   b. **If no code changes exist** (or only spec artifacts changed): scope = `design`
   c. **If code changes exist**: scope = `code`

   Then load context based on scope:

   ### Scope: `design` (post-tasks, pre-implement)

   Review design artifacts — catch gaps before writing code.
   - **REQUIRED**: Read spec.md (acceptance criteria, user stories, FRs)
   - **REQUIRED**: Read plan.md (architecture decisions, tech stack, file structure)
   - **REQUIRED**: Read tasks.md (task breakdown, phasing, dependencies)
   - **IF EXISTS**: Read data-model.md (entities, relationships)
   - **IF EXISTS**: Read contracts/ (API specs, interface definitions)
   - **IF EXISTS**: Read research.md (technical decisions, alternatives considered)

   ### Scope: `code` (post-implement or post-review)

   Review implemented code — find bugs, security issues, spec drift.
   - Read tasks.md to identify the target phase and its tasks
   - Read spec.md for acceptance criteria relevant to the phase
   - Read plan.md for architecture decisions
   - Run `git diff --merge-base --name-only main HEAD` to get the list of changed files
   - If no files changed in code scope, report "No code changes to review against main. Use `--scope design` to review design artifacts." and stop

6. **Compute review input** based on scope:

   ### For `code` scope:
   ```bash
   git diff --merge-base main HEAD --no-ext-diff --unified=3 --no-color > FEATURE_DIR/.crossreview.patch
   git diff --merge-base --name-only main HEAD > FEATURE_DIR/.crossreview-files.txt
   ```

   ### For `design` scope:
   Concatenate the design artifacts into a single review document:
   ```bash
   echo "# Design Artifacts for Review" > FEATURE_DIR/.crossreview.patch
   echo "" >> FEATURE_DIR/.crossreview.patch
   for doc in spec.md plan.md tasks.md data-model.md research.md; do
     if [ -f "FEATURE_DIR/$doc" ]; then
       echo "---" >> FEATURE_DIR/.crossreview.patch
       echo "## $doc" >> FEATURE_DIR/.crossreview.patch
       cat "FEATURE_DIR/$doc" >> FEATURE_DIR/.crossreview.patch
       echo "" >> FEATURE_DIR/.crossreview.patch
     fi
   done
   # Include contracts/ directory if it exists
   if [ -d "FEATURE_DIR/contracts" ]; then
     for contract in FEATURE_DIR/contracts/*.md FEATURE_DIR/contracts/*.json FEATURE_DIR/contracts/*.yaml; do
       if [ -f "$contract" ]; then
         echo "---" >> FEATURE_DIR/.crossreview.patch
         echo "## contracts/$(basename "$contract")" >> FEATURE_DIR/.crossreview.patch
         cat "$contract" >> FEATURE_DIR/.crossreview.patch
         echo "" >> FEATURE_DIR/.crossreview.patch
       fi
     done
   fi
   echo "spec.md plan.md tasks.md" > FEATURE_DIR/.crossreview-files.txt
   ```

7. **Build the review prompt** — write to `FEATURE_DIR/.crossreview-prompt.md`:

   Select the prompt based on scope:

   ### Prompt for `code` scope:

   # Cross-Harness Adversarial Review — Code

   You are reviewing code written by a DIFFERENT AI agent. Your job is to be
   adversarial — assume the implementing agent has blind spots and find them.

   ## Review Checklist
   - Spec compliance: does the implementation satisfy the acceptance criteria below?
   - Correctness: logic errors, edge cases, off-by-one, null/undefined handling
   - Security: injection, auth bypass, secrets exposure, OWASP top 10
   - Data integrity: race conditions, partial writes, missing validation at boundaries
   - Backwards compatibility: breaking changes to existing interfaces
   - Missing tests: untested paths that the spec requires

   ## Changed Files
   [insert contents of FEATURE_DIR/.crossreview-files.txt]

   ## Acceptance Criteria for Phase [N]
   [insert relevant acceptance criteria from spec.md for the target phase]

   ## Architecture Context
   [insert key decisions from plan.md — tech stack, file structure, patterns]

   ## Additional Focus
   [insert any additional text from user arguments, or "None" if empty]

   ## Instructions
   Read the patch at the end of this prompt and inspect the changed files in the
   working directory if needed. Focus on substance — ignore style unless it hides a bug.

   Return your findings as JSON with this exact structure:
   ```json
   {
     "summary": "one-paragraph summary of findings",
     "blocking": [{"file": "path", "line": 42, "issue": "description", "fix": "suggestion"}],
     "non_blocking": [{"file": "path", "line": 10, "issue": "description", "fix": "suggestion"}]
   }
   ```

   Only blocking issues should be things that MUST be fixed before merge.
   Non-blocking issues are improvements worth noting but not merge-gating.

   ### Prompt for `design` scope:

   # Cross-Harness Adversarial Review — Design

   You are reviewing a feature design (spec, plan, and task breakdown) produced by
   a DIFFERENT AI agent. Your job is to find gaps, contradictions, and risks BEFORE
   any code is written — this is the cheapest place to catch mistakes.

   ## Review Checklist
   - Completeness: are all user stories from the spec covered by tasks?
   - Task ordering: do dependencies make sense? Are blocking tasks identified?
   - Scope alignment: do the tasks match the spec, or is there scope creep/drift?
   - Architecture fitness: does the plan's tech stack and structure support the spec requirements?
   - Missing concerns: security, error handling, edge cases, performance, accessibility
   - Testability: can each phase be independently verified?
   - Data model: do entities and relationships support all user stories?
   - Risk areas: which tasks are underspecified or likely to cause rework?

   ## Design Artifacts
   [the artifacts are included at the end of this prompt]

   ## Additional Focus
   [insert any additional text from user arguments, or "None" if empty]

   ## Instructions
   Read the design artifacts at the end of this prompt. Focus on substance —
   things that will cause rework, missed requirements, or broken implementations
   if not caught now.

   Return your findings as JSON with this exact structure:
   ```json
   {
     "summary": "one-paragraph summary of design quality and readiness",
     "blocking": [{"file": "artifact.md", "issue": "description", "fix": "suggestion"}],
     "non_blocking": [{"file": "artifact.md", "issue": "description", "fix": "suggestion"}]
   }
   ```

   Blocking issues are things that MUST be resolved before implementation starts.
   Non-blocking issues are improvements worth noting but not implementation-gating.

   Fill in the bracketed sections with actual content. Do not leave placeholders.

8. **Write the output schema** to `FEATURE_DIR/.crossreview.schema.json` by copying from `.specify/templates/crossreview.schema.json`.

9. **Generate timestamp**: `TIMESTAMP=$(date +%Y-%m-%dT%H-%M-%S)`

10. **Invoke the launcher script and capture the output path**:
    ```bash
    CROSSREVIEW_OUTPUT=".shared/crossreview-${REVIEW_HARNESS}-${TIMESTAMP}.json"
    bash scripts/bash/crossreview.sh \
      --harness "$REVIEW_HARNESS" \
      --model "$REVIEW_MODEL" \
      --effort "$REVIEW_EFFORT" \
      --output "$CROSSREVIEW_OUTPUT" \
      --prompt-file "FEATURE_DIR/.crossreview-prompt.md" \
      --patch-file "FEATURE_DIR/.crossreview.patch" \
      --schema-file "FEATURE_DIR/.crossreview.schema.json"
    ```

    If in tmux, this splits the pane and the reviewer runs visually in the side pane.
    If not in tmux, this blocks until the reviewer finishes.

    Note: crossreview.sh delegates to crossreview-backend.py for the actual harness CLI invocation and JSON processing.

11. **Read the output JSON** from `$CROSSREVIEW_OUTPUT` (the specific file from this run, not a wildcard). Parse the JSON structure.

12. **Present findings** to the user:

    ```markdown
    ## Cross-Harness Review — {harness} ({model}) [{scope}]

    **Scope**: {design|code}
    **Phase**: Phase N — [phase name]
    **Reviewer**: {harness} ({model}, effort: {effort})

    ### Summary
    [summary from JSON]

    ### Blocking Issues ({count})
    | # | File | Line | Issue | Suggested Fix |
    |---|------|------|-------|---------------|
    [rows from blocking array]

    ### Non-Blocking Issues ({count})
    | # | File | Line | Issue | Suggested Fix |
    |---|------|------|-------|---------------|
    [rows from non_blocking array]
    ```

    If no blocking issues: "No blocking issues found. Cross-review passed."

    For `design` scope, additionally suggest: "Design review passed. Proceed with `/speckit.assign` or `/speckit.implement`."
    For `code` scope with blocking issues, suggest: "Address blocking issues before merge."

13. **Append to review.md** in FEATURE_DIR under a `### Cross-Harness Review` section using the same format as step 12.

14. **If blocking issues exist**, recommend: "There are N blocking issues from the cross-harness review. Address them before merge."

15. **Check for extension hooks** (`hooks.after_crossreview`):
    - Check if `.specify/extensions.yml` exists in the project root
    - If it exists, read it and look for entries under the `hooks.after_crossreview` key
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
