"""Auto-discovery of canonical SDD artifacts under a feature directory.

Replaces the `cite.md` bash loop that hardcoded the same logic.
Returns absolute paths in canonical order: plan.md, data-model.md,
research.md, quickstart.md, tasks.md, then contracts/**/*.md (sorted).
"""
from __future__ import annotations

from pathlib import Path

CANONICAL_ARTIFACTS: tuple[str, ...] = (
    "plan.md",
    "data-model.md",
    "research.md",
    "quickstart.md",
    "tasks.md",
)


def discover(feature_dir: Path) -> list[Path]:
    """Return absolute paths of existing SDD artifacts under feature_dir.

    Order: canonical artifacts first (in CANONICAL_ARTIFACTS order, only
    those that exist), then contracts/**/*.md sorted alphabetically by
    relative path. Empty list if feature_dir doesn't exist.
    """
    if not feature_dir.is_dir():
        return []

    feature_dir = feature_dir.resolve()
    paths: list[Path] = []

    for name in CANONICAL_ARTIFACTS:
        candidate = feature_dir / name
        if candidate.is_file():
            paths.append(candidate)

    contracts_dir = feature_dir / "contracts"
    if contracts_dir.is_dir():
        contained: list[Path] = []
        for p in contracts_dir.rglob("*.md"):
            if not p.is_file():
                continue
            rp = p.resolve()
            try:
                rp.relative_to(feature_dir)
            except ValueError:
                # Symlink resolved outside the feature_dir. Drop it; we
                # don't want references pointing at unrelated trees.
                continue
            contained.append(rp)
        paths.extend(sorted(contained))

    return paths
