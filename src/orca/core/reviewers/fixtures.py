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

    @property
    def name(self) -> str:
        if self._explicit_name is not None:
            return self._explicit_name
        return self._load().get("reviewer", "fixture")

    def _load(self) -> dict[str, Any]:
        if not self.scenario.exists():
            raise ReviewerError(f"fixture not found: {self.scenario}")
        return json.loads(self.scenario.read_text(encoding="utf-8"))

    def review(self, bundle: ReviewBundle, prompt: str) -> RawFindings:
        data = self._load()
        return RawFindings(
            reviewer=data.get("reviewer", "fixture"),
            findings=list(data.get("raw_findings", [])),
            metadata={"fixture": str(self.scenario), "bundle_hash": bundle.bundle_hash},
        )
