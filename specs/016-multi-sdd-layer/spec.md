# Feature Specification: Multi-SDD Layer — Phase 1 (Adapter Interface + SpecKit Adapter)

**Feature Branch**: `016-multi-sdd-layer`
**Created**: 2026-04-16
**Status**: Implemented
**Input**: "Refactor Orca so spec-kit artifact reads flow through a narrow adapter interface, preparing (but not delivering) future support for OpenSpec, BMAD, and Taskmaster."

## Context

Orca today is wired to one on-disk convention: features live at
`specs/NNN-slug/`, artifacts are a fixed set of markdown files, stages
are the hardcoded nine-step pipeline, and `flow_state.py` reads all of
it directly. Roughly 70 percent of `flow_state.py` is spec-kit-flavored
path logic and parsing. See `specs/016-multi-sdd-layer/brainstorm.md`
for the full landscape survey and motivation.

The brainstorm proposes an adapter pattern in three phases:

- **Phase 1 (this spec)**: introduce the adapter interface and a
  spec-kit reference adapter; refactor `flow_state.py` to route
  spec-kit artifact reads through the adapter. No user-visible change.
- Phase 2 (deferred): OpenSpec adapter.
- Phase 3 (deferred): BMAD and Taskmaster detection stubs.

Phase 1 is a pure refactor. It ships zero new behavior. The operator
value of Phase 1 is that the follow-on phases become possible without
another core rewrite; the immediate value is that the spec-kit-specific
logic is now named, bounded, and separable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator Sees No Change (Priority: P1)

An existing spec-kit user runs `uv run python -m speckit_orca.flow_state
specs/NNN-feature` before and after this refactor.

**Why this priority**: Zero-behavior-change is the exit gate for Phase 1.
If operators see any difference, the refactor failed.

**Independent Test**: Run the full existing test suite
(`uv run pytest tests/`) against the pre-refactor and post-refactor
code. All tests pass unchanged. JSON and text outputs of
`compute_flow_state` on every fixture feature are byte-identical.

**Acceptance Scenarios**:

1. **Given** any feature directory under `specs/`, **When**
   `compute_flow_state(feature_dir)` is called, **Then** the returned
   `FlowStateResult` is identical to the pre-refactor result for the
   same inputs.
2. **Given** the CLI invocation `python -m speckit_orca.flow_state
   <target> --format json`, **When** run against any fixture target
   (feature directory, spec-lite record, adoption record), **Then**
   stdout is byte-identical to pre-refactor output.
3. **Given** the existing test suite, **When** run after the refactor,
   **Then** every test passes with no edits to test code.

---

### User Story 2 - Developer Touching Adapter Code Sees A Single Interface (Priority: P1)

A developer adding a new artifact kind or fixing a bug in spec-kit
artifact handling touches one file (`sdd_adapter.py` or the spec-kit
adapter) instead of hunting through `flow_state.py`.

**Why this priority**: The refactor only pays off if the seam is real.
If `flow_state.py` still mixes spec-kit I/O with stage and review
semantics, Phase 2 will be just as hard as Phase 1 was.

**Independent Test**: A developer can read `sdd_adapter.py` and the
spec-kit adapter in isolation and understand the full contract for
"reading spec-kit artifacts." No reference to `flow_state.py` internals
is required to understand the adapter contract.

**Acceptance Scenarios**:

1. **Given** the adapter module, **When** a developer reads the
   dataclass definitions and abstract method signatures, **Then** they
   can describe the full set of inputs and outputs for adapter-owned
   operations without opening `flow_state.py`.
2. **Given** `flow_state.py` after refactor, **When** grepping for
   `feature_path / "spec.md"` or similar spec-kit path literals,
   **Then** no matches appear outside the spec-kit adapter.

---

### User Story 3 - Phase 2 Author Has A Working Template (Priority: P2)

A future contributor starting the OpenSpec adapter can subclass
`SddAdapter`, implement its abstract methods, and have confidence the
core will consume the result the same way it consumes spec-kit.

**Why this priority**: Phase 1 justifies itself on refactor hygiene,
but its strategic purpose is to unblock Phase 2. The interface shape
must be concrete enough to build against.

**Independent Test**: Write a trivial `NullAdapter` in a test file
whose `detect` always returns `False`. Verify `SpecKitAdapter` and
`NullAdapter` both satisfy the same abstract base class and both
produce a `NormalizedArtifacts` instance when called.

**Acceptance Scenarios**:

1. **Given** the adapter ABC, **When** a subclass implements the
   abstract methods, **Then** it passes `isinstance(obj, SddAdapter)`
   and can be instantiated.
2. **Given** two adapter implementations, **When** both are called on
   their respective fixture trees, **Then** both return
   `NormalizedArtifacts` instances the same downstream code can
   consume.

### Edge Cases

- What happens if a feature directory exists but is empty? The adapter
  returns a `NormalizedArtifacts` with all optional fields unset and
  an empty task list. `flow_state` produces the same "nothing present"
  result it produces today.
- What happens if the feature directory contains unexpected files
  (e.g., a stray `notes.md`)? The adapter ignores them, same as
  current behavior.
- What happens if `tasks.md` exists but contains no recognizable task
  lines? The adapter returns an empty task list with a zero-count
  summary, matching current `_parse_tasks` behavior.
- What happens if the caller passes a path that is not a feature
  directory (e.g., a spec-lite file, an AR file)? Phase 1 does not
  route those through the adapter; `compute_spec_lite_state` and
  `compute_adoption_state` stay on their current code path. The
  adapter is only invoked from `compute_flow_state` /
  `collect_feature_evidence`.
- What happens if an adapter method raises? The adapter is responsible
  for mapping I/O errors to empty-string and empty-list results
  (matching current `_read_text_if_exists` behavior); uncaught
  exceptions propagate. Phase 1 does not introduce new error paths.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Introduce a new module `src/speckit_orca/sdd_adapter.py`
  that defines the abstract base class `SddAdapter` and the supporting
  dataclasses `FeatureHandle`, `NormalizedArtifacts`, `NormalizedTask`,
  and `StageProgress`.
- **FR-002**: `SddAdapter` MUST declare (at minimum) abstract methods
  for: detection (`detect(repo_root)`), feature enumeration
  (`list_features(repo_root)`), artifact loading
  (`load_feature(handle)`), stage progression computation
  (`compute_stage(artifacts)`), and path-to-feature reverse lookup
  (`id_for_path(path, repo_root)`).
- **FR-003**: `NormalizedArtifacts` MUST carry enough information for
  `flow_state.collect_feature_evidence` and its downstream consumers
  to produce byte-identical output to the current implementation. This
  includes, at minimum, the path map of raw artifacts, the parsed
  task summary data, the parsed review evidence, the linked-brainstorm
  paths, and the worktree lane records.
- **FR-004**: Introduce a concrete `SpecKitAdapter` class in
  `src/speckit_orca/sdd_adapter.py` (or a sibling module imported by
  it) that implements `SddAdapter` using the current spec-kit path
  conventions (`specs/NNN-slug/`, canonical artifact filenames,
  `.specify/orca/` registry paths).
- **FR-005**: `SpecKitAdapter` MUST mirror the behavior of the
  existing `flow_state.py` helpers (`_parse_tasks`,
  `_parse_review_evidence`, `_find_linked_brainstorms`,
  `_load_worktree_lanes`, `_find_repo_root`) without altering their
  outputs. Phase 1 is allowed to move the implementations; it is not
  allowed to change their semantics.
- **FR-006**: `flow_state.collect_feature_evidence` MUST be refactored
  to obtain its artifact data by instantiating and calling the
  `SpecKitAdapter` rather than calling the private helpers directly.
  The function's public signature, return type, and observable
  behavior MUST NOT change.
- **FR-007**: All other public `flow_state` surfaces
  (`compute_flow_state`, `compute_spec_lite_state`,
  `compute_adoption_state`, `list_yolo_runs_for_feature`,
  `write_resume_metadata`, `main`, and every dataclass currently
  exported) MUST retain their current signatures and behavior. Phase 1
  MUST NOT change the CLI.
- **FR-008**: The existing test suite MUST pass unchanged. No
  test file in `tests/` may be edited as part of Phase 1 except to add
  new tests. Existing assertions, fixtures, and expected outputs stay
  the same.
- **FR-009**: New tests MUST cover the adapter in isolation: the
  dataclass shapes, `SpecKitAdapter.detect`, `SpecKitAdapter.list_features`,
  `SpecKitAdapter.load_feature`, and `SpecKitAdapter.id_for_path` each
  get direct unit coverage against synthetic fixture trees. These
  tests are additive; they do not replace existing flow-state tests.
- **FR-010**: Phase 1 MUST NOT introduce adapter registry lookup,
  auto-detection logic, CLI flags, or extension-manifest changes
  beyond what is strictly necessary to wire `SpecKitAdapter` into
  `flow_state`. Phase 1 wires `SpecKitAdapter` into `flow_state` via a
  module-level singleton `_SPEC_KIT_ADAPTER = SpecKitAdapter()` that
  `collect_feature_evidence` dispatches through; tests (see T020 in
  `tasks.md`) may monkeypatch `_SPEC_KIT_ADAPTER` to intercept adapter
  calls. A registry lookup replaces this singleton in Phase 2.
- **FR-011**: Phase 1 MUST NOT touch `src/speckit_orca/matriarch.py`,
  `src/speckit_orca/yolo.py`, `src/speckit_orca/brainstorm_memory.py`,
  `src/speckit_orca/context_handoffs.py`, `extension.yml`,
  `commands/*.md`, or user-facing docs except the spec itself.
- **FR-012**: `StageProgress` MUST be defined in Phase 1 but MAY be
  populated with spec-kit's current nine-stage model without any
  cross-format abstraction. The stage-kind enum and per-format
  mappings are deferred to Phase 2.
- **FR-013**: Phase 1 MUST NOT add OpenSpec, BMAD, or Taskmaster
  adapters (even as stubs). The adapter base class ships with exactly
  one concrete subclass: `SpecKitAdapter`.
- **FR-014**: Errors in adapter I/O (e.g., a missing feature directory)
  MUST produce the same observable result as the current
  implementation. The adapter does not add new exception types or new
  failure modes.

## Key Entities *(include if feature involves data)*

- **SddAdapter**: Abstract base class in `src/speckit_orca/sdd_adapter.py`
  describing the read-side contract for an SDD format. Phase 1 defines
  the interface but only ships one implementation.
- **FeatureHandle**: Opaque dataclass identifying a feature in
  adapter-native terms. Fields: `feature_id` (format-native ID),
  `display_name` (human label), `root_path` (where artifacts live),
  `adapter_name` (which adapter owns it).
- **NormalizedArtifacts**: Dataclass carrying the adapter's output
  into `flow_state`. Must be rich enough to reconstruct today's
  `FeatureEvidence` without loss. Contains the raw artifact path map,
  the parsed task list, the review evidence, linked brainstorms, and
  worktree lane records.
- **NormalizedTask**: Dataclass representing one task item. Fields
  (Phase 1): `task_id`, `text`, `completed`, `assignee`. Later phases
  may add `dependencies` and `native_status`.
- **StageProgress**: Dataclass representing a feature's stage state.
  Phase 1 shape mirrors the current spec-kit milestones (stage name,
  status, evidence sources, notes). The stage-kind abstraction is out
  of scope.
- **SpecKitAdapter**: The reference implementation. Wraps current
  spec-kit path and parsing logic. This is the only adapter shipped in
  Phase 1.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every existing test in `tests/` passes without edits
  after the refactor lands.
- **SC-002**: `compute_flow_state(feature_dir)` returns the same
  `FlowStateResult` (field-by-field equality) before and after the
  refactor, for every feature directory in the repo.
- **SC-003**: CLI stdout for `python -m speckit_orca.flow_state
  <target> --format json` is byte-identical before and after the
  refactor for the same inputs.
- **SC-004**: `grep -n 'feature_path /' src/speckit_orca/flow_state.py`
  returns zero matches for spec-kit artifact filename literals
  (`"spec.md"`, `"plan.md"`, `"tasks.md"`, etc.). All such literals
  live inside the adapter module.
- **SC-005**: The adapter module is importable on its own and its
  public surface (ABC + four dataclasses + SpecKitAdapter) is covered
  by at least one direct unit test each.
- **SC-006**: No public signature on `flow_state` changes. A simple
  script importing `from speckit_orca.flow_state import ...` keeps
  working unchanged after the refactor.

## Documentation Impact *(mandatory)*

- **README Impact**: Not required for Phase 1.
- **Why**: Phase 1 is invisible to operators. README updates are
  deferred to Phase 2 (when a second real adapter lands and the
  feature becomes user-facing).
- **Expected Updates**: spec/plan/tasks for this feature only.

## Assumptions

- The current spec-kit test suite is sufficient to detect a regression.
  If a test gap exists today, it also exists after Phase 1; closing
  it is out of scope.
- Phase 2's interface needs are allowed to drive Phase 1's interface
  shape. The brainstorm's draft signatures are a starting point; Phase
  1 is free to simplify them as long as it does not actively preclude
  Phase 2 use cases (OpenSpec delta model, different feature roots).
- `compute_spec_lite_state` and `compute_adoption_state` remain on
  their current direct-parse path. Spec-lite and adoption records are
  Orca-native, not spec-kit-native, so they do not need adapter
  routing in any phase.
- `flow_state.list_yolo_runs_for_feature` stays as-is. Yolo runtime
  continues to read its own event logs directly. Adapter-awareness
  for yolo is a Phase 2+ concern, out of scope here.
- The adapter class lives in `src/speckit_orca/sdd_adapter.py` as a
  single module. A future adapters package (`adapters/`) may be
  introduced in Phase 2 when a second real adapter exists; Phase 1
  does not need the directory.
