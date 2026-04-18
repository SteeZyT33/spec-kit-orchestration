# Feature Specification: OpenSpec Adapter — Phase 2 of the Multi-SDD Layer

**Feature Branch**: `019-openspec-adapter`
**Created**: 2026-04-16
**Status**: Proposed
**Predecessors**: 016-multi-sdd-layer (Phase 1 landed), PR #62 (Phase 1.5 landed)
**Input**: "Add an OpenSpec adapter behind the Phase 1 adapter interface so Orca can detect, enumerate, and read OpenSpec repos without changing any Phase 1 public API, and introduce the minimum registry, stage-kind, and capability infrastructure to make 'two in-tree adapters' a coherent concept."

## Context

Phase 1 (016) shipped a single-concrete-adapter wiring: `SpecKitAdapter`
behind the `SddAdapter` ABC, consumed by `flow_state` via the
module-level `_SPEC_KIT_ADAPTER` singleton. Phase 1.5 (PR #62) pushed
review evidence and worktree lanes off `flow_state` internals into
normalized adapter-owned types.

Phase 2 adds the second real adapter (`OpenSpecAdapter`), a registry
that resolves adapters per path and per repo, a stage-kind vocabulary
so matriarch/TUI/yolo can reason across formats without hardcoding
stage names, and a `supports(capability)` probe so format-specific
subsystems (review split, worktree lanes, yolo runtime) can gate
themselves.

This spec mirrors the structure of `specs/016-multi-sdd-layer/spec.md`.
The brainstorm at `specs/019-openspec-adapter/brainstorm.md` (1540
lines) is the source for cross-references below.

## Clarifications / decisions recorded

The brainstorm flagged eight primary open questions. The orchestrator
has resolved them. These are binding for v1 and the spec is written
against them. Do not relitigate in `plan.md`.

1. **Stage-kind vocabulary is fixed for v1.** The canonical enum is
   `{spec, plan, tasks, implementation, review_spec, review_code,
   review_pr, ship}`. `decompose` is folded into `plan` for v1.
   Additional kinds are a future spec.
2. **Filename keys are semantic, not format-native.** Adapters map
   the semantic keys (`"spec"`, `"plan"`, `"tasks"`, `"review_spec"`,
   `"review_code"`, `"review_pr"`) to their on-disk filenames. For
   OpenSpec, `"spec"` maps to `proposal.md`.
3. **Archived OpenSpec changes are hidden by default.**
   `list_features` excludes them. An `include_archived: bool = False`
   parameter turns them back on. Feature IDs for archived changes are
   stable across archive moves (the slug is the ID; the date prefix
   is not part of the ID).
4. **Singleton is deprecated but still functional.** `AdapterRegistry`
   is introduced as the canonical way to obtain adapters. The Phase 1
   `_SPEC_KIT_ADAPTER` singleton remains importable and writable for
   one release, marked deprecated. Removal is a future spec.
5. **Matriarch ignores OpenSpec features.** The adapter declares
   `supports("lanes") == False` and matriarch respects that: no lane
   registration, no readiness gates, no coordination. OpenSpec
   operators use OpenSpec's own tooling for those concerns.
6. **018 TUI needs no changes for v1.** The TUI already consumes
   normalized artifacts; OpenSpec features appear alongside spec-kit
   features once the registry resolves them. 018 is not a dependency
   of 019 and 019 is not a dependency of 018.
7. **OpenSpec fixture is hand-authored.** A minimal repo under
   `tests/fixtures/openspec_repo/`. Do not clone a real OpenSpec repo.
   The hand-authored shape is documented in the fixture README.
8. **Capability vocabulary v1 is closed.** `{"lanes", "yolo",
   "review_code", "review_pr", "adoption"}`. Each adapter's
   `supports(capability) -> bool` answers these. Unknown capabilities
   return False.

Cross-reference: these decisions close brainstorm §17 items 1, 2, 3,
4, 5, 6, 7, and 10. The remaining open questions appear under
§Open questions below.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Existing OpenSpec User Sees Their Changes in Flow State (Priority: P1)

An existing OpenSpec user runs
`uv run python -m speckit_orca.flow_state openspec/changes/add-dark-mode`
in a repo that uses OpenSpec conventions. Orca detects the format,
loads the change, and reports its stage progression and tasks.

**Why this priority**: OpenSpec support is the feature. If this
scenario does not work, Phase 2 has not shipped.

**Independent Test**: Point `compute_flow_state` at an
`openspec/changes/<slug>/` directory in a fixture repo. Assert the
returned `FlowStateResult` contains non-empty stage evidence, the
task list parsed from `tasks.md`, and references the change's
`proposal.md` via the `"spec"` filename key.

**Acceptance Scenarios**:

1. **Given** a fixture OpenSpec repo with an active change
   `add-dark-mode`, **When** `compute_flow_state` is called on
   `openspec/changes/add-dark-mode`, **Then** the result contains a
   `FeatureEvidence` whose `adapter_name == "openspec"`, whose
   `filenames["spec"]` is `proposal.md`, and whose task summary
   matches the checkbox counts in the fixture `tasks.md`.
2. **Given** the same repo, **When** `compute_flow_state` is called
   on the repo root (no feature specified), **Then** active OpenSpec
   changes are enumerated alongside any spec-kit features.
3. **Given** a path to an archived change
   (`openspec/changes/archive/<dated-slug>/`), **When**
   `compute_flow_state` is called on it, **Then** the path is not
   resolved to a feature (registry returns `None`) and flow_state
   reports the path as unrecognized, matching its current behavior
   for paths outside the adapter surface.

---

### User Story 2 — Flow State Reports Stage Progress Correctly for OpenSpec Changes (Priority: P1)

`compute_flow_state` reports OpenSpec stages using the v1 stage-kind
vocabulary so downstream consumers (TUI, matriarch for read-only
display) do not need per-format branches.

**Why this priority**: If stage-kind does not work, every downstream
consumer has to know "spec-kit stages" vs "OpenSpec stages" and the
abstraction has not paid off.

**Independent Test**: Call `compute_stage(artifacts)` on a loaded
OpenSpec change. Assert every returned `StageProgress` has a `kind`
field drawn from the v1 vocabulary. Call the same on a spec-kit
feature. Assert the same property holds.

**Acceptance Scenarios**:

1. **Given** an active OpenSpec change with `proposal.md`, `design.md`,
   and a partially-checked `tasks.md`, **When** `compute_stage` runs,
   **Then** the returned stages include a `spec` kind (present,
   complete), a `plan` kind (present, complete), and an
   `implementation` kind (in progress). `review_spec`, `review_code`,
   `review_pr` kinds are either absent or marked not-applicable.
2. **Given** a spec-kit feature after Phase 2 lands, **When**
   `compute_stage` runs, **Then** every returned `StageProgress.kind`
   is in `SddAdapter.ordered_stage_kinds()` and the overall shape
   matches the Phase 1 output byte-for-byte except for the added
   `kind` field.

---

### User Story 3 — Adapter Author Adds a Third Adapter Without Editing Core (Priority: P2)

A future contributor starting a BMAD or Taskmaster adapter subclasses
`SddAdapter`, registers the adapter via `AdapterRegistry.register`,
and the rest of Orca resolves their features without edits to
`flow_state`, `matriarch`, `yolo`, or the TUI.

**Why this priority**: The registry earns its weight by making the
third adapter as cheap as the second. If wiring the third adapter
requires editing core modules, we built the wrong abstraction.

**Independent Test**: In a test, register a trivial stub adapter,
assert `registry.resolve_for_path` returns it for paths it claims,
and assert `flow_state.compute_flow_state` on such a path dispatches
through the stub without any core module edits.

**Acceptance Scenarios**:

1. **Given** a stub adapter registered at test time, **When**
   `resolve_for_path` is called on a path the stub claims, **Then**
   the stub adapter is returned and its `load_feature` is invoked.
2. **Given** the stub adapter, **When** `compute_flow_state` runs on
   a path owned by the stub, **Then** the returned `FlowStateResult`
   carries the stub's normalized artifacts without any edits to
   `flow_state.py`, `matriarch.py`, or `yolo.py`.

---

### User Story 4 — Mixed Repo Works Without Cross-Contamination (Priority: P2)

A repo with both `specs/NNN-slug/` and `openspec/changes/<slug>/` is
supported. Each adapter enumerates its own features, and each feature
is resolved by the correct adapter based on path.

**Why this priority**: Migration scenarios (a team moving from
spec-kit to OpenSpec, or running both temporarily) should work without
errors.

**Independent Test**: Fixture repo with both conventions. Assert
`registry.resolve_for_repo` returns both adapters. Assert
`resolve_for_path` on a spec-kit feature returns `SpecKitAdapter` and
on an OpenSpec change returns `OpenSpecAdapter`.

**Acceptance Scenarios**:

1. **Given** a mixed-repo fixture, **When** `resolve_for_repo(root)`
   is called, **Then** both `SpecKitAdapter` and `OpenSpecAdapter` are
   returned.
2. **Given** the same mixed repo, **When**
   `resolve_for_path(specs/001-foo/spec.md)` is called, **Then** the
   result is `(SpecKitAdapter, "001-foo")`. **When**
   `resolve_for_path(openspec/changes/bar/proposal.md)` is called,
   **Then** the result is `(OpenSpecAdapter, "bar")`.

---

### User Story 5 — Yolo Rejects OpenSpec Features Cleanly (Priority: P3)

An operator invoking yolo against an OpenSpec change gets a clean
error pointing at OpenSpec's own `/opsx:apply` flow rather than a
stack trace or a partial run.

**Why this priority**: Yolo compatibility is not required for v1, but
a confusing failure mode is worse than a clear rejection.

**Independent Test**: Invoke yolo entry with a path resolving to
`OpenSpecAdapter`. Assert the process exits with a non-zero status and
the documented error message.

**Acceptance Scenarios**:

1. **Given** an OpenSpec change path, **When** yolo is invoked against
   it, **Then** yolo exits with the documented error message naming
   the adapter and pointing at OpenSpec's native workflow. No stage
   events are recorded.

---

### Edge Cases

- Active OpenSpec change with empty `specs/` subdirectory and missing
  `design.md`: adapter returns `NormalizedArtifacts` with `"plan"`
  filename key pointing at `design.md` but the file marker absent;
  the `plan` kind reports "not started" rather than "not applicable."
- OpenSpec change whose `tasks.md` uses free-form task IDs (no `T\d+`
  convention): adapter assigns synthetic IDs. Task bodies are
  preserved verbatim.
- Repo with `openspec/` directory but no `openspec/changes/` and no
  `openspec/specs/`: `OpenSpecAdapter.detect` returns True (the
  `openspec/` marker is sufficient) and `list_features` returns `[]`.
- Archived change directory passed directly to `compute_flow_state`:
  `resolve_for_path` returns `None`. Flow state reports the path as
  unrecognized.
- Path outside any adapter's scope (random file in `/tmp`):
  `resolve_for_path` returns `None`. Flow state falls through to its
  existing "no feature at this path" behavior.
- Stub adapter registered twice with the same adapter name: registry
  registration is idempotent; the second registration is a no-op.

## Requirements *(mandatory)*

### Functional Requirements

#### Adapter interface additions

- **FR-001**: `SddAdapter` MUST gain a new non-abstract method
  `ordered_stage_kinds() -> list[str]`. The default implementation
  returns the v1 canonical list
  `["spec", "plan", "tasks", "implementation", "review_spec",
  "review_code", "review_pr", "ship"]`. Adapters MAY override to
  return a subset in their native order.
- **FR-002**: `SddAdapter` MUST gain a new non-abstract method
  `supports(capability: str) -> bool`. Default implementation returns
  `False` for any capability. Each concrete adapter overrides to
  declare the capabilities it supports from the v1 vocabulary
  `{"lanes", "yolo", "review_code", "review_pr", "adoption"}`.
  Unknown capability strings MUST return `False`.
- **FR-003**: `StageProgress` MUST gain a `kind: str` field. The
  field is required to be one of the values returned by the adapter's
  `ordered_stage_kinds()`. Existing Phase 1 `StageProgress`
  consumers MUST continue to work (the field is additive and has no
  default-changing effect on existing serialization).
- **FR-004**: The ABC stays binary-compatible: only additive methods
  and fields are introduced. Phase 1 `SpecKitAdapter` MUST continue to
  pass `isinstance(obj, SddAdapter)` after Phase 2.

#### OpenSpec adapter

- **FR-005**: Introduce `OpenSpecAdapter` as a concrete subclass of
  `SddAdapter`. It lives in the `sdd_adapter` package (see FR-019).
- **FR-006**: `OpenSpecAdapter.detect(repo_root)` MUST return `True`
  when `repo_root / "openspec"` exists and is a directory. It returns
  `False` otherwise. See brainstorm §5.1.
- **FR-007**: `OpenSpecAdapter.list_features(repo_root,
  include_archived=False)` MUST enumerate every directory under
  `repo_root / "openspec" / "changes"` that is not `archive/`, each
  as a `FeatureHandle` with `feature_id = <slug>`,
  `display_name = <slug>`, `root_path` pointing at the change
  directory, and `adapter_name = "openspec"`.
- **FR-008**: When `include_archived=True`, `list_features` MUST also
  return handles for each directory under
  `openspec/changes/archive/`. Archived handles MUST carry
  `feature_id = <slug>` (the slug portion only; the date prefix
  `YYYY-MM-DD-` is stripped). Archived handles MUST be distinguishable
  from active handles via a field on `FeatureHandle` (e.g.,
  `archived: bool = False` or equivalent, to be finalized in
  `plan.md`).
- **FR-009**: `OpenSpecAdapter.load_feature(handle)` MUST return a
  `NormalizedArtifacts` with:
  - `filenames = {"spec": "proposal.md", "plan": "design.md",
    "tasks": "tasks.md"}`. Review filename keys MUST be absent.
  - Raw artifact path map covering `proposal.md`, `design.md`,
    `tasks.md`, and any files found under the change's `specs/`
    subdirectory.
  - Parsed task list from `tasks.md` as `NormalizedTask` instances.
    Task IDs MUST be derived from explicit IDs if present, otherwise
    synthesized as `<feature_id>#<NN>` where `NN` is the 1-indexed
    checkbox position.
  - `review_evidence` defaulted to every sub-evidence `exists=False`.
  - `worktree_lanes = []`.
  - `linked_brainstorms` populated if any `brainstorm.md` sibling is
    present in the change directory, matching the spec-kit convention.
- **FR-010**: `OpenSpecAdapter.compute_stage(artifacts)` MUST return
  `StageProgress` entries covering at least `spec`, `plan`, and
  `implementation` kinds, with status derived from artifact presence
  and task completion. Review kinds (`review_spec`, `review_code`,
  `review_pr`) MAY be omitted from the result or MUST be returned with
  a status indicating the capability does not apply. `ship` kind MUST
  only appear for features resolved from archived paths (only reachable
  when `include_archived=True`).
- **FR-011**: `OpenSpecAdapter.id_for_path(path, repo_root=None)` MUST
  resolve any path under `repo_root/openspec/changes/<slug>/` to
  `<slug>`. Paths under `openspec/changes/archive/` MUST return `None`
  unless `include_archived=True` is threaded through (v1 default
  behavior: archive paths return `None`).
- **FR-012**: `OpenSpecAdapter.supports(capability)` MUST return:
  - `"lanes"` -> `False`
  - `"yolo"` -> `False`
  - `"review_code"` -> `False`
  - `"review_pr"` -> `False`
  - `"adoption"` -> `True` (adoption records are Orca-native, not
    adapter-owned; see brainstorm §12)
  - unknown -> `False`

#### Spec-kit adapter updates

- **FR-013**: `SpecKitAdapter` MUST set its filename map using the v1
  semantic keys. The exact map:
  ```
  {
      "spec": "spec.md",
      "plan": "plan.md",
      "tasks": "tasks.md",
      "review_spec": "review-spec.md",
      "review_code": "review-code.md",
      "review_pr": "review-pr.md",
  }
  ```
  Any Phase 1 constants using dashed keys (`"review-spec"` etc.) MUST
  be migrated to underscored semantic keys. A back-compat alias for
  dashed keys is optional and decided in `plan.md`.
- **FR-014**: `SpecKitAdapter.supports(capability)` MUST return:
  - `"lanes"` -> `True`
  - `"yolo"` -> `True`
  - `"review_code"` -> `True`
  - `"review_pr"` -> `True`
  - `"adoption"` -> `True`
  - unknown -> `False`
- **FR-015**: `SpecKitAdapter.compute_stage` MUST attach a `kind` to
  every returned `StageProgress` using the following mapping:
  - `brainstorm` -> `spec` (the brainstorm is the early spec artifact
    in spec-kit's flow)
  - `specify` -> `spec`
  - `plan` -> `plan`
  - `tasks` -> `tasks`
  - `assign` -> `tasks` (folded because `decompose` is not a v1 kind)
  - `implement` -> `implementation`
  - `review-spec` -> `review_spec`
  - `review-code` -> `review_code`
  - `review-pr` -> `review_pr`
  - `ship` / post-merge -> `ship`
- **FR-016**: `SpecKitAdapter` output for spec-kit fixtures MUST
  remain byte-identical to Phase 1 output, except for the added
  `kind` field on `StageProgress`. See FR-027 for the regression gate.

#### Registry

- **FR-017**: Introduce `AdapterRegistry` in the `sdd_adapter` package.
  The registry MUST expose:
  - `register(adapter: SddAdapter) -> None`. Idempotent by
    `adapter.name`; registering the same name twice is a no-op.
  - `adapters() -> tuple[SddAdapter, ...]`. Returns an immutable
    snapshot in registration order.
  - `resolve_for_path(path: Path, repo_root: Path | None = None) ->
    tuple[SddAdapter, str] | None`. Iterates adapters in registration
    order; returns the first `(adapter, feature_id)` whose
    `id_for_path` returns non-None. Returns `None` if no adapter
    claims the path.
  - `resolve_for_feature(repo_root: Path, feature_id: str) ->
    tuple[SddAdapter, FeatureHandle] | None`. Iterates adapters;
    returns the first whose `list_features(repo_root)` includes a
    handle with matching `feature_id`. Returns `None` otherwise.
  - `reset_to_defaults() -> None`. Test helper that clears the
    registry and re-registers the in-tree adapters.
- **FR-018**: The registry MUST be populated at import time by
  `sdd_adapter/__init__.py` registering `SpecKitAdapter()` first and
  `OpenSpecAdapter()` second. Registration order matters for
  `resolve_for_path` but does not produce conflicts because the two
  adapters' path scopes (`specs/` vs `openspec/`) are mutually
  exclusive.

#### Module layout and singleton deprecation

- **FR-019**: `src/speckit_orca/sdd_adapter.py` MUST be restructured
  into a package `src/speckit_orca/sdd_adapter/` with modules
  `base.py` (ABC + dataclasses), `spec_kit.py` (`SpecKitAdapter`),
  `openspec.py` (`OpenSpecAdapter`), `registry.py` (`AdapterRegistry`
  and module-level registry instance), and `__init__.py` re-exporting
  the full Phase 1 public surface plus the Phase 2 additions.
- **FR-020**: Every Phase 1 import path (e.g., `from
  speckit_orca.sdd_adapter import SpecKitAdapter,
  NormalizedArtifacts, SddAdapter, FeatureHandle`) MUST continue to
  resolve after the restructure. The `__init__.py` re-exports every
  public name.
- **FR-021**: The Phase 1 `_SPEC_KIT_ADAPTER` module-level attribute
  on `flow_state` MUST remain importable and writable for one
  release. It MUST be marked deprecated in code (docstring or
  `DeprecationWarning` on access, decided in `plan.md`). Its value
  MUST stay in sync with the registry's `SpecKitAdapter` instance so
  tests that monkeypatch it continue to work.
- **FR-022**: `flow_state.collect_feature_evidence` MUST obtain its
  adapter via `registry.resolve_for_path` rather than the direct
  singleton reference. Fallback behavior for paths outside any
  adapter's scope MUST preserve Phase 1 behavior (no crash; falls
  through to the current "no feature at this path" code path).

#### Mixed-repo behavior

- **FR-023**: In a repo with both `specs/` and `openspec/` trees,
  `resolve_for_repo(root)` MUST return both adapters in registration
  order. `resolve_for_path` MUST return the correct adapter per path
  without ambiguity (spec-kit paths resolve to `SpecKitAdapter`;
  OpenSpec paths resolve to `OpenSpecAdapter`).
- **FR-024**: `compute_flow_state` on a mixed-repo root MUST
  enumerate both adapter's features and return them in a single
  `FlowStateResult` without de-duplication (the namespaces do not
  overlap) and without crashing.

#### Yolo, matriarch, TUI

- **FR-025**: Yolo entry MUST call `registry.resolve_for_path` on its
  target. If the resolved adapter's `supports("yolo")` returns
  `False`, yolo MUST exit with a non-zero status and print the
  documented message:
  ```
  error: yolo runtime only supports adapters that declare
  supports("yolo") == True. This path is managed by the
  '<adapter-name>' adapter. See `/speckit.orca.doctor` for detected
  formats.
  ```
  No stage events are recorded, no mailbox writes are performed.
- **FR-026**: Matriarch MUST remain read-only with respect to
  OpenSpec features. Matriarch MAY display them in status views (via
  flow_state) but MUST NOT attempt to register lanes, issue
  readiness gates, or coordinate stage transitions for features
  whose resolving adapter returns `supports("lanes") == False`.
  Phase 2 does not modify matriarch code beyond whatever minimum is
  required to honor the `supports` probe (which matriarch may already
  honor implicitly because OpenSpec features have no lanes registered;
  this FR is an explicit no-regression clause).
- **FR-027**: The 018 TUI MUST continue to render the spec-kit
  fixtures identically after Phase 2 lands. Phase 2 MUST NOT edit TUI
  code. A smoke test covers this (see FR-031).

#### Testing

- **FR-028**: Add a hand-authored OpenSpec fixture repo at
  `tests/fixtures/openspec_repo/` containing at minimum:
  - Two active changes under `openspec/changes/`: one with full
    files (`proposal.md`, `design.md`, `tasks.md`, `specs/<cap>.md`)
    and one minimal (`proposal.md`, `tasks.md` only).
  - One archived change under `openspec/changes/archive/
    YYYY-MM-DD-<slug>/`.
  - One capability under `openspec/specs/<cap>/spec.md` (the
    persistent store).
  - A `README.md` in the fixture directory documenting that the
    layout is hand-authored from the OpenSpec README + workflows
    doc, and flagging any TBC items against a real OpenSpec repo.
  - A minimal `.git/` marker directory so repo-root detection works.
- **FR-029**: Snapshot tests MUST cover:
  - `OpenSpecAdapter.detect` on the fixture returns True.
  - `OpenSpecAdapter.list_features` returns exactly the two active
    handles when `include_archived=False`. With `include_archived=
    True`, it also returns the archived handle.
  - `OpenSpecAdapter.load_feature` on the full change returns a
    `NormalizedArtifacts` with the expected filename map, non-empty
    tasks, `review_evidence` all False, `worktree_lanes` empty.
  - `OpenSpecAdapter.compute_stage` returns stages with kinds drawn
    from the v1 vocabulary.
  - `OpenSpecAdapter.id_for_path` on a known active path returns the
    slug; on an archive path returns None.
- **FR-030**: Registry tests MUST cover `register` idempotency,
  `resolve_for_path` on spec-kit paths, on OpenSpec paths, and on
  unrelated paths; `resolve_for_repo` on both single-format and
  mixed-format fixtures; and `reset_to_defaults`.
- **FR-031**: A parity test MUST run the spec-kit fixture tree
  through the Phase 2 registry and assert the `FeatureEvidence`
  output is byte-identical to Phase 1 golden snapshots except for
  the added `StageProgress.kind` field. This is the no-regression
  gate referenced in FR-016.
- **FR-032**: An anti-leak test MUST assert that
  `src/speckit_orca/flow_state.py` contains no OpenSpec filename
  literals (`"proposal.md"`, `"design.md"`, `"openspec"`) and no
  spec-kit filename literals beyond what Phase 1 permits.
- **FR-033**: A yolo-rejection test MUST invoke yolo entry against
  an OpenSpec fixture path and assert the documented error message
  and non-zero exit status.
- **FR-034**: Existing Phase 1 tests MUST pass unchanged except for
  the single allowed case where `_SPEC_KIT_ADAPTER` monkeypatching
  needs a minimum-necessary update due to the alias layer (decided
  in `plan.md`). No Phase 1 assertion semantics change.

### Non-functional Requirements

- **NFR-001**: `OpenSpecAdapter.detect(repo_root)` plus
  `list_features(repo_root, include_archived=False)` MUST complete
  in under 200 milliseconds on a repo with 100 active changes (no
  archived changes scanned when `include_archived=False`). Measured
  on the reference developer environment (Ubuntu on WSL2, SSD-backed
  filesystem).
- **NFR-002**: No new runtime dependencies. Phase 2 MUST NOT add
  any import to `pyproject.toml`. Parsing uses stdlib only (`pathlib`,
  `re`, existing markdown/checkbox helpers).
- **NFR-003**: Public API stability for adapter authors. Every name
  exported by `speckit_orca.sdd_adapter` in Phase 1 (ABC, dataclasses,
  `SpecKitAdapter`) MUST remain importable from the same path after
  Phase 2. Adding fields or methods is allowed; renaming or removing
  is not.
- **NFR-004**: `flow_state.collect_feature_evidence` latency MUST NOT
  regress by more than 5 percent on spec-kit fixtures after the
  registry wire-up. Registry lookup is an in-memory iteration over
  two adapters; the overhead is negligible but must be measured.
- **NFR-005**: The `sdd_adapter/` package MUST be import-safe in
  isolation. Importing `speckit_orca.sdd_adapter.base` alone MUST NOT
  trigger `SpecKitAdapter` or `OpenSpecAdapter` construction. Only
  `__init__.py` builds and registers the in-tree adapters.

## Out of Scope

The following are explicitly out of scope for 019 and must not be
introduced by review comments:

- BMAD adapter (Phase 3+).
- Taskmaster adapter (Phase 3+).
- OpenSpec adoption records. Adoption (017) stays Orca-native and
  format-agnostic; no OpenSpec-specific adoption flow lands here.
- Yolo running OpenSpec features. Rejection only.
- Matriarch managing OpenSpec features (lane registration, readiness
  gates, mailbox coordination). Read-only display via flow_state is
  fine; coordination is not.
- Additional stage kinds beyond the v1 vocabulary
  (`spec, plan, tasks, implementation, review_spec, review_code,
  review_pr, ship`). `decompose`, `ideate`, and other kinds floated
  in the brainstorm are deferred.
- Removal of the `_SPEC_KIT_ADAPTER` singleton. Deprecated in v1,
  removal is a future spec.
- Write support on `OpenSpecAdapter`. No archive, sync, or propose
  operations.
- Cross-format review orchestration. `review-spec`, `review-code`,
  `review-pr` stay spec-kit-only.
- `orca convert` between formats.
- Installer integration for OpenSpec.
- TUI OpenSpec-awareness beyond passthrough rendering. 018 owns any
  OpenSpec-specific TUI work.
- Plugin system for third-party out-of-tree adapters.
- `.specify/orca/` rename or relocate (grandfathered).

## Dependencies and Prerequisites

- **016 Phase 1** merged to `main` (landed).
- **PR #62 (Phase 1.5)** merged to `main` — normalized review
  evidence and worktree lane types must be in place.
- No external API dependencies. No new network calls, no new
  packages, no new services.
- 018 TUI is NOT a prerequisite and NOT a dependency of 019. They
  proceed in parallel.
- 017 brownfield adoption is orthogonal.

## Risks and Mitigations

Imported from brainstorm §20.

1. **OpenSpec format is moving fast.** Upstream may change file
   conventions between ship date and user adoption.
   *Mitigation*: parser is narrow; note upstream version targeted in
   the fixture README; parser patches do not require interface
   changes.
2. **Stage-kind vocabulary is wrong.** The v1 eight-kind enum is a
   guess.
   *Mitigation*: kinds are additive; v1 mappings stay stable; Phase 3
   (BMAD/Taskmaster) stress-tests the enum and can extend it.
3. **Registry migration breaks Phase 1 tests.** Monkeypatching
   `_SPEC_KIT_ADAPTER` must keep working.
   *Mitigation*: keep the attribute live and synced to the registry
   for one release; migrate tests lazily.
4. **018 TUI diverges.** If 018 lands before 019 and hardcodes stage
   names, coordination cost spikes.
   *Mitigation*: decisions §6 and FR-027 lock the contract; 019
   smoke-tests TUI rendering of spec-kit unchanged.
5. **Matriarch silently misbehaves on OpenSpec features in mixed
   repos.** An operator may see features stuck "in flight" without
   explanation.
   *Mitigation*: FR-026 locks matriarch to silent degradation;
   document the limitation in the adapter catalog; defer adapter-
   aware matriarch to a follow-up spec.
6. **Yolo rejection is too blunt.** Operators who want yolo on
   OpenSpec get a hard stop.
   *Mitigation*: rejection is a single configurable gate keyed on
   `supports("yolo")`; a future spec can loosen it without touching
   019.
7. **OpenSpec adapter sees low adoption.** We build it and nobody
   uses OpenSpec.
   *Mitigation*: the registry, stage-kind, and `supports` scaffolding
   pay for themselves independent of OpenSpec usage. BMAD and
   Taskmaster reuse all of it.
8. **OpenSpec format understanding is wrong in ways fixture testing
   does not catch.** We authored the fixture from README + workflow
   doc; the real on-disk shape may differ (front-matter, headings,
   delta format).
   *Mitigation*: the fixture README documents TBC items; a follow-up
   task pulls a real OpenSpec example repo and diffs; patches land on
   the parser only, not the interface.

## Acceptance Criteria

High-level gates that map onto the user stories and FR clusters.
These become the spec-level review checklist.

- **AC-001 (US1)**: `compute_flow_state` on an OpenSpec change
  fixture path returns a `FlowStateResult` with `adapter_name ==
  "openspec"`, `filenames["spec"] == "proposal.md"`, and a task
  summary whose counts match the fixture.
- **AC-002 (US2, FR-003, FR-010, FR-015)**: Every `StageProgress`
  returned by any in-tree adapter carries a `kind` drawn from
  `SddAdapter.ordered_stage_kinds()`. The v1 vocabulary matches the
  decision list.
- **AC-003 (US3, FR-017, FR-018)**: A stub adapter registered at
  test time can own paths that `flow_state` dispatches through
  without edits to `flow_state.py`, `matriarch.py`, or `yolo.py`.
- **AC-004 (US4, FR-023, FR-024)**: A mixed-repo fixture resolves
  spec-kit paths to `SpecKitAdapter` and OpenSpec paths to
  `OpenSpecAdapter` without conflict. Both adapters appear in
  `resolve_for_repo`.
- **AC-005 (US5, FR-025, FR-033)**: Yolo invoked on an OpenSpec
  fixture path exits non-zero with the documented message. No events
  are recorded.
- **AC-006 (FR-016, FR-031)**: `FeatureEvidence` output for spec-kit
  fixtures is byte-identical to Phase 1 golden snapshots except for
  the new `StageProgress.kind` field.
- **AC-007 (FR-020, FR-021)**: Every Phase 1 import and every
  Phase 1 test passes after Phase 2, with at most one minimum-
  necessary monkeypatch update for `_SPEC_KIT_ADAPTER`.
- **AC-008 (FR-028, FR-029)**: The hand-authored OpenSpec fixture
  exists, is documented, and is covered by snapshot tests for every
  `OpenSpecAdapter` method.
- **AC-009 (FR-032)**: No OpenSpec filename literals leak into
  `flow_state.py`. Anti-leak test passes.
- **AC-010 (NFR-001)**: `detect + list_features` under 200 ms on a
  100-change fixture.
- **AC-011 (NFR-002)**: `pyproject.toml` unchanged by 019 (no new
  runtime dependencies).
- **AC-012 (FR-026, FR-027)**: Matriarch and TUI code untouched by
  019. Smoke test confirms spec-kit rendering unchanged.

## Open Questions

Questions that remain after the 8 binding decisions above. Each has
a deadline indicating where resolution must land.

1. **`FeatureHandle.archived` field shape.** Is it a boolean, an
   enum (`Status.ACTIVE | Status.ARCHIVED`), or encoded into
   `feature_id`? FR-008 allows any of these. *Deadline: before
   `plan.md`.*
2. **Dashed vs underscored filename key aliases.** FR-013 migrates
   spec-kit to underscored keys (`"review_spec"`). Do we ship a
   back-compat alias for the dashed forms, or is it a hard break
   for any external reader that grepped the dict? *Deadline: before
   `plan.md`.*
3. **`_SPEC_KIT_ADAPTER` deprecation mechanism.** Docstring-only
   note, runtime `DeprecationWarning` on access, or both? *Deadline:
   before `plan.md`.*
4. **`compute_stage` behavior for OpenSpec review kinds.** FR-010
   allows either omission or "not applicable" status. Which do we
   ship? *Deadline: before `tasks.md`.*
5. **Task ID synthesis format.** `<feature_id>#NN` per FR-009 is
   the leaning decision. Is `#` the right separator given matriarch
   or TUI might use it in URLs? *Deadline: before `tasks.md`.*
6. **`design.md` missing vs empty.** Does an absent `design.md`
   produce a `plan` kind status of "not started" (brainstorm §17
   Q8 leaning) or "not applicable"? *Deadline: before `tasks.md`.*
7. **Parity snapshot format.** Are Phase 1 golden snapshots already
   versioned in a format Phase 2 can diff against, or do we need to
   regenerate with the new `kind` field first? *Deadline: before
   `tasks.md`; may be handled as a plan-phase investigation task.*
8. **Real OpenSpec fixture follow-up.** When do we diff the hand-
   authored fixture against a real OpenSpec repo? Is that a task in
   019 or a follow-up spec? *Deferrable. Plan-phase decision.*
9. **Matriarch display tag for OpenSpec features.** Brainstorm
   Risk 5 mitigation suggests showing `adapter: openspec` in
   matriarch's dashboard row. Is that in scope for 019 (display-only,
   honors the read-only contract) or deferred? *Deferrable.*
10. **`ordered_stage_kinds` vs `stage_kinds` naming.** Brainstorm
    §17 Q15. *Deferrable; plan-phase cosmetic.*

---

**Brainstorm references**: §0 (scope), §1 (why the second adapter is
hard), §2 (OpenSpec format essentials), §3 (semantic misalignment,
stage kinds), §4 (proposed interface changes), §5 (detection), §6
(feature identity and archived changes), §7 (task model), §8 (review
evidence), §9 (worktree lanes), §10 (registry model), §11 (mixed
repos), §12 (brownfield), §13 (yolo), §14 (TUI), §15 (matriarch),
§16 (test strategy), §17 (open questions), §18 (scope discipline),
§20 (risks).
