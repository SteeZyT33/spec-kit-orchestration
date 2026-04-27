"""Pure-function data collectors for the Orca TUI panes.

Each collector is a pure function of `repo_root` and the filesystem state
under that root. No module-level caching of mutable state; no Textual or
Rich imports. This separation is required so collectors are unit-testable
without a terminal (spec FR-014).

The collectors call through to:

- `orca.flow_state.compute_flow_state`

None of the collectors parse `spec.md` / `plan.md` / `tasks.md` directly;
that is delegated to `flow_state` per spec FR-015.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from orca import flow_state as _flow_state

logger = logging.getLogger(__name__)


EVENT_FEED_MAX_ENTRIES = 30

# Review statuses that count as "still open" for the review queue pane.
# Anything NOT in the set below is considered pending / attention-needed.
COMPLETE_REVIEW_STATUSES = frozenset({
    "complete",
    "overall_complete",
    "present",
})


@dataclass(frozen=True)
class ReviewRow:
    feature_id: str
    review_type: str
    status: str


@dataclass(frozen=True)
class EventFeedEntry:
    timestamp: str
    source: str
    summary: str


@dataclass
class CollectorResult:
    reviews: list[ReviewRow] = field(default_factory=list)
    event_feed: list[EventFeedEntry] = field(default_factory=list)
    collected_at: str = ""
    polling_mode: bool = False


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_reviews(repo_root: Path) -> list[ReviewRow]:
    """Scan `specs/` and surface pending review milestones for each feature."""
    specs_dir = repo_root / "specs"
    if not specs_dir.exists():
        return []

    rows: list[ReviewRow] = []
    for feat_dir in sorted(specs_dir.iterdir()):
        if not feat_dir.is_dir():
            continue
        try:
            result = _flow_state.compute_flow_state(feat_dir, repo_root=repo_root)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "flow_state failed for %s: %s",
                feat_dir,
                exc,
                exc_info=True,
            )
            rows.append(ReviewRow(
                feature_id=feat_dir.name,
                review_type="error",
                status=f"flow_state failed: {type(exc).__name__}: {exc}",
            ))
            continue
        for rm in result.review_milestones:
            if rm.status in COMPLETE_REVIEW_STATUSES:
                continue
            rows.append(ReviewRow(
                feature_id=feat_dir.name,
                review_type=rm.review_type,
                status=rm.status,
            ))
    return rows


def collect_event_feed(repo_root: Path) -> list[EventFeedEntry]:
    """Return the event feed.

    No event sources remain after the v1 strip; the feed returns `[]`
    until later phases re-source it from review artifacts or other
    in-repo signals. The pane stays functional and renders an empty feed.
    """
    return []


def collect_all(repo_root: Path, polling_mode: bool = False) -> CollectorResult:
    """Run every collector in sequence and bundle the result."""
    return CollectorResult(
        reviews=collect_reviews(repo_root),
        event_feed=collect_event_feed(repo_root),
        collected_at=_now_utc_iso(),
        polling_mode=polling_mode,
    )
