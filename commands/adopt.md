---
description: "Brownfield intake command — record existing features as durable reference (adoption records). Single-file records under .specify/orca/adopted/ documenting summary, location, and key behaviors. Never reviewed, not drivable by yolo, cannot anchor a matriarch lane."
---

# adopt — brownfield intake stub

> **Prompt status**: STUB. The full operator-facing prompt body is
> being rewritten in a separate follow-up PR per the 015 plan's
> deferral pattern (same convention used for 012 and 013). This
> stub exists so the extension manifest can register the command
> and the runtime module has a caller.

## Runtime

The command dispatches to the Python CLI
`python -m speckit_orca.adoption` with the following subcommands:

- `create --title "..." --summary "..." --location "p1" --location "p2" --key-behavior "b1" --key-behavior "b2" [--known-gap "..."] [--baseline-commit <sha> | --no-baseline] [--adopted-on YYYY-MM-DD]`
  — creates a new adoption record with auto-allocated `AR-NNN` id.
  By default pre-populates `Baseline Commit` with the short HEAD
  SHA; `--no-baseline` omits the field.
- `list [--status adopted|superseded|retired]` — lists records,
  optionally filtered by status. (For a grouped view, see the
  auto-generated `00-overview.md` in the registry directory.)
- `get <AR-NNN[-slug]>` — shows a single record.
- `supersede <ar-id> <full-spec-id>` — marks the record as
  superseded by a full spec under `specs/`. Validates that the
  target spec's `spec.md` exists; rejects otherwise.
- `retire <ar-id> [--reason "..."]` — marks the record as retired.
  Without `--reason`, no retirement-reason section is written —
  presence of `Status: retired` is the signal (plan open question 5).
- `regenerate-overview` — rewrites `00-overview.md` from records.

## Records

Records live at `.specify/orca/adopted/AR-NNN-<slug>.md` with:

- **Metadata (2 required + 1 optional)**: Status (adopted /
  superseded / retired), Adopted-on (YYYY-MM-DD), Baseline Commit
  (optional).
- **Required body sections**: Summary, Location, Key Behaviors
  (in that relative order).
- **Optional body sections**: Known Gaps, Superseded By,
  Retirement Reason.

Unknown sections are tolerated and captured in an `extra` bucket —
015's tolerant-parser posture, explicit divergence from 013's
strict spec-lite parser (ARs are operator-editable reference
documents; spec-lite is small-new-work).

## Not supported

- No review participation — `review_state` is hard-coded to
  `"not-applicable"` in the flow-state view. ARs do NOT
  participate in 012's Review Milestone model.
- No yolo start — ARs are not a valid yolo start artifact.
- No matriarch lane anchoring — the guard in `matriarch.py`
  rejects lane registration against AR records. If you need
  coordination on an area an AR covers, hand-author a full
  spec and cite the AR as context.
- No promote path — to replace an AR with a full spec, author
  the full spec first, then run `supersede <ar-id> <spec-id>`.

## User Input

```text
$ARGUMENTS
```
