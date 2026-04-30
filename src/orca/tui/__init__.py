"""Orca TUI - read-only Textual view of review / event-feed state.

Phase 1 scope: projection, never a source. The TUI watches files the
existing CLI already writes and renders them. No mutations.

Entry point: `python -m orca.tui`. See `specs/018-orca-tui/`.
"""

from __future__ import annotations

from orca.tui.app import OrcaTUI, main

__all__ = ["OrcaTUI", "main"]
