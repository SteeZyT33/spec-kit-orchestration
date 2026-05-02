"""Textual Widget subclasses for the Orca TUI panes.

Each pane is a thin wrapper around a Textual `DataTable`. Panes receive
plain-data rows from collectors and populate their table - no direct
filesystem access from widgets.
"""

from __future__ import annotations

from rich.text import Text
from textual.containers import Container
from textual.widgets import DataTable

from orca.tui.adoption import AdoptionRow, render_rows as adoption_render_rows
from orca.tui.collectors import (
    EventFeedEntry,
    ReviewRow,
)
from orca.tui.timefmt import format_age


# Severity-based color hints, picked from the standard ANSI palette so
# they degrade gracefully across themes. Goal: "scan and spot blockers
# in one glance" - no rainbow, just red/yellow/green/dim.
_REVIEW_STATUS_STYLES: dict[str, str] = {
    "missing": "red",
    "blocked": "red bold",
    "stale": "red",
    "needs-revision": "yellow",
    "in_progress": "yellow",
    "phases_partial": "yellow",
    "not_started": "dim",
    "complete": "green",
    "overall_complete": "green",
    "present": "green",
}

_EVENT_SOURCE_STYLES: dict[str, str] = {
    "git": "cyan",
    "review": "green",
}


def _styled(value: str, styles: dict[str, str]) -> Text:
    """Wrap a cell value in Rich Text with a severity-keyed style."""
    return Text(value, style=styles.get(value, ""))


def _adoption_value_styled(value: str) -> Text:
    """Color the adoption applied/status row by leading-keyword severity.

    Reads only the first token so changes to the suffix (file count,
    timestamp, hint text) don't break the styling.
    """
    head = value.split(" ", 1)[0].lower()
    if head.startswith("yes"):
        return Text(value, style="green")
    if head in {"manifest"} or value.startswith("manifest only"):
        return Text(value, style="yellow")
    if head in {"not"} or value.startswith("not adopted"):
        return Text(value, style="red")
    return Text(value)


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
        prev_cursor = table.cursor_row if table.row_count else 0
        table.clear()
        # Border title carries an at-a-glance count so the operator
        # doesn't have to scroll the table to assess load.
        if rows:
            self.border_title = f"reviews · {len(rows)} pending"
        else:
            self.border_title = "reviews · clear"
        if not rows:
            table.add_row("-", "-", Text("no pending reviews", style="dim green"))
            return
        for r in rows:
            table.add_row(
                r.feature_id,
                self._short_review_kind(r.review_type),
                _styled(r.status, _REVIEW_STATUS_STYLES),
            )
        # Restore cursor to its prior row if it still exists.
        if 0 <= prev_cursor < len(rows):
            try:
                table.move_cursor(row=prev_cursor)
            except Exception:  # noqa: BLE001
                pass

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
        prev_cursor = table.cursor_row if table.row_count else 0
        table.clear()
        if entries:
            self.border_title = f"events · {len(entries)}"
        else:
            self.border_title = "events"
        if not entries:
            table.add_row("-", "-", Text("no events yet", style="dim"))
            return
        # entries are sorted desc; render newest first. The 'when' column
        # uses a compact relative-age string so the summary column has
        # room to breathe on 80-col terminals.
        for e in entries:
            table.add_row(
                format_age(e.timestamp),
                _styled(e.source, _EVENT_SOURCE_STYLES),
                e.summary,
            )
        if 0 <= prev_cursor < len(entries):
            try:
                table.move_cursor(row=prev_cursor)
            except Exception:  # noqa: BLE001
                pass

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
        prev_cursor = table.cursor_row if table.row_count else 0
        table.clear()
        if not rows:
            table.add_row("-", Text("no adoption manifest", style="red"))
            self.border_title = "adoption"
            return
        host = next((r.value for r in rows if r.label == "host"), "")
        if host and host != "(unset)":
            self.border_title = f"adoption · {host}"
        else:
            self.border_title = "adoption"
        for r in rows:
            value: object = r.value
            if r.label in {"applied", "status"}:
                value = _adoption_value_styled(r.value)
            table.add_row(r.label, value)
        if 0 <= prev_cursor < len(rows):
            try:
                table.move_cursor(row=prev_cursor)
            except Exception:  # noqa: BLE001
                pass

    def update_from_info(self, info) -> None:
        """Convenience: build rows from an AdoptionInfo and apply them."""
        self.update_rows(adoption_render_rows(info))
