"""HostLayout adapters: spec-system-agnostic path resolution."""
from __future__ import annotations

from pathlib import Path

from orca.core.adoption.manifest import load_manifest
from orca.core.host_layout.bare import BareLayout
from orca.core.host_layout.detect import detect
from orca.core.host_layout.openspec import OpenSpecLayout
from orca.core.host_layout.protocol import HostLayout
from orca.core.host_layout.spec_kit import SpecKitLayout
from orca.core.host_layout.superpowers import SuperpowersLayout

_ADAPTERS = {
    "spec-kit": SpecKitLayout,
    "openspec": OpenSpecLayout,
    "superpowers": SuperpowersLayout,
    "bare": BareLayout,
}


def from_manifest(repo_root: Path) -> HostLayout:
    """Load the manifest at <repo_root>/.orca/adoption.toml; return adapter.

    Raises ManifestError or FileNotFoundError if manifest absent/invalid.
    """
    manifest_path = repo_root / ".orca" / "adoption.toml"
    manifest = load_manifest(manifest_path)
    cls = _ADAPTERS[manifest.host.system]
    return cls(repo_root=repo_root)


__all__ = [
    "HostLayout", "BareLayout", "SpecKitLayout", "SuperpowersLayout",
    "OpenSpecLayout", "detect", "from_manifest",
]
