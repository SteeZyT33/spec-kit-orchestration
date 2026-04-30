"""SpecKitLayout — the original spec-kit convention."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SpecKitLayout:
    """Repos using spec-kit's `.specify/` + `specs/<id>/` convention."""

    repo_root: Path

    def resolve_feature_dir(self, feature_id: str) -> Path:
        return self.repo_root / "specs" / feature_id

    def list_features(self) -> list[str]:
        root = self.repo_root / "specs"
        if not root.is_dir():
            return []
        return sorted(
            entry.name
            for entry in root.iterdir()
            if entry.is_dir() and not entry.name.startswith("_")
        )

    def constitution_path(self) -> Path | None:
        path = self.repo_root / ".specify" / "memory" / "constitution.md"
        return path if path.exists() else None

    def agents_md_path(self) -> Path:
        # spec-kit hosts conventionally use CLAUDE.md
        return self.repo_root / "CLAUDE.md"

    def review_artifact_dir(self) -> Path:
        return self.repo_root / "specs"
