"""Protocol contract tests, parametrized over all host_layout implementations.

Each adapter must implement the same public surface; this file is the
canonical contract test. Adding a new adapter = parametrize it in.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.host_layout import BareLayout, HostLayout


@pytest.fixture
def bare_repo(tmp_path: Path) -> Path:
    """A minimal repo with no spec system at all."""
    (tmp_path / "README.md").write_text("# bare\n")
    return tmp_path


def test_bare_layout_satisfies_protocol(bare_repo: Path) -> None:
    layout: HostLayout = BareLayout(repo_root=bare_repo)
    assert isinstance(layout.repo_root, Path)


def test_bare_layout_resolve_feature_dir(bare_repo: Path) -> None:
    layout = BareLayout(repo_root=bare_repo)
    fd = layout.resolve_feature_dir("001-example")
    assert fd == bare_repo / "docs" / "orca-specs" / "001-example"


def test_bare_layout_list_features_empty(bare_repo: Path) -> None:
    layout = BareLayout(repo_root=bare_repo)
    assert layout.list_features() == []


def test_bare_layout_list_features_after_creation(bare_repo: Path) -> None:
    (bare_repo / "docs" / "orca-specs" / "001-x").mkdir(parents=True)
    (bare_repo / "docs" / "orca-specs" / "002-y").mkdir(parents=True)
    layout = BareLayout(repo_root=bare_repo)
    assert sorted(layout.list_features()) == ["001-x", "002-y"]


def test_bare_layout_constitution_path_is_none(bare_repo: Path) -> None:
    layout = BareLayout(repo_root=bare_repo)
    assert layout.constitution_path() is None


def test_bare_layout_agents_md_path_default(bare_repo: Path) -> None:
    layout = BareLayout(repo_root=bare_repo)
    assert layout.agents_md_path() == bare_repo / "AGENTS.md"


def test_bare_layout_review_artifact_dir(bare_repo: Path) -> None:
    layout = BareLayout(repo_root=bare_repo)
    assert layout.review_artifact_dir() == bare_repo / "docs" / "orca-specs" / "_reviews"


from orca.core.host_layout import SpecKitLayout


@pytest.fixture
def spec_kit_repo(tmp_path: Path) -> Path:
    (tmp_path / ".specify" / "memory").mkdir(parents=True)
    (tmp_path / ".specify" / "memory" / "constitution.md").write_text("# constitution\n")
    (tmp_path / "specs" / "001-example").mkdir(parents=True)
    (tmp_path / "specs" / "002-other").mkdir(parents=True)
    return tmp_path


def test_spec_kit_layout_resolve_feature_dir(spec_kit_repo: Path) -> None:
    layout = SpecKitLayout(repo_root=spec_kit_repo)
    assert layout.resolve_feature_dir("001-example") == spec_kit_repo / "specs" / "001-example"


def test_spec_kit_layout_list_features(spec_kit_repo: Path) -> None:
    layout = SpecKitLayout(repo_root=spec_kit_repo)
    assert sorted(layout.list_features()) == ["001-example", "002-other"]


def test_spec_kit_layout_constitution_present(spec_kit_repo: Path) -> None:
    layout = SpecKitLayout(repo_root=spec_kit_repo)
    assert layout.constitution_path() == spec_kit_repo / ".specify" / "memory" / "constitution.md"


def test_spec_kit_layout_constitution_missing_returns_none(tmp_path: Path) -> None:
    layout = SpecKitLayout(repo_root=tmp_path)
    assert layout.constitution_path() is None


def test_spec_kit_layout_review_artifact_dir(spec_kit_repo: Path) -> None:
    layout = SpecKitLayout(repo_root=spec_kit_repo)
    assert layout.review_artifact_dir() == spec_kit_repo / "specs"


from orca.core.host_layout import SuperpowersLayout


@pytest.fixture
def superpowers_repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "specs" / "2026-04-29-feature-x").mkdir()
    (tmp_path / "docs" / "superpowers" / "constitution.md").write_text("# c\n")
    (tmp_path / "AGENTS.md").write_text("# agents\n")
    return tmp_path


def test_superpowers_layout_resolve_feature_dir(superpowers_repo: Path) -> None:
    layout = SuperpowersLayout(repo_root=superpowers_repo)
    fd = layout.resolve_feature_dir("2026-04-29-feature-x")
    assert fd == superpowers_repo / "docs" / "superpowers" / "specs" / "2026-04-29-feature-x"


def test_superpowers_layout_list_features(superpowers_repo: Path) -> None:
    layout = SuperpowersLayout(repo_root=superpowers_repo)
    assert layout.list_features() == ["2026-04-29-feature-x"]


def test_superpowers_layout_constitution(superpowers_repo: Path) -> None:
    layout = SuperpowersLayout(repo_root=superpowers_repo)
    assert layout.constitution_path() == superpowers_repo / "docs" / "superpowers" / "constitution.md"


def test_superpowers_layout_review_artifact_dir(superpowers_repo: Path) -> None:
    layout = SuperpowersLayout(repo_root=superpowers_repo)
    assert layout.review_artifact_dir() == superpowers_repo / "docs" / "superpowers" / "reviews"


from orca.core.host_layout import OpenSpecLayout


@pytest.fixture
def openspec_repo(tmp_path: Path) -> Path:
    (tmp_path / "openspec" / "changes" / "add-feature-x").mkdir(parents=True)
    (tmp_path / "openspec" / "specs").mkdir()
    return tmp_path


def test_openspec_layout_resolve_feature_dir(openspec_repo: Path) -> None:
    layout = OpenSpecLayout(repo_root=openspec_repo)
    fd = layout.resolve_feature_dir("add-feature-x")
    assert fd == openspec_repo / "openspec" / "changes" / "add-feature-x"


def test_openspec_layout_list_features(openspec_repo: Path) -> None:
    layout = OpenSpecLayout(repo_root=openspec_repo)
    assert layout.list_features() == ["add-feature-x"]


def test_openspec_layout_no_constitution(openspec_repo: Path) -> None:
    layout = OpenSpecLayout(repo_root=openspec_repo)
    # openspec doesn't have a constitution.md convention
    assert layout.constitution_path() is None


def test_openspec_layout_review_artifact_dir(openspec_repo: Path) -> None:
    layout = OpenSpecLayout(repo_root=openspec_repo)
    assert layout.review_artifact_dir() == openspec_repo / "openspec" / "changes"
