---
description: Structured pre-spec ideation that captures the problem, options, constraints, and recommendation without dropping into implementation.
handoffs:
  - label: Write The Spec
    agent: speckit.specify
    prompt: Turn the brainstorm output into a proper spec
  - label: Plan The Feature
    agent: speckit.plan
    prompt: Turn the brainstorm output into an implementation plan
  - label: Use Quicktask Instead
    agent: speckit.orca.micro-spec
    prompt: This looks small enough for the micro-spec lane
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

This command is Orca's native ideation stage. It exists to replace dependence on
external brainstorming workflows and keep early design work inside the same Spec
Kit ecosystem as the rest of the feature lifecycle.

This is **not** an implementation command.

## Workflow Contract

- Capture framing, constraints, alternatives, and a recommendation.
- Stop before implementation.
- Do not generate implementation tasks.
- Do not route directly to `/speckit.implement`.
- Hand off to `/speckit.specify`, `/speckit.plan`, or `/speckit.orca.micro-spec`.

## Outline

1. Determine whether the request is:
   - new feature ideation
   - refinement of an existing feature
   - small enough to fit the micro-spec lane instead

2. Resolve artifact destination with this precedence:
   - If `--feature <id>` was provided, use `specs/<feature>/brainstorm.md`
   - Else if an active feature context can be resolved from the current branch or prerequisite script and the user is refining that feature, use `specs/<feature>/brainstorm.md`
   - Else if this is durable new-idea capture or a revisit of durable brainstorm memory, write to `brainstorm/NN-topic-slug.md` and regenerate `brainstorm/00-overview.md`
   - Else use `.specify/orca/inbox/brainstorm-<timestamp>.md` only for intentionally temporary scratch capture

3. Gather the minimum context needed:
   - the user request
   - any existing `spec.md`, `plan.md`, `tasks.md`, `research.md`, or `review.md` for the target feature if it exists
   - any relevant repo constraints that materially shape the solution

4. For durable brainstorm-memory operations, use the deterministic helper rather than hand-editing numbering or overview files:

   - create a new record:
     `uv run python -m speckit_orca.brainstorm_memory create --root <repo> --title "<title>" ...`
   - inspect likely revisit candidates:
     `uv run python -m speckit_orca.brainstorm_memory matches --root <repo> --title "<title>"`
   - update an existing record additively:
     `uv run python -m speckit_orca.brainstorm_memory update --path <record> --revision-summary "<summary>" ...`
   - recover or refresh the overview explicitly when needed:
     `uv run python -m speckit_orca.brainstorm_memory regenerate-overview --root <repo>`

   For feature-scoped brainstorm work that is intended to flow into another
   Orca stage, create or refresh the matching handoff file:

   - brainstorm to specify:
     `uv run python -m speckit_orca.context_handoffs create --feature-dir specs/<feature> --source-stage brainstorm --target-stage specify --summary "<ready-for-spec summary>" --artifact specs/<feature>/brainstorm.md`
   - if planning is the real next step, keep the brainstorm handoff pointed at
     `specify` and let the later `specify -> plan` handoff be created from the
     resulting spec artifact instead of inventing an unsupported direct
     brainstorm-to-plan transition

5. Produce a structured brainstorm artifact with these sections:

   ```markdown
   # Brainstorm

   ## Problem
   ## Desired Outcome
   ## Constraints
   ## Existing Context
   ## Options Considered
   ## Recommendation
   ## Open Questions
   ## Ready For Spec
   ```

   Durable brainstorm records in `brainstorm/` also require stable metadata:

   ```text
   **Status**: active|parked|abandoned|spec-created
   **Created**: YYYY-MM-DD
   **Updated**: YYYY-MM-DD
   **Downstream**: none|<type>:<ref>
   ```

6. In `## Options Considered`, include at least:
   - one favored path
   - one meaningful alternative
   - brief reasons for rejection or downgrade of the alternative

7. In `## Ready For Spec`, write a short handoff summary suitable for the next command:
   - If this needs a formal feature spec, recommend `/speckit.specify`
   - If a spec already exists and the main missing artifact is architecture/decomposition, recommend `/speckit.plan`
   - If the work is bounded enough for the micro-spec lane, recommend `/speckit.orca.micro-spec`

   When writing to `specs/<feature>/brainstorm.md`, reuse that summary as the
   `context_handoffs create --summary` value so the next stage has a durable
   machine-readable handoff as well as prose guidance.

8. Output a concise summary to the user:
   - artifact path
   - overview path when durable brainstorm memory was written or updated
   - recommended next command
   - any unresolved questions that block progression

## Guardrails

- If the work is clearly a small bugfix, narrow refactor, tooling tweak, or docs update, say so and recommend `/speckit.orca.micro-spec` instead of pretending it needs full feature ideation.
- If the request is still too vague after initial framing, state the open questions explicitly in the artifact instead of making false precision.
- If an existing feature artifact already contains a brainstorm file, update it in place rather than creating a parallel brainstorm file in the same feature directory.
- Default to not saving trivial sessions unless the user explicitly asks to preserve them.
- Treat the session as meaningful when at least two core sections contain substantive content, the core body is roughly 100 non-whitespace characters, or the user explicitly asks to preserve it.
- When related brainstorm memory records exist, surface the likely matches and require an intentional choice between updating an existing record and creating a new one.
- After any durable brainstorm-memory write or update, regenerate `brainstorm/00-overview.md`.
