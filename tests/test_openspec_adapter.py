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
