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
from orca.tui.timefmt import format_age


class ReviewPane(Container):
    """Left: pending reviews across all features."""

    DEFAULT_CSS = """
    ReviewPane { border: round $accent; }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "reviews"
        self._last_rows: list[ReviewRow] = []

    def compose(self):  # type: ignore[override]
        table = DataTable(id="review-table")
        table.cursor_type = "row"
        # Cap columns so all three fit at 80-col split-pane (inner ~36).
        # Feature col gets 18 (ellipsizes long names); review type is
        # rendered without the redundant 'review-' prefix so 4 chars
        # cover spec/code/pr; status gets 13 to fit 'not_started'.
        table.add_column("feature", width=14)
        table.add_column("kind", width=4)
        table.add_column("status", width=11)
        yield table

    @staticmethod
    def _short_review_kind(review_type: str) -> str:
        """Strip the 'review-' prefix so spec/code/pr stay 4-char."""
        if review_type.startswith("review-"):
            return review_type[len("review-"):]
        return review_type

    def update_rows(self, rows: list[ReviewRow]) -> None:
        self._last_rows = list(rows)
        table = self.query_one("#review-table", DataTable)
        table.clear()
        if not rows:
            table.add_row("-", "-", "no pending reviews")
            return
        for r in rows:
            table.add_row(
                r.feature_id,
                self._short_review_kind(r.review_type),
                r.status,
            )

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
        self.border_title = "events"
        self._last_entries: list[EventFeedEntry] = []

    def compose(self):  # type: ignore[override]
        # DataTable so rows are selectable and Enter can trigger drilldown.
        # The id stays #event-log for keybinding compatibility with v1.
        table = DataTable(id="event-log")
        table.cursor_type = "row"
        # Width caps free the summary column to grow with the pane.
        table.add_column("when", width=6)
        table.add_column("src", width=6)
        table.add_column("summary")
        yield table

    def update_rows(self, entries: list[EventFeedEntry]) -> None:
        self._last_entries = list(entries)
        table = self.query_one("#event-log", DataTable)
        table.clear()
        if not entries:
            table.add_row("-", "-", "no events yet")
            return
        # entries are sorted desc; render newest first. The 'when' column
        # uses a compact relative-age string so the summary column has
        # room to breathe on 80-col terminals.
        for e in entries:
            table.add_row(format_age(e.timestamp), e.source, e.summary)

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.border_title = "adoption"

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
