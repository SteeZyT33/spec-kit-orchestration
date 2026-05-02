"""Compact relative-age formatter for the TUI event feed.

ISO-8601 timestamps are too wide for split panes on 80-col terminals.
`format_age` returns ≤8-character relative-age strings:

  now / 30s / 5m / 3h / 2d / Apr 30

Anything older than ~7 days falls back to a `MMM D` calendar date.
Unparseable input yields a short fallback string rather than raising.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def _parse_iso(ts: str) -> Optional[datetime]:
    # Accept the canonical "YYYY-MM-DDTHH:MM:SSZ" form the collectors emit,
    # plus a few common variants. Returns None on any failure.
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def format_age(ts: str, *, now: Optional[datetime] = None) -> str:
    """Return a compact (≤8-char) relative-age string for `ts`.

    `now` is injectable for deterministic tests.
    """
    parsed = _parse_iso(ts)
    if parsed is None:
        # Fallback: trim original to 8 chars rather than raise.
        return ts[:8]
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    delta = now - parsed
    seconds = int(delta.total_seconds())

    if seconds < 0:
        seconds = 0
    if seconds < 5:
        return "now"
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    if days < 7:
        return f"{days}d"
    # ≥7 days: short calendar date, e.g. "Apr 30".
    return parsed.strftime("%b %d").lstrip("0")
