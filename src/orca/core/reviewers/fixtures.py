from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orca.core.bundle import ReviewBundle
from orca.core.reviewers.base import RawFindings, ReviewerError


class FixtureReviewer:
    """Replays a recorded JSON scenario as if it were a live reviewer.

    Used in tests to exercise downstream code (cross combiner, capabilities)
    without making LLM calls. The fixture file shape is:

        {"reviewer": "<name>", "raw_findings": [<finding_dict>, ...]}
    """

    def __init__(self, *, scenario: Path, name: str | None = None):
        self.scenario = Path(scenario)
        self._explicit_name = name
        self._cached: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        if self._explicit_name is not None:
            return self._explicit_name
        try:
            return self._load().get("reviewer", "fixture")
        except ReviewerError:
            return "fixture"  # safe fallback; review() will still raise

    def _load(self) -> dict[str, Any]:
        if self._cached is not None:
            return self._cached
        if not self.scenario.exists():
            raise ReviewerError(f"fixture not found: {self.scenario}")
        try:
            self._cached = json.loads(self.scenario.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ReviewerError(
                f"malformed fixture {self.scenario}: {exc}"
            ) from exc
        return self._cached

    def review(self, bundle: ReviewBundle, prompt: str) -> RawFindings:
        del prompt  # unused; protocol conformance
        data = self._load()
        return RawFindings(
            reviewer=data.get("reviewer", "fixture"),
            findings=list(data.get("raw_findings", [])),
            metadata={"fixture": str(self.scenario), "bundle_hash": bundle.bundle_hash},
        )
