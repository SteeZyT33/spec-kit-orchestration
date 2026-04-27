"""Textual Widget subclasses for the Orca TUI panes.

Each pane is a thin wrapper around a Textual `DataTable` (or `RichLog`
for the event feed). Panes receive plain-data rows from collectors and
populate their table - no direct filesystem access from widgets.
"""

from __future__ import annotations

from textual.containers import Container
from textual.widgets import DataTable, RichLog

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
    """Right: live event feed (no sources after v1 strip)."""

    DEFAULT_CSS = """
    EventFeedPane { border: round $accent; }
    """

    def compose(self):  # type: ignore[override]
        yield RichLog(id="event-log", highlight=True, markup=False, max_lines=200)

    def update_rows(self, entries: list[EventFeedEntry]) -> None:
        log = self.query_one("#event-log", RichLog)
        log.clear()
        if not entries:
            log.write("- no events yet -")
            return
        # entries are sorted desc; render newest at bottom for tail-readability
        for e in reversed(entries):
            log.write(f"{e.timestamp} [{e.source}] {e.summary}")
