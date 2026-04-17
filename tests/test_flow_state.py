"""019 Sub-phase A: dashed-key filename deprecation on FeatureEvidence.

Phase 1 consumers read `FeatureEvidence.filenames["review-spec"]` with
dashed keys. Phase 2 migrates `SpecKitAdapter._FILENAME_MAP` to
underscored canonical keys (FR-013); a one-release read alias in
`flow_state.py` keeps dashed-key reads working and emits a
`DeprecationWarning`. Underscored access emits no warning.
"""

from __future__ import annotations

import warnings
from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_feature_evidence(tmp_path: Path):
    from speckit_orca import flow_state as fs_mod

    feature_dir = tmp_path / "specs" / "050-dash"
    _write(feature_dir / "spec.md", "# Spec\n")
    (tmp_path / ".specify").mkdir(exist_ok=True)
    ev = fs_mod.collect_feature_evidence(feature_dir, repo_root=tmp_path)
    return ev


class TestDashedKeyFilenameAlias:
    """T014: dashed-key read on FeatureEvidence.filenames works and warns."""

    def test_dashed_key_read_emits_deprecation_warning(self, tmp_path: Path):
        ev = _build_feature_evidence(tmp_path)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            value = ev.filenames["review-spec"]

        assert value == "review-spec.md"
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(deprecations) >= 1
        msg = str(deprecations[0].message)
        assert "review-spec" in msg
        assert "review_spec" in msg

    def test_underscored_key_read_does_not_warn(self, tmp_path: Path):
        ev = _build_feature_evidence(tmp_path)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            value = ev.filenames["review_spec"]

        assert value == "review-spec.md"
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deprecations == []

    def test_all_three_dashed_review_keys_alias(self, tmp_path: Path):
        ev = _build_feature_evidence(tmp_path)
        # Suppress warnings; alias behavior is the subject here.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert ev.filenames["review-spec"] == "review-spec.md"
            assert ev.filenames["review-code"] == "review-code.md"
            assert ev.filenames["review-pr"] == "review-pr.md"


# ---------------------------------------------------------------------------
# 019 Sub-phase B: registry routing + deprecated singleton access.
# ---------------------------------------------------------------------------


class _SpySpecKitAdapterFactory:
    """Build subclasses that record which methods were called."""

    @staticmethod
    def build():
        from speckit_orca.sdd_adapter import SpecKitAdapter

        calls: dict[str, int] = {"load_feature": 0, "id_for_path": 0}

        class _SpyAdapter(SpecKitAdapter):
            def load_feature(self, handle, repo_root=None):
                calls["load_feature"] += 1
                return super().load_feature(handle, repo_root=repo_root)

            def id_for_path(self, path, repo_root=None):
                calls["id_for_path"] += 1
                return super().id_for_path(path, repo_root=repo_root)

        return _SpyAdapter(), calls


class TestFlowStateRoutesThroughRegistry:
    """T025: flow_state.collect_feature_evidence routes through registry."""

    def test_registered_spy_adapter_is_invoked(
        self, tmp_path: Path, monkeypatch
    ):
        from speckit_orca import flow_state as fs_mod
        from speckit_orca.sdd_adapter import registry

        feature_dir = tmp_path / "specs" / "060-spy"
        _write(feature_dir / "spec.md", "# Spec\n")
        (tmp_path / ".specify").mkdir(exist_ok=True)

        spy, calls = _SpySpecKitAdapterFactory.build()

        # Swap the adapter tuple so resolve_for_path hits the spy for spec-kit
        # paths. We use the registry's public reset_to_defaults + register
        # surface to keep the test honest.
        original_adapters = registry.adapters()
        monkeypatch.setattr(registry, "_adapters", (spy,), raising=False)
        try:
            fs_mod.collect_feature_evidence(
                feature_dir, repo_root=tmp_path
            )
        finally:
            monkeypatch.setattr(
                registry, "_adapters", original_adapters, raising=False
            )

        assert calls["load_feature"] >= 1

    def test_monkeypatched_spec_kit_adapter_still_works(
        self, tmp_path: Path, monkeypatch
    ):
        """FR-021 / FR-034: the legacy _SPEC_KIT_ADAPTER monkeypatch path
        continues to work. Setting the attribute must also update the
        registry so the resolver picks up the spy.
        """

        from speckit_orca import flow_state as fs_mod

        feature_dir = tmp_path / "specs" / "061-legacy"
        _write(feature_dir / "spec.md", "# Spec\n")
        (tmp_path / ".specify").mkdir(exist_ok=True)

        spy, calls = _SpySpecKitAdapterFactory.build()
        monkeypatch.setattr(fs_mod, "_SPEC_KIT_ADAPTER", spy, raising=False)

        fs_mod.collect_feature_evidence(feature_dir, repo_root=tmp_path)
        assert calls["load_feature"] >= 1


class TestSpecKitAdapterDeprecationWarning:
    """T027: accessing ``flow_state._SPEC_KIT_ADAPTER`` emits DeprecationWarning.

    Note on PEP 562 limitation (plan sub-phase B Risk #2): existing
    ``from speckit_orca.flow_state import _SPEC_KIT_ADAPTER`` module-scope
    imports bind the attribute BEFORE ``__getattr__`` fires, so they do not
    warn. The tests below cover the attribute-access forms that DO route
    through ``__getattr__``:

    - ``getattr(fs_mod, "_SPEC_KIT_ADAPTER")``
    - ``fs_mod._SPEC_KIT_ADAPTER``

    The unreachable module-scope-import case is documented in
    ``flow_state.py`` next to the ``__getattr__`` implementation.
    """

    def _reset_deprecation_cache(self, fs_mod):
        """Reset the once-per-process flag + warnings registry so the
        test is independent of cross-test pollution.

        Deliberately does NOT call ``importlib.reload`` — reloading
        ``flow_state`` orphans every other module that imported classes
        like ``SpecLiteFlowState`` from it, breaking `isinstance`
        checks in sibling tests. Instead, poke the module's state
        directly and clear the warnings registry.
        """
        # Drop the (possibly-persisted) attribute so __getattr__ fires.
        fs_mod.__dict__.pop("_SPEC_KIT_ADAPTER", None)
        # The module exposes ``_deprecation_warned`` via ``__dict__``.
        fs_mod.__dict__["_deprecation_warned"] = False
        if hasattr(fs_mod, "__warningregistry__"):
            fs_mod.__warningregistry__.clear()
        return fs_mod

    def test_attribute_access_emits_deprecation_warning(self):
        import speckit_orca.flow_state as fs_mod

        fs_mod = self._reset_deprecation_cache(fs_mod)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ = fs_mod._SPEC_KIT_ADAPTER

        deprecations = [
            w for w in caught if issubclass(w.category, DeprecationWarning)
        ]
        assert len(deprecations) == 1
        msg = str(deprecations[0].message)
        assert "_SPEC_KIT_ADAPTER" in msg
        assert "registry" in msg.lower()

    def test_getattr_form_emits_deprecation_warning(self):
        import speckit_orca.flow_state as fs_mod

        fs_mod = self._reset_deprecation_cache(fs_mod)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ = getattr(fs_mod, "_SPEC_KIT_ADAPTER")

        deprecations = [
            w for w in caught if issubclass(w.category, DeprecationWarning)
        ]
        assert len(deprecations) == 1

    def test_subsequent_access_does_not_warn_again(self):
        import speckit_orca.flow_state as fs_mod

        fs_mod = self._reset_deprecation_cache(fs_mod)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ = fs_mod._SPEC_KIT_ADAPTER
            _ = fs_mod._SPEC_KIT_ADAPTER
            _ = fs_mod._SPEC_KIT_ADAPTER

        deprecations = [
            w for w in caught if issubclass(w.category, DeprecationWarning)
        ]
        assert len(deprecations) == 1
