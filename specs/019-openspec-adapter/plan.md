# Implementation Plan: OpenSpec Adapter - Phase 2 of the Multi-SDD Layer

**Branch**: `019-openspec-adapter` | **Date**: 2026-04-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/019-openspec-adapter/spec.md`
**Brainstorm**: [brainstorm.md](./brainstorm.md)
**Predecessors**: 016 Phase 1 (landed), PR #62 Phase 1.5 (landed)

## Summary

Phase 2 lands the second real adapter (`OpenSpecAdapter`), introduces
the minimum registry, stage-kind vocabulary, and `supports(capability)`
probe so "two in-tree adapters" becomes a coherent concept, and leaves
Phase 1 behavior byte-identical for spec-kit callers.

The spec's eight binding decisions are fixed. This plan translates the
34 functional requirements and 12 acceptance criteria into a TDD-ordered
sequence of four sub-phases (A through D), each with its own red-first
test gate, rollback plan, and exit condition.

The hard non-regression gate is the parity snapshot: spec-kit fixture
output must stay byte-identical to Phase 1 golden snapshots except for
the additive `StageProgress.kind` field (FR-016, FR-031, AC-006).

## Technical Context

**Language/Version**: Python 3.10+ (unchanged).
**Dependencies**: zero new runtime deps (NFR-002); stdlib-only parsing.
**Storage**: no new on-disk state.
**Testing**: `pytest`; two new fixture trees, one new adapter test
module, one registry test module, one parity-gate test. Phase 1 test
files untouched except the single `_SPEC_KIT_ADAPTER` monkeypatch
update allowed by FR-034.
**Project Type**: internal refactor + new adapter, plus package-ization
of `sdd_adapter.py` into `sdd_adapter/` (FR-019).
**Performance**: `detect + list_features` under 200 ms for 100 changes
(NFR-001); registry overhead under 5% on spec-kit (NFR-004).
**Constraints**: zero change to CLI, extension manifest, command
prompts, matriarch, yolo (beyond the documented rejection gate), or
TUI code. Every Phase 1 import path stays live (NFR-003).
**Scale**: roughly 600-900 new LOC across the `sdd_adapter/` package,
300-500 LOC of tests, plus two hand-authored fixture trees.

## Constitution Check

Pre-design gates pass: second adapter is provider-agnostic by
definition; the 34 FRs are binding so delivery is spec-driven; the
restructure is narrow and parallel-safe; the parity and anti-leak
tests are the verification gates; the registry is two-entry, no
discovery, no dynamic loading.

Post-design: design stays aligned if the package stays cohesive
(one module per concrete adapter; `base.py` for ABC + normalized
types; `registry.py` for only the registry), `flow_state.py` gains no
OpenSpec literals (FR-032), the parity gate passes, and
`pyproject.toml` stays unchanged (NFR-002, AC-011). No violations to
justify.

## Project Structure

### Documentation (this feature)

```text
specs/019-openspec-adapter/
├── brainstorm.md
├── spec.md
├── plan.md
└── tasks.md           (produced after this plan)
```

No `contracts/`, `data-model.md`, `research.md`, or `quickstart.md` for
Phase 2. The spec plus the Python ABC in `sdd_adapter/base.py` plus the
fixture READMEs carry the full contract surface.

### Source Code (repository root)

```text
src/speckit_orca/
├── sdd_adapter/              # NEW package (replaces sdd_adapter.py content)
│   ├── __init__.py           # re-exports Phase 1 names + Phase 2 additions; registers defaults
│   ├── base.py               # ABC, normalized types, StageProgress with kind
│   ├── spec_kit.py           # SpecKitAdapter (moved); underscored filename keys
│   ├── openspec.py           # OpenSpecAdapter
│   └── registry.py           # AdapterRegistry + module-level registry
├── sdd_adapter.py            # import shim re-exporting from package (one-release grace)
├── flow_state.py             # MODIFIED - registry routing, deprecated singleton
├── yolo.py                   # MODIFIED - supports("yolo") gate
└── matriarch.py              # UNTOUCHED

tests/
├── test_sdd_adapter.py                # MODIFIED - interface extension coverage
├── test_sdd_adapter_registry.py       # NEW - FR-030
├── test_openspec_adapter.py           # NEW - FR-029
├── test_flow_state_parity.py          # NEW - FR-031
├── test_flow_state_anti_leak.py       # NEW or MODIFIED - FR-032
├── fixtures/openspec_repo/            # NEW - hand-authored; FR-028
└── fixtures/mixed_sdd_repo/           # NEW - spec-kit + OpenSpec
```

**Structure Decision**: package split lands now (FR-019). Phase 1 plan
predicted exactly this moment. The import shim preserves every Phase 1
import path (NFR-003, AC-007).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Package-ize `sdd_adapter` | Two concrete adapters share the ABC; one module gets noisy | Single file would force `openspec.py` to live next to `SpecKitAdapter` and the ABC, making the "no spec-kit leaks into OpenSpec" invariant harder to enforce via import boundaries |
| `AdapterRegistry` class | `flow_state` and `yolo` both need a single lookup surface, and tests need a reset helper | A module-level list would reinvent the class with worse ergonomics; no discovery mechanism is added, so the class stays narrow |
| `ordered_stage_kinds` default on the ABC | Callers want a single method without isinstance checks | Freestanding vocabulary constant would force every downstream to know which adapter uses which subset |
| `supports(capability)` probe | Yolo and matriarch both need a way to ask "can I run here" without hardcoding adapter names | Per-capability abstract methods (`supports_yolo`, `supports_lanes`) would explode the ABC surface; the capability-string pattern stays open for additive growth |

No other new complexity.

## Research Decisions

### 1. Four sub-phases, strict TDD ordering

Sub-phase A (interface additions) lands first as a pure additive
change with parity maintained. Sub-phase B adds the registry and
rewires `flow_state`. Sub-phase C adds `OpenSpecAdapter` plus the
package restructure. Sub-phase D hardens with fixtures, anti-leak
tests, and documentation.

Rationale: each sub-phase is individually rollback-able; the parity
gate exists from sub-phase A forward so every sub-phase proves "no
regression" at its own boundary; `OpenSpecAdapter` cannot leak into
the rest of the system until the registry exists to admit it. This
mirrors 016 Phase 1's cadence. Alternatives rejected: single-PR ship
(too large against line-by-line parity review); adapter-before-registry
(violates TDD order).

### 2. Resolve the three spec "Open Questions" that block `plan.md`

The spec's 10 open questions include three with "before `plan.md`"
deadlines. Resolving them here.

**Q1 - `FeatureHandle.archived` shape**: boolean field, default `False`.
Rationale: FR-008 allows bool or enum; a boolean keeps `FeatureHandle`
JSON-serializable, is one attribute vs a new two-state enum, and
extends via sibling fields if a third state ever appears.

**Q2 - Dashed vs underscored filename key aliases**: ship underscored
keys as canonical (`"review_spec"`) plus a one-release read alias for
dashed forms (`"review-spec"` reads through). The alias is read-only
and emits `DeprecationWarning` on dashed-key access. Rationale:
`flow_state.py` and any third-party consumer reading
`filenames["review-spec"]` deserves one release of grace.

**Q3 - `_SPEC_KIT_ADAPTER` deprecation mechanism**: docstring note plus
a once-per-process runtime `DeprecationWarning` via a PEP 562
`__getattr__` on `flow_state`. Rationale: docstring-only is invisible
to automated consumers; per-access warning is noisy; once-per-process
is the right middle.

### 3. Defer spec Q4-Q7 to `tasks.md`, Q8-Q10 explicit deferrals

Noted in sub-phase C docstring and tasks.md touch list.

### 4. Parity gate mechanism

New `tests/test_flow_state_parity.py` captures canonical JSON
snapshots of `compute_flow_state(feature_dir).to_dict()` for every
feature directory under `specs/` on the pre-Phase-2 main branch,
stores them under `tests/fixtures/flow_state_snapshots/`, and asserts
byte equality after each sub-phase.

Sub-phase A's gate masks the new `kind` fields; sub-phase B onward
asserts full byte equality against snapshots regenerated with `kind`
populated. This is the 016 Phase 1 "snapshot vs pre-refactor CLI"
approach, shifted one sub-phase for the additive field. See §Parity
Gate below.

## Design Decisions

### 1. Interface shape after Phase 2

The ABC gains two non-abstract methods, `StageProgress` gains one
field. Signatures: `SddAdapter.ordered_stage_kinds(self) -> list[str]`
(default returns the eight-kind canonical list; adapters override for
native subset); `SddAdapter.supports(self, capability: str) -> bool`
(default False; concrete adapters override); `StageProgress.kind: str`
(added after existing fields; every production construction site sets
it explicitly, no default after sub-phase A's gate passes). The five
existing abstract methods stay; nothing is removed.

### 2. Filename-key indirection

Each adapter exposes a `_FILENAME_MAP: dict[str, str]` class attribute
keyed on underscored semantic keys (`spec`, `plan`, `tasks`,
`review_spec`, `review_code`, `review_pr`). `NormalizedArtifacts.filenames`
is populated from this map at `load_feature` time. Callers look up by
semantic key, never literal filename. The dashed-key back-compat read
alias lives in `flow_state.py`, not in the adapter.

### 3. Registry shape

`AdapterRegistry` is a plain class holding an ordered tuple of adapter
instances. The module-level `registry` is built in
`sdd_adapter/__init__.py`; `flow_state.py` imports it. Surface:
`register`, `adapters`, `resolve_for_path`, `resolve_for_feature`,
`resolve_for_repo`, `reset_to_defaults` (FR-017). Resolution is O(N)
over two adapters; negligible (NFR-004).

### 4. Path scope disambiguation

Registration order: `SpecKitAdapter` first, `OpenSpecAdapter` second
(FR-018). `resolve_for_path` returns the first adapter whose
`id_for_path` returns non-None. Path scopes (`specs/NNN-slug/` vs
`openspec/changes/`) do not overlap, so order is belt-and-suspenders;
mixed-repo fixture test proves no ambiguity (US4).

### 5. `compute_stage` for OpenSpec review kinds

Spec Q4 leans toward omission over "not applicable" status. This plan
leaves the question open; sub-phase C surfaces it with implementation
data. Omission is simpler and needs no downstream vocabulary changes.

### 6. What does NOT change

Every Phase 1 import path resolves (FR-020, NFR-003); `FlowStateResult`,
`FlowMilestone`, `ReviewMilestone`, `FeatureEvidence`, `TaskSummary`,
and per-review dataclasses stay shape-stable; `compute_flow_state`,
`compute_spec_lite_state`, `compute_adoption_state`,
`list_yolo_runs_for_feature`, `write_resume_metadata`, `main` keep
signatures; CLI, extension manifest, command prompts, TUI (FR-027),
matriarch (FR-026), and `pyproject.toml` (NFR-002) untouched.

## Implementation Phases

Phase 2 of the multi-SDD layer program breaks into four sub-phases
(A through D). Each sub-phase has its own TDD-red-first test gate.

---

### Sub-phase A - Core interface extension (additive)

**Goal**: Extend the ABC with `ordered_stage_kinds` and `supports`,
extend `StageProgress` with `kind`, switch `SpecKitAdapter` to
underscored filename keys, and prove nothing observable changed.

**Deliverables**:

- New abstract/default methods on `SddAdapter`: `ordered_stage_kinds`,
  `supports` (FR-001, FR-002).
- `StageProgress.kind: str` field (FR-003).
- `SpecKitAdapter.ordered_stage_kinds` returns the v1 eight-kind list
  in spec-kit's native order.
- `SpecKitAdapter.supports` returns True for lanes, yolo, review_code,
  review_pr, adoption; False otherwise (FR-014).
- `SpecKitAdapter.compute_stage` attaches `kind` via the FR-015
  mapping.
- `SpecKitAdapter._FILENAME_MAP` migrated to underscored keys
  (FR-013).
- Dashed-key read alias in `flow_state.py` artifact lookup (one-release
  grace; emits `DeprecationWarning`).
- Parity-gate test module scaffold (baseline snapshots generated).

**Risks** (top 3):

1. Changing `_SPEC_KIT_FILENAMES` keys breaks a consumer we did not
   notice. Mitigation: the read alias plus a grep audit of the
   codebase for dashed-key literals before the PR.
2. Adding `kind` to `StageProgress` with no default changes the
   legacy dataclass constructor signature and breaks Phase 1 tests
   that construct `StageProgress` positionally. Mitigation: add a
   sentinel default during sub-phase A tests, then remove once all
   construction sites are updated; a one-time sweep finds every site.
3. The parity gate flags real pre-existing drift because snapshots
   were captured on a slightly different fixture state. Mitigation:
   generate snapshots from a clean `main` checkout immediately
   before sub-phase A starts; commit the snapshot files in the same
   PR that lands the test.

**Tests that MUST exist before code (TDD red-first)**:

- `test_sdd_adapter.py`: `ordered_stage_kinds_default_returns_v1_list`,
  `supports_default_returns_false_for_anything`,
  `stage_progress_has_kind_field`,
  `spec_kit_ordered_stage_kinds_matches_native_order`,
  `spec_kit_supports_each_v1_capability`,
  `spec_kit_compute_stage_attaches_kind_per_frs_mapping`,
  `spec_kit_filename_map_uses_underscored_keys`.
- `test_flow_state.py`: `dashed_key_filename_lookup_emits_deprecation_warning`.
- `test_flow_state_parity.py`: `spec_kit_fixtures_match_phase1_snapshots_modulo_kind`.

All must be red against Phase 1 code before implementation starts.

**Rollback plan**: revert the sub-phase A PR; `sdd_adapter.py` stays as
a module; `StageProgress` loses `kind`; filename keys stay dashed; Phase
1 state restored.

**Dependencies on earlier sub-phases**: none (first sub-phase).

---

### Sub-phase B - Registry introduction

**Goal**: Introduce `AdapterRegistry`, route `flow_state` through it,
keep `_SPEC_KIT_ADAPTER` live and synced with a deprecation warning,
and prove parity still holds.

**Deliverables**:

- `AdapterRegistry` class with `register`, `adapters`,
  `resolve_for_path`, `resolve_for_feature`, `resolve_for_repo`, and
  `reset_to_defaults` (FR-017).
- Module-level `registry` instance populated with `SpecKitAdapter()` at
  `sdd_adapter` import time (FR-018; OpenSpec registration happens in
  sub-phase C).
- `flow_state.collect_feature_evidence` obtains its adapter via
  `registry.resolve_for_path`, with Phase-1 fallback preserved
  (FR-022).
- `_SPEC_KIT_ADAPTER` retained as a live reference synced with the
  registry's `SpecKitAdapter`; PEP 562 `__getattr__` on `flow_state`
  emits `DeprecationWarning` on access (FR-021; Research §2 Q3).
- Registry tests for idempotency, path resolution, feature resolution,
  repo resolution, reset (FR-030).

**Risks** (top 3):

1. Tests that monkeypatch `_SPEC_KIT_ADAPTER` break because the
   singleton is now derived rather than canonical. Mitigation:
   sync is bidirectional during sub-phase B only; the module
   attribute assignment is intercepted to also update the registry
   (setter logic documented in `flow_state.py` comment); FR-034
   allows exactly one minimum-necessary monkeypatch update.
2. PEP 562 `__getattr__` interacts badly with `from flow_state import
   _SPEC_KIT_ADAPTER` statements already in the codebase. Mitigation:
   grep for every `_SPEC_KIT_ADAPTER` reference; confirm each is an
   attribute access rather than a `from ... import` at module scope;
   migrate any offenders to attribute access in the same PR.
3. Registry dispatch overhead exceeds the 5% budget (NFR-004).
   Mitigation: benchmark in the parity-gate test; iteration over two
   adapters is ~100 ns per call, well under any plausible budget, but
   measure to confirm.

**Tests that MUST exist before code (TDD red-first)**:

- `test_sdd_adapter_registry.py`: `register_is_idempotent_by_name`,
  `resolve_for_path_spec_kit_fixture`,
  `resolve_for_path_unrelated_returns_none`,
  `resolve_for_feature_returns_matching_handle`,
  `resolve_for_repo_single_format_returns_one_adapter`,
  `reset_to_defaults_restores_in_tree_adapters`.
- `test_flow_state.py`: `spec_kit_adapter_access_emits_deprecation_warning`,
  `spec_kit_adapter_monkeypatch_still_works`.
- `test_flow_state_parity.py`: `registry_wired_parity_holds_full_shape`.

All must be red against sub-phase A output before implementation starts.

**Rollback plan**: revert the sub-phase B PR; `flow_state` reverts to
direct singleton use; registry stays on a branch; sub-phase A additions
remain and continue to pass their tests.

**Dependencies on earlier sub-phases**: A (needs `ordered_stage_kinds`,
`supports`, and the underscored filename keys before the registry has
something to route).

---

### Sub-phase C - OpenSpec adapter implementation

**Goal**: Ship `OpenSpecAdapter`, restructure `sdd_adapter.py` into the
`sdd_adapter/` package, register OpenSpec in the default registry, and
gate yolo on `supports("yolo")`.

**Deliverables**:

- `src/speckit_orca/sdd_adapter/` package (FR-019): `base.py` (ABC,
  normalized types, `StageProgress` with `kind`), `spec_kit.py`
  (`SpecKitAdapter` moved from sub-phase A), `openspec.py`
  (`OpenSpecAdapter`), `registry.py` (`AdapterRegistry` + module-level
  instance), `__init__.py` (re-exports every Phase 1 public name +
  Phase 2 additions per FR-020; registers `SpecKitAdapter()` then
  `OpenSpecAdapter()`).
- `sdd_adapter.py` reduced to an import shim re-exporting from the
  package (NFR-003).
- `OpenSpecAdapter` implementing every abstract + Phase 2 method:
  `name` returns `"openspec"`; `detect` True iff `repo_root/"openspec"`
  is a directory (FR-006); `list_features` scans `openspec/changes/*`
  excluding `archive/` by default, with `include_archived=True`
  including archived changes and stripping date prefixes (FR-007/008);
  `load_feature` populates the FR-009 filename map + parsed tasks +
  absent review evidence + empty lanes + optional brainstorms;
  `compute_stage` emits at least `spec`/`plan`/`implementation` kinds,
  review kinds omitted in v1 (spec Q4 leaning omission), `ship` only
  for archived paths (FR-010); `id_for_path` active -> slug, archive ->
  None (FR-011); `ordered_stage_kinds` returns the native subset;
  `supports` True only for `"adoption"` (FR-012).
- `FeatureHandle.archived: bool = False` (Research §2 Q1).
- Registry populated with both adapters in order (FR-018).
- Yolo entry calls `registry.resolve_for_path` and rejects with the
  documented message when `supports("yolo") == False` (FR-025).
- Hand-authored OpenSpec fixture at `tests/fixtures/openspec_repo/`
  (FR-028) with README documenting upstream-version targeting.

**Risks** (top 3):

1. OpenSpec format assumptions encoded in the fixture drift from the
   real upstream layout. Mitigation: fixture README documents TBC
   items; a follow-up task diffs against a real OpenSpec repo; parser
   is narrow and localized to `openspec.py` so patches stay in one
   file (Risk 1, 8 in the spec).
2. `load_feature` gracefully handling a change with missing `design.md`
   or `tasks.md` requires status decisions the spec punts to
   `tasks.md` (Q6). Mitigation: sub-phase C lands a "not started"
   status for missing `design.md` as the leaning decision, documented
   in `openspec.py` docstring, and a task in `tasks.md` re-surfaces
   the question.
3. Package-ization breaks an import we did not catch. Mitigation: grep
   for every `from speckit_orca.sdd_adapter import` in the repo and
   assert each still resolves; the import shim makes most cases
   automatic, but relative imports inside the package need careful
   review.

**Tests that MUST exist before code (TDD red-first)**:

- `test_openspec_adapter.py`:
  `detect_returns_true_when_openspec_dir_exists`,
  `detect_returns_false_when_no_openspec_dir`,
  `list_features_excludes_archive_by_default`,
  `list_features_includes_archived_when_requested`,
  `list_features_strips_date_prefix_from_archived_slug`,
  `load_feature_populates_filename_map_per_fr009`,
  `load_feature_parses_tasks_with_synthetic_ids`,
  `load_feature_review_evidence_all_false`,
  `load_feature_worktree_lanes_empty`,
  `compute_stage_emits_spec_plan_implementation_kinds`,
  `compute_stage_ship_only_for_archived_paths`,
  `id_for_path_active_returns_slug`,
  `id_for_path_archive_returns_none_by_default`,
  `supports_returns_true_only_for_adoption`,
  `ordered_stage_kinds_subset_of_v1_vocabulary`.
- `test_sdd_adapter_registry.py`: `both_adapters_registered_by_default`,
  `resolve_for_path_openspec_fixture`.
- `test_yolo.py`: `yolo_rejects_non_yolo_adapter_with_documented_message`,
  `yolo_rejection_records_no_stage_events`.
- `test_imports.py`: `phase1_import_paths_still_resolve`.

All must be red against sub-phase B output before implementation starts.

**Rollback plan**: revert the sub-phase C PR; `sdd_adapter/` package
removed; `sdd_adapter.py` restored as a single file; OpenSpec adapter
gone; yolo rejection gate removed; sub-phases A and B remain intact.

**Dependencies on earlier sub-phases**: A and B (needs the extended
ABC, the registry, and the parity gate all in place).

---

### Sub-phase D - Fixtures, tests, and documentation

**Goal**: Ship the mixed-repo fixture, finalize the parity gate, land
the anti-leak test, and update documentation.

**Deliverables**:

- Mixed-repo fixture at `tests/fixtures/mixed_sdd_repo/` with
  `specs/001-foo/` + `openspec/changes/bar/` (FR-023, FR-024).
- Mixed-repo tests: `resolve_for_repo` returns both adapters;
  `resolve_for_path` routes correctly; `compute_flow_state` enumerates
  both namespaces without de-dup and without crash (FR-023/024, US4).
- Stub-adapter test: trivial stub registered via `registry.register`
  and exercised through `compute_flow_state` with zero core edits
  (FR-017, US3).
- Golden-snapshot parity test finalized (FR-031) with full-shape byte
  equality against snapshots in `tests/fixtures/flow_state_snapshots/`.
- Anti-leak test `tests/test_flow_state_anti_leak.py` (FR-032)
  asserting no OpenSpec literals (`"proposal.md"`, `"design.md"`,
  `"openspec"`) and no extra spec-kit filename literals.
- 100-change performance test (NFR-001) generating a synthetic tree in
  a temp dir and timing `detect + list_features`.
- README update: Phase 2 landed note + fixture-README pointer.
- `specs/016-multi-sdd-layer/review.md` one-line Phase 2 landing
  pointer.

**Risks** (top 3):

1. Anti-leak test flags a legitimate literal in `flow_state.py` that
   cannot be removed without a bigger refactor. Mitigation: the list
   of disallowed literals is tight (OpenSpec filenames only); the
   Phase 1 anti-leak test already proved the spec-kit side is clean.
2. Snapshot format drifts between generation and assertion due to
   dictionary ordering or path separators. Mitigation: snapshots
   serialize with `json.dumps(..., indent=2, sort_keys=True)`;
   absolute paths are normalized to repo-relative in the snapshot
   serializer.
3. Documentation updates get out of sync with what actually shipped.
   Mitigation: the sub-phase D PR updates README and the 016 review
   pointer in the same commit range as the test landing, so stale
   docs surface in PR review.

**Tests that MUST exist before code (TDD red-first)**:

- `test_sdd_adapter_registry.py`:
  `mixed_repo_resolve_for_repo_returns_both_adapters`,
  `mixed_repo_resolve_for_path_routes_correctly`,
  `stub_adapter_registration_works_without_core_edits`.
- `test_flow_state.py`: `mixed_repo_compute_flow_state_enumerates_both_namespaces`.
- `test_flow_state_parity.py`: `byte_identical_snapshots_for_every_feature`.
- `test_flow_state_anti_leak.py`: `no_openspec_literals_in_flow_state`.
- `test_openspec_adapter.py`: `detect_plus_list_features_under_200ms_for_100_changes`.
- `test_imports.py`: `tui_imports_unchanged`, `matriarch_imports_unchanged`.

All must be red against sub-phase C output before implementation starts.

**Rollback plan**: revert the sub-phase D PR; fixture directories
deleted; tests removed; documentation reverts. Sub-phases A-C remain
functional; Phase 2 is considered "partial ship" and re-landed via a
follow-up PR.

**Dependencies on earlier sub-phases**: A, B, and C (needs the full
Phase 2 stack to exist before the cross-cutting fixtures and gates
exercise it).

---

## Parity Gate

The non-regression gate for Phase 2 is a golden-snapshot comparison of
`compute_flow_state(feature_dir).to_dict()` across every spec-kit
feature directory under `specs/`.

**Generation** (one-time, before sub-phase A lands): on the pre-Phase-2
main commit, run `python -m speckit_orca.flow_state feature_dir
--format json` for each `feature_dir in specs/*`; serialize with
`json.dumps(..., indent=2, sort_keys=True)`; normalize absolute paths
to repo-relative; write to
`tests/fixtures/flow_state_snapshots/<feature_id>.json`; commit with
sub-phase A.

**Assertion**: sub-phase A asserts byte equality except for the new
`completed_milestones[*].kind` and `incomplete_milestones[*].kind`
fields (which did not exist pre-Phase-2). Sub-phase B onward asserts
full byte equality against snapshots regenerated to include `kind`.

This mirrors 016 Phase 1's "snapshot vs pre-refactor CLI output"
approach, shifted one sub-phase to accommodate the additive `kind`
field.

## Definition of Done

Mapped to the spec's acceptance criteria. All must be green for Phase 2
to land.

- [ ] **AC-001** (US1): `compute_flow_state` on an OpenSpec fixture
      change returns a `FlowStateResult` with
      `adapter_name == "openspec"`, `filenames["spec"] == "proposal.md"`,
      and task-summary counts matching the fixture.
- [ ] **AC-002** (US2, FR-003/010/015): every `StageProgress` carries a
      `kind` drawn from `ordered_stage_kinds`.
- [ ] **AC-003** (US3, FR-017/018): stub-adapter test passes with zero
      edits to `flow_state.py`, `matriarch.py`, `yolo.py`.
- [ ] **AC-004** (US4, FR-023/024): mixed-repo fixture routes each path
      to the correct adapter, and `resolve_for_repo` returns both.
- [ ] **AC-005** (US5, FR-025/033): yolo on an OpenSpec path exits
      non-zero with the documented message; no events recorded.
- [ ] **AC-006** (FR-016/031): parity snapshots byte-identical for
      every spec-kit fixture, modulo the additive `kind` field.
- [ ] **AC-007** (FR-020/021): every Phase 1 import still resolves;
      Phase 1 tests pass with at most one monkeypatch update.
- [ ] **AC-008** (FR-028/029): OpenSpec fixture exists, is documented,
      and is covered by snapshot tests for every adapter method.
- [ ] **AC-009** (FR-032): anti-leak test passes; no OpenSpec literals
      in `flow_state.py`.
- [ ] **AC-010** (NFR-001): `detect + list_features` under 200 ms on a
      100-change synthetic fixture.
- [ ] **AC-011** (NFR-002): `pyproject.toml` unchanged by Phase 2.
- [ ] **AC-012** (FR-026/027): matriarch and TUI code untouched; smoke
      test confirms spec-kit TUI rendering unchanged.

## What Stays Deferred

Re-stated from the spec's §Out of Scope. The following are explicitly
out of scope for 019 and must not be introduced by review:

- BMAD adapter (Phase 3+); Taskmaster adapter (Phase 3+).
- OpenSpec adoption records. Adoption (017) stays Orca-native and
  format-agnostic; no OpenSpec-specific adoption flow lands here.
- Yolo running OpenSpec features (rejection only).
- Matriarch managing OpenSpec features (lane registration, readiness
  gates, mailbox coordination). Read-only display is fine;
  coordination is not.
- Additional stage kinds beyond the v1 vocabulary. `decompose`,
  `ideate`, and others from the brainstorm are deferred.
- Removal of the `_SPEC_KIT_ADAPTER` singleton. Deprecated in v1;
  removal is a future spec.
- Write support on `OpenSpecAdapter`. No archive, sync, or propose.
- Cross-format review orchestration. `review-spec`, `review-code`,
  `review-pr` stay spec-kit-only.
- `orca convert` between formats; installer integration for OpenSpec.
- TUI OpenSpec-awareness beyond passthrough rendering. 018 owns any
  OpenSpec-specific TUI work.
- Plugin system for third-party out-of-tree adapters.
- `.specify/orca/` rename or relocate (grandfathered).

## Touch List

Files modified or created, grouped by sub-phase.

### Sub-phase A

- `src/speckit_orca/sdd_adapter.py` - MOD: add `ordered_stage_kinds`,
  `supports`, `kind` on `StageProgress`; migrate filename map to
  underscored keys; attach `kind` in `SpecKitAdapter.compute_stage`.
- `src/speckit_orca/flow_state.py` - MOD: dashed-key read alias with
  `DeprecationWarning`.
- `tests/test_sdd_adapter.py` - MOD: interface extension tests.
- `tests/test_flow_state.py` - MOD: dashed-key deprecation test.
- `tests/test_flow_state_parity.py` - NEW.
- `tests/fixtures/flow_state_snapshots/*.json` - NEW, one per existing
  spec-kit feature directory.

### Sub-phase B

- `src/speckit_orca/sdd_adapter.py` - MOD: `AdapterRegistry` +
  module-level `registry` populated with `SpecKitAdapter`.
- `src/speckit_orca/flow_state.py` - MOD: route through
  `registry.resolve_for_path`; PEP 562 `__getattr__` deprecation on
  `_SPEC_KIT_ADAPTER`; keep the attribute live and synced.
- `tests/test_sdd_adapter_registry.py` - NEW.
- `tests/test_flow_state.py` - MOD: deprecation-warning test,
  monkeypatch-still-works test.
- `tests/test_flow_state_parity.py` - MOD: switch to full-shape
  equality.

### Sub-phase C

- `src/speckit_orca/sdd_adapter/` - NEW package: `__init__.py`,
  `base.py`, `spec_kit.py`, `openspec.py`, `registry.py`.
- `src/speckit_orca/sdd_adapter.py` - MOD: reduced to an import shim
  re-exporting from the package.
- `src/speckit_orca/yolo.py` - MOD: registry lookup + rejection gate
  on `supports("yolo") == False`.
- `tests/test_openspec_adapter.py` - NEW.
- `tests/test_yolo.py` - MOD or NEW: rejection behavior.
- `tests/test_imports.py` - NEW: Phase 1 import-path resolution.
- `tests/fixtures/openspec_repo/` - NEW: README, `.git/`,
  `openspec/changes/{add-dark-mode,minimal-change,archive/2026-04-01-first-shipped}/`,
  `openspec/specs/dark-mode/spec.md`.

### Sub-phase D

- `tests/fixtures/mixed_sdd_repo/` - NEW.
- `tests/test_sdd_adapter_registry.py` - MOD: mixed-repo and
  stub-adapter tests.
- `tests/test_flow_state.py` - MOD: mixed-repo `compute_flow_state`.
- `tests/test_flow_state_anti_leak.py` - NEW or MOD: OpenSpec literal
  check.
- `tests/test_openspec_adapter.py` - MOD: 200 ms performance test.
- `tests/test_imports.py` - MOD: TUI and matriarch import stability.
- `README.md` - MOD: Phase 2 landed note with fixture-README pointer.
- `specs/016-multi-sdd-layer/review.md` - MOD: one-line Phase 2
  landing pointer.

---

**Brainstorm references**: §4 (proposed interface changes), §5
(detection), §6 (feature identity and archived changes), §10 (registry
model), §11 (mixed repos), §13 (yolo), §15 (matriarch), §16 (test
strategy), §17 (open questions), §18 (scope discipline), §20 (risks).
