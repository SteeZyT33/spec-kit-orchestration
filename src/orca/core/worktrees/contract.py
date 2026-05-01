"""Loader + merge logic for .worktree-contract.json.

Per docs/superpowers/specs/2026-05-01-orca-worktree-contract-design.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONTRACT_FILENAME = ".worktree-contract.json"
SUPPORTED_SCHEMA_VERSION = 1


class ContractError(ValueError):
    """Raised on contract schema violation."""


@dataclass(frozen=True)
class ContractData:
    schema_version: int
    symlink_paths: list[str] = field(default_factory=list)
    symlink_files: list[str] = field(default_factory=list)
    init_script: str | None = None


def _contract_path(repo_root: Path) -> Path:
    return repo_root / CONTRACT_FILENAME


def _validate_path_relative(p: str, field_name: str) -> None:
    if Path(p).is_absolute():
        raise ContractError(
            f"{field_name}: absolute paths rejected (got {p!r}); "
            f"contract paths are repo-root-relative"
        )
    parts = Path(p).parts
    if ".." in parts:
        raise ContractError(
            f"{field_name}: path traversal rejected (got {p!r})"
        )


def load_contract(repo_root: Path) -> ContractData | None:
    """Read .worktree-contract.json from repo_root.

    Returns None if file is absent. Raises ContractError on schema violation.
    """
    path = _contract_path(repo_root)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ContractError(f"contract parse failed: {exc}") from exc
    if not isinstance(raw, dict):
        raise ContractError(
            f"contract must be a JSON object, got {type(raw).__name__}"
        )

    schema_version = raw.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ContractError(
            f"schema_version={schema_version!r} not supported; "
            f"this orca expects {SUPPORTED_SCHEMA_VERSION}"
        )

    for field_name in ("symlink_paths", "symlink_files"):
        value = raw.get(field_name, [])
        if not isinstance(value, list):
            raise ContractError(
                f"{field_name} must be a list, got {type(value).__name__}"
            )
        for entry in value:
            if not isinstance(entry, str):
                raise ContractError(
                    f"{field_name} entries must be strings; got "
                    f"{type(entry).__name__}"
                )
            _validate_path_relative(entry, field_name)

    init_script = raw.get("init_script")
    if init_script is not None:
        if not isinstance(init_script, str):
            raise ContractError(
                f"init_script must be a string or null, got "
                f"{type(init_script).__name__}"
            )
        _validate_path_relative(init_script, "init_script")

    if "extensions" in raw:
        ext = raw["extensions"]
        if not isinstance(ext, dict):
            raise ContractError(
                f"extensions must be a JSON object, got "
                f"{type(ext).__name__}"
            )

    return ContractData(
        schema_version=schema_version,
        symlink_paths=list(raw.get("symlink_paths", [])),
        symlink_files=list(raw.get("symlink_files", [])),
        init_script=init_script,
    )


def merge_symlinks(
    host: list[str],
    contract: list[str] | None,
    toml: list[str],
) -> list[str]:
    """Union three symlink-path lists in order host → contract → toml.

    Deduplicates while preserving first-insertion position. Used by
    auto_symlink.run_stage1 to produce the final symlink list per spec
    §"Conflict resolution".
    """
    chained = list(host) + list(contract or []) + list(toml)
    return list(dict.fromkeys(chained))
