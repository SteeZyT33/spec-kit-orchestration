# Tasks: OpenSpec Adapter — Phase 2 of the Multi-SDD Layer

**Input**: `specs/019-openspec-adapter/spec.md`, `specs/019-openspec-adapter/plan.md`, `specs/019-openspec-adapter/brainstorm.md`
**Predecessors**: 016 Phase 1 (landed), PR #62 Phase 1.5 (landed)
**TDD**: Every `[IMPL]` task is preceded by at least one `[TEST]` task that is red against the prior commit. Every `[REFACTOR]` is preceded by either a `[PARITY-GATE]` task (already green) or a regression test.

## Phase 1.5 to this phase

016 Phase 1.5 (PR #62) is the binding prerequisite. It introduced `NormalizedReviewEvidence` and `NormalizedWorktreeLane` so adapters never need to import `flow_state` internals. Phase 2 only adds; it does not retract Phase 1.5.

The spec's eight binding decisions (spec §Clarifications / decisions recorded) are fixed:

1. v1 stage-kind vocabulary is `{spec, plan, tasks, implementation, review_spec, review_code, review_pr, ship}`.
2. Filename keys are semantic (`"spec"` -> `proposal.md` for OpenSpec).
3. Archived OpenSpec changes are hidden by default; slug is the stable ID.
4. `_SPEC_KIT_ADAPTER` stays importable for one release, marked deprecated.
5. Matriarch ignores OpenSpec features (`supports("lanes") == False`).
6. 018 TUI needs no Phase 2 changes.
7. OpenSpec fixture is hand-authored.
8. Capability vocabulary v1 is closed: `{lanes, yolo, review_code, review_pr, adoption}`.

Plus the three plan-level resolutions (plan §Research §2):

- Q1: `FeatureHandle.archived: bool = False`.
- Q2: underscored filename keys are canonical; one-release dashed-key read alias in `flow_state.py` only, emits `DeprecationWarning`.
- Q3: `_SPEC_KIT_ADAPTER` deprecation via PEP 562 `__getattr__` on `flow_state`, once-per-process `DeprecationWarning`.

Do not relitigate any of the above in implementation. Open questions Q4-Q10 from the spec are deferred per plan §Research §3 and surfaced as inline TBC notes in the relevant tasks below.

## What's out of scope

Restated from the spec's §Out of Scope. The following MUST NOT land in this phase:

- BMAD or Taskmaster adapters.
- OpenSpec adoption records (017 stays Orca-native).
- Yolo running OpenSpec features (rejection only).
- Matriarch managing OpenSpec features beyond passive read-only display.
- Stage kinds beyond the v1 eight-kind enum.
- Removal of the `_SPEC_KIT_ADAPTER` singleton (deprecated only).
- Write support on `OpenSpecAdapter` (no archive, sync, propose).
- Cross-format review orchestration.
- `orca convert`, installer integration for OpenSpec.
- TUI OpenSpec-awareness beyond passthrough rendering.
- Plugin system for third-party out-of-tree adapters.
- `.specify/orca/` rename.

---

## Sub-phase A: Core interface extension (additive)

**Goal**: Extend `SddAdapter` with `ordered_stage_kinds()` and `supports()`; add `StageProgress.kind`; migrate `SpecKitAdapter` to underscored filename keys; baseline the parity gate. Zero observable change beyond the additive `kind` field and the deprecation warning on dashed keys.

**Target files**: `src/speckit_orca/sdd_adapter.py`, `src/speckit_orca/flow_state.py`, `tests/test_sdd_adapter.py`, `tests/test_flow_state.py`, `tests/test_flow_state_parity.py` (new), `tests/fixtures/flow_state_snapshots/*.json` (new).

### T001 [A] [PARITY-GATE] Baseline pre-Phase-2 golden snapshots
**Files:** `tests/fixtures/flow_state_snapshots/<feature_id>.json` (new, one per `specs/*` feature dir on `main`)
**Acceptance:** For every `specs/<feature_id>/` containing a `spec.md`, a JSON file exists serialized with `json.dumps(..., indent=2, sort_keys=True)`, absolute paths normalized to `<FIXTURE_ROOT>`, captured from `python -m speckit_orca.flow_state <feature_dir> --format json` on the pre-Phase-2 `main` commit.
**Depends on:** none

### T002 [A] [TEST] Assert `SddAdapter.ordered_stage_kinds` exists with default
**Files:** `tests/test_sdd_adapter.py`
**Acceptance:** `SddAdapter.ordered_stage_kinds(self)` returns `["spec", "plan", "tasks", "implementation", "review_spec", "review_code", "review_pr", "ship"]` on a minimal subclass that does not override it. Fails on the current ABC.
**Depends on:** none

### T003 [A] [TEST] Assert `SddAdapter.supports` default returns False
**Files:** `tests/test_sdd_adapter.py`
**Acceptance:** A minimal subclass that does not override `supports` returns `False` for every capability in `{"lanes", "yolo", "review_code", "review_pr", "adoption", "anything-else"}`. Fails on the current ABC.
**Depends on:** none

### T004 [A] [IMPL] Add `ordered_stage_kinds` and `supports` to `SddAdapter`
**Files:** `src/speckit_orca/sdd_adapter.py`
**Acceptance:** T002 and T003 pass. Both methods are non-abstract; `ordered_stage_kinds` returns the v1 eight-kind list; `supports(capability)` returns `False`.
**Depends on:** T002, T003

### T005 [A] [TEST] Assert `StageProgress.kind` field is present
**Files:** `tests/test_sdd_adapter.py`
**Acceptance:** `set(f.name for f in fields(StageProgress))` contains `"kind"`. Constructing `StageProgress(stage="specify", status="complete", evidence_sources=[], notes=[], kind="spec")` succeeds. Fails on Phase 1.5 dataclass.
**Depends on:** none

### T006 [A] [IMPL] Add `kind: str` field to `StageProgress`
**Files:** `src/speckit_orca/sdd_adapter.py`
**Acceptance:** T005 passes. `kind` is appended after existing fields. A sentinel default of `""` is allowed during sub-phase A only; T013 removes it.
**Depends on:** T005

### T007 [A] [TEST] Assert `SpecKitAdapter._FILENAME_MAP` uses underscored keys
**Files:** `tests/test_sdd_adapter.py`
**Acceptance:** `SpecKitAdapter._FILENAME_MAP == {"spec": "spec.md", "plan": "plan.md", "tasks": "tasks.md", "review_spec": "review-spec.md", "review_code": "review-code.md", "review_pr": "review-pr.md"}`. Fails on Phase 1's dashed-key map.
**Depends on:** none

### T008 [A] [TEST] Assert SpecKitAdapter maps each semantic key correctly
**Files:** `tests/test_sdd_adapter.py`
**Acceptance:** Per-key assertions: `_FILENAME_MAP["spec"] == "spec.md"`, `["plan"] == "plan.md"`, `["tasks"] == "tasks.md"`, `["review_spec"] == "review-spec.md"`, `["review_code"] == "review-code.md"`, `["review_pr"] == "review-pr.md"`. Brainstorm key (`"brainstorm"`) is NOT in the map (handled separately).
**Depends on:** none

### T009 [A] [IMPL] Land `SpecKitAdapter._FILENAME_MAP` with underscored keys
**Files:** `src/speckit_orca/sdd_adapter.py`
**Acceptance:** T007 and T008 pass. `_FILENAME_MAP` is a class attribute on `SpecKitAdapter`. `NormalizedArtifacts.filenames` is populated from it in `load_feature`.
**Depends on:** T007, T008

### T010 [A] [TEST] Assert `SpecKitAdapter.ordered_stage_kinds` returns native subset
**Files:** `tests/test_sdd_adapter.py`
**Acceptance:** `SpecKitAdapter().ordered_stage_kinds()` returns the eight-kind list in spec-kit's native order. Every entry is a member of the v1 vocabulary.
**Depends on:** T004

### T011 [A] [TEST] Assert `SpecKitAdapter.supports` returns the FR-014 truth table
**Files:** `tests/test_sdd_adapter.py`
**Acceptance:** `SpecKitAdapter().supports(c)` returns `True` for each of `"lanes"`, `"yolo"`, `"review_code"`, `"review_pr"`, `"adoption"`, and `False` for `"unknown"`.
**Depends on:** T004

### T012 [A] [TEST] Assert `SpecKitAdapter.compute_stage` attaches `kind` per FR-015 mapping
**Files:** `tests/test_sdd_adapter.py`
**Acceptance:** On a fixture with brainstorm, spec, plan, tasks, and all three reviews present, `compute_stage` returns `StageProgress` entries whose `kind` matches FR-015: `brainstorm` -> `spec`, `specify` -> `spec`, `plan` -> `plan`, `tasks` -> `tasks`, `assign` -> `tasks`, `implement` -> `implementation`, `review-spec` -> `review_spec`, `review-code` -> `review_code`, `review-pr` -> `review_pr`. (`ship` is not emitted by spec-kit; FR-015 covers it for post-merge only.)
**Depends on:** T006

### T013 [A] [IMPL] SpecKitAdapter overrides `ordered_stage_kinds`/`supports`; `compute_stage` attaches `kind`
**Files:** `src/speckit_orca/sdd_adapter.py`
**Acceptance:** T010, T011, T012 pass. `kind` is set on every `StageProgress` constructed by `SpecKitAdapter.compute_stage`. The sub-phase A sentinel default on `StageProgress.kind` is removed; every construction site sets `kind` explicitly.
**Depends on:** T010, T011, T012

### T014 [A] [TEST] Assert dashed-key filename lookup emits `DeprecationWarning`
**Files:** `tests/test_flow_state.py`
**Acceptance:** Reading `filenames["review-spec"]` (dashed) on a `FeatureEvidence` returned by `compute_flow_state` returns `"review-spec.md"` AND emits one `DeprecationWarning` whose message names the dashed key and points at the underscored canonical. Underscored access (`filenames["review_spec"]`) emits no warning.
**Depends on:** T009

### T015 [A] [IMPL] Add dashed-key read alias in `flow_state.py`
**Files:** `src/speckit_orca/flow_state.py`
**Acceptance:** T014 passes. The alias lives in `flow_state.py`, NOT in `sdd_adapter.py`. The alias is read-only; writes through dashed keys are not supported. Audit grep confirms no Phase 1 internal callsite still reads dashed keys from a `NormalizedArtifacts.filenames` dict.
**Depends on:** T014

### T016 [A] [TEST] Parity-gate scaffold: spec-kit fixtures match snapshots modulo `kind`
**Files:** `tests/test_flow_state_parity.py` (new)
**Acceptance:** For every snapshot in `tests/fixtures/flow_state_snapshots/`, `compute_flow_state(<feature_dir>).to_dict()` matches the snapshot byte-for-byte AFTER stripping every `completed_milestones[*].kind` and `incomplete_milestones[*].kind` field from the live output (the snapshots predate `kind`). Test fails if any non-`kind` field drifts.
**Depends on:** T001, T013, T015

### T017 [A] [PARITY-GATE] Confirm sub-phase A parity holds end-to-end
**Files:** none (verification only)
**Acceptance:** `uv run pytest tests/test_sdd_adapter.py tests/test_flow_state.py tests/test_flow_state_parity.py` is green. Full test suite passes. Record pre/post test count delta.
**Depends on:** T016

---

## Sub-phase B: Registry introduction

**Goal**: Introduce `AdapterRegistry`, route `flow_state.collect_feature_evidence` through it, keep `_SPEC_KIT_ADAPTER` live and synced with a once-per-process `DeprecationWarning` on access. Parity holds with full byte equality (snapshots regenerated to include `kind`).

**Target files**: `src/speckit_orca/sdd_adapter.py`, `src/speckit_orca/flow_state.py`, `tests/test_sdd_adapter_registry.py` (new), `tests/test_flow_state.py`, `tests/test_flow_state_parity.py`, `tests/fixtures/flow_state_snapshots/*.json`.

### T018 [B] [TEST] Registry `register` is idempotent by adapter name
**Files:** `tests/test_sdd_adapter_registry.py` (new)
**Acceptance:** `AdapterRegistry()` instance; `register(SpecKitAdapter())` then `register(SpecKitAdapter())` results in `len(registry.adapters()) == 1`. A second adapter with a distinct `name` adds an entry; total is 2.
**Depends on:** T017

### T019 [B] [TEST] `resolve_for_path` returns `(SpecKitAdapter, feature_id)` for spec-kit paths
**Files:** `tests/test_sdd_adapter_registry.py`
**Acceptance:** Synthetic `specs/042-widget/spec.md` fixture; `registry.resolve_for_path(fixture / "specs/042-widget/spec.md", repo_root=fixture)` returns `(SpecKitAdapter_instance, "042-widget")`.
**Depends on:** T017

### T020 [B] [TEST] `resolve_for_path` returns `None` for unrelated paths
**Files:** `tests/test_sdd_adapter_registry.py`
**Acceptance:** `registry.resolve_for_path(Path("/tmp/nowhere/file.md"))` returns `None`.
**Depends on:** T017

### T021 [B] [TEST] `resolve_for_feature` returns matching `(adapter, FeatureHandle)`
**Files:** `tests/test_sdd_adapter_registry.py`
**Acceptance:** Synthetic repo with `specs/001-foo/spec.md`; `registry.resolve_for_feature(repo_root, "001-foo")` returns `(SpecKitAdapter_instance, FeatureHandle(feature_id="001-foo", ...))`. Returns `None` for `"999-missing"`.
**Depends on:** T017

### T022 [B] [TEST] `resolve_for_repo` returns the adapter list whose `detect` is True
**Files:** `tests/test_sdd_adapter_registry.py`
**Acceptance:** Single-format spec-kit fixture; `registry.resolve_for_repo(repo_root)` returns a tuple containing exactly the `SpecKitAdapter` instance. Empty-repo fixture returns `()`.
**Depends on:** T017

### T023 [B] [TEST] `reset_to_defaults` restores in-tree adapters
**Files:** `tests/test_sdd_adapter_registry.py`
**Acceptance:** Register a stub adapter; call `registry.reset_to_defaults()`; `registry.adapters()` matches the post-import default. Stub is gone.
**Depends on:** T017

### T024 [B] [IMPL] Add `AdapterRegistry` class to `sdd_adapter.py`
**Files:** `src/speckit_orca/sdd_adapter.py`
**Acceptance:** T018-T023 pass. Surface: `register`, `adapters`, `resolve_for_path(path, repo_root=None)`, `resolve_for_feature(repo_root, feature_id)`, `resolve_for_repo(repo_root)`, `reset_to_defaults`. Module-level `registry` instance is built at import time and pre-populated with `SpecKitAdapter()`.
**Depends on:** T018, T019, T020, T021, T022, T023

### T025 [B] [TEST] `flow_state.collect_feature_evidence` routes through registry
**Files:** `tests/test_flow_state.py`
**Acceptance:** Register a `SpyAdapter` subclass of `SpecKitAdapter` via `registry.register` (or via `monkeypatch.setattr(registry, "_adapters", ...)`); call `compute_flow_state` on a fixture; assert spy's `load_feature` was invoked. The pre-Phase-2 monkeypatch on `_SPEC_KIT_ADAPTER` MUST also still work (FR-021); a sibling assertion verifies that path.
**Depends on:** T024

### T026 [B] [IMPL] Switch `flow_state.collect_feature_evidence` to `registry.resolve_for_path`
**Files:** `src/speckit_orca/flow_state.py`
**Acceptance:** T025 passes. Phase-1 fallback for unrecognized paths is preserved (no crash; existing "no feature at this path" code path).
**Depends on:** T025

### T027 [B] [TEST] `_SPEC_KIT_ADAPTER` access via attribute lookup emits `DeprecationWarning`
**Files:** `tests/test_flow_state.py`
**Acceptance:** `import speckit_orca.flow_state as fs; with pytest.warns(DeprecationWarning): _ = fs._SPEC_KIT_ADAPTER` succeeds and emits exactly one warning per process. Subsequent accesses in the same process do NOT emit additional warnings (once-per-process semantics per plan §Research §2 Q3). Documents in a comment that `from speckit_orca.flow_state import _SPEC_KIT_ADAPTER` at module scope is NOT covered by PEP 562 `__getattr__` and therefore does not warn; this is an explicit limitation called out in the plan's sub-phase B Risk #2 mitigation.
**Depends on:** T026

### T028 [B] [IMPL] PEP 562 `__getattr__` on `flow_state` for deprecated singleton
**Files:** `src/speckit_orca/flow_state.py`
**Acceptance:** T027 passes. The module-level `__getattr__` returns the live registry's `SpecKitAdapter` instance and emits `DeprecationWarning` once. Setter logic intercepts `flow_state._SPEC_KIT_ADAPTER = X` to also update the registry so legacy monkeypatches continue to work (FR-021, FR-034).
**Depends on:** T027

### T029 [B] [TEST] Existing `_SPEC_KIT_ADAPTER` monkeypatch still works
**Files:** `tests/test_flow_state.py`
**Acceptance:** `monkeypatch.setattr(flow_state_mod, "_SPEC_KIT_ADAPTER", SpyAdapter())` followed by `compute_flow_state` invokes the spy. This is the FR-034 minimum-necessary update: the existing test from Phase 1.5 keeps working unchanged or with at most a one-line decorator/import shift documented in the test docstring.
**Depends on:** T028

### T030 [B] [REFACTOR] Audit `flow_state.py` for direct `SpecKitAdapter()` constructions
**Files:** `src/speckit_orca/flow_state.py`
**Acceptance:** Grep confirms no `SpecKitAdapter()` constructor calls remain in `flow_state.py` outside the `__getattr__` setter path. Every adapter access goes through `registry`. Sub-phase A tests still green.
**Depends on:** T028

### T031 [B] [PARITY-GATE] Regenerate snapshots with `kind`; assert full byte equality
**Files:** `tests/fixtures/flow_state_snapshots/*.json`, `tests/test_flow_state_parity.py`
**Acceptance:** Snapshots are regenerated against the sub-phase B head (with `kind` populated). The parity test no longer strips `kind`; it asserts byte equality against the regenerated snapshots. `uv run pytest tests/test_flow_state_parity.py` is green.
**Depends on:** T028, T030

---

## Sub-phase C: OpenSpec adapter implementation

**Goal**: Restructure `sdd_adapter.py` into a package; ship `OpenSpecAdapter`; register it in the default registry; gate yolo on `supports("yolo")`.

**Plan risk #2**: package split is SEPARATE from new-adapter work. Tasks T032-T037 land the package split with a thin import shim, NO `OpenSpecAdapter` yet. T038 onward adds the adapter.

**Target files**: `src/speckit_orca/sdd_adapter/{__init__,base,spec_kit,openspec,registry}.py` (new package), `src/speckit_orca/sdd_adapter.py` (shim), `src/speckit_orca/yolo.py`, `tests/test_openspec_adapter.py` (new), `tests/test_yolo.py`, `tests/test_imports.py` (new), `tests/test_sdd_adapter_registry.py`.

### T032 [C] [TEST] Phase-1 import paths resolve after package split
**Files:** `tests/test_imports.py` (new)
**Acceptance:** Imports of `SddAdapter`, `SpecKitAdapter`, `FeatureHandle`, `NormalizedTask`, `StageProgress`, `NormalizedArtifacts`, `NormalizedReviewSpec`, `NormalizedReviewCode`, `NormalizedReviewPr`, `NormalizedReviewEvidence`, `NormalizedWorktreeLane`, `_SPEC_KIT_FILENAMES`, and the `SPEC_KIT_*_FILENAME` constants from `speckit_orca.sdd_adapter` ALL succeed. Each name `is` the corresponding name imported from the new package's submodule.
**Depends on:** T031

### T033 [C] [IMPL] Create `sdd_adapter/` package with `base.py` (ABC + normalized types)
**Files:** `src/speckit_orca/sdd_adapter/__init__.py`, `src/speckit_orca/sdd_adapter/base.py`
**Acceptance:** `base.py` holds `SddAdapter`, `FeatureHandle`, `NormalizedTask`, `StageProgress` (with `kind`), `NormalizedReviewSpec`/`Code`/`Pr`/`Evidence`, `NormalizedWorktreeLane`, `NormalizedArtifacts`. `__init__.py` re-exports everything. Sub-phase B tests still green; T032 still red because `SpecKitAdapter` not yet relocated.
**Depends on:** T032

### T034 [C] [IMPL] Move `SpecKitAdapter` and constants into `sdd_adapter/spec_kit.py`
**Files:** `src/speckit_orca/sdd_adapter/spec_kit.py`, `src/speckit_orca/sdd_adapter/__init__.py`
**Acceptance:** `SpecKitAdapter`, `_FILENAME_MAP`, `_SPEC_KIT_FILENAMES`, `SPEC_KIT_*_FILENAME` constants live in `spec_kit.py`. `__init__.py` re-exports them. Sub-phase B tests green.
**Depends on:** T033

### T035 [C] [IMPL] Move `AdapterRegistry` into `sdd_adapter/registry.py`
**Files:** `src/speckit_orca/sdd_adapter/registry.py`, `src/speckit_orca/sdd_adapter/__init__.py`
**Acceptance:** `AdapterRegistry` lives in `registry.py`. `__init__.py` builds the module-level `registry` and registers `SpecKitAdapter()` first. Sub-phase B tests green.
**Depends on:** T034

### T036 [C] [IMPL] Replace `sdd_adapter.py` with import shim
**Files:** `src/speckit_orca/sdd_adapter.py` (shim)
**Acceptance:** Old `sdd_adapter.py` is reduced to `from speckit_orca.sdd_adapter import *` (or equivalent re-export of every Phase 1 public name) and a deprecation comment. T032 passes. NFR-005 holds: importing `speckit_orca.sdd_adapter.base` alone does NOT trigger any concrete adapter construction (verified by a sub-test under T032 that imports `base` in a fresh subprocess and inspects the registry size).
**Depends on:** T035

### T037 [C] [PARITY-GATE] Confirm package split holds parity end-to-end
**Files:** none (verification)
**Acceptance:** `uv run pytest tests/` is green; T031 parity test still byte-exact; no module-level test required `_SPEC_KIT_ADAPTER` import-statement migration beyond the FR-034-allowed minimum.
**Depends on:** T036

### T038 [C] [TEST] `OpenSpecAdapter.detect` returns True iff `repo_root/openspec/` exists
**Files:** `tests/test_openspec_adapter.py` (new)
**Acceptance:** Synthetic tree with `openspec/` directory: `detect(root)` returns `True`. Without `openspec/`: returns `False`. Empty `openspec/` (no `changes/`, no `specs/`) still returns `True` per spec §Edge Cases.
**Depends on:** T037

### T039 [C] [TEST] `OpenSpecAdapter.list_features` excludes archived by default
**Files:** `tests/test_openspec_adapter.py`
**Acceptance:** Fixture with `openspec/changes/{add-dark-mode,minimal-change,archive/2026-04-01-shipped}/`; `list_features(root)` returns exactly two `FeatureHandle` entries with `feature_id in {"add-dark-mode", "minimal-change"}`. None have `archived=True`.
**Depends on:** T037

### T040 [C] [TEST] `OpenSpecAdapter.list_features(include_archived=True)` includes archived
**Files:** `tests/test_openspec_adapter.py`
**Acceptance:** Same fixture; `list_features(root, include_archived=True)` returns three handles. The archived handle has `feature_id == "shipped"` (date prefix `2026-04-01-` stripped per FR-008) and `archived is True`.
**Depends on:** T037

### T041 [C] [TEST] `FeatureHandle.archived` field defaults to False
**Files:** `tests/test_openspec_adapter.py`
**Acceptance:** `FeatureHandle(...)` without `archived=` constructs with `archived is False`. `set(f.name for f in fields(FeatureHandle))` includes `"archived"`. Sub-phase B tests using positional `FeatureHandle(...)` still pass (field is appended last with a default).
**Depends on:** T037

### T042 [C] [IMPL] Add `archived: bool = False` to `FeatureHandle`
**Files:** `src/speckit_orca/sdd_adapter/base.py`
**Acceptance:** T041 passes; sub-phase B tests still green.
**Depends on:** T041

### T043 [C] [TEST] `OpenSpecAdapter.load_feature` populates `NormalizedArtifacts` per FR-009
**Files:** `tests/test_openspec_adapter.py`
**Acceptance:** On the full active change (`add-dark-mode` with `proposal.md`, `design.md`, `tasks.md`, `specs/dark-mode.md`):
- `filenames == {"spec": "proposal.md", "plan": "design.md", "tasks": "tasks.md"}`. No review keys.
- `artifacts` includes paths for `proposal.md`, `design.md`, `tasks.md`, plus the `specs/dark-mode.md` entry.
- `tasks` non-empty; each `NormalizedTask` has explicit ID if present, else synthesized as `f"{feature_id}#NN"`. (Spec Q5 separator deferred; `#` is the leaning value documented in `openspec.py` docstring.)
- `review_evidence` has every sub-evidence `exists is False`.
- `worktree_lanes == []`.
**Depends on:** T037

### T044 [C] [TEST] `load_feature` handles minimal change with missing `design.md`
**Files:** `tests/test_openspec_adapter.py`
**Acceptance:** On `minimal-change` (only `proposal.md` + `tasks.md`): `load_feature` succeeds; `artifacts["design.md"]` exists in the dict but the file is absent on disk; `tasks` parses correctly. No exception.
**Depends on:** T037

### T045 [C] [TEST] `OpenSpecAdapter.compute_stage` emits `spec`/`plan`/`implementation` kinds
**Files:** `tests/test_openspec_adapter.py`
**Acceptance:** On the full active change, `compute_stage(artifacts)` returns `StageProgress` entries whose `kind` set is a subset of `{"spec", "plan", "implementation"}`. Review kinds are OMITTED entirely (spec Q4 leaning per plan §Design §5: omission over not-applicable status). Asserts `"review_spec"` and `"review_code"` and `"review_pr"` do NOT appear in the returned `kind` set.
**Depends on:** T037

### T046 [C] [TEST] `compute_stage` emits `ship` kind only for archived paths
**Files:** `tests/test_openspec_adapter.py`
**Acceptance:** On an active change: no `ship` kind. On an archived change loaded via `include_archived=True`: a `ship` kind is present. Spec Q6 (`design.md` missing -> "not started" vs "not applicable") is resolved per plan sub-phase C Risk #2 leaning: missing `design.md` produces a `plan` kind with status `"not started"`. Test asserts that exact status string for the minimal-change fixture.
**Depends on:** T044

### T047 [C] [TEST] `OpenSpecAdapter.id_for_path` is stable for active and None for archive
**Files:** `tests/test_openspec_adapter.py`
**Acceptance:** `id_for_path(root / "openspec/changes/add-dark-mode/proposal.md", root)` returns `"add-dark-mode"`. `id_for_path(root / "openspec/changes/archive/2026-04-01-shipped/proposal.md", root)` returns `None` (v1 default per FR-011). Path outside `openspec/changes/`: returns `None`.
**Depends on:** T037

### T048 [C] [TEST] `OpenSpecAdapter.supports` returns the FR-012 truth table
**Files:** `tests/test_openspec_adapter.py`
**Acceptance:** `supports("lanes") is False`, `supports("yolo") is False`, `supports("review_code") is False`, `supports("review_pr") is False`, `supports("adoption") is True`, `supports("anything-else") is False`.
**Depends on:** T037

### T049 [C] [TEST] `OpenSpecAdapter.ordered_stage_kinds` is the v1-vocabulary subset
**Files:** `tests/test_openspec_adapter.py`
**Acceptance:** Every entry of `OpenSpecAdapter().ordered_stage_kinds()` is in the v1 eight-kind list. The subset includes at least `spec`, `plan`, `implementation`, and `ship` (in OpenSpec's native order).
**Depends on:** T037

### T050 [C] [IMPL] Implement `OpenSpecAdapter` in `sdd_adapter/openspec.py`
**Files:** `src/speckit_orca/sdd_adapter/openspec.py`, `src/speckit_orca/sdd_adapter/__init__.py`
**Acceptance:** T038-T040, T043-T049 pass. `OpenSpecAdapter.name == "openspec"`. `__init__.py` registers it second after `SpecKitAdapter`. Docstrings record the spec Q5/Q6 leaning resolutions.
**Depends on:** T038, T039, T040, T042, T043, T044, T045, T046, T047, T048, T049

### T051 [C] [TEST] Default registry contains both adapters in order
**Files:** `tests/test_sdd_adapter_registry.py`
**Acceptance:** After fresh import, `[a.name for a in registry.adapters()] == ["spec-kit", "openspec"]`.
**Depends on:** T050

### T052 [C] [TEST] `resolve_for_path` resolves OpenSpec fixture paths to OpenSpecAdapter
**Files:** `tests/test_sdd_adapter_registry.py`
**Acceptance:** `registry.resolve_for_path(fixture / "openspec/changes/add-dark-mode/proposal.md", fixture)` returns `(OpenSpecAdapter_instance, "add-dark-mode")`.
**Depends on:** T050

### T053 [C] [TEST] Mixed-repo fixture resolves each path to its correct adapter
**Files:** `tests/test_sdd_adapter_registry.py`
**Acceptance:** Mixed fixture (T060) with `specs/001-foo/spec.md` AND `openspec/changes/bar/proposal.md`. `resolve_for_path(specs path)` returns `SpecKitAdapter`. `resolve_for_path(openspec path)` returns `OpenSpecAdapter`. No path resolves to both.
**Depends on:** T050, T060

### T054 [C] [TEST] Yolo rejects non-yolo adapter with documented message
**Files:** `tests/test_yolo.py`
**Acceptance:** Invoking yolo entry against an OpenSpec fixture path exits with non-zero status. Stderr or stdout contains the FR-025 documented message verbatim, naming `'openspec'` and pointing at `/speckit.orca.doctor`. No `.specify/orca/runs/` events written; assert run dir count unchanged before/after.
**Depends on:** T050

### T055 [C] [IMPL] Gate yolo entry on `registry.resolve_for_path` + `supports("yolo")`
**Files:** `src/speckit_orca/yolo.py`
**Acceptance:** T054 passes. Yolo calls `registry.resolve_for_path` first; if the resolved adapter's `supports("yolo")` is False, prints the FR-025 message and exits non-zero before any side effects. Existing yolo behavior on spec-kit paths is unchanged (verified by existing `tests/test_yolo.py` tests staying green).
**Depends on:** T054

### T056 [C] [PARITY-GATE] Confirm sub-phase C parity holds; full suite green
**Files:** none (verification)
**Acceptance:** `uv run pytest tests/` is green; T031 parity test still byte-exact for spec-kit fixtures; record test count delta.
**Depends on:** T055

---

## Sub-phase D: Fixtures, tests, and documentation

**Goal**: Ship the mixed-repo fixture; register a stub adapter test (US3); land the anti-leak and performance tests; update documentation.

**Target files**: `tests/fixtures/openspec_repo/`, `tests/fixtures/mixed_sdd_repo/` (new), `tests/test_sdd_adapter_registry.py`, `tests/test_flow_state.py`, `tests/test_flow_state_anti_leak.py` (new), `tests/test_openspec_adapter.py`, `tests/test_imports.py`, `README.md`, `specs/016-multi-sdd-layer/review.md`.

### T057 [D] [FIXTURE] Author OpenSpec fixture: full active change
**Files:** `tests/fixtures/openspec_repo/openspec/changes/add-dark-mode/{proposal,design,tasks}.md`, `tests/fixtures/openspec_repo/openspec/changes/add-dark-mode/specs/dark-mode.md`
**Acceptance:** Files exist with realistic OpenSpec-shaped content (proposal narrative, design notes, partially-checked tasks list with at least 3 tasks including one explicit ID and one synthesized).
**Depends on:** T056

### T058 [D] [FIXTURE] Author OpenSpec fixture: minimal active change
**Files:** `tests/fixtures/openspec_repo/openspec/changes/minimal-change/{proposal,tasks}.md`
**Acceptance:** Only `proposal.md` and `tasks.md` exist; no `design.md`; no `specs/` subdirectory. Tasks list has at least 2 entries.
**Depends on:** T056

### T059 [D] [FIXTURE] Author OpenSpec fixture: archived change + persistent spec + README + .git marker
**Files:** `tests/fixtures/openspec_repo/openspec/changes/archive/2026-04-01-shipped/{proposal,design,tasks}.md`, `tests/fixtures/openspec_repo/openspec/specs/dark-mode/spec.md`, `tests/fixtures/openspec_repo/README.md`, `tests/fixtures/openspec_repo/.git/HEAD`
**Acceptance:** Archived change has full file set. `openspec/specs/dark-mode/spec.md` exists as the persistent capability store. `README.md` documents the hand-authored nature, the OpenSpec upstream version targeted, and the TBC items called out in plan sub-phase C Risk #1. `.git/HEAD` contains `ref: refs/heads/main` so repo-root detection works.
**Depends on:** T056

### T060 [D] [FIXTURE] Author mixed-repo fixture
**Files:** `tests/fixtures/mixed_sdd_repo/specs/001-foo/{spec,plan,tasks}.md`, `tests/fixtures/mixed_sdd_repo/openspec/changes/bar/{proposal,tasks}.md`, `tests/fixtures/mixed_sdd_repo/.git/HEAD`, `tests/fixtures/mixed_sdd_repo/README.md`
**Acceptance:** Both adapter trees coexist; each is enumerable in isolation. README documents the purpose of the fixture (US4 evidence).
**Depends on:** T056

### T061 [D] [TEST] `resolve_for_repo` on mixed fixture returns both adapters
**Files:** `tests/test_sdd_adapter_registry.py`
**Acceptance:** `[a.name for a in registry.resolve_for_repo(mixed_fixture_root)] == ["spec-kit", "openspec"]`.
**Depends on:** T060

### T062 [D] [TEST] `compute_flow_state` on mixed-repo root enumerates both namespaces
**Files:** `tests/test_flow_state.py`
**Acceptance:** `compute_flow_state(mixed_fixture_root)` returns a `FlowStateResult` listing `001-foo` AND `bar` features with the correct `adapter_name` on each. No de-duplication, no crash. Output round-trips through `to_dict()` without error.
**Depends on:** T060

### T063 [D] [TEST] Stub adapter registered at test time owns paths via registry without core edits
**Files:** `tests/test_sdd_adapter_registry.py`
**Acceptance:** Define a `StubAdapter(SddAdapter)` with `name="stub"`, `detect=lambda root: True`, `id_for_path=lambda p, r=None: "stub-feature" if "stubland" in str(p) else None`, plus minimum methods returning empty/normalized data. Register via `registry.register`; `compute_flow_state` on a `stubland/` path dispatches to the stub. Assert grep on `flow_state.py`, `matriarch.py`, `yolo.py` shows zero string `"stub"` literals (US3 evidence).
**Depends on:** T056

### T064 [D] [TEST] Anti-leak: `flow_state.py` contains no OpenSpec literals
**Files:** `tests/test_flow_state_anti_leak.py` (new)
**Acceptance:** Read `src/speckit_orca/flow_state.py` as text; assert none of `"proposal.md"`, `"design.md"`, `"openspec"`, `'proposal.md'`, `'design.md'`, `'openspec'` appear as substrings. Asserts the FR-032 invariant.
**Depends on:** T056

### T065 [D] [TEST] `detect + list_features` performance under 200ms for 100 changes
**Files:** `tests/test_openspec_adapter.py`
**Acceptance:** Generate a synthetic `openspec/changes/<NNN>/proposal.md` tree with 100 active changes in a `tmp_path`; `time.perf_counter()` around `OpenSpecAdapter().detect(root)` then `list_features(root)`; assert total elapsed < 200 ms (NFR-001). Test is marked with a generous 3x slack note in a comment to avoid CI flake.
**Depends on:** T056

### T066 [D] [TEST] TUI and matriarch imports unchanged after Phase 2
**Files:** `tests/test_imports.py`
**Acceptance:** Importing `speckit_orca.matriarch` and the TUI entrypoint module succeeds; `git diff --stat main -- src/speckit_orca/matriarch.py src/speckit_orca/tui*` is empty (FR-026, FR-027). Test parses the diff via `subprocess.run(["git", "diff", "--stat", "main", "--"...])` and asserts empty output.
**Depends on:** T056

### T067 [D] [TEST] Final test-count delta vs Phase 1.5 baseline
**Files:** none (verification)
**Acceptance:** `uv run pytest tests/ --co -q | tail -1` shows the post-Phase-2 collected count. Record delta vs Phase 1.5 baseline (~482 tests). Confirm zero existing test regressed (no XFAIL or skip introduced for previously-green tests).
**Depends on:** T061, T062, T063, T064, T065, T066

### T068 [D] [DOC] Update README with Phase 2 landed note
**Files:** `README.md`
**Acceptance:** README includes a one-paragraph "OpenSpec adapter (Phase 2)" note pointing at `tests/fixtures/openspec_repo/README.md` and naming the supported v1 detection (`openspec/` marker).
**Depends on:** T067

### T069 [D] [DOC] Update `specs/016-multi-sdd-layer/review.md` with Phase 2 landing pointer
**Files:** `specs/016-multi-sdd-layer/review.md`
**Acceptance:** A single new line under the Phase tracking section: `Phase 2 landed via specs/019-openspec-adapter on <date>; see tasks.md for evidence.` No other content changes.
**Depends on:** T067

### T070 [D] [DOC] Add migration note for `_SPEC_KIT_ADAPTER` deprecation
**Files:** `specs/019-openspec-adapter/migration-notes.md` (new) AND a one-line pointer added to `README.md`
**Acceptance:** Migration note explains the once-per-process `DeprecationWarning`, points consumers at `from speckit_orca.sdd_adapter import registry`, documents the one-release grace period, and explicitly notes the PEP 562 `__getattr__` limitation on `from ... import _SPEC_KIT_ADAPTER` at module scope (T027 docstring cross-reference).
**Depends on:** T068

### T071 [D] [PARITY-GATE] Final golden-snapshot comparison vs pre-Phase-2 head
**Files:** none (verification)
**Acceptance:** `uv run pytest tests/test_flow_state_parity.py -v` is green with full byte equality (the regenerated-with-`kind` snapshots from T031). Re-run on a clean checkout of `main` confirms snapshot generation procedure is reproducible. Document the test count and the parity result in this tasks file's completion checkpoint.
**Depends on:** T067, T068, T069, T070

---

## Completion checkpoint

Phase 2 is done when ALL of the following are true (mirrors plan §Definition of Done):

- [ ] **AC-001** US1: `compute_flow_state` on `tests/fixtures/openspec_repo/openspec/changes/add-dark-mode/` returns `adapter_name == "openspec"`, `filenames["spec"] == "proposal.md"`, task counts match the fixture.
- [ ] **AC-002** US2: every `StageProgress` returned by any in-tree adapter carries a `kind` drawn from that adapter's `ordered_stage_kinds()`.
- [ ] **AC-003** US3: T063 passes with zero edits to `flow_state.py`, `matriarch.py`, `yolo.py`.
- [ ] **AC-004** US4: T053 + T061 + T062 all pass; mixed-repo routes correctly.
- [ ] **AC-005** US5: T054 + T055 pass; yolo on OpenSpec exits non-zero with the documented message and writes no events.
- [ ] **AC-006** Parity: T031 + T071 byte-identical for every spec-kit fixture (with `kind` populated).
- [ ] **AC-007** Imports: T032 + T066 pass; every Phase 1 import resolves; only the FR-034 minimum-necessary monkeypatch update was applied.
- [ ] **AC-008** Fixture: T057 + T058 + T059 + T038-T049 all pass.
- [ ] **AC-009** Anti-leak: T064 passes; no OpenSpec literals in `flow_state.py`.
- [ ] **AC-010** Performance: T065 passes under 200 ms.
- [ ] **AC-011** `pyproject.toml` unchanged by 019 (`git diff main -- pyproject.toml` empty).
- [ ] **AC-012** T066 confirms matriarch and TUI code untouched.

Record final test count, snapshot count, and the parity-gate result before marking the phase complete.

---

## Dependencies and execution order

- Sub-phase A (T001-T017) lands first; it is a pure additive change behind the parity gate.
- Sub-phase B (T018-T031) depends on A; introduces the registry and rewires `flow_state`.
- Sub-phase C (T032-T056) depends on B; package split (T032-T037) lands SEPARATELY from `OpenSpecAdapter` (T038-T056) per plan risk #2.
- Sub-phase D (T057-T071) depends on C; cross-cutting fixtures, anti-leak, performance, docs.

### TDD execution rule

Every `[IMPL]` task lists at least one `[TEST]` task in its `Depends on`. Every `[REFACTOR]` follows a `[PARITY-GATE]` or a regression-locked test. The parity gate (T001 baseline; T016 / T017 sub-phase A; T031 sub-phase B; T037 / T056 sub-phase C; T071 sub-phase D) anchors no-regression at every sub-phase boundary.
