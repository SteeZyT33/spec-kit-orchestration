"""SuperpowersLayout — superpowers/ convention with date-prefixed specs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SuperpowersLayout:
    """Repos using the superpowers convention: `docs/superpowers/specs/`."""

    repo_root: Path

    def resolve_feature_dir(self, feature_id: str) -> Path:
        return self.repo_root / "docs" / "superpowers" / "specs" / feature_id

    def list_features(self) -> list[str]:
        root = self.repo_root / "docs" / "superpowers" / "specs"
        if not root.is_dir():
            return []
        return [
            entry.name
            for entry in root.iterdir()
            if entry.is_dir() and not entry.name.startswith("_")
        ]

    def constitution_path(self) -> Path | None:
        path = self.repo_root / "docs" / "superpowers" / "constitution.md"
        return path if path.exists() else None

    def agents_md_path(self) -> Path:
        return self.repo_root / "AGENTS.md"

    def review_artifact_dir(self) -> Path:
        return self.repo_root / "docs" / "superpowers" / "reviews"
