"""Path-safety validation helpers.

Enforces docs/superpowers/contracts/path-safety.md at CLI boundaries.

Design:
- Pure stdlib (pathlib, re, os).
- Each validator raises PathSafetyError on contract violation, returns the
  resolved Path (or sanitized string for identifiers) on success.
- Exception carries field/rule_violated/value_redacted suitable for
  INPUT_INVALID error envelopes via to_error_detail().
"""
from __future__ import annotations

import os
import re
from pathlib import Path


class PathSafetyError(Exception):
    """Raised by path_safety helpers on contract violation."""

    def __init__(
        self,
        message: str,
        *,
        field: str,
        rule_violated: str,
        value_redacted: str,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.rule_violated = rule_violated
        self.value_redacted = value_redacted

    def to_error_detail(self) -> dict:
        return {
            "field": self.field,
            "rule_violated": self.rule_violated,
            "value_redacted": self.value_redacted,
        }


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_identifier(
    value: str,
    *,
    field: str,
    max_length: int = 128,
) -> str:
    """Validate a Class D identifier string.

    Returns the value unchanged on success. Raises PathSafetyError otherwise.
    Rules per contract: regex [A-Za-z0-9._-]+, not '.' or '..', not empty,
    no leading '-', length <= max_length.
    """
    if value == "":
        raise PathSafetyError(
            f"{field} is empty",
            field=field, rule_violated="identifier_empty", value_redacted="",
        )
    if value in (".", ".."):
        raise PathSafetyError(
            f"{field}={value!r} not allowed (reserved path component)",
            field=field, rule_violated="identifier_reserved", value_redacted=value,
        )
    if len(value) > max_length:
        raise PathSafetyError(
            f"{field} exceeds {max_length} chars (got {len(value)})",
            field=field, rule_violated="identifier_too_long", value_redacted=value,
        )
    if value.startswith("-"):
        raise PathSafetyError(
            f"{field}={value!r} cannot start with '-'",
            field=field, rule_violated="identifier_format", value_redacted=value,
        )
    if not _IDENTIFIER_RE.match(value):
        raise PathSafetyError(
            f"{field}={value!r} must match [A-Za-z0-9._-]+",
            field=field, rule_violated="identifier_format", value_redacted=value,
        )
    return value


def _resolve_and_check_symlink(path: Path, *, field: str) -> Path:
    """Resolve to absolute. Reject if any component traverses a symlink.

    Uses os.path.realpath vs os.path.abspath to detect component-level
    symlinks (Path.is_symlink only checks the leaf). Raises on mismatch.
    Returns the resolved Path (which equals abspath when no symlinks).
    """
    raw = str(path)
    abs_path = os.path.abspath(raw)
    real_path = os.path.realpath(raw)
    if abs_path != real_path:
        raise PathSafetyError(
            f"symlinks rejected in resolved path: {raw}",
            field=field,
            rule_violated="symlink_in_resolved_path",
            value_redacted=raw,
        )
    return Path(abs_path)


def _check_root_containment(resolved: Path, root: Path, *, field: str) -> None:
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise PathSafetyError(
            f"path outside root: {resolved} not under {root_resolved}",
            field=field,
            rule_violated="path_outside_root",
            value_redacted=str(resolved),
        )


def validate_repo_file(
    path: "str | Path",
    *,
    root: Path,
    field: str,
    must_exist: bool = True,
    max_bytes: int = 10 * 1024 * 1024,
) -> Path:
    """Validate a Class A path that must point at a regular file.

    Resolves to absolute, rejects symlinks, enforces containment in root,
    enforces regular-file type if must_exist, enforces size cap.
    Returns the resolved Path. Raises PathSafetyError on violation.
    """
    resolved = _resolve_and_check_symlink(Path(path), field=field)
    _check_root_containment(resolved, root, field=field)

    if not must_exist:
        return resolved

    if not resolved.exists():
        raise PathSafetyError(
            f"path does not exist: {resolved}",
            field=field,
            rule_violated="does_not_exist",
            value_redacted=str(resolved),
        )
    if not resolved.is_file():
        raise PathSafetyError(
            f"not a regular file: {resolved}",
            field=field,
            rule_violated="not_a_regular_file",
            value_redacted=str(resolved),
        )
    size = resolved.stat().st_size
    if size > max_bytes:
        raise PathSafetyError(
            f"file exceeds {max_bytes} byte cap ({size} bytes): {resolved}",
            field=field,
            rule_violated="size_cap_exceeded",
            value_redacted=str(resolved),
        )
    return resolved


def validate_repo_dir(
    path: "str | Path",
    *,
    root: Path,
    field: str,
    must_exist: bool = True,
) -> Path:
    """Validate a Class A path that must point at a directory.

    Same containment + symlink rules as validate_repo_file. No size cap
    (directories don't have meaningful sizes for this contract). Returns
    the resolved Path. Raises PathSafetyError on violation.
    """
    resolved = _resolve_and_check_symlink(Path(path), field=field)
    _check_root_containment(resolved, root, field=field)

    if not must_exist:
        return resolved

    if not resolved.exists():
        raise PathSafetyError(
            f"path does not exist: {resolved}",
            field=field,
            rule_violated="does_not_exist",
            value_redacted=str(resolved),
        )
    if not resolved.is_dir():
        raise PathSafetyError(
            f"not a directory: {resolved}",
            field=field,
            rule_violated="not_a_directory",
            value_redacted=str(resolved),
        )
    return resolved


def validate_findings_file(
    path: "str | Path",
    *,
    root: Path,
    field: str,
    max_bytes: int = 10 * 1024 * 1024,
) -> Path:
    """Validate a Class C findings-file path (path-shape only).

    No must_exist parameter: findings files are always read-only consumed
    by orca (the host LLM authors them out-of-band before orca runs), so
    a missing file is always a violation. Content-layer validation (JSON
    parse, schema) stays in the calling module.
    """
    return validate_repo_file(
        path, root=root, field=field, must_exist=True, max_bytes=max_bytes,
    )
