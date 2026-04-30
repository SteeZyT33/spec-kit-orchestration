---
description: Validate citations and ref hygiene in synthesis text using rule-based heuristics. Wraps the orca citation-validator capability.
handoffs:
  - label: Address Uncited Claims
    agent: orca:cite
    prompt: Re-run after adding refs to flagged claims
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

`cite` is the personal SDD wrapper around the orca `citation-validator`
capability. It scans synthesis prose for assertion-shaped sentences
without `[ref]` brackets and `[ref]` brackets that don't resolve to a
known reference path.

This is a **lint, not scientific validation** of the underlying claims.
Rule-based heuristics catch surface-syntactic patterns (assertion verbs,
numerical claims) and miss semantic claims. See
`docs/capabilities/citation-validator/README.md` for limitations
(year false-positives, abbreviation handling, ref normalization).

## Workflow Contract

- Read user input for `--content-path` (the synthesis file).
- Read user input for `--reference-set` (repeatable; paths to refs).
- Read user input for `--mode` (`strict` or `lenient`; default `strict`).
- Read user input for `--write` (append to `<feature-dir>/cite-report.md`).
- Invoke `orca-cli citation-validator` and render results.

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

1. Resolve `--content-path` from user input. Required.

1a. Resolve `<feature-dir>` via the host-aware adapter (used in the
   reference-set discovery below):

   ```bash
   FEATURE_DIR="$(orca-cli resolve-path --kind feature-dir --feature-id "$FEATURE_ID")"
   ```

   Honors `.orca/adoption.toml` if present; otherwise auto-detects.

2. Resolve `--reference-set` paths. If the operator passed any
   `--reference-set` flag(s), use those. Otherwise auto-discover
   via `orca-cli resolve-path --kind reference-set`:

   ```bash
   REFS=()
   while IFS= read -r ref; do
     [ -n "$ref" ] && REFS+=("--reference-set" "$ref")
   done < <(orca-cli resolve-path --kind reference-set --feature-id "$FEATURE_ID" 2>/dev/null)
   ```

   This produces the same canonical artifact list (`plan.md`,
   `data-model.md`, `research.md`, `quickstart.md`, `tasks.md`,
   `contracts/**/*.md`) as the legacy bash loop, but consults the
   host-aware adapter so adopted hosts on openspec/superpowers/bare
   layouts also work.

   If `REFS` is empty (no SDD artifacts present), fall back to whatever
   the operator explicitly passes; the capability runs against an empty
   reference set and reports broken refs accordingly.

3. Determine `--mode` from user input (default `strict`).

4. Invoke `orca-cli citation-validator`. Resolve a base directory
   for command artifacts: use `$FEATURE_DIR` if a feature dir is
   resolvable, else fall back to the repo root (`.`):

   (If `uv run orca-cli ...` fails with `Failed to spawn`, see the
   Prerequisites section above and substitute `"${ORCA_RUN[@]}"` /
   `"${ORCA_PY[@]}"` in the snippets below.)

   ```bash
   BASE_DIR="${FEATURE_DIR:-.}"
   uv run orca-cli citation-validator \
     --content-path "<content-path>" \
     --reference-set "<ref1>" \
     --reference-set "<ref2>" \
     --mode "<mode>" \
     > "$BASE_DIR/.cite-envelope.json"
   ```

5. Render markdown:

   ```bash
   uv run python -m orca.cli_output render-citation \
     --content-path "<content-path>" \
     --envelope-file "$BASE_DIR/.cite-envelope.json" \
     > "$BASE_DIR/.cite-report.md"
   cat "$BASE_DIR/.cite-report.md"
   ```

6. If `--write` was passed, append the report to a `cite-report.md`
   artifact (under the feature dir if resolvable, else the repo root):

   ```bash
   cat "$BASE_DIR/.cite-report.md" >> "$BASE_DIR/cite-report.md"
   ```

7. Report coverage + counts to the user. If coverage < 1.0, list the
   uncited claims with line numbers so the operator can address them.

## Errors

If `orca-cli citation-validator` returns `Err(...)`:

- `INPUT_INVALID`: report the message verbatim (typical: missing
  `--content-path` or non-existent file).
