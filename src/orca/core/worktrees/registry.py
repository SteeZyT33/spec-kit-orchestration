"""Registry + sidecar persistence with atomic writes and dual-emit legacy fields.

Layout under <repo>/.orca/worktrees/:
  registry.json         schema_version 2; lanes = [{lane_id, branch, ...}]
  registry.lock         lock file for fcntl/msvcrt protection
  <lane_id>.json        per-lane sidecar; emits both v2 and legacy keys
  events.jsonl          append-only lifecycle event log
  registry.v1.bak.json  one-shot backup written by the v1->v2 migrator
"""
from __future__ import annotations

import contextlib
import errno
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 2
LOCK_FILENAME = "registry.lock"
DEFAULT_LOCK_TIMEOUT_S = 30.0


class LockTimeout(RuntimeError):
    """Raised when registry lock cannot be acquired within the timeout."""


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


def _lock_path(worktree_root: Path) -> Path:
    return worktree_root / LOCK_FILENAME


def _ensure_lock_file(path: Path) -> None:
    """Create the lock file with a 1-byte sentinel if missing.

    Windows msvcrt.locking on a 0-byte file returns EINVAL; the sentinel
    ensures byte 0 exists for both POSIX (where it's harmless) and Windows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with open(path, "wb") as f:
            f.write(b"\0")


@contextlib.contextmanager
def acquire_registry_lock(
    worktree_root: Path,
    *,
    timeout_s: float | None = None,
):
    """Acquire an exclusive lock on registry.lock for the duration of the
    `with` block. Cross-platform: fcntl on POSIX, msvcrt on Windows.

    Raises LockTimeout if the lock cannot be acquired within timeout_s.
    """
    timeout = timeout_s if timeout_s is not None else float(
        os.environ.get("ORCA_WT_LOCK_TIMEOUT", DEFAULT_LOCK_TIMEOUT_S)
    )
    path = _lock_path(worktree_root)
    _ensure_lock_file(path)

    if sys.platform == "win32":
        ctx = _windows_lock(path, timeout)
    else:
        ctx = _posix_lock(path, timeout)

    with ctx:
        yield


@contextlib.contextmanager
def _posix_lock(path: Path, timeout: float):
    import fcntl
    fd = os.open(str(path), os.O_RDWR)
    deadline = time.monotonic() + timeout
    attempt = 0
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as e:
                if e.errno not in (errno.EAGAIN, errno.EACCES):
                    raise
                if time.monotonic() >= deadline:
                    raise LockTimeout(
                        f"could not acquire {path} within {timeout}s"
                    ) from e
                time.sleep(min(0.05 * (2 ** attempt), 0.5))
                attempt += 1
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


@contextlib.contextmanager
def _windows_lock(path: Path, timeout: float):
    """Windows msvcrt mandatory byte-range lock on byte 0, length 1.

    Uses LK_NBLCK (non-blocking) + retry loop. Avoids LK_LOCK because
    Windows blocking locks can deadlock when the holder is itself blocked.
    """
    import msvcrt  # type: ignore[import-not-found]
    fd = os.open(str(path), os.O_RDWR)
    deadline = time.monotonic() + timeout
    attempt = 0
    locked = False
    try:
        while True:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                locked = True
                break
            except OSError as e:
                if e.errno not in (errno.EACCES, errno.EDEADLK):
                    raise
                if time.monotonic() >= deadline:
                    raise LockTimeout(
                        f"could not acquire {path} within {timeout}s"
                    ) from e
                time.sleep(min(0.1 * (2 ** attempt), 1.0))
                attempt += 1
        yield
    finally:
        if locked:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        os.close(fd)


def migrate_v1_to_v2(worktree_root: Path) -> bool:
    """Migrate a v1 (string-lane) registry to v2 (object-lane) shape.

    Returns True if migration was performed, False if no-op (already v2 or
    no registry). Backs up the v1 file as registry.v1.bak.json before write.
    Caller should hold the registry lock when invoking this.
    """
    path = registry_path(worktree_root)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    if data.get("schema_version") == SCHEMA_VERSION:
        return False  # already v2

    raw_lanes = data.get("lanes", [])
    rows: list[LaneRow] = []
    for entry in raw_lanes:
        if isinstance(entry, str):
            sc = read_sidecar(sidecar_path(worktree_root, entry))
            if sc is not None:
                rows.append(LaneRow(
                    lane_id=sc.lane_id,
                    branch=sc.branch,
                    worktree_path=sc.worktree_path,
                    feature_id=sc.feature_id,
                ))
        elif isinstance(entry, dict) and "lane_id" in entry:
            rows.append(LaneRow(
                lane_id=entry["lane_id"],
                branch=entry["branch"],
                worktree_path=entry["worktree_path"],
                feature_id=entry.get("feature_id"),
            ))

    backup = worktree_root / "registry.v1.bak.json"
    backup.write_bytes(path.read_bytes())
    write_registry(worktree_root, rows)
    return True
