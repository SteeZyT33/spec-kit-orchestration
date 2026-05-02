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
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from orca import flow_state as _flow_state

logger = logging.getLogger(__name__)


EVENT_FEED_MAX_ENTRIES = 30

# Review-artifact filenames the event feed surfaces. These are the
# durable signals review work has happened against a feature; other
# .md files under specs/<feature>/ are not events.
REVIEW_ARTIFACT_NAMES = frozenset({
    "review-spec.md",
    "review-code.md",
    "review-pr.md",
})

# Cap on git commits queried per refresh. The merged feed is then
# trimmed to EVENT_FEED_MAX_ENTRIES, but pulling more than that here
# is wasteful when review entries also compete for slots.
GIT_LOG_FETCH_LIMIT = EVENT_FEED_MAX_ENTRIES

# Subprocess timeout for the git probe. The TUI must never block on
# a slow VCS call; the feed simply omits git entries on timeout.
GIT_LOG_TIMEOUT_SECONDS = 2.0

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


def _resolve_layout(repo_root: Path):
    """Return a HostLayout for `repo_root`. Manifest-driven when adopted,
    detection-driven otherwise; bare fallback if both fail.
    """
    from orca.core.host_layout import from_manifest, detect
    from orca.core.host_layout.bare import BareLayout
    try:
        return from_manifest(repo_root)
    except Exception:  # noqa: BLE001
        try:
            return detect(repo_root)
        except Exception:  # noqa: BLE001
            return BareLayout(repo_root=repo_root)


def collect_reviews(repo_root: Path) -> list[ReviewRow]:
    """Surface pending review milestones for every feature.

    Host-agnostic: uses `orca.core.host_layout` to find features so
    spec-kit, superpowers, openspec, and bare repos all work.
    """
    layout = _resolve_layout(repo_root)
    rows: list[ReviewRow] = []
    for feature_id in layout.list_features():
        feat_dir = layout.resolve_feature_dir(feature_id)
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
                feature_id=feature_id,
                review_type="error",
                status=f"flow_state failed: {type(exc).__name__}: {exc}",
            ))
            continue
        for rm in result.review_milestones:
            if rm.status in COMPLETE_REVIEW_STATUSES:
                continue
            rows.append(ReviewRow(
                feature_id=feature_id,
                review_type=rm.review_type,
                status=rm.status,
            ))
    return rows


def _ts_from_epoch(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _collect_review_events(repo_root: Path) -> list[EventFeedEntry]:
    """Surface review-artifact writes as event-feed rows.

    Host-agnostic: walks features via `orca.core.host_layout`. Any
    file under a feature dir whose name is in REVIEW_ARTIFACT_NAMES
    contributes one entry. Summary is `<feature_id>/<artifact_name>`.
    """
    layout = _resolve_layout(repo_root)
    rows: list[EventFeedEntry] = []
    for feature_id in layout.list_features():
        feat_dir = layout.resolve_feature_dir(feature_id)
        if not feat_dir.is_dir():
            continue
        for name in REVIEW_ARTIFACT_NAMES:
            artifact = feat_dir / name
            try:
                mtime = artifact.stat().st_mtime
            except FileNotFoundError:
                continue
            except OSError:
                logger.debug("review artifact stat failed: %s", artifact, exc_info=True)
                continue
            rows.append(EventFeedEntry(
                timestamp=_ts_from_epoch(mtime),
                source="review",
                summary=f"{feature_id}/{name}",
            ))
    return rows


def _collect_git_events(repo_root: Path) -> list[EventFeedEntry]:
    """Surface recent git commits as event-feed rows.

    Returns [] for repos without a working git history (uninitialized
    .git/, empty repo, or git unavailable). Never raises.
    """
    if not (repo_root / ".git").exists():
        return []
    try:
        completed = subprocess.run(
            [
                "git", "-C", str(repo_root), "log",
                f"-n{GIT_LOG_FETCH_LIMIT}",
                "--pretty=format:%ct%x09%h%x09%s",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=GIT_LOG_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError, OSError):
        logger.debug("git log probe failed in %s", repo_root, exc_info=True)
        return []

    rows: list[EventFeedEntry] = []
    for line in completed.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        epoch_str, short_hash, subject = parts
        try:
            epoch = float(epoch_str)
        except ValueError:
            continue
        rows.append(EventFeedEntry(
            timestamp=_ts_from_epoch(epoch),
            source="git",
            summary=f"{short_hash} {subject}",
        ))
    return rows


def collect_event_feed(repo_root: Path) -> list[EventFeedEntry]:
    """Merge per-source event rows, sort newest-first, cap at the max.

    Sources are isolated: a failure in one source omits its rows
    rather than losing the whole feed. Empty repos (no specs/, no
    commits) return [].
    """
    rows: list[EventFeedEntry] = []
    for source_fn in (_collect_review_events, _collect_git_events):
        try:
            rows.extend(source_fn(repo_root))
        except Exception:  # noqa: BLE001
            logger.debug("event-feed source %s failed", source_fn.__name__,
                         exc_info=True)
    rows.sort(key=lambda e: e.timestamp, reverse=True)
    return rows[:EVENT_FEED_MAX_ENTRIES]


def collect_all(repo_root: Path, polling_mode: bool = False) -> CollectorResult:
    """Run every collector in sequence and bundle the result."""
    return CollectorResult(
        reviews=collect_reviews(repo_root),
        event_feed=collect_event_feed(repo_root),
        collected_at=_now_utc_iso(),
        polling_mode=polling_mode,
    )
