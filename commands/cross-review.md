---
description: Invoke a cross-harness adversarial review at any pipeline stage — validates design artifacts (post-tasks) or code changes (post-review) using a different AI harness.
scripts:
  sh: scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks
  ps: scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks
handoffs:
  - label: Run Standard Review
    agent: speckit.orca.code-review
    prompt: Run the standard code-review passes on the current phase
  - label: Implement Project
    agent: speckit.implement
    prompt: Start the implementation in phases
  - label: Assign Agents
    agent: speckit.orca.assign
    prompt: Assign agents to tasks before implementation
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

1. Run `{SCRIPT}` from repo root and parse FEATURE_DIR and AVAILABLE_DOCS list. All paths must be absolute. For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot").
   When shared flow-state output is available, treat it as the stage and milestone baseline and use lane metadata only as contextual enrichment.

2. **Parse arguments** from user input:
   - `--scope design|code`: Explicitly set review scope (see step 5 for auto-detection)
   - `--phase N`: Review a specific phase (default: latest completed phase from tasks.md)
   - Any remaining text: Additional review focus or instructions for the reviewer

3. **Read configuration** from `.specify/init-options.json`:
   - `review_harness` (optional, preferred default: first installed harness that is different from the active `ai` in `.specify/init-options.json`; otherwise fall back to `"codex"`): The CLI harness to invoke (`codex`, `claude`, `gemini`)
   - `review_model` (optional, default: `"o4-mini-high"` for codex, `null` for others): Model override for the review session
   - `review_effort` (optional, default: `"high"`): Reasoning effort level
   - If `review_harness` is not set, choose a different installed harness when possible and output a note:
     ```text
     No review_harness configured — auto-selecting a non-current harness when available.
     To customize, add to .specify/init-options.json:
       "review_harness": "claude",
       "review_model": null,
       "review_effort": "high"
     ```
     If the chosen harness matches the active provider, warn that the run is no longer truly cross-harness.

4. **Harness availability**: Do NOT check `command -v` here — the launcher and backend handle CLI resolution (including non-PATH installs like `~/.claude/local/`). If the harness is missing, the backend will return a structured error in the JSON output.

5. **Determine the review scope**:

   If `--scope` was explicitly passed, use that value. Otherwise, auto-detect:

   a. Run `git diff --merge-base --name-only main HEAD` to check for committed code changes
   b. Run `git diff --name-only` to check for dirty working-tree changes
   c. Include untracked files that are not review artifacts (for example new source files or scripts)
   d. **If no code changes exist across committed diff, working tree, or untracked files** (or only spec artifacts changed): scope = `design`
   e. **If code changes exist in any of those buckets**: scope = `code`

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
   - Run `git diff --merge-base --name-only main HEAD`, `git diff --name-only`, and `git ls-files --others --exclude-standard` to get the full working review set
   - If no files changed in code scope, report "No code changes to review against main. Use `--scope design` to review design artifacts." and stop

6. **Detect Orca lane context**:
   - If `.specify/orca/worktrees/registry.json` exists, read lane metadata for this feature
   - If the current branch or working directory matches a lane record, capture:
     - lane ID
     - lane branch
     - lane `task_scope`
     - lane status
   - If lane metadata exists but no direct match is found, treat the review as feature-wide with live-lane context
   - Cross-review does not own worktree orchestration. It only reports lane context when present.

7. **Compute review input** based on scope:

   ### For `code` scope:
   ```bash
   {
     echo "# Code Review Patch"
     echo
     echo "## Merge-base diff"
     git diff --merge-base main HEAD --no-ext-diff --unified=3 --no-color
     echo
     echo "## Working tree diff"
     git diff --no-ext-diff --unified=3 --no-color
     echo
     echo "## Untracked files"
     git ls-files -z --others --exclude-standard | while IFS= read -r -d '' file; do
       case "$file" in
         "$FEATURE_DIR"/.crossreview-*|.shared/*) continue ;;
       esac
       echo
       echo "diff --git a/$file b/$file"
       echo "--- /dev/null"
       echo "+++ b/$file"
       sed 's/^/+/' "$file"
     done
   } > "$FEATURE_DIR/.crossreview.patch"
   tmp_crossreview_files="$(mktemp)"
   {
     git diff --merge-base --name-only main HEAD
     git diff --name-only
     git ls-files -z --others --exclude-standard | while IFS= read -r -d '' file; do
       case "$file" in
         "$FEATURE_DIR"/.crossreview-*|.shared/*) continue ;;
       esac
       printf '%s\n' "$file"
     done
   } | sort -u > "$tmp_crossreview_files"
   mv "$tmp_crossreview_files" "$FEATURE_DIR/.crossreview-files.txt"
   ```

   ### For `design` scope:
   Concatenate the design artifacts into a single review document:
   ```bash
   echo "# Design Artifacts for Review" > "$FEATURE_DIR/.crossreview.patch"
   echo "" >> "$FEATURE_DIR/.crossreview.patch"
   for doc in spec.md plan.md tasks.md data-model.md research.md; do
     if [ -f "$FEATURE_DIR/$doc" ]; then
       echo "---" >> "$FEATURE_DIR/.crossreview.patch"
       echo "## $doc" >> "$FEATURE_DIR/.crossreview.patch"
       cat "$FEATURE_DIR/$doc" >> "$FEATURE_DIR/.crossreview.patch"
       echo "" >> "$FEATURE_DIR/.crossreview.patch"
     fi
   done
   if [ -d "$FEATURE_DIR/contracts" ]; then
     for contract in "$FEATURE_DIR"/contracts/*.md "$FEATURE_DIR"/contracts/*.json "$FEATURE_DIR"/contracts/*.yaml; do
       if [ -f "$contract" ]; then
         echo "---" >> "$FEATURE_DIR/.crossreview.patch"
         echo "## contracts/$(basename "$contract")" >> "$FEATURE_DIR/.crossreview.patch"
         cat "$contract" >> "$FEATURE_DIR/.crossreview.patch"
         echo "" >> "$FEATURE_DIR/.crossreview.patch"
       fi
     done
   fi
   echo "spec.md plan.md tasks.md" > "$FEATURE_DIR/.crossreview-files.txt"
   ```

8. **Build the review prompt** — write to `$FEATURE_DIR/.crossreview-prompt.md` using the code-scope or design-scope prompt shape, demanding structured JSON output with `summary`, `blocking`, and `non_blocking`.

9. **Write the output schema** to `$FEATURE_DIR/.crossreview.schema.json` by copying from `.specify/templates/crossreview.schema.json`.

10. **Generate timestamp**: `TIMESTAMP=$(date +%Y-%m-%dT%H-%M-%S)`

11. **Invoke the launcher script and capture the output path**:
    ```bash
    CROSSREVIEW_OUTPUT=".shared/crossreview-${REVIEW_HARNESS}-${TIMESTAMP}.json"
    bash scripts/bash/crossreview.sh \
      --harness "$REVIEW_HARNESS" \
      --model "$REVIEW_MODEL" \
      --effort "$REVIEW_EFFORT" \
      --output "$CROSSREVIEW_OUTPUT" \
      --prompt-file "$FEATURE_DIR/.crossreview-prompt.md" \
      --patch-file "$FEATURE_DIR/.crossreview.patch" \
      --schema-file "$FEATURE_DIR/.crossreview.schema.json"
    ```

12. **Read the output JSON** from `$CROSSREVIEW_OUTPUT` and parse it.

    - If the backend returns a structured harness failure instead of review findings, surface that explicitly as an operational blocker and stop pretending a substantive cross-harness review occurred.

13. **Present findings** to the user with:
    - scope
    - phase
    - reviewer harness/model/effort
    - lane ID and branch when present
    - blocking and non-blocking issues

14. **Append to `review.md`** in FEATURE_DIR under a `### Cross-Harness Review` section.

15. **If blocking issues exist**, recommend addressing them before merge.

16. **Check for extension hooks** under `hooks.after_crossreview` in `.specify/extensions.yml` and surface optional or mandatory hook execution instructions.
