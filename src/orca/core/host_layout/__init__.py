"""HostLayout adapters: spec-system-agnostic path resolution."""
from __future__ import annotations

from orca.core.host_layout.bare import BareLayout
from orca.core.host_layout.openspec import OpenSpecLayout
from orca.core.host_layout.protocol import HostLayout
from orca.core.host_layout.spec_kit import SpecKitLayout
from orca.core.host_layout.superpowers import SuperpowersLayout

__all__ = [
    "HostLayout",
    "BareLayout",
    "SpecKitLayout",
    "SuperpowersLayout",
    "OpenSpecLayout",
]
