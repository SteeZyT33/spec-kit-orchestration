# Data Model: 015 Brownfield Adoption

**Status**: Draft
**Parent**: [plan.md](./plan.md)

Entities, relationships, and field-level definitions for the
adoption-record intake layer. Derived from the two contract files
under `contracts/`. This document is the canonical cross-reference
for runtime code that constructs, reads, or validates adoption
records.

---

## Entity: `Adoption Record`

**Description**: A reference-only intake artifact — one markdown
file documenting an existing feature's shape, location, and
observed behaviors. No phase gates, no review participation, no
yolo participation, no lane-anchor capability.

**File**: `.specify/orca/adopted/<id>.md`
**Contract**: [adoption-record.md](./contracts/adoption-record.md)

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `id` | string (`AR-NNN-<slug>`) | yes | derived from `number` (parsed from the `AR-NNN` prefix in the `# Adoption Record:` title heading) and `slug` (parsed from the filename stem `<id>.md`) |
| `number` | int (1-999) | yes | parsed from the `AR-NNN` prefix in the `# Adoption Record:` title heading |
| `slug` | string | yes | parsed from the filename stem (the `-<slug>` suffix of `<id>.md`) |
| `title` | string | yes | text after `AR-NNN:` in `# Adoption Record:` heading |
| `status` | enum (`adopted`, `superseded`, `retired`) | yes | `**Status**:` metadata line |
| `adopted_on` | date (`YYYY-MM-DD`) | yes | `**Adopted-on**:` metadata line |
| `baseline_commit` | git SHA or null | no | `**Baseline Commit**:` metadata line, null if absent |
| `summary` | string (1-3 sentences) | yes | `## Summary` section body |
| `location` | list[string] (at least 1) | yes | `## Location` bullet items |
| `key_behaviors` | list[string] (at least 1) | yes | `## Key Behaviors` bullet items |
| `known_gaps` | string or null | no | `## Known Gaps` section body, null if absent |
| `superseded_by` | string or null | no | `## Superseded By` section body, null if absent |
| `retirement_reason` | string or null | no | `## Retirement Reason` section body, null if absent |

### Relationships

- Lives under the global registry `.specify/orca/adopted/`,
  not inside a feature directory under `specs/` and not alongside
  spec-lite records under `.specify/orca/spec-lite/`.
- May be cited by ID in a hand-authored full spec's body (e.g., as
  background context: "this work touches the area covered by
  AR-001"). The full spec links back; the AR does not link
  forward to citing specs.
- A single full spec MAY supersede an AR via the
  `adopt supersede <ar-id> <spec-id>` command, which writes the
  full spec ID into the AR's `## Superseded By` section. The AR
  file is preserved as historical context.
- Cannot anchor a matriarch lane — see
  [matriarch-guard.md](./contracts/matriarch-guard.md).
- Does not participate in 012's Review Milestone contract — no
  sibling review files, no review_state contribution.
- Overview file `00-overview.md` in the same directory is a
  generated index, not a record.

### Invariants

- One file per record; no per-record directory.
- Filename stem equals `id`.
- `id` is unique across the registry.
- `adopted_on` is write-once (never mutated after first write).
- `baseline_commit`, when present, is write-once.
- `status` is one of exactly three enum values
  (`adopted`, `superseded`, `retired`).
- `location` has at least one non-empty entry.
- `key_behaviors` has at least one non-empty entry.
- `summary` body is non-empty.
- Optional sections (`Known Gaps`, `Superseded By`,
  `Retirement Reason`), when present, MUST have non-empty bodies;
  an empty optional section heading with no body is structurally
  invalid.
- Optional sections MAY appear regardless of `status` value (the
  parser is tolerant — see "Status / section pairing" in the
  contract). Commands write the expected sections for the target
  status; manual edits are not validated against status.
- All section headings use exact text as specified
  (case-sensitive).
- Metadata block precedes all body sections in file order.

---

## Entity: `Adoption Overview`

**Description**: A generated index file listing all adoption
records grouped by status. Not a record — excluded from
record-listing walks by filename.

**File**: `.specify/orca/adopted/00-overview.md`
**Contract**: [adoption-record.md](./contracts/adoption-record.md)
(overview section)

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `adopted_records` | list[record summary] | yes (may be empty) | records with `status: adopted` |
| `superseded_records` | list[record summary] | yes (may be empty) | records with `status: superseded` |
| `retired_records` | list[record summary] | yes (may be empty) | records with `status: retired` |

Each record summary contains: `id`, `title`, `adopted_on` date,
`superseded_by` (if status is superseded), and a relative link to
the record file.

### Invariants

- Regenerated automatically on every `create`, `supersede`,
  `retire`, and explicit `regenerate-overview` call.
- Safe to delete — recreated on next runtime call.
- Must not be hand-edited (edits lost on regeneration).
- Excluded from all record-listing operations by filename
  (`00-overview.md`).
- All three status groups are always present in the rendered
  output, even when empty (renders the heading with no bullets).

---

## Entity: `Adoption Flow-State View`

**Description**: Flow-state's computed view of an adoption record.
Not a durable artifact; computed on demand from the record file
when flow-state's CLI is invoked with a path under
`.specify/orca/adopted/AR-*.md`.

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `kind` | literal `"adoption"` | yes | fixed |
| `id` | string | yes | parsed from record |
| `slug` | string | yes | parsed from record filename |
| `title` | string | yes | parsed from record |
| `status` | enum (`adopted`, `superseded`, `retired`, `invalid`) | yes | parsed from record |
| `adopted_on` | date | yes | parsed from record |
| `baseline_commit` | string or null | yes | parsed from record |
| `location` | list[string] | yes | parsed from record |
| `key_behaviors` | list[string] | yes | parsed from record |
| `known_gaps` | string or null | yes | parsed from record |
| `superseded_by` | string or null | yes | parsed from record |
| `retirement_reason` | string or null | yes | parsed from record |
| `review_state` | literal `"not-applicable"` | yes | hard-coded by 015 |

### Relationships

- Derived from an `Adoption Record` entity.
- `review_state` is an inline view field defined by 015 (parallel
  to how 013 defines `review_state` for the spec-lite view —
  `unreviewed | self-reviewed | cross-reviewed`). 015 hard-codes
  the value `"not-applicable"` for the adoption kind. This is
  NOT a 012 contract field; 012's per-artifact Review Milestone
  fields (`review_spec_status`, `review_code_status`,
  `review_pr_status`, `overall_ready_for_merge`) are not modified
  by 015.
- Consumed by overview regeneration (for status grouping).
- Consumed by command prompts and matriarch's diagnostic output
  when an AR file path is the inspection target.

### Invariants

- `kind` is always the literal string `"adoption"` — flow-state
  uses this to distinguish from full-spec, spec-lite, and any
  future kinds.
- `review_state` is always the literal string `"not-applicable"`
  for the adoption kind. This is a hard invariant — operators
  cannot opt into reviewing an AR; the field exists only to
  satisfy the flow-state view contract uniformly across kinds.
- Malformed records produce
  `kind: "adoption", status: "invalid"` rather than a parse
  crash — flow-state catches parse errors gracefully.
- For AR file targets, flow-state does NOT derive directory-style
  milestone entries (no incomplete-milestone reports for absent
  `plan.md` / `tasks.md` / `brainstorm.md`). The full-spec
  milestone derivation path is bypassed entirely.

---

## Entity: `Matriarch Lane-Registration Guard (adoption)`

**Description**: A precondition check in `register_lane` that
rejects adoption records before any lane-creation side effects
proceed. Sibling to 013's spec-lite guard; runs in the same
precondition block.

**Contract**: [matriarch-guard.md](./contracts/matriarch-guard.md)

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `spec_id` | string | yes | input to `register_lane` |
| `is_adoption_record` | bool | yes | output of `_is_adoption_record(paths, spec_id)` |
| `error` | `MatriarchError` or null | yes | raised if `is_adoption_record` is `True` |

### Invariants

- Guard fires before `_feature_dir` resolves AND before any
  filesystem side effects (mailbox root creation, reports
  directory creation, delegated-task file write). Ordering is
  load-bearing; rejected AR registrations leave the workspace
  untouched.
- Guard fires for all adoption records regardless of `status`
  (`adopted`, `superseded`, or `retired`).
- Guard does not fire for full specs that cite adoption records
  in their body.
- Guard does not fire for spec-lite records — those are rejected
  by 013's separate `_is_spec_lite_record` guard, which runs
  first in the precondition block by ordering.
- Guard recognizes ID-only inputs (no slug) via the glob fallback
  in the detection function.

---

## Cross-entity relationships diagram

```text
.specify/orca/
├── spec-lite/
│   ├── 00-overview.md           ← 013 generated index (not a record)
│   ├── SL-001-<slug>.md         ← 013 Spec-Lite Record
│   └── ...
└── adopted/
    ├── 00-overview.md           ← 015 generated index (not a record)
    ├── AR-001-<slug>.md         ← 015 Adoption Record
    ├── AR-002-<slug>.md
    └── ...

Flow-state reads:
  AR-NNN-<slug>.md  ──→  Adoption Flow-State View
                              │
                              ├── review_state: "not-applicable" (hard-coded)
                              │
                              └── kind: "adoption" (distinct from
                                  "feature" and "spec-lite")

Matriarch precondition block (in register_lane):
  spec_id input
    │
    ├── _is_spec_lite_record(paths, spec_id) → True?
    │     └── raise MatriarchError("...spec-lite...")  (013's guard)
    │
    ├── _is_adoption_record(paths, spec_id) → True?
    │     └── raise MatriarchError("...adoption record...")  (015's guard)
    │
    └── (only now) _feature_dir + mailbox + reports + delegated-task

Supersession (operator action):
  adopt supersede AR-002 020-new-auth
    │
    ├── validate specs/020-new-auth/spec.md exists
    ├── write `## Superseded By` section into AR-002
    ├── update `**Status**: superseded`
    └── regenerate overview (AR-002 moves to "Superseded" group)
```

---

## Cross-spec interaction summary

| Other spec | 015 interaction |
|---|---|
| 013 spec-lite | Mirrors registry layout, ID scheme, guard pattern, overview convention. No modifications to 013. Guards run sequentially in `register_lane` (013 first, then 015). |
| 012 review-model | NOT modified. 015's `review_state: "not-applicable"` is an inline flow-state view field (parallel to 013's spec-lite `review_state`), not an extension to 012's per-artifact Review Milestone contract. 015 ships independently of 012's merge state. |
| 010 matriarch | Guard added to `register_lane` precondition block (alongside 013's). No other matriarch surface modified. 015 does not change the canonical mailbox / event-envelope contract or its accepted event types — see [`specs/010-orca-matriarch/contracts/event-envelope.md`](../010-orca-matriarch/contracts/event-envelope.md) for the authoritative type list. |
| 009 yolo | NOT modified. 015 does not add ARs as a valid yolo start artifact. 009's spec.md current language about valid yolo starts is a 009 concern, not 015's. |
| 005 flow-state | Per-target interpretation extended (mirrors 013's per-file spec-lite extension). New `kind: "adoption"` view returned when given an AR file path. No repo-wide summary UX, no new CLI flags. |
| 011 evolve | NOT modified. ARs do not interact with evolve's design-decision tracking. |
| 002 brainstorm-memory | NOT modified. Brainstorms may cite ARs by ID as context; no schema change to brainstorm-memory. |
| 008 capability-packs | NOT modified. ARs are not pack-extensible in v1. |

---

## Open questions (tactical, for implementation task)

1. **Parser approach**: pure-markdown with strict section-name
   matching (lean from plan's open question 1). No YAML
   frontmatter. Matches evolve, brainstorm-memory, and spec-lite
   conventions.
2. **`_is_adoption_record` detection**: canonical path + glob +
   scoped header check (not a repo-wide scan). Mirrors 013's
   pattern.
3. **Overview regeneration**: automatic on every write
   (`create`, `supersede`, `retire`) plus explicit
   `regenerate-overview` for recovery. Lean from plan's open
   question 2.
4. **`baseline_commit` pre-population**: defensive fallback —
   reads `git rev-parse HEAD`; if not a git repo or git
   unavailable, the field is omitted. Lean from plan's open
   question 3.
5. **Supersede validation**: requires `specs/<spec-id>/spec.md`
   to exist (not just the directory). Lean from plan's open
   question 4.
6. **Retire reason empty-body handling**: omit the section
   entirely when `--reason` is not provided. Lean from plan's
   open question 5.
7. **Tolerant parser boundaries**: structural failures
   (missing required section, missing title heading, unknown
   `Status` value, malformed `Adopted-on`) raise structured parse
   errors; status / optional-section pairing inconsistencies are
   accepted. Lean from plan's open question 7.
