# Plan: Brownfield Adoption — Reference Records for Pre-Orca Features

**Feature Branch**: `015-brownfield-adoption`
**Created**: 2026-04-14
**Status**: Draft
**Brainstorm**: [brainstorm.md](./brainstorm.md)
**Research inputs**:
- Session comparison of spec-kit vs. OpenSpec vs. spec-kitty
  (2026-04-14)
- Memory note `project_brownfield_adoption.md` (2026-04-12) —
  ranking of brownfield candidate ideas

---

## 1. Summary

Ship a new `Adoption Record` (AR) primitive — a reference-only
document describing an existing feature's shape, location, and
known behaviors. Separate registry from spec-lite. Never reviewed.
Not drivable by yolo. Cannot anchor a matriarch lane. Cross-lane
coordination across adopted territory stays the operator's
responsibility in v1 (touch-point metadata cut per cross-review
— see section 13 non-goals and Section 2 strawman Q1).

This is **purely additive**. 013 (spec-lite) stays locked. The full
spec flow stays authoritative for new work. Nothing is renamed or
retired. 015 does **not** modify 012's Review Milestone contract or
any other existing contract. The `review_state: not-applicable`
marker is an inline field on flow-state's adoption view only —
015 defines it there, mirroring how 013 defines `review_state` on
the spec-lite view. Neither spec modifies 012's per-artifact status
fields (`review_spec_status`, `review_code_status`,
`review_pr_status`, `overall_ready_for_merge`).

Four initial records (AR-001 through AR-004) ship in the same wave
as 015's primitive, covering the uncovered pre-Orca subsystems in
spec-kit-orca itself. All four land with `status: adopted`. The
supersession mechanic is exercised by `tests/test_adoption.py`
against test fixtures, NOT by superseding a production record in
the first wave.

## 2. Strawman answers (proposed defaults — non-final)

These are the plan's proposed answers to the seven remaining open
questions from the brainstorm (question 8, the repo audit, was
resolved during brainstorm drafting and is documented in the
brainstorm's "Initial Records" section). They are non-final
defaults — edit the answers you disagree with before the
contract-writing task starts.

**Note**: Section 14 below contains a separate, distinct set of
open questions that surface only during plan drafting and are
properly resolved by the contract-writing task. Section 2 covers
brainstorm-era questions; Section 14 covers contract-era
questions. The two sets do not overlap.

| # | Question | Strawman answer |
|---|---|---|
| 1 | Touch-point syntax | **Cut from v1.** Codex cross-review found the proposed advisory-warning-on-lane-overlap mechanism too weak to justify its complexity (no persistence, no readiness impact, no recomputation) AND impossible to implement without a new matriarch mailbox event type. Deferred to a future spec if brownfield coordination need materializes. ARs in v1 are reference-only with a hard lane-anchor guard; cross-lane coordination stays the operator's responsibility. |
| 2 | Overview layout | **Three fixed groups** (`## Adopted`, `## Superseded`, `## Retired`). Mirrors spec-lite's overview grouping by status. Flat sorted list loses the at-a-glance status read. |
| 3 | Baseline Commit required? | **Optional.** The `new` command pre-populates HEAD SHA in the template; operator can clear it before saving. Optional keeps v1 friction low; v2's adoption manifest elevates its importance for partial-flow-state suppression. |
| 4 | Adoption manifest location | **Deferred to v2.** v1 does not ship a manifest. Brainstorm noted `.specify/orca/adoption.md` at registry root as the likely v2 location; plan captures this as a design intent, not a v1 deliverable. |
| 5 | Supersede validation | **Validate.** `adopt supersede <ar-id> <spec-id>` rejects if `specs/<spec-id>/spec.md` does not exist. Prevents broken Superseded-By pointers. |
| 6 | Retire reason storage | **Dedicated section.** When status is `retired`, a `## Retirement Reason` section appears after `## Superseded By` (matches the template ordering in section 6). Keeps status-specific content out of semantic sections like Known Gaps (which may still be relevant after retirement for historical context). |
| 7 | OpenSpec delta-spec semantics | **Reference-only in 015.** Delta-spec semantics (ADDED/MODIFIED/REMOVED) are a larger architectural shift and deserve their own spec (016+) if demand emerges. 015's `Location` field is forward-compatible with a future delta model but does not implement it. |

## 3. Scope

### In scope

- Define the adoption record shape in a contract file (3 metadata
  fields: Status required, Adopted-on required, Baseline Commit
  optional; 3 required body sections: Summary, Location, Key
  Behaviors; up to 3 optional body sections: Known Gaps, Superseded
  By, Retirement Reason)
- Create `commands/adopt.md` (prompt stub — the full prompt is
  written in a follow-up task, same deferral rule as 012/013)
- Update `extension.yml` to register `speckit.orca.adopt`
- Add `src/speckit_orca/adoption.py` runtime module for
  create/list/get/supersede/retire/regenerate-overview operations.
  `adoption.py` owns overview regeneration
  (`.specify/orca/adopted/00-overview.md`).
- Add adoption integration in `src/speckit_orca/flow_state.py`:
  per-file AR interpretation (mirrors 013's per-file spec-lite
  extension), new `adoption` kind returned when given an AR file
  path, no directory-style milestone derivation for AR file targets
  (full-spec interpretation expects `plan.md` / `tasks.md` siblings;
  AR files are single-file registry records and don't have those
  artifacts by design). Flow-state does NOT get a new repo-wide
  summary UX — the existing per-target interface is what 015
  extends.
- Add adoption guard in `src/speckit_orca/matriarch.py`
  (`_is_adoption_record` + rejection at `register_lane`). Guard
  must fire at the TOP of `register_lane`, before any mailbox root
  / reports dir / delegated-task file side effects.
- Update `README.md` intake section to name adoption records as
  the brownfield entry point
- Bootstrap `.specify/orca/adopted/00-overview.md` as part of the
  first commit so the runtime has a target to regenerate against
- Record AR-001 through AR-004 as the first wave's initial
  records, all with `status: adopted`

### Explicitly out of scope

- **Command prompt content rewrite.** `commands/adopt.md` lands as
  a stub; the body is written in a separate follow-up after this
  plan and contracts merge. Same deferral rule as 012/013.
- **Touch-point coordination metadata.** No `**Touches ARs**:`
  metadata parsing. No cross-lane conflict detection. No new
  matriarch mailbox event types. Deferred to a future spec (016+)
  if brownfield coordination demand materializes.
- **Modifying 012's Review Milestone contract.** 015 is additive
  to 012, not a contract change. `review_state: not-applicable`
  lives on flow-state's adoption view, not on 012's per-artifact
  status fields.
- **Repo-wide flow-state summary UX.** No new `--show-superseded`
  / `--show-retired` CLI flags. The `00-overview.md` file is the
  registry-wide index; flow-state's CLI stays per-target.
- **Cross-wave supersession exercise.** AR-002 is NOT superseded
  in-wave. Supersession is tested in `tests/test_adoption.py`
  against test fixtures.
- **Status-dependent section invariant enforcement.** Parser is
  tolerant: `Status` is authoritative, commands write expected
  sections, manual markdown edits are allowed. Malformed records
  parse to `status: invalid`; no cross-section consistency check
  on write.
- v2 per-project adoption pipeline (manifest, scan, init wizard)
- Auto-generation of ARs from git history or code introspection
- Adding ARs as a valid yolo start artifact (009's spec.md
  currently still mentions `micro-spec/spec artifact` as valid
  yolo starts; changing that is a 009/013 concern, not 015's)
- OpenSpec delta-spec semantics
- Archive layer semantics (ARs are durable references, not
  archived changes)
- Any AR review gates
- Bulk-supersede or bulk-retire operations
- AR-005 (PR-thread resolver) is optional; plan reviewer decides
  whether to include
- Touching frozen docs (refinement reviews, v1.4 design docs)

## 4. Rollout strategy

**Atomic additive wave.** No existing data to migrate (adoption
records are a brand-new primitive). No vocabulary rename (adoption
does not collide with spec-lite, evolve, or any other registry).
No contract modifications to 012, 013, or any other spec. Single
PR, three commits (down from four after codex-review removed the
012 extension commit and the AR-002 supersession step), shipped
together.

All four initial records land with `status: adopted`. The
supersession mechanic is exercised end-to-end in
`tests/test_adoption.py` against fixture records, not against
production ARs in the first wave.

## 5. File-by-file change list

Grouped into **3 commits** for reviewability (revised down from
four after cross-review removed the 012 contract extension commit
and collapsed the AR-002 supersession step into test fixtures).

### Commit 1 — Extension registration + command stub

- **`extension.yml`** — add `speckit.orca.adopt` command
  registration:
  - New entry with `name: speckit.orca.adopt`,
    `file: commands/adopt.md`, description naming the five
    subcommands (new, list, supersede, retire, regenerate-overview)
  - Bump appropriate version/tags fields to match 012/013's pattern
- **`commands/adopt.md`** (new, stub) — file created with
  placeholder body. Full prompt rewrite is a separate follow-up.
  Stub includes the command name/argument shape so the extension
  manifest doesn't point at an empty file.
- **`.specify/integrations/claude.manifest.json`** — register
  `speckit.orca.adopt` alongside existing command registrations.
  Same update in `.specify/integrations/speckit.manifest.json`
  (mirror any other agent manifest files present at plan time).

This commit **must land atomically with commit 2** or the extension
registers a command with no runtime behind it.

### Commit 2 — Runtime + tests

- **`src/speckit_orca/adoption.py`** (new) — the adoption runtime
  module. See section 7 for the full design. Functions:
  `create_record`, `list_records`, `get_record`, `supersede_record`,
  `retire_record`, `regenerate_overview`. No `update_record` — ARs
  are edited as markdown directly. **`adoption.py` owns overview
  regeneration**, not `flow_state.py`.
- **`src/speckit_orca/flow_state.py`** (modify) — add:
  - New `AdoptionRecord` dataclass + `_parse_adoption_record`
    function mirroring 013's per-file spec-lite parser
  - Per-target interpretation: when flow_state's CLI is invoked
    with a path under `.specify/orca/adopted/AR-*.md`, return the
    adoption view shape (see section 8)
  - Adoption view has `kind: "adoption"` and a hard-coded
    `review_state: "not-applicable"` field (mirrors how 013's
    spec-lite view defines `review_state` inline — not a 012
    contract field)
  - No directory-style milestone derivation for AR file targets
    (the full-spec path expects `plan.md` / `tasks.md` siblings;
    AR files are single-file registry records and don't have those)
  - No repo-wide summary rendering changes, no new CLI flags
- **`src/speckit_orca/matriarch.py`** (modify) — add:
  - New `_is_adoption_record(paths, spec_id)` function mirroring
    013's `_is_spec_lite_record` plan pattern (both guards
    implemented together when 013 lands; 015 adds the sibling
    guard)
  - **Guard insertion: at the TOP of `register_lane`**, before
    mailbox root creation, reports dir creation, or delegated-task
    file writes. Both spec-lite and adoption guards MUST fire
    before any filesystem side effect so a rejected registration
    leaves the workspace untouched.
  - No touch-point parser. No new mailbox event types. These
    deferred per cross-review findings.
- **`.specify/orca/adopted/00-overview.md`** (new, bootstrap) —
  empty template committed as part of this commit so the runtime
  has a target to regenerate against. Matches evolve's
  `00-overview.md` bootstrap pattern.
- **`tests/test_adoption.py`** (new) — unit tests covering
  create/list/get/supersede/retire/regenerate-overview against
  fixture records. Supersession is exercised here, NOT against
  production ARs in commit 3. See section 10 for detailed coverage.
- **`tests/test_flow_state_adoption.py`** (new) — integration
  tests covering flow-state's adoption-file interpretation,
  warning-suppression behavior, and regression checks against
  full-spec and spec-lite paths.
- **`tests/test_matriarch.py`** (modify) — add adoption guard
  tests: registration rejection for AR targets, non-misfire on
  full specs, non-misfire on spec-lite (ordering check), and
  **no-side-effect assertion**: after a rejected AR registration,
  no mailbox root / reports dir / delegated-task files exist on
  disk.

### Commit 3 — Docs + initial records

- **`README.md`** — update intake section to name adoption records
  as the brownfield entry point. Short subsection explaining when
  to pick AR vs. spec-lite vs. full spec. Scan the Basic Workflow
  block for any other updates needed.
- **`docs/orca-roadmap.md`** — mention brownfield adoption under
  shipped features.
- **`.specify/orca/adopted/AR-001-cli-entrypoint.md`** (new) —
  authored per the shape in section 6. Summary describes
  `src/speckit_orca/cli.py` and the `speckit-orca` binary.
  `status: adopted`.
- **`.specify/orca/adopted/AR-002-cross-review-shim.md`** (new) —
  authored per the shape in section 6. Summary describes the
  pre-012 cross-review implementation. `status: adopted`.
  (Eventual supersession by 012 is an operator decision post-wave;
  not part of this plan.)
- **`.specify/orca/adopted/AR-003-templates-infrastructure.md`**
  (new) — authored per the shape in section 6. Summary describes
  the `templates/` directory's role. `status: adopted`.
- **`.specify/orca/adopted/AR-004-extension-manifest.md`** (new) —
  authored per the shape in section 6. Summary describes the
  extension manifest and install pipeline. `status: adopted`.
- **`.specify/orca/adopted/00-overview.md`** — regenerated to
  reflect the four records, all under the "Adopted" group.

## 6. The adoption record shape

An adoption record has **3 metadata fields (2 required + 1
optional)** and **3 required body sections + up to 3 optional body
sections**. The record lives in a markdown file under
`.specify/orca/adopted/AR-NNN-<slug>.md`:

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

### Metadata fields (3 total: 2 required + 1 optional)

- **Status** (required) — one of `adopted`, `superseded`, `retired`
- **Adopted-on** (required) — `YYYY-MM-DD` (RFC3339 full-date),
  matching evolve / brainstorm-memory / spec-lite conventions
- **Baseline Commit** (optional) — git SHA describing the code
  state the record covers. Pre-populated by the `new` command with
  HEAD SHA; operator can clear before saving.

No `Source Name` field (unlike spec-lite). ARs describe the feature,
not the person who wrote the record. Git blame covers authorship.

### Body sections (3 required + 3 optional)

Required for all statuses:
- **Summary** (required) — 1-3 sentences
- **Location** (required) — at least one file path
- **Key Behaviors** (required) — at least one bullet

Optional:
- **Known Gaps** (optional) — what's missing or unreviewed. Can
  appear regardless of status.
- **Superseded By** (optional) — full spec ID (e.g., `020-new-auth`)
  that replaced the AR. Written by the `supersede` command.
  Typically appears when `Status: superseded`, but the parser
  does not enforce this coupling.
- **Retirement Reason** (optional) — free-form reason text.
  Written by the `retire --reason` command or added manually.
  Typically appears when `Status: retired`, but the parser does
  not enforce this coupling.

### Parser posture

`Status` is authoritative. The `new` / `supersede` / `retire`
commands write the expected sections for the target status.
Manual markdown edits are allowed — ARs are operator-editable
reference documents, not strict schemas. If a hand-edited record
has inconsistent metadata (e.g., `Status: adopted` with a
`Superseded By` section), the parser returns the record with the
declared status and includes the extra section in its view; no
hard error, no schema-violation warning. Malformed structural
elements (missing required section, unparseable metadata) produce
`status: invalid` at parse time, same pattern as spec-lite.

## 7. Runtime design

`src/speckit_orca/adoption.py` matches the shape of existing
runtime modules such as `evolve.py` and `brainstorm_memory.py`
(and the planned `spec_lite.py` from 013, if 013 ships its
runtime module — but 015 does not depend on `spec_lite.py`
existing). Thin Python module consumed by the command prompt
via bash.

### Core functions

```python
def create_record(
    *,
    repo_root: Path,
    title: str,
    summary: str,
    location: list[str],
    key_behaviors: list[str],
    known_gaps: str | None = None,
    baseline_commit: str | None = None,
    adopted_on: str | None = None,
) -> AdoptionRecord: ...

def list_records(
    *,
    repo_root: Path,
    status: str | None = None,
) -> list[AdoptionRecord]: ...

def get_record(
    *,
    repo_root: Path,
    record_id: str,
) -> AdoptionRecord: ...

def supersede_record(
    *,
    repo_root: Path,
    record_id: str,
    superseded_by: str,
) -> AdoptionRecord:
    """Sets Status to superseded, writes Superseded By section.

    Validates that specs/<superseded_by>/spec.md exists. Raises
    AdoptionError with a clear pointer if missing. Regenerates
    overview on success.
    """

def retire_record(
    *,
    repo_root: Path,
    record_id: str,
    reason: str | None = None,
) -> AdoptionRecord:
    """Sets Status to retired, writes Retirement Reason section."""

def regenerate_overview(repo_root: Path) -> Path: ...
```

### CLI surface

```bash
uv run python -m speckit_orca.adoption --root . list
uv run python -m speckit_orca.adoption --root . list --status superseded
uv run python -m speckit_orca.adoption --root . create \
    --title "..." --summary "..." \
    --location "path1" --location "path2" \
    --key-behavior "behavior1" --key-behavior "behavior2"
uv run python -m speckit_orca.adoption --root . get AR-001
uv run python -m speckit_orca.adoption --root . supersede AR-002 012-review-model
uv run python -m speckit_orca.adoption --root . retire AR-005 --reason "removed in commit abc1234"
uv run python -m speckit_orca.adoption --root . regenerate-overview
```

### AdoptionRecord dataclass

```python
@dataclass(frozen=True)
class AdoptionRecord:
    id: str                      # "AR-001-cli-entrypoint"
    number: int                  # 1
    slug: str                    # "cli-entrypoint"
    title: str
    status: str                  # "adopted" | "superseded" | "retired"
    adopted_on: str              # "2026-04-14"
    baseline_commit: str | None
    summary: str
    location: list[str]
    key_behaviors: list[str]
    known_gaps: str | None
    superseded_by: str | None
    retirement_reason: str | None
    file_path: Path
```

Parsed from markdown by `_parse_adoption_record` (shared with
flow_state's parser — same module or re-exported).

### ID allocation

`create_record` reads existing `AR-*.md` filenames, extracts the
highest `NNN`, increments by 1. Matches evolve and spec-lite
patterns. Three-digit zero-padded (001, 002, ...).

## 8. Flow-state integration

`flow_state.py`'s CLI accepts a per-target path argument. 013
extends it to interpret a spec-lite file path (not just a feature
directory) and return the spec-lite view. 015 extends it further
to interpret an AR file path and return the adoption view.

When flow_state is invoked with a path under
`.specify/orca/adopted/AR-*.md`, it parses the AR file via
`_parse_adoption_record` and returns:

```python
{
  "kind": "adoption",
  "id": "AR-003-templates-infrastructure",
  "slug": "templates-infrastructure",
  "title": "Templates Infrastructure",
  "status": "adopted" | "superseded" | "retired" | "invalid",
  "adopted_on": "2026-04-14",
  "baseline_commit": "abc1234" | None,
  "location": [...],
  "superseded_by": "020-new-auth" | None,
  "review_state": "not-applicable",  # inline field on adoption view
}
```

### Design notes

- **`review_state` is a flow-state view field, not a 012 contract
  field.** 013 defines `review_state` as an inline field on the
  spec-lite view (`unreviewed | self-reviewed | cross-reviewed`).
  015 adds the adoption view with a hard-coded
  `review_state: "not-applicable"`. Neither spec modifies 012's
  Review Milestone fields (`review_spec_status`,
  `review_code_status`, `review_pr_status`,
  `overall_ready_for_merge`). 012 stays untouched.
- **AR-file handling is scoped to avoid directory-style milestone
  derivation.** flow-state's full-spec interpretation builds
  milestones from feature-directory siblings (`plan.md`,
  `tasks.md`, etc.) and reports incomplete-milestone state when
  expected artifacts are absent. When the CLI target is an AR file
  (not a directory), that full-spec path is structurally not
  applicable — flow-state is reading a single-file registry
  record, not a feature folder. The integration is "don't crash
  on a file target and don't derive directory-style milestones for
  it" rather than "suppress a warning that would otherwise fire."
- **No new CLI flags.** No `--show-superseded` / `--show-retired`.
  The existing per-target interface is what 015 extends.
- **No repo-wide registry summary from flow-state.** The
  `.specify/orca/adopted/00-overview.md` file IS the registry-wide
  index and lives under `adoption.py`'s ownership. Operators who
  want "show me all ARs" read the overview file (or run
  `speckit.orca.adopt list`), not a flow-state command.
- **Supersession chain visibility in the overview**: when an AR
  has `Superseded By: 020-new-auth`, the overview file renders the
  link under the "Superseded" group. This is produced by
  `adoption.py`'s `regenerate_overview`, not by flow-state.
- **Full-spec and spec-lite paths untouched**: 015 is additive.
  Regression tests confirm full-spec per-directory interpretation
  and spec-lite per-file interpretation still return their
  existing view shapes.

## 9. Matriarch integration

### Guard: adoption records cannot anchor lanes

Mirror of 013's `_is_spec_lite_record` plan pattern. New function:

```python
def _is_adoption_record(paths: MatriarchPaths, spec_id: str) -> bool:
    """Return True if spec_id refers to an adoption record.

    Checks canonical path first (fast), then falls back to glob
    and a scoped spec.md header check (defensive — handles ID
    collisions where a full-spec directory happens to share a
    stem with an AR).
    """
    adopted_dir = paths.repo_root / ".specify" / "orca" / "adopted"

    # 1. Canonical path check
    canonical = adopted_dir / f"{spec_id}.md"
    if canonical.exists():
        return True

    # 2. Glob for any file matching the ID stem under adopted/
    if adopted_dir.is_dir():
        for candidate in adopted_dir.glob(f"{spec_id}*.md"):
            if candidate.name == "00-overview.md":
                continue
            return True

    # 3. Scoped header check on specs/<spec_id>/spec.md — catches
    #    an AR file that was mistakenly authored under specs/
    #    instead of under .specify/orca/adopted/. NOT a repo-wide
    #    scan; only this one path is checked.
    feature_dir = paths.repo_root / "specs" / spec_id
    spec_file = feature_dir / "spec.md"
    if spec_file.exists():
        first_line = spec_file.read_text().split("\n", 1)[0]
        if re.match(r"^# Adoption Record: AR-\d{3}", first_line):
            return True

    return False
```

### Guard placement in `register_lane`

**Critical constraint from cross-review**: the current
`register_lane` creates mailbox root, reports dir, and the
delegated-task file BEFORE flow-state is computed. Saying "before
`_feature_dir`" is not sufficient — a rejected AR registration
would leave those runtime artifacts on disk.

Both guards (spec-lite and adoption) MUST fire at the **TOP** of
`register_lane`, before any filesystem side effects:

```python
def register_lane(*, spec_id: str, ...) -> LaneRecord:
    # GUARDS FIRST — no side effects have run yet
    if _is_spec_lite_record(paths, spec_id):
        raise MatriarchError(...spec-lite message...)
    if _is_adoption_record(paths, spec_id):
        raise MatriarchError(
            f"Cannot register lane for adoption record {spec_id!r}. "
            f"Adoption records describe pre-existing features, not "
            f"active work. To coordinate work that touches "
            f"{spec_id!r}, hand-author a full spec under specs/ and "
            f"register that instead. The adoption record can be "
            f"used as reference content when drafting the full spec."
        )

    # Only now do we start the actual lane setup
    mailbox_root = _ensure_mailbox_root(paths, spec_id)
    reports_dir = _ensure_reports_dir(paths, spec_id)
    ...
```

Tests assert that after a rejected registration, no mailbox root,
no reports dir, and no delegated-task file exist on disk for the
rejected `spec_id`.

### What 015 does NOT add to matriarch in v1

**Per cross-review**: touch-points and cross-lane coordination are
cut from v1. Specifically:

- No `_parse_touch_points` function
- No `**Touches ARs**:` metadata parsing in full specs
- No cross-lane overlap detection
- No new mailbox event types (current accepted set:
  `instruction`, `ack`, `status`, `blocker`, `question`,
  `approval_needed`, `handoff`, `shutdown`; `send_mailbox_event`
  hard-rejects unknown types, and 015 does not change this)
- No automatic sequencing, no cross-lane locking, no
  AR-level approval workflow
- No notification to ARs when a superseding spec merges (the
  `Superseded By` field is updated via `adopt supersede` — manual
  operator action only)

If brownfield coordination need materializes later, a future spec
can add touch-point metadata + a new mailbox event type together
as one contract change. 015 does not build speculative coordination
infrastructure.

## 10. Testing approach

### Unit tests — `tests/test_adoption.py` (new)

Covers `adoption.py` module:

- **create**: create a record with all required fields, verify file
  shape, ID allocation (sequential `AR-NNN`), overview regeneration
- **create with all optional fields**: verify Baseline Commit,
  Known Gaps are written correctly
- **create with missing required field**: verify rejection
- **list**: filter by status, verify ordering
- **get**: parse all fields from a well-formed record
- **get malformed**: safe parse failure returning status `invalid`
- **supersede**: validate that superseding spec exists, write
  Superseded By section, update status, regenerate overview
- **supersede with nonexistent spec**: verify rejection with clear
  pointer
- **retire with reason**: write Retirement Reason section, update
  status, regenerate overview
- **retire without reason**: `## Retirement Reason` section is
  NOT written; `Status: retired` is written alone. Consistent with
  open question 5 answer: no empty sections added for their own
  sake.
- **regenerate_overview**: verify overview groups records by status
  correctly, skips `00-overview.md` itself, sorts deterministically
- **ID allocation with gap**: e.g., AR-001, AR-003 exist (AR-002
  deleted). Next create picks AR-004, not AR-002. Matches spec-lite
  and evolve behavior.
- **Tolerant parsing of mismatched sections**: create a record
  with `Status: adopted` plus a `Superseded By` section (simulating
  hand-editing). Parser returns the record with `status: adopted`
  and includes the extra section in its view. NO parse warning,
  NO hard error. Validates the tolerant-parser posture from
  section 6.

### Integration tests — `tests/test_flow_state_adoption.py` (new)

Covers flow-state's per-target adoption-file handling. Matches
section 8's design: no repo-wide summary UX, no CLI flags.

- **Flow-state returns adoption view** when called with a path
  `.specify/orca/adopted/AR-*.md` — asserts `kind: "adoption"`,
  `review_state: "not-applicable"`, parsed status / slug / title /
  location fields.
- **Flow-state does not crash on AR file targets** — no
  FileNotFoundError / KeyError when interpreting a file instead of
  a feature directory.
- **No directory-style milestone derivation for AR file targets**
  — when the CLI target is an AR file, the result does not
  include incomplete-milestone entries for absent `plan.md` /
  `tasks.md` / `brainstorm.md` (those artifacts are structurally
  not expected for a single-file registry record). The full-spec
  milestone path is bypassed entirely for AR targets.
- **Full-spec directory regression** — calling flow-state on a
  feature directory under `specs/NNN-*/` still returns the
  full-spec view shape unchanged.
- **Spec-lite regression** — calling flow-state on a spec-lite
  file under `.specify/orca/spec-lite/SL-*.md` still returns the
  spec-lite view shape unchanged.
- **Superseded and retired statuses** — AR file with
  `Status: superseded` and `Superseded By: 020-new-auth` returns
  a view with those fields populated; same for retired.
- **Malformed AR file** — unparseable record returns
  `status: "invalid"` gracefully, no crash.

Integration tests do NOT cover a repo-wide summary UX, CLI flags,
or grouped output — those are not part of the 015 design. The
overview file (`00-overview.md`) is owned by `adoption.py` and
tested in `tests/test_adoption.py`, not here.

### Matriarch guard tests — `tests/test_matriarch.py` (modify)

Add to existing test file:

- **Guard fires**: create an adoption record at
  `.specify/orca/adopted/AR-001-test.md`, call `register_lane`
  with `spec_id="AR-001-test"`, assert `MatriarchError` with the
  expected message substring.
- **Guard does not misfire on full spec**: create a full spec,
  call `register_lane`, assert success (regression).
- **Guard does not misfire on spec-lite**: create a spec-lite,
  call `register_lane`, assert `MatriarchError` points at
  spec-lite message, NOT adoption message (ordering check).
- **Guard catches ID-only input**: `spec_id="AR-001"` (no slug),
  assert `MatriarchError`.
- **Guard catches misplaced file**: create a file at
  `specs/AR-001-test/spec.md` with `# Adoption Record: AR-001`
  header, assert `MatriarchError` via the scoped header check.
  (This is a defensive path for operator mistakes; it is NOT a
  repo-wide scan.)
- **No-side-effects on rejection** (new, critical): after a
  rejected AR registration, assert that
  `<mailbox_root>/<spec_id>/`, `<reports_dir>/<spec_id>/`, and
  any delegated-task file for `spec_id` all DO NOT exist. Verifies
  the guard fires before side effects.

### Manual verification

- Create AR-001 via `speckit.orca.adopt new "CLI entrypoint"`;
  verify the file lands under `.specify/orca/adopted/` with
  `status: adopted` and HEAD SHA pre-populated in Baseline Commit.
- Run `speckit.orca.adopt list`; verify AR-001 appears.
- Run `flow-state .specify/orca/adopted/AR-001-cli-entrypoint.md`;
  verify the adoption view returns with `review_state: not-applicable`
  and no incomplete-milestone entries derived from a directory-style
  expectation.
- Run `speckit.orca.adopt supersede AR-001 999-test-fixture` against
  a temporary test fixture (NOT against a real spec); verify the
  supersede command rejects if the target spec does not exist.
- Attempt `matriarch register-lane AR-001-cli-entrypoint`; verify
  rejection with the adoption-specific error message and verify
  no mailbox / reports artifacts were created.

## 11. Dependencies and sequencing

### Hard prerequisites

- **013 spec-lite** must merge first. 015 mirrors 013's registry
  pattern, guard template (guards placed at the TOP of
  `register_lane`, both implemented together), and per-file
  flow-state extension. `_is_adoption_record` mirrors the 013
  plan pattern rather than copying implemented code — 013's guard
  is not yet in `matriarch.py` at plan time.

### Soft prerequisites

- **012 review-model** — NOT a hard prerequisite. 015 does not
  modify 012's Review Milestone contract. The
  `review_state: not-applicable` marker is an inline field on
  flow-state's adoption view (mirroring how 013 defines
  `review_state` on the spec-lite view), not an extension to 012.
  015 can ship independently of 012's merge state.
- **009/014 yolo runtime** — not a blocker. 009's spec.md
  currently mentions `micro-spec/spec artifact` as valid yolo
  starts; 013 renames `micro-spec` to `spec-lite` and opts it out
  of yolo in v1. 015 similarly does not add ARs as a valid yolo
  start. If 009 wants to include ARs (or spec-lites) as a valid
  yolo start in a future version, that's a 009 concern, not 015's.

### What 015 blocks

- Nothing. 015 is purely additive.

### What 015 does not block

- 012 runtime completion (if 012 contracts have shipped but runtime
  is in progress)
- 009/014 runtime implementation
- Any future capability pack work
- v2 per-project adoption pipeline (016+)

### Suggested order relative to 012 and 013

1. **013 spec-lite** — merged
2. **012 review-model** — merged (at least contracts; runtime
   can be in progress)
3. **015 plan** (this doc) — reviewed
4. **015 contracts** (follow-up task) — reviewed
5. **015 implementation wave** — 3 commits, one PR, atomic
   additive change (matches Section 5 grouping)
6. **015 command prompt rewrite** — separate PR after contracts,
   same deferral rule as 012/013

## 12. Success criteria

- `commands/adopt.md` exists and is registered in `extension.yml`
- `extension.yml` registers `speckit.orca.adopt`
- `.specify/orca/adopted/` directory exists with `00-overview.md`
  bootstrap file
- `src/speckit_orca/adoption.py` runtime module exists with six
  functions (create / list / get / supersede / retire /
  regenerate-overview)
- `flow_state.py` interprets AR file paths and returns the adoption
  view with `review_state: "not-applicable"` as a hard-coded field
- `flow_state.py` does not crash on AR file targets and does not
  derive directory-style incomplete-milestone entries for them
- `flow_state.py` changes do not alter full-spec or spec-lite
  behavior (regression tests)
- `matriarch.py` rejects lane registration against adoption
  records with a clear pointer at the full-spec alternative
- `matriarch.py` guards fire BEFORE any filesystem side effects in
  `register_lane` — rejected AR registrations leave no mailbox
  root, no reports dir, no delegated-task file on disk
- AR-001 through AR-004 exist as real records, all with
  `status: adopted`
- All existing tests still pass (spec-lite tests, full-spec tests,
  etc.)
- New tests cover create/list/get/supersede/retire, flow-state
  per-file interpretation, matriarch guard, and the no-side-effect
  invariant
- `README.md` intake section names adoption records as the
  brownfield entry point
- Zero references to touch-point metadata, `**Touches ARs**:`
  parsing, or new mailbox event types anywhere in runtime code or
  tests (verifiable by grep — confirms scope discipline held)

## 13. Explicit non-goals

- Not rewriting `commands/adopt.md` prompt content in this plan
  (deferred)
- Not auto-generating ARs from git history or code
- Not implementing `adopt new --from <path>` code-introspection
  scaffolding
- Not implementing `adopt scan` repo-wide discovery
- Not shipping a v2 adoption manifest
- Not making ARs drivable by the 009 yolo runner (and not
  retroactively changing 009's `micro-spec/spec artifact` wording —
  that's a 009/013 concern)
- Not changing spec-lite's shape (013 stays locked)
- Not modifying 012's Review Milestone contract — `review_state`
  stays an inline flow-state view field, not a cross-spec contract
- Not introducing OpenSpec delta-spec semantics
- Not building AR review gates
- Not adding touch-point coordination metadata, `**Touches ARs**:`
  parsing, or cross-lane overlap detection — deferred to a future
  spec if brownfield coordination demand materializes and is
  scoped with a proper contract addition
- Not adding new mailbox event types — current accepted set
  stays untouched
- Not enforcing status-dependent section invariants — markdown is
  operator-editable; parser is tolerant
- Not shipping a repo-wide flow-state summary UX — per-target CLI
  is preserved; the overview file is the registry-wide index
- Not exercising supersession against production records in the
  first wave — tested in `tests/test_adoption.py` only
- Not coordinating with an upstream lightweight-spec concept
- Not touching frozen docs (refinement reviews, v1.4 design docs)

## 14. Open questions for the contract-writing task

These surface during plan drafting but are properly answered during
the contract-writing task, not now:

1. **Record schema**: pure markdown with strict section naming
   (lean: yes, matches 013/evolve/brainstorm-memory) or YAML
   frontmatter? My lean: pure markdown.
2. **Overview regeneration frequency**: automatic on every write
   (create / supersede / retire) or explicit via
   `regenerate-overview`? My lean: both — automatic by default,
   explicit command available for recovery.
3. **`baseline_commit` pre-population**: `adopt new` reads
   `git rev-parse HEAD` at creation time. If the repo isn't a git
   repo or git is unavailable, fall back gracefully (leave field
   empty, don't crash). My lean: defensive fallback.
4. **Supersede validation**: when the superseding spec is under
   `specs/<NNN-something>/`, does validation require `spec.md` to
   exist, or just the directory? My lean: require `spec.md` — the
   directory alone may be scaffolding that hasn't been populated.
5. **Retire reason empty-body handling**: if `adopt retire` runs
   without `--reason`, should the Retirement Reason section be
   written empty, written with a sentinel (`<no reason given>`),
   or omitted entirely? My lean: omit the section entirely — the
   presence of `Status: retired` is enough signal; no empty
   sections added for their own sake. Matches the tolerant-parser
   posture from section 6.
6. **Initial-records commit ordering**: AR-001 through AR-004 can
   be created by running the `new` command against the just-built
   runtime, or hand-authored. My lean: run the `new` command so
   the test pass exercises real ID allocation and overview
   regeneration on real files. Hand-authored fallback if the test
   setup is awkward.
7. **Tolerant parser boundaries**: the plan says the parser
   accepts hand-edited records with inconsistent section/status
   pairings (e.g., `Status: adopted` with a `Superseded By`
   section). Is there any inconsistency that SHOULD still fail
   parsing? My lean: structural failures only — missing required
   section (Summary / Location / Key Behaviors), unparseable
   metadata (unknown Status value, malformed Adopted-on), no
   matching `# Adoption Record:` header. Everything else parses.

## 15. Suggested next steps

1. Merge this plan PR.
2. Start the contract-writing task:
   - `specs/015-brownfield-adoption/contracts/adoption-record.md`
     (metadata + body section shape, tolerant-parser posture,
     status authority, structural vs. semantic failure modes)
   - `specs/015-brownfield-adoption/contracts/matriarch-guard.md`
     (lane-registration rejection, guard placement at the TOP of
     `register_lane`, no-side-effect invariant)
   - `specs/015-brownfield-adoption/data-model.md` (entities,
     relationships, invariants, mirroring 013's data-model
     structure)
   - `specs/015-brownfield-adoption/quickstart.md` (walkthrough:
     create AR, list, mark superseded against a test fixture,
     mark retired)
3. Implementation wave (3 commits, one PR).
4. Command prompt rewrite for `commands/adopt.md` (separate PR).
5. Future work — not scoped here:
   - Touch-point coordination metadata + matriarch mailbox event
     type extension (one spec, one wave, one contract change)
   - v2 per-project adoption pipeline (manifest, scan, init
     wizard) in a separate spec (016+)
