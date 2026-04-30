"""Adoption state.json: tracks what was applied for revertibility."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FileEntry:
    rel_path: str
    pre_hash: str
    post_hash: str


@dataclass(frozen=True)
class AdoptionState:
    manifest_hash: str
    applied_at: str  # ISO-8601 UTC
    backup_timestamp: str
    files: list[FileEntry] = field(default_factory=list)


def write_state(state: AdoptionState, path: Path) -> None:
    """Atomic write of state.json."""
    payload = {
        "manifest_hash": state.manifest_hash,
        "applied_at": state.applied_at,
        "backup_timestamp": state.backup_timestamp,
        "files": [asdict(f) for f in state.files],
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(encoded)
    tmp.replace(path)


def load_state(path: Path) -> AdoptionState:
    data = json.loads(path.read_text())
    return AdoptionState(
        manifest_hash=data["manifest_hash"],
        applied_at=data["applied_at"],
        backup_timestamp=data["backup_timestamp"],
        files=[FileEntry(**f) for f in data.get("files", [])],
    )
