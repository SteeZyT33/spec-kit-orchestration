"""Textual Widget subclasses for the Orca TUI panes.

Each pane is a thin wrapper around a Textual `DataTable`. Panes receive
plain-data rows from collectors and populate their table - no direct
filesystem access from widgets.
"""

from __future__ import annotations

from textual.containers import Container
from textual.widgets import DataTable

from orca.tui.adoption import AdoptionRow, render_rows as adoption_render_rows
from orca.tui.collectors import (
    EventFeedEntry,
    ReviewRow,
)


class ReviewPane(Container):
    """Left: pending reviews across all features."""

    DEFAULT_CSS = """
    ReviewPane { border: round $accent; }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_rows: list[ReviewRow] = []

    def compose(self):  # type: ignore[override]
        table = DataTable(id="review-table")
        table.cursor_type = "row"
        table.add_columns("feature", "review", "status")
        yield table

    def update_rows(self, rows: list[ReviewRow]) -> None:
        self._last_rows = list(rows)
        table = self.query_one("#review-table", DataTable)
        table.clear()
        if not rows:
            table.add_row("-", "-", "no pending reviews")
            return
        for r in rows:
            table.add_row(r.feature_id, r.review_type, r.status)

    def row_at_cursor(self) -> ReviewRow | None:
        if not self._last_rows:
            return None
        try:
            idx = self.query_one("#review-table", DataTable).cursor_row
        except Exception:  # noqa: BLE001
            return None
        if idx is None or idx < 0 or idx >= len(self._last_rows):
            return None
        return self._last_rows[idx]


class EventFeedPane(Container):
    """Right: live event feed (review-artifact writes + recent commits)."""

    DEFAULT_CSS = """
    EventFeedPane { border: round $accent; }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_entries: list[EventFeedEntry] = []

    def compose(self):  # type: ignore[override]
        # DataTable so rows are selectable and Enter can trigger drilldown.
        # The id stays #event-log for keybinding compatibility with v1.
        table = DataTable(id="event-log")
        table.cursor_type = "row"
        table.add_columns("when", "src", "summary")
        yield table

    def update_rows(self, entries: list[EventFeedEntry]) -> None:
        self._last_entries = list(entries)
        table = self.query_one("#event-log", DataTable)
        table.clear()
        if not entries:
            table.add_row("-", "-", "no events yet")
            return
        # entries are sorted desc; render newest first.
        for e in entries:
            table.add_row(e.timestamp, e.source, e.summary)

    def row_at_cursor(self) -> EventFeedEntry | None:
        if not self._last_entries:
            return None
        try:
            idx = self.query_one("#event-log", DataTable).cursor_row
        except Exception:  # noqa: BLE001
            return None
        if idx is None or idx < 0 or idx >= len(self._last_entries):
            return None
        return self._last_entries[idx]


class AdoptionPane(Container):
    """Bottom: orca adoption state for this repo (key/value summary)."""

    DEFAULT_CSS = """
    AdoptionPane { border: round $accent; height: auto; min-height: 7; }
    """

    def compose(self):  # type: ignore[override]
        table = DataTable(id="adoption-table", show_header=False)
        table.cursor_type = "row"
        table.add_columns("key", "value")
        yield table

    def update_rows(self, rows: list[AdoptionRow]) -> None:
        table = self.query_one("#adoption-table", DataTable)
        table.clear()
        if not rows:
            table.add_row("-", "no adoption manifest")
            return
        for r in rows:
            table.add_row(r.label, r.value)

    def update_from_info(self, info) -> None:
        """Convenience: build rows from an AdoptionInfo and apply them."""
        self.update_rows(adoption_render_rows(info))
