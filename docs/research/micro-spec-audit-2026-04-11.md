# Audit: Existing `micro-spec` Surface (2026-04-11)

**Purpose**: Input for `013-spec-lite` plan. The 013 brainstorm's open
question #5 was *"are there any existing `micro-spec` records in the
repo that need migration?"* — this audit answers that and also maps
every file that references `micro-spec` as vocabulary, so the 013 plan
knows the full rename scope.

**Scope**: Static grep-and-find over the main branch at `4f76a66`.

## 1. Existing records on disk

**Count: 0.**

No files or directories matching `*micro*` exist under `.specify/`.
There are no in-flight `micro-spec` records to migrate, no data to
port, no legacy artifacts to preserve.

**Implication for 013 plan**: skip the migration-tool step entirely.
`013-spec-lite` is a **purely forward-looking** rename. The breaking
change cost is just vocabulary, not data.

## 2. Vocabulary references (16 files)

These are the files that mention `micro-spec` and will need updates
when 013 lands. Grouped by update type:

### Command prompt (retire)

- `commands/micro-spec.md` — 4848 bytes, Apr 8 snapshot. The
  command prompt itself. **Retired** in the 013 breaking wave,
  replaced by `commands/spec-lite.md`. Prompt rewrite is deferred
  per the same rule that governs 012 and 014.

### Command prompts that route to it (update)

- `commands/brainstorm.md` — the brainstorm command recommends
  `micro-spec` as a downstream option for bounded work. Update to
  `spec-lite`.

### Spec vocabulary (update in place)

- `specs/002-brainstorm-memory/contracts/brainstorm-command.md` —
  contract naming `micro-spec` as a routing target. Update to
  `spec-lite`.
- `specs/005-orca-flow-state/brainstorm.md` — historical brainstorm.
  **Leave as-is** (historical record) unless it names an
  operational expectation that's still load-bearing.
- `specs/009-orca-yolo/spec.md` — yolo spec mentions `micro-spec` as
  a valid start artifact for a yolo run. Update to acknowledge both
  `spec-lite` and full spec as start artifacts. (But see note on 009
  scope: 014 yolo runtime intentionally excludes spec-lite in v1, so
  this may be a no-op wording tweak.)
- `specs/009-orca-yolo/brainstorm.md` — historical brainstorm.
  **Leave as-is**.
- `specs/013-spec-lite/brainstorm.md` — the brainstorm proposing the
  rename. Already uses both vocabularies intentionally.

### Repo-level docs (update)

- `README.md` — touched by PR #24's four-concept workflow section.
  Update to `spec-lite` in the same breaking wave. Coordinate with
  013's plan to avoid double-updating.
- `extension.yml` — **verified**: contains a **formal command
  registration** under `commands:` at lines 30-32:
  ```yaml
  - name: "speckit.orca.micro-spec"
    file: "commands/micro-spec.md"
    description: "Canonical micro-spec workflow for bounded work..."
  ```
  Rename touches three things in this file: the top-level
  description at line 7 (mentions "micro-specs" in prose), the
  command `name` field, the `file` path pointer, and the command
  `description` text. All four must change in the same wave or the
  extension will fail to register the new command or silently
  continue registering the old one.
- `src/speckit_orca/assets/speckit-orca-main.sh` — **verified**:
  three user-facing strings reference `micro-spec`:
  - Line 576 (install success banner): lists `micro-spec` in the
    orchestration command summary. Simple rename.
  - Line 624 (help output): lists `.micro-spec` in the dotted
    command name summary. Simple rename.
  - Line 627 (help output flow sketch):
    `"micro-spec → mini-plan → verification-plan → implement → code-review"`.
    **This is not a rename — it needs a rewrite.** That flow
    sketch describes the current ceremonious micro-spec path
    (mini-plan, verification-plan, code-review gate), which is
    exactly what 013 is cutting. The new sketch should reflect
    spec-lite's lighter shape, probably:
    `"spec-lite → implement"` or
    `"spec-lite → implement [→ optional verification]"`.
    Flag this in the 013 plan as a real wording change, not a
    vocabulary substitution.

### Roadmap / design docs (update)

- `docs/orca-roadmap.md` — roadmap narrative mentions `micro-spec`.
  Update to `spec-lite` when 013 ships, same breaking wave as
  README.
- `docs/refinement-reviews/2026-04-11-product-surface.md` — GPT Pro
  refinement review. **Leave as-is** — it is a frozen review
  document by design, not a live spec. The `micro-spec` reference
  there is historical context.
- `docs/worktree-protocol.md` — **verified**: contains a
  load-bearing rules section at lines 402-408 that defines
  micro-spec's worktree and lane behavior:
  ```text
  ### `speckit.orca.micro-spec`

  `micro-spec` should:
  - attach the quicktask record to the active feature when possible
  - avoid creating a new lane unless the work actually requires parallel isolation
  - promote to full spec flow if lane coordination becomes necessary
  ```
  **This is not a rename — it needs a rewrite.** 013's brainstorm
  positions spec-lite as **never anchoring a matriarch lane in v1**
  (promote first if lane coordination is needed). The worktree
  protocol rules for spec-lite should therefore become:
  ```text
  ### `speckit.orca.spec-lite`

  `spec-lite` should:
  - never create a new lane or attach to an existing one
  - operate in the active feature's existing repo context
  - require explicit promotion to a full spec before any
    matriarch lane involvement
  ```
  013's plan must include this section rewrite. It is load-bearing
  behavior, not vocabulary.

### Legacy v1.4 planning docs (leave or archive)

- `docs/orca-v1.4-design.md`
- `docs/orca-v1.4-decisions.md`
- `docs/orca-v1.4-execution-plan.md`

These are the v1.4 planning snapshot docs. **Leave as-is** — they
are a frozen historical record. Adding "(renamed to spec-lite after
013)" as a pointer note would be nice but is not required.

## 3. Summary for 013 plan

| Category | Count | Action |
|---|---|---|
| Existing records to migrate | 0 | None |
| Files to retire | 1 | `commands/micro-spec.md` |
| Files to update vocabulary | ~8-10 | Rename `micro-spec` → `spec-lite` |
| Files to leave frozen | ~5-6 | Historical records, brainstorms, refinement reviews |

The 013 plan's "Rollout" section in the brainstorm proposed atomic
breaking change. This audit confirms that's realistic: there's no
data migration tool needed, the rename is purely vocabulary, and the
update set is bounded to <15 files.

**Recommendation for 013 plan**: group the rename into four
commits (was three — added a fourth for the load-bearing rewrites
uncovered during the verification pass):

1. **Extension registration commit** — update `extension.yml` in
   all four places: top-level description at line 7, command
   `name` at line 30, command `file` path pointer at line 31,
   command `description` at line 32. This is the commit that makes
   the new `speckit.orca.spec-lite` command actually registered.
   Must land as part of the same wave as the new
   `commands/spec-lite.md` file or the extension breaks.

2. **Runtime / prompts commit** — retire `commands/micro-spec.md`,
   create `commands/spec-lite.md`, update `commands/brainstorm.md`
   routing references, update `specs/002-brainstorm-memory/contracts/brainstorm-command.md`.
   Also updates `src/speckit_orca/assets/speckit-orca-main.sh` at
   lines 576 and 624 (simple rename) and **rewrites line 627's
   flow sketch** from the current ceremonious
   `"micro-spec → mini-plan → verification-plan → implement → code-review"`
   to spec-lite's lighter shape. Also rewrites the **load-bearing
   rules section in `docs/worktree-protocol.md` lines 402-408** to
   reflect that spec-lite never creates a lane and must be
   promoted before any lane involvement.

3. **Spec docs commit** — update `specs/009-orca-yolo/spec.md` to
   acknowledge spec-lite as a valid start artifact (or leave the
   reference since 014 runtime excludes spec-lite in v1 anyway).
   Consider this a nearly no-op commit; worth keeping separate
   because it touches 009 and any 009 regression should be easy to
   bisect.

4. **Repo-level docs commit** — update `README.md` four-concept
   workflow section (intake column) and `docs/orca-roadmap.md`
   "micro-spec" mentions. Low risk, pure vocabulary.

Legacy v1.4 design docs and the 2026-04-11 refinement review are
explicitly out of scope.

## Verification pass summary (added 2026-04-11)

Three files originally flagged as "needs a look" have been verified
against main at `4f76a66`. Findings:

- **`extension.yml`**: contains a formal command registration (not
  just vocabulary). Rename touches four fields in this file.
- **`src/speckit_orca/assets/speckit-orca-main.sh`**: contains a
  flow-sketch at line 627 that describes the current ceremonious
  micro-spec path. This is not a rename — it needs a rewrite to
  reflect spec-lite's lighter shape.
- **`docs/worktree-protocol.md`**: contains a load-bearing rules
  section at lines 402-408 defining micro-spec's lane behavior.
  Spec-lite has different lane behavior (never anchors a lane in
  v1), so this section needs a rewrite, not a rename.

The 3-commit rollout proposal has been updated to a 4-commit
proposal with an explicit extension-registration commit separated
out, because the `extension.yml` changes must land atomically with
the new command file to avoid a broken extension state.

## 4. Open question resolved

**013 brainstorm open question #5**: *"Audit — are there existing
micro-spec records in the repo that need migration?"*

**Answer: No records exist. Migration scope is zero.**
