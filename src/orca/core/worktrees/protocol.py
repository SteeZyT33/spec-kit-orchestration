"""WorktreeManager Protocol — the public surface used by CLI handlers."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CreateRequest:
    branch: str
    from_branch: str | None
    feature: str | None
    lane: str | None
    agent: str  # "claude" | "codex" | "none"
    prompt: str | None
    extra_args: list[str]
    reuse_branch: bool = False
    recreate_branch: bool = False
    no_setup: bool = False
    trust_hooks: bool = False
    record_trust: bool = False


@dataclass(frozen=True)
class CreateResult:
    lane_id: str
    worktree_path: Path
    branch: str
    tmux_session: str | None
    tmux_window: str | None
    setup_outcomes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RemoveRequest:
    branch: str
    force: bool
    keep_branch: bool
    all_lanes: bool


class WorktreeManagerProtocol(Protocol):
    def create(self, req: CreateRequest) -> CreateResult: ...
    def remove(self, req: RemoveRequest) -> None: ...
