"""Agent session presence tracking.

Every Orca command writes a heartbeat file so operators and other agents
can see "who is working where right now". Sessions auto-reap after a TTL
so crashed agents don't hold phantom locks.

File layout::

    .orca/sessions/
    ├── <session-id>.json      # one per active agent session
    └── .lock                   # flock-backed write lock

Session file shape::

    {
        "session_id": "claude-abc123def456",
        "agent": "claude",
        "started": "2026-04-16T10:15:00+00:00",
        "last_heartbeat": "2026-04-16T10:47:32+00:00",
        "scope": {
            "feature_dir": "specs/022-mneme",
            "lane_id": "022-mneme",
            "worktree": ".orca/worktrees/022-mneme"
        },
        "pid": 12345,
        "host": "Kyrgyzstan"
    }

Stdlib-only. No heartbeat daemon — each operation that uses the registry
touches its own heartbeat and opportunistically reaps stale siblings.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import platform
import re
import secrets
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

# Session TTL: 5 minutes since last heartbeat. Any session older than this
# is treated as crashed and auto-reaped by the next command that touches
# the session directory. Generous enough to span a long LLM turn, tight
# enough that abandoned sessions don't hold lane scopes forever.
SESSION_TTL_SECONDS: int = 300

SESSIONS_DIRNAME: str = ".orca/sessions"
SESSION_LOCK_FILENAME: str = ".lock"

# Session IDs are used verbatim in filesystem paths. Restrict to a
# conservative filesystem-safe pattern so values like "../../evil" or
# "/etc/passwd" cannot escape the sessions dir. Length cap keeps the
# resulting filename well below any sane filesystem limit.
_SAFE_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _validate_session_id(session_id: str) -> str:
    """Return session_id if filesystem-safe; raise ValueError otherwise.

    Rejects empty strings, path separators, leading dots that could
    produce dotfiles or traversal segments, and anything outside the
    allowed character class.
    """
    if not isinstance(session_id, str) or not _SAFE_SESSION_ID_RE.fullmatch(session_id):
        raise ValueError(
            f"Invalid session_id {session_id!r}: must match "
            f"^[A-Za-z0-9._-]{{1,128}}$ and may not traverse paths."
        )
    if session_id in {".", ".."} or session_id.startswith("."):
        raise ValueError(
            f"Invalid session_id {session_id!r}: may not start with '.'"
        )
    return session_id


@dataclass
class SessionScope:
    """What the session is working on. All fields optional."""

    feature_dir: str | None = None
    lane_id: str | None = None
    worktree: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SessionScope":
        if not data:
            return cls()
        return cls(
            feature_dir=data.get("feature_dir"),
            lane_id=data.get("lane_id"),
            worktree=data.get("worktree"),
        )

    def overlaps(self, other: "SessionScope") -> bool:
        """Two scopes conflict if they name the same lane or feature dir.

        Worktree overlap alone is not a conflict — two agents inspecting
        the same worktree read-only is fine. Conflict requires an
        intentional-work scope (lane_id or feature_dir).
        """
        if self.lane_id and other.lane_id and self.lane_id == other.lane_id:
            return True
        if (
            self.feature_dir
            and other.feature_dir
            and self.feature_dir == other.feature_dir
        ):
            return True
        return False


@dataclass
class Session:
    """A live agent session."""

    session_id: str
    agent: str
    started: str
    last_heartbeat: str
    scope: SessionScope = field(default_factory=SessionScope)
    pid: int = 0
    host: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent": self.agent,
            "started": self.started,
            "last_heartbeat": self.last_heartbeat,
            "scope": self.scope.to_dict(),
            "pid": self.pid,
            "host": self.host,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        return cls(
            session_id=data["session_id"],
            agent=data["agent"],
            started=data["started"],
            last_heartbeat=data["last_heartbeat"],
            scope=SessionScope.from_dict(data.get("scope")),
            pid=int(data.get("pid", 0)),
            host=data.get("host", ""),
        )

    def is_stale(self, ttl_seconds: int = SESSION_TTL_SECONDS, now: datetime | None = None) -> bool:
        """True if last_heartbeat is older than ttl_seconds.

        Defensive about the two ways a timestamp can be unusable:
          - ``fromisoformat`` raises ``ValueError`` on garbage input.
          - ``fromisoformat`` returns an offset-naive datetime when the
            input has no timezone. Subtracting that from our aware
            ``now`` would raise ``TypeError``. Treat both as stale so a
            single bad file can't crash ``_reap_stale_unlocked`` /
            ``list_active_sessions``.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        try:
            last = datetime.fromisoformat(self.last_heartbeat)
        except (ValueError, TypeError):
            return True  # unparseable timestamp -> treat as stale
        if last.tzinfo is None or last.utcoffset() is None:
            return True  # offset-naive timestamp -> treat as stale
        try:
            delta = (now - last).total_seconds()
        except TypeError:
            return True  # mismatched datetime kinds -> treat as stale
        return delta > ttl_seconds


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sessions_dir(repo_root: Path) -> Path:
    return repo_root / SESSIONS_DIRNAME


def _ensure_dir(repo_root: Path) -> Path:
    directory = _sessions_dir(repo_root)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@contextlib.contextmanager
def _lock(repo_root: Path, timeout_seconds: float = 5.0) -> Iterator[None]:
    """Advisory flock on .orca/sessions/.lock. Stdlib fcntl."""
    directory = _ensure_dir(repo_root)
    lock_path = directory / SESSION_LOCK_FILENAME
    with open(lock_path, "a+") as fh:
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Could not acquire session lock at {lock_path} "
                        f"within {timeout_seconds}s"
                    ) from None
                time.sleep(0.05)
        try:
            yield
        finally:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON via tempfile + rename so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)
        raise


def _session_path(repo_root: Path, session_id: str) -> Path:
    """Resolve the on-disk path for a session file.

    Validates ``session_id`` against a filesystem-safe pattern before
    interpolating it into the filename so callers cannot escape
    ``.orca/sessions`` with values like ``../../evil``.
    """
    safe_id = _validate_session_id(session_id)
    candidate = _sessions_dir(repo_root) / f"{safe_id}.json"
    # Defense in depth: even after the regex check, make sure the
    # resolved path is still inside the sessions directory. The parent
    # dir may not exist yet, so resolve the parent via its own resolve()
    # and then join the (validated) filename.
    sessions_root = _sessions_dir(repo_root)
    sessions_root.mkdir(parents=True, exist_ok=True)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(sessions_root.resolve())
    except ValueError as exc:
        raise ValueError(
            f"Resolved session path {resolved} escapes sessions dir "
            f"{sessions_root.resolve()}"
        ) from exc
    return candidate


def _read_session_file(path: Path) -> Session | None:
    """Read one session file. Returns None if corrupt or missing."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None
    try:
        return Session.from_dict(data)
    except (KeyError, TypeError, ValueError):
        return None


def _generate_session_id(agent: str) -> str:
    """Deterministic-ish ID: <agent>-<8 hex chars>. Collisions rejected by create.

    The agent name is sanitized to keep the generated id within the
    filesystem-safe character class AND aligned with the stricter
    validator pattern. Agent values that do not start with an
    alphanumeric character (e.g. ``.claude``) or contain unsafe
    characters are collapsed to ``agent`` so the produced id always
    passes ``_validate_session_id``.
    """
    safe_agent = (
        agent
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", agent or "")
        else "agent"
    )
    return f"{safe_agent}-{secrets.token_hex(4)}"


def _reap_stale_unlocked(repo_root: Path, ttl_seconds: int = SESSION_TTL_SECONDS) -> list[str]:
    """Delete session files older than TTL. Caller must hold the lock."""
    directory = _sessions_dir(repo_root)
    if not directory.is_dir():
        return []
    reaped: list[str] = []
    now = datetime.now(timezone.utc)
    for session_file in directory.glob("*.json"):
        session = _read_session_file(session_file)
        if session is None:
            # Corrupt file — reap it
            with contextlib.suppress(FileNotFoundError):
                session_file.unlink()
            reaped.append(session_file.stem)
            continue
        if session.is_stale(ttl_seconds=ttl_seconds, now=now):
            with contextlib.suppress(FileNotFoundError):
                session_file.unlink()
            reaped.append(session.session_id)
    return reaped


# ─── Public API ──────────────────────────────────────────────────────────


def list_active_sessions(
    *, repo_root: Path | str, reap: bool = True, ttl_seconds: int = SESSION_TTL_SECONDS
) -> list[Session]:
    """Return all non-stale sessions. Reaps stale ones first unless reap=False."""
    root = Path(repo_root)
    directory = _sessions_dir(root)
    if not directory.is_dir():
        return []
    with _lock(root):
        if reap:
            _reap_stale_unlocked(root, ttl_seconds=ttl_seconds)
        now = datetime.now(timezone.utc)
        sessions: list[Session] = []
        for session_file in directory.glob("*.json"):
            session = _read_session_file(session_file)
            if session is None:
                continue
            if session.is_stale(ttl_seconds=ttl_seconds, now=now):
                continue
            sessions.append(session)
        sessions.sort(key=lambda s: s.started)
        return sessions


def find_conflicting_session(
    scope: SessionScope,
    *,
    repo_root: Path | str,
    exclude_session_id: str | None = None,
    ttl_seconds: int = SESSION_TTL_SECONDS,
) -> Session | None:
    """Return an active session whose scope overlaps with ``scope``, or None.

    exclude_session_id lets a session refresh its own registration
    without detecting itself as a conflict.
    """
    for session in list_active_sessions(repo_root=repo_root, ttl_seconds=ttl_seconds):
        if exclude_session_id and session.session_id == exclude_session_id:
            continue
        if session.scope.overlaps(scope):
            return session
    return None


def start_session(
    *,
    agent: str,
    repo_root: Path | str,
    scope: SessionScope | None = None,
    session_id: str | None = None,
) -> Session:
    """Create and persist a new session file. Returns the Session record."""
    root = Path(repo_root)
    _ensure_dir(root)
    sid = session_id or _generate_session_id(agent)
    now = _now_iso()
    session = Session(
        session_id=sid,
        agent=agent,
        started=now,
        last_heartbeat=now,
        scope=scope or SessionScope(),
        pid=os.getpid(),
        host=platform.node() or "",
    )
    with _lock(root):
        _reap_stale_unlocked(root)
        path = _session_path(root, sid)
        if path.exists():
            raise FileExistsError(f"Session file already exists: {path}")
        _atomic_write(path, session.to_dict())
    return session


def heartbeat(
    session_id: str,
    *,
    repo_root: Path | str,
    scope: SessionScope | None = None,
) -> Session:
    """Update last_heartbeat (and optionally scope) for an existing session.

    Raises FileNotFoundError if the session was already reaped or never
    existed. Callers that want idempotent upsert should catch and restart.
    """
    root = Path(repo_root)
    path = _session_path(root, session_id)
    with _lock(root):
        session = _read_session_file(path)
        if session is None:
            raise FileNotFoundError(f"Session {session_id} not found")
        session.last_heartbeat = _now_iso()
        if scope is not None:
            session.scope = scope
        _atomic_write(path, session.to_dict())
        return session


def end_session(session_id: str, *, repo_root: Path | str) -> bool:
    """Remove the session file. Returns True if it existed, False otherwise."""
    root = Path(repo_root)
    path = _session_path(root, session_id)
    with _lock(root):
        if path.exists():
            path.unlink()
            return True
        return False


@contextlib.contextmanager
def session_scope(
    *,
    agent: str,
    repo_root: Path | str,
    scope: SessionScope | None = None,
) -> Iterator[Session]:
    """Context manager: start a session on entry, end it on exit.

    Usage::

        with session_scope(agent="claude", repo_root=".", scope=SessionScope(lane_id="X")) as s:
            ...  # do work; optionally call heartbeat(s.session_id, ...)
    """
    session = start_session(agent=agent, repo_root=repo_root, scope=scope)
    try:
        yield session
    finally:
        with contextlib.suppress(FileNotFoundError):
            end_session(session.session_id, repo_root=repo_root)
