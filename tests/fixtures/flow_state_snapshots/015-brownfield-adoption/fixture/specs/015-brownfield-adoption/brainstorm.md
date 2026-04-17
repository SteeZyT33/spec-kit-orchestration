# Brainstorm: Brownfield Adoption — Reference Records for Pre-Orca Features

**Feature Branch**: `015-brownfield-adoption`
**Created**: 2026-04-14
**Status**: Brainstorm (historical — scope narrowed in plan per 2026-04-14 cross-review)
**Informed by**:

- Session comparison of GitHub spec-kit vs. `@fission-ai/openspec` vs.
  Priivacy-ai spec-kitty (2026-04-14). OpenSpec's philosophy —
  *"built for brownfield not just greenfield"* — exposed a real gap:
  Orca currently assumes greenfield.
- Memory note `project_brownfield_adoption.md` (2026-04-12) ranking
  five candidate ideas. Top of the list: spec-lite as brownfield
  intake + partial flow-state.
- `specs/013-spec-lite/brainstorm.md` for the registry/guard pattern
  that 015 mirrors.
- Codex (gpt-5.4, high effort) cross-review on 2026-04-14 —
  findings in [review-codex.md](./review-codex.md). Cuts applied
  in [plan.md](./plan.md).

---

## Post-cross-review revision (2026-04-14)

A cross-review pass by codex gpt-5.4 (high effort) identified
several items from this brainstorm that were **cut or rescoped in
the plan**. Keep this document as the historical exploration, but
treat `plan.md` as the authoritative scope. Summary of what
changed:

- **Touch-point coordination metadata** (sections on full-spec
  `**Touches ARs**:` declaration and matriarch conflict warnings)
  — **cut from v1**. The proposed mechanism required a new
  matriarch mailbox event type (which does not exist — the current
  accepted set is `instruction`, `ack`, `status`, `blocker`,
  `question`, `approval_needed`, `handoff`, `shutdown`) and was
  too weak structurally to justify the complexity. Deferred to a
  future spec if brownfield coordination demand materializes.
- **AR-002 in-wave supersession** — **cut from v1**. The
  supersession mechanic is exercised in `tests/test_adoption.py`
  against fixture records, not against production ARs.
- **012 `review_state` aggregator extension** — **dropped**. 012's
  actual contract is `Review Milestone` with per-artifact status
  fields (`review_spec_status`, `review_code_status`,
  `review_pr_status`, `overall_ready_for_merge`), not a shared
  `review_state` enum. `review_state: not-applicable` is an
  inline field on flow-state's adoption view, mirroring how 013
  defines `review_state` on the spec-lite view.
- **Repo-wide flow-state rendering with `--show-superseded` /
  `--show-retired` flags** — **cut**. `flow_state.py` is a
  per-target interpreter (file or directory); 015 extends it to
  interpret AR files, matching 013's per-file spec-lite extension.
  The `00-overview.md` file is the registry-wide index, owned by
  `adoption.py`.
- **Status-dependent section invariants** — **relaxed**. Parser is
  tolerant: `Status` is authoritative; sections that don't match
  the status are parsed and returned, not rejected. Structural
  failures (missing required section) still produce
  `status: invalid`.
- **Guard insertion point** — **specified more precisely**. Guards
  fire at the TOP of `register_lane`, before mailbox root / reports
  dir / delegated-task file side effects. Rejected registrations
  leave the workspace untouched.

The primitive shape below (AR separate from spec-lite, registry
layout, lane-anchor guard instinct) survived the review. Only the
coordination machinery and cross-spec assumptions were cut.

---

## Problem

Orca's entire workflow assumes features start life inside the system:
`brainstorm → specify → plan → tasks → implement → reviews`. Every
durable primitive (flow-state, matriarch, yolo runner) reads a
`specs/NNN-feature/` directory and expects the full artifact set.

Real projects don't look like that. A typical codebase has dozens of
features that predate Orca adoption. They exist, they work, and
nothing in Orca knows they're there. Consequences today:

- **Flow-state is noisy on brownfield projects.** Every pre-Orca
  feature either gets ignored (no record) or retroactively spec'd
  (enormous ceremony cost). There's no "this feature exists, it's
  done, don't warn" option.
- **Matriarch can't coordinate around legacy features.** If two new
  lanes both touch the auth middleware (which was built pre-Orca),
  matriarch has no way to see the conflict. Touch-point coordination
  requires a spec file that never got written.
- **Spec-kit-orca itself is in this state right now.** Several
  subsystems (CLI entry, worktree runtime, early config loading) were
  built before 005-flow-state and 010-matriarch existed. They have no
  records in Orca's own `specs/` directory.
- **OpenSpec explicitly markets brownfield as a core strength.** Orca
  chose spec-kit as substrate for good reasons (phase-gated lanes,
  governance, review artifacts), but inherited spec-kit's greenfield
  assumption. Without a brownfield story, Orca is less adoptable than
  it should be.

013 spec-lite helps (lightweight intake for small NEW work), but
spec-lite's `## Problem` / `## Solution` fields don't fit a feature
that already works. Forcing existing features into spec-lite's shape
produces awkward records like *"Problem: nothing, Solution: nothing,
Acceptance: the existing behavior."*

## Proposed Model

**Ship a new `Adoption Record` (AR) primitive** — a reference-only
document describing an existing feature's shape, location, and known
behaviors. Separate from spec-lite. Never reviewed. Not drivable by
yolo. Never anchors a matriarch lane.

Adoption records live beside spec-lite in their own registry:

```text
.specify/orca/
├── spec-lite/
│   ├── 00-overview.md
│   ├── SL-001-<slug>.md        ← small NEW work
│   └── ...
└── adopted/
    ├── 00-overview.md
    ├── AR-001-<slug>.md        ← existing feature reference
    └── ...
```

### Minimum shape

```markdown
# Adoption Record: AR-NNN: <title>

**Status**: adopted
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
<optional: full spec ID that later replaced this AR>
```

**Required fields**: ID, Title, Status, Adopted-on, Summary, Location
(≥1 path), Key Behaviors (≥1 bullet).
**Optional fields**: Baseline Commit, Known Gaps, Superseded By.

### Status enum

Three values: `adopted` | `superseded` | `retired`.

- `adopted` — stable reference state, feature exists and works
- `superseded` — a full spec has replaced the AR; AR kept as history
- `retired` — feature was removed from the codebase; AR kept as
  historical record

No `invalid` status on disk — malformed records surface as
`status: invalid` at flow-state parse time, same pattern as
spec-lite's malformed-record handling.

### Overview file

`.specify/orca/adopted/00-overview.md` — generated index grouping ARs
by status. Regenerated on every `new` / `supersede` / `retire` /
explicit `regenerate-overview` call. Same pattern as spec-lite's
overview. Excluded from record-listing walks by filename.

## Relationship to spec-lite (013)

Parallel registries, zero coupling. The memory note initially
suggested extending spec-lite with a fourth `adopted` status. We
rejected that approach because spec-lite's `## Problem` / `## Solution`
fields fight the adoption use case — an existing feature has no
problem and no solution, it just *is*. Forcing one primitive to span
"bounded new work" and "existing reality" creates a schema that
fights itself. Two well-fit primitives are cleaner than one
overloaded one.

013 stays locked. User-stated design principle: *"keep lite lite."*

Spec-lite records CAN reference ARs in their body as context, same
way full specs can. ARs cannot reference spec-lites (spec-lites are
transient; ARs are durable).

## Relationship to full spec flow

Adoption records are reference-only. They do NOT participate in the
full spec flow. The decision rule:

- **Adoption Record** for an existing feature Orca needs to know
  about but which has no active work against it
- **Spec-lite** for bounded NEW work that doesn't justify a full
  spec folder (a fix, a small refactor, a doc update)
- **Full spec** for a new subsystem, cross-module change, contract
  change, or anything that benefits from review gates

An AR can be *superseded* by a full spec: when you write
`specs/020-new-auth/` to replace the adoption record AR-003
(auth-middleware), you run `speckit.orca.adopt supersede AR-003
020-new-auth`. The AR file stays, gains `**Superseded By**: 020-new-auth`,
and flow-state renders it under the "superseded" group in the
overview.

## Relationship to 012-review-model

Adoption records are never reviewed. `review_state: not-applicable`
is a hard invariant for this kind, distinct from spec-lite's
`unreviewed` default (which implies "could be reviewed, hasn't
been").

~~012's review aggregator contract must learn a third
`review_state` value — `not-applicable` — alongside `unreviewed` and
the reviewed states. 015 depends on 012 landing first for this
contract extension.~~

**(Superseded by [plan.md](./plan.md) — see revision note at the top
of this file.)** 015 does NOT modify 012's contract.
`review_state: not-applicable` lives on flow-state's adoption view
inline (mirroring how 013 defines `review_state` on the spec-lite
view), not on 012's per-artifact status fields. 012 is not a hard
prerequisite.

## Relationship to 010-matriarch

**Guard**: adoption records cannot anchor matriarch lanes. A new
guard function `_is_adoption_record(paths, spec_id)` mirrors 013's
`_is_spec_lite_record` pattern — canonical path check, glob fallback
under `.specify/orca/adopted/`, header-scan fallback for misplaced
files. `register_lane` runs both guards before `_feature_dir`
resolves.

Error shape follows 013's template:

```text
Cannot register lane for adoption record 'AR-003-auth-middleware'.
Adoption records describe pre-existing features, not active work.
To coordinate work that touches AR-003, hand-author a full spec
under specs/ and declare the AR as a touch-point in its metadata.
```

**Touch-points**: full specs declare which ARs they touch in spec.md
metadata:

```markdown
# Feature Specification: New Auth Model
**Feature Branch**: `020-new-auth`
**Created**: 2026-04-14
**Touches ARs**: AR-001-session-store, AR-003-auth-middleware
```

Spec-lites and ARs do not declare touch-points. Only full specs do.

**Conflict detection**: when `register_lane` succeeds for a full
spec, matriarch reads the spec's touch-points, compares against
active lanes' touch-points, and emits an advisory WARNING event to
the new lane's mailbox if there's overlap. Registration still
succeeds — warnings are advisory, not blocking. Operator judgment
resolves. Rationale: matriarch can't distinguish concurrent-edit
conflicts from shared-context false positives; blocking would
generate enough false positives to drive people around the system.

Readiness aggregation is unaffected by touch-points.

## Relationship to 009/014 yolo runtime

Adoption records are out of yolo's scope. Same rule as spec-lite: the
yolo runner drives full specs through stages; ARs have no stages.
Attempting to yolo an AR would require inventing a "reference-only"
run mode for no clear benefit.

If future work ever needs automated AR lifecycle (e.g., scan a repo
and propose retirements), that's a separate command under the
`speckit.orca.adopt` surface, not a yolo extension.

## Command surface

Same restraint as 012/013: this brainstorm proposes the shape; the
actual `commands/adopt.md` prompt gets rewritten in a later task
after the plan lands.

### v1 commands

- **`speckit.orca.adopt new <title>`** — creates
  `.specify/orca/adopted/AR-NNN-<slug>.md` with next ID and populated
  template. Regenerates overview.
- **`speckit.orca.adopt list [--status adopted|superseded|retired]`**
  — lists ARs with ID, title, status, adopted-on date. Matches
  spec-lite list output style.
- **`speckit.orca.adopt supersede <ar-id> <spec-id>`** — writes
  `**Superseded By**: <spec-id>` into the AR, moves it into the
  superseded group in the overview. AR file preserved.
- **`speckit.orca.adopt retire <ar-id> [--reason "<text>"]`** —
  marks AR as retired, records optional reason. AR file preserved.
- **`speckit.orca.adopt regenerate-overview`** — rebuilds
  `.specify/orca/adopted/00-overview.md` from current AR files.
  Safe to run anytime; overview is always derivable from records.

### Deferred to v2 (per-project scope)

- `speckit.orca.adopt new --from <path>` — code-introspection
  scaffolding (pre-fill Location + Key Behaviors)
- `speckit.orca.adopt scan` — repo-wide discovery
- `speckit.orca.adopt init` — project-level adoption wizard
  (writes adoption manifest, bulk-creates initial ARs)

Touch-point declaration is NOT a command — it's markdown metadata
the author writes into spec.md. No CLI surface for touch-points.

No `adopt update` command — edit the markdown directly. ARs are not
reviewed; edits don't need a formal change flow.

## Flow-state integration

### New view kind

Flow-state currently recognizes `feature` (full spec) and `spec-lite`.
015 adds `adoption`:

```text
kind: "adoption"
id: "AR-003-auth-middleware"
slug: "auth-middleware"
title: "Auth Middleware (pre-Orca)"
status: "adopted" | "superseded" | "retired" | "invalid"
adopted_on: "2026-04-14"
baseline_commit: "abc1234" | null
location: ["src/auth/middleware.py", "src/auth/sessions.py"]
superseded_by: "020-new-auth" | null
review_state: "not-applicable"   ← hard invariant
```

### Key behaviors

- **No stage progression.** ARs are born `adopted` and stay that way
  until superseded or retired. Flow-state reports a single adoption
  milestone, not a stage chain.
- **Missing-artifact warnings suppressed.** Flow-state today warns
  about features missing plan.md / tasks.md. For ARs, these warnings
  are suppressed — the feature predates Orca and won't have those
  artifacts, by design. This is the "partial flow-state" idea from
  the memory note: flow-state learns that partial-is-valid for
  `kind: adoption`.
- **Supersession chain visibility.** When an AR has
  `Superseded By: 020-new-auth`, flow-state renders the link in the
  overview. Traceable history without burying the AR.
- **Rendering section.** ARs get their own section in the
  `speckit.orca.flow-state` summary output, positioned below
  spec-lite and above full specs, labeled "Adopted features
  (<count>)". Superseded ARs collapse to a one-line entry by default;
  `--show-superseded` expands them.

### Parser

`_parse_adoption_record(path)` in `flow_state.py` reads markdown,
validates required sections, returns `AdoptionRecord` dataclass.
Malformed records produce `kind: "adoption", status: "invalid"` with
graceful degradation — same pattern as spec-lite.

## Downstream impact (file-by-file)

### `src/speckit_orca/flow_state.py`

- New `AdoptionRecord` dataclass + `_parse_adoption_record` function
- New view kind `adoption` with fixed `review_state: not-applicable`
- New section in flow-state summary output
- Warning-suppression logic for missing-artifact checks on AR kind
- Overview regeneration for `.specify/orca/adopted/00-overview.md`

### `src/speckit_orca/matriarch.py`

- New guard function `_is_adoption_record(paths, spec_id)` mirroring
  `_is_spec_lite_record` (013)
- `register_lane` runs both guards before `_feature_dir` resolves
- New touch-point parser that reads `**Touches ARs**:` from full spec
  metadata
- New advisory-warning logic for overlapping touch-points across
  active lanes

### `commands/adopt.md` (new)

Command prompt covering `new` / `list` / `supersede` / `retire`.
Written after the plan lands, same deferral pattern as 012/013.

### Extension manifest

`.specify/integrations/claude.manifest.json` registers the new
slash commands. Same pattern as spec-lite's registration.

### `README.md`

- Update the intake/lifecycle section to mention adoption records as
  the brownfield entry point, beside spec-lite for new small work and
  full specs for substantial new work.
- Add a short "brownfield adoption" subsection explaining when to
  pick AR vs. spec-lite vs. full spec.

### `specs/013-spec-lite/`

- No changes. 015 is purely additive. 013 stays locked.

### `specs/012-review-model/`

- Small contract extension: `review_state` aggregator learns
  `not-applicable` as a third value. May be a no-op if 012's
  contract already admits arbitrary enum values.

## Rollout

Single atomic breaking wave, matching 012/013 pattern. No alias
period — adoption is new, nothing to deprecate. Rollout ordering:

1. 013 spec-lite merged (provides registry pattern)
2. 012 review-model merged (provides review aggregator contract)
3. 015 plan drafted
4. 015 contracts + data model
5. 015 runtime (`flow_state.py` + `matriarch.py` changes)
6. 015 tests
7. 015 commands + README updates
8. 015 ships with initial ARs populated (see Initial Records below)

## Initial Records (first wave)

A repo audit ran as part of this brainstorm. The following pre-Orca
subsystems are uncovered by any existing spec and will ship as the
first four adoption records in the same wave as 015's primitive.
They serve double duty: real records the project actually needs, and
end-to-end proof that the primitive works before anyone else touches
it.

### AR-001 — CLI entrypoint

- **Location**: `src/speckit_orca/cli.py`, `speckit-orca` binary
- **Summary**: Argument routing, subcommand dispatch, and config
  loading for the `speckit-orca` CLI. Predates every named spec.
- **Why first**: exercises the most basic AR flow — a pure reference
  record with no lifecycle events. Proves parsing, flow-state
  rendering, and overview generation work on the simplest case.

### AR-002 — Cross-review shim

- **Location**: `scripts/bash/crossreview.sh`,
  `scripts/bash/crossreview-backend.py`
- **Summary**: Pre-012 implementation of cross-review coordination.
  Implements an older model that 012's three-artifact review design
  supersedes.
- **Why second**: exercises the full supersession flow. Plan calls for
  landing AR-002 as `adopted`, then immediately running
  `speckit.orca.adopt supersede AR-002 012-review-model` as part of
  the same wave. Proves the supersession mechanic, the overview
  regrouping, and the `Superseded By` metadata write — all before any
  external user touches the primitive.

### AR-003 — Templates infrastructure

- **Location**: `templates/` directory
- **Summary**: Spec templates, command templates, review templates
  used by spec-kit-orca's tooling and integration packages.
- **Why third**: exercises touch-point behavior. Most future specs
  will touch `templates/` when adding new command prompts or spec
  shapes; AR-003 becomes a common touch-point declaration in those
  specs, validating matriarch's conflict-detection path.

### AR-004 — Extension manifest / install pipeline

- **Location**: `extension.yml`,
  `.specify/integrations/claude.manifest.json`,
  `.specify/integrations/speckit.manifest.json`, relevant `Makefile`
  targets
- **Summary**: How Orca commands get registered with Claude Code,
  Codex, and Gemini. Operator-facing surface that every other
  subsystem depends on.
- **Why fourth**: exercises multi-file Location fields and validates
  that ARs can describe cross-cutting infrastructure, not just
  per-module code.

### Deferred / optional

- **AR-005 — PR-thread resolver** (`scripts/bash/resolve-pr-threads.sh`).
  Trivial utility. Including it proves ARs work for scripts; omitting
  it keeps the initial set tight. Plan decides.

## Open questions (to resolve before plan.md)

1. **Touch-point syntax**: comma-separated list in a single metadata
   line (`**Touches ARs**: AR-001, AR-003`) OR a bullet list under a
   dedicated `## Touch-Points` section? Single-line metadata matches
   existing `**Feature Branch**:` / `**Created**:` convention. Bullet
   list scales better if a spec touches many ARs. My lean: single
   metadata line for v1; promote to section if 10+ touch-points
   becomes common.

2. **Overview layout**: three fixed groups (adopted / superseded /
   retired) OR a single flat list sorted by status then date? Fixed
   groups match spec-lite's pattern. My lean: fixed groups.

3. **Baseline Commit field**: required or optional in v1? Optional is
   simpler; required is more robust for v2's partial-flow-state
   posture. My lean: optional in v1, recommended by the `new`
   command's default template (pre-populated with current HEAD SHA
   the user can clear if they don't want it).

4. **Adoption manifest location**: `.specify/orca/adoption.md`
   (project root of the orca registry) OR
   `.specify/orca/adopted/MANIFEST.md` (inside the registry)?
   Project-root placement signals project-level scope; in-registry
   placement keeps related files together. My lean: project-root for
   v2, but v1 doesn't ship a manifest at all so this is a v2
   question.

5. **Supersede behavior when the superseding spec doesn't exist
   yet**: should `adopt supersede AR-003 020-new-auth` validate that
   `specs/020-new-auth/` exists? My lean: yes, reject if missing.
   Prevents broken Superseded-By pointers.

6. **Retire reason storage**: append to Known Gaps section, or
   dedicated `## Retirement Reason` section? My lean: dedicated
   section, appears only when status is retired.

7. **OpenSpec delta-spec semantics for future work**: explicitly
   out of scope for 015, but worth deciding whether a future 016
   spec might introduce them. If so, 015's `Location` field and
   touch-point mechanism should be forward-compatible with a delta
   model. My lean: design 015 reference-only; revisit delta semantics
   in a dedicated 016 brainstorm only if real demand emerges.

8. **Audit: existing pre-Orca features in spec-kit-orca itself** —
   resolved during this brainstorm. Findings documented in "Initial
   Records (first wave)" above. Four ARs to ship (AR-001 CLI,
   AR-002 cross-review shim, AR-003 templates, AR-004 extension
   manifest), one optional (AR-005 PR-thread resolver).

## Explicit non-goals

- Not changing spec-lite's shape (013 stays locked; user-stated
  principle: *"keep lite lite"*)
- Not changing the full spec flow (still authoritative for new work)
- Not adopting OpenSpec delta-spec semantics (reference-only in v1)
- Not introducing an archive layer (OpenSpec's `archive/` model is a
  separate question; ARs are durable references, not archived
  changes)
- Not building AR review gates (`review_state: not-applicable` is a
  hard invariant)
- Not auto-generating ARs from git history (v1 is manual)
- Not making ARs drivable by the 009 yolo runner
- Not changing `commands/adopt.md` prompt in this brainstorm (same
  deferral pattern as 012/013)
- Not building the v2 per-project adoption pipeline (manifest, scan,
  init wizard) — design the v1 primitive to compose with v2, don't
  build v2
- Not building bulk-supersede or bulk-retire operations — one AR at
  a time keeps the audit trail clear

## Dependencies on other in-flight work

### Hard prerequisites

- **013 spec-lite** — provides the registry pattern, guard template,
  overview convention. 015's `_is_adoption_record` guard is a direct
  copy of `_is_spec_lite_record`.
- **012 review-model** — 015 requires `review_state: not-applicable`
  as a third aggregator value.

### Soft prerequisites (nice-to-have, not blocking)

- **009 yolo runtime** (if 009 ships before 015) — lets 015 explicitly
  document that ARs are out of yolo scope with concrete vocabulary
  instead of hypothetical references.
- **Product-surface refinements** touching README intake section —
  015 updates the same section; conflict is avoidable if 015 lands
  after.

### Independent of 015 timing

- 011 evolve — no interaction
- 010 matriarch's other in-flight refinements (drift flag, checkout
  target) — 015 adds guards to matriarch.py but doesn't touch the
  refinement surface

## Suggested next steps

1. Review this brainstorm and answer the remaining open questions
   (1-7; q8 resolved in "Initial Records" above).
2. Write `specs/015-brownfield-adoption/plan.md` with storage layout,
   parser contract, matriarch integration, command surface, and
   initial-records specifics.
3. Write `specs/015-brownfield-adoption/data-model.md` and contract
   files (adoption-record.md, matriarch-guard.md modeled after
   013's).
4. Implement `flow_state.py` + `matriarch.py` changes.
5. Write tests.
6. Rewrite `commands/adopt.md` prompt.
7. Update README intake section.
8. Record AR-001 through AR-004 (plus AR-005 if plan accepts it) in
   the same wave. Supersede AR-002 with 012-review-model immediately
   after landing to exercise the supersession flow.
