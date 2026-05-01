"""Append-only lifecycle event log at .orca/worktrees/events.jsonl.

Closed event vocabulary: new events require contract bump.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVENT_VOCAB = frozenset({
    "lane.created", "lane.attached", "lane.removed",
    "setup.after_create.started", "setup.after_create.completed",
    "setup.after_create.failed",
    "setup.before_run.started", "setup.before_run.completed",
    "setup.before_run.failed", "setup.before_run.skipped_untrusted",
    "setup.before_remove.started", "setup.before_remove.completed",
    "setup.before_remove.failed", "setup.before_remove.skipped_untrusted",
    "tmux.window.created", "tmux.window.killed",
    "tmux.session.created", "tmux.session.killed",
    "agent.launched", "agent.exited",
})

EVENTS_FILENAME = "events.jsonl"


def emit_event(
    worktree_root: Path,
    *,
    event: str,
    lane_id: str,
    **fields: Any,
) -> None:
    """Append one event line to events.jsonl."""
    if event not in EVENT_VOCAB:
        raise ValueError(
            f"event {event!r} not in event vocabulary "
            f"(see EVENT_VOCAB; contract bump required to add)"
        )
    worktree_root.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        "lane_id": lane_id,
    }
    payload.update(fields)
    line = json.dumps(payload, sort_keys=True)
    with open(worktree_root / EVENTS_FILENAME, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_events(worktree_root: Path) -> list[dict[str, Any]]:
    """Read all events; skips corrupt lines."""
    path = worktree_root / EVENTS_FILENAME
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
