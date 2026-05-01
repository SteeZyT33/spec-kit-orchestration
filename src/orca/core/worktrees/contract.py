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
    return ContractData(
        schema_version=raw.get("schema_version", 1),
        symlink_paths=list(raw.get("symlink_paths", [])),
        symlink_files=list(raw.get("symlink_files", [])),
        init_script=raw.get("init_script"),
    )
