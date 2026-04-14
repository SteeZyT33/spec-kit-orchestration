# Data Model: 013 Spec-Lite

**Status**: Draft
**Parent**: [plan.md](./plan.md)

Entities, relationships, and field-level definitions for the
spec-lite intake layer. Derived from the two contract files
under `contracts/`. This document is the canonical cross-reference
for runtime code that constructs, reads, or validates spec-lite
records.

---

## Entity: `Spec-Lite Record`

**Description**: A lightweight intake artifact — one markdown
file recording a problem, solution, acceptance scenario, and
affected files. No phase gates, no review requirements, no
promotion pathway.

**File**: `.specify/orca/spec-lite/<id>.md`
**Contract**: [spec-lite-record.md](./contracts/spec-lite-record.md)

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `id` | string (`SL-NNN-<slug>`) | yes | parsed from title heading |
| `title` | string | yes | text after `SL-NNN:` in `# Spec-Lite` heading |
| `source_name` | string | yes | `**Source Name**:` metadata line |
| `created` | date (`YYYY-MM-DD`) | yes | `**Created**:` metadata line |
| `status` | enum (`open`, `implemented`, `abandoned`) | yes | `**Status**:` metadata line |
| `problem` | string (1-2 sentences) | yes | `## Problem` section body |
| `solution` | string (1-2 sentences) | yes | `## Solution` section body |
| `acceptance_scenario` | string (BDD given/when/then) | yes | `## Acceptance Scenario` section body |
| `files_affected` | list[string] (at least 1) | yes | `## Files Affected` bullet items |
| `verification_evidence` | string or null | no | `## Verification Evidence` section body, null if absent |

### Relationships

- Lives under the global registry `.specify/orca/spec-lite/`,
  not inside a feature directory under `specs/`
- May be cited by ID in a hand-authored full spec's body (the
  full spec links back; the spec-lite does not link forward)
- Cannot anchor a matriarch lane — see
  [matriarch-guard.md](./contracts/matriarch-guard.md)
- Overview file `00-overview.md` in the same directory is a
  generated index, not a record

### Invariants

- One file per record; no per-record directory
- Filename stem equals `id`
- `id` is unique across the registry
- `created` is write-once (never mutated after first write)
- `status` is one of exactly three enum values
- `files_affected` has at least one non-empty entry
- `verification_evidence` is either absent (section omitted) or
  non-empty (section present with body content); an empty section
  heading with no body is invalid
- All section headings use exact text as specified (case-sensitive)
- Metadata block precedes all body sections in file order

---

## Entity: `Spec-Lite Overview`

**Description**: A generated index file listing all spec-lite
records grouped by status. Not a record — excluded from
record-listing walks by filename.

**File**: `.specify/orca/spec-lite/00-overview.md`
**Contract**: [spec-lite-record.md](./contracts/spec-lite-record.md)
(overview section)

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `active_records` | list[record summary] | yes (may be empty) | records with `status: open` |
| `implemented_records` | list[record summary] | yes (may be empty) | records with `status: implemented` |
| `abandoned_records` | list[record summary] | yes (may be empty) | records with `status: abandoned` |

Each record summary contains: `id`, `title`, `created` date, and
a relative link to the record file.

### Invariants

- Regenerated automatically on every `create`, `update-status`,
  and explicit `regenerate-overview` call
- Safe to delete — recreated on next runtime call
- Must not be hand-edited (edits lost on regeneration)
- Excluded from all record-listing operations by filename
  (`00-overview.md`)

---

## Entity: `Spec-Lite Flow-State View`

**Description**: Flow-state's computed summary of a spec-lite
record. Not a durable artifact; computed on demand from the
record file and any sibling review files.

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `kind` | literal `"spec-lite"` | yes | fixed |
| `id` | string | yes | parsed from record |
| `slug` | string | yes | parsed from record filename |
| `title` | string | yes | parsed from record |
| `source_name` | string | yes | parsed from record |
| `created` | date | yes | parsed from record |
| `status` | enum (`open`, `implemented`, `abandoned`) | yes | parsed from record |
| `files_affected` | list[string] | yes | parsed from record |
| `has_verification_evidence` | bool | yes | `True` if section present and non-empty |
| `review_state` | enum (`unreviewed`, `self-reviewed`, `cross-reviewed`) | yes | derived from sibling review files |

### Relationships

- Derived from a `Spec-Lite Record` entity
- `review_state` is derived from sibling review files sharing the
  record's ID stem (e.g., `SL-001-<slug>.self-review.md`,
  `SL-001-<slug>.cross-review.md`) — not from a per-record
  directory
- Consumed by matriarch's lane readiness checks (to confirm
  rejection)
- Consumed by overview regeneration (for status grouping)

### Invariants

- `kind` is always the literal string `"spec-lite"` — flow-state
  uses this to distinguish from full-spec feature-state views
- `review_state` defaults to `unreviewed` per the opt-out default
  (013 plan question 3)
- Malformed records produce `kind: "spec-lite", status: "invalid"`
  rather than a parse crash — flow-state catches parse errors
  gracefully

---

## Entity: `Matriarch Lane-Registration Guard`

**Description**: A precondition check in `register_lane` that
rejects spec-lite records before lane creation proceeds.

**Contract**: [matriarch-guard.md](./contracts/matriarch-guard.md)

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `spec_id` | string | yes | input to `register_lane` |
| `is_spec_lite` | bool | yes | output of `_is_spec_lite_record(paths, spec_id)` |
| `error` | `MatriarchError` or null | yes | raised if `is_spec_lite` is `True` |

### Invariants

- Guard fires before `_feature_dir` resolves (ordering is
  load-bearing — `_feature_dir` does not know about
  `.specify/orca/spec-lite/`)
- Guard fires for all spec-lite records regardless of status
- Guard does not fire for full specs that cite spec-lite records
  in their body

---

## Cross-entity relationships diagram

```text
.specify/orca/spec-lite/
├── 00-overview.md              ← generated index (not a record)
├── SL-001-<slug>.md            ← Spec-Lite Record
├── SL-001-<slug>.self-review.md  ← optional review sibling
├── SL-001-<slug>.cross-review.md ← optional review sibling
├── SL-002-<slug>.md
└── ...

Flow-state reads:
  SL-NNN-<slug>.md  ──→  Spec-Lite Flow-State View
                              │
                              ├── review_state derived from
                              │   sibling *.self-review.md / *.cross-review.md
                              │
                              └── kind: "spec-lite" (distinct from full-spec)

Matriarch guard:
  register_lane(spec_id="SL-001-slug")
    └── _is_spec_lite_record(paths, "SL-001-slug") → True
          └── raise MatriarchError("Cannot register lane...")
```

---

## Vocabulary migration

Old vocabulary (from retired `micro-spec`) → new vocabulary (013):

| Old | New | Notes |
|---|---|---|
| `micro-spec` command | `spec-lite` command | Full rename; zero existing records to migrate |
| `commands/micro-spec.md` | `commands/spec-lite.md` | File retired and replaced |
| `speckit.orca.micro-spec` | `speckit.orca.spec-lite` | Extension registration updated |
| Mini-plan section | (removed) | Spec-lite has no phase decomposition |
| Verification mode enum | (removed) | Verification is optional and unstructured |
| Code-review handoff | (removed) | Review is opt-out by default |
| Promote command | (removed) | No formal promotion pathway; hand-author a full spec instead |

## Open questions (tactical, for implementation task)

1. **Parser approach**: pure-markdown with strict section-name
   matching (lean from plan's open question 1). No YAML frontmatter.
   Matches evolve and brainstorm-memory conventions.
2. **`_is_spec_lite_record` detection**: both path prefix and
   header scan fallback (lean from plan's open question 2).
3. **Overview regeneration**: automatic on every write (lean from
   plan's open question 3). Matches evolve's pattern.
