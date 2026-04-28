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

## Outline

1. Resolve `--content-path` from user input. Required.

2. Resolve `--reference-set` paths from user input. If none provided,
   default to `events.jsonl`, `experiments.tsv`, and any
   `specs/<feature>/research.md` files present in the repo root.

3. Determine `--mode` from user input (default `strict`).

4. Invoke `orca-cli citation-validator`. Resolve a base directory
   for command artifacts: use `$FEATURE_DIR` if a feature dir is
   resolvable, else fall back to the repo root (`.`):

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
