# Plan: Spec-Lite — OpenSpec-Inspired Intake

**Feature Branch**: `013-spec-lite`
**Created**: 2026-04-11
**Status**: Draft
**Brainstorm**: [brainstorm.md](./brainstorm.md)
**Research inputs**:
- [`docs/research/micro-spec-audit-2026-04-11.md`](../../docs/research/micro-spec-audit-2026-04-11.md)
  (migration scope verification and file-by-file rename audit)
- [`docs/refinement-reviews/2026-04-11-product-surface.md`](../../docs/refinement-reviews/2026-04-11-product-surface.md)
  (product-surface origin for making intake feel like an entry layer)

---

## 1. Summary

Rename `micro-spec` to `spec-lite` and cut scope to a five-field
record inspired by OpenSpec's intake philosophy. Drop phase gates,
mandatory verification mode, mandatory code-review handoff, and the
automatic promotion path. If scope grows mid-flight, extend the
spec-lite inline; promote to a full spec only when the operator
decides ceremony is justified.

This is a **breaking change** — the `micro-spec` command and its
associated files are retired and replaced with `spec-lite`. The
migration audit on main confirms **zero existing `micro-spec`
records** exist under `.specify/`, so the migration scope is purely
vocabulary, not data.

## 2. Strawman answers (7 open questions)

The brainstorm captured 7 open questions. This plan answers each
with the lean from the brainstorm, with reasoning. Edit the answers
you disagree with before the contract-writing task starts.

| # | Question | Strawman answer |
|---|---|---|
| 1 | Storage location | **Global registry** under `.specify/orca/spec-lite/` — one file per record. Matches `brainstorm-memory` and `evolve` conventions. |
| 2 | ID scheme | **`SL-NNN-<slug>.md`** — matches evolve's `EV-NNN-<slug>` pattern for consistency and easy mental mapping. |
| 3 | Review participation default | **Opt-out.** Spec-lite's whole point is reduced ceremony; implicit review gates would undo that. Flow-state reports spec-lite records as `unreviewed` by default. Cross-review is still available as an explicit operator command. |
| 4 | Matriarch lane compatibility | **Spec-lite cannot anchor a matriarch lane in v1.** Promote to a full spec first if lane coordination is needed. Matriarch lane registration explicitly rejects spec-lite records. |
| 5 | Existing record audit | **Zero records found.** Verified in `docs/research/micro-spec-audit-2026-04-11.md`. No migration tool needed. |
| 6 | Promotion command | **Ship `speckit.orca.spec-lite promote <id>` as an explicit command.** Preserves the "spec-lite stays as a history pointer" rule and makes promotion auditable. |
| 7 | Upstream spec-kit alignment | **Not tied to upstream.** `github/spec-kit` has no equivalent lightweight-spec concept as of 2026-04-11. If upstream adds one later, revisit the vocabulary then. |

**Question 3 is the most opinionated.** The opt-out default is the
single biggest philosophical difference between `micro-spec` (which
required code-review handoff) and `spec-lite` (which trusts the
operator to decide when a review is worth running). If you want
review to stay mandatory, say so now — it reshapes most of sections
4 and 5.

## 3. Scope

### In scope

- Retire `commands/micro-spec.md` and create `commands/spec-lite.md`
  (prompt rewrite deferred — see Out of scope)
- Define the five-field record shape in a contract file
- Update `extension.yml` to register the new `speckit.orca.spec-lite`
  command and retire the `speckit.orca.micro-spec` registration
- Update `src/speckit_orca/assets/speckit-orca-main.sh` user-facing
  strings (banner line 576, help line 624, **flow sketch line 627
  rewrite**)
- Rewrite `docs/worktree-protocol.md` lines 402-408 rules section
  (not a rename — the rules themselves change because spec-lite has
  different lane behavior)
- Update `commands/brainstorm.md` routing references
- Update `specs/002-brainstorm-memory/contracts/brainstorm-command.md`
  routing target
- Update `specs/009-orca-yolo/spec.md` to acknowledge `spec-lite`
  as a valid start artifact (or leave if 014 runtime excludes
  spec-lite in v1)
- Update `README.md` four-concept workflow "intake" column
- Update `docs/orca-roadmap.md` mentions
- Add `src/speckit_orca/spec_lite.py` runtime module for
  list/create/promote operations (optional — may defer to a
  follow-up if the command prompt can do the work)
- Add flow-state integration so `flow_state.py` understands
  spec-lite records as a distinct feature-state kind
- Add matriarch integration guard so lane registration rejects
  spec-lite records

### Explicitly out of scope

- **Command prompt content rewrites.** The new
  `commands/spec-lite.md` file is created as a stub in this wave,
  with the prompt body rewritten in a separate follow-up task after
  the plan and contracts land. Same deferral rule that governs 012
  and 014.
- Migration of existing `micro-spec` records (zero found on main).
- Integration with the 014 yolo runtime (spec-lite explicitly out
  of scope for 014 v1 per 014 brainstorm).
- Any capability pack that extends spec-lite behavior — out of
  scope for the first version; pack integration points can be
  added later if operators actually toggle behavior.
- Renaming any legacy v1.4 design docs under `docs/`. Historical
  record stays frozen.
- Touching `docs/refinement-reviews/2026-04-11-product-surface.md`
  — frozen review document, historical context only.

## 4. Migration strategy

**Atomic breaking change.** The micro-spec audit on main confirms
zero existing records, so there's no data migration concern. The
rollout is a vocabulary rename plus a small number of load-bearing
rewrites (flow-sketch and worktree-protocol rules), shipped in one
PR.

**No coexistence window.** `micro-spec` and `spec-lite` do not live
side by side. Operators who were about to run `speckit.orca.micro-spec`
after 013 merges will get an error and a clear pointer to `spec-lite`.
The retry is trivial.

## 5. File-by-file change list

Grouped into **4 commits** for reviewability, matching the updated
audit recommendation.

### Commit 1 — Extension registration

- **`extension.yml`** — four changes:
  - Line 7 top-level description: remove "micro-specs" prose
    mention, add "spec-lite" equivalent
  - Line 30 `name`: `speckit.orca.micro-spec` → `speckit.orca.spec-lite`
  - Line 31 `file`: `commands/micro-spec.md` → `commands/spec-lite.md`
  - Line 32 `description`: rewrite to match spec-lite's lighter
    scope (no mention of mini-plan, verification mode, code-review
    gate, promotion rules — those are deliberately gone)

This commit **must land atomically with commit 2** or the extension
breaks: the `file` path points at a file that doesn't exist yet
until commit 2 creates it.

### Commit 2 — Runtime / prompts

- **Retire `commands/micro-spec.md`** (delete)
- **Create `commands/spec-lite.md`** (new file, stub prompt body —
  the full prompt is written in a follow-up task after the plan is
  approved)
- **Update `commands/brainstorm.md`** — replace "recommend micro-spec"
  routing references with "recommend spec-lite"
- **Update `specs/002-brainstorm-memory/contracts/brainstorm-command.md`** —
  replace `micro-spec` in the contract's routing target list with
  `spec-lite`
- **Rewrite `src/speckit_orca/assets/speckit-orca-main.sh`** at
  three locations:
  - Line 576 (install success banner): `micro-spec` → `spec-lite`
  - Line 624 (help output dotted command names): `.micro-spec` →
    `.spec-lite`
  - **Line 627 (flow sketch) — not a rename, a rewrite**. Current:
    `"micro-spec → mini-plan → verification-plan → implement → code-review"`.
    New: `"spec-lite → implement"` or `"spec-lite → implement → optional verification"`.
    The ceremonious path is intentionally gone.
- **Rewrite `docs/worktree-protocol.md` lines 402-408** — load-
  bearing rules section. Current text defines micro-spec's
  "attach to active feature, avoid creating new lane unless
  parallel isolation required, promote to full spec if lane
  coordination needed" behavior. New text defines spec-lite's
  "never create a new lane or attach to an existing one, operate
  in active feature's repo context, require explicit promotion
  before any matriarch lane involvement" behavior. See the audit
  research doc for the exact suggested replacement text.

### Commit 3 — Spec vocabulary update

- **`specs/009-orca-yolo/spec.md`** — scan for `micro-spec`
  references. If 009 names `micro-spec` as a valid start artifact
  for a yolo run, update to `spec-lite` or leave in place
  acknowledging 014 runtime explicitly excludes spec-lite in v1.
  Likely a nearly-noop commit, but keep it separate for bisect
  clarity if 009 regresses.

### Commit 4 — Repo-level docs

- **`README.md`** — four-concept workflow intake column. PR #24
  merged the four-concept layout; update the intake row to name
  `spec-lite` instead of `micro-spec`. Also scan the "Basic
  Workflow" block for any micro-spec mention.
- **`docs/orca-roadmap.md`** — narrative mentions. Replace with
  `spec-lite`.
- **`src/speckit_orca/spec_lite.py`** — NEW runtime module
  (optional, see Open questions below). Provides read/write helpers
  for spec-lite records: `create`, `list`, `get`, `promote`,
  `regenerate-overview`. CLI entrypoint via `python -m speckit_orca.spec_lite`.
- **`src/speckit_orca/flow_state.py`** — add spec-lite as a
  distinct feature-state kind (`spec-lite-open`,
  `spec-lite-implemented`, `spec-lite-abandoned`). Existing
  full-spec feature-state logic is untouched.
- **`src/speckit_orca/matriarch.py`** — add explicit guard in lane
  registration: if the target is a spec-lite record (detected by
  path `.specify/orca/spec-lite/*`), reject with a clear error
  pointing at `spec-lite promote <id>` as the next step.
- **`.specify/orca/spec-lite/00-overview.md`** — bootstrap file
  created as part of this commit so the runtime has a target to
  regenerate against. Matches evolve's `00-overview.md` pattern.
- **`tests/test_spec_lite.py`** — NEW test file covering the
  create/list/get/promote flows and the matriarch lane rejection
  guard.

## 6. The spec-lite record shape

Five fields, four required, one optional. All fields are sections
in a markdown file under `.specify/orca/spec-lite/SL-NNN-<slug>.md`:

```markdown
# Spec-Lite SL-<NNN>: <title>

**Source Name**: <operator or agent that created this>
**Created**: YYYY-MM-DD
**Status**: open | implemented | abandoned
**Promoted To**: (optional — spec id this was promoted to)

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

**Required:** Problem, Solution, Acceptance Scenario, Files Affected.
**Optional:** Verification Evidence (added after implementation).

**No mini-plan, no verification mode enum, no review gates.**
This is the core difference from the current `micro-spec` shape.

## 7. Runtime design

This plan proposes a thin `src/speckit_orca/spec_lite.py` runtime
module matching the shape of `evolve.py` and `brainstorm_memory.py`.
The module is optional — the command prompt could do most of the
work directly without a dedicated runtime module. Including it
makes the tests straightforward and gives flow-state a clean Python
API to consume.

### Core functions

```python
def create_record(
    *,
    repo_root: Path,
    title: str,
    problem: str,
    solution: str,
    acceptance: str,
    files_affected: list[str],
    source_name: str = "operator",
    date: str | None = None,
) -> SpecLiteRecord: ...

def list_records(
    *,
    repo_root: Path,
    status: str | None = None,
) -> list[SpecLiteRecord]: ...

def get_record(
    *,
    repo_root: Path,
    record_id: str,
) -> SpecLiteRecord: ...

def promote_record(
    *,
    repo_root: Path,
    record_id: str,
    target_spec_id: str,
) -> dict[str, Any]: ...

def regenerate_overview(repo_root: Path) -> Path: ...
```

### CLI surface

```bash
uv run python -m speckit_orca.spec_lite --root . list
uv run python -m speckit_orca.spec_lite --root . create \
    --title "..." --problem "..." --solution "..." \
    --acceptance "..." --files-affected "path1,path2"
uv run python -m speckit_orca.spec_lite --root . get SL-001
uv run python -m speckit_orca.spec_lite --root . promote SL-001 \
    --target 015-new-feature
uv run python -m speckit_orca.spec_lite --root . regenerate-overview
```

The CLI mirrors `evolve.py`'s shape for consistency. Command
prompts call this CLI via bash, same pattern as existing Orca
runtime integration.

## 8. Flow-state integration

`src/speckit_orca/flow_state.py` learns a new feature-state kind:
**spec-lite**. When flow-state is asked about a feature directory
that looks like a spec-lite record (either by path under
`.specify/orca/spec-lite/` or by file shape), it returns a shorter
result:

```python
{
  "kind": "spec-lite",
  "id": "SL-001",
  "title": "...",
  "status": "open" | "implemented" | "abandoned",
  "files_affected": [...],
  "promoted_to": None | "NNN-name",
  "review_state": "unreviewed" | "self-reviewed" | "cross-reviewed",
}
```

Flow-state's existing full-spec output shape is **untouched**.
Spec-lite records do not try to fit into the stage model — they
either are or aren't implemented, and if the operator opted into a
review, flow-state reports that too.

The `review_state` field defaults to `unreviewed` (per the opt-out
default from question 3) and flips to `self-reviewed` or
`cross-reviewed` only if a review artifact is present in the same
record directory or a parent feature directory.

## 9. Matriarch guard

`src/speckit_orca/matriarch.py` gets a small explicit rejection at
lane registration time:

```python
def register_lane(*, spec_id: str, ...) -> LaneRecord:
    spec_path = _feature_dir(paths, spec_id)
    if _is_spec_lite_record(spec_path):
        raise MatriarchError(
            f"Cannot register lane for spec-lite record {spec_id!r}. "
            f"Spec-lite does not participate in matriarch lanes in v1. "
            f"Run `speckit.orca.spec-lite promote {spec_id}` to convert "
            f"to a full spec before lane registration."
        )
    ...
```

The `_is_spec_lite_record` helper checks both the path prefix
(`.specify/orca/spec-lite/`) and, as a fallback, scans the file for
the `# Spec-Lite SL-` header marker.

## 10. Testing approach

### Unit tests — `tests/test_spec_lite.py`

- Create a record with all required fields, verify file shape
- Create with missing required field, verify rejection
- List records by status
- Get a record by id, verify all fields parsed
- Promote a record, verify the new spec dir is created and the
  spec-lite record gains a `Promoted To:` field
- Regenerate overview, verify the index reflects current state
- Malformed record, verify safe parse failure

### Integration tests — new in `tests/test_flow_state_spec_lite.py`

- Flow-state against a spec-lite record returns the new kind shape
- Flow-state against a full spec directory still returns the old
  shape (regression check)
- Flow-state against a mixed directory (both spec-lite records and
  full spec dirs) reports each correctly

### Matriarch guard tests — in existing `tests/test_matriarch.py`

- Registering a lane against a spec-lite record raises
  `MatriarchError` with the expected message
- Registering a lane against a promoted record (after the record's
  `Promoted To:` field is set) works against the target spec

### Manual verification

- Create a spec-lite, implement the change, mark `Status: implemented`,
  verify `spec-lite list` shows it
- Create another, promote to a full spec mid-flight, verify the
  record becomes a history pointer

## 11. Dependencies and sequencing

### Hard prerequisites (already satisfied)

- **PR #28** (research notes) — MERGED. Audit findings available.
- **PR #29** (012 plan) — MERGED. Review vocabulary defined.

### Soft prerequisites

- 012 contracts — not strictly required for 013 because 013 opts
  spec-lite out of reviews, but 013's review-participation default
  should reference 012's vocabulary once contracts land.

### What 013 blocks

- Nothing. 013 is an intake-layer change that does not gate other
  work. Ships independently.

### What 013 does not block

- 012 contracts and runtime — independent
- 014 runtime — spec-lite is explicitly excluded from 014 v1
- Any future capability pack work

### Suggested order relative to 012 and 014

1. **013 plan** (this doc) → reviewed
2. **013 contracts** (follow-up task) → reviewed
3. **013 implementation wave** — 4 commits, one PR, atomic breaking
   change
4. **013 command prompt rewrite** — separate PR after contracts,
   same deferral rule as 012 and 014

013 can ship independently of 012 contracts and 014 runtime. It
does not need to wait for them.

## 12. Success criteria

- `commands/micro-spec.md` is retired (deleted)
- `commands/spec-lite.md` exists and is registered in `extension.yml`
- `extension.yml` no longer registers `speckit.orca.micro-spec`
- `speckit-orca-main.sh` help and banner strings say `spec-lite`
  and the flow sketch reflects the lighter shape (no mini-plan,
  no verification-plan, no code-review gate in the sketch)
- `docs/worktree-protocol.md` rules section reflects spec-lite's
  "never anchor a lane in v1" behavior
- `flow_state.py` reports spec-lite records as a distinct kind
  without breaking the existing full-spec path
- `matriarch.py` rejects lane registration against spec-lite
  records with a clear pointer at the promote command
- Zero references to `micro-spec` as a current command anywhere in
  runtime code, command prompts, extension manifest, or README
  (grep-verifiable)
- Historical references in frozen docs (refinement review, v1.4
  design docs) are left untouched
- All 45+ existing tests still pass
- New tests cover create/list/get/promote, flow-state reporting,
  and the matriarch guard

## 13. Explicit non-goals

- Not preserving backward compatibility with `micro-spec` command
  name — breaking change
- Not migrating data from `micro-spec` records (zero exist)
- Not supporting spec-lite as a yolo start artifact in v1
- Not supporting spec-lite as a matriarch lane anchor in v1
- Not making spec-lite review-mandatory (opt-out is the default)
- Not adding any phase gates to spec-lite
- Not rewriting `commands/spec-lite.md` prompt content in this
  plan (deferred)
- Not touching legacy v1.4 design docs or the refinement review
- Not coordinating with an upstream `github/spec-kit` lightweight-
  spec concept (none exists as of 2026-04-11)

## 14. Open questions for the contract-writing task

These surface during plan drafting but are properly answered
during the contract-writing task, not now:

1. **Record schema**: YAML frontmatter + markdown body, or pure
   markdown with strict section naming? My lean: pure markdown
   with strict section naming — matches evolve and
   brainstorm-memory conventions.
2. **`_is_spec_lite_record` detection**: path prefix only, or also
   header scan? My lean: both — path prefix first, header fallback
   for any record that ends up outside the canonical dir.
3. **Promotion command output**: does `promote SL-NNN --target 015-name`
   create the target spec skeleton, or require it to exist first?
   My lean: require the target to exist (operator runs
   `specify init` or equivalent first), because spec-lite's rule
   is "promote only when the full spec is justified" — the
   operator should have already decided to create the target.
4. **Overview regeneration frequency**: automatic on every write,
   or explicit via the `regenerate-overview` command? My lean:
   automatic, matching evolve's pattern.

## 15. Suggested next steps

1. You react to the seven strawman answers in section 2. Edit any
   you disagree with.
2. You react to the four contract-writing open questions in
   section 14.
3. Merge this plan PR.
4. Start the contract-writing task:
   - `specs/013-spec-lite/contracts/spec-lite-record.md` (the five-
     field shape)
   - `specs/013-spec-lite/contracts/promotion.md` (promote command
     contract, including "stays as history pointer" rule)
   - `specs/013-spec-lite/contracts/matriarch-guard.md` (the
     lane-registration rejection)
   - `specs/013-spec-lite/data-model.md`
   - `specs/013-spec-lite/quickstart.md`
5. Implementation wave (4 commits, one PR).
6. Command prompt rewrite for `commands/spec-lite.md` (separate PR).
