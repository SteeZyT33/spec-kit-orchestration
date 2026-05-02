"""Format ISO-8601 timestamps as short relative ages: 5s, 3m, 2h, 14d."""
from __future__ import annotations

from datetime import datetime, timezone


def format_age(iso_ts: str | None, *, now: datetime | None = None) -> str:
    """Return short relative age. '-' for None or invalid input."""
    if not iso_ts:
        return "-"
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return "-"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    cur = now or datetime.now(timezone.utc)
    sec = max(0, int((cur - ts).total_seconds()))
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m"
    if sec < 86400:
        return f"{sec // 3600}h"
    return f"{sec // 86400}d"
