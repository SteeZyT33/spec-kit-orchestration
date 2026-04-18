"""019 Sub-phase C: OpenSpecAdapter tests (T038-T049).

Per-method organization. Fixtures live under
``tests/fixtures/openspec_repo_min/``; the full Sub-phase D fixture at
``tests/fixtures/openspec_repo/`` lands later.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "openspec_repo_min"


class TestDetect:
    """T038: detect returns True when openspec/ subtree exists."""

    def test_detect_true_for_fixture(self):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        assert OpenSpecAdapter().detect(FIXTURE) is True

    def test_detect_false_when_no_openspec_dir(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        assert OpenSpecAdapter().detect(tmp_path) is False

    def test_detect_true_for_empty_openspec_dir(self, tmp_path: Path):
        """Spec §Edge Cases: empty openspec/ still counts."""
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        (tmp_path / "openspec").mkdir()
        assert OpenSpecAdapter().detect(tmp_path) is True

    def test_detect_true_when_only_specs_subdir_exists(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        (tmp_path / "openspec" / "specs" / "cap").mkdir(parents=True)
        (tmp_path / "openspec" / "specs" / "cap" / "spec.md").write_text("", encoding="utf-8")
        assert OpenSpecAdapter().detect(tmp_path) is True


class TestListFeatures:
    """T039 + T040: list_features excludes archive by default, includes with flag."""

    def test_list_features_excludes_archived_by_default(self):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        handles = OpenSpecAdapter().list_features(FIXTURE)
        ids = sorted(h.feature_id for h in handles)
        assert ids == ["add-dark-mode", "minimal-change"]
        assert all(h.archived is False for h in handles)
        assert all(h.adapter_name == "openspec" for h in handles)

    def test_list_features_include_archived_appends_archive(self):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        handles = OpenSpecAdapter().list_features(FIXTURE, include_archived=True)
        ids = sorted(h.feature_id for h in handles)
        assert ids == ["add-dark-mode", "minimal-change", "shipped"]
        archived = [h for h in handles if h.archived]
        assert len(archived) == 1
        assert archived[0].feature_id == "shipped"

    def test_list_features_empty_for_non_openspec_repo(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        assert OpenSpecAdapter().list_features(tmp_path) == []


class TestFeatureHandleArchivedField:
    """T041: FeatureHandle.archived defaults to False, is a field."""

    def test_feature_handle_archived_default_false(self, tmp_path: Path):
        from dataclasses import fields as dc_fields

        from speckit_orca.sdd_adapter import FeatureHandle

        handle = FeatureHandle(
            feature_id="x",
            display_name="x",
            root_path=tmp_path,
            adapter_name="openspec",
        )
        assert handle.archived is False
        names = {f.name for f in dc_fields(FeatureHandle)}
        assert "archived" in names


class TestLoadFeature:
    """T043 + T044: load_feature populates NormalizedArtifacts per FR-009."""

    def _handle(self, feature_id: str, archived: bool = False):
        from speckit_orca.sdd_adapter import FeatureHandle

        root = (
            FIXTURE / "openspec" / "changes" / feature_id
            if not archived
            else FIXTURE
            / "openspec"
            / "changes"
            / "archive"
            / f"2026-04-01-{feature_id}"
        )
        return FeatureHandle(
            feature_id=feature_id,
            display_name=feature_id,
            root_path=root,
            adapter_name="openspec",
            archived=archived,
        )

    def test_load_feature_full_change_filenames_map(self):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        normalized = OpenSpecAdapter().load_feature(self._handle("add-dark-mode"))
        assert normalized.filenames == {
            "spec": "proposal.md",
            "plan": "design.md",
            "tasks": "tasks.md",
        }
        # Review filename keys MUST be absent (FR-009).
        for key in ("review_spec", "review_code", "review_pr"):
            assert key not in normalized.filenames

    def test_load_feature_full_change_artifacts_include_delta(self):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        normalized = OpenSpecAdapter().load_feature(self._handle("add-dark-mode"))
        keys = set(normalized.artifacts.keys())
        assert {"proposal.md", "design.md", "tasks.md"}.issubset(keys)
        # At least one specs/ delta file surfaced.
        assert any(k.startswith("specs/") for k in keys)

    def test_load_feature_tasks_parse_synthesized_ids(self):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        normalized = OpenSpecAdapter().load_feature(self._handle("add-dark-mode"))
        assert len(normalized.tasks) == 3
        ids = [t.task_id for t in normalized.tasks]
        # First task has no explicit ID -> synthesized "add-dark-mode#01".
        assert ids[0] == "add-dark-mode#01"
        # Second task has explicit T002 -> preserved verbatim.
        assert ids[1] == "T002"
        # Third task has no explicit ID -> synthesized "add-dark-mode#03".
        assert ids[2] == "add-dark-mode#03"
        # Completed flag + assignee parse.
        assert normalized.tasks[0].completed is True
        assert normalized.tasks[1].assignee == "alice"

    def test_load_feature_review_evidence_all_absent(self):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        normalized = OpenSpecAdapter().load_feature(self._handle("add-dark-mode"))
        rev = normalized.review_evidence
        assert rev.review_spec.exists is False
        assert rev.review_code.exists is False
        assert rev.review_pr.exists is False

    def test_load_feature_worktree_lanes_empty(self):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        normalized = OpenSpecAdapter().load_feature(self._handle("add-dark-mode"))
        assert normalized.worktree_lanes == []

    def test_load_feature_minimal_change_missing_design(self):
        """T044: minimal change (no design.md, no specs/) loads cleanly."""
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        normalized = OpenSpecAdapter().load_feature(self._handle("minimal-change"))
        # design.md key is present in the dict; file is absent on disk.
        assert "design.md" in normalized.artifacts
        assert normalized.artifacts["design.md"].exists() is False
        # tasks parse correctly.
        assert len(normalized.tasks) == 2
        assert normalized.tasks[0].task_id == "minimal-change#01"


class TestComputeStage:
    """T045 + T046: compute_stage lifecycle -> stage-kind mapping."""

    def _load(self, feature_id: str, archived: bool = False):
        from speckit_orca.sdd_adapter import FeatureHandle, OpenSpecAdapter

        root = (
            FIXTURE / "openspec" / "changes" / feature_id
            if not archived
            else FIXTURE
            / "openspec"
            / "changes"
            / "archive"
            / f"2026-04-01-{feature_id}"
        )
        handle = FeatureHandle(
            feature_id=feature_id,
            display_name=feature_id,
            root_path=root,
            adapter_name="openspec",
            archived=archived,
        )
        adapter = OpenSpecAdapter()
        return adapter, adapter.load_feature(handle)

    def test_compute_stage_active_emits_spec_plan_implementation(self):
        adapter, normalized = self._load("add-dark-mode")
        progress = adapter.compute_stage(normalized)
        kinds = {p.kind for p in progress}
        # Subset of {spec, plan, implementation} — NO review kinds.
        assert kinds.issubset({"spec", "plan", "tasks", "implementation"})
        assert "review_spec" not in kinds
        assert "review_code" not in kinds
        assert "review_pr" not in kinds
        # Active change: no ship kind.
        assert "ship" not in kinds

    def test_compute_stage_minimal_missing_design_not_started(self):
        """T046: missing design.md -> plan kind with 'not started' status."""
        adapter, normalized = self._load("minimal-change")
        progress = adapter.compute_stage(normalized)
        plan_entries = [p for p in progress if p.kind == "plan"]
        assert len(plan_entries) == 1
        assert plan_entries[0].status == "not started"

    def test_compute_stage_archived_emits_ship_kind(self):
        """T046: archived change -> ship kind appears."""
        adapter, normalized = self._load("shipped", archived=True)
        progress = adapter.compute_stage(normalized)
        kinds = {p.kind for p in progress}
        assert "ship" in kinds
        # Implementation is also complete for archived (everything ticked).
        assert "implementation" in kinds


class TestIdForPath:
    """T047: id_for_path active slugs, None for archive."""

    def test_id_for_path_active_proposal(self):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        proposal = FIXTURE / "openspec" / "changes" / "add-dark-mode" / "proposal.md"
        assert (
            OpenSpecAdapter().id_for_path(proposal, repo_root=FIXTURE)
            == "add-dark-mode"
        )

    def test_id_for_path_active_specs_delta(self):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        delta = (
            FIXTURE
            / "openspec"
            / "changes"
            / "add-dark-mode"
            / "specs"
            / "dark-mode.md"
        )
        assert (
            OpenSpecAdapter().id_for_path(delta, repo_root=FIXTURE)
            == "add-dark-mode"
        )

    def test_id_for_path_archive_returns_none(self):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        archived = (
            FIXTURE
            / "openspec"
            / "changes"
            / "archive"
            / "2026-04-01-shipped"
            / "proposal.md"
        )
        assert OpenSpecAdapter().id_for_path(archived, repo_root=FIXTURE) is None

    def test_id_for_path_outside_openspec_returns_none(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        outside = tmp_path / "random.md"
        outside.write_text("", encoding="utf-8")
        assert OpenSpecAdapter().id_for_path(outside, repo_root=tmp_path) is None


class TestOrderedStageKinds:
    """T049: ordered_stage_kinds is a v1-subset without review kinds."""

    def test_ordered_stage_kinds_matches_spec(self):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        kinds = OpenSpecAdapter().ordered_stage_kinds()
        # v1 vocabulary membership.
        v1 = {
            "spec",
            "plan",
            "tasks",
            "implementation",
            "review_spec",
            "review_code",
            "review_pr",
            "ship",
        }
        assert set(kinds).issubset(v1)
        # OpenSpec's native subset: spec, plan, tasks, implementation, ship.
        assert set(kinds) >= {"spec", "plan", "implementation", "ship"}
        # Review kinds MUST be excluded.
        for rk in ("review_spec", "review_code", "review_pr"):
            assert rk not in kinds


class TestSupports:
    """T048: supports truth table per FR-012."""

    def test_supports_only_adoption_true(self):
        from speckit_orca.sdd_adapter import OpenSpecAdapter

        adapter = OpenSpecAdapter()
        assert adapter.supports("adoption") is True
        assert adapter.supports("lanes") is False
        assert adapter.supports("yolo") is False
        assert adapter.supports("review_code") is False
        assert adapter.supports("review_pr") is False
        assert adapter.supports("anything-else") is False


class TestYoloRejectsOpenSpec:
    """T054 + T055: yolo entry rejects OpenSpec features."""

    def _copy_fixture(self, tmp_path: Path) -> Path:
        """Copy the min fixture under tmp_path so run writes stay isolated."""
        import shutil

        dest = tmp_path / "repo"
        shutil.copytree(FIXTURE, dest)
        return dest

    def test_yolo_cli_exits_nonzero_and_writes_no_runs(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        from speckit_orca.yolo import cli_main

        repo = self._copy_fixture(tmp_path)
        runs_dir = repo / ".specify" / "orca" / "yolo" / "runs"
        before = sorted(runs_dir.iterdir()) if runs_dir.exists() else []

        rc = cli_main(
            [
                "--root",
                str(repo),
                "start",
                "add-dark-mode",
                "--branch",
                "main",
                "--sha",
                "abc",
            ]
        )

        assert rc != 0
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "openspec" in combined
        assert "/speckit.orca.doctor" in combined

        # No runs dir created, no events written.
        after = sorted(runs_dir.iterdir()) if runs_dir.exists() else []
        assert after == before

    def test_yolo_gate_pass_through_for_spec_kit(self, tmp_path: Path):
        """spec-kit features are not gated — existing yolo paths stay green."""
        from speckit_orca.yolo import _yolo_supports_gate

        # Build a minimal spec-kit repo.
        (tmp_path / ".specify").mkdir()
        (tmp_path / ".specify" / "config.json").write_text("{}\n", encoding="utf-8")
        feature_dir = tmp_path / "specs" / "001-foo"
        feature_dir.mkdir(parents=True)
        (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")

        # supports("yolo") is True for spec-kit -> gate returns None.
        assert _yolo_supports_gate(tmp_path, "001-foo") is None
