# Implementation Plan: Multi-SDD Layer — Phase 1

**Branch**: `016-multi-sdd-layer` | **Date**: 2026-04-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/016-multi-sdd-layer/spec.md`
**Brainstorm**: [brainstorm.md](./brainstorm.md)

## Summary

Phase 1 is a pure refactor. Extract the spec-kit-specific parts of
`flow_state.py` into a named interface (`SddAdapter`) and a single
concrete implementation (`SpecKitAdapter`). Route
`collect_feature_evidence` through the adapter. Ship no new user
behavior.

The goal is not to support a second SDD format yet. The goal is to
draw the seam where that support will later plug in, validated by the
fact that the existing test suite passes unchanged through the
refactor.

## Technical Context

**Language/Version**: Python 3.10+ (matches existing codebase).
**Primary Dependencies**: no new runtime dependencies. The adapter is
internal Python.
**Storage**: no new on-disk state. The adapter is a pure function over
the existing filesystem layout.
**Testing**: `pytest`. Existing `tests/test_flow_state_*.py` suite
stays untouched. New `tests/test_sdd_adapter.py` added for adapter-
level coverage.
**Target Platform**: same as current Orca (Linux/WSL2, macOS, Docker).
**Project Type**: internal refactor of `src/speckit_orca/flow_state.py`
with one new module `src/speckit_orca/sdd_adapter.py`.
**Performance Goals**: no regression vs. current. Adapter dispatch is
one extra function call; filesystem reads are unchanged.
**Constraints**: zero user-visible behavior change. Existing tests
pass without edits. No change to CLI, extension manifest, commands,
or docs.
**Scale/Scope**: single new module, targeted refactor of one existing
module, one new test file. Roughly 200-400 LOC moved; net new LOC is
the adapter scaffolding only.

## Constitution Check

### Pre-design gates

1. **Provider-agnostic orchestration**: pass. The refactor is about
   format agnosticism, which is provider-agnostic by definition.
2. **Spec-driven delivery**: pass. Phase 1 is fully specified before
   any implementation touches the refactor target.
3. **Safe parallel work**: pass. Phase 1 touches only two files
   (`flow_state.py` and the new `sdd_adapter.py`) plus new tests. It
   does not conflict with in-flight work on matriarch, yolo, or the
   extension surface.
4. **Verification before convenience**: pass. The exit gate is
   "existing tests pass unchanged." No convenience optimization is
   allowed to bypass that.
5. **Small, composable runtime surfaces**: pass. The adapter is a
   single small module with one concrete implementation. No registry,
   no discovery, no dynamic loading.

### Post-design check

The design stays constitution-aligned if:

- the adapter module is small and standalone,
- `flow_state` shrinks rather than grows,
- no new dependencies are pulled in,
- every observable output is preserved.

No constitution violations currently need justification.

## Project Structure

### Documentation (this feature)

```text
specs/016-multi-sdd-layer/
├── brainstorm.md
├── spec.md
├── plan.md
└── tasks.md
```

No `contracts/`, `data-model.md`, `research.md`, or `quickstart.md`
for Phase 1. The spec and plan are self-contained at this scope. The
adapter interface contract is the Python ABC in `sdd_adapter.py`
plus docstrings; a separate contract document is deferred to Phase 2
when a second adapter exists to contract against.

### Source Code (repository root)

```text
src/speckit_orca/
├── sdd_adapter.py          # NEW — ABC, dataclasses, SpecKitAdapter
├── flow_state.py           # MODIFIED — collect_feature_evidence uses adapter
├── matriarch.py            # UNTOUCHED in Phase 1
├── yolo.py                 # UNTOUCHED in Phase 1
├── brainstorm_memory.py    # UNTOUCHED in Phase 1
├── context_handoffs.py     # UNTOUCHED in Phase 1
├── spec_lite.py            # UNTOUCHED
├── adoption.py             # UNTOUCHED
└── ...

tests/
├── test_sdd_adapter.py     # NEW — direct adapter coverage
├── test_flow_state_*.py    # UNTOUCHED — must pass unchanged
└── ...
```

**Structure Decision**: single-module adapter in Phase 1. If Phase 2
or Phase 3 introduces a second concrete adapter, that is the right
moment to promote `sdd_adapter.py` to an `sdd_adapter/` package with
`base.py`, `spec_kit.py`, etc. Premature packaging in Phase 1 would
add directory churn without paying for itself.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New adapter module | Phase 2 needs a named seam to plug OpenSpec into | Leaving spec-kit logic inline would require touching `flow_state.py` again for every future format |
| Adapter ABC with dataclasses | Makes the contract enforceable at subclass-time | Duck typing would leave the contract unwritten and unenforceable |
| `SpecKitAdapter` as a class, not free functions | Gives Phase 2 a subclass-able target | Free functions would require re-plumbing at Phase 2 |

No other new complexity. The refactor removes hardcoded paths from
`flow_state.py` and replaces them with a single adapter call.

## Research Decisions

### 1. Spec-kit first, alone, no registry

Decision: Phase 1 ships exactly one adapter (`SpecKitAdapter`). No
registry, no auto-detection, no `--adapter` flag.

Rationale:

- avoids premature abstraction — a registry with one entry is a
  solution to a problem that does not yet exist;
- makes the zero-behavior-change guarantee easier to honor;
- keeps the PR small enough to review against the line-by-line
  behavior of the current `flow_state.py`.

Alternatives considered:

- ship the registry and auto-detection in Phase 1: speculative without
  a second adapter to exercise it. Deferred to Phase 2.
- ship `SpecKitAdapter` plus OpenSpec stub: violates the "one adapter
  only" principle and risks the stub's gaps leaking into the
  interface design.

### 2. Adapter module, not adapter package

Decision: one file, `src/speckit_orca/sdd_adapter.py`, containing the
ABC, the dataclasses, and `SpecKitAdapter`.

Rationale:

- Phase 1 has one concrete adapter; a package for one module is
  noise;
- Phase 2 will naturally want to split when OpenSpec lands — at that
  moment, refactor to a package with `base.py`, `spec_kit.py`,
  `openspec.py`;
- keeping it one file in Phase 1 makes the refactor diff easier to
  read (one new file, one changed file).

Alternatives considered:

- `sdd_adapter/` package with `base.py` and `spec_kit.py` from day
  one: extra directory, no benefit in Phase 1.

### 3. Adapter shape matches brainstorm's draft interface, trimmed

Decision: ship `detect`, `list_features`, `load_feature`,
`compute_stage`, `id_for_path` as abstract methods. Omit the
brainstorm's optional `write_review_verdict` and `supports(...)`
helpers; they are not needed by `flow_state` in Phase 1 and risk
locking in a contract that may look different after the OpenSpec
implementation exposes its needs.

Rationale:

- smallest interface that still works;
- easier to add later than to remove;
- consistent with Phase 1's "refactor only" scope.

Alternatives considered:

- ship the full brainstorm draft interface verbatim: premature; better
  to let Phase 2's concrete second adapter inform the shape.

### 4. `NormalizedArtifacts` is a faithful proxy for `FeatureEvidence`

Decision: the dataclass is designed so that the current
`FeatureEvidence` can be constructed from it without loss.

Rationale:

- the zero-behavior-change gate is the hard constraint;
- if Phase 1 loses information, downstream output differs, and the
  gate fails;
- minor field name differences between `NormalizedArtifacts` and
  `FeatureEvidence` are acceptable; information content is not.

Alternatives considered:

- make `NormalizedArtifacts` a strict superset or strict subset of
  `FeatureEvidence`: both cause unnecessary adapter-boundary
  translation. Aim for parity.

### 5. Stage-kind abstraction is deferred

Decision: `StageProgress` in Phase 1 carries spec-kit's nine-stage
model verbatim. No stage-kind enum. No per-format stage mapping.

Rationale:

- the stage-kind enum is a Phase 2+ problem with no single right
  answer until a second real adapter exposes its stage model;
- Phase 1's `StageProgress` exists only to keep the adapter interface
  ready for Phase 2, not to solve it.

Alternatives considered:

- ship the seven-kind enum from the brainstorm now: speculative
  without a second adapter to pressure-test it. Deferred.

## Design Decisions

### 1. Interface shape

Five abstract methods, four dataclasses, one concrete subclass:

```python
@dataclass
class FeatureHandle:
    feature_id: str
    display_name: str
    root_path: Path
    adapter_name: str

@dataclass
class NormalizedTask:
    task_id: str
    text: str
    completed: bool
    assignee: str | None

@dataclass
class StageProgress:
    stage: str
    status: str
    evidence_sources: list[str]
    notes: list[str]

@dataclass
class NormalizedArtifacts:
    feature_id: str
    feature_dir: Path
    repo_root: Path | None
    artifacts: dict[str, Path]
    tasks: list[NormalizedTask]
    task_summary_data: dict  # counts the current TaskSummary carries
    review_evidence: ReviewEvidence  # reuse existing dataclass
    linked_brainstorms: list[Path]
    worktree_lanes: list[WorktreeLane]  # reuse existing dataclass
    ambiguities: list[str]
    notes: list[str]

class SddAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def detect(self, repo_root: Path) -> bool: ...
    @abstractmethod
    def list_features(self, repo_root: Path) -> list[FeatureHandle]: ...
    @abstractmethod
    def load_feature(self, handle: FeatureHandle) -> NormalizedArtifacts: ...
    @abstractmethod
    def compute_stage(
        self, artifacts: NormalizedArtifacts
    ) -> list[StageProgress]: ...
    @abstractmethod
    def id_for_path(
        self, path: Path, repo_root: Path | None = None
    ) -> str | None: ...
```

Reusing `ReviewEvidence` and `WorktreeLane` from `flow_state.py` is
intentional: Phase 1 is a refactor, not a redesign. Moving those
dataclasses into the adapter module is allowed; duplicating them is
not.

### 2. Dataclass boundary

`NormalizedArtifacts` is the single structure crossing the adapter
boundary. Everything else (`FlowStateResult`, `FlowMilestone`,
`ReviewMilestone`, the yolo-run summary) lives on the `flow_state`
side and is constructed from the adapter output.

This means:

- the adapter knows how to read files;
- `flow_state` knows how to compute stage/review/ambiguity/next-step
  semantics from the adapter output.

The seam lands exactly where it will need to land for Phase 2.

### 3. Error handling

The adapter inherits the current `_read_text_if_exists` posture: a
missing file is not an error; it is an absent artifact. No exceptions
are swallowed beyond what the current code swallows. No new exception
types are introduced.

If the adapter cannot determine a repo root, it returns `None` (same
as `_find_repo_root` today).

### 4. How `flow_state.collect_feature_evidence` uses the adapter

```python
_SPEC_KIT_ADAPTER = SpecKitAdapter()  # module-level singleton

def collect_feature_evidence(feature_dir, repo_root=None) -> FeatureEvidence:
    handle = _SPEC_KIT_ADAPTER.handle_for_feature_dir(
        Path(feature_dir), Path(repo_root) if repo_root else None
    )
    normalized = _SPEC_KIT_ADAPTER.load_feature(handle)
    return _feature_evidence_from_normalized(normalized)
```

The module-level singleton is fine in Phase 1 because there is only
one adapter. Phase 2 will replace the singleton with a registry
lookup. That change is deferred.

### 5. What does NOT change

- `FlowStateResult`, `FlowMilestone`, `ReviewMilestone`, and the
  per-review-type evidence dataclasses stay exactly where they are.
- `compute_flow_state`, `compute_spec_lite_state`,
  `compute_adoption_state`, `list_yolo_runs_for_feature`,
  `write_resume_metadata`, and `main` keep their current signatures
  and behavior.
- The CLI is untouched.
- The extension manifest is untouched.
- All command prompts are untouched.
- README is untouched.

## Implementation Phases

Phase 1 of the multi-SDD layer program breaks into four sub-phases
(A through D) for implementation and verification sequencing. See
`tasks.md` for the task breakdown.

### Sub-phase A — Interface and dataclasses

Scope: create `src/speckit_orca/sdd_adapter.py` with the ABC and the
four dataclasses (`FeatureHandle`, `NormalizedArtifacts`,
`NormalizedTask`, `StageProgress`). No concrete adapter yet. Add
Phase 1 adapter-shape tests that exercise the ABC's subclass-enforcement
behavior and the dataclass field shapes.

Exit: `test_sdd_adapter.py::test_abc_rejects_incomplete_subclass`,
`::test_dataclasses_have_expected_fields` pass.

### Sub-phase B — `SpecKitAdapter` implementation

Scope: implement `SpecKitAdapter` by moving the relevant helpers
(`_parse_tasks`, `_parse_review_evidence`, `_find_linked_brainstorms`,
`_load_worktree_lanes`, `_find_repo_root`, and the spec-kit artifact-
filename literals) into the adapter. The existing private helpers in
`flow_state.py` remain in place during this sub-phase and are deleted
in sub-phase C; keeping both during B avoids a giant atomic diff.

Exit: direct adapter unit tests pass. The existing flow-state tests
still pass because `flow_state.py` has not been rewired yet.

### Sub-phase C — Rewire `flow_state.collect_feature_evidence`

Scope: change `collect_feature_evidence` to call the adapter. Remove
the duplicated private helpers from `flow_state.py` now that the
adapter owns them.

Exit: full test suite passes unchanged. A final grep confirms no
spec-kit filename literals remain in `flow_state.py`.

### Sub-phase D — Regression verification

Scope: no code changes. Run the full test suite, run the CLI against
each fixture target, diff stdout pre- and post-refactor, and record
parity evidence.

Exit: all SC-001 through SC-006 in the spec are satisfied with
evidence.

## Verification Strategy

### Primary verification

1. Run the full `pytest tests/` suite. Every test must pass with zero
   test-code edits.
2. For every feature directory under `specs/`, assert that
   `compute_flow_state(feature_dir).to_dict()` equals a snapshot of
   the pre-refactor result. Capture snapshots by running the CLI on
   a pre-refactor checkout.
3. For every feature directory, run the CLI and diff stdout against
   the pre-refactor CLI output. Diff must be empty.
4. Add a one-line grep assertion in CI or in a test: spec-kit artifact
   filename literals (`"spec.md"`, `"plan.md"`, `"tasks.md"`,
   `"review-spec.md"`, `"review-code.md"`, `"review-pr.md"`,
   `"brainstorm.md"`) must not appear in `flow_state.py` anymore.

### Secondary verification

1. Direct adapter unit tests: `detect`, `list_features`,
   `load_feature`, `compute_stage`, `id_for_path` each get a focused
   test against synthetic fixture trees.
2. ABC subclass enforcement test: a subclass missing one of the
   abstract methods must raise `TypeError` at instantiation.
3. `NormalizedArtifacts` round-trip: calling the adapter and
   converting back into `FeatureEvidence` produces a value equal to
   calling the pre-refactor `collect_feature_evidence` directly.

## Open Questions

Deferred to Phase 2 (answer when a second adapter is on the table):

- What is the final stage-kind enum shape?
- Does the adapter interface need a write surface, and if so is it
  opt-in or required-raise?
- Should the repo-root detection move from `flow_state` into a
  per-adapter method, or stay a shared helper?

None of these block Phase 1. Phase 1's exit gate is "behavior
unchanged"; the answers above can land later without rework of the
Phase 1 refactor.
