"""Registry + sidecar persistence with atomic writes and dual-emit legacy fields.

Layout under <repo>/.orca/worktrees/:
  registry.json         schema_version 2; lanes = [{lane_id, branch, ...}]
  registry.lock         lock file for fcntl/msvcrt protection
  <lane_id>.json        per-lane sidecar; emits both v2 and legacy keys
  events.jsonl          append-only lifecycle event log
  registry.v1.bak.json  one-shot backup written by the v1->v2 migrator
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 2


@dataclass(frozen=True)
class Sidecar:
    schema_version: int
    lane_id: str
    lane_mode: str  # "branch" | "lane"
    feature_id: Optional[str]
    lane_name: Optional[str]
    branch: str
    base_branch: str
    worktree_path: str
    created_at: str  # ISO-8601 UTC
    tmux_session: str
    tmux_window: str
    agent: str  # "claude" | "codex" | "none"
    setup_version: str
    last_attached_at: Optional[str]
    host_system: str
    status: str = "active"
    task_scope: list[str] = field(default_factory=list)


def sidecar_path(worktree_root: Path, lane_id: str) -> Path:
    return worktree_root / f"{lane_id}.json"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    tmp = path.with_suffix(path.suffix + ".partial")
    try:
        tmp.write_bytes(encoded)
        tmp.replace(path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def write_sidecar(worktree_root: Path, sc: Sidecar) -> None:
    """Atomic write with dual-emit legacy fields for sdd_adapter compat."""
    payload = asdict(sc)
    # Dual-emit: legacy field names alongside v2 names. Read-side compat
    # for src/orca/sdd_adapter.py:799-845.
    # TODO(schema-v3, 2026-Q4): drop dual-emit of {id, feature, path} once
    # all consumers read v2-shaped fields. Tracked per spec line 393.
    payload["id"] = sc.lane_id
    payload["feature"] = sc.feature_id
    payload["path"] = sc.worktree_path
    _atomic_write_json(sidecar_path(worktree_root, sc.lane_id), payload)


def read_sidecar(path: Path) -> Sidecar | None:
    """Read a sidecar; return None if missing or corrupt."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    try:
        return Sidecar(
            schema_version=data["schema_version"],
            lane_id=data["lane_id"],
            lane_mode=data["lane_mode"],
            feature_id=data.get("feature_id"),
            lane_name=data.get("lane_name"),
            branch=data["branch"],
            base_branch=data["base_branch"],
            worktree_path=data["worktree_path"],
            created_at=data["created_at"],
            tmux_session=data["tmux_session"],
            tmux_window=data["tmux_window"],
            agent=data["agent"],
            setup_version=data["setup_version"],
            last_attached_at=data.get("last_attached_at"),
            host_system=data["host_system"],
            status=data.get("status", "active"),
            task_scope=data.get("task_scope", []),
        )
    except KeyError:
        return None


@dataclass(frozen=True)
class LaneRow:
    lane_id: str
    branch: str
    worktree_path: str
    feature_id: Optional[str] = None


@dataclass(frozen=True)
class RegistryView:
    schema_version: int
    lanes: list[LaneRow]


def registry_path(worktree_root: Path) -> Path:
    return worktree_root / "registry.json"


def write_registry(worktree_root: Path, lanes: list[LaneRow]) -> None:
    """Atomic write of v2 registry. Caller must hold the registry lock."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "lanes": [asdict(row) for row in lanes],
    }
    _atomic_write_json(registry_path(worktree_root), payload)


def read_registry(worktree_root: Path) -> RegistryView:
    """Read v2 registry. Returns empty view if missing or corrupt.

    Tolerates v1 (string lanes) by normalizing on read; full migration is
    handled by `migrate_v1_to_v2` (Task 8). This function is read-only and
    does NOT mutate the registry on disk.
    """
    path = registry_path(worktree_root)
    if not path.exists():
        return RegistryView(schema_version=SCHEMA_VERSION, lanes=[])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return RegistryView(schema_version=SCHEMA_VERSION, lanes=[])

    raw_lanes = data.get("lanes", [])
    rows: list[LaneRow] = []
    for entry in raw_lanes:
        if isinstance(entry, str):
            # v1 shape: string lane-id only. Hydrate from sidecar if present.
            sc = read_sidecar(sidecar_path(worktree_root, entry))
            if sc is not None:
                rows.append(LaneRow(
                    lane_id=sc.lane_id,
                    branch=sc.branch,
                    worktree_path=sc.worktree_path,
                    feature_id=sc.feature_id,
                ))
        elif isinstance(entry, dict):
            try:
                rows.append(LaneRow(
                    lane_id=entry["lane_id"],
                    branch=entry["branch"],
                    worktree_path=entry["worktree_path"],
                    feature_id=entry.get("feature_id"),
                ))
            except KeyError:
                continue
        # Other types: skip silently
    return RegistryView(
        schema_version=data.get("schema_version", 1),
        lanes=rows,
    )
