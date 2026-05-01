"""worktrees.toml + worktrees.local.toml loader with deep-merge.

worktrees.toml: committed (set-once team policy).
worktrees.local.toml: gitignored (per-machine overrides).
Local overrides committed via TOML deep-merge, last-writer-wins per key.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

SUPPORTED_SCHEMA_VERSION = 1

_DEFAULT_AGENTS = {
    "claude": "claude --dangerously-skip-permissions",
    "codex": "codex --yolo",
}


class ConfigError(ValueError):
    """Raised when worktrees.toml schema is invalid."""


@dataclass(frozen=True)
class WorktreesConfig:
    schema_version: int = 1
    base: str = ".orca/worktrees"
    lane_id_mode: Literal["branch", "lane", "auto"] = "auto"
    symlink_paths: list[str] = field(default_factory=list)
    symlink_files: list[str] = field(
        default_factory=lambda: [".env", ".env.local", ".env.secrets"]
    )
    after_create_hook: str = "after_create"
    before_run_hook: str = "before_run"
    before_remove_hook: str = "before_remove"
    tmux_session: str = "orca"
    default_agent: Literal["claude", "codex", "none"] = "claude"
    agents: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_AGENTS))


def _require_list(d: dict[str, Any], key: str) -> list[Any]:
    if key not in d:
        return []
    value = d[key]
    if not isinstance(value, list):
        raise ConfigError(
            f"worktrees.{key} must be a list, got {type(value).__name__}"
        )
    return list(value)


def _merge(committed: dict, local: dict) -> dict:
    """Deep-merge: local overrides committed, last-writer-wins per leaf key."""
    out = dict(committed)
    for key, val in local.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], val)
        else:
            out[key] = val
    return out


def load_config(repo_root: Path) -> WorktreesConfig:
    """Load + merge worktrees.toml and worktrees.local.toml. Returns defaults
    if both are missing."""
    committed_path = repo_root / ".orca" / "worktrees.toml"
    local_path = repo_root / ".orca" / "worktrees.local.toml"

    committed: dict[str, Any] = {}
    local: dict[str, Any] = {}
    if committed_path.exists():
        committed = tomllib.loads(committed_path.read_text(encoding="utf-8"))
    if local_path.exists():
        local = tomllib.loads(local_path.read_text(encoding="utf-8"))

    merged = _merge(committed, local)
    section = merged.get("worktrees", {})
    if not section:
        return WorktreesConfig()

    schema_version = section.get("schema_version", SUPPORTED_SCHEMA_VERSION)
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ConfigError(
            f"worktrees.schema_version={schema_version} not supported; "
            f"expected {SUPPORTED_SCHEMA_VERSION}"
        )

    # Distinguish "key absent" (use defaults) from "explicit []" (operator
    # wants no .env symlinks at all). The previous truthy fallback collapsed
    # both cases.
    if "symlink_files" in section:
        symlink_files = _require_list(section, "symlink_files")
    else:
        symlink_files = list(WorktreesConfig().symlink_files)

    return WorktreesConfig(
        schema_version=schema_version,
        base=section.get("base", ".orca/worktrees"),
        lane_id_mode=section.get("lane_id_mode", "auto"),
        symlink_paths=_require_list(section, "symlink_paths"),
        symlink_files=symlink_files,
        after_create_hook=section.get("after_create_hook", "after_create"),
        before_run_hook=section.get("before_run_hook", "before_run"),
        before_remove_hook=section.get("before_remove_hook", "before_remove"),
        tmux_session=section.get("tmux_session", "orca"),
        default_agent=section.get("default_agent", "claude"),
        agents={**_DEFAULT_AGENTS, **section.get("agents", {})},
    )


def write_default_config(repo_root: Path) -> Path:
    """Write a default worktrees.toml if missing. Returns the path."""
    path = repo_root / ".orca" / "worktrees.toml"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "worktrees": {
            "schema_version": SUPPORTED_SCHEMA_VERSION,
            "base": ".orca/worktrees",
            "lane_id_mode": "auto",
            "tmux_session": "orca",
            "default_agent": "claude",
            "agents": dict(_DEFAULT_AGENTS),
        }
    }
    encoded = tomli_w.dumps(payload).encode("utf-8")
    tmp = path.with_suffix(".toml.partial")
    tmp.write_bytes(encoded)
    tmp.replace(path)
    return path
