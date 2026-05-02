"""Detect which spec system a repo uses; pick the matching adapter."""
from __future__ import annotations

from pathlib import Path

from orca.core.host_layout.bare import BareLayout
from orca.core.host_layout.openspec import OpenSpecLayout
from orca.core.host_layout.protocol import HostLayout
from orca.core.host_layout.spec_kit import SpecKitLayout
from orca.core.host_layout.superpowers import SuperpowersLayout


def detect(repo_root: Path) -> HostLayout:
    """Probe `repo_root` and return the best-fit HostLayout.

    Priority order: superpowers > openspec > spec-kit > bare.
    spec-kit recognized by either `.specify/` (canonical marker) OR a
    `specs/` directory containing feature subdirectories (looser but
    matches fresh / partial spec-kit setups and test fixtures).
    """
    if (repo_root / "docs" / "superpowers" / "specs").is_dir():
        return SuperpowersLayout(repo_root=repo_root)
    if (repo_root / "openspec" / "changes").is_dir():
        return OpenSpecLayout(repo_root=repo_root)
    if (repo_root / ".specify").is_dir():
        return SpecKitLayout(repo_root=repo_root)
    specs = repo_root / "specs"
    if specs.is_dir() and any(p.is_dir() for p in specs.iterdir()):
        return SpecKitLayout(repo_root=repo_root)
    return BareLayout(repo_root=repo_root)
