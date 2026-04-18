# Brainstorm: OpenSpec Adapter — Phase 2 of the Multi-SDD Layer

**Feature Branch**: `019-openspec-adapter`
**Created**: 2026-04-16
**Status**: Brainstorm
**Predecessor**: 016-multi-sdd-layer (Phase 1 — landed), PR #62 (Phase 1.5 —
normalized review + worktree types, merged)
**Scope flag**: Phase 2 of the multi-SDD adapter program. Second adapter only.
BMAD and Taskmaster stubs stay Phase 3+.

**Informed by**:

- `specs/016-multi-sdd-layer/brainstorm.md` (1136 lines) — the landscape
  survey and the adapter pattern argument. Especially:
  - The OpenSpec subsection under "Problem" (brainstorm §Problem, the
    OpenSpec bullet describing `openspec/changes/<change>/proposal.md`
    with delta files plus persistent `openspec/specs/` store).
  - The "Deferred to Phase 2" notes under §Sequencing (the 016 plan
    explicitly says Phase 2 is "OpenSpec adapter. Detection, enumeration,
    artifact loading, stage computation via stage-kinds. Read-only.").
  - The "What we harvest from each format → OpenSpec" §, which listed
    delta-spec model, three-field proposal, brownfield-first posture,
    archive-as-first-class as candidates.
  - The fifteen open questions at the end of 016's brainstorm. Five
    of those become actionable now that we have a concrete second
    adapter on the table.
- `specs/016-multi-sdd-layer/spec.md` — specifically FR-012 (stage-kind
  mapping deferred), FR-013 ("Phase 1 MUST NOT add OpenSpec, BMAD, or
  Taskmaster adapters"), and the Assumptions block that explicitly
  permits Phase 2 to restructure `sdd_adapter.py` into a package.
- `specs/016-multi-sdd-layer/plan.md` — read the Research Decisions and
  Design Decisions, in particular:
  - Decision 1: no registry in Phase 1. Phase 2 replaces the
    `_SPEC_KIT_ADAPTER = SpecKitAdapter()` module-level singleton with a
    real registry lookup.
  - Decision 3: Phase 1 omitted `write_review_verdict` and `supports`
    helpers. Phase 2 is the moment to ask whether OpenSpec pressure
    reveals a need.
  - Decision 5: stage-kind abstraction deferred. Phase 2 is the moment.
  - Open Questions: "What is the final stage-kind enum shape?" — on
    the table now.
- `src/speckit_orca/sdd_adapter.py` — 953 lines, containing the ABC,
  dataclasses (including Phase 1.5's `NormalizedReviewEvidence`,
  `NormalizedReviewSpec/Code/Pr`, `NormalizedWorktreeLane`), constants
  (`_SPEC_KIT_FILENAMES`, `_SPEC_KIT_ARTIFACT_NAMES`), and the
  `SpecKitAdapter` concrete implementation.
- `src/speckit_orca/flow_state.py` — the consumer. We care about the
  module-level `_SPEC_KIT_ADAPTER` singleton (line 382), the
  `collect_feature_evidence` function (line 385) that now dispatches
  through it, and the public signatures downstream consumers rely on
  (`FeatureEvidence`, `FlowStateResult`, `compute_flow_state`).
- WebFetch of `fission-ai/openspec` README, `docs/workflows.md`, and
  `docs/commands.md`. The `openspec/project.md` path 404'd so some
  details (front-matter, exact spec.md shape inside a change) are TBC
  against a real fixture repo. See §OpenSpec format essentials for
  what we learned and what we flagged.

---

## 0. Context and Scope

Phase 1 (016) landed a narrow adapter ABC and wired `flow_state`
through a single `SpecKitAdapter` without changing any observable
behavior. Phase 1.5 (PR #62) tightened the adapter boundary: the
adapter no longer hands back `flow_state.ReviewEvidence` or
`flow_state.WorktreeLane` instances — it hands back
`NormalizedReviewEvidence`, `NormalizedReviewSpec`,
`NormalizedReviewCode`, `NormalizedReviewPr`, and
`NormalizedWorktreeLane`, and `SpecKitAdapter.to_feature_evidence`
does the one-way translation back to legacy types at the boundary.
That clean-up was a prerequisite for any second adapter: it means a
new adapter can populate review evidence and worktree lanes without
importing a line of `flow_state`.

Phase 2 (this spec, `019-openspec-adapter`) adds the second real
adapter — `OpenSpecAdapter` — plus the minimum registry infrastructure
to make "two in-tree adapters" a coherent concept. The scope is
deliberately narrow:

**In scope**
- Detection, enumeration, and read-only artifact loading for OpenSpec
  repos.
- A registry that holds at least two adapters and resolves the right
  one for a given repo or path.
- Stage-kind mapping (deferred from Phase 1) — enough to represent
  OpenSpec's `proposal → implement → archive` lifecycle alongside
  spec-kit's nine-stage pipeline without forcing either into the
  other's shape.
- Yolo / matriarch / TUI interaction review: confirm what works
  without change, flag what doesn't, punt what we don't need Phase 2
  to solve.
- Fixture OpenSpec repo under `tests/fixtures/openspec_repo/` with
  enough shape to drive snapshot tests.

**Out of scope (Phase 2)**
- Write support on `OpenSpecAdapter`. No archive operations, no
  spec-merge behavior. If we ever implement archiving or sync from
  Orca, it's a separate spec.
- Cross-format review orchestration. `review-spec`, `review-code`,
  `review-pr` stay spec-kit-pinned. `OpenSpecAdapter.supports(...)`
  returns False for those and we document the gap.
- Yolo runtime against OpenSpec. Either reject cleanly or defer; see
  §Yolo runtime interaction.
- BMAD and Taskmaster adapters. Phase 3+. We design the registry so
  they plug in without another refactor, but we do not build them
  here.
- `orca convert` between formats. Separate spec, not on the table.
- Installer / extension manifest integration for OpenSpec. The
  installer stays spec-kit-first (matches the 016 brainstorm's
  decision).

## 1. Problem Statement — Why Is the Second Adapter Hard?

The 016 brainstorm argued the adapter pattern would pay off even if
no second adapter ever landed, because it named the seam. Phase 1
delivered the seam. Phase 1.5 widened the seam enough that the
adapter owns its own review + worktree types. None of that proves the
interface fits anything but spec-kit.

Phase 2's specific value is that OpenSpec is the semantically most
different format we're likely to ship an adapter for:

- **Directory convention differs**: `openspec/changes/<slug>/` instead
  of `specs/NNN-<slug>/`. No numeric prefix. No padded three-digit
  id. Slug-only identity.
- **Delta-first lifecycle**: a change contains `proposal.md`,
  `design.md`, `tasks.md`, and a `specs/` subdirectory holding
  delta-spec fragments. On archive, those fragments are merged into
  `openspec/specs/` (the persistent current-state store) and the
  change directory is moved to `openspec/changes/archive/
  YYYY-MM-DD-<slug>/`.
- **Review model differs**: OpenSpec reviews the proposal before
  archive. There is no `review-code.md` analog. There is no
  `review-pr.md` analog. There is no clarify session concept, no
  `## Clarifications` block, no `- status: ready-for-pr` verdict
  grammar.
- **Stage vocabulary differs**: `propose → apply → archive` is three
  stages, not nine. `explore`, `continue`, `ff` exist as pre-propose
  or sub-propose steps but do not have a stable on-disk signature.
  There's no separate "plan" stage — `design.md` inside the change
  plays roughly that role but is not always present.
- **Tasks live inside a per-change `tasks.md`** — same filename as
  spec-kit, same markdown checklist shape from what we can tell, but
  the task IDs are not constrained to `T\d+`. OpenSpec's examples in
  the docs use free-form text after the checkbox.
- **Archive is first-class**: spec-kit has no native archive concept;
  retired features just sit in `specs/` forever. OpenSpec explicitly
  moves completed changes out of the active tree. Our adapter has to
  decide whether archived changes are "features" flow-state knows
  about, or whether they're invisible once archived.

The interface we shipped in Phase 1 was designed against spec-kit
alone. Phase 1.5 added Phase-2-shaped types (review and worktree) but
did not prove them against a real second adapter. Phase 2's first
question is: does the current `SddAdapter` shape survive contact with
OpenSpec, or do we need to break it?

Spoiler lean: **the shape mostly survives, with three additive
changes** (new optional method for stage-kind mapping, new registry
module, new optional `supports(...)` helper). See §4 for the
proposal.

## 2. OpenSpec Format Essentials

What we know from the README, workflows doc, and commands doc:

### 2.1 Directory layout

Active change (pre-archive):

```
openspec/
├── changes/
│   └── add-dark-mode/              # slug, no numeric prefix
│       ├── proposal.md             # "why + what changes + technical direction"
│       ├── specs/                  # delta-spec fragments (may be empty early)
│       │   ├── <capability>.md     # one or more delta files, names flexible
│       │   └── ...
│       ├── design.md               # technical approach (analog to our plan.md)
│       └── tasks.md                # checklist (analog to our tasks.md)
└── specs/                          # persistent current-state store
    ├── <capability>/
    │   └── spec.md                 # merged/authoritative spec per capability
    └── ...
```

Archived change (post `/opsx:archive`):

```
openspec/
├── changes/
│   ├── archive/
│   │   └── 2026-01-24-add-dark-mode/
│   │       ├── proposal.md
│   │       ├── specs/
│   │       ├── design.md
│   │       └── tasks.md
│   └── ... (other active changes)
└── specs/
    └── <capability>/
        └── spec.md                 # now includes merged dark-mode delta
```

### 2.2 Files inside a change

- **`proposal.md`**: three conceptual sections — purpose / what
  changes / technical direction. The README calls this the proposal
  and says it carries the three fields. Exact heading text is TBC
  against a real fixture (the `openspec/project.md` path 404'd so we
  can't copy a real file verbatim right now).
- **`specs/`** (inside the change): holds delta-spec fragments. One
  or more `.md` files, filenames flexible. From the workflow doc:
  the directory may be empty during propose and gets populated
  during `/opsx:ff` or `/opsx:continue`. On archive, these deltas are
  merged into `openspec/specs/<capability>/spec.md`.
- **`design.md`**: technical approach. Analog-ish to our `plan.md`.
  Not always present in the early "propose only" state.
- **`tasks.md`**: implementation checklist. Markdown checkboxes.
  Task IDs are not standardized — OpenSpec's docs don't constrain
  them to `T\d+`. Our `SpecKitAdapter._parse_tasks` would not match
  the OpenSpec shape directly.

### 2.3 `openspec/specs/` — the persistent store

- Organized by **capability**, not by feature/change. Each
  capability subdirectory holds a `spec.md`.
- Updated on `/opsx:archive` or `/opsx:sync` — deltas from completed
  changes merge in.
- This is what makes OpenSpec "current-state oriented" vs. spec-kit's
  "one spec per feature forever."

### 2.4 Lifecycle in stages

Per `docs/workflows.md`:

1. **Propose / explore**: `openspec/changes/<slug>/` created.
   `proposal.md` and skeleton files laid down. `specs/` may be empty.
2. **Planning expansion** (`/opsx:ff` or `/opsx:continue`):
   `specs/<capability>.md` delta fragments written, `design.md`
   expanded, `tasks.md` fleshed out.
3. **Implement** (`/opsx:apply`): code changes in the actual source
   tree, `tasks.md` checkboxes ticked. No new files inside the change
   dir.
4. **Verify** (`/opsx:verify`, optional): tooling reads artifacts,
   writes no files, produces a report.
5. **Archive** (`/opsx:archive`): change directory moves to
   `openspec/changes/archive/YYYY-MM-DD-<slug>/`. `openspec/specs/`
   updated with merged deltas.

### 2.5 What's TBC

We did not confirm by reading a real OpenSpec repo's on-disk files:

- Exact heading text inside `proposal.md`.
- Whether `design.md` has a canonical structure or is free-form.
- Whether deltas in the per-change `specs/` use a diff-style format,
  an annotated full-file format, or just "new content to merge."
- Whether there's front-matter (YAML) on any of these files.
- Whether `openspec/` has a top-level config (`.openspecrc`,
  `openspec.json`, etc.) we should look for during detection.

**Mitigation**: the 019 plan will require pulling a real OpenSpec
example repo into `tests/fixtures/openspec_repo/` before we finalize
the parsing regexes. If we build the adapter against the README shape
and find the real files look different, we patch the parser. The
adapter interface is unaffected — only the internal parse is.

## 3. Semantic Misalignment Analysis

The adapter ABC does not care about stage vocabulary today —
`compute_stage` returns an opaque `list[StageProgress]` with adapter-
specific stage names. That's good. The misalignment problem isn't in
the interface; it's in the **consumers** that currently assume
spec-kit stage names.

### 3.1 Where stage names leak

- `flow_state._stage_milestones` (legacy helper, still lives in
  flow_state even after Phase 1) knows about
  `brainstorm / specify / plan / tasks / assign / implement /
  review-spec / review-code / review-pr` literally.
- `flow_state._next_step` hardcodes the ladder.
- `flow_state._derive_ambiguities` knows "plan without spec" is
  weird.
- `matriarch` reads readiness from flow-state output; the readiness
  logic is keyed on spec-kit stage names.
- `yolo` event log records `STAGE_ENTERED(stage="plan")` with
  spec-kit stage names.

Phase 1 did not de-leak the stage names because FR-012 deferred it.
Phase 2 has to decide.

### 3.2 Three options

**Option A — Force OpenSpec into the nine-stage model.**

Map OpenSpec stages onto spec-kit stages:

| OpenSpec state | Spec-kit stage |
|---|---|
| proposal.md exists | `brainstorm` or `specify`? |
| specs/ fragments exist | `specify` |
| design.md exists | `plan` |
| tasks.md has items | `tasks` |
| tasks.md has checked items | `implement` |
| archived | `review-pr`? `complete`? |

Pros: zero change to consumers. Matriarch, yolo, TUI all keep
working on spec-kit stage names.

Cons: lossy and wrong. OpenSpec has no `assign` stage; we fake it.
OpenSpec has no split review (`review-spec` vs `review-code` vs
`review-pr`); we fake one. `archive` is not the same as `review-pr`
semantically but we'd have to pick. The fake stages would show up as
"incomplete" forever and pollute the readiness view.

**Option B — Extend the stage enum to be the union of all formats.**

Add OpenSpec's stages (`proposal`, `apply`, `archive`) to the global
stage list. Each adapter reports its own stages. The enum grows.

Pros: honest.

Cons: every consumer now has to know about every adapter's stages.
Matriarch's readiness logic explodes into per-format branches.
`_next_step` becomes an N-format switch. The stage enum becomes a
soup.

**Option C — Stage kinds (016 brainstorm's original proposal).**

Core defines a fixed small enum of *kinds*: `ideate`, `specify`,
`plan`, `decompose`, `implement`, `review`, `ship`. Adapters map
their native stages onto kinds. Consumers gate on kinds. Adapters
keep their native stage names in a side channel for display.

| OpenSpec stage | Kind |
|---|---|
| propose (proposal.md created) | `ideate` + `specify` |
| planning expansion (design.md + specs/<cap>.md) | `plan` |
| apply (tasks.md checked off) | `decompose` + `implement` |
| verify | `review` |
| archive | `ship` |

| Spec-kit stage | Kind |
|---|---|
| brainstorm | `ideate` |
| specify | `specify` |
| plan | `plan` |
| tasks | `decompose` |
| assign | `decompose` (same kind, different stage) |
| implement | `implement` |
| review-spec / review-code / review-pr | `review` |
| (shipped, retired) | `ship` |

Pros: honest and stable. Consumers operate on a fixed small enum.
Adapters can evolve their native stage lists without breaking
matriarch. New adapters (BMAD, Taskmaster) slot in by mapping their
stages to the same kinds.

Cons: the kind enum itself is a guess; it might not fit BMAD or
Taskmaster cleanly. Multiple native stages collapsing to the same
kind (e.g., spec-kit `tasks` + `assign` both `decompose`) means we
lose fidelity at the kind level.

**Recommendation: Option C.** The 016 brainstorm already proposed it.
Phase 1 punted it because a second adapter wasn't concrete. Now it is.

**How we ship Option C without breaking Phase 1 consumers:**

1. Add a `kind: str` field to `StageProgress`. Default to the stage
   name (so spec-kit can leave it unset and existing code keeps
   working). Enforce the kind enum in Phase 3 when BMAD stress-tests
   it.
2. Add a new optional method on `SddAdapter`:
   `ordered_stage_kinds() -> list[str]` that returns the kind-order
   this adapter supports. Default implementation returns
   `["ideate", "specify", "plan", "decompose", "implement", "review",
   "ship"]` — the full enum in canonical order.
3. `SpecKitAdapter.compute_stage` continues to return the nine native
   stages; each `StageProgress` gets a kind filled in.
4. `OpenSpecAdapter.compute_stage` returns `proposal`, `apply`,
   `archive` (three native stages) each tagged with their kind(s).
5. Consumers that want kind-level readiness iterate
   `normalized.compute_stage()` and group by kind.
6. Consumers that want native stage names still get them (for
   display).

**Open question we leave to the plan**: does `decompose` genuinely
earn its place as a separate kind, or does it collapse into
`implement`? Spec-kit's `tasks` + `assign` stages are both arguably
setup-for-implement. Lean: keep `decompose` separate so the kind enum
can represent "tasks written but nothing implemented yet" distinctly
from "implementing." That distinction matters for matriarch.

### 3.3 What this implies for `NormalizedArtifacts.filenames`

Phase 1 introduced `NormalizedArtifacts.filenames: dict[str, str]`
with semantic keys like `"spec"`, `"plan"`, `"tasks"`,
`"review-code"`. The keys are adapter-agnostic; the values differ per
adapter. OpenSpec will set:

```python
{
    "spec": "specs/",           # directory, not a file — awkward
    "plan": "design.md",
    "tasks": "tasks.md",
    "proposal": "proposal.md",  # new key
    # no "review-spec", "review-code", "review-pr"
}
```

The `"spec"` → directory issue is a real wart. Spec-kit's `spec.md`
is a single file; OpenSpec's "spec" is a directory of delta files
plus the merged `openspec/specs/<capability>/spec.md` store. The
current filenames map assumes file-per-key. Three options:

- Map `"spec"` to the *first* delta file in the change's `specs/`
  dir. Weird and fragile.
- Add a new key `"specs_dir"` and leave `"spec"` absent for
  OpenSpec. Means every consumer that does
  `artifacts.filenames.get("spec")` has to handle None.
- Keep `"spec"` mapped to `"proposal.md"` as the "narrative entry
  point" analog. Loses the distinction between "this is a spec" and
  "this is a proposal," but honest about the role.

Lean: **keep `"spec"` mapped to `"proposal.md"`** because downstream
`next_step` logic uses `filenames["spec"]` to tell the operator "open
this file to continue." Pointing them at `proposal.md` is correct.
Add a separate `"proposal"` key *also* mapped to `"proposal.md"` so
adapters that want the semantic distinction can opt in.

## 4. Proposed Interface Changes

The 016 plan's "Deferred to Phase 2" notes listed:

- Stage-kind enum — §3 above. Additive (`kind` field on
  `StageProgress`, new default method `ordered_stage_kinds`).
- Adapter write surface — not needed for Phase 2 read-only scope.
  Defer again.
- Repo-root detection per-adapter — see §6; yes, we need this.
- Registry to replace the `_SPEC_KIT_ADAPTER` module singleton —
  see §10.

### 4.1 Summary of proposed additive changes

1. **`StageProgress.kind: str`** — new field. Default empty string.
   Spec-kit fills with the kind from the Option C table. OpenSpec
   fills likewise.
2. **`SddAdapter.ordered_stage_kinds() -> list[str]`** — new
   non-abstract method. Default returns the canonical 7-kind list.
3. **`SddAdapter.supports(capability: str) -> bool`** — new
   non-abstract method. Default returns True for spec-kit-historical
   capabilities (`"review-spec"`, `"review-code"`, `"review-pr"`,
   `"worktree-lanes"`, `"brainstorm-memory"`). `OpenSpecAdapter`
   overrides to return False for review split and worktree lanes,
   True for brainstorm memory (brainstorm memory is Orca-native and
   cross-format).
4. **`SddAdapter.repo_root_markers() -> tuple[str, ...]`** — new
   non-abstract method used by the registry. Spec-kit returns
   `(".git", ".specify")`. OpenSpec returns `("openspec",)` — the
   presence of an `openspec/` directory at a repo root is the
   marker.
5. **New `NormalizedArtifacts.filenames` keys**: `"proposal"`,
   `"design"`, `"specs_dir"`. Adapters opt in. Legacy consumers
   ignore unknown keys.
6. **Optional back-compat**: `StageProgress` and `NormalizedArtifacts`
   stay backward-compatible. No existing field renamed or removed.

### 4.2 What we are NOT changing

- `NormalizedReviewEvidence` / `NormalizedReviewSpec/Code/Pr` stay
  spec-kit-shaped. `OpenSpecAdapter` returns a default-constructed
  `NormalizedReviewEvidence` with every `exists=False`. We accept
  that OpenSpec's own review semantics (proposal-level approval
  before archive) are not represented in Orca in Phase 2. See §8.
- `NormalizedWorktreeLane` stays spec-kit-shaped. OpenSpec returns
  `[]`. See §9.
- `NormalizedTask` stays as-is. Task IDs are strings; OpenSpec's
  free-form IDs fit without change.
- The ABC stays binary-compatible: we only *add* non-abstract
  methods. Phase 1 subclasses (namely `SpecKitAdapter`) keep passing
  the ABC check.

### 4.3 Module restructuring

Phase 1's plan explicitly said "Phase 1 has one concrete adapter; a
package for one module is noise. Phase 2 will naturally want to
split when OpenSpec lands — at that moment, refactor to a package
with `base.py`, `spec_kit.py`, `openspec.py`."

We do that now. `src/speckit_orca/sdd_adapter.py` becomes
`src/speckit_orca/sdd_adapter/`:

```
src/speckit_orca/sdd_adapter/
├── __init__.py          # re-exports public surface for back-compat
├── base.py              # ABC + dataclasses
├── spec_kit.py          # SpecKitAdapter + spec-kit constants
├── openspec.py          # OpenSpecAdapter (new)
└── registry.py          # register / resolve_for_repo / resolve_for_path
```

The `__init__.py` re-exports everything Phase 1 code imports:
`SddAdapter`, `FeatureHandle`, `NormalizedArtifacts`,
`NormalizedTask`, `StageProgress`, `NormalizedReviewEvidence`,
`NormalizedReviewSpec`, `NormalizedReviewCode`, `NormalizedReviewPr`,
`NormalizedWorktreeLane`, `SpecKitAdapter`, plus the new
`OpenSpecAdapter` and registry functions. External imports like
`from speckit_orca.sdd_adapter import SpecKitAdapter` keep working.

The T030 anti-leak test from Phase 1 (checks `flow_state.py` has no
spec-kit filename literals) needs a twin that checks `flow_state.py`
has no OpenSpec filename literals either. Same logic, expanded
forbidden list.

## 5. Detection Heuristics

`SddAdapter.detect(repo_root)` returns True if the adapter recognizes
the layout. Phase 1's spec-kit detector looks for
`repo_root / "specs/<feature>/spec.md"`.

### 5.1 OpenSpec detector

The cheap probe is:

```python
def detect(self, repo_root: Path) -> bool:
    openspec_root = Path(repo_root) / "openspec"
    if not openspec_root.is_dir():
        return False
    # An OpenSpec repo has at least one of:
    #   openspec/changes/<slug>/proposal.md
    #   openspec/specs/<capability>/spec.md
    #   openspec/changes/archive/<dated-slug>/proposal.md
    for candidate in (
        openspec_root / "changes",
        openspec_root / "specs",
    ):
        if candidate.is_dir():
            return True
    return False
```

That matches any repo with the `openspec/` marker directory. We could
be stricter and require at least one real change or capability, but
that would miss a fresh repo right after `/opsx:onboard`.

**Mixed repos**: a repo with both `specs/NNN-slug/spec.md` and
`openspec/changes/add-auth/proposal.md` is legal. Both adapters'
`detect()` returns True. The registry holds both. Per-feature
resolution is by path (see §10).

### 5.2 Edge cases

- A repo that has `openspec/` but no `changes/` and no `specs/` (just
  e.g. an `openspec/project.md` config file). We return True on the
  directory presence alone. Strict detectors could reject; we're
  permissive so an operator can run `doctor` on an in-progress repo.
- A repo with a misspelled `OpenSpec/` or `openspec_stuff/`. We only
  match literal `openspec/`. That's fine — OpenSpec's tooling
  creates the literal name.
- A spec-kit repo that happens to have a `docs/openspec/` doc file.
  Our detector only probes the repo root. No conflict.

### 5.3 Detection vs. feature resolution

`detect()` answers "is this repo (at least partially) in format X?"
It does *not* answer "which adapter owns this file?" For that we use
`id_for_path()` per adapter. See §10.

## 6. Feature Identity

What is a "feature" in OpenSpec terms?

**Decision: each *change* is a feature.** `openspec/changes/add-dark-
mode/` is a feature with `feature_id = "add-dark-mode"`. The
`openspec/specs/<capability>/` persistent store is *not* enumerated
as features — it's the merged current-state, not a unit of work.

### 6.1 `FeatureHandle` fields

```python
FeatureHandle(
    feature_id="add-dark-mode",
    display_name="add-dark-mode",
    root_path=Path("/repo/openspec/changes/add-dark-mode").resolve(),
    adapter_name="openspec",
)
```

### 6.2 ID collision risk

`FeatureHandle.id` needs to be unique across adapters. Spec-kit uses
`NNN-slug` shapes (e.g. `019-openspec-adapter`). OpenSpec uses plain
slugs (e.g. `add-dark-mode`). The numeric prefix prevents collision
*in practice* for spec-kit-vs-openspec. But:

- A user could name an OpenSpec change `019-something`. Then
  spec-kit's `019-openspec-adapter` and OpenSpec's `019-something`
  both have ids starting with `019-`. No actual collision (different
  full strings), but visually confusing.
- A user could run both adapters with a change slug that matches a
  spec-kit id suffix (`openspec-adapter` vs `019-openspec-adapter`).
  No collision, different strings.

**Decision: IDs are namespaced by `adapter_name`, not by uniqueness
of `feature_id`.** Any cross-adapter lookup uses `(adapter_name,
feature_id)` as the key. The registry enforces this. Consumers that
care about cross-adapter identity use
`f"{adapter_name}/{feature_id}"` as a display key.

### 6.3 `id_for_path` for OpenSpec

```python
def id_for_path(self, path, repo_root=None):
    resolved = Path(path).resolve()
    root = resolve_repo_root(resolved, repo_root)
    if root is None:
        return None
    changes_root = root / "openspec" / "changes"
    try:
        rel = resolved.relative_to(changes_root)
    except ValueError:
        return None
    parts = rel.parts
    if not parts or parts[0] == "archive":
        # We could return the archived id (parts[1]) for archived changes.
        # v1 decision: archived changes are NOT enumerated by list_features;
        # id_for_path returns None for archive paths so downstream flow_state
        # doesn't try to load them. See §6.4.
        return None
    return parts[0]
```

### 6.4 Archived changes

OpenSpec moves completed changes to
`openspec/changes/archive/2026-01-24-add-dark-mode/`. Are those
"features" we enumerate?

**Decision: no, not in Phase 2.** Rationale:

- Archived changes are terminal. They don't need a flow-state view,
  they don't need matriarch coordination, they don't need yolo.
- Enumerating them pollutes `list_features()` output with a
  potentially huge historical list.
- Their paths (`archive/2026-01-24-add-dark-mode`) embed a date
  prefix that conflicts with the bare-slug convention of active
  changes.

We document this in the adapter docstring and add an explicit skip
in `list_features()`. A future spec could add an "archived view" but
Phase 2 doesn't need it.

### 6.5 Feature identity vs. spec-kit 015 adoption records

Adoption records (015) live at
`.specify/orca/adopted/AR-NNN-slug.md`. They describe pre-Orca code,
not specs in any SDD format. They're adapter-agnostic — the 016
brainstorm confirmed this. An OpenSpec repo can still have adoption
records. The `OpenSpecAdapter` does not own them; the existing
Orca-native adoption logic continues to handle them the same way it
does in a spec-kit repo. Confirmed via `src/speckit_orca/adoption.py`
(UNTOUCHED in 016 plan).

## 7. Task Model

OpenSpec's `tasks.md` is a markdown checkbox list. From the docs,
the exact format inside a real fixture is TBC, but the README and
workflow doc consistently describe "checkboxes the operator ticks
off during apply."

### 7.1 Proposed regex

Spec-kit uses:

```python
r"^- \[(?P<mark>[ xX])\] (?P<task>T\d+)\b(?P<body>.*)$"
```

OpenSpec likely uses:

```python
r"^- \[(?P<mark>[ xX])\] (?P<body>.+)$"
```

Looser — no `T\d+` id constraint. We assign synthetic IDs:
`feature_id#NN` where `NN` is the 1-indexed position in the file. If
OpenSpec repos do use explicit IDs (e.g. `1.`, `1.1`, `T1`), we
detect and use them.

### 7.2 `NormalizedTask` field mapping

| Field | Source in OpenSpec tasks.md |
|---|---|
| `task_id` | explicit ID in line if detected, else synthetic `<slug>#01` |
| `text` | body after the checkbox |
| `completed` | `[x]` or `[X]` |
| `assignee` | `[@handle]` if present, else None |

Same `[@handle]` assignment convention we use in spec-kit. If
OpenSpec repos don't use that convention in practice, `assignee`
stays None and nothing breaks.

### 7.3 Task summary

The legacy `task_summary_data` dict (`total`, `completed`,
`incomplete`, `assigned`, `headings`) maps straight over. OpenSpec's
`tasks.md` may use `##` headings to group tasks by phase — we slugify
headings the same way.

### 7.4 Edge case: subtasks

OpenSpec supports indented subtasks (the docs show nested checkboxes
as a common pattern). Spec-kit doesn't formalize subtasks. For
Phase 2 we flatten: every checkbox line at any indent becomes a task.
Parent-child relationships are lost. If we need hierarchical tasks
later, we add a field to `NormalizedTask` (the 016 brainstorm
already flagged this as a harvest candidate from Taskmaster). Not
needed for Phase 2.

## 8. Review Evidence

OpenSpec reviews the *proposal* before archive. No split into
spec-review / code-review / pr-review. No `review-spec.md` or
`review-code.md` files. The proposal itself is the review target,
and approval is "the proposal got archived" (implicit).

### 8.1 What `OpenSpecAdapter` returns

`NormalizedReviewEvidence` with every sub-evidence `exists=False`:

```python
NormalizedReviewEvidence(
    review_spec=NormalizedReviewSpec(exists=False),
    review_code=NormalizedReviewCode(exists=False),
    review_pr=NormalizedReviewPr(exists=False),
)
```

This is honest: Orca's split-review model does not apply to
OpenSpec. Any flow-state consumer that asks "was review-spec done?"
gets False. Any that asks "is the feature shipped?" gets no signal
from review evidence — they'd have to look at whether the change is
archived.

### 8.2 Is "archived" a review signal?

Arguably yes. An archived OpenSpec change has had its proposal
reviewed (implicitly, because it got archived) and its implementation
verified (`/opsx:verify` step). We could synthesize a
`NormalizedReviewPr(exists=True, verdict="merged")` for archived
changes to keep flow-state's "is this feature done" logic working.

**But** we decided in §6.4 not to enumerate archived changes at all.
So this is moot for Phase 2.

**Punt**: when (if) we add archived-change enumeration, we'd also
want to decide whether to synthesize review evidence for them.
Separate spec.

### 8.3 Declaring the gap explicitly

Two things to do:

1. `OpenSpecAdapter.supports("review-spec")` returns False, and
   likewise for `review-code`, `review-pr`.
2. The adapter's docstring and the adapter catalog (README section
   added in this phase) clearly state the limitation: "OpenSpec's
   native review flow is proposal-level approval before archive.
   Orca's split-review model (`/speckit.review-spec`,
   `.review-code`, `.review-pr`) does not apply. To review an
   OpenSpec change, use OpenSpec's own `/opsx:verify` or whatever
   convention the team has."

### 8.4 Could we build a shim?

A "proposal review" shim would map OpenSpec proposal-level approval
onto Orca review semantics. Imaginary: we sniff for a
`proposal-review.md` sibling file in the change dir, or for
front-matter on the proposal like `status: approved`.

**Decision: no.** OpenSpec does not specify such a file or
front-matter, we'd be inventing a convention on top of a format that
doesn't use it, and the whole point of the adapter is to respect the
source format. Users who want Orca's split review stay on spec-kit.

## 9. Worktree Lanes

Orca's worktree lane concept (lane = `.specify/orca/worktrees/
<lane>.json`) is Orca-native. OpenSpec has no equivalent. The
`.specify/orca/` registry tree is a spec-kit-convention directory
(per the 016 brainstorm, we grandfathered the name) but the records
inside are adapter-agnostic.

### 9.1 What `OpenSpecAdapter._load_worktree_lanes` returns

`[]`. An OpenSpec change isn't tracked by any lane. We don't create
lanes for OpenSpec changes in Phase 2.

### 9.2 Could an operator manually create a lane for an OpenSpec
change?

Probably not usefully. The lane registry keys by `feature` or `id`
fields — if an operator hand-wrote
`.specify/orca/worktrees/openspec-add-dark-mode.json` with
`"feature": "add-dark-mode"`, the `OpenSpecAdapter` could pick it
up. But:

- The semantics of a lane assume sequential stage progression
  (matriarch coordinates stages). OpenSpec's proposal-first flow
  doesn't progress the same way.
- Nothing in Orca's OpenSpec support path expects lanes.

**Decision: `OpenSpecAdapter.supports("worktree-lanes")` returns
False.** Lanes on OpenSpec features are unsupported. If an operator
creates one, we don't error — we just ignore it.

### 9.3 Spec-kit worktree registry and mixed repos

In a mixed repo, the `.specify/orca/worktrees/` registry still works
for spec-kit features. OpenSpec features coexist without touching
the registry. No interaction.

## 10. Registry Model

Phase 1 used a module-level singleton
`_SPEC_KIT_ADAPTER = SpecKitAdapter()` in `flow_state.py`. Phase 2
needs:

- A registry that holds at least two adapters.
- Per-feature resolution (given a path, which adapter?).
- Per-repo resolution (given a repo_root, which adapter(s) detect
  it?).
- Fallback behavior for paths outside any adapter.

### 10.1 Proposed API

`src/speckit_orca/sdd_adapter/registry.py`:

```python
from pathlib import Path
from typing import Iterable

_REGISTRY: list[SddAdapter] = []

def register(adapter: SddAdapter) -> None:
    """Append an adapter to the registry. Idempotent by adapter.name."""

def adapters() -> tuple[SddAdapter, ...]:
    """Immutable snapshot of registered adapters."""

def resolve_for_path(
    path: Path, repo_root: Path | None = None
) -> tuple[SddAdapter, str] | None:
    """Return (adapter, feature_id) that owns path, else None.

    Iterates adapters in registration order; first adapter whose
    id_for_path returns non-None wins.
    """

def resolve_for_repo(repo_root: Path) -> list[SddAdapter]:
    """Return every adapter whose detect() accepts repo_root."""
```

### 10.2 Registration timing

Option 1: adapters register themselves at import time. Downside: the
import order matters; an unused adapter still gets loaded.

Option 2: a central `__init__.py` hook registers the built-ins.

**Decision: Option 2.** `src/speckit_orca/sdd_adapter/__init__.py`
does:

```python
from .registry import register
from .spec_kit import SpecKitAdapter
from .openspec import OpenSpecAdapter

register(SpecKitAdapter())
register(OpenSpecAdapter())
```

Predictable, testable, no import-order fragility. Tests can clear
the registry and register stubs.

### 10.3 How `flow_state` uses the registry

Replace the Phase 1 line:

```python
_SPEC_KIT_ADAPTER = SpecKitAdapter()
```

with (logical equivalent — actual code in the plan):

```python
from .sdd_adapter.registry import resolve_for_path

def collect_feature_evidence(feature_dir, repo_root=None):
    result = resolve_for_path(Path(feature_dir), repo_root)
    if result is None:
        # No adapter claims this path. Fall back to spec-kit behavior
        # (current default) for backward compatibility.
        from .sdd_adapter.spec_kit import SpecKitAdapter
        adapter = SpecKitAdapter()
        handle = adapter.handle_for_feature_dir(...)
    else:
        adapter, feature_id = result
        handle = FeatureHandle(feature_id=feature_id, ...)
    normalized = adapter.load_feature(handle, repo_root=repo_root)
    return adapter.to_feature_evidence(normalized, repo_root=repo_root)
```

Note: `to_feature_evidence` stays spec-kit-specific today. Phase 2
needs `OpenSpecAdapter.to_feature_evidence` as well. `FeatureEvidence`
itself is defined in `flow_state.py` and the boundary translation is
per-adapter; both adapters call into the same downstream
`FeatureEvidence` constructor.

### 10.4 Backward compatibility

`flow_state._SPEC_KIT_ADAPTER` is monkeypatched by Phase 1 tests
(per FR-010 in 016 spec). Phase 2 either:

- Keeps `_SPEC_KIT_ADAPTER` as an alias for
  `registry.adapters()[0]` (tests keep working if they assume
  spec-kit-first registration order). Fragile but backward-compatible.
- Migrates those tests to use the registry API explicitly. Clean.

**Decision: migrate the tests, keep `_SPEC_KIT_ADAPTER` as a
deprecation alias for one release.** Phase 1 tests that monkeypatch
it still work; new tests use `registry.register()` + teardown.

### 10.5 Test harness

Tests that want to install a fake adapter:

```python
from speckit_orca.sdd_adapter import registry

def test_custom_adapter(tmp_path):
    registry._REGISTRY.clear()
    registry.register(FakeAdapter())
    try:
        # ... test ...
    finally:
        # Restore default adapters.
        registry._reset_to_defaults()
```

We add `registry._reset_to_defaults()` as a test helper.

## 11. Mixed-Repo Behavior

A repo with both `specs/NNN-slug/` and `openspec/changes/<slug>/`.
How does Orca behave?

### 11.1 Detection

Both adapters' `detect(repo_root)` return True. `resolve_for_repo`
returns `[SpecKitAdapter(), OpenSpecAdapter()]`.

### 11.2 Feature resolution per path

`resolve_for_path` iterates in registration order. First adapter
whose `id_for_path` returns non-None wins. Since spec-kit registers
first (by our convention) and checks `specs/NNN-slug/` while
OpenSpec checks `openspec/changes/<slug>/`, the two adapters are
mutually exclusive by path. No conflict.

### 11.3 `doctor` output

A mixed repo's `doctor` lists both:

```
Detected SDD formats:
  - spec-kit   (16 features in specs/)
  - openspec   (4 changes in openspec/changes/)
```

### 11.4 `list_features` semantics

Each adapter enumerates its own features. If a consumer wants every
feature across adapters, it iterates `registry.adapters()` and
concatenates. `flow_state` today calls `collect_feature_evidence` on
a specific path, so it doesn't need a global list.

The one caller that wants a global list is matriarch's dashboard
view. We'll handle that in §14.

### 11.5 Is this realistic?

Probably not common but possible. A team adopting OpenSpec on top of
an existing spec-kit history would have both during migration. We
support it because the engineering cost is near-zero (mutually
exclusive path scopes), and the alternative (error on mixed repo) is
hostile to migration.

## 12. Brownfield Interaction

017 brownfield adoption scans a repo for existing code and emits
adoption records under `.specify/orca/adopted/AR-NNN-slug.md`.

### 12.1 Does OpenSpec support adoption records?

Adoption records describe existing *code*, not existing specs. They
are orthogonal to SDD format. An OpenSpec repo can have adoption
records just as easily as a spec-kit repo. The `.specify/orca/` tree
is grandfathered-spec-kit-convention per the 016 brainstorm.

### 12.2 Who creates adoption records in an OpenSpec repo?

The same Orca-native `adoption.py` module creates them. Nothing
adapter-specific.

### 12.3 Could an adoption record point at an OpenSpec change?

Adoption records' `Location` field is a path. That path can be any
directory. An adoption record could point at
`openspec/changes/add-auth/` if someone wanted to adopt that change
as a pre-Orca artifact. Strange use case — OpenSpec changes aren't
code, they're specs — but no mechanism prevents it.

**Flag for human decision**: should adoption records restrict to
"code paths, not spec paths?" Probably yes, but out of scope for 019.

### 12.4 What 017 needs from OpenSpec

Nothing, in Phase 2. The 017 scanner looks at `src/`, `lib/`, etc.
— real code directories. It doesn't scan `specs/` or `openspec/`.

## 13. Yolo Runtime Interaction

014 yolo runtime assumes sequential stage progression per lane.
OpenSpec's `propose → apply → archive` is sequential too, but with
different stage names.

### 13.1 Three options

**(a) OpenSpec features don't run yolo.** Yolo rejects OpenSpec
features at invocation with a clear error: "yolo runtime supports
spec-kit features only. Run OpenSpec's own `/opsx:apply` instead."

**(b) Yolo becomes adapter-aware.** Yolo reads the feature's adapter
and uses that adapter's stage order. Events record `stage_kind`
alongside `stage`.

**(c) Yolo rejects OpenSpec features with a clear error.** Same as
(a), but we make the error message part of the design, not a side
effect of missing support.

**Decision: (c) in Phase 2, move toward (b) in a later phase.**

Rationale:

- Yolo is a significant moving target. 014's runtime is still
  being built (commits 3 days ago in this branch). Adapter-awareness
  on yolo is a large cross-cutting change that would double the
  Phase 2 scope.
- OpenSpec operators already have `/opsx:apply` for driving
  implementation. They don't need yolo on day one.
- Clean rejection is honest and unblocks.

Implementation: when yolo is invoked on a path, it calls
`registry.resolve_for_path(path)`. If the returned adapter's name
is not `"spec-kit"`, yolo errors with:

```
error: yolo runtime only supports spec-kit features in this release.
This path is managed by the '<adapter-name>' adapter. See
`/speckit.orca.doctor` for detected formats.
```

### 13.2 What goes into the plan

The plan's §Implementation Phases explicitly lists a Sub-phase for
yolo integration with one task: "reject non-spec-kit features at
yolo entry with a clear error." Small, scoped.

## 14. TUI Interaction

018 Orca TUI reads `flow_state` output. Phase 1 + 1.5 made sure the
adapter boundary doesn't leak through flow_state's public surface.
If the TUI consumes `FlowStateResult` / `FeatureEvidence` as-is,
Phase 2 shouldn't require TUI changes.

### 14.1 Tracing the data path

1. TUI calls `compute_flow_state(target)`.
2. `compute_flow_state` calls `collect_feature_evidence(feature_dir)`.
3. `collect_feature_evidence` uses the registry to find the adapter.
4. Adapter's `load_feature` returns `NormalizedArtifacts`.
5. Adapter's `to_feature_evidence` returns `FeatureEvidence`.
6. `compute_flow_state` wraps into `FlowStateResult`.
7. TUI renders `FlowStateResult`.

The TUI sees `FeatureEvidence`. `FeatureEvidence` has the same
fields for spec-kit and OpenSpec — only their *values* differ
(filenames map, review evidence mostly False for OpenSpec, worktree
lanes empty, stage names different).

### 14.2 What the TUI might need to handle

- **Stage name display**: if TUI hardcoded stage names like "plan"
  or "review-code" in its layout, OpenSpec's `proposal` / `apply` /
  `archive` will look empty. The TUI should iterate the stages
  returned by the adapter, not hardcode a nine-row layout.
- **Review panel**: if TUI shows a "Review: spec ✓ code ✗ pr ✗"
  tricolor, all three will be empty for OpenSpec. That's honest but
  might look confusing. TUI could check `adapter.supports("review-
  spec")` and hide the row if False.
- **Filenames**: if TUI uses `artifacts.filenames["spec"]` to link
  to the narrative entry point, it gets `proposal.md` for OpenSpec.
  Works.

### 14.3 Decision

Phase 2 does not change the TUI. If the TUI (which is a
newer/in-flight project) has hardcoded stage names, the TUI author
updates as part of 018, not as part of 019. We verify Phase 2
doesn't actively break the TUI — we do not make the TUI OpenSpec-
aware in 019.

**Flag for human decision**: does 018 need a dependency on 019? Or
does 019 just need a smoke test that the TUI still renders
spec-kit features correctly after the registry refactor? Lean: the
latter. 019 owns "spec-kit feature TUI render is unchanged." 018
owns "OpenSpec feature TUI render." Clean split.

## 15. Matriarch Interaction

010 matriarch uses lanes. Lanes are spec-kit-specific (§9.3).
OpenSpec features don't use lanes.

### 15.1 Does matriarch need to change for Phase 2?

Matriarch's core logic (dependency graph, mailbox events, delegated
tasks) is format-agnostic. Its input is flow-state output. If an
OpenSpec feature has no lanes and no split review, matriarch just
sees a feature with limited signal. It doesn't crash; it has less
to coordinate.

**Decision: matriarch stays untouched in Phase 2.** It reads
flow-state-like data, makes decisions based on stage progression,
and spec-kit-only subsystems (yolo, split review) remain
spec-kit-only. If an operator invokes matriarch-specific commands
on an OpenSpec change, they'll either get no-op behavior (nothing
to coordinate) or clean error paths from the underlying commands.

### 15.2 What matriarch might misbehave on

- **Readiness aggregation**: if matriarch checks
  `feature.review_evidence.review_pr.verdict == "merged"` to know
  a feature shipped, OpenSpec features never satisfy this check.
  They appear "in flight forever" from matriarch's POV.
- **Lane-based dependency graphs**: OpenSpec features have no lanes;
  they don't appear in lane-registered coordination.

**Flag**: we'd want a follow-up spec to make matriarch
adapter-aware. Not in Phase 2. Phase 2's exit criterion for
matriarch is "spec-kit matriarch behavior unchanged." If
OpenSpec-specific matriarch matters to users, that's a new spec.

## 16. Test Strategy

### 16.1 Fixture repo

Add `tests/fixtures/openspec_repo/` with a realistic OpenSpec
layout:

```
tests/fixtures/openspec_repo/
├── .git/                     # empty marker dir is fine for tests
├── openspec/
│   ├── changes/
│   │   ├── add-dark-mode/
│   │   │   ├── proposal.md
│   │   │   ├── specs/
│   │   │   │   └── theme.md
│   │   │   ├── design.md
│   │   │   └── tasks.md
│   │   ├── fix-perf/
│   │   │   ├── proposal.md
│   │   │   └── tasks.md          # minimal change, no specs/ yet
│   │   └── archive/
│   │       └── 2026-01-01-old-done/
│   │           ├── proposal.md
│   │           ├── specs/
│   │           ├── design.md
│   │           └── tasks.md
│   └── specs/
│       └── theme/
│           └── spec.md
└── src/                      # empty, just for realism
```

Two active changes (one fully-fledged, one minimal), one archived,
one capability in the persistent store.

### 16.2 Snapshot tests

- `test_openspec_detect` on the fixture returns True.
- `test_openspec_list_features` returns exactly two handles:
  `add-dark-mode` and `fix-perf`. Not the archived one.
- `test_openspec_load_feature` on `add-dark-mode` returns a
  `NormalizedArtifacts` with expected filename map, non-empty tasks,
  `review_evidence` all False, `worktree_lanes` empty.
- `test_openspec_compute_stage` returns three stages
  (`proposal`/`apply`/`archive`) each with the expected kind tag.
- `test_openspec_id_for_path` resolves
  `openspec/changes/add-dark-mode/proposal.md` to
  `"add-dark-mode"`, and `openspec/changes/archive/...` to None.

### 16.3 Parity tests (spec-kit regression)

We add a parity test that runs the spec-kit fixture tree through
the Phase 2 registry and asserts the `FeatureEvidence` output is
byte-identical to Phase 1's golden snapshots. SC-002 from 016 spec
is the spirit here: spec-kit users see zero behavior change in
Phase 2.

### 16.4 Registry tests

- `test_registry_resolves_spec_kit_path` returns
  `(SpecKitAdapter, "019-openspec-adapter")` for
  `specs/019-openspec-adapter/spec.md`.
- `test_registry_resolves_openspec_path` returns
  `(OpenSpecAdapter, "add-dark-mode")` for
  `openspec/changes/add-dark-mode/proposal.md`.
- `test_registry_returns_none_for_unrelated_path` for a path like
  `/tmp/random.md`.
- `test_registry_mixed_repo_detection` — repo with both `specs/`
  and `openspec/` has `resolve_for_repo` return both adapters.
- `test_registry_reset_to_defaults` — reset helper works.

### 16.5 Stage-kind tests

- `test_spec_kit_stage_kinds` — all nine stages have kind assigned
  per the Option C mapping.
- `test_openspec_stage_kinds` — three stages with expected kinds.
- `test_stage_kinds_within_canonical_enum` — every returned kind is
  in `SddAdapter.ordered_stage_kinds()` output.

### 16.6 Anti-leak tests

- Phase 1 T030 had a grep check for spec-kit filename literals in
  `flow_state.py`. We add a twin for OpenSpec filename literals
  (`"proposal.md"`, `"design.md"`, `"openspec"`). Neither spec-kit
  literals nor OpenSpec literals should appear in `flow_state.py`.
- `flow_state.py` should only reference `FeatureHandle`,
  `NormalizedArtifacts`, `FeatureEvidence`, registry functions.

### 16.7 Yolo rejection test

- `test_yolo_rejects_openspec_feature` — invoke yolo entry against
  an OpenSpec path; verify it errors with the documented message.

### 16.8 TUI smoke

Out of scope to implement in 019 if 018 lands later. If 018 has
already landed, we add one smoke test: TUI renders the spec-kit
fixture without change. OpenSpec rendering is 018's problem in its
Phase 2.

## 17. Open Questions

Enumerated for plan-phase decision.

1. **Stage-kind enum final shape**. 7 kinds (`ideate`, `specify`,
   `plan`, `decompose`, `implement`, `review`, `ship`). Does
   `decompose` earn its slot, or does it fold into `implement`?
   Lean: keep it separate. Plan finalizes.

2. **Whether `"spec"` filename key maps to `proposal.md` for
   OpenSpec, or we add a separate `"proposal"` key and leave
   `"spec"` absent**. Lean: both — map `"spec"` to `proposal.md`
   for next-step compatibility AND add `"proposal"` key for
   semantic clarity.

3. **Archived change visibility**. Phase 2 hides them. Is that
   right? Or do we want a `--include-archived` flag on
   `list_features`? Lean: hide, add flag later if needed.

4. **Deprecation of `_SPEC_KIT_ADAPTER` alias**. Keep it one
   release? Drop immediately and fix Phase 1 tests? Lean: one
   release with a deprecation warning.

5. **Matriarch readiness on OpenSpec features**. Does matriarch
   treat OpenSpec features as "ineligible for spec-kit-only
   checks" automatically, or do we need explicit feature gates?
   Lean: silent degradation in Phase 2. Explicit adapter-awareness
   in a follow-up spec.

6. **TUI dependency on 019**. Does 018 wait for 019, or can it
   proceed? Lean: proceed in parallel. 019 adds the registry,
   018 uses it when ready.

7. **Fixture OpenSpec repo origin**. Do we hand-author the fixture
   or clone a real OpenSpec example? Lean: hand-author from the
   README + workflows doc shape, TODO-tag anything we're not sure
   about, patch later if a real OpenSpec example reveals drift.

8. **`design.md` treatment**. We want it to be the "plan" analog.
   But the workflow doc says it's not always present (empty during
   propose). If `design.md` is missing, do we mark `plan` kind as
   incomplete or as N/A? Lean: incomplete.

9. **Task ID synthesis**. Synthetic IDs like `<slug>#01` for
   OpenSpec tasks that lack explicit IDs. Or is a flat integer
   (`1`, `2`, ...) better? Lean: `<slug>#NN` so IDs are unique
   across features.

10. **Capability probe values**. Full list of capability strings
    we recognize: `review-spec`, `review-code`, `review-pr`,
    `worktree-lanes`, `brainstorm-memory`, `yolo-runtime`,
    `task-dag`. Spec-kit returns True for all except
    `task-dag`; OpenSpec returns True only for `brainstorm-
    memory`. Do we codify this list as an enum, or leave as
    loose strings? Lean: loose strings in Phase 2, formalize in
    Phase 3 when BMAD adds new ones.

11. **Does `OpenSpecAdapter` need its own repo-root-marker method
    or do we centralize in the registry?** Lean: per-adapter
    method (§4.1 item 4). Registry calls it.

12. **`handle_for_feature_dir` exists on `SpecKitAdapter` but
    isn't in the ABC.** Phase 2 adds an equivalent to
    `OpenSpecAdapter`. Do we promote it to the ABC? Lean: yes,
    add as optional method with default implementation building a
    handle from the path's basename.

13. **Archive path detection for `id_for_path`**. We skip archived
    paths (return None). But should a path like
    `openspec/changes/archive/2026-01-01-old/proposal.md` return
    a special "archived" sentinel? Lean: no, None is correct —
    flow-state shouldn't try to load an archived change.

14. **Version marker on the adapter interface**. The 016 brainstorm
    question 12 punted this. Phase 2 adds an additive extension;
    do we bump a version? Lean: not yet; version when we break
    compatibility.

15. **Naming**. `SddAdapter.ordered_stage_kinds()` is a mouthful.
    Shorter names: `stage_kinds()`, `kinds()`. Lean: `stage_kinds`.
    Plan finalizes.

## 18. Scope Discipline — What Phase 2 Must NOT Do

Explicitly out of scope for 019. If any of these come up in review,
defer.

- **BMAD or Taskmaster adapters, even as stubs**. They come in
  Phase 3+. The registry we ship must tolerate their addition
  without another refactor, but we don't ship them.
- **Cross-format review orchestration**. `/speckit.review-spec` /
  `-code` / `-pr` remain spec-kit-pinned. Any attempt to
  generalize them is a new spec.
- **OpenSpec write support** (archive, sync, propose). `OpenSpecAdapter`
  is read-only. We don't orchestrate `/opsx:apply` or
  `/opsx:archive`. Those remain OpenSpec's own tools.
- **`orca convert` between formats**. Separate spec if we ever want
  it.
- **Archived change enumeration**. §6.4.
- **Matriarch adapter-awareness**. §15.
- **Yolo adapter-awareness beyond clean rejection**. §13.
- **TUI adapter-awareness**. §14.
- **Installer integration for OpenSpec**. Spec-kit-first stays the
  rule. An OpenSpec operator uses Orca via direct module invocation
  (`uv run python -m speckit_orca.flow_state openspec/changes/<slug>`)
  or via a future spec.
- **`.specify/orca/` rename or relocate**. Grandfathered, stays.
- **Plugin system for third-party adapters**. In-tree only.
- **Changing any Phase 1 public API on `flow_state`**. `FeatureEvidence`,
  `FlowStateResult`, `compute_flow_state` signatures are frozen.
  Additive field growth on `FeatureEvidence.filenames` is allowed;
  field removal or rename is not.
- **Rewriting Phase 1 review parsing logic**. `SpecKitAdapter._parse_
  review_*` stays byte-identical output for spec-kit fixtures.
- **Changing existing test files**. Like Phase 1, Phase 2 adds
  tests; it does not edit existing ones unless the registry
  migration of `_SPEC_KIT_ADAPTER` forces a monkeypatch update (in
  which case we update the minimum necessary).

## 19. Suggested Next Steps

1. **Review this brainstorm.** Resolve the 15 open questions above,
   or triage them into "plan-critical," "plan-punt," "after plan."
2. **Pull a real OpenSpec example repo** into
   `tests/fixtures/openspec_repo/` (or hand-author to the README
   shape with a TODO for real-content validation).
3. **Write `specs/019-openspec-adapter/spec.md`** with functional
   requirements for:
   - `OpenSpecAdapter` detection, enumeration, loading, stage
     computation, id_for_path.
   - Registry API.
   - Stage-kind field on `StageProgress`.
   - `supports(capability)` method.
   - Yolo rejection for non-spec-kit features.
   - Test-parity guarantee for spec-kit.
4. **Write `specs/019-openspec-adapter/plan.md`** with:
   - Module layout (`sdd_adapter/` package).
   - Registry wire-up.
   - Migration of `_SPEC_KIT_ADAPTER` to deprecation alias.
   - Test plan (fixture repo + registry tests + parity gate).
   - Sub-phases mirroring Phase 1's A/B/C/D structure.
5. **Write `specs/019-openspec-adapter/tasks.md`** task-by-task.
6. **Implement** sub-phases. Land registry first (no behavior
   change), then OpenSpec adapter, then yolo rejection, then
   parity verification.

## 20. Risks and Mitigations

### Risk 1: OpenSpec format is moving fast

The `fission-ai/openspec` project is young. File conventions might
change between when we ship and when users adopt it.

**Mitigation**: our parser is narrow (filename probes, checkbox
regex, optional heading heading detection). Changes to OpenSpec's
internal file structure would require parser patches but not
interface changes. Track upstream releases; add a note to the
README adapter section flagging the OpenSpec version we target.

### Risk 2: Stage-kind enum is wrong

Our 7-kind enum is a guess against two formats. BMAD or Taskmaster
may reveal it needs an eighth kind, or some kinds need to split.

**Mitigation**: kinds are extensible by design (adding a kind is
additive). Spec-kit and OpenSpec adapter mappings stay stable.
Phase 3's first job is to stress-test the enum against BMAD.

### Risk 3: Registry migration breaks Phase 1 tests

Phase 1 tests monkeypatch `_SPEC_KIT_ADAPTER`. Moving to
`registry.register()` plus deprecation alias might have subtle test
fallout.

**Mitigation**: keep `_SPEC_KIT_ADAPTER` as a live attribute for one
release. Tests that monkeypatch still work. New tests use registry.
Migration is gradual.

### Risk 4: TUI (018) ends up adapter-aware anyway

If 018 lands before 019 and hardcodes spec-kit stage names, 019 has
to fix 018. Coordination overhead.

**Mitigation**: flag 018 dependency now. Either 018 lands after
019, or 018 authors know the adapter story is coming and defensively
avoid hardcoding stage names. Soft dependency, not a blocker.

### Risk 5: Matriarch readiness silently misbehaves on OpenSpec features

A mixed-repo user might run matriarch and see OpenSpec features
stuck in "incomplete" forever, with no clear explanation.

**Mitigation**: matriarch's dashboard row for an OpenSpec feature
shows `adapter: openspec` tag and a "review model not applicable"
note. Small UX addition, not a matriarch rewrite. If that's too
invasive, we document the limitation in README and defer to a
follow-up.

### Risk 6: Yolo rejection is too blunt

Some operators might want to run yolo on OpenSpec features anyway
and just accept that the stage progression is weird. A hard
rejection is unfriendly.

**Mitigation**: we rarely see a use case where yolo on OpenSpec is
better than `/opsx:apply`. If demand emerges, add
adapter-aware yolo in a follow-up spec. Phase 2 ships the
rejection; it can be softened later.

### Risk 7: We build the OpenSpec adapter and nobody uses OpenSpec

Same risk the 016 brainstorm already acknowledged. The refactor is
additive — Phase 1 and 1.5 already paid for themselves in code
hygiene. Phase 2's OpenSpec adapter specifically might see low
adoption. That's fine; the registry and stage-kind abstraction it
forces us to land are the real deliverables. Even with zero OpenSpec
users, we have:

- a registry that holds N adapters (ready for BMAD/Taskmaster),
- a stage-kind abstraction (ready for any format we want),
- a per-adapter `supports(...)` surface (ready for per-command
  capability gates in future specs),
- a `sdd_adapter/` package structure (ready for adapters to
  multiply without churn).

### Risk 8: Our OpenSpec format understanding is wrong in a way fixture testing can't catch

We wrote this from the README and workflow doc. The real on-disk
shape might differ (front-matter, heading conventions, delta
format).

**Mitigation**: the 019 plan requires at least one test run against
a real OpenSpec example repo (either clone
`fission-ai/openspec`'s own `openspec/` tree or pull one from a
user). If drift is found, patch the parser. The interface and
registry do not depend on the exact file format.

## 21. Summary

Phase 2 adds `OpenSpecAdapter` — the second real SDD adapter — and
the minimum infrastructure to support it: a package-structured
`sdd_adapter/`, a registry, a stage-kind abstraction, a `supports(...)`
capability probe.

The interface survives Phase 2 with three additive changes (kind
field on `StageProgress`, `ordered_stage_kinds` default method,
`supports` default method). No Phase 1 public API changes. Phase 1.5
already moved review evidence and worktree lanes off `flow_state`
internals, so OpenSpec plugs in cleanly.

OpenSpec's semantic differences from spec-kit are real but bounded:
different directory (`openspec/` vs `specs/`), different stages
(three vs nine), no split review, no worktree lanes, no yolo
runtime support. We represent these honestly — empty review
evidence, empty worktree lanes, `supports("review-code")` returns
False, yolo rejects cleanly — rather than faking them onto a
spec-kit-shaped slot.

Scope discipline: BMAD and Taskmaster do NOT land in Phase 2. Yolo
does not become adapter-aware in Phase 2. Matriarch does not become
adapter-aware in Phase 2. TUI does not change in Phase 2. Write
support does not land in Phase 2. `orca convert` does not land in
Phase 2. Installer integration does not land in Phase 2.

What lands: OpenSpec read-only, registry, stage-kind, `supports`,
fixture repo, full test coverage, yolo rejection, matriarch
silent-degradation.

Fifteen open questions enumerated above; most are plan-phase
decisions, none block this brainstorm. Eight risks enumerated, all
have mitigations that scope inside Phase 2.

Next: answer the open questions, pull a real OpenSpec fixture or
hand-author one, write spec + plan + tasks.
