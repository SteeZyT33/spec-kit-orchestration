"""HostLayout protocol — the single abstraction over spec systems."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class HostLayout(Protocol):
    """Adapter interface; implementations live in sibling modules."""

    repo_root: Path

    def resolve_feature_dir(self, feature_id: str) -> Path:
        """Return absolute path to the feature dir for `feature_id`.

        Path is computed; existence is not checked. Caller decides
        whether to create / require existence.
        """
        ...

    def list_features(self) -> list[str]:
        """Return feature_ids found under this host's feature root.

        Empty list if no feature root exists yet. IDs are returned
        as the directory basename, not absolute paths.
        """
        ...

    def constitution_path(self) -> Path | None:
        """Return absolute path to the host's constitution.md.

        Returns None if this host has no constitution convention
        (e.g., bare repo).
        """
        ...

    def agents_md_path(self) -> Path:
        """Return absolute path to the host's AGENTS.md (or CLAUDE.md).

        Always returns a path; caller checks `.exists()` if needed.
        """
        ...

    def review_artifact_dir(self) -> Path:
        """Return absolute path to where review-spec.md and friends land."""
        ...
