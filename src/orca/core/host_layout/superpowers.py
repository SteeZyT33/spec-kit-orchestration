"""SuperpowersLayout — superpowers/ convention with date-prefixed specs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_DESIGN_SUFFIX = "-design"


def _feature_id_from_path(entry: Path) -> str:
    """Extract a feature id from a superpowers spec path.

    Files like `2026-04-26-foo-design.md` -> `2026-04-26-foo`. The
    `-design` suffix is the convention for design docs; stripping it
    gives a stable id that matches the corresponding plan filename
    `docs/superpowers/plans/2026-04-26-foo.md`.
    """
    if entry.is_file() and entry.suffix == ".md":
        stem = entry.stem
        if stem.endswith(_DESIGN_SUFFIX):
            stem = stem[: -len(_DESIGN_SUFFIX)]
        return stem
    return entry.name


@dataclass(frozen=True)
class SuperpowersLayout:
    """Repos using the superpowers convention.

    Specs live at `docs/superpowers/specs/<id>-design.md` (single file
    per spec, the common form) or `docs/superpowers/specs/<id>/`
    (directory per spec). Both are supported.
    """

    repo_root: Path

    def resolve_feature_dir(self, feature_id: str) -> Path:
        as_dir = self.repo_root / "docs" / "superpowers" / "specs" / feature_id
        return as_dir  # may not exist for file-form specs; callers degrade gracefully

    def spec_path(self, feature_id: str) -> Path:
        """File-form spec path: `<root>/specs/<id>-design.md`."""
        return self.repo_root / "docs" / "superpowers" / "specs" / f"{feature_id}{_DESIGN_SUFFIX}.md"

    def plan_path(self, feature_id: str) -> Path:
        """File-form plan path: `<root>/plans/<id>.md`."""
        return self.repo_root / "docs" / "superpowers" / "plans" / f"{feature_id}.md"

    def list_features(self) -> list[str]:
        """Return feature ids found under `docs/superpowers/specs/`.

        For file-form specs, only `*-design.md` files count as feature
        specs; other `.md` files in the directory (review artifacts,
        notes) are excluded. Directory-form specs always count.
        """
        root = self.repo_root / "docs" / "superpowers" / "specs"
        if not root.is_dir():
            return []
        ids: set[str] = set()
        for entry in root.iterdir():
            if entry.name.startswith("_"):
                continue
            if entry.is_dir():
                ids.add(entry.name)
            elif (
                entry.is_file()
                and entry.suffix == ".md"
                and entry.stem.endswith(_DESIGN_SUFFIX)
            ):
                ids.add(_feature_id_from_path(entry))
        return sorted(ids)

    def constitution_path(self) -> Path | None:
        path = self.repo_root / "docs" / "superpowers" / "constitution.md"
        return path if path.exists() else None

    def agents_md_path(self) -> Path:
        return self.repo_root / "AGENTS.md"

    def review_artifact_dir(self) -> Path:
        return self.repo_root / "docs" / "superpowers" / "reviews"
