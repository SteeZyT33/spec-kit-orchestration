"""TOFU (trust-on-first-use) hook ledger.

Hook scripts run with operator's full privileges. The ledger records
which (repo_key, script_path, sha256) triples the operator has approved.
First run prompts; subsequent runs match against the ledger.

Storage: ${ORCA_TRUST_LEDGER:-${XDG_CONFIG_HOME:-$HOME/.config}/orca/worktree-trust.json}.
Locking: same fcntl/msvcrt strategy as the registry, on a sibling .lock file.
"""
from __future__ import annotations

import contextlib
import errno
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LEDGER_FILENAME = "worktree-trust.json"
_DEFAULT_TRUST_LOCK_TIMEOUT_S = 30.0


def ledger_path() -> Path:
    """Resolve ledger path per env precedence."""
    explicit = os.environ.get("ORCA_TRUST_LEDGER")
    if explicit:
        return Path(explicit)
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "orca" / LEDGER_FILENAME


def _trust_lock_path() -> Path:
    """Sibling .lock file for the trust ledger; protects concurrent record."""
    p = ledger_path()
    return p.with_suffix(p.suffix + ".lock")


@contextlib.contextmanager
def _acquire_trust_lock(timeout_s: float | None = None):
    """Cross-platform advisory lock on a sibling .lock file.

    Mirrors registry.acquire_registry_lock so concurrent ``check_or_prompt``
    calls (with record=True) don't lose ledger writes. fcntl on POSIX,
    msvcrt on Windows.
    """
    timeout = timeout_s if timeout_s is not None else float(
        os.environ.get("ORCA_TRUST_LOCK_TIMEOUT",
                       _DEFAULT_TRUST_LOCK_TIMEOUT_S)
    )
    path = _trust_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with open(path, "wb") as f:
            f.write(b"\0")  # Sentinel byte for Windows msvcrt

    if sys.platform == "win32":
        ctx = _windows_trust_lock(path, timeout)
    else:
        ctx = _posix_trust_lock(path, timeout)
    with ctx:
        yield


@contextlib.contextmanager
def _posix_trust_lock(path: Path, timeout: float):
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
                    raise TimeoutError(
                        f"could not acquire trust lock {path} within "
                        f"{timeout}s"
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
def _windows_trust_lock(path: Path, timeout: float):
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
                    raise TimeoutError(
                        f"could not acquire trust lock {path} within "
                        f"{timeout}s"
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


def resolve_repo_key(repo_root: Path) -> str:
    """Return remote.origin.url if available; else realpath of the repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, check=False,
        )
        url = result.stdout.strip()
        if url:
            return url
    except (FileNotFoundError, OSError):
        pass
    return str(repo_root.resolve())


@dataclass
class _Entry:
    repo_key: str
    script_path: str
    sha: str


@dataclass
class TrustLedger:
    """In-memory ledger snapshot. Use .load()/.save() for I/O."""
    entries: list[_Entry] = field(default_factory=list)

    @classmethod
    def load(cls) -> "TrustLedger":
        path = ledger_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        entries = [
            _Entry(
                repo_key=e["repo_key"],
                script_path=e["script_path"],
                sha=e["sha"],
            )
            for e in data.get("entries", [])
            if isinstance(e, dict) and "repo_key" in e
        ]
        return cls(entries=entries)

    def is_trusted(self, repo_key: str, script_path: str, sha: str) -> bool:
        return any(
            e.repo_key == repo_key and e.script_path == script_path and e.sha == sha
            for e in self.entries
        )

    def record(self, *, repo_key: str, script_path: str, sha: str) -> None:
        # Replace any prior entry for the same (repo_key, script_path)
        self.entries = [
            e for e in self.entries
            if not (e.repo_key == repo_key and e.script_path == script_path)
        ]
        self.entries.append(_Entry(repo_key, script_path, sha))

    def save(self) -> None:
        path = ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "schema_version": 1,
            "entries": [
                {"repo_key": e.repo_key, "script_path": e.script_path, "sha": e.sha}
                for e in self.entries
            ],
        }
        encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        tmp = path.with_suffix(path.suffix + ".partial")
        tmp.write_bytes(encoded)
        tmp.replace(path)


# --- Task 14: trust prompt flow ---
import enum


class TrustOutcome(enum.Enum):
    """Outcome of a trust check.

    TRUSTED: matched an existing ledger entry; no prompt shown.
    RECORDED: bypass + record (--trust-hooks --record) OR interactive yes.
    BYPASSED: --trust-hooks without --record; one-shot bypass.
    DECLINED: interactive prompt answered 'no'.
    REFUSED_NONINTERACTIVE: stdin not a tty AND no --trust-hooks AND not in
        ledger; CLI handler should exit INPUT_INVALID with hint.
    """
    TRUSTED = "trusted"
    RECORDED = "recorded"
    BYPASSED = "bypassed"
    DECLINED = "declined"
    REFUSED_NONINTERACTIVE = "refused_noninteractive"


@dataclass(frozen=True)
class TrustDecision:
    trust_hooks: bool  # --trust-hooks or ORCA_TRUST_HOOKS=1
    record: bool       # --record subflag


def check_or_prompt(
    *,
    repo_key: str,
    script_path: str,
    sha: str,
    script_text: str,
    decision: TrustDecision,
    interactive: bool,
) -> TrustOutcome:
    """Resolve trust for a hook script.

    Logic:
      1. If already in ledger: TRUSTED
      2. Else if decision.trust_hooks and decision.record: record + RECORDED
      3. Else if decision.trust_hooks: BYPASSED (no record)
      4. Else if not interactive: REFUSED_NONINTERACTIVE
      5. Else: prompt; on 'y' -> record + RECORDED; on 'n' -> DECLINED
    """
    # Hold the trust lock around load → mutate → save so concurrent
    # `wt new --record` calls serialize and don't drop writes.
    with _acquire_trust_lock():
        ledger = TrustLedger.load()
        if ledger.is_trusted(repo_key, script_path, sha):
            return TrustOutcome.TRUSTED

        if decision.trust_hooks:
            if decision.record:
                ledger.record(
                    repo_key=repo_key, script_path=script_path, sha=sha,
                )
                ledger.save()
                return TrustOutcome.RECORDED
            return TrustOutcome.BYPASSED

        if not interactive:
            return TrustOutcome.REFUSED_NONINTERACTIVE

        print(f"\nHook script: {script_path}")
        print(f"SHA-256: {sha}")
        print("--- script content ---")
        print(script_text)
        print("--- end script ---")
        print(f"Trust this script for repo {repo_key}? [y/N]: ",
              end="", flush=True)
        answer = sys.stdin.readline().strip().lower()
        if answer == "y":
            ledger.record(
                repo_key=repo_key, script_path=script_path, sha=sha,
            )
            ledger.save()
            return TrustOutcome.RECORDED
        return TrustOutcome.DECLINED
