"""Pure-data shapes for the fleet view. No Textual imports."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FleetRow:
    """One row in the fleet view. Everything pre-rendered to strings."""
    lane_id: str
    feature_id: str | None
    branch: str
    worktree_path: str
    agent: str  # "claude" | "codex" | "none"
    state: str  # "live" | "stale" | "merged" | "failed" | "idle"
    stage_segments: tuple[tuple[str, str], ...]  # (text, style) pairs
    last_seen: str
    done: str
    health: str
