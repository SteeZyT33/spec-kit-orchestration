"""Adoption-state collector + render helper for the TUI.

Reads `.orca/adoption.toml` (declarative) and `.orca/adoption-state.json`
(last apply outcome). Pure function of `repo_root`. Never raises:
malformed files yield blank fields rather than killing the pane.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib as _toml
else:  # pragma: no cover - 3.10 path
    import tomli as _toml  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdoptionInfo:
    """Snapshot of a repo's orca adoption state.

    `present` is True iff `.orca/adoption.toml` exists. `applied` is
    True iff `.orca/adoption-state.json` parses to a record with at
    least one applied file.
    """
    present: bool = False
    host_system: str = ""
    installed_capabilities: int = 0
    slash_namespace: str = ""
    slash_enabled: int = 0
    constitution_policy: str = ""
    applied: bool = False
    applied_files: int = 0
    applied_at: str = ""


@dataclass(frozen=True)
class AdoptionRow:
    label: str
    value: str


def collect_adoption(repo_root: Path) -> AdoptionInfo:
    manifest_path = repo_root / ".orca" / "adoption.toml"
    if not manifest_path.is_file():
        return AdoptionInfo(present=False)

    manifest_data: dict = {}
    try:
        with manifest_path.open("rb") as fh:
            manifest_data = _toml.load(fh)
    except (OSError, ValueError, _toml.TOMLDecodeError):
        logger.debug("adoption.toml unreadable: %s", manifest_path, exc_info=True)
        # File exists but unreadable: present=True, fields blank.
        return AdoptionInfo(present=True)

    host = manifest_data.get("host", {}) or {}
    orca_section = manifest_data.get("orca", {}) or {}
    slash = manifest_data.get("slash_commands", {}) or {}
    constitution = manifest_data.get("constitution", {}) or {}

    state_info = _read_state(repo_root)

    return AdoptionInfo(
        present=True,
        host_system=str(host.get("system", "") or ""),
        installed_capabilities=len(orca_section.get("installed_capabilities", []) or []),
        slash_namespace=str(slash.get("namespace", "") or ""),
        slash_enabled=len(slash.get("enabled", []) or []),
        constitution_policy=str(constitution.get("policy", "") or ""),
        applied=state_info[0],
        applied_files=state_info[1],
        applied_at=state_info[2],
    )


def _read_state(repo_root: Path) -> tuple[bool, int, str]:
    """Return (applied, file_count, applied_at) from adoption-state.json."""
    state_path = repo_root / ".orca" / "adoption-state.json"
    if not state_path.is_file():
        return (False, 0, "")
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        logger.debug("adoption-state.json unreadable: %s", state_path, exc_info=True)
        return (False, 0, "")
    files = payload.get("files") or []
    applied_at = str(payload.get("applied_at") or "")
    applied = bool(files)
    return (applied, len(files), applied_at)


def render_rows(info: AdoptionInfo) -> list[AdoptionRow]:
    """Build the key/value rows the AdoptionPane renders."""
    if not info.present:
        return [AdoptionRow(label="status", value="not adopted (run: orca-cli adopt)")]

    applied_value = (
        f"yes ({info.applied_files} files, {info.applied_at})"
        if info.applied else "manifest only (run: orca-cli apply)"
    )
    slash_value = (
        f"{info.slash_enabled} enabled (namespace: {info.slash_namespace or 'flat'})"
    )
    return [
        AdoptionRow(label="host", value=info.host_system or "(unset)"),
        AdoptionRow(
            label="capabilities",
            value=str(info.installed_capabilities),
        ),
        AdoptionRow(label="slash commands", value=slash_value),
        AdoptionRow(
            label="constitution",
            value=info.constitution_policy or "(unset)",
        ),
        AdoptionRow(label="applied", value=applied_value),
    ]
