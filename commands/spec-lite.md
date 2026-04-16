---
description: "Lightweight intake command for bounded work. Writes a single-file spec-lite record (problem, solution, acceptance scenario, files affected) under .specify/orca/spec-lite/. Replaces the retired micro-spec."
---

# spec-lite — intake stub

> **Prompt status**: STUB. The full operator-facing prompt body
> is being rewritten in a separate follow-up PR per the 013 plan's
> deferral pattern (same convention used for 012). This stub
> exists so the extension manifest can register the command and
> the runtime module has a caller.

## Runtime

The command dispatches to the Python CLI
`python -m speckit_orca.spec_lite` with the following subcommands:

- `create --title "..." --problem "..." --solution "..." --acceptance "..." --files-affected "p1,p2"`
  — creates a new record with auto-allocated `SL-NNN` id.
- `list [--status open|implemented|abandoned]` — lists records.
- `get <SL-NNN[-slug]>` — shows a single record.
- `update-status <id> <open|implemented|abandoned> [--verification-evidence "..."]`
  — transitions status, optionally attaches verification evidence.
- `regenerate-overview` — rewrites `00-overview.md` from records.

## Records

Records live at `.specify/orca/spec-lite/SL-NNN-<slug>.md` with
3 metadata fields (Source Name, Created, Status) and 5 body
sections (Problem, Solution, Acceptance Scenario, Files Affected
required; Verification Evidence optional).

## Not supported

- No `promote` command — spec-lite is reference-only per 013 plan
  Q6. If scope grows, hand-author a full spec under `specs/` and
  cite the spec-lite by ID in the full spec's body.
- No matriarch lane registration — the guard rejects spec-lite
  records. Full coordination requires promoting to a full spec.

## User Input

```text
$ARGUMENTS
```
