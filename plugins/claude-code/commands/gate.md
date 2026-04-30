---
description: Check whether an SDD-managed feature has cleared gates for a target stage. Wraps the orca completion-gate capability.
handoffs:
  - label: Re-Run Once Blockers Are Addressed
    agent: orca:gate
    prompt: Re-run the completion gate after fixing blockers
  - label: Fix Spec
    agent: speckit.specify
    prompt: Address spec-stage blockers (missing spec, [NEEDS CLARIFICATION], etc.)
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

`gate` is the personal SDD wrapper around the orca `completion-gate`
capability. It evaluates whether a feature has cleared the artifact +
evidence gates for a given stage transition (`plan-ready`,
`implement-ready`, `pr-ready`, `merge-ready`).

This is a **lint, not formal verification**. A `pass` status means the
documented gates passed; the operator decides whether to proceed.

## Workflow Contract

- Read user input for `--target-stage` (one of `plan-ready`,
  `implement-ready`, `pr-ready`, `merge-ready`). Default: `plan-ready`.
- Read user input for `--persist` (write to `<feature-dir>/gate-history.md`).
- Resolve `<feature-dir>` from user input or current branch.
- Invoke `orca-cli completion-gate` and render results.
- Report status to the user.

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

1. Resolve `<feature-id>` from user input or current branch, then resolve
   `<feature-dir>` via the host-aware adapter:

   ```bash
   FEATURE_DIR="$(orca-cli resolve-path --kind feature-dir --feature-id "$FEATURE_ID")"
   ```

   Honors `.orca/adoption.toml` if present; otherwise auto-detects.

2. Determine `--target-stage` from user input (default `plan-ready`).

3. If the operator provided `--evidence-json` (e.g., `'{"ci_green": true}'`),
   pass it through. Otherwise omit.

4. Invoke `orca-cli completion-gate`. Use the no-evidence form by default;
   switch to the with-evidence form when the operator passed
   `--evidence-json`.

   (If `uv run orca-cli ...` fails with `Failed to spawn`, see the
   Prerequisites section above and substitute `"${ORCA_RUN[@]}"` /
   `"${ORCA_PY[@]}"` in the snippets below.)

   Without `--evidence-json`:

   ```bash
   uv run orca-cli completion-gate \
     --feature-dir "$FEATURE_DIR" \
     --target-stage "<stage>" \
     > "$FEATURE_DIR/.gate-envelope.json"
   ```

   With `--evidence-json` (e.g., CI green status):

   ```bash
   uv run orca-cli completion-gate \
     --feature-dir "$FEATURE_DIR" \
     --target-stage "<stage>" \
     --evidence-json '{"ci_green": true}' \
     > "$FEATURE_DIR/.gate-envelope.json"
   ```

5. Render markdown:

   ```bash
   uv run python -m orca.cli_output render-completion-gate \
     --target-stage "<stage>" \
     --envelope-file "$FEATURE_DIR/.gate-envelope.json" \
     > "$FEATURE_DIR/.gate-report.md"
   cat "$FEATURE_DIR/.gate-report.md"
   ```

6. If `--persist` was passed, append the report to
   `$FEATURE_DIR/gate-history.md`:

   ```bash
   cat "$FEATURE_DIR/.gate-report.md" >> "$FEATURE_DIR/gate-history.md"
   ```

7. Report status to the user (one of `pass`, `blocked`, `stale`) and
   list any blockers / stale artifacts. If `blocked`, recommend the
   appropriate handoff (e.g., spec revision for `spec_exists` /
   `no_unclarified` blockers).

## Errors

If `orca-cli completion-gate` returns `Err(...)`:

- `INPUT_INVALID`: report the message verbatim; the gate did not run.
- Other kinds: surface the `detail.underlying` if present.
