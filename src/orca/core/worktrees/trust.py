"""TOFU (trust-on-first-use) hook ledger.

Hook scripts run with operator's full privileges. The ledger records
which (repo_key, script_path, sha256) triples the operator has approved.
First run prompts; subsequent runs match against the ledger.

Storage: ${ORCA_TRUST_LEDGER:-${XDG_CONFIG_HOME:-$HOME/.config}/orca/worktree-trust.json}.
Locking: same fcntl/msvcrt strategy as the registry, on a sibling .lock file.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LEDGER_FILENAME = "worktree-trust.json"


def ledger_path() -> Path:
    """Resolve ledger path per env precedence."""
    explicit = os.environ.get("ORCA_TRUST_LEDGER")
    if explicit:
        return Path(explicit)
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "orca" / LEDGER_FILENAME


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
