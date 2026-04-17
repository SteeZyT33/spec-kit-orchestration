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
        expected = {"feature_id", "display_name", "root_path", "adapter_name"}
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
        assert field_names == {"stage", "status", "evidence_sources", "notes"}

    def test_stage_progress_construction(self):
        from speckit_orca.sdd_adapter import StageProgress

        progress = StageProgress(
            stage="specify",
            status="complete",
            evidence_sources=["/tmp/specs/009/spec.md"],
            notes=[],
        )
        assert progress.stage == "specify"
        assert progress.status == "complete"


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
