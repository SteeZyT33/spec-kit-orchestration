"""Orca TUI - read-only 4-pane Textual view of lane / yolo / review state.

Phase 1 scope: projection, never a source. The TUI watches files the
existing CLI already writes and renders them. No mutations.

Entry point: `python -m speckit_orca.tui`. See `specs/018-orca-tui/`.
"""

from __future__ import annotations

from speckit_orca.tui.app import OrcaTUI, main

__all__ = ["OrcaTUI", "main"]
