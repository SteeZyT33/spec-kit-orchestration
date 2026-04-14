# Contract: Adoption Record

**Status**: Draft
**Parent**: [015-brownfield-adoption plan.md](../plan.md)
**Binds**: `src/speckit_orca/adoption.py` (runtime),
`commands/adopt.md` (command prompt, deferred),
`src/speckit_orca/flow_state.py` (reader integration),
`src/speckit_orca/matriarch.py` (rejection guard via
[matriarch-guard.md](./matriarch-guard.md))

---

Defines the durable on-disk shape of an `Adoption Record` (AR). An
adoption record is a single markdown file — not a directory, not
a multi-file feature folder. It is the brownfield-intake counterpart
to spec-lite: where spec-lite is the lightest first-class artifact
for *new* bounded work, an adoption record is the lightest
first-class artifact for *existing* features Orca needs to know
about. Adoption records are reference-only — never reviewed, never
drivable by yolo, never anchored to a matriarch lane.

## Location

One file per record, under a global registry parallel to spec-lite:

```text
.specify/orca/adopted/
├── 00-overview.md             ← generated index, see below
├── AR-001-<slug>.md
├── AR-002-<slug>.md
└── ...
```

- **Global registry** — not per-feature. Matches `brainstorm-memory`,
  `evolve`, and `spec-lite` conventions.
- **One file per record.** No per-record directory. No sibling
  review files (ARs are not reviewed — see "Forbidden operations"
  below).
- **ID scheme: `AR-NNN-<slug>`** — matches evolve's `EV-NNN-<slug>`
  and spec-lite's `SL-NNN-<slug>` patterns. `NNN` is zero-padded to
  3 digits, monotonically increasing, gaps allowed (deletions leave
  holes; new records do not backfill).
- **Filename: `<id>.md`** — the full ID including slug is the
  filename stem. Example: `AR-001-cli-entrypoint.md`.

## File structure

A valid adoption record MUST have:

1. **Title heading** — `# Adoption Record: AR-<NNN>: <title>`
   (exact format, used by header-scan detection in matriarch guard)
2. **Metadata block** — 2 required fields + 1 optional
3. **Body sections** — 3 required + up to 3 optional, in the
   exact order shown below

### Full template

```markdown
# Adoption Record: AR-<NNN>: <title>

**Status**: adopted | superseded | retired
**Adopted-on**: YYYY-MM-DD
**Baseline Commit**: <sha>  (optional)

## Summary
<1-3 sentences describing what the feature does>

## Location
- path/to/primary/module.py
- path/to/related/file.md

## Key Behaviors
- <observed behavior 1>
- <observed behavior 2>

## Known Gaps
<optional: what's missing, unreviewed, or not yet Orca-managed>

## Superseded By
<optional: full spec ID that replaced this AR, e.g., 020-new-auth.
Written by the supersede command; typically paired with
Status: superseded.>

## Retirement Reason
<optional: free-form reason text. Written by the retire command;
typically paired with Status: retired.>
```

## Metadata fields (3 total: 2 required + 1 optional)

| Field | Type | Required | Notes |
|---|---|---|---|
| `Status` | enum | yes | One of `adopted`, `superseded`, `retired`. Starts at `adopted` for a freshly created record; advances via explicit operator action (the `supersede` or `retire` command). |
| `Adopted-on` | `YYYY-MM-DD` | yes | RFC3339 full-date. Matches evolve / brainstorm-memory / spec-lite conventions. Set at record creation, never mutated thereafter. |
| `Baseline Commit` | git SHA | no | Optional commit SHA describing the code state the record covers. Pre-populated by the `create` command with the current `git rev-parse HEAD` value; operator MAY clear before saving. Defensive fallback: if the workspace is not a git repo or `git` is unavailable, the field is omitted (the runtime does not crash). |

**No `Source Name` field** (unlike spec-lite). Adoption records
describe the feature, not the person who wrote the record. Git
blame on the record file covers authorship.

### Status enum semantics

- **`adopted`** — stable reference state; the feature exists and
  works. Default for a freshly created record. May remain in this
  state indefinitely.
- **`superseded`** — a full spec under `specs/<NNN-name>/` has
  replaced the AR. The `## Superseded By` section names the spec.
  AR file is preserved as historical context.
- **`retired`** — the feature was removed from the codebase. The
  `## Retirement Reason` section captures the operator's reason,
  if provided. AR file is preserved as historical record.

A record's status MAY transition `adopted → superseded` (via
`adopt supersede`), `adopted → retired` (via `adopt retire`), or
`superseded → retired` (the feature was first replaced by a new
spec, then later removed). The runtime does NOT enforce that
`retired → *` or `superseded → adopted` are blocked at the
operator level — markdown is hand-editable — but the `supersede`
and `retire` CLI commands operate only on records currently in
`adopted` state. Operators who want to override this manually edit
the file.

## Body sections (3 required + 3 optional)

Every valid adoption record MUST contain the first three body
sections (`Summary`, `Location`, `Key Behaviors`), with the exact
heading text shown. **When present, recognized sections MUST appear
in the relative order shown below** (required first in the listed
order, optional sections after, in the listed order). The parser
tolerates unknown sections in any position by capturing them in
an `extra` bucket — they do not violate the ordering rule for
recognized sections (see "Parser notes" below).

| # | Heading | Required | Content shape |
|---|---|---|---|
| 1 | `## Summary` | yes | 1-3 sentences describing what the feature does. |
| 2 | `## Location` | yes | Bulleted list of file paths. At least one entry. |
| 3 | `## Key Behaviors` | yes | Bulleted list of observed behaviors. At least one entry. |
| 4 | `## Known Gaps` | no | What's missing, unreviewed, or not yet Orca-managed. May appear regardless of status. |
| 5 | `## Superseded By` | no | Full spec ID that replaced the AR (e.g., `020-new-auth`). Typically paired with `Status: superseded`. |
| 6 | `## Retirement Reason` | no | Free-form reason text. Typically paired with `Status: retired`. |

**Intentionally absent:**

- No `## Problem` / `## Solution` (spec-lite shape — does not fit
  an existing feature that already works).
- No `## Acceptance Scenario` (ARs describe observed behavior, not
  test criteria for new work).
- No `## Verification Evidence` (ARs are not reviewed; nothing to
  verify against).
- No `## Touches ARs` metadata or other coordination fields (cut
  from v1 per cross-review).
- No `## Source Name` (see above).

### Status / section pairing (tolerant parser)

`Status` is authoritative. Optional sections that don't match the
declared status ARE allowed by the parser — for example, a record
with `Status: adopted` and an unexpected `## Superseded By`
section parses successfully and includes the section in its view.
The parser does NOT raise a warning, does NOT promote the status
based on section presence, and does NOT remove the section.

This is the explicit "tolerant parser" posture from plan section 6
and plan open question 7. Rationale: ARs are operator-editable
reference documents, not strict schemas. Hand edits should not
break parsing. Commands (`create`, `supersede`, `retire`) write the
expected sections for the target status; cross-section consistency
is a recommendation, not an invariant.

Structural failures DO fail parsing — see "Detection rules" and
"Parser notes" below.

## Detection rules

A file is an adoption record if EITHER of these holds:

1. **Path match**: the file lives under `.specify/orca/adopted/`
   AND has a `.md` extension AND the filename stem matches
   `AR-\d{3}-.+` (regex) — i.e., the canonical on-disk filename
   form `AR-NNN-<slug>` with a non-empty slug. The overview file
   `00-overview.md` is excluded by name. (`AR-NNN` without a slug
   is accepted as an *input alias* by commands that look up records
   — see the matriarch guard's glob fallback in
   [matriarch-guard.md](./matriarch-guard.md) — but it is not a
   valid on-disk filename for a record.)
2. **Header match** (fallback for misplaced files): the file's
   first non-blank line matches `^# Adoption Record: AR-\d{3}(:.*)?$`
   (regex).

Path match takes precedence. Header match only applies to files
outside the canonical directory (for safety against mislocation).

The overview file `.specify/orca/adopted/00-overview.md` is NOT
a record — it is generated by `regenerate_overview` and is
explicitly excluded from the record-listing walk by filename.

## Invariants

- Exactly one file per record; no per-record directory.
- Filename stem equals the ID (`AR-NNN-<slug>`).
- ID is unique across the registry. The runtime assigns the next
  available `NNN` at creation time; operators SHOULD NOT
  hand-author an ID that collides with an existing one.
- Metadata block appears before any body section.
- Required metadata fields are exactly the two defined above
  (`Status`, `Adopted-on`); `Baseline Commit` is optional but
  recognized when present. Additional metadata lines are ignored
  by parsers but discouraged.
- `## Summary` has non-empty body.
- `## Location` has at least one non-empty bullet entry.
- `## Key Behaviors` has at least one non-empty bullet entry.
- Optional sections, when present, MUST have non-empty bodies. An
  empty optional section heading with no body is treated as a
  structural failure (parses to `status: invalid`).
- Status is one of the three enum values (lowercase, exact).
- `Adopted-on` is never mutated after the record is first written.
- `Baseline Commit`, if present, is never mutated after the record
  is first written. Operators who want to update the recorded
  baseline write a new AR rather than mutating in place.
- All **recognized** headings (the 3 required + 3 optional listed
  in "Body sections" above) MUST use the exact text shown
  (case-sensitive). Headings whose text does not match any
  recognized name are treated as unknown sections — they are
  permitted but non-authoritative; the parser captures them in an
  `extra` bucket on the parsed record without raising. See "Parser
  notes" below for the full tolerance contract.

## Overview file

`.specify/orca/adopted/00-overview.md` is a generated index of
all records in the registry. Shape:

```markdown
# Adoption Records Overview

_Generated by `speckit_orca.adoption regenerate-overview`. Do not edit by hand._

## Adopted

- **[AR-001-<slug>](./AR-001-<slug>.md)** — <title> _(adopted YYYY-MM-DD)_
- ...

## Superseded

- **[AR-002-<slug>](./AR-002-<slug>.md)** — <title> _(adopted YYYY-MM-DD, superseded by 020-new-auth)_
- ...

## Retired

- **[AR-003-<slug>](./AR-003-<slug>.md)** — <title> _(adopted YYYY-MM-DD, retired)_
- ...
```

- Regeneration is automatic on every `create`, `supersede`,
  `retire`, and explicit `regenerate-overview` call.
- The overview file is safe to delete; the next runtime call
  recreates it.
- Operators MUST NOT hand-edit the overview; edits are lost on
  next regeneration.
- Three groups are always present (`Adopted`, `Superseded`,
  `Retired`), each rendered with its current entries; an empty
  group renders the heading with no bullets.

## Flow-state interpretation

`flow_state.py` reads an adoption record (when given a path under
`.specify/orca/adopted/AR-*.md`) and returns:

```python
{
    "kind": "adoption",
    "id": "AR-001-cli-entrypoint",
    "slug": "cli-entrypoint",
    "title": "...",
    "status": "adopted" | "superseded" | "retired" | "invalid",
    "adopted_on": "YYYY-MM-DD",
    "baseline_commit": "abc1234" | None,
    "location": ["path", ...],
    "key_behaviors": ["behavior", ...],
    "known_gaps": "..." | None,
    "superseded_by": "020-new-auth" | None,
    "retirement_reason": "..." | None,
    "review_state": "not-applicable",
}
```

- `kind` is always the literal string `"adoption"` — flow-state
  uses this to distinguish from full-spec and spec-lite views.
- `review_state` is hard-coded to `"not-applicable"` for the
  adoption kind. This is an inline view field defined by 015,
  parallel to how 013 defines `review_state` for the spec-lite
  view (`unreviewed | self-reviewed | cross-reviewed`). 015 does
  NOT modify 012's per-artifact Review Milestone fields
  (`review_spec_status`, `review_code_status`, `review_pr_status`,
  `overall_ready_for_merge`); 012 stays untouched.
- For AR file targets, `flow_state.py` does NOT derive
  directory-style milestone entries (no incomplete-milestone
  reports for absent `plan.md` / `tasks.md`). The full-spec
  milestone path is bypassed entirely for AR targets.
- Malformed records produce
  `kind: "adoption", status: "invalid"` rather than a parse crash.

## Forbidden operations

- **No programmatic mutation of `Adopted-on` or `Baseline Commit`.**
  Both are write-once.
- **No lane registration.** The matriarch guard rejects registering
  a lane against an adoption record — see
  [matriarch-guard.md](./matriarch-guard.md).
- **No yolo participation.** ARs are not a valid yolo start
  artifact in v1. The 009 yolo runtime does not consume them.
- **No reviews.** ARs do not participate in 012's Review Milestone
  contract. There is no `AR-NNN-<slug>.review-spec.md` or similar
  sibling. The `review_state` view field is hard-coded to
  `"not-applicable"`.
- **No touch-point coordination metadata.** No
  `**Touches ARs**:` parsing, no cross-lane overlap detection.
  Cut from v1 per cross-review; deferred to a future spec if
  brownfield coordination demand materializes.
- **No supersession of records that don't exist.** The
  `supersede` command validates that `specs/<spec-id>/spec.md`
  exists before writing the `## Superseded By` section. If the
  target spec doesn't exist, the command rejects with a clear
  pointer.

## Parser notes

Per plan open question 1, the 015 runtime MUST use a pure-markdown
parser with strict section-name matching (no YAML frontmatter).
This matches evolve, brainstorm-memory, and spec-lite conventions
and avoids a new dependency. The parser:

1. Reads the file line by line.
2. Extracts the title from the `# Adoption Record: AR-NNN: ...`
   heading.
3. Walks metadata lines (`**Field**: value`) until the first
   `##` heading.
4. Splits body into sections at each `##` heading until EOF.
5. Validates that the three required section names
   (`Summary`, `Location`, `Key Behaviors`) are all present and,
   when encountered, appear in the listed relative order. Missing
   any required section is a structural failure.
6. Recognizes optional section names (`Known Gaps`,
   `Superseded By`, `Retirement Reason`) and includes them in the
   parsed record when present. When present, optional sections
   appear after the required block in the listed relative order.
7. Tolerates unknown sections by including them in an `extra`
   bucket on the parsed record (does not raise, and does not
   invalidate the recognized-section ordering rule). Unknown
   sections may appear in any position.
8. Returns a typed `AdoptionRecord` struct.

Structural parse failures (missing required section, missing title
heading, unknown `Status` value, malformed `Adopted-on`) raise a
structured parse error with the line number and expected vs actual
content. Flow-state catches parse errors and reports the record as
`kind: "adoption", status: "invalid"` rather than crashing.

The tolerant-parser posture (see "Status / section pairing" above)
applies only to optional-section / status pairing, NOT to
structural validity. A record missing `## Summary` is invalid; a
record with `Status: adopted` plus a `## Superseded By` section is
valid.

## Supersedes

This contract is new in 015. It does not supersede any existing
contract. It is purely additive — it does not modify the spec-lite
contract (013), the matriarch contract (010), the flow-state
contract (005), or the Review Milestone contract (012).
