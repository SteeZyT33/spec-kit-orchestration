---
description: Cross-only adversarial review of a clarified spec. Validates cross-spec consistency, feasibility, security implications, dependency risks, and industry patterns against the feature's spec.md.
handoffs:
  - label: Revise The Spec
    agent: speckit.specify
    prompt: Spec review found issues - revise the spec before planning
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

`review-spec` is 012's cross-only spec review. A different agent from the
spec author examines the clarified `spec.md` for consistency, feasibility,
security, dependencies, and industry-pattern alignment. There is no
self-pass - spec review is adversarial by design.

## Workflow Contract

- Read the feature's `spec.md` (and `brainstorm.md` / `plan.md` if present
  for context).
- Produce a structured review artifact at
  `<feature-dir>/review-spec.md` with cross-pass findings.
- Do not implement anything. Do not modify the spec.
- If the spec has critical issues, record them and recommend revision
  before planning proceeds.

## Prerequisites

The examples below assume `orca-cli` is on PATH. In a fresh host repo where
spec-kit-orca is not installed as a tool, `uv run orca-cli` fails with
`Failed to spawn: orca-cli`. Resolve the invocation up front:

```bash
if command -v orca-cli >/dev/null 2>&1; then
  ORCA_RUN=(orca-cli)
  ORCA_PY=(python -m orca.cli_output)
elif [ -n "${ORCA_PROJECT:-}" ] && [ -d "$ORCA_PROJECT" ]; then
  ORCA_RUN=(uv run --project "$ORCA_PROJECT" orca-cli)
  ORCA_PY=(uv run --project "$ORCA_PROJECT" python -m orca.cli_output)
elif [ -d "$HOME/spec-kit-orca" ]; then
  ORCA_RUN=(uv run --project "$HOME/spec-kit-orca" orca-cli)
  ORCA_PY=(uv run --project "$HOME/spec-kit-orca" python -m orca.cli_output)
else
  echo "orca-cli not found; install spec-kit-orca or set ORCA_PROJECT" >&2
  exit 1
fi
```

Use `"${ORCA_RUN[@]}"` in place of `orca-cli` and `"${ORCA_PY[@]}"` in place of
`python -m orca.cli_output` in the bash blocks below when the bare forms fail.

## Outline

1. Resolve `<feature-id>` from user input or current branch.
   - If user passed `--feature <id>`, use that.
   - Else infer from branch name (e.g., `001-foo` from branch `001-foo`).

2. Resolve `<feature-dir>` via host-aware adapter:

   ```bash
   FEATURE_DIR="$(orca-cli resolve-path --kind feature-dir --feature-id "$FEATURE_ID")"
   ```

   This honors `.orca/adoption.toml` if present; otherwise auto-detects
   the host's spec system (spec-kit, openspec, superpowers, or bare).
   For host repos that haven't run `orca-cli adopt`, this still works.

3. Determine the next round number: count existing `### Round N - ` or `### Round N — ` headers (em-dash legacy form supported for backward compat) in `<feature-dir>/review-spec.md` (if it exists), N+1 is the new round; otherwise round 1.

4. Build the cross-pass review prompt and dispatch the in-session Claude reviewer (Claude Code only):

   (If `uv run orca-cli ...` fails with `Failed to spawn`, see the
   Prerequisites section above and substitute `"${ORCA_RUN[@]}"` /
   `"${ORCA_PY[@]}"` in the snippets below.)

   ```bash
   ORCA_PROMPT=$(uv run orca-cli build-review-prompt \
     --kind spec \
     --criteria cross-spec-consistency \
     --criteria feasibility \
     --criteria security \
     --criteria dependencies \
     --criteria industry-patterns)
   ```

   Dispatch a `Code Reviewer` subagent via the Agent tool with:
   - description: `Cross-pass review of <feature-id> spec.md`
   - prompt: `$ORCA_PROMPT` followed by the full text of `<feature-dir>/spec.md`

   Capture the subagent's full response text. Then pipe it through
   `parse-subagent-response` to validate and write the findings file:

   ```bash
   printf '%s' "$SUBAGENT_RESPONSE" | uv run orca-cli parse-subagent-response \
     > "<feature-dir>/.review-spec-claude-findings.json"
   ```

   If `parse-subagent-response` exits non-zero, append a `### Round N - FAILED` block to `<feature-dir>/review-spec.md` describing the parse failure and STOP.

5. Invoke `orca-cli cross-agent-review` against the spec, providing the file-backed claude findings:

   (If `uv run orca-cli ...` fails with `Failed to spawn`, see the
   Prerequisites section above and substitute `"${ORCA_RUN[@]}"` /
   `"${ORCA_PY[@]}"` in the snippets below.)

   ```bash
   uv run orca-cli cross-agent-review \
     --kind spec \
     --target "<feature-dir>/spec.md" \
     --feature-id "<feature-id>" \
     --reviewer cross \
     --claude-findings-file "<feature-dir>/.review-spec-claude-findings.json" \
     --criteria "cross-spec-consistency" \
     --criteria "feasibility" \
     --criteria "security" \
     --criteria "dependencies" \
     --criteria "industry-patterns" \
     > "<feature-dir>/.review-spec-envelope.json"
   ```

   Live mode (real LLM calls) requires `ORCA_LIVE=1`. For dry-run/testing
   set `ORCA_FIXTURE_REVIEWER_CLAUDE` and `ORCA_FIXTURE_REVIEWER_CODEX`
   to JSON fixture paths.

6. Translate the JSON envelope into a markdown round-block:

   ```bash
   uv run python -m orca.cli_output render-review-spec \
     --feature-id "<feature-id>" \
     --round <N> \
     --envelope-file "<feature-dir>/.review-spec-envelope.json" \
     >> "<feature-dir>/review-spec.md"
   ```

7. Read the resulting `review-spec.md` and report verdict to the user:
   - `ready` if the round had no findings
   - `needs-revision` if there are blocker/high findings
   - `blocked` if the envelope was a failure (`ok: false`)

8. If a handoff is appropriate, route via the existing `handoffs` block in this file's frontmatter.

## Guardrails

- This is a CROSS-only review. The reviewing agent must be different from
  the agent that authored the spec. If you are the author, say so and
  recommend routing to a different agent via the cross-pass mechanism.
- Do not conflate spec review with code review. Spec review examines the
  DESIGN artifact, not implementation code.
- If no `spec.md` exists for the target feature, stop and explain;
  do not fabricate a review against missing input.
