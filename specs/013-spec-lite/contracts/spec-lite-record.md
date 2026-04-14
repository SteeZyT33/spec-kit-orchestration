# Contract: Spec-Lite Record

**Status**: Draft
**Parent**: [013-spec-lite plan.md](../plan.md)
**Binds**: `src/speckit_orca/spec_lite.py` (runtime),
`commands/spec-lite.md` (command prompt, deferred),
`src/speckit_orca/flow_state.py` (reader integration),
`src/speckit_orca/matriarch.py` (rejection guard via
[matriarch-guard.md](./matriarch-guard.md))

---

Defines the durable on-disk shape of a `spec-lite` record. A
spec-lite record is a single markdown file — not a directory, not
a multi-file feature folder. It is deliberately the lightest
first-class intake artifact in Orca.

## Location

One file per record, under a global registry:

```
.specify/orca/spec-lite/
├── 00-overview.md             ← generated index, see below
├── SL-001-<slug>.md
├── SL-002-<slug>.md
└── ...
```

- **Global registry** — not per-feature. Matches
  `brainstorm-memory` and `evolve` conventions.
- **One file per record.** No per-record directory. Review
  artifacts, if opted in, live as sibling files sharing the
  record's ID stem (e.g., `SL-001-<slug>.self-review.md`) rather
  than inside a per-record directory. See
  [quickstart.md](../quickstart.md) for the opt-in review flow.
- **ID scheme: `SL-NNN-<slug>`** — matches evolve's `EV-NNN-<slug>`
  pattern. `NNN` is zero-padded to 3 digits, monotonically
  increasing, gaps allowed (deletions leave holes; new records do
  not backfill).
- **Filename: `<id>.md`** — the full ID including slug is the
  filename stem. Example: `SL-001-cs2-team-stats-sync.md`.

## File structure

A valid spec-lite record MUST have:

1. **Title heading** — `# Spec-Lite SL-<NNN>: <title>` (exact
   format, used by header-scan detection in matriarch guard)
2. **Metadata block** — 3 required fields
3. **Body sections** — 4 required + 1 optional, in the exact
   order shown below

### Full template

```markdown
# Spec-Lite SL-<NNN>: <title>

**Source Name**: <operator or agent identifier>
**Created**: YYYY-MM-DD
**Status**: open | implemented | abandoned

## Problem
<1-2 sentences: what's broken, missing, or needed>

## Solution
<1-2 sentences: what you're doing about it>

## Acceptance Scenario
<one BDD given/when/then — manual or test>

## Files Affected
- <path>
- <path>

## Verification Evidence (optional)
<command, output, or manual step — added after completion>
```

## Metadata fields (3, all required)

| Field | Type | Required | Notes |
|---|---|---|---|
| `Source Name` | string | yes | Operator name or agent identifier (e.g., `claude`, `codex`, `operator`). Free-form, used for provenance only. |
| `Created` | `YYYY-MM-DD` | yes | RFC3339 full-date. Matches evolve and brainstorm-memory conventions. Must be set at record creation, never mutated thereafter. |
| `Status` | enum | yes | One of `open`, `implemented`, `abandoned`. Starts at `open`; advances via explicit operator action or runtime API. |

**No `Promoted To` field.** Spec-lite has no formal promotion
pathway per the 013 plan question 6 resolution. An operator who
wants to turn a spec-lite into a full spec hand-authors the full
spec and links back to the spec-lite by ID in the full spec's
body; the relationship is documented in the new spec, not here.

### Status enum semantics

- **`open`** — record is drafted; implementation has not started
  or is in progress. Default for a fresh record.
- **`implemented`** — the solution has landed and (if the optional
  Verification Evidence section is populated) has been verified.
  Terminal state for the happy path.
- **`abandoned`** — the record was created but never implemented
  and will not be. Terminal state. Kept on disk as historical
  context; operators are not expected to delete abandoned records.

Status transitions are explicit operator actions (via the runtime
module or manual edit). There is no automatic advancement.

## Body sections (5: 4 required + 1 optional)

Every valid spec-lite record MUST contain the first four body
sections, in this exact order, with the exact heading text shown.
The fifth is optional.

| # | Heading | Required | Content shape |
|---|---|---|---|
| 1 | `## Problem` | yes | 1-2 sentences. What's broken, missing, or needed. |
| 2 | `## Solution` | yes | 1-2 sentences. What you're doing about it. |
| 3 | `## Acceptance Scenario` | yes | One BDD given/when/then scenario (manual or test). |
| 4 | `## Files Affected` | yes | Bulleted list of file paths. At least one entry. |
| 5 | `## Verification Evidence` | no | Command, output, or manual step. Added after implementation. Omitted until relevant. |

**Intentionally absent:**

- No `## Mini-Plan` — spec-lite has no phase decomposition.
- No `## Verification Mode` enum — verification is optional and
  unstructured.
- No `## Code Review Handoff` — review participation is opt-out
  per the 013 plan question 3 resolution.
- No `## Promoted To` / `## Promotion Notes` — spec-lite does not
  promote; see plan question 6.

These omissions are the core difference from the retired
`micro-spec` shape. They are not bugs, they are the point.

## Detection rules

A file is a spec-lite record if EITHER of these holds:

1. **Path match**: the file lives under
   `.specify/orca/spec-lite/` AND has a `.md` extension AND the
   filename stem matches `SL-\d{3}(-.+)?` (regex).
2. **Header match** (fallback for misplaced files): the file's
   first non-blank line matches `^# Spec-Lite SL-\d{3}(:.*)?$`
   (regex).

Path match takes precedence. Header match only applies to files
outside the canonical directory (for safety against mislocation).

The overview file `.specify/orca/spec-lite/00-overview.md` is NOT
a record — it is generated by `regenerate_overview` and is
explicitly excluded from the record-listing walk by filename.

## Invariants

- Exactly one file per record; no per-record directory.
- Filename stem equals the ID (`SL-NNN-<slug>`).
- ID is unique across the registry. The runtime assigns the next
  available `NNN` at creation time; operators SHOULD NOT
  hand-author an ID that collides with an existing one.
- Metadata block appears before any body section.
- Metadata fields are exactly the three defined above; additional
  metadata lines are ignored by parsers but discouraged.
- `## Files Affected` has at least one non-empty bullet entry.
- `## Verification Evidence` is either absent entirely or has
  non-empty body content. An empty `## Verification Evidence`
  heading with no body is invalid.
- Status is one of the three enum values (lowercase, exact).
- `Created` is never mutated after the record is first written.
- All headings use exact text as specified (case-sensitive).

## Overview file

`.specify/orca/spec-lite/00-overview.md` is a generated index of
all records in the registry. Shape:

```markdown
# Spec-Lite Overview

_Generated by `speckit_orca.spec_lite regenerate-overview`. Do not edit by hand._

## Active records (`open`)

- **[SL-001-<slug>](./SL-001-<slug>.md)** — <title> _(created YYYY-MM-DD)_
- ...

## Implemented records

- **[SL-002-<slug>](./SL-002-<slug>.md)** — <title> _(created YYYY-MM-DD, implemented)_
- ...

## Abandoned records

- **[SL-003-<slug>](./SL-003-<slug>.md)** — <title> _(created YYYY-MM-DD, abandoned)_
- ...
```

- Regeneration is automatic on every `create`, `update-status`,
  and explicit `regenerate-overview` call.
- The overview file is safe to delete; the next runtime call
  recreates it.
- Operators MUST NOT hand-edit the overview; edits are lost on
  next regeneration.

## Flow-state interpretation

`flow_state.py` reads a spec-lite record and returns:

```python
{
    "kind": "spec-lite",
    "id": "SL-001",
    "slug": "cs2-team-stats-sync",
    "title": "...",
    "source_name": "...",
    "created": "YYYY-MM-DD",
    "status": "open" | "implemented" | "abandoned",
    "files_affected": ["path", ...],
    "has_verification_evidence": bool,
    "review_state": "unreviewed" | "self-reviewed" | "cross-reviewed",
}
```

- `review_state` defaults to `unreviewed` per the opt-out default.
- `review_state` flips to `self-reviewed` or `cross-reviewed`
  only if a review artifact exists as a sibling file sharing the
  record ID stem (e.g., `SL-001-<slug>.self-review.md`,
  `SL-001-<slug>.cross-review.md`).
- Flow-state does NOT try to track relationships between a
  spec-lite and a hand-authored full spec that cites it.

## Forbidden operations

- **No programmatic mutation of `Created`.** It is write-once.
- **No lane registration.** The matriarch guard rejects
  registering a lane against a spec-lite record — see
  [matriarch-guard.md](./matriarch-guard.md).
- **No promote command.** There is no `speckit.orca.spec-lite
  promote <id>` subcommand; the runtime module exposes no
  `promote_record` function. See plan question 6.
- **No phase gates, no verification mode, no review handoff.**
  These are micro-spec features that spec-lite deliberately drops.

## Parser notes

Per the plan's open questions for contracts, the 013 runtime
MUST use a pure-markdown parser with strict section-name matching
(no YAML frontmatter). This matches evolve and brainstorm-memory
conventions and avoids a new dependency. The parser:

1. Reads the file line by line.
2. Extracts the title from the `# Spec-Lite SL-NNN: ...` heading.
3. Walks metadata lines (`**Field**: value`) until the first
   `##` heading.
4. Splits body into sections at each `##` heading until EOF.
5. Validates section names against the required set.
6. Returns a typed record struct.

Malformed files raise a structured parse error with the line
number and expected vs actual content. Flow-state catches parse
errors and reports the record as `kind: "spec-lite", status:
"invalid"` rather than crashing.

## Supersedes

This contract supersedes the `micro-spec` record shape documented
in the retired `commands/micro-spec.md` prompt. The micro-spec
audit (`docs/research/micro-spec-audit-2026-04-11.md`) confirmed
zero existing `micro-spec` records on main, so there is no
on-disk migration to perform — only vocabulary retirement in the
runtime and command surface.
