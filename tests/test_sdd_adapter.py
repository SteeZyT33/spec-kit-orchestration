"""Tests for the multi-SDD adapter interface (016 Phase A).

Phase A: interface and dataclasses only. No concrete adapter yet.
Phase 1 invariant: zero user-visible behavior change in Orca.
"""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Phase A: Dataclasses
# ---------------------------------------------------------------------------


class TestFeatureHandle:
    def test_feature_handle_fields(self):
        from speckit_orca.sdd_adapter import FeatureHandle

        field_map = {f.name: f.type for f in fields(FeatureHandle)}
        expected = {
            "feature_id",
            "display_name",
            "root_path",
            "adapter_name",
            "archived",  # 019 T042
        }
        assert set(field_map.keys()) == expected

    def test_feature_handle_construction(self):
        from speckit_orca.sdd_adapter import FeatureHandle

        handle = FeatureHandle(
            feature_id="009-orca-yolo",
            display_name="Orca YOLO",
            root_path=Path("/tmp/specs/009-orca-yolo"),
            adapter_name="spec-kit",
        )
        assert handle.feature_id == "009-orca-yolo"
        assert handle.adapter_name == "spec-kit"


class TestNormalizedTask:
    def test_normalized_task_fields(self):
        from speckit_orca.sdd_adapter import NormalizedTask

        field_names = {f.name for f in fields(NormalizedTask)}
        assert field_names == {"task_id", "text", "completed", "assignee"}

    def test_normalized_task_construction(self):
        from speckit_orca.sdd_adapter import NormalizedTask

        task = NormalizedTask(
            task_id="T001", text="Write tests", completed=False, assignee=None
        )
        assert task.task_id == "T001"
        assert task.completed is False
        assert task.assignee is None


class TestStageProgress:
    def test_stage_progress_fields(self):
        from speckit_orca.sdd_adapter import StageProgress

        field_names = {f.name for f in fields(StageProgress)}
        # 019 Sub-phase A: `kind` added as an additive field.
        assert field_names == {
            "stage",
            "status",
            "evidence_sources",
            "notes",
            "kind",
        }

    def test_stage_progress_construction(self):
        from speckit_orca.sdd_adapter import StageProgress

        progress = StageProgress(
            stage="specify",
            status="complete",
            evidence_sources=["/tmp/specs/009/spec.md"],
            notes=[],
            kind="spec",
        )
        assert progress.stage == "specify"
        assert progress.status == "complete"
        assert progress.kind == "spec"


class TestNormalizedArtifacts:
    def test_normalized_artifacts_fields(self):
        from speckit_orca.sdd_adapter import NormalizedArtifacts

        field_names = {f.name for f in fields(NormalizedArtifacts)}
        expected = {
            "feature_id",
            "feature_dir",
            "artifacts",
            "filenames",
            "tasks",
            "task_summary_data",
            "review_evidence",
            "linked_brainstorms",
            "worktree_lanes",
            "ambiguities",
            "notes",
        }
        assert field_names == expected


# ---------------------------------------------------------------------------
# Phase A: Abstract Base Class
# ---------------------------------------------------------------------------


class TestSddAdapterABC:
    def test_sdd_adapter_is_abstract(self):
        from speckit_orca.sdd_adapter import SddAdapter

        with pytest.raises(TypeError):
            SddAdapter()  # type: ignore[abstract]

    def test_incomplete_subclass_still_abstract(self):
        from speckit_orca.sdd_adapter import SddAdapter

        class Incomplete(SddAdapter):
            @property
            def name(self) -> str:
                return "incomplete"

            def detect(self, repo_root: Path) -> bool:
                return False

            # Missing list_features, load_feature, compute_stage, id_for_path

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_complete_subclass_can_instantiate(self):
        from speckit_orca.sdd_adapter import (
            FeatureHandle,
            NormalizedArtifacts,
            SddAdapter,
            StageProgress,
        )

        class Stub(SddAdapter):
            @property
            def name(self) -> str:
                return "stub"

            def detect(self, repo_root: Path) -> bool:
                return False

            def list_features(self, repo_root: Path) -> list[FeatureHandle]:
                return []

            def load_feature(
                self, handle: FeatureHandle
            ) -> NormalizedArtifacts:
                from speckit_orca.sdd_adapter import NormalizedArtifacts

                return NormalizedArtifacts(
                    feature_id=handle.feature_id,
                    feature_dir=handle.root_path,
                    artifacts={},
                    tasks=[],
                    task_summary_data={},
                    review_evidence=None,
                    linked_brainstorms=[],
                    worktree_lanes=[],
                    ambiguities=[],
                    notes=[],
                )

            def compute_stage(
                self, artifacts: NormalizedArtifacts
            ) -> list[StageProgress]:
                return []

            def id_for_path(
                self, path: Path, repo_root: Path | None = None
            ) -> str | None:
                return None

        obj = Stub()
        assert isinstance(obj, SddAdapter)
        assert obj.name == "stub"


# ---------------------------------------------------------------------------
# Phase B: SpecKitAdapter
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestSpecKitAdapterName:
    def test_spec_kit_adapter_name(self):
        from speckit_orca.sdd_adapter import SpecKitAdapter

        assert SpecKitAdapter().name == "spec-kit"


class TestSpecKitDetect:
    def test_spec_kit_detect_true(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import SpecKitAdapter

        _write(tmp_path / "specs" / "001-foo" / "spec.md", "# Spec\n")
        assert SpecKitAdapter().detect(tmp_path) is True

    def test_spec_kit_detect_false(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import SpecKitAdapter

        # No specs/ directory at all
        (tmp_path / "docs").mkdir()
        assert SpecKitAdapter().detect(tmp_path) is False

    def test_spec_kit_detect_empty_specs(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import SpecKitAdapter

        # specs/ exists but contains no spec.md anywhere
        (tmp_path / "specs").mkdir()
        assert SpecKitAdapter().detect(tmp_path) is False


class TestSpecKitListFeatures:
    def test_spec_kit_list_features(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import SpecKitAdapter

        _write(tmp_path / "specs" / "001-foo" / "spec.md", "# Foo\n")
        _write(tmp_path / "specs" / "002-bar" / "spec.md", "# Bar\n")

        features = SpecKitAdapter().list_features(tmp_path)

        ids = sorted(h.feature_id for h in features)
        assert ids == ["001-foo", "002-bar"]
        for handle in features:
            assert handle.adapter_name == "spec-kit"
            assert handle.root_path.name == handle.feature_id

    def test_spec_kit_list_features_empty(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import SpecKitAdapter

        assert SpecKitAdapter().list_features(tmp_path) == []


class TestSpecKitIdForPath:
    def test_spec_kit_id_for_path_inside_feature(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import SpecKitAdapter

        feature = tmp_path / "specs" / "042-widget"
        _write(feature / "anything.md", "body")
        adapter = SpecKitAdapter()

        assert adapter.id_for_path(feature / "anything.md", tmp_path) == "042-widget"
        assert adapter.id_for_path(feature / "spec.md", tmp_path) == "042-widget"

    def test_spec_kit_id_for_path_outside(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import SpecKitAdapter

        _write(tmp_path / "docs" / "readme.md", "hi")
        adapter = SpecKitAdapter()

        assert adapter.id_for_path(tmp_path / "docs" / "readme.md", tmp_path) is None


class TestSpecKitLoadFeatureEmpty:
    def test_spec_kit_load_feature_empty_dir(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import FeatureHandle, SpecKitAdapter

        feature_dir = tmp_path / "specs" / "001-empty"
        feature_dir.mkdir(parents=True)
        handle = FeatureHandle(
            feature_id="001-empty",
            display_name="001-empty",
            root_path=feature_dir,
            adapter_name="spec-kit",
        )

        normalized = SpecKitAdapter().load_feature(handle)

        assert normalized.feature_id == "001-empty"
        assert normalized.tasks == []
        assert normalized.linked_brainstorms == []
        assert normalized.worktree_lanes == []
        assert normalized.review_evidence.review_spec.exists is False
        assert normalized.review_evidence.review_code.exists is False
        assert normalized.review_evidence.review_pr.exists is False


class TestSpecKitLoadFeatureFullTree:
    def test_spec_kit_load_feature_full_tree(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import FeatureHandle, SpecKitAdapter

        feature_dir = tmp_path / "specs" / "042-widget"
        _write(feature_dir / "spec.md", "# Spec\n")
        _write(feature_dir / "plan.md", "# Plan\n")
        _write(
            feature_dir / "tasks.md",
            "\n".join(
                [
                    "# Tasks",
                    "",
                    "- [ ] T001 first task",
                    "- [ ] T002 second task [@agent-scout]",
                    "- [x] T003 third task done",
                    "",
                ]
            ),
        )
        _write(
            feature_dir / "review-spec.md",
            "\n".join(
                [
                    "# Review spec",
                    "- status: ready",
                    "",
                    "## Cross Pass (primary)",
                    "body",
                    "",
                ]
            ),
        )

        handle = FeatureHandle(
            feature_id="042-widget",
            display_name="042-widget",
            root_path=feature_dir,
            adapter_name="spec-kit",
        )
        normalized = SpecKitAdapter().load_feature(handle)

        assert len(normalized.tasks) == 3
        completed_ids = [t.task_id for t in normalized.tasks if t.completed]
        assert completed_ids == ["T003"]
        assignees = [t.assignee for t in normalized.tasks]
        # T002 carries [@agent-scout]
        assert "agent-scout" in (assignees[1] or "")
        # Review-spec evidence: verdict ready + cross pass detected
        assert normalized.review_evidence.review_spec.verdict == "ready"
        assert normalized.review_evidence.review_spec.has_cross_pass is True


class TestSpecKitLoadFeatureMatchesLegacy:
    """T016 parity gate — golden-snapshot edition.

    The prior iteration of this test compared `SpecKitAdapter` against
    `collect_feature_evidence`, but after Phase C both sides are adapter
    code, so the equality proved self-consistency rather than legacy
    parity. This version pins the pre-refactor (commit 7510fc1) JSON
    output of `compute_flow_state` as a golden snapshot per fixture and
    asserts the current code path reproduces it byte-for-byte after
    path normalization.

    Snapshots and fixture trees live under
    `tests/fixtures/flow_state_snapshots/<feature_id>/`:
      - `fixture/specs/<feature_id>/...` — frozen copy of the feature
        directory as it existed at 7510fc1
      - `fixture/.specify/`              — repo-root anchor
      - `golden.json`                    — pre-refactor CLI output with
        absolute paths replaced by `<FIXTURE_ROOT>`
    """

    SNAPSHOTS_ROOT = (
        Path(__file__).parent / "fixtures" / "flow_state_snapshots"
    )

    SNAPSHOT_FEATURES = [
        "009-orca-yolo",
        "010-orca-matriarch",
        "015-brownfield-adoption",
        "005-orca-flow-state",
    ]

    @staticmethod
    def _normalize_paths(obj, fixture_root: Path):
        root_str = str(fixture_root)
        if isinstance(obj, str):
            return obj.replace(root_str, "<FIXTURE_ROOT>")
        if isinstance(obj, list):
            return [
                TestSpecKitLoadFeatureMatchesLegacy._normalize_paths(
                    x, fixture_root
                )
                for x in obj
            ]
        if isinstance(obj, dict):
            return {
                k: TestSpecKitLoadFeatureMatchesLegacy._normalize_paths(
                    v, fixture_root
                )
                for k, v in obj.items()
            }
        return obj

    @pytest.mark.parametrize("feature_id", SNAPSHOT_FEATURES)
    def test_compute_flow_state_matches_golden(self, feature_id: str):
        from speckit_orca.flow_state import compute_flow_state

        snapshot_dir = self.SNAPSHOTS_ROOT / feature_id
        fixture_root = (snapshot_dir / "fixture").resolve()
        feature_dir = fixture_root / "specs" / feature_id
        golden_path = snapshot_dir / "golden.json"

        assert fixture_root.is_dir(), (
            f"missing fixture tree for {feature_id}: {fixture_root}"
        )
        assert golden_path.is_file(), (
            f"missing golden snapshot for {feature_id}: {golden_path}"
        )

        golden_text = golden_path.read_text(encoding="utf-8")

        result = compute_flow_state(feature_dir, repo_root=fixture_root)
        live = self._normalize_paths(result.to_dict(), fixture_root)
        # Byte-exact parity gate: serialize with the same formatting the
        # golden snapshots were captured with (`indent=2` plus trailing
        # newline) and compare the raw strings. A structural-equality
        # check would pass even if key order or whitespace drifted.
        live_text = json.dumps(live, indent=2) + "\n"

        assert live_text == golden_text, (
            f"Flow-state parity drift for {feature_id}: current output "
            f"diverges from pre-refactor (7510fc1) golden. Regenerate "
            f"golden only after verifying the drift is intentional."
        )


class TestSpecKitComputeStageOrder:
    def test_spec_kit_compute_stage_order(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import FeatureHandle, SpecKitAdapter

        feature_dir = tmp_path / "specs" / "021-three-stage"
        _write(feature_dir / "spec.md", "# Spec\n")
        _write(feature_dir / "plan.md", "# Plan\n")
        _write(
            feature_dir / "tasks.md",
            "\n".join(
                [
                    "# Tasks",
                    "",
                    "- [ ] T001 first",
                    "",
                ]
            ),
        )

        adapter = SpecKitAdapter()
        handle = FeatureHandle(
            feature_id="021-three-stage",
            display_name="021-three-stage",
            root_path=feature_dir.resolve(),
            adapter_name="spec-kit",
        )
        normalized = adapter.load_feature(handle, repo_root=tmp_path)
        stages = adapter.compute_stage(normalized)

        # Spec-kit's canonical nine-stage order.
        expected_order = [
            "brainstorm",
            "specify",
            "plan",
            "tasks",
            "assign",
            "implement",
            "review-spec",
            "review-code",
            "review-pr",
        ]
        assert [s.stage for s in stages] == expected_order

        status_map = {s.stage: s.status for s in stages}
        # spec + plan + tasks present (no reviews).
        assert status_map["specify"] == "complete"
        assert status_map["plan"] == "complete"
        assert status_map["tasks"] == "complete"
        # No reviews written.
        assert status_map["review-spec"] == "missing"
        assert status_map["review-code"] == "not_started"
        assert status_map["review-pr"] == "not_started"
        # No brainstorm file, no assignees, no completed tasks.
        assert status_map["brainstorm"] == "incomplete"
        assert status_map["assign"] == "incomplete"
        assert status_map["implement"] == "incomplete"


# ---------------------------------------------------------------------------
# Phase C: flow_state routes through SpecKitAdapter
# ---------------------------------------------------------------------------


class TestFlowStateUsesAdapter:
    """T020: `compute_flow_state` must dispatch through the module-level
    `_SPEC_KIT_ADAPTER`, not re-parse spec-kit artifacts inline.
    """

    def test_flow_state_uses_adapter(self, tmp_path: Path, monkeypatch):
        from speckit_orca import flow_state as flow_state_mod
        from speckit_orca.sdd_adapter import SpecKitAdapter

        feature_dir = tmp_path / "specs" / "030-spy"
        _write(feature_dir / "spec.md", "# Spec\n")
        _write(feature_dir / "plan.md", "# Plan\n")
        _write(feature_dir / "tasks.md", "# Tasks\n\n- [ ] T001 first\n")

        calls: list[str] = []

        class SpyAdapter(SpecKitAdapter):
            def load_feature(self, handle, repo_root=None):
                calls.append(handle.feature_id)
                return super().load_feature(handle, repo_root=repo_root)

        monkeypatch.setattr(flow_state_mod, "_SPEC_KIT_ADAPTER", SpyAdapter())

        flow_state_mod.compute_flow_state(feature_dir, repo_root=tmp_path)

        assert calls == ["030-spy"]


class TestNormalizedReviewEvidence:
    """Phase 1.5 T034: adapter-owned review-evidence types.

    These types let a second adapter populate review evidence without
    importing any ``flow_state`` internals. The field shapes mirror the
    legacy ``flow_state.ReviewEvidence`` family so
    ``SpecKitAdapter.to_feature_evidence`` can translate at the boundary.
    """

    def test_normalized_review_spec_fields(self):
        from speckit_orca.sdd_adapter import NormalizedReviewSpec

        field_names = {f.name for f in fields(NormalizedReviewSpec)}
        assert field_names == {
            "exists",
            "verdict",
            "clarify_session",
            "stale_against_clarify",
            "has_cross_pass",
        }

    def test_normalized_review_code_fields(self):
        from speckit_orca.sdd_adapter import NormalizedReviewCode

        field_names = {f.name for f in fields(NormalizedReviewCode)}
        assert field_names == {
            "exists",
            "verdict",
            "phases_found",
            "has_self_passes",
            "has_cross_passes",
            "overall_complete",
        }

    def test_normalized_review_pr_fields(self):
        from speckit_orca.sdd_adapter import NormalizedReviewPr

        field_names = {f.name for f in fields(NormalizedReviewPr)}
        assert field_names == {"exists", "verdict", "has_retro_note"}

    def test_normalized_review_evidence_fields(self):
        from speckit_orca.sdd_adapter import NormalizedReviewEvidence

        field_names = {f.name for f in fields(NormalizedReviewEvidence)}
        assert field_names == {"review_spec", "review_code", "review_pr"}

    def test_normalized_review_evidence_defaults(self):
        from speckit_orca.sdd_adapter import (
            NormalizedReviewCode,
            NormalizedReviewEvidence,
            NormalizedReviewPr,
            NormalizedReviewSpec,
        )

        ev = NormalizedReviewEvidence()
        assert isinstance(ev.review_spec, NormalizedReviewSpec)
        assert isinstance(ev.review_code, NormalizedReviewCode)
        assert isinstance(ev.review_pr, NormalizedReviewPr)
        assert ev.review_spec.exists is False
        assert ev.review_code.phases_found == []
        assert ev.review_pr.has_retro_note is False


class TestNormalizedTypesMirrorLegacyShape:
    """Phase 1.5 T034: normalized types MUST mirror legacy flow_state
    shapes field-by-field, including type annotations, field order,
    defaults, and default_factories. Codex cross-pass flagged the
    field-name-only parity tests as insufficient because they would
    miss a default drift (e.g., `phases_found` losing its
    default_factory or a new field appearing on one side only).

    This test intentionally pins the EXACT field tuples. Phase 2 tightens
    or extends these shapes deliberately; until then, drift is a bug.
    """

    @staticmethod
    def _field_signature(fld) -> tuple:
        factory = fld.default_factory
        if factory is not None and factory is not type(None):
            # dataclasses.MISSING sentinel → None for comparison purposes.
            try:
                from dataclasses import MISSING

                factory_key = (
                    None if factory is MISSING else factory.__name__
                )
            except Exception:
                factory_key = getattr(factory, "__name__", None)
        else:
            factory_key = None
        default = fld.default
        try:
            from dataclasses import MISSING

            if default is MISSING:
                default = "__MISSING__"
        except Exception:
            pass
        return (fld.name, str(fld.type), default, factory_key)

    def test_normalized_review_spec_mirrors_legacy(self):
        from speckit_orca.flow_state import ReviewSpecEvidence
        from speckit_orca.sdd_adapter import NormalizedReviewSpec

        a = [self._field_signature(f) for f in fields(NormalizedReviewSpec)]
        b = [self._field_signature(f) for f in fields(ReviewSpecEvidence)]
        assert a == b, f"NormalizedReviewSpec drifted from ReviewSpecEvidence:\n{a}\nvs\n{b}"

    def test_normalized_review_code_mirrors_legacy(self):
        from speckit_orca.flow_state import ReviewCodeEvidence
        from speckit_orca.sdd_adapter import NormalizedReviewCode

        a = [self._field_signature(f) for f in fields(NormalizedReviewCode)]
        b = [self._field_signature(f) for f in fields(ReviewCodeEvidence)]
        assert a == b, f"NormalizedReviewCode drifted from ReviewCodeEvidence:\n{a}\nvs\n{b}"

    def test_normalized_review_pr_mirrors_legacy(self):
        from speckit_orca.flow_state import ReviewPrEvidence
        from speckit_orca.sdd_adapter import NormalizedReviewPr

        a = [self._field_signature(f) for f in fields(NormalizedReviewPr)]
        b = [self._field_signature(f) for f in fields(ReviewPrEvidence)]
        assert a == b, f"NormalizedReviewPr drifted from ReviewPrEvidence:\n{a}\nvs\n{b}"

    def test_normalized_worktree_lane_mirrors_legacy(self):
        from speckit_orca.flow_state import WorktreeLane
        from speckit_orca.sdd_adapter import NormalizedWorktreeLane

        a = [self._field_signature(f) for f in fields(NormalizedWorktreeLane)]
        b = [self._field_signature(f) for f in fields(WorktreeLane)]
        assert a == b, f"NormalizedWorktreeLane drifted from WorktreeLane:\n{a}\nvs\n{b}"


class TestNormalizedWorktreeLane:
    """Phase 1.5 T034: adapter-owned worktree-lane type."""

    def test_normalized_worktree_lane_fields(self):
        from speckit_orca.sdd_adapter import NormalizedWorktreeLane

        field_names = {f.name for f in fields(NormalizedWorktreeLane)}
        assert field_names == {
            "lane_id",
            "branch",
            "status",
            "path",
            "task_scope",
        }

    def test_normalized_worktree_lane_construction(self):
        from speckit_orca.sdd_adapter import NormalizedWorktreeLane

        lane = NormalizedWorktreeLane(
            lane_id="lane-a",
            branch="feat/a",
            status="active",
            path="/tmp/wt-a",
            task_scope=["T001", "T002"],
        )
        assert lane.lane_id == "lane-a"
        assert lane.task_scope == ["T001", "T002"]

    def test_normalized_worktree_lane_default_task_scope(self):
        from speckit_orca.sdd_adapter import NormalizedWorktreeLane

        lane = NormalizedWorktreeLane(
            lane_id="lane-b", branch=None, status=None, path=None
        )
        assert lane.task_scope == []


class TestSpecKitAdapterProducesNormalizedTypes:
    """Phase 1.5 T034: ``load_feature`` returns adapter-owned types.

    The adapter must no longer leak ``flow_state.ReviewEvidence`` or
    ``flow_state.WorktreeLane`` through ``NormalizedArtifacts``. Those
    types are only reconstructed at the ``to_feature_evidence`` boundary.
    """

    def test_load_feature_returns_normalized_review_evidence(
        self, tmp_path: Path
    ):
        from speckit_orca.sdd_adapter import (
            FeatureHandle,
            NormalizedReviewEvidence,
            SpecKitAdapter,
        )

        feature_dir = tmp_path / "specs" / "099-norm"
        _write(feature_dir / "spec.md", "# Spec\n")
        _write(
            feature_dir / "review-spec.md",
            "\n".join(
                [
                    "# Review spec",
                    "- status: ready",
                    "",
                    "## Cross Pass (primary)",
                    "body",
                    "",
                ]
            ),
        )
        handle = FeatureHandle(
            feature_id="099-norm",
            display_name="099-norm",
            root_path=feature_dir,
            adapter_name="spec-kit",
        )
        normalized = SpecKitAdapter().load_feature(handle, repo_root=tmp_path)
        assert isinstance(normalized.review_evidence, NormalizedReviewEvidence)
        # And not a flow_state.ReviewEvidence
        from speckit_orca import flow_state as fs_mod

        assert not isinstance(normalized.review_evidence, fs_mod.ReviewEvidence)
        assert normalized.review_evidence.review_spec.verdict == "ready"
        assert normalized.review_evidence.review_spec.has_cross_pass is True

    def test_load_feature_returns_normalized_worktree_lanes(
        self, tmp_path: Path
    ):
        from speckit_orca.sdd_adapter import (
            FeatureHandle,
            NormalizedWorktreeLane,
            SpecKitAdapter,
        )

        feature_dir = tmp_path / "specs" / "098-lane"
        _write(feature_dir / "spec.md", "# Spec\n")
        # Minimal worktree registry + one lane file bound to this feature.
        worktrees = tmp_path / ".specify" / "orca" / "worktrees"
        _write(worktrees / "registry.json", json.dumps({"lanes": ["lane-x"]}))
        _write(
            worktrees / "lane-x.json",
            json.dumps(
                {
                    "id": "lane-x",
                    "feature": "098-lane",
                    "branch": "feat/lane-x",
                    "status": "active",
                    "path": "/tmp/wt-x",
                    "task_scope": ["T001"],
                }
            ),
        )
        # Anchor the repo so _find_repo_root accepts tmp_path.
        (tmp_path / ".specify").mkdir(exist_ok=True)

        handle = FeatureHandle(
            feature_id="098-lane",
            display_name="098-lane",
            root_path=feature_dir,
            adapter_name="spec-kit",
        )
        normalized = SpecKitAdapter().load_feature(handle, repo_root=tmp_path)
        assert len(normalized.worktree_lanes) == 1
        lane = normalized.worktree_lanes[0]
        assert isinstance(lane, NormalizedWorktreeLane)
        from speckit_orca import flow_state as fs_mod

        assert not isinstance(lane, fs_mod.WorktreeLane)
        assert lane.lane_id == "lane-x"
        assert lane.task_scope == ["T001"]


class TestToFeatureEvidenceTranslation:
    """Phase 1.5 T034: ``to_feature_evidence`` translates back at boundary.

    ``collect_feature_evidence`` still returns a ``FeatureEvidence`` that
    carries ``flow_state.ReviewEvidence`` and ``flow_state.WorktreeLane``
    instances, so flow_state consumers (and every existing test) keep
    working. This test nails the translation directly instead of relying
    on the golden snapshot to prove it.
    """

    def test_to_feature_evidence_round_trip(self, tmp_path: Path):
        from speckit_orca import flow_state as fs_mod
        from speckit_orca.sdd_adapter import FeatureHandle, SpecKitAdapter

        feature_dir = tmp_path / "specs" / "097-rt"
        _write(feature_dir / "spec.md", "# Spec\n")
        _write(feature_dir / "plan.md", "# Plan\n")
        _write(
            feature_dir / "tasks.md",
            "# Tasks\n\n- [ ] T001 a\n- [x] T002 b\n",
        )
        _write(
            feature_dir / "review-spec.md",
            "# R\n- status: ready\n\n## Cross Pass (x)\nbody\n",
        )
        _write(
            feature_dir / "review-code.md",
            "# C\n- status: ready-for-pr\n\n## P1 Self Pass (x)\nbody\n\n## P1 Cross Pass (x)\nbody\n\n## Overall Verdict\nok\n",
        )
        _write(
            feature_dir / "review-pr.md",
            "# PR\n- status: merged\n\n## Retro Note\nok\n",
        )
        # Worktree lane bound to the feature.
        worktrees = tmp_path / ".specify" / "orca" / "worktrees"
        _write(worktrees / "registry.json", json.dumps({"lanes": ["lane-r"]}))
        _write(
            worktrees / "lane-r.json",
            json.dumps(
                {
                    "id": "lane-r",
                    "feature": "097-rt",
                    "branch": "feat/r",
                    "status": "active",
                    "path": "/tmp/wt-r",
                    "task_scope": ["T001"],
                }
            ),
        )
        (tmp_path / ".specify").mkdir(exist_ok=True)

        adapter = SpecKitAdapter()
        handle = FeatureHandle(
            feature_id="097-rt",
            display_name="097-rt",
            root_path=feature_dir,
            adapter_name="spec-kit",
        )
        normalized = adapter.load_feature(handle, repo_root=tmp_path)
        evidence = adapter.to_feature_evidence(normalized, repo_root=tmp_path)

        # FeatureEvidence carries the LEGACY flow_state types.
        assert isinstance(evidence.review_evidence, fs_mod.ReviewEvidence)
        assert isinstance(
            evidence.review_evidence.review_spec, fs_mod.ReviewSpecEvidence
        )
        assert isinstance(
            evidence.review_evidence.review_code, fs_mod.ReviewCodeEvidence
        )
        assert isinstance(
            evidence.review_evidence.review_pr, fs_mod.ReviewPrEvidence
        )
        # Field values preserved through the round-trip.
        assert evidence.review_evidence.review_spec.verdict == "ready"
        assert evidence.review_evidence.review_spec.has_cross_pass is True
        # clarify_session + stale_against_clarify start at their defaults
        # for this fixture; we cover the populated/stale path separately.
        assert evidence.review_evidence.review_spec.clarify_session is None
        assert (
            evidence.review_evidence.review_spec.stale_against_clarify is False
        )
        assert evidence.review_evidence.review_code.verdict == "ready-for-pr"
        assert evidence.review_evidence.review_code.has_self_passes is True
        assert evidence.review_evidence.review_code.has_cross_passes is True
        assert evidence.review_evidence.review_code.overall_complete is True
        assert evidence.review_evidence.review_pr.verdict == "merged"
        assert evidence.review_evidence.review_pr.has_retro_note is True
        # Worktree lanes translated to flow_state.WorktreeLane.
        assert len(evidence.worktree_lanes) == 1
        lane = evidence.worktree_lanes[0]
        assert isinstance(lane, fs_mod.WorktreeLane)
        assert lane.lane_id == "lane-r"
        assert lane.branch == "feat/r"
        assert lane.status == "active"
        assert lane.path == "/tmp/wt-r"
        assert lane.task_scope == ["T001"]


class TestToFeatureEvidenceClarifySessionTranslation:
    """Phase 1.5 T034 (codex follow-up): the bridge must preserve
    ``clarify_session`` and ``stale_against_clarify`` end-to-end.

    The golden parity gate cannot catch a regression here because
    ``FlowStateResult.to_dict()`` does not serialize raw review evidence.
    This test pins the translation directly.
    """

    def test_clarify_session_populated_and_not_stale(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import FeatureHandle, SpecKitAdapter

        feature_dir = tmp_path / "specs" / "096-clar"
        _write(
            feature_dir / "spec.md",
            "\n".join(
                [
                    "# Spec",
                    "",
                    "## Clarifications",
                    "",
                    "### Session 2026-04-15",
                    "",
                    "body",
                    "",
                ]
            ),
        )
        _write(
            feature_dir / "review-spec.md",
            "\n".join(
                [
                    "# R",
                    "- status: ready",
                    "- Clarify session: 2026-04-15",
                    "",
                    "## Cross Pass (x)",
                    "body",
                    "",
                ]
            ),
        )
        adapter = SpecKitAdapter()
        handle = FeatureHandle(
            feature_id="096-clar",
            display_name="096-clar",
            root_path=feature_dir,
            adapter_name="spec-kit",
        )
        normalized = adapter.load_feature(handle, repo_root=tmp_path)
        evidence = adapter.to_feature_evidence(normalized, repo_root=tmp_path)

        assert (
            normalized.review_evidence.review_spec.clarify_session
            == "2026-04-15"
        )
        assert (
            normalized.review_evidence.review_spec.stale_against_clarify
            is False
        )
        assert (
            evidence.review_evidence.review_spec.clarify_session == "2026-04-15"
        )
        assert (
            evidence.review_evidence.review_spec.stale_against_clarify is False
        )

    def test_clarify_session_stale_against_newer_clarify(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import FeatureHandle, SpecKitAdapter

        feature_dir = tmp_path / "specs" / "095-stale"
        # Spec has a NEWER clarify session than the review-spec cites.
        _write(
            feature_dir / "spec.md",
            "\n".join(
                [
                    "# Spec",
                    "",
                    "## Clarifications",
                    "",
                    "### Session 2026-04-10",
                    "",
                    "older",
                    "",
                    "### Session 2026-04-20",
                    "",
                    "newer",
                    "",
                ]
            ),
        )
        _write(
            feature_dir / "review-spec.md",
            "\n".join(
                [
                    "# R",
                    "- status: ready",
                    "- Clarify session: 2026-04-10",
                    "",
                    "## Cross Pass (x)",
                    "body",
                    "",
                ]
            ),
        )
        adapter = SpecKitAdapter()
        handle = FeatureHandle(
            feature_id="095-stale",
            display_name="095-stale",
            root_path=feature_dir,
            adapter_name="spec-kit",
        )
        normalized = adapter.load_feature(handle, repo_root=tmp_path)
        evidence = adapter.to_feature_evidence(normalized, repo_root=tmp_path)

        assert (
            normalized.review_evidence.review_spec.clarify_session
            == "2026-04-10"
        )
        assert (
            normalized.review_evidence.review_spec.stale_against_clarify
            is True
        )
        assert (
            evidence.review_evidence.review_spec.clarify_session == "2026-04-10"
        )
        assert (
            evidence.review_evidence.review_spec.stale_against_clarify is True
        )


# ---------------------------------------------------------------------------
# 019 Sub-phase A: ABC extension (ordered_stage_kinds, supports, kind field,
# underscored filename keys, compute_stage kind attachment).
# ---------------------------------------------------------------------------


V1_STAGE_KINDS = [
    "spec",
    "plan",
    "tasks",
    "implementation",
    "review_spec",
    "review_code",
    "review_pr",
    "ship",
]


class _MinimalAdapter:
    """Helper: a minimal SddAdapter subclass used to exercise defaults
    on the ABC for `ordered_stage_kinds` and `supports`. Defined as a
    factory inside each test to avoid import-time coupling.
    """


def _make_minimal_adapter_cls():
    from speckit_orca.sdd_adapter import (
        FeatureHandle,
        NormalizedArtifacts,
        SddAdapter,
        StageProgress,
    )

    class Minimal(SddAdapter):
        @property
        def name(self) -> str:
            return "minimal"

        def detect(self, repo_root: Path) -> bool:
            return False

        def list_features(self, repo_root: Path) -> list[FeatureHandle]:
            return []

        def load_feature(self, handle: FeatureHandle) -> NormalizedArtifacts:  # pragma: no cover
            raise NotImplementedError

        def compute_stage(
            self, artifacts: NormalizedArtifacts
        ) -> list[StageProgress]:
            return []

        def id_for_path(
            self, path: Path, repo_root: Path | None = None
        ) -> str | None:
            return None

    return Minimal


class TestSddAdapterOrderedStageKindsDefault:
    """T002: ABC default for `ordered_stage_kinds` returns the v1 list."""

    def test_default_returns_v1_vocabulary(self):
        cls = _make_minimal_adapter_cls()
        assert cls().ordered_stage_kinds() == V1_STAGE_KINDS


class TestSddAdapterSupportsDefault:
    """T003: ABC default for `supports` returns False for every capability."""

    def test_default_returns_false_for_all_v1_capabilities(self):
        cls = _make_minimal_adapter_cls()
        adapter = cls()
        for cap in (
            "lanes",
            "yolo",
            "review_code",
            "review_pr",
            "adoption",
            "anything-else",
        ):
            assert adapter.supports(cap) is False, cap


class TestStageProgressHasKind:
    """T005: StageProgress gains a `kind` field."""

    def test_stage_progress_kind_field_present(self):
        from speckit_orca.sdd_adapter import StageProgress

        names = {f.name for f in fields(StageProgress)}
        assert "kind" in names

    def test_stage_progress_construct_with_kind(self):
        from speckit_orca.sdd_adapter import StageProgress

        sp = StageProgress(
            stage="specify",
            status="complete",
            evidence_sources=[],
            notes=[],
            kind="spec",
        )
        assert sp.kind == "spec"


class TestSpecKitFilenameMapUnderscoredKeys:
    """T007: `_FILENAME_MAP` uses underscored semantic keys."""

    def test_filename_map_exact_shape(self):
        from speckit_orca.sdd_adapter import SpecKitAdapter

        assert SpecKitAdapter._FILENAME_MAP == {
            "spec": "spec.md",
            "plan": "plan.md",
            "tasks": "tasks.md",
            "review_spec": "review-spec.md",
            "review_code": "review-code.md",
            "review_pr": "review-pr.md",
        }


class TestSpecKitFilenameMapSemanticKeys:
    """T008: per-key semantic mapping; `brainstorm` is not in the map."""

    def test_per_key_semantic_mapping(self):
        from speckit_orca.sdd_adapter import SpecKitAdapter

        m = SpecKitAdapter._FILENAME_MAP
        assert m["spec"] == "spec.md"
        assert m["plan"] == "plan.md"
        assert m["tasks"] == "tasks.md"
        assert m["review_spec"] == "review-spec.md"
        assert m["review_code"] == "review-code.md"
        assert m["review_pr"] == "review-pr.md"
        assert "brainstorm" not in m


class TestSpecKitOrderedStageKinds:
    """T010: SpecKitAdapter returns native-order v1 subset."""

    def test_returns_native_order_subset(self):
        from speckit_orca.sdd_adapter import SpecKitAdapter

        kinds = SpecKitAdapter().ordered_stage_kinds()
        for k in kinds:
            assert k in V1_STAGE_KINDS, k
        # Native spec-kit order matches the v1 canonical list.
        assert kinds == V1_STAGE_KINDS


class TestSpecKitSupports:
    """T011: FR-014 truth table."""

    def test_supports_truth_table(self):
        from speckit_orca.sdd_adapter import SpecKitAdapter

        a = SpecKitAdapter()
        assert a.supports("lanes") is True
        assert a.supports("yolo") is True
        assert a.supports("review_code") is True
        assert a.supports("review_pr") is True
        assert a.supports("adoption") is True
        assert a.supports("unknown") is False


class TestSpecKitComputeStageAttachesKind:
    """T012: FR-015 stage-name → kind mapping."""

    def test_compute_stage_attaches_kind_per_fr015(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import FeatureHandle, SpecKitAdapter

        feature_dir = tmp_path / "specs" / "077-kind"
        _write(feature_dir / "brainstorm.md", "# B\n")
        _write(feature_dir / "spec.md", "# S\n")
        _write(feature_dir / "plan.md", "# P\n")
        _write(
            feature_dir / "tasks.md",
            "# T\n\n- [ ] T001 first [@agent-a]\n- [x] T002 second\n",
        )
        _write(
            feature_dir / "review-spec.md",
            "# R\n- status: ready\n\n## Cross Pass (x)\nbody\n",
        )
        _write(
            feature_dir / "review-code.md",
            "# C\n- status: ready-for-pr\n\n## P1 Self Pass (x)\nbody\n\n## P1 Cross Pass (x)\nbody\n\n## Overall Verdict\nok\n",
        )
        _write(
            feature_dir / "review-pr.md",
            "# PR\n- status: merged\n\n## Retro Note\nok\n",
        )
        adapter = SpecKitAdapter()
        handle = FeatureHandle(
            feature_id="077-kind",
            display_name="077-kind",
            root_path=feature_dir.resolve(),
            adapter_name="spec-kit",
        )
        normalized = adapter.load_feature(handle, repo_root=tmp_path)
        stages = adapter.compute_stage(normalized)

        mapping = {s.stage: s.kind for s in stages}
        assert mapping == {
            "brainstorm": "spec",
            "specify": "spec",
            "plan": "plan",
            "tasks": "tasks",
            "assign": "tasks",
            "implement": "implementation",
            "review-spec": "review_spec",
            "review-code": "review_code",
            "review-pr": "review_pr",
        }
        # Every emitted kind belongs to the adapter's ordered list.
        allowed = set(adapter.ordered_stage_kinds())
        for s in stages:
            assert s.kind in allowed, s


class TestFlowStateNoSpeckitPathLiterals:
    """T021 / T030: spec-kit artifact filename literals must not appear in
    `src/speckit_orca/flow_state.py`. The adapter owns those filenames now.
    """

    def test_flow_state_no_speckit_path_literals(self):
        import speckit_orca.flow_state as flow_state_mod

        source = Path(flow_state_mod.__file__).read_text(encoding="utf-8")
        forbidden = (
            '"spec.md"',
            "'spec.md'",
            '"plan.md"',
            "'plan.md'",
            '"tasks.md"',
            "'tasks.md'",
            '"review-spec.md"',
            "'review-spec.md'",
            '"review-code.md"',
            "'review-code.md'",
            '"review-pr.md"',
            "'review-pr.md'",
            '"brainstorm.md"',
            "'brainstorm.md'",
        )
        leaks = [literal for literal in forbidden if literal in source]
        assert not leaks, (
            "flow_state.py must not hardcode spec-kit filenames; use "
            "constants imported from speckit_orca.sdd_adapter instead. "
            f"Leaked literals: {leaks}"
        )
