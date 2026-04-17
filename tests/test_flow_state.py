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
