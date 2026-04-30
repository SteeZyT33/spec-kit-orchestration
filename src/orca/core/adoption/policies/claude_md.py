"""CLAUDE.md / AGENTS.md merge policies.

`apply_section` is the canonical merge: idempotent, marker-delimited,
safe to re-apply. `remove_section` removes the marker-delimited block
during revert. `detect_section` checks for marker presence.
"""
from __future__ import annotations

import re
from pathlib import Path

START_MARKER = "<!-- orca:adoption:start version=1 -->"
END_MARKER = "<!-- orca:adoption:end -->"

_BLOCK_RE = re.compile(
    rf"\n*{re.escape(START_MARKER)}\n.*?\n{re.escape(END_MARKER)}\n*",
    re.DOTALL,
)


class ClaudeMdPolicyError(ValueError):
    """Raised when a policy operation cannot proceed safely."""


def detect_section(path: Path) -> bool:
    """Return True if path exists and contains an orca-managed section."""
    if not path.exists():
        return False
    return START_MARKER in path.read_text()


def apply_section(
    path: Path,
    content: str,
    *,
    section_marker: str,
) -> None:
    """Insert or replace the orca-managed section in `path`.

    If `path` does not exist, create it with just the orca block.
    If an orca block already exists, replace it in place.
    Otherwise append the orca block (with a leading blank line).
    """
    block = _build_block(content, section_marker)
    if not path.exists():
        path.write_text(block + "\n")
        return

    existing = path.read_text()
    if START_MARKER in existing:
        new = _BLOCK_RE.sub("\n\n" + block + "\n", existing)
    else:
        sep = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
        new = existing + sep + block + "\n"

    if new != existing:
        path.write_text(new)


def remove_section(path: Path) -> None:
    """Remove the orca-managed section from `path`, if present.

    No-op if path missing or no markers present.
    """
    if not path.exists():
        return
    existing = path.read_text()
    if START_MARKER not in existing:
        return
    cleaned = _BLOCK_RE.sub("\n", existing)
    # Collapse triple blank lines down to double
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    path.write_text(cleaned)


def _build_block(content: str, section_marker: str) -> str:
    body = content if content.endswith("\n") else content + "\n"
    return f"{START_MARKER}\n{section_marker}\n\n{body}{END_MARKER}"
