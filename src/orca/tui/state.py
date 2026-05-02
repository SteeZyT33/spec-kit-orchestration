"""Derive state ('live'|'stale'|'merged'|'failed'|'idle') from sidecar + events."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


STALE_AFTER = timedelta(hours=24)


@dataclass(frozen=True)
class StateInputs:
    last_attached_at: str | None    # ISO-8601 from Sidecar.last_attached_at
    last_event: str | None          # most recent event type for this lane
    tmux_alive: bool
    branch_merged: bool             # branch reachable from base via --merged
    last_setup_failed: bool         # last setup.* event was .failed


def _parse_iso(iso_ts: str | None) -> datetime | None:
    if not iso_ts:
        return None
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def derive_state(inp: StateInputs, *, now: datetime | None = None) -> str:
    """Priority: failed > merged > live > stale > idle.

    Failed wins because the operator should see a broken lane immediately.
    Merged wins over live because a merged-but-not-cleaned-up lane is a
    cleanup signal regardless of recent activity. Live wins over stale.
    """
    cur = now or datetime.now(timezone.utc)
    if inp.last_setup_failed:
        return "failed"
    if inp.branch_merged:
        return "merged"
    if inp.tmux_alive and inp.last_event == "agent.launched":
        return "live"
    last = _parse_iso(inp.last_attached_at)
    if last is None or (cur - last) > STALE_AFTER:
        return "stale"
    return "idle"
