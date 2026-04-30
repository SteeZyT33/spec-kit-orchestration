"""Detection priority + override tests."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from orca.core.host_layout import (
    BareLayout,
    OpenSpecLayout,
    SpecKitLayout,
    SuperpowersLayout,
    detect,
    from_manifest,
)


def test_detect_superpowers(tmp_path: Path) -> None:
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    layout = detect(tmp_path)
    assert isinstance(layout, SuperpowersLayout)


def test_detect_openspec(tmp_path: Path) -> None:
    (tmp_path / "openspec" / "changes").mkdir(parents=True)
    layout = detect(tmp_path)
    assert isinstance(layout, OpenSpecLayout)


def test_detect_spec_kit(tmp_path: Path) -> None:
    (tmp_path / ".specify").mkdir()
    layout = detect(tmp_path)
    assert isinstance(layout, SpecKitLayout)


def test_detect_bare(tmp_path: Path) -> None:
    layout = detect(tmp_path)
    assert isinstance(layout, BareLayout)


def test_detect_superpowers_wins_over_specify(tmp_path: Path) -> None:
    """When both .specify/ and docs/superpowers/specs/ exist (mid-migration),
    superpowers wins per priority order."""
    (tmp_path / ".specify").mkdir()
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    layout = detect(tmp_path)
    assert isinstance(layout, SuperpowersLayout)


def test_detect_openspec_wins_over_specify(tmp_path: Path) -> None:
    (tmp_path / ".specify").mkdir()
    (tmp_path / "openspec" / "changes").mkdir(parents=True)
    layout = detect(tmp_path)
    assert isinstance(layout, OpenSpecLayout)


def _write_manifest(tmp_path: Path, system: str, pattern: str) -> Path:
    manifest = tmp_path / ".orca" / "adoption.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(textwrap.dedent(f"""
        schema_version = 1
        [host]
        system = "{system}"
        feature_dir_pattern = "{pattern}"
        agents_md_path = "AGENTS.md"
        review_artifact_dir = "x"
        [orca]
        state_dir = ".orca"
        installed_capabilities = []
        [slash_commands]
        namespace = "orca"
        enabled = []
        disabled = []
        [claude_md]
        policy = "section"
        [constitution]
        policy = "respect-existing"
        [reversal]
        backup_dir = ".orca/adoption-backup"
    """))
    return manifest


def test_from_manifest_spec_kit(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "spec-kit", "specs/{feature_id}")
    layout = from_manifest(tmp_path)
    assert isinstance(layout, SpecKitLayout)
    assert layout.repo_root == tmp_path


def test_from_manifest_superpowers(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "superpowers", "docs/superpowers/specs/{feature_id}")
    layout = from_manifest(tmp_path)
    assert isinstance(layout, SuperpowersLayout)


def test_from_manifest_openspec(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "openspec", "openspec/changes/{feature_id}")
    layout = from_manifest(tmp_path)
    assert isinstance(layout, OpenSpecLayout)


def test_from_manifest_bare(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "bare", "docs/orca-specs/{feature_id}")
    layout = from_manifest(tmp_path)
    assert isinstance(layout, BareLayout)


def test_from_manifest_missing(tmp_path: Path) -> None:
    """No manifest at <repo>/.orca/adoption.toml -> raise."""
    from orca.core.adoption.manifest import ManifestError
    with pytest.raises((ManifestError, FileNotFoundError)):
        from_manifest(tmp_path)
