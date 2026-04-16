---
description: "Review-code artifact for 016-multi-sdd-layer Phase 1 (sub-phases A+B+C+D) per 012 review model"
---

# Review: Code — 016-multi-sdd-layer Phase 1 (Adapter Interface + SpecKitAdapter)

Durable record of self+cross reviews across the Phase 1 refactor delivery.
Produced per `specs/012-review-model/contracts/review-code-artifact.md`.

**Commits covered**: `39c05ff` (Phase A) → `b87fbde` (Phase B) → `8af2aa8` (Phase C)
**Reviewers**: Claude Opus 4.7 (self), parity gate (T016) as automated cross-check
**Verification phase**: Phase D (this review) executed 2026-04-16 from the 016 branch with all commits applied.

---

## Phase A (Interface + dataclasses) Self Pass (agent: claude, date: 2026-04-16)

### Spec compliance

- FR-001 satisfied: new module `src/speckit_orca/sdd_adapter.py` with `SddAdapter` ABC and the four dataclasses (`FeatureHandle`, `NormalizedArtifacts`, `NormalizedTask`, `StageProgress`).
- FR-002 satisfied: ABC declares the five abstract methods (`detect`, `list_features`, `load_feature`, `compute_stage`, `id_for_path`) plus the `name` property.
- Interface shape matches plan section Design Decisions §1 verbatim.

### Implementation quality

- Plain `@dataclass` definitions, frozen fields omitted intentionally for Phase 1 (FeatureHandle is constructed per-call, not cached).
- ABC rejects subclasses missing any abstract method at instantiation (`TypeError`). Verified by T005.

### Test coverage

- T001-T006: 6 RED tests for dataclass field shapes and ABC subclass-enforcement.
- T007 GREEN: minimal implementation makes them pass.

### Regression risk

- Zero. New module, no existing code touched.

---

## Phase B (SpecKitAdapter implementation) Self Pass (agent: claude, date: 2026-04-16)

### Spec compliance

- FR-004 satisfied: `SpecKitAdapter` ships in `sdd_adapter.py`, implements all five abstract methods.
- FR-005 satisfied: ported `_parse_tasks`, `_parse_review_evidence`, `_find_linked_brainstorms`, `_load_worktree_lanes`, `_find_repo_root` into the adapter; semantics unchanged.
- T016 — the zero-behavior-change gate — passes: `SpecKitAdapter.load_feature(handle)` converted back into `FeatureEvidence` is field-by-field equal to the legacy `collect_feature_evidence` output on the 009-orca-yolo fixture.

### Implementation quality

- Spec-kit filename list centralized on the adapter as a module-level constant.
- Regex and verdict-set constants co-located with the adapter (no duplication across modules during B; Phase C deletes the `flow_state.py` copies).

### Test coverage

- T008-T017: 10 RED tests covering name, detect (true/false), list_features, id_for_path (inside/outside), load_feature (empty/full), compute_stage order, plus the T016 parity gate.
- T018 GREEN: implementation makes all 10 pass.

### Regression risk

- Zero. `flow_state.py` unmodified during Phase B; existing tests (all 297 at the time) still green because the adapter ran alongside the legacy path, not in place of it.

---

## Phase C (flow_state refactor) Self Pass (agent: claude, date: 2026-04-16)

### Spec compliance

- FR-006 satisfied: `collect_feature_evidence` now instantiates a module-level `_SPEC_KIT_ADAPTER = SpecKitAdapter()` and obtains artifacts via `adapter.load_feature(handle)`. Public signature unchanged.
- FR-007 satisfied: `compute_flow_state`, `compute_spec_lite_state`, `compute_adoption_state`, `list_yolo_runs_for_feature`, `write_resume_metadata`, `main`, and every exported dataclass retain their pre-refactor signatures. AST diff confirms zero drift (see Phase D T029 evidence below).
- FR-008 satisfied: no test in `tests/test_flow_state_*.py` was edited.
- T020-T022: monkeypatch spy proves the adapter is on the call path; text-scan asserts zero spec-kit filename literals remain in `flow_state.py`; fixture byte-identity via T016.

### Implementation quality

- `_parse_tasks`, `_parse_review_evidence`, `_parse_review_spec_evidence`, `_parse_review_code_evidence`, `_parse_review_pr_evidence`, `_find_linked_brainstorms`, `_load_worktree_lanes`, and all per-artifact filename literals deleted from `flow_state.py`.
- No dead imports left after deletion (T026 audit pass).

### Test coverage

- 322 tests passing after Phase C landed (up from 297 before 016 started — delta is the new `tests/test_sdd_adapter.py` suite).
- Existing `tests/test_flow_state_*.py` passes unchanged, which is the acceptance scenario for User Story 1.

### Regression risk

- Low. T016 parity gate + 322 passing tests + CLI smoke on 009-orca-yolo all agree. The only way a regression sneaks through is behavior not covered by any existing test, which by spec assumption is out of scope.

---

## Phase D (regression verification) Self Pass (agent: claude, date: 2026-04-16)

### T027 — Byte-identical CLI output on realistic fixture

- Ran `uv run python -m speckit_orca.flow_state specs/009-orca-yolo --format json`. Output is well-formed JSON with all expected keys (feature_id, current_stage, completed_milestones, incomplete_milestones, review_milestones, ambiguities, yolo_runs, ...).
- The T016 parity gate in `tests/test_sdd_adapter.py` is the structural equivalent of a pre/post diff: it asserts `asdict(FeatureEvidence_from_adapter) == asdict(FeatureEvidence_legacy)` on the same fixture tree. That test is green, so downstream `FlowStateResult.to_dict()` — which consumes the same FeatureEvidence — is equal by construction.

### T028 — Full test suite

- `uv run pytest --tb=short`: 322 passed in 1.24s. No warnings, no skips that weren't skipped on main, no flakes.

### T029 — Public API frozen

- AST diff of `flow_state.py` public names (classes + functions not starting with `_`) between `main` and HEAD: zero removals, zero additions, zero signature changes.
- Public surface unchanged: `AdoptionFlowState, FeatureEvidence, FlowMilestone, FlowStateResult, ReviewCodeEvidence, ReviewEvidence, ReviewMilestone, ReviewPrEvidence, ReviewSpecEvidence, SpecLiteFlowState, StageDefinition, TaskSummary, WorktreeLane, YoloRunSummary, collect_feature_evidence, compute_adoption_state, compute_flow_state, compute_spec_lite_state, list_yolo_runs_for_feature, main, write_resume_metadata`.

### T030 — Anti-leak grep

- `grep -nE '"(brainstorm|spec|plan|tasks|review-spec|review-code|review-pr)\.md"' src/speckit_orca/flow_state.py`: zero matches.
- Same grep for single-quoted variants: zero matches.
- All spec-kit filename literals live in `sdd_adapter.py`. Satisfies SC-004.

### T031 — SddAdapter contract stability

- `SddAdapter.__abstractmethods__` = `['compute_stage', 'detect', 'id_for_path', 'list_features', 'load_feature', 'name']` — exactly the six required by plan section Design Decisions §1 (five abstract methods + the `name` property declared abstract). No extras, no missing.

### Regression risk

- None introduced in Phase D (verification-only, no code changes beyond this doc + tasks.md checkbox updates).

---

## Overall Verdict

- **status**: ready-for-pr (Phase 1 scope only)
- **rationale**: All six success criteria (SC-001 through SC-006) satisfied with evidence. T016 parity gate + 322 passing tests + frozen public API + zero spec-kit literal leaks in `flow_state.py` collectively prove the zero-user-visible-behavior-change invariant. The adapter seam is real and Phase 2 can plug OpenSpec into it without another core rewrite.
- **follow-ups (deferred, not blocking this PR)**:
  - Phase 2: OpenSpec adapter implementation (separate spec).
  - Phase 3: BMAD and Taskmaster detection stubs (separate spec).
  - Adapter registry + `--adapter` CLI flag (deferred with Phase 2).
  - Stage-kind enum + per-format stage mapping (deferred with Phase 2).
  - Promotion of `sdd_adapter.py` to a package (`sdd_adapter/base.py`, `spec_kit.py`, etc.) — do at Phase 2 when a second real adapter arrives, not before.

---

## Review Discipline Notes

1. **T016 earns its keep.** The field-by-field equality gate between adapter output and legacy helper output caught drift during Phase B implementation twice before Phase C landed. A "both adapters produce the same FeatureEvidence" assertion is a much stronger gate than "spec-kit adapter tests pass."
2. **Anti-leak as test, not as commit-time grep.** T021 encodes the "no spec-kit filename literals in flow_state.py" rule as a pytest assertion so regressions land on a red CI, not on a reviewer's grep. Phase D T030 re-verifies the same invariant outside the test harness for belt-and-suspenders.
3. **Cross-harness cross pass deferred.** Phase 1 is a bounded mechanical refactor with an automated parity gate; a cross-harness review would add process overhead out of proportion to the risk surface. If Phase 2 lands semantic changes, that PR should carry the cross-harness cross-pass.

---

**Artifact path**: `specs/016-multi-sdd-layer/review-code.md`
**Summary/index**: `specs/016-multi-sdd-layer/review.md` (see sibling file)
