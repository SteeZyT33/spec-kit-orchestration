# Brainstorm: Spec-Lite — OpenSpec-Inspired Intake

**Feature Branch**: `013-spec-lite`
**Created**: 2026-04-11
**Status**: Brainstorm
**Supersedes**: `micro-spec` (the current command, not a formal spec)
**Informed by**:
- `docs/refinement-reviews/2026-04-11-product-surface.md` (GPT Pro said: "intake should feel like an entry layer; micro-spec is too heavy")
- Session research on `@fission-ai/openspec` (three-field proposal, no phase gates, no promotion path)
- Session research on `spec-kitty` (their mission model for comparison)

---

## Problem

Current `micro-spec` is supposed to be a lighter-weight alternative to
the full feature-spec path, for bounded work that does not justify
running `brainstorm → specify → plan → tasks → implement → reviews`.
In practice, it still carries:

- A mini-plan (structured planning section)
- A declared verification mode (test / characterization / evidence-first)
- A code-review handoff gate
- Explicit promotion rules when scope grows
- Durable record in a per-feature or global micro-spec directory

That's not an entry layer. It's *"the full spec, but shorter"*. The
refinement review called this out as one of the places Orca's surface
is heavier than it needs to be, and GPT Pro explicitly recommended
making intake feel like one clean concept.

Meanwhile, OpenSpec's philosophy — *"fluid not rigid, iterative not
waterfall, easy not complex, built for brownfield not just greenfield"*
— ships an intake shape that's **three mandatory fields** and that's
it. No phase gates, no promotion path, the same structure scales from
a bug fix to a full feature by adding sections as the work grows.

## Proposed Model

**Rename `micro-spec` to `spec-lite` AND cut scope to five fields max.**

Spec-lite should feel like writing a good commit message: enough
structure to force clarity, not so much that you abandon it for a
to-do list.

### Minimum shape

```markdown
# Spec-Lite: <title>

## Problem
<1-2 sentences: what is broken, missing, or needed>

## Solution
<1-2 sentences: what you are doing about it>

## Acceptance Scenario
<one BDD given/when/then, manual or test — the bar for "done">

## Files Affected
<list of paths, no implementation detail>

## Verification Evidence (optional)
<command, output, or manual step — added after completion>
```

Five fields. Four required, one optional. **No phase gates. No
mandatory verification mode. No code-review handoff. No promotion
path.**

### What "no promotion path" means in practice

If a spec-lite's scope grows mid-flight:

1. **Default: extend the spec-lite inline.** Add sections, add more
   acceptance scenarios, add a sketch of files. The document grows
   in-place. It is not a different document type.
2. **Only promote when the spec-lite outgrows "one feature dir."**
   Creating a new full spec under `specs/NNN-<name>/` is a deliberate
   move, not an automatic trigger. The user decides.
3. **If promotion happens, the spec-lite stays as a pointer.** The
   feature dir's `spec.md` links back to the original spec-lite record
   for history. The spec-lite is not deleted.

This replaces the current `micro-spec` rule ("promote when scope
exceeds X sections"). The new rule is: **extend until promotion feels
obvious**. Promotion is a human judgment call, not a threshold.

### Storage

**Two options for where spec-lite records live.** Both are viable;
picking one is an open question for the plan.

**Option A — global registry.** All spec-lites live under
`.specify/orca/spec-lite/` with an auto-incrementing ID
(`SL-001`, `SL-002`, ...). One markdown file per record. Easy to list,
easy to cross-reference. Matches the pattern `brainstorm-memory` and
`evolve` already use.

**Option B — feature-dir-scoped.** A spec-lite lives as
`spec-lite.md` inside a lightweight feature directory, one level
shallower than a full `specs/NNN-<name>/`. Maybe
`.specify/orca/spec-lite/<slug>/spec-lite.md` so it has room to grow
its own `files-affected.md` or `verification.md` if needed.

My lean: **Option A for the first version.** Simpler file layout,
easier for flow-state to enumerate, fits the "one doc, not a folder"
philosophy. If a spec-lite genuinely needs supporting docs, that's a
signal it should be promoted.

## Relationship to the full spec flow

Spec-lite does NOT replace the full spec flow. It sits beside it as
the answer to *"what if this doesn't deserve a whole spec folder?"*.
The full spec flow (`brainstorm → specify → plan → tasks → implement
→ reviews`) is still the right tool for features that need real
planning, contracts, data models, and review gates.

The decision rule for an operator is roughly:

- **Spec-lite** for a bug fix, a one-module refactor, a doc update, a
  small behavior tweak, a cleanup that fits in one commit
- **Full spec** for a new subsystem, a cross-module change, a
  contract change, anything that needs a data model or contract
  files, anything that benefits from structured review gates

**Same repo, same tooling, same commands where they overlap.** The
difference is the shape of the record.

## Relationship to `012-review-model`

This is a real design question that needs an answer before the plan.

**Does a spec-lite participate in review-spec / review-code /
review-pr?** Three options:

1. **Full participation.** A spec-lite can have a `review-spec.md`
   (cross-pass against the spec-lite), a `review-code.md` (code
   review against the change), and a `review-pr.md` (PR comments).
   Review still happens, just against shorter artifacts.
2. **Implicit self-pass only.** Spec-lite skips formal review
   artifacts. The author's own check during implementation is
   assumed. Cross-review is available but opt-in via explicit
   `review-code` run.
3. **Optional and operator-chosen.** Spec-lite has no mandatory
   review. The operator can run any of the three reviews manually if
   they want one, but the default is to skip all of them.

My lean: **Option 3.** Spec-lite's whole reason for existing is to
reduce ceremony. Making it implicitly trigger review artifacts
re-adds the ceremony. The honest default is "no mandatory reviews,
run them if you want them." Cross-review is still available as an
explicit command against whatever spec-lite file you point at.

Trade-off: no automated signal that the change was reviewed. Mitigation:
flow-state reports spec-lite records as `unreviewed` by default, so
the information is still visible — it just doesn't block merge.

## Relationship to `014-yolo-runtime`

Spec-lite should **probably not** be drivable by the 009 yolo runner
in v1. The yolo runner is for end-to-end feature execution from spec
through review, which is the full-spec flow. Spec-lite intentionally
skips most of those stages. Trying to run yolo against a spec-lite
would mean reinventing a "light yolo" for no clear benefit.

If spec-lite ever needs automated execution, the right answer is
probably a different command (`speckit.orca.spec-lite-implement` or
similar) that walks the acceptance scenario and asks the operator to
run the change. Out of scope for this brainstorm.

## Command surface

The user said *"don't change the review prompts until we have dialed
this in."* Spec-lite is not a review prompt, but it IS a command
prompt, so the same restraint applies: **this brainstorm proposes the
model; the actual `commands/spec-lite.md` prompt gets rewritten in a
later task after the plan lands**.

However, the command surface does need a proposed shape in this
brainstorm so we can reason about whether the model works:

- **`speckit.orca.spec-lite new <title>`** — create a new spec-lite
  record with the five-field template pre-populated. Dispatches to the
  author to fill in Problem / Solution / Acceptance Scenario / Files
  Affected.
- **`speckit.orca.spec-lite list`** — list all spec-lite records with
  status (open, implemented, abandoned).
- **`speckit.orca.spec-lite done <id>`** — mark a spec-lite as
  implemented, optionally record verification evidence.
- **`speckit.orca.spec-lite promote <id>`** — start a full spec
  (`specs/NNN-<name>/`) from a spec-lite's content as the seed.
  Spec-lite stays as a history pointer.

The current `micro-spec` command is retired. If there are existing
`micro-spec` records in the repo (`.specify/orca/micro-specs/` or
wherever they live), they get migrated to the new spec-lite shape in
the same breaking wave.

## Downstream impact

Smaller than 012's impact because spec-lite is additive for most of
the system, but still real:

### `src/speckit_orca/flow_state.py`
- Needs to understand spec-lite records as a distinct feature-state
  kind, separate from full-spec features
- Report shape: `spec-lite-open`, `spec-lite-implemented`,
  `spec-lite-abandoned`
- Should NOT treat a spec-lite record as a full-spec with most stages
  missing — that would produce noisy "incomplete" warnings

### `src/speckit_orca/matriarch.py`
- Lane model currently assumes one primary **feature spec** per lane
  (FR-001a from 010)
- Can a spec-lite be a lane anchor? **My lean: no, not in v1.**
  Spec-lite is explicitly lighter than the multi-lane coordination
  matriarch was designed for. If someone needs a lane around a
  spec-lite, they should promote it to a full spec first.
- Simplest runtime rule: matriarch only registers lanes against
  full-spec directories, not against spec-lite records.

### `commands/micro-spec.md`
- Retired. Replaced by `commands/spec-lite.md` in the same wave.
- The prompt rewrite is deferred per user instruction, same as 012.

### `README.md`
- PR #24's four-concept workflow section mentions `micro-spec` under
  intake. After 013 merges, update to `spec-lite`.
- The "Basic Workflow" section mentions `micro-spec` as the smaller-work
  escape hatch. Update to `spec-lite`.

### Existing `micro-spec` records (if any)
- Audit needed: are there any real `micro-spec` records in the repo
  under `.specify/orca/micro-specs/` or elsewhere? If yes, they get
  migrated to the spec-lite shape in the breaking wave. If no, we
  skip the migration step entirely.

### `specs/002-brainstorm-memory/`
- Brainstorms today can link to micro-specs as forward references.
  Update that to point at spec-lites. Small doc change.

## Rollout

**Option A — atomic breaking change (recommended).** Rename the
command, retire the old records and paths, update all references in
one wave. Same as 012's rollout pattern. Lower drift risk.

**Option B — alias `micro-spec` to `spec-lite` for a deprecation window.**
Both names work, one eventually retires. More complexity. Not worth
it unless there's real external usage of `micro-spec`, which there
isn't (Orca hasn't shipped externally).

**Recommendation: Option A.**

## Open questions (to resolve before plan.md)

1. **Storage location** — global registry under
   `.specify/orca/spec-lite/` OR feature-dir-scoped like
   `.specify/orca/spec-lite/<slug>/spec-lite.md`? My lean: global
   registry, one file per record.

2. **Auto-increment ID or slug-based filename?** My lean: `SL-NNN-<slug>`
   matching evolve's `EV-NNN-<slug>` pattern for consistency.

3. **Review participation** — full participation / implicit self-pass
   only / fully optional? My lean: fully optional, operator-chosen,
   flow-state reports `unreviewed` as the default state.

4. **Matriarch lane compatibility** — can a spec-lite anchor a lane?
   My lean: no in v1, promote first if you need a lane.

5. **Audit: existing `micro-spec` records in the repo?** I need to grep
   for them before the plan so I know the migration scope.

6. **Promotion command** — `speckit.orca.spec-lite promote <id>` as
   an explicit command, or just "copy the content manually into a new
   full-spec dir"? My lean: ship the command, because it encodes the
   "spec-lite stays as a history pointer" rule.

7. **Relationship to spec-kit's own lightweight-spec concept.**
   Upstream `github/spec-kit` may have or may add a lightweight spec
   shape. If so, Orca should probably match their vocabulary. Worth
   a quick check during the plan phase.

## Explicit non-goals

- Not replacing the full spec flow. Both shapes coexist.
- Not adding new review gates to spec-lite — explicitly removing
  them from the current micro-spec.
- Not making spec-lite matriarch-addressable in v1.
- Not driving spec-lite with the 009 yolo runner in v1.
- Not building a migration tool unless the audit finds real
  `micro-spec` records to migrate.
- Not changing the `commands/spec-lite.md` prompt in this brainstorm.
  Prompt rewrite happens after the plan lands, same as 012.
- Not bikeshedding naming beyond `spec-lite`. `quick-spec`,
  `mini-spec`, `draft-spec`, `small-spec` are all fine alternatives;
  I'm picking `spec-lite` because it's the clearest "same thing,
  lighter" signal and it was the user's own suggestion earlier.

## Dependencies on other in-flight work

- **PR #23** (deployment-readiness cleanup) — no direct conflict
- **PR #24** (product-surface refinement) — touches README.md basic
  workflow + four-concept sections which name `micro-spec`. 013
  plan lands after #24 merges to avoid conflict; 013 then updates
  those sections to say `spec-lite`.
- **012-review-model** — related but independent. The review
  participation question (open question #3 above) depends on 012's
  shape being clear, but the answer is "opt out" regardless of what
  012 decides, so this brainstorm is not blocked on 012.
- **014-yolo-runtime** — independent. Spec-lite is intentionally
  out of scope for 014's first version.

## Suggested next steps

1. Review this brainstorm and the seven open questions
2. Run the audit: are there any existing `micro-spec` records in the
   repo that need migration?
3. Resolve the open questions
4. Write `specs/013-spec-lite/plan.md` with storage layout, command
   surface, migration path (if any), and explicit file-by-file
   changes
5. Only then rewrite `commands/spec-lite.md` and create templates
