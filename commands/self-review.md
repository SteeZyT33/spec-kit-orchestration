---
description: Process retrospective that evaluates workflow effectiveness, identifies improvement opportunities, and dispatches agents to improve extension commands.
handoffs:
  - label: Run Code Review
    agent: speckit.orca.code-review
    prompt: Run the standard code-review passes on the current phase
  - label: Cross-Harness Review
    agent: speckit.orca.cross-review
    prompt: Run a cross-harness adversarial review
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

This is NOT a code review. This is a **process review** — an introspective pass over the spec-driven development workflow itself. The goal is to evaluate what worked, what didn't, and to automatically improve the orchestration extension commands based on what we learned.

## Outline

1. Run the prerequisite script from repo root to identify FEATURE_DIR and available artifacts. All paths must be absolute.

2. **Load process artifacts** — read from FEATURE_DIR:
   - `spec.md` — original requirements and acceptance criteria
   - `plan.md` — architecture decisions made at planning time
   - `tasks.md` — task breakdown, phase boundaries, completion status
   - shared flow-state output when available — artifact-first stage and milestone interpretation
   - `review.md` — review findings, fixes applied, PR lifecycle history
   - Git log for the feature branch — commit frequency, revert patterns, fix-after-fix sequences
   - If `.specify/orca/worktrees/registry.json` exists, load lane metadata for this feature
   - If available, load delivery evidence:
     - branch naming shape
     - lane branch to feature branch relationship
     - PR structure notes from review artifacts or git history

3. **Evaluate process dimensions** — for each dimension, produce a score (1-5) and specific evidence:

   ### Dimension 1: Spec Fidelity
   - Did the spec accurately predict what was needed?
   - What requirements were added mid-implementation that should have been in the original spec?
   - What specified requirements turned out to be unnecessary?
   - **Signal**: Scope creep findings in review.md, unplanned tasks added to tasks.md

   ### Dimension 2: Plan Accuracy
   - Did the architecture hold up or did it change significantly during implementation?
   - Were the file paths and module boundaries in plan.md correct?
   - **Signal**: Code quality findings about plan deviations in review.md

   ### Dimension 3: Task Decomposition Quality
   - Were tasks right-sized? (Too large = multi-day, too small = trivial)
   - Were dependencies correctly identified?
   - Were any tasks blocked that shouldn't have been?
   - **Signal**: Git commit patterns — many small fixes after a task "completed" indicates poor decomposition

   ### Dimension 4: Review Effectiveness
   - How many issues were caught by review vs discovered later?
   - What was the auto-fix vs suggest-fix vs flag-only ratio?
   - Did cross-review find things the primary review missed?
   - **Signal**: review.md actions taken section, post-merge verification results

   ### Dimension 5: Workflow Friction
   - Where did the developer (or agent) spend time fighting the process instead of building?
   - Were there unnecessary round-trips between commands?
   - Did any extension hooks block progress without adding value?
   - **Signal**: Time gaps in git log, repeated runs of the same command, abandoned branches, blocked or stale Orca lanes

   ### Lane And Delivery Evidence (required when available)
   - Were lane boundaries clear or did they overlap?
   - Did lane ownership reduce merge pain or create churn?
   - Were branch names, commits, and PR shape aligned with the lane model?
   - **Signal**: stale lane records, blocked lanes, cross-lane shared-file edits, noisy commit history, unclear branch/PR integration path

4. **Produce the retrospective report** — write to `FEATURE_DIR/self-review.md`:

   ```markdown
   # Process Self-Review — [feature name]

   **Date**: YYYY-MM-DD
   **Feature**: [branch name]
   **Duration**: [first commit] → [last commit]

   ## Scores

   | Dimension | Score | Key Evidence |
   |-----------|-------|-------------|
   | Spec Fidelity | X/5 | ... |
   | Plan Accuracy | X/5 | ... |
   | Task Decomposition | X/5 | ... |
   | Review Effectiveness | X/5 | ... |
   | Workflow Friction | X/5 | ... |

   ## What Worked
   - [specific things that went well, with evidence]

   ## What Didn't
   - [specific problems, with evidence]

   ## Process Improvements
   - [actionable changes to how we work]

   ## Extension Improvements
   - [specific changes to orchestration commands based on this experience]
   ```

5. **Extract extension improvement candidates** — from the retrospective, identify concrete improvements to orchestration extension commands:

   For each candidate improvement:
   - Which command file needs to change (review.md, assign.md, crossreview.md, self-review.md)
   - What specific section or behavior should change
   - Why (link to retrospective evidence)
   - Risk level: LOW (wording/instructions), MEDIUM (new behavior), HIGH (changes existing behavior)

   Also extract protocol-level improvement candidates when evidence points to:
   - lane metadata ambiguity
   - delivery hygiene problems (branch, commit, or PR structure)
   - quicktask misuse as a spec bypass or test-discipline bypass

6. **Dispatch improvement agents** — apply in dependency order (inspired by spec-kit-iterate):

   Improvements MUST be applied in this order to prevent broken cross-references:
   1. `extension.yml` (manifest changes)
   2. `config-template.yml` (configuration changes)
   3. `commands/assign.md` (upstream in workflow)
   4. `commands/code-review.md` (mid-workflow)
   5. `commands/cross-review.md` (late workflow)
   6. `commands/self-review.md` (terminal — this file)
   7. `bootstrap.sh` and `README.md` (documentation)

   For each LOW or MEDIUM risk improvement, launch a background agent to:
   a. Read the current command file from the orchestration extension repo
   b. Verify the target section still exists (guard against stale improvements)
   c. Apply the specific improvement
   d. Run a syntax/consistency check — does the change reference sections, flags, or behaviors that exist in other commands?
   e. Commit with message: `fix(self-review): [description] — from [feature] retrospective`
   f. Report what was changed

   For HIGH risk improvements:
   - Write them to `FEATURE_DIR/self-review.md` under `## Deferred Improvements`
   - Do NOT auto-apply — these need human review

7. **Check community catalog for new relevant extensions**:

   Read the community catalog at the project's cached location or fetch from upstream.
   Compare installed extensions against available ones. Flag any new extensions that:
   - Address a problem identified in this retrospective
   - Overlap with something we're doing manually
   - Could replace a workaround we invented

   Output: `## Community Extension Opportunities` section in self-review.md

8. **Completion** — output summary:
   - Process scores table
   - Count of improvements dispatched (LOW/MEDIUM) and deferred (HIGH)
   - Any community extension recommendations
   - Path to self-review.md
