"""019 Sub-phase B: AdapterRegistry tests (T018-T023).

Red-first tests for the new registry surface. Each test targets a method
on ``speckit_orca.sdd_adapter.AdapterRegistry`` or the module-level
``registry`` instance that must be populated with ``SpecKitAdapter()``
at import time.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_spec_kit_fixture(root: Path, feature_id: str = "042-widget") -> Path:
    """Build the minimum tree SpecKitAdapter detects as a feature."""

    _write(root / ".specify" / "config.json", "{}\n")
    feature_dir = root / "specs" / feature_id
    _write(feature_dir / "spec.md", "# Spec\n")
    return feature_dir


class TestAdapterRegistryRegistration:
    """T018: register is idempotent by adapter name."""

    def test_register_is_idempotent_by_name(self):
        from speckit_orca.sdd_adapter import AdapterRegistry, SpecKitAdapter

        reg = AdapterRegistry()
        reg.register(SpecKitAdapter())
        reg.register(SpecKitAdapter())

        assert len(reg.adapters()) == 1

    def test_register_second_distinct_adapter_adds_entry(self):
        from speckit_orca.sdd_adapter import (
            AdapterRegistry,
            SddAdapter,
            SpecKitAdapter,
        )

        class _StubAdapter(SddAdapter):
            @property
            def name(self) -> str:
                return "stub-for-registry-test"

            def detect(self, repo_root):
                return False

            def list_features(self, repo_root):
                return []

            def load_feature(self, handle):  # pragma: no cover - not exercised
                raise NotImplementedError

            def compute_stage(self, artifacts):  # pragma: no cover
                raise NotImplementedError

            def id_for_path(self, path, repo_root=None):
                return None

        reg = AdapterRegistry()
        reg.register(SpecKitAdapter())
        reg.register(_StubAdapter())

        assert len(reg.adapters()) == 2


class TestAdapterRegistryResolveForPath:
    """T019 + T020: resolve_for_path returns correct adapter or None."""

    def test_resolve_for_path_spec_kit_fixture(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import (
            AdapterRegistry,
            SpecKitAdapter,
        )

        feature_dir = _make_spec_kit_fixture(tmp_path, "042-widget")
        spec_md = feature_dir / "spec.md"

        reg = AdapterRegistry()
        reg.register(SpecKitAdapter())

        resolved = reg.resolve_for_path(spec_md, repo_root=tmp_path)

        assert resolved is not None
        adapter, feature_id = resolved
        assert isinstance(adapter, SpecKitAdapter)
        assert feature_id == "042-widget"

    def test_resolve_for_path_unrelated_returns_none(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import (
            AdapterRegistry,
            SpecKitAdapter,
        )

        unrelated = tmp_path / "nowhere" / "file.md"
        _write(unrelated, "# nope\n")

        reg = AdapterRegistry()
        reg.register(SpecKitAdapter())

        assert reg.resolve_for_path(unrelated) is None


class TestAdapterRegistryResolveForFeature:
    """T021: resolve_for_feature returns matching (adapter, FeatureHandle)."""

    def test_resolve_for_feature_returns_matching_handle(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import (
            AdapterRegistry,
            FeatureHandle,
            SpecKitAdapter,
        )

        _make_spec_kit_fixture(tmp_path, "001-foo")

        reg = AdapterRegistry()
        reg.register(SpecKitAdapter())

        resolved = reg.resolve_for_feature(tmp_path, "001-foo")
        assert resolved is not None
        adapter, handle = resolved
        assert isinstance(adapter, SpecKitAdapter)
        assert isinstance(handle, FeatureHandle)
        assert handle.feature_id == "001-foo"

    def test_resolve_for_feature_missing_returns_none(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import AdapterRegistry, SpecKitAdapter

        _make_spec_kit_fixture(tmp_path, "001-foo")
        reg = AdapterRegistry()
        reg.register(SpecKitAdapter())

        assert reg.resolve_for_feature(tmp_path, "999-missing") is None


class TestAdapterRegistryResolveForRepo:
    """T022: resolve_for_repo returns adapters whose detect is True."""

    def test_single_format_returns_one_adapter(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import AdapterRegistry, SpecKitAdapter

        _make_spec_kit_fixture(tmp_path, "001-foo")

        reg = AdapterRegistry()
        reg.register(SpecKitAdapter())

        resolved = reg.resolve_for_repo(tmp_path)
        assert len(resolved) == 1
        assert isinstance(resolved[0], SpecKitAdapter)

    def test_empty_repo_returns_empty_tuple(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import AdapterRegistry, SpecKitAdapter

        reg = AdapterRegistry()
        reg.register(SpecKitAdapter())

        resolved = reg.resolve_for_repo(tmp_path)
        assert resolved == ()


class TestAdapterRegistryResetToDefaults:
    """T023: reset_to_defaults restores in-tree adapters."""

    def test_reset_to_defaults_restores_in_tree_adapters(self):
        from speckit_orca.sdd_adapter import (
            AdapterRegistry,
            SddAdapter,
            SpecKitAdapter,
        )

        class _StubAdapter(SddAdapter):
            @property
            def name(self) -> str:
                return "reset-test-stub"

            def detect(self, repo_root):
                return False

            def list_features(self, repo_root):
                return []

            def load_feature(self, handle):  # pragma: no cover
                raise NotImplementedError

            def compute_stage(self, artifacts):  # pragma: no cover
                raise NotImplementedError

            def id_for_path(self, path, repo_root=None):
                return None

        reg = AdapterRegistry()
        reg.register(SpecKitAdapter())
        reg.register(_StubAdapter())
        assert len(reg.adapters()) == 2

        reg.reset_to_defaults()
        names = [a.name for a in reg.adapters()]
        assert "reset-test-stub" not in names
        # 019 T050: post-Sub-phase-C default is spec-kit then openspec.
        assert names == ["spec-kit", "openspec"]


class TestModuleLevelRegistry:
    """Module-level ``registry`` must be prepopulated with SpecKitAdapter."""

    def test_module_level_registry_exists_and_has_spec_kit(self):
        from speckit_orca.sdd_adapter import SpecKitAdapter, registry

        names = [a.name for a in registry.adapters()]
        assert "spec-kit" in names
        assert any(isinstance(a, SpecKitAdapter) for a in registry.adapters())


class TestSubPhaseCDefaultRegistry:
    """T051 + T052 + T053: registry contains both adapters; resolves each."""

    def test_t051_default_registry_lists_both_adapters_in_order(self):
        from speckit_orca.sdd_adapter import AdapterRegistry

        reg = AdapterRegistry()
        reg.reset_to_defaults()
        assert [a.name for a in reg.adapters()] == ["spec-kit", "openspec"]

    def test_t052_resolve_for_path_openspec_fixture(self, tmp_path: Path):
        from speckit_orca.sdd_adapter import AdapterRegistry, OpenSpecAdapter

        # Minimal inline OpenSpec layout (no shared fixture dep here).
        proposal = tmp_path / "openspec" / "changes" / "add-dark-mode" / "proposal.md"
        _write(proposal, "# proposal\n")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

        reg = AdapterRegistry()
        reg.reset_to_defaults()

        resolved = reg.resolve_for_path(proposal, repo_root=tmp_path)
        assert resolved is not None
        adapter, feature_id = resolved
        assert isinstance(adapter, OpenSpecAdapter)
        assert feature_id == "add-dark-mode"

    def test_t053_mixed_repo_routes_each_path_to_correct_adapter(
        self, tmp_path: Path
    ):
        from speckit_orca.sdd_adapter import (
            AdapterRegistry,
            OpenSpecAdapter,
            SpecKitAdapter,
        )

        # Spec-kit side
        _make_spec_kit_fixture(tmp_path, "001-foo")
        # OpenSpec side
        proposal = tmp_path / "openspec" / "changes" / "bar" / "proposal.md"
        _write(proposal, "# proposal\n")

        spec_md = tmp_path / "specs" / "001-foo" / "spec.md"

        reg = AdapterRegistry()
        reg.reset_to_defaults()

        sk = reg.resolve_for_path(spec_md, repo_root=tmp_path)
        os_ = reg.resolve_for_path(proposal, repo_root=tmp_path)

        assert sk is not None and isinstance(sk[0], SpecKitAdapter)
        assert sk[1] == "001-foo"
        assert os_ is not None and isinstance(os_[0], OpenSpecAdapter)
        assert os_[1] == "bar"
        # Sanity: neither path resolves to both.
        assert not isinstance(sk[0], OpenSpecAdapter)
        assert not isinstance(os_[0], SpecKitAdapter)
