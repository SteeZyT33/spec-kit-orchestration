# Brainstorm: Multi-SDD Layer — Orca as a Format-Agnostic Workflow Layer

**Feature Branch**: `016-multi-sdd-layer`
**Created**: 2026-04-16
**Status**: Brainstorm
**Informed by**:

- Survey of the SDD tooling landscape in Q1 2026: GitHub `spec-kit`
  (our current substrate), `@fission-ai/openspec` (three-field
  proposals, delta-spec model, brownfield-first), BMAD-METHOD
  (agile-flavored SDD with story/sprint primitives), and
  `taskmaster-ai` (task-graph-driven, PRD-to-task decomposition).
- `specs/005-orca-flow-state/spec.md` — flow-state is the per-feature
  aggregator and the most obvious place where assumptions about
  spec-kit paths, filenames, and review conventions are baked in.
- `specs/015-brownfield-adoption/brainstorm.md` — precedent for how
  this repo structures brainstorms, and the starting point for a
  brownfield-friendly Orca. 015 answered "what about existing code
  in *this* repo format?"; 016 asks "what about *other* repo formats
  entirely?"
- `src/speckit_orca/flow_state.py` — current interpreter. Hard-codes
  `specs/NNN-feature/{spec,plan,tasks,review-*}.md` as ground truth
  and derives stage progress from literal file existence. Any
  multi-format story has to reckon with this file first.
- `extension.yml` command surface — `brainstorm`, `spec-lite`,
  `adopt`, `review-spec`, `review-code`, `review-pr`, `assign`,
  `matriarch`, `yolo`. Each command carries implicit format
  assumptions that have to either generalize or stay pinned.
- User memory: `project_brownfield_adoption.md` noted OpenSpec's
  brownfield posture as a real adoption gap. 015 closed the gap
  *inside* spec-kit; 016 closes it *across formats*.

---

## Problem

Orca is marketed as "an operating layer on top of Spec Kit." The
hidden word is *only*. Every durable primitive — flow-state,
matriarch, yolo, review artifacts, brainstorm memory, context
handoffs, capability packs — assumes one specific on-disk shape:

- Features live at `specs/NNN-feature-name/`.
- A feature has (at minimum) `spec.md`, usually `plan.md`, sometimes
  `tasks.md`, and optionally `review-spec.md`, `review-code.md`,
  `review-pr.md`.
- Stage progression is a linear nine-step chain
  (`brainstorm → specify → plan → tasks → assign → implement →
  review-spec → review-code → review-pr`), codified in
  `flow_state.STAGE_ORDER`.
- Review verdicts use a fixed enum
  (`ready` / `needs-revision` / `blocked`,
  `ready-for-pr` / `needs-fixes` / `blocked`,
  `merged` / `pending-merge` / `reverted`).
- Tasks use GitHub-flavored markdown checkboxes with `T\d+` IDs.
- The registry for non-feature records (brainstorms, spec-lite,
  adopted, handoffs, yolo runs, evolve, worktrees) is
  `.specify/orca/*`.

This is fine if everybody uses spec-kit. They don't. The SDD space
has fragmented fast:

- **OpenSpec** (`@fission-ai/openspec`) — three-field proposals
  (`Why / What Changes / Impact`), delta-specs that describe
  *changes* rather than full replacements, an explicit `archive/`
  layer, explicit brownfield-first posture. Repos look like
  `openspec/changes/<change>/proposal.md` with delta files beside,
  plus a persistent `openspec/specs/` current-state store that deltas
  merge into. Completely different directory convention from
  spec-kit.
- **BMAD-METHOD** — agile-flavored, uses `docs/prd.md`,
  `docs/architecture.md`, sharded `docs/epics/epic-N.md` and
  `docs/stories/S-N.md`. Stories carry `status`, `acceptance`,
  `tasks`, and are driven through dev/QA cycles by named agents.
  Matches the Scrum/XP vocabulary.
- **Taskmaster** (`taskmaster-ai`) — PRD document parsed into a task
  graph, stored as JSON (`.taskmaster/tasks/tasks.json`), with
  dependency edges, priorities, and sub-tasks. Not markdown-first;
  the task graph is the unit of truth.
- **spec-kit** — our current native. `specs/NNN-feature/...`.

A user who already runs OpenSpec, BMAD, or Taskmaster has no
low-friction path to adopt Orca. They'd have to either
(a) abandon their existing conventions and re-author everything as
spec-kit, or (b) run Orca in parallel and maintain two sets of
artifacts. Both are dealbreakers.

More pointedly: Orca's *value* is in the operating layer — durable
brainstorm memory, split review artifacts, flow-state aggregation,
matriarch lane supervision, yolo runner, capability packs. None of
that value is inherently tied to spec-kit's directory layout. It's
tied to spec-kit's *semantics* (idea → spec → plan → tasks →
implement → review), which other SDD formats also have, just
expressed in different file shapes.

So Orca has two possible futures:

1. **Stay a spec-kit-only tool.** Accept the ceiling. Users of other
   SDD formats are not customers. Fine if spec-kit wins the format
   war. Risky if OpenSpec or BMAD gain market share.
2. **Become a layer.** Let Orca operate over any SDD format that can
   expose the right primitives through an adapter. The commands,
   primitives, and operating semantics stay constant; only the
   format-specific I/O varies.

This brainstorm argues for option 2, and proposes how to build it
without breaking the existing spec-kit experience.

### Why now

- **Market pressure.** OpenSpec is small but growing (`@fission-ai`
  has real shipping velocity). Taskmaster has real usage in the
  Cursor/Windsurf ecosystem. Not urgent, but the longer we wait,
  the more format-specific assumptions calcify.
- **015 created the template.** 015 showed that introducing a new
  artifact kind (adoption records) requires touching flow-state,
  matriarch, and the README intake section. If we do 016 now, we
  land the adapter layer *before* the 015 implementation ossifies
  into another spec-kit-only primitive.
- **Flow-state is still the only real aggregator.** Matriarch and
  yolo read flow-state's output. If we adapter-ify flow-state first,
  matriarch and yolo come along for free (modulo contract cleanup).
  Wait six months and two or three more subsystems will bake in
  spec-kit assumptions independently.
- **The wrapper-capability candidates (evolve) are unbuilt.** We have
  room to design the wrapper-capability layer so it composes with
  the adapter layer, instead of discovering the conflict post-hoc.

### Why this is hard

- **Semantic misalignment, not syntactic.** OpenSpec's delta-spec
  model fundamentally disagrees with spec-kit's full-spec-per-feature
  model. BMAD's story/sprint hierarchy doesn't cleanly map to
  spec-kit's nine stages. Taskmaster's task graph has no stage
  concept at all. An adapter can't just rename paths — it has to
  reconcile different ontologies.
- **Some Orca primitives *are* format-specific.** Review artifacts
  (`review-spec.md`, `review-code.md`, `review-pr.md`) were designed
  around spec-kit's linear stages. They don't obviously carry over
  to OpenSpec's delta model or BMAD's per-story review.
- **Matriarch assumes one lane = one feature directory.** What's a
  lane when the feature is three OpenSpec delta-specs that share a
  proposal, or one BMAD epic with seven stories?
- **There are more than three formats.** Kiro, Agent-OS, Cursor's
  `.cursorrules`-driven SDD, Windsurf's cascade — the space is not
  four items, it's a long tail. We need an architecture that
  tolerates growth without constant core rewrites.

## Proposed Approach: SDD Format Adapter Pattern

**Ship a thin adapter interface.** Orca's core commands, primitives,
and persistent state stay format-agnostic. Per-format adapters
translate between "what's on disk in format X" and "Orca's internal
semantic model."

### Design principles

1. **Orca's semantic model is the stable contract.** The internal
   model is richer than any single format and tolerant of gaps. An
   adapter maps its format into this model, filling defaults where
   the format doesn't carry a concept.
2. **Adapters don't own semantics, they own I/O.** An adapter reads
   and writes artifact files. It does not decide what a stage is,
   what a review verdict means, or how matriarch coordinates lanes.
   Those live in Orca core.
3. **spec-kit is the reference adapter.** The spec-kit adapter is
   the simplest — it's essentially a rename of the current
   hardcoded paths. Building it first forces the interface to match
   reality. OpenSpec/BMAD/Taskmaster adapters come after.
4. **Format detection, not format configuration.** We auto-detect
   the format by looking at the repo layout. A user shouldn't have
   to set `orca.format = openspec` in a config file — Orca should
   see `openspec/changes/` and infer. Manual override is available
   via config for ambiguous cases.
5. **Multi-format in one repo is allowed but discouraged.** If a repo
   has both `specs/` and `openspec/`, each adapter scopes to its
   own directory. Orca reports both. We don't try to unify them.
6. **Native format can be native.** The spec-kit adapter doesn't
   have to be the slowest path. Core can keep spec-kit fast-paths
   for the common case; the adapter interface just formalizes the
   contract.

### Why adapter and not plugin

A plugin system (third parties write adapters, load them at runtime,
register via some protocol) is the "right" long-term answer. It's
also an enormous scope increase and a support nightmare in v1. The
Orca surface doesn't yet have the install/runtime story for dynamic
plugins (no `.so` loading, no Python entrypoint discovery, no
sandboxing). Plugins imply a stable public ABI, versioning policy,
and documentation burden that doesn't match Orca's current
maturity.

**v1 decision: adapters ship in-tree.** Every supported format is a
Python module inside `src/speckit_orca/adapters/<format>/`. Adding a
new format is a PR to this repo. We revisit plugin loading in v2 or
v3 when the in-tree adapters have stabilized and real demand for
third-party adapters materializes.

### Why not a config-driven schema

OpenSpec-style "write a YAML describing your format and we'll parse
it" is attractive but brittle. SDD formats encode workflow
*semantics*, not just file layouts. Delta-specs vs. full specs,
story/epic vs. feature-directory, task-graph vs. checkbox-list —
these are structural differences that need code to handle correctly.
A schema file would have to embed enough Turing-complete mapping
logic that it becomes a DSL, at which point we've built a bad
programming language instead of using Python.

**v1 decision: adapters are Python code.** Small Python modules.
Not config files.

## What Orca currently assumes about spec-kit

Before we can build an adapter layer, we need a ruthless audit of
every place spec-kit specifics leak into Orca's core. Findings from
reading `flow_state.py` and the extension manifest:

### Path assumptions

- **Feature directory shape**: `specs/NNN-feature-name/`. NNN is a
  zero-padded three-digit integer. Slug is `lower-kebab`.
- **Canonical artifact filenames**: `brainstorm.md`, `spec.md`,
  `plan.md`, `tasks.md`, `review-spec.md`, `review-code.md`,
  `review-pr.md`. Hardcoded in `collect_feature_evidence`:
  ```python
  artifacts = {
      name: feature_path / name
      for name in ("brainstorm.md", "spec.md", "plan.md", "tasks.md",
                   "review-spec.md", "review-code.md", "review-pr.md")
  }
  ```
- **Registry paths**: `.specify/orca/brainstorms/`, `.specify/orca/spec-lite/`,
  `.specify/orca/adopted/`, `.specify/orca/handoffs/`,
  `.specify/orca/yolo/runs/`, `.specify/orca/worktrees/`,
  `.specify/orca/evolve/`, `.specify/orca/flow-state/`.
- **Repo root detection**: looks for `.git` OR `.specify/` as the
  signal. Works for spec-kit-native. Would need per-adapter root
  detection for OpenSpec/BMAD/Taskmaster.

### File shape assumptions

- **Tasks parsing**: expects GitHub-flavored markdown checkboxes
  with `T\d+` task IDs. `TASK_LINE_RE = re.compile(r"^- \[(?P<mark>[ xX])\] (?P<task>T\d+)\b...")`.
  Taskmaster stores tasks as JSON, BMAD stores them per-story in
  narrative prose plus a checklist, OpenSpec doesn't have tasks at
  all at the spec level.
- **Review verdict parsing**: `_extract_verdict` scans for
  `^- status:\s*(.+)$`. Review verdicts use three specific enum sets
  (`REVIEW_SPEC_VERDICT_VALUES`, etc.). Hardcoded to three review
  artifact files.
- **Clarify session parsing**: looks for `^## Clarifications` and
  `^### Session (\d{4}-\d{2}-\d{2})\b`. Completely spec-kit-specific
  convention.
- **Assignment parsing**: `\[@[^\]]+\]` — looks for `[@agent-name]`
  in task body. spec-kit convention.
- **Spec-lite filename**: `SL-\d{3}(?:-<slug>)?.md`. Header:
  `# Spec-Lite SL-\d{3}:\s+.+$`.
- **Adoption record filename**: `AR-\d{3}(?:-<slug>)?.md`. Header:
  `# Adoption Record: AR-\d{3}:\s+.+$`.

### Stage model assumptions

- **Canonical nine-stage pipeline** (`STAGE_ORDER`). Stages are
  hardcoded. There is no concept of "this format has different
  stages." The stage kind enum (`meta` / `build` / `review`) is
  also hardcoded.
- **Stage-to-artifact mapping**: `brainstorm` → `brainstorm.md`,
  `specify` → `spec.md`, etc. Inverting the map from artifact to
  stage is baked into `_stage_milestones`.
- **Next-step logic**: `_next_step` is a hardcoded ladder of
  spec-kit stage transitions. Completely format-specific.
- **Ambiguity detection**: detects skipped stages (plan without spec,
  tasks without plan) — which presupposes the linear spec-kit stage
  model.

### Review model assumptions

- **Three review artifacts**: review-spec, review-code, review-pr.
  Hardcoded in `REVIEW_ARTIFACT_NAMES`.
- **Verdict enums per artifact**: each review artifact has a
  specific set of valid verdicts.
- **Self+cross passes are spec-kit-native**: `^## (.+?) Self Pass`
  and `^## (.+?) Cross Pass` are spec-kit's 012-review-model shape.
  Other formats review differently or don't distinguish self/cross.

### Worktree and lane assumptions

- **Worktree metadata**: `.specify/orca/worktrees/registry.json` plus
  per-lane `.specify/orca/worktrees/<lane>.json`. Lanes are
  identified by `feature` key matching `specs/NNN-feature-name/`'s
  ID. spec-kit-specific.
- **Feature ID format**: `NNN-slug`. Yolo runs look up features by
  this shape.

### Brainstorm memory assumptions

- **Linked brainstorm discovery**: `_find_linked_brainstorms` scans
  `repo_root / "brainstorm"` (the legacy dir) for references to
  `specs/{feature_id}/`. spec-kit directory convention baked in.
- **In-feature brainstorm**: `feature_dir / "brainstorm.md"` is the
  current convention; legacy `brainstorm/` references are the prior
  convention. Both are spec-kit-world.

### Yolo runtime assumptions

- **Event log path**: `.specify/orca/yolo/runs/<run_id>/events.jsonl`.
- **RUN_STARTED event carries `feature_id`** in spec-kit shape
  (`NNN-slug`). Matching runs to features assumes that format.
- **Stage names in events**: match `STAGE_ORDER` verbatim. Yolo has
  no concept of "the stage model depends on the adapter."

### Summary

Nearly every code path in `flow_state.py` is spec-kit-flavored. The
file is ~1250 lines; I estimate 70% of it is format-specific and
needs to either move behind an adapter interface or become
format-agnostic by generalizing the concepts it encodes.

## Adapter Interface Shape

The adapter is a Python class (or module) that implements a fixed
set of methods. Below is a first-draft shape — names will change in
the plan phase, but the structural shape is what matters.

### Core responsibilities

An adapter must provide:

1. **Detection**: is this repo in my format?
2. **Enumeration**: what features exist?
3. **Artifact resolution**: given a feature ID, where do its
   artifacts live?
4. **Stage computation**: given the feature's artifacts, what stage
   is it at?
5. **Review evidence**: what review artifacts exist, and what do
   they say?
6. **Task parsing**: what tasks exist and what's their status?
7. **Format-native IDs**: what does a feature ID look like in this
   format?

Adapters do *not* provide:

- Coordination logic (matriarch owns it)
- Brainstorm memory storage (registry stays centralized under
  `.specify/orca/`)
- Review orchestration (review commands own it)
- Yolo runtime (runtime is format-agnostic; adapter just knows how
  to read/write feature-level artifacts)

### Draft interface

```python
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass

@dataclass
class FeatureHandle:
    """Opaque handle for a feature in adapter-specific terms."""
    feature_id: str                # format-native ID
    display_name: str              # human-readable label
    root_path: Path                # where the feature's artifacts live
    adapter_name: str              # which adapter owns this feature

@dataclass
class NormalizedArtifacts:
    """Orca's internal canonical view of a feature's artifacts."""
    feature_id: str
    spec_text: str | None          # narrative spec content
    plan_text: str | None          # narrative plan content
    tasks: list[NormalizedTask]    # canonical task list
    review_evidence: NormalizedReviewEvidence
    raw_artifacts: dict[str, Path] # path map for debug/trace
    native_metadata: dict          # format-specific extras

@dataclass
class NormalizedTask:
    task_id: str                   # native task ID (T001, S-1.3, etc.)
    text: str
    completed: bool
    assignee: str | None
    dependencies: list[str] = field(default_factory=list)
    native_status: str | None = None  # in case format has richer status

class SddAdapter(ABC):
    name: str  # "spec-kit" | "openspec" | "bmad" | "taskmaster"

    @abstractmethod
    def detect(self, repo_root: Path) -> bool:
        """Return True if this adapter recognizes the repo."""

    @abstractmethod
    def list_features(self, repo_root: Path) -> list[FeatureHandle]:
        """Enumerate all features/changes/epics in the repo."""

    @abstractmethod
    def load_feature(self, handle: FeatureHandle) -> NormalizedArtifacts:
        """Read all artifacts for a feature and normalize."""

    @abstractmethod
    def compute_stage(self, artifacts: NormalizedArtifacts) -> StageProgress:
        """Compute stage progression. Adapter decides its stage model."""

    @abstractmethod
    def id_for_path(self, path: Path, repo_root: Path) -> str | None:
        """Reverse lookup: given a path, is it part of a feature?"""

    # Optional — adapters can decline to support write operations
    def write_review_verdict(
        self,
        handle: FeatureHandle,
        review_type: str,
        verdict: str,
        body: str,
    ) -> None:
        raise NotImplementedError

    def supports(self, capability: str) -> bool:
        """E.g., supports('review-pr'), supports('task-graph')."""
        return False
```

### Stage progression

The stage model is the trickiest piece. Options:

- **Option A**: force every adapter into Orca's nine-stage linear
  model. Adapters fake stages they don't have (mark as
  `not-applicable`) or bundle multiple native stages into one Orca
  stage. Simple, but Procrustean — OpenSpec's delta lifecycle
  doesn't have a "plan" that's distinct from the proposal.
- **Option B**: let each adapter expose its native stage model and
  Orca core consumes whatever shape it gets. More faithful, but
  breaks existing assumptions in matriarch, yolo, and review
  commands that hardcode the nine stages.
- **Option C**: core defines a small set of *stage kinds*
  (`ideate` / `specify` / `plan` / `decompose` / `implement` /
  `review` / `ship`) and adapters tag their native stages with
  these kinds. Core operates on kinds; adapters translate.

**My lean: C**. Kinds are stable; stages are format-dialects.
OpenSpec's `proposal → implement → archive` maps to
`ideate → specify → implement → ship`. BMAD's
`prd → architecture → epic → story → dev → qa` maps to
`specify → plan → decompose → implement → review`. Spec-kit's nine
stages map one-to-one with kinds. Yolo runner gates on kinds;
matriarch coordinates on kinds; review commands fire on `review`
kind.

This also means `flow_state.FlowMilestone` needs a `kind` field
alongside `stage`, and `STAGE_ORDER` has to become either (a)
per-adapter or (b) a kind-ordering plus adapter-specific stage-list
under each kind.

### Artifact I/O

Adapters read artifacts from their native location and write them
back in native shape. Core writes to centralized locations under
`.specify/orca/` (brainstorm memory, spec-lite, adopted, handoffs,
yolo runs, worktrees, evolve). Adapter reads are lossless; adapter
writes are opt-in (not all adapters support all Orca commands).

OpenSpec's archive model is interesting: when a delta is accepted,
it's moved into `openspec/archive/` and the current `openspec/specs/`
is updated. The adapter handles that lifecycle; core doesn't need
to know.

### Detection

Detection is a cheap directory probe:

- spec-kit: presence of `specs/NNN-*/spec.md`
- OpenSpec: presence of `openspec/changes/` or `openspec/specs/`
- BMAD: presence of `docs/prd.md` + `docs/stories/`
- Taskmaster: presence of `.taskmaster/` or `taskmaster.json`

Orca's `doctor` command learns to report detected formats. Multiple
formats in one repo means each adapter's features appear side by
side in flow-state output, tagged with `adapter: <name>`.

### Capabilities

Not every adapter supports every Orca subsystem. Example: Taskmaster
has no concept of review artifacts, so
`adapter.supports('review-code')` returns `False`. Commands that
need an unsupported capability degrade gracefully
(`speckit.orca.review-code` on a Taskmaster feature prints "This
format does not support split review artifacts. Use the native
Taskmaster review flow, or convert the feature to spec-kit with
`orca convert`.").

## Which Orca subsystems need adapter-ification

### Flow-state (`src/speckit_orca/flow_state.py`)

**Highest impact, highest leverage.** Flow-state is the visible
aggregator — everything downstream consumes its output. Make
flow-state adapter-aware and most of the rest falls into place.

Changes:

- `collect_feature_evidence` becomes adapter-dispatched. Given a
  target path, determine the owning adapter, call
  `adapter.load_feature()`, get a `NormalizedArtifacts`, derive
  `FlowStateResult` from it.
- `STAGE_ORDER` moves into the spec-kit adapter. Core operates on
  stage kinds.
- `_stage_milestones`, `_derive_ambiguities`, `_next_step` all take
  an adapter argument so they can consult format-specific rules.
- The CLI target-resolution in `main()` learns to detect which
  adapter owns the target path.
- `list_yolo_runs_for_feature` stays spec-kit-native for v1
  (yolo runtime lives in spec-kit land first).

Effort estimate: 2-3 days of refactor. Most of it is moving code,
not rewriting logic.

### Matriarch (`src/speckit_orca/matriarch.py`)

**Second highest impact.** Matriarch registers lanes, coordinates
dependencies, aggregates readiness. Lane identity is
`feature_id = NNN-slug` in spec-kit terms.

Changes:

- Lane registration takes a `FeatureHandle` (adapter + feature ID)
  instead of a raw path.
- `_is_spec_lite_record` / `_is_adoption_record` guards generalize:
  ask the adapter `adapter.can_anchor_lane(handle)`.
- Readiness aggregation consumes the kind-based flow state, not
  spec-kit stage names.
- Touch-point declarations (from 015) either stay spec-kit-native
  for v1 or generalize per adapter.

Effort estimate: 1-2 days. Matriarch's core logic (dependency
graph, mailbox events, delegated tasks) is already format-agnostic —
it just currently assumes feature IDs look a certain way.

### Yolo (`src/speckit_orca/yolo.py`)

**Medium impact, complicated.** Yolo's event log records stages that
match `STAGE_ORDER`. Events like `STAGE_ENTERED(stage="plan")` would
break if the adapter's stage model is different.

Changes:

- Events record *stage kinds*, not native stage names. Native stage
  names go in a side channel.
- Resume logic uses kinds for gate evaluation.
- Runtime hooks into adapter for "what's the next stage?" rather
  than hardcoding the ladder.

Effort estimate: 3-5 days. Yolo is not yet running in production
(still contract-complete, not runtime-complete per README). We can
build it adapter-aware from day one instead of retrofitting.

### Review commands (`commands/review-*.md`)

**Lowest impact in core, highest impact in command text.** The review
commands are prompt templates — the actual prompt text is hardcoded
for spec-kit conventions (talks about `spec.md`, `tasks.md`, etc.).

Changes:

- Prompt templates grow template variables (`{spec_path}`,
  `{tasks_path}`) that adapters fill in.
- Output parsing in `flow_state._parse_review_*` generalizes.
- OpenSpec review model is different — they review proposals before
  archive. Either the review commands grow format-specific branches
  or the OpenSpec adapter fakes a spec-kit-like review shape.

**v1 decision**: review commands stay spec-kit-only for v1. Other
adapters report `supports('review-spec') = False` and defer to the
native format's review flow. We ship the three-review model on
spec-kit and revisit cross-format review in v2.

### Brainstorm memory (`src/speckit_orca/brainstorm_memory.py`)

**Low impact.** Brainstorm memory is stored centrally under
`.specify/orca/brainstorms/`. The `.specify/` directory is itself
a spec-kit convention, but the brainstorm registry is *additive* —
any format can benefit from it.

Changes:

- Linking brainstorms to features learns about adapter handles
  instead of `specs/NNN-slug/` strings.
- Registry directory stays `.specify/orca/brainstorms/` across all
  adapters. No format-specific brainstorm storage.

Effort estimate: ~1 day. Mostly link-resolution cleanup.

### Context handoffs (`src/speckit_orca/context_handoffs.py`)

**Low impact.** Handoffs are records of "stage X completed, here's
the handoff to stage Y." If stages are kinds, handoffs are
kind-to-kind. Storage stays centralized.

Effort estimate: ~1 day.

### Spec-lite, adopt, evolve

**Zero impact.** These are Orca-native primitives with their own
registries. They don't depend on spec-kit — they depend on Orca's
central `.specify/orca/` store. They'll work for every adapter
unchanged.

One wrinkle: `.specify/orca/` is a *spec-kit* convention by
virtue of living under `.specify/`. For a pure OpenSpec or BMAD
repo, there's no `.specify/`. v1 decision: Orca creates
`.specify/orca/` on first use regardless of adapter. The directory
name is grandfathered. Not worth breaking.

### Worktree runtime

**Medium impact.** Worktree metadata keys lanes by feature ID.
Already need to change for matriarch; this is essentially the same
change.

### Capability packs

**Zero impact.** Packs are cross-cutting composition — they layer
on top of flow-state output. Once flow-state is adapter-aware, packs
inherit that.

### Brownfield adoption (015)

**Interesting interaction.** Adoption records describe existing
features that predate Orca. They live at
`.specify/orca/adopted/AR-NNN-slug.md`. Are they format-native?

v1 decision: **adoption records are Orca-native, adapter-agnostic.**
They describe existing code, not existing specs. Their `Location`
field just points at paths. An OpenSpec repo can still have
adoption records describing the pre-OpenSpec auth middleware.

### Extension manifest / installer

**Medium impact.** Installer hooks assume spec-kit catalog. The
`speckit-orca` CLI assumes `.specify/integrations/*.manifest.json`
exists. Cross-format install is a separate can of worms — do we
*install* into an OpenSpec repo at all? What does that mean?

**v1 decision**: installer stays spec-kit-required. Other formats
consume Orca via `uv run python -m speckit_orca.flow_state ...`
direct invocation against their repos, no install. The polished
install flow is spec-kit-only until we have real demand for
OpenSpec/BMAD installer integration.

## What we harvest from each format

The goal isn't just "support other formats." It's also "steal the
good ideas." Each format has primitives Orca should consider
adopting into its core model.

### OpenSpec

**Harvest**:
- **Delta-spec model** (tentative). OpenSpec's
  `proposal → implement → archive` flow with delta files is a
  genuinely different way to manage change vs. spec-kit's
  full-spec-per-feature. Worth studying for the archive layer
  especially. 015 explicitly flagged this as out-of-scope; 016
  could be where we revisit.
- **Three-field proposal structure** (`Why / What Changes / Impact`).
  Tighter than spec-kit's full spec template. Potential input for a
  future `spec-lite-lite` or a spec-kit spec template refresh.
- **Brownfield-first posture**. 015 addressed this inside spec-kit;
  OpenSpec's brownfield story is more holistic. Worth a pattern
  harvest into Orca's onboarding docs.
- **Archive as first-class concept**. Retired specs have a home.
  spec-kit doesn't have this — retired specs just sit in `specs/`
  indefinitely or get moved to a custom `archive/` folder by
  convention. Orca could adopt OpenSpec's pattern.

**Keep spec-kit-native**:
- Full spec ceremony. OpenSpec's delta model trades ceremony for
  incrementalism. spec-kit's full-spec model is better for
  higher-stakes work where we want a durable artifact, not a chain
  of deltas. Don't convert spec-kit to delta-specs.
- Nine-stage pipeline. OpenSpec's lifecycle is simpler. We already
  have the spec-kit pipeline embedded in many places; keeping it
  is cheaper than converting it.

### BMAD

**Harvest**:
- **Story/epic decomposition**. BMAD's `epic → story → task` three-tier
  hierarchy is richer than spec-kit's `feature → task` two-tier.
  For very large features (a full product line), the three-tier shape
  would help. Evolve candidate.
- **Named agents per stage**. BMAD has `@pm`, `@architect`,
  `@dev`, `@qa` with explicit handoffs. Orca's `assign` command
  does something similar but is less prescriptive. BMAD's naming
  convention is worth borrowing.
- **Story status enum** (`draft / approved / in-progress /
  review / done`). Richer than spec-kit's checkbox-completed. Could
  inform task-status richness in Orca.

**Keep spec-kit-native**:
- Sprint/backlog primitives. BMAD imports Scrum scaffolding. Orca's
  lane model (matriarch) is different — it's not a sprint, it's a
  parallel work stream. Don't merge the concepts.
- QA-as-named-stage. BMAD puts QA in the ladder; Orca puts review
  in the ladder. Different emphasis. Keep Orca's review model.

### Taskmaster

**Harvest**:
- **Task graph with dependencies**. Orca's `tasks.md` is a flat list
  with implicit order. Taskmaster's DAG is richer. Evolve candidate
  — maybe tasks.md grows a `depends_on` field.
- **PRD-to-task automation**. Taskmaster decomposes a PRD into
  tasks via LLM. Spec-kit's `/speckit.tasks` does something similar
  but less graph-aware. Good pattern to study.
- **Subtasks**. Nested task decomposition. Orca's `T001` / `T002`
  / ... is flat.

**Keep spec-kit-native**:
- JSON-as-source-of-truth. Taskmaster puts tasks in `tasks.json`,
  not markdown. Orca's markdown-first posture is user-friendly and
  git-diff-friendly. Don't move to JSON.
- PRD as the only spec artifact. Taskmaster collapses spec, plan,
  tasks into a single PRD. Too coarse for the gated review model
  Orca wants. Keep spec/plan/tasks separation.

### Summary of harvest plan

- **Deferred to v2+** (separate specs, not part of 016): delta-spec
  model, epic/story decomposition, task DAG, named-agent per-stage
  conventions, OpenSpec archive layer.
- **Part of 016** (adapter scope): feature enumeration, artifact
  normalization, stage-kind mapping, review-capability probe,
  detection, capability probing.

## Downstream Impact (file-by-file)

### New files

- `src/speckit_orca/adapters/__init__.py` — adapter registry and
  detection.
- `src/speckit_orca/adapters/base.py` — abstract base class,
  dataclasses (`FeatureHandle`, `NormalizedArtifacts`,
  `NormalizedTask`, `StageProgress`).
- `src/speckit_orca/adapters/spec_kit.py` — reference adapter,
  wraps current flow-state logic.
- `src/speckit_orca/adapters/openspec.py` — new adapter, v1 scope.
- `src/speckit_orca/adapters/bmad.py` — stub for v1, fleshed out in
  v2. Detection and enumeration only.
- `src/speckit_orca/adapters/taskmaster.py` — stub for v1, fleshed
  out in v2. Detection and enumeration only.
- `specs/016-multi-sdd-layer/plan.md` — next phase.
- `specs/016-multi-sdd-layer/data-model.md` — normalized model
  shapes.
- `specs/016-multi-sdd-layer/contracts/adapter-interface.md` —
  canonical interface contract.
- `specs/016-multi-sdd-layer/contracts/stage-kind.md` — stage-kind
  enum and per-format mappings.
- `tests/test_adapters.py` — golden-file tests per adapter.

### Modified files

- `src/speckit_orca/flow_state.py` — major refactor. `STAGE_ORDER`
  moves out. Dispatch-on-adapter added. `NormalizedArtifacts`
  consumed instead of raw file probes. Estimated 40-50% of the file
  either moves or becomes thin wrapper.
- `src/speckit_orca/matriarch.py` — lane registration takes handles;
  `_is_*_record` guards consult adapter.
- `src/speckit_orca/yolo.py` — event schema learns `stage_kind`
  alongside `stage`. (Yolo is pre-runtime; we can shape it cleanly.)
- `src/speckit_orca/brainstorm_memory.py` — link resolution via
  adapter.
- `src/speckit_orca/context_handoffs.py` — kind-to-kind handoffs.
- `src/speckit_orca/cli.py` — `--adapter <name>` flag for explicit
  selection, `--doctor` reports detected adapters.
- `extension.yml` — add `yolo` adapter-aware note, `supports`
  field per command? (Or defer.)
- `commands/*.md` — review-spec/code/pr stay spec-kit-pinned for
  v1; other commands learn to check adapter capabilities.
- `README.md` — new section explaining the adapter layer, list
  supported formats, document how to pick.

### Untouched files

- `src/speckit_orca/spec_lite.py` — adapter-agnostic, no changes.
- `src/speckit_orca/adoption.py` — adapter-agnostic, no changes.
- `src/speckit_orca/evolve.py` — adapter-agnostic, no changes.
- `src/speckit_orca/capability_packs.py` — layers on top,
  inherits from flow-state changes.

## Sequencing — what ships first

v1 scope is a hard carve. Ship the smallest thing that proves the
architecture; don't over-scope.

### Phase 1 — adapter interface + spec-kit adapter (MVP)

Scope:
- Define the interface (`SddAdapter` abstract base, data classes).
- Implement `SpecKitAdapter` that wraps current flow-state logic
  behind the interface. No behavior changes.
- Refactor `flow_state.py` to dispatch through the adapter registry.
- Tests: existing flow-state tests pass unchanged. New tests prove
  the adapter interface.

Exit criteria: zero external user-visible change. Internal code
restructured. Foundation for Phase 2.

### Phase 2 — OpenSpec adapter (real second format)

Scope:
- Implement `OpenSpecAdapter`.
- Detection, enumeration, artifact loading, stage computation via
  stage-kinds.
- Read-only. Can't write review verdicts, can't run yolo against an
  OpenSpec repo in v1.
- `speckit-orca --doctor` reports detected formats including
  OpenSpec.
- Flow-state produces meaningful output for OpenSpec changes.
- Tests: golden-file tests with a fixture OpenSpec repo.

Exit criteria: a user with an OpenSpec repo can run
`uv run python -m speckit_orca.flow_state openspec/changes/<change>`
and get a useful view. No other command is guaranteed to work on
OpenSpec yet.

### Phase 3 — BMAD and Taskmaster stubs

Scope:
- Detection only. Enumeration only. No deep load.
- `speckit-orca --doctor` reports detected formats.
- Flow-state on a BMAD or Taskmaster feature returns a shallow
  "detected but not fully supported" view.

Exit criteria: future adapters have skeletons. Users can tell Orca
sees their repo even if it doesn't drive it yet.

### Deferred to v2+

- Full BMAD adapter with story/epic awareness.
- Full Taskmaster adapter with task-graph import.
- Cross-format review artifacts.
- `orca convert` — migrate a feature from format A to format B.
- Plugin system for third-party adapters.
- Write support for non-spec-kit adapters.

### Why spec-kit first, then OpenSpec

- spec-kit first because it's the reference — the interface has to
  fit reality before it can fit hypothetical reality.
- OpenSpec second because it's the most semantically different from
  spec-kit (delta model, different directory, brownfield-first).
  If the interface survives OpenSpec, it will survive BMAD and
  Taskmaster.
- BMAD and Taskmaster after because they're additional proofs, not
  architectural risks.

## Non-Goals

Explicitly out of scope for 016:

- **Not building a plugin system.** Adapters are in-tree v1. Plugin
  discovery, sandboxing, versioning is deferred.
- **Not building `orca convert`.** Migrating a feature from spec-kit
  to OpenSpec (or vice versa) is a separate spec. Users who want
  that can ask.
- **Not rewriting review-spec / review-code / review-pr to be
  format-agnostic.** Review artifacts stay spec-kit-shaped in v1.
  Other adapters return `supports('review-code') = False`.
- **Not generalizing the nine-stage model to an arbitrary DAG.**
  Stage kinds are a fixed small set. If a format has a stage Orca's
  kind enum doesn't cover, the adapter maps it to `other` or omits
  it. We don't build a DAG engine.
- **Not moving `.specify/orca/` to a format-neutral path.** The
  directory name is grandfathered. A v3 project could rename it
  with a migration script, but 016 doesn't.
- **Not supporting multi-format installs via the installer.** The
  `speckit-orca <provider>` install command stays spec-kit-first.
  Other formats use direct invocation.
- **Not shipping a BMAD or Taskmaster full adapter in v1.** Only
  detection stubs.
- **Not adding `orca.format = <name>` to the config template.**
  Auto-detection first; config-based override only if detection
  proves insufficient.
- **Not changing `extension.yml` schema.** Adapter metadata lives
  in Python code, not in the manifest.
- **Not building an adapter for `kiro`, `agent-os`, `windsurf`,
  or `cursor-rules`-driven SDD.** The long tail is real but out of
  v1 scope. Architecture should tolerate adding them later without
  core changes.
- **Not building GUI / TUI for format-switching.** 018-orca-tui is
  a separate spec; it'll learn adapters when it lands.

## Open Questions for the Plan Phase

1. **Stage kind enum — final shape.** Current candidate:
   `ideate / specify / plan / decompose / implement / review / ship`.
   Is `ship` a kind or a meta-state? Does `decompose` conflate
   "write tasks" and "generate DAG"? Does `ideate` include
   brainstorm *and* spec-lite *and* adoption? My lean: keep it at
   7 kinds, accept some lossiness. Plan nails this down.

2. **Adapter write support — opt-in or opt-out?** v1 decision is
   read-only for non-spec-kit. Do we want the adapter API to
   *require* a write interface (adapters raise NotImplementedError
   for unsupported writes) or *omit* the write interface entirely
   (adapters optionally implement a mixin)? My lean: require + raise.
   Simpler reflection.

3. **Detection precedence — what if both `specs/` and `openspec/`
   exist?** Report both. Each adapter scopes to its own directory.
   Flow-state output tags `adapter: <name>`. But what if a user runs
   `speckit-orca --status` without a target? My lean: report all
   adapters' state side-by-side, same as matriarch lanes.

4. **`FeatureHandle` serialization format.** Need to round-trip
   through JSON for yolo event logs and matriarch registry. My
   lean: `{"adapter": "openspec", "feature_id": "add-auth", ...}`
   as a plain dict. Include in contracts file.

5. **Spec-kit adapter — stateful or stateless?** Currently
   `flow_state.py` has no state; every call re-reads the filesystem.
   Should adapters cache parse results within a process? My lean:
   stateless for v1. Caching is a performance optimization, not a
   correctness requirement.

6. **Review commands on non-spec-kit adapters.** v1 says "return
   `supports('review-code') = False` and defer to native flow." But
   what does the CLI do? Print a helpful error? Forward to the
   native tool? My lean: print a helpful error with a link to the
   native tool's docs. Don't try to shell out.

7. **Brainstorm-to-feature linking across formats.** Current
   brainstorm memory scans for `specs/NNN-slug/` references. In
   OpenSpec, the reference is `openspec/changes/<slug>/`. Do we
   teach the scanner about each format? My lean: yes, via the
   adapter's `id_for_path`. Small per-adapter addition.

8. **`.specify/orca/` on a pure OpenSpec repo — create on first
   use or require explicit opt-in?** Current default-creation pattern
   is aggressive. For a user who's just running flow-state once on
   an OpenSpec repo, we'd litter their project with
   `.specify/orca/`. My lean: create lazily, only when a command
   needs to *write*. Read-only flow-state doesn't create anything.

9. **Testing strategy — fixture repos or synthetic trees?** My
   lean: both. Synthetic trees for unit tests (fast, easy to
   hand-construct). Real fixture repos (tiny clones of OpenSpec /
   BMAD examples) for integration tests (catches format drift).

10. **Adapter resolution for cross-format dependencies.** If a
    spec-kit feature has a `Touches ARs` field pointing at an
    AR-001, and AR-001 lives in `.specify/orca/adopted/` (Orca
    central), that's fine. But what if a future adapter uses a
    different central store? v1 doesn't have this problem;
    flag for v2.

11. **Error surface for unsupported operations.** Should the CLI
    error on unsupported operations (exit 1) or warn and continue
    (exit 0 with stderr message)? My lean: exit 2 for user errors
    ("this adapter doesn't support X, try Y"). Distinct from
    exit 1 (bug) and exit 0 (success). Standard CLI convention.

12. **Versioning the adapter interface.** When we change the
    interface in v2, in-tree adapters update in lockstep. If plugins
    ever arrive, we'll need a `SddAdapter.API_VERSION = 1`
    convention. Flag for v2; don't build in v1.

13. **Documentation surface.** README gets a new section, but the
    real adapter docs are per-adapter ("how to tell Orca about your
    OpenSpec repo"). Where do those live? My lean:
    `docs/adapters/<name>.md`. Not in READMEs.

14. **Migration guidance.** If a user is on spec-kit and wants to
    try OpenSpec, Orca is not the tool that migrates them. But Orca
    *could* notice both directories and advise. Out of scope for
    v1; flag for v2.

15. **What about `@github/copilot` "workspace" or Cursor's
    `.cursorrules`?** These aren't SDD formats in the sense of
    on-disk artifact layouts — they're agent runtime contexts. They
    don't belong in the adapter enum. v1 ignores them.

## Suggested Next Steps

1. **Review this brainstorm.** Answer the 15 open questions above,
   or triage them into "v1 critical," "v1 punt," "v2+."
2. **Get a cross-review pass** (same pattern as 015). Goal: have a
   different agent (probably codex gpt-5.4 high effort) stress-test
   the adapter interface shape before we commit.
3. **Write `specs/016-multi-sdd-layer/plan.md`** with:
   - Final adapter interface.
   - Stage-kind enum.
   - Phase-by-phase deliverables.
   - Test strategy.
   - Backwards-compat guarantee for existing spec-kit users.
4. **Write `specs/016-multi-sdd-layer/contracts/adapter-interface.md`**
   — canonical interface, version 1.
5. **Write `specs/016-multi-sdd-layer/contracts/stage-kind.md`** —
   kind enum and per-format mappings.
6. **Write `specs/016-multi-sdd-layer/data-model.md`** — normalized
   artifact, task, and review-evidence shapes.
7. **Implement Phase 1** (interface + spec-kit adapter, no
   behavior change). Land it. Ship flow-state unchanged. Validate
   the refactor didn't regress.
8. **Implement Phase 2** (OpenSpec adapter). Land it. Flow-state
   starts returning useful output on OpenSpec repos.
9. **Implement Phase 3** (BMAD + Taskmaster stubs). Land it.
   Detection works; deep load is stubbed.
10. **Harvest candidates.** Feed delta-specs, epic/story
    decomposition, task DAGs, archive layer into `evolve.py` as
    deferred adoption candidates for future specs.
11. **Update README.** New section on adapter layer. Update
    "Current Focus" and "Internals." Link to adapter docs.

## Dependencies on Other In-Flight Work

### Hard prerequisites

- **None.** 016 is foundational. It restructures existing code but
  doesn't depend on any in-flight feature.

### Soft prerequisites (nice-to-have)

- **015 brownfield adoption** should land first. 015's adoption
  record primitive is adapter-agnostic (Orca-native), and landing
  it first means 016 doesn't have to restructure
  `.specify/orca/adopted/` while the ink is wet on it.
- **014 yolo runtime** could land first or after. If yolo ships
  before 016, we retrofit stage-kinds; if after, we build stage-kinds
  in from day one. My lean: do 016 *first* so yolo is born
  adapter-aware. Yolo is contract-complete but not
  runtime-complete, so this is cheap.

### Independent of 016 timing

- 011 evolve — no interaction beyond evolve tracking harvest
  candidates.
- 010 matriarch's in-flight refinements (drift flag, tmux
  inspection) — 016 touches matriarch's lane-registration surface,
  not the refinement surface.
- 017 brownfield-v2 — sibling to 016; both address brownfield but
  from different angles. 017 is deeper inside spec-kit; 016 goes
  wider across formats. They don't conflict.
- 018 orca-tui — 018 will render adapter-aware state if 016 lands
  first. If 018 lands first, it retrofits. Either works.

## Risks and Mitigations

### Risk 1: Interface churn

The adapter interface will probably need to change after contact
with a second real adapter. We ship v1 against spec-kit only, then
find the interface wrong when building OpenSpec.

**Mitigation**: Phase 1 lands the interface and the spec-kit
adapter. Phase 2 is permitted to change the interface if OpenSpec
reveals a mismatch. We're willing to break the interface between
v1 and v2 as long as (a) we bump a version marker and (b) in-tree
adapters update in lockstep. Since there are no plugins yet, this
is a free move.

### Risk 2: Stage-kind enum is wrong

The 7-kind enum is a guess. BMAD's story lifecycle might have a
phase that doesn't fit. OpenSpec's archive step might.

**Mitigation**: Phase 2 can add kinds if genuinely needed. Don't
over-design the enum up front; design it against spec-kit and
OpenSpec, add for BMAD/Taskmaster as needed.

### Risk 3: Users get confused about which adapter is active

Multi-format repos are rare but exist. A user running a command
might not know which adapter claimed their feature.

**Mitigation**: Every CLI output tags the adapter. `doctor`
explicitly lists detected adapters. The `--adapter <name>` override
is documented.

### Risk 4: spec-kit-only users see no benefit and some risk

The refactor is invisible to them. They're exposed to regression
bugs with no upside.

**Mitigation**: Phase 1 exit criterion is "zero behavior change."
Existing tests pass. New tests prove the interface. No user-visible
change until they *opt in* by using a non-spec-kit repo.

### Risk 5: We build the adapter layer and nobody uses OpenSpec

Scope expansion for hypothetical users.

**Mitigation**: The adapter *pattern* is worth it even if nobody
uses OpenSpec, because it cleans up the 70% of `flow_state.py`
that's currently spec-kit-flavored. The refactor pays for itself
in code hygiene. OpenSpec adapter is gravy.

### Risk 6: Review commands stay spec-kit-pinned and that becomes a
permanent dead-end

If review-spec/code/pr never generalize, OpenSpec/BMAD users never
get Orca's review value. The layer goal is half-achieved.

**Mitigation**: v1 explicitly defers cross-format review. v2 or v3
addresses it. Users of OpenSpec/BMAD get flow-state, matriarch
(maybe), yolo (maybe), but not review in v1. That's still a real
improvement over nothing, and it's honest about the limit.

## Summary

Orca is a spec-kit-only tool today. It shouldn't be. The SDD space
is fragmenting; OpenSpec, BMAD, and Taskmaster are real. Orca's
value is in the operating layer, not the directory convention.

Ship a thin adapter pattern: fixed Python interface, in-tree
adapters, spec-kit first (as reference), OpenSpec second (to prove
the architecture), BMAD and Taskmaster stubs third (for
discoverability). Map per-format stages to a small `stage-kind`
enum so core stays format-agnostic. Leave review commands
spec-kit-pinned for v1 and revisit in v2+.

The refactor cleans up `flow_state.py` (which is 70% spec-kit
flavored) even if nobody ever writes a non-spec-kit adapter. That's
enough justification on its own. The cross-format adoption is the
upside.

Non-goals list is aggressive: no plugins, no conversion tool, no
cross-format review, no format-neutral `.specify/` path, no
full-fat BMAD or Taskmaster adapters in v1. Restraint here is how
we ship this without turning it into an 18-month architecture
project.

Next: answer the 15 open questions, get a cross-review pass, write
the plan.
