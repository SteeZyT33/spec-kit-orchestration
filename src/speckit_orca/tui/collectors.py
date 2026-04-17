"""Pure-function data collectors for the Orca TUI panes.

Each collector is a pure function of `repo_root` and the filesystem state
under that root. No module-level caching of mutable state; no Textual or
Rich imports. This separation is required so collectors are unit-testable
without a terminal (spec FR-014).

The collectors call through to:

- `speckit_orca.matriarch.list_lanes`
- `speckit_orca.yolo.list_runs` + `yolo.run_status` (+ reducer helpers)
- `speckit_orca.flow_state.compute_flow_state`

None of the collectors parse `spec.md` / `plan.md` / `tasks.md` directly;
that is delegated to `flow_state` per spec FR-015.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# These imports are kept at function scope in some places to tolerate
# half-configured repos (missing matriarch, etc.). Top-level import is
# fine because every module is importable independently.
from speckit_orca import flow_state as _flow_state
from speckit_orca import matriarch as _matriarch
from speckit_orca import yolo as _yolo

logger = logging.getLogger(__name__)


TERMINAL_OUTCOMES = frozenset({"completed", "canceled", "failed"})
EVENT_FEED_MAX_ENTRIES = 30

# Review statuses that count as "still open" for the review queue pane.
# Anything NOT in the set below is considered pending / attention-needed.
COMPLETE_REVIEW_STATUSES = frozenset({
    "complete",
    "overall_complete",
    "present",
})


@dataclass(frozen=True)
class LaneRow:
    lane_id: str
    effective_state: str
    owner_id: str | None
    status_reason: str


@dataclass(frozen=True)
class YoloRow:
    run_id: str
    feature_id: str
    current_stage: str
    outcome: str
    matriarch_sync_failed: bool


@dataclass(frozen=True)
class ReviewRow:
    feature_id: str
    review_type: str
    status: str


@dataclass(frozen=True)
class EventFeedEntry:
    timestamp: str
    source: str  # "yolo" | "matr"
    summary: str


@dataclass
class CollectorResult:
    lanes: list[LaneRow] = field(default_factory=list)
    yolo_runs: list[YoloRow] = field(default_factory=list)
    reviews: list[ReviewRow] = field(default_factory=list)
    event_feed: list[EventFeedEntry] = field(default_factory=list)
    collected_at: str = ""
    polling_mode: bool = False


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _matriarch_root(repo_root: Path) -> Path:
    return repo_root / ".specify" / "orca" / "matriarch"


def collect_lanes(repo_root: Path) -> list[LaneRow]:
    """Read matriarch's lane registry and return LaneRow summaries.

    Graceful degradation: if the matriarch directory is absent, returns
    `[]` with no side effects. If a specific lane record is malformed,
    `matriarch.list_lanes` returns an error dict for that lane and we
    surface it with a placeholder row.
    """
    if not _matriarch_root(repo_root).exists():
        return []
    try:
        lanes = _matriarch.list_lanes(repo_root=repo_root)
    except Exception:  # noqa: BLE001 - degrade rather than crash the pane
        logger.debug("Failed to list matriarch lanes", exc_info=True)
        return []

    rows: list[LaneRow] = []
    for lane in lanes:
        if "error" in lane:
            rows.append(LaneRow(
                lane_id=lane.get("lane_id", "<unknown>"),
                effective_state="error",
                owner_id=None,
                status_reason=lane.get("error", ""),
            ))
            continue
        rows.append(LaneRow(
            lane_id=lane.get("lane_id", "<unknown>"),
            effective_state=lane.get("effective_state", "unknown"),
            owner_id=lane.get("owner_id"),
            status_reason=lane.get("status_reason", ""),
        ))
    return rows


def collect_yolo_runs(repo_root: Path) -> list[YoloRow]:
    """List non-terminal yolo runs in the repo.

    Filters out runs whose outcome is in {completed, canceled, failed}
    per spec FR-005.
    """
    runs_dir = repo_root / ".specify" / "orca" / "yolo" / "runs"
    if not runs_dir.exists():
        return []
    try:
        run_ids = _yolo.list_runs(repo_root)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to list yolo runs", exc_info=True)
        return []

    rows: list[YoloRow] = []
    for rid in run_ids:
        try:
            state = _yolo.run_status(repo_root, rid)
        except Exception:  # noqa: BLE001 - one bad run shouldn't kill the pane
            logger.debug(
                "Skipping yolo run due to status read failure: %s", rid, exc_info=True
            )
            continue
        if state.outcome in TERMINAL_OUTCOMES:
            continue
        rows.append(YoloRow(
            run_id=state.run_id,
            feature_id=state.feature_id,
            current_stage=state.current_stage,
            outcome=state.outcome,
            matriarch_sync_failed=bool(state.matriarch_sync_failed),
        ))
    return rows


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
        except Exception:  # noqa: BLE001
            logger.debug(
                "Skipping feature due to flow_state failure: %s",
                feat_dir,
                exc_info=True,
            )
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


def _tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    """Read the last `limit` valid JSON lines from `path`.

    Missing files return `[]`. Malformed lines are skipped quietly.
    """
    import json
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        # Unreadable (permissions, disappeared mid-read) or non-utf8 bytes:
        # degrade to empty for this file rather than aborting the feed.
        logger.debug("Skipping unreadable event-feed file: %s", path, exc_info=True)
        return []
    # Walk from the end, collecting valid JSON lines up to limit.
    collected: list[dict[str, Any]] = []
    for line in reversed(raw):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            collected.append(obj)
            if len(collected) >= limit:
                break
    return list(reversed(collected))


def _safe_iterdir(path: Path) -> list[Path]:
    """Return sorted children of `path`, or `[]` if the tree is unreadable.

    `iterdir()` can raise `OSError` (e.g. permission denied, directory removed
    mid-walk). The event feed is best-effort, so degrade silently rather than
    propagating the failure and aborting the refresh.
    """
    try:
        return sorted(path.iterdir())
    except OSError:
        logger.debug("Skipping unreadable directory: %s", path, exc_info=True)
        return []


def _collect_yolo_event_entries(repo_root: Path, per_run_limit: int = 30) -> list[EventFeedEntry]:
    runs_dir = repo_root / ".specify" / "orca" / "yolo" / "runs"
    if not runs_dir.exists():
        return []
    entries: list[EventFeedEntry] = []
    for run_dir in _safe_iterdir(runs_dir):
        if not run_dir.is_dir():
            continue
        events_path = run_dir / "events.jsonl"
        try:
            objs = _tail_jsonl(events_path, per_run_limit)
        except Exception:  # noqa: BLE001 - one bad file shouldn't kill the feed
            logger.debug("Skipping unreadable yolo event file: %s", events_path, exc_info=True)
            continue
        for obj in objs:
            ts = obj.get("timestamp", "")
            etype = obj.get("event_type", "?")
            to_stage = obj.get("to_stage")
            feat = obj.get("feature_id", "?")
            summary = f"{run_dir.name[:8]} {feat} {etype}"
            if to_stage:
                summary += f" -> {to_stage}"
            entries.append(EventFeedEntry(timestamp=ts, source="yolo", summary=summary))
    return entries


def _collect_matriarch_event_entries(repo_root: Path, per_lane_limit: int = 30) -> list[EventFeedEntry]:
    mroot = _matriarch_root(repo_root)
    if not mroot.exists():
        return []
    mailbox_root = mroot / "mailbox"
    if not mailbox_root.exists():
        return []
    entries: list[EventFeedEntry] = []
    for lane_dir in _safe_iterdir(mailbox_root):
        if not lane_dir.is_dir():
            continue
        inbound = lane_dir / "inbound.jsonl"
        try:
            objs = _tail_jsonl(inbound, per_lane_limit)
        except Exception:  # noqa: BLE001 - one bad mailbox shouldn't kill the feed
            logger.debug("Skipping unreadable matriarch mailbox: %s", inbound, exc_info=True)
            continue
        for obj in objs:
            ts = obj.get("timestamp", "")
            etype = obj.get("type", "?")
            sender = obj.get("sender", "?")
            summary = f"{lane_dir.name} {etype} from {sender}"
            entries.append(EventFeedEntry(timestamp=ts, source="matr", summary=summary))
    return entries


def collect_event_feed(repo_root: Path) -> list[EventFeedEntry]:
    """Merge yolo + matriarch mailbox entries, sort desc by timestamp, cap at 30.

    Every per-file / per-directory failure degrades to empty for that source
    rather than aborting the refresh, so one corrupt JSONL or permission
    error never zeros out the whole feed.
    """
    entries: list[EventFeedEntry] = []
    try:
        entries.extend(_collect_yolo_event_entries(repo_root))
    except Exception:  # noqa: BLE001
        logger.debug("yolo event-feed collection failed", exc_info=True)
    try:
        entries.extend(_collect_matriarch_event_entries(repo_root))
    except Exception:  # noqa: BLE001
        logger.debug("matriarch event-feed collection failed", exc_info=True)
    entries.sort(key=lambda e: e.timestamp, reverse=True)
    return entries[:EVENT_FEED_MAX_ENTRIES]


def collect_all(repo_root: Path, polling_mode: bool = False) -> CollectorResult:
    """Run every collector in sequence and bundle the result."""
    return CollectorResult(
        lanes=collect_lanes(repo_root),
        yolo_runs=collect_yolo_runs(repo_root),
        reviews=collect_reviews(repo_root),
        event_feed=collect_event_feed(repo_root),
        collected_at=_now_utc_iso(),
        polling_mode=polling_mode,
    )
