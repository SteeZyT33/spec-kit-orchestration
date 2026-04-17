---
description: "Review-code artifact for 016-multi-sdd-layer Phase 1 (sub-phases A+B+C+D) per 012 review model"
---

# Review: Code — 016-multi-sdd-layer Phase 1 (Adapter Interface + SpecKitAdapter)

Durable record of self+cross reviews across the Phase 1 refactor delivery.
Produced per `specs/012-review-model/contracts/review-code-artifact.md`.

**Commits covered**: `39c05ff` (Phase A) → `b87fbde` (Phase B) → `8af2aa8` (Phase C) → `ced6092` (golden-snapshot parity gate) → `1186153` (ABC signature alignment)
**Reviewers**: Claude Opus 4.7 (self), Codex (cross-harness cross pass)
**Verification phase**: Phase D executed 2026-04-16 from the 016 branch. Codex cross pass landed 2026-04-16 and surfaced two BLOCKERs + two WARNINGs; both BLOCKERs are resolved in `ced6092` and `1186153` and are re-reviewed below.

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
- T016 in its original form compared the adapter output against `collect_feature_evidence`; once Phase C rewired `collect_feature_evidence` through the adapter, both sides of that assertion became adapter code (self-consistency, not legacy parity). Codex cross pass flagged this as BLOCKER 1. Resolved in `ced6092` by capturing frozen golden snapshots from the pre-refactor commit `7510fc1` and asserting current `compute_flow_state` output equals them after path normalization. See the updated SC-002/SC-003 evidence entries under Phase D below.

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

- 325 tests passing after the golden-snapshot T016 rewrite landed. Phase C itself closed at 322; `ced6092` replaced 1 legacy self-consistency assertion with 4 parametrized golden-snapshot comparisons (net +3).
- Existing `tests/test_flow_state_*.py` passes unchanged, which is the acceptance scenario for User Story 1.

### Regression risk

- Low. Golden-snapshot parity gate on four realistic features (009-orca-yolo, 010-orca-matriarch, 015-brownfield-adoption, 005-orca-flow-state) + 325 passing tests + CLI smoke on 009-orca-yolo all agree. The only way a regression sneaks through is behavior not covered by any existing test or fixture, which by spec assumption is out of scope.

---

## Phase D (regression verification) Self Pass (agent: claude, date: 2026-04-16)

### T027 / SC-003 — Byte-identical CLI output on realistic fixtures

- Golden snapshots captured from commit `7510fc1` (pre-refactor) using the pre-refactor `compute_flow_state` against frozen copies of four feature directories. Snapshots live under `tests/fixtures/flow_state_snapshots/<feature_id>/golden.json` and their matching `fixture/` trees are checked into the repo.
- The parametrized test `TestSpecKitLoadFeatureMatchesLegacy::test_compute_flow_state_matches_golden` runs the post-refactor `compute_flow_state` against each fixture, normalizes absolute paths (`<FIXTURE_ROOT>` placeholder), and asserts equality with the golden JSON. All four cases pass: `009-orca-yolo`, `010-orca-matriarch`, `015-brownfield-adoption`, `005-orca-flow-state`.
- This is the real SC-002 and SC-003 evidence: same input, byte-identical JSON output, before and after Phase 1.

### T028 — Full test suite

- `uv run pytest --tb=short`: 325 passed. No warnings, no skips that weren't skipped on main, no flakes.

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

---

## Codex Cross Pass (agent: codex, date: 2026-04-16)

### Findings

- **BLOCKER 1 — T016 was not a real parity gate.** After Phase C, `collect_feature_evidence` routes through the adapter, so the old T016 compared adapter output to adapter output. **Resolution**: commit `ced6092` captures golden JSON snapshots from the pre-refactor commit `7510fc1` against frozen fixture trees for four real features, and T016 is now a parametrized byte-equality gate between the current `compute_flow_state` output and those snapshots. This is the actual SC-002/SC-003 evidence.
- **BLOCKER 2 — Review docs overstated readiness.** `review-code.md` and `review.md` claimed ready-for-pr while still citing the self-consistent T016. **Resolution**: this doc now records the cross-pass findings, and readiness is re-gated on BLOCKERs being fixed with tests green (they are).
- **WARNING 1 — `NormalizedArtifacts` carries flow_state types.** `review_evidence`, `worktree_lanes`, and the to-`FeatureEvidence` bridge all reach back into `flow_state.py` types. This is a real leak but it is architectural (Phase 2 concern). **Resolution**: deferred. Tracked as a PHASE-1.5-DEFERRED follow-up in `tasks.md`: introduce `NormalizedReviewEvidence` and `NormalizedWorktreeLane` types in `sdd_adapter.py` before the OpenSpec adapter is built.
- **WARNING 2 — `id_for_path` ABC signature did not match spec.** The ABC was `id_for_path(self, path)`; the spec says `id_for_path(path, repo_root)`. The concrete `SpecKitAdapter` already implemented the two-arg form. **Resolution**: commit `1186153` updates the ABC to `id_for_path(self, path, repo_root=None)` with docstring explaining the fallback. Existing single-arg call sites (T012/T013) still work via the default.

### Cross Pass Verdict

- All BLOCKERs resolved, both WARNINGs triaged. Cross pass clears the refactor for PR subject to the tests-green confirmation below.

---

## Overall Verdict

- **status**: ready-for-pr (Phase 1 scope only)
- **rationale**: Both Codex BLOCKERs are closed in `ced6092` and `1186153`. All six success criteria (SC-001 through SC-006) are now satisfied with real evidence: the new golden-snapshot parity gate covers SC-002/SC-003 (not self-consistency), the ABC signature matches the spec, and 325 tests pass locally. The adapter seam is real and Phase 2 can plug OpenSpec into it without another core rewrite.
- **follow-ups (deferred, not blocking this PR)**:
  - **Phase 1.5 deferred**: introduce `NormalizedReviewEvidence` and `NormalizedWorktreeLane` in `sdd_adapter.py` so adapters do not need to import `flow_state` types. Required before any second adapter lands.
  - Phase 2: OpenSpec adapter implementation (separate spec).
  - Phase 3: BMAD and Taskmaster detection stubs (separate spec).
  - Adapter registry + `--adapter` CLI flag (deferred with Phase 2).
  - Stage-kind enum + per-format stage mapping (deferred with Phase 2).
  - Promotion of `sdd_adapter.py` to a package (`sdd_adapter/base.py`, `spec_kit.py`, etc.) — do at Phase 2 when a second real adapter arrives, not before.

---

## Review Discipline Notes

1. **Self-consistency is not parity.** The first T016 iteration compared adapter to adapter after Phase C and still looked green; Codex cross pass caught it. The lesson: a parity gate for a refactor has to anchor on frozen pre-refactor output, not on a reference implementation that also got rewritten. The new T016 captures `compute_flow_state` JSON at `7510fc1` and diffs it against current output byte-for-byte with path normalization.
2. **Anti-leak as test, not as commit-time grep.** T021 encodes the "no spec-kit filename literals in flow_state.py" rule as a pytest assertion so regressions land on a red CI, not on a reviewer's grep. Phase D T030 re-verifies the same invariant outside the test harness for belt-and-suspenders.
3. **Cross-harness cross pass IS the backstop for mechanical refactors.** The prior review doc argued a cross-harness pass was unnecessary for a bounded refactor. Codex caught two correctness issues (BLOCKER 1, WARNING 2) the self-pass had explicitly reasoned away. For any refactor touching a parity invariant, the cross-pass should run, even when the risk looks low.

---

**Artifact path**: `specs/016-multi-sdd-layer/review-code.md`
**Summary/index**: `specs/016-multi-sdd-layer/review.md` (see sibling file)
