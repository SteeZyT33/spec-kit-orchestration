"""BareLayout — fallback for repos with no recognized spec system."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BareLayout:
    """No spec system detected; orca creates docs/orca-specs/ as fallback."""

    repo_root: Path

    def resolve_feature_dir(self, feature_id: str) -> Path:
        return self.repo_root / "docs" / "orca-specs" / feature_id

    def list_features(self) -> list[str]:
        root = self.repo_root / "docs" / "orca-specs"
        if not root.is_dir():
            return []
        return sorted(
            entry.name
            for entry in root.iterdir()
            if entry.is_dir() and not entry.name.startswith("_")
        )

    def constitution_path(self) -> Path | None:
        return None

    def agents_md_path(self) -> Path:
        return self.repo_root / "AGENTS.md"

    def review_artifact_dir(self) -> Path:
        return self.repo_root / "docs" / "orca-specs" / "_reviews"
