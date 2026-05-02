"""Health tags: comma-joined short flags. Empty string when the lane is fine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from orca.tui.timefmt import format_age


STALE_AFTER = timedelta(hours=24)


@dataclass(frozen=True)
class HealthInputs:
    last_attached_at: str | None
    last_setup_failed: bool
    branch_merged: bool
    tmux_alive: bool
    sidecar_active: bool
    doctor_warnings: list[str] = field(default_factory=list)


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


def derive_health(inp: HealthInputs, *, now: datetime | None = None) -> str:
    cur = now or datetime.now(timezone.utc)
    tags: list[str] = []

    if inp.last_setup_failed:
        tags.append("setup-failed")

    if inp.branch_merged and inp.sidecar_active:
        tags.append("merged·cleanup")

    last = _parse_iso(inp.last_attached_at)
    if last is not None and (cur - last) > STALE_AFTER:
        tags.append(f"stale {format_age(inp.last_attached_at, now=cur)}")

    if (inp.sidecar_active and not inp.tmux_alive
            and not any(t.startswith("stale ") for t in tags)
            and not inp.branch_merged):
        tags.append("tmux-orphan")

    for w in inp.doctor_warnings:
        tags.append(f"doctor: {w}")

    return ", ".join(tags)
