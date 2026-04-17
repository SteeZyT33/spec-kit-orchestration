"""Textual Widget subclasses for the four Orca TUI panes.

Each pane is a thin wrapper around a Textual `DataTable` (or `RichLog`
for the event feed). Panes receive plain-data rows from collectors and
populate their table - no direct filesystem access from widgets.
"""

from __future__ import annotations

from textual.containers import Container
from textual.widgets import DataTable, RichLog

from speckit_orca.tui.collectors import (
    EventFeedEntry,
    LaneRow,
    ReviewRow,
    YoloRow,
)


class LanePane(Container):
    """Top-left: lane roster."""

    DEFAULT_CSS = """
    LanePane { border: round $accent; }
    """

    def compose(self):  # type: ignore[override]
        table = DataTable(id="lane-table")
        table.cursor_type = "row"
        table.add_columns("lane", "state", "owner", "reason")
        yield table

    def update_rows(self, rows: list[LaneRow]) -> None:
        table = self.query_one("#lane-table", DataTable)
        table.clear()
        if not rows:
            table.add_row("-", "-", "-", "no lanes registered")
            return
        for r in rows:
            table.add_row(
                r.lane_id,
                r.effective_state,
                r.owner_id or "-",
                (r.status_reason or "")[:60],
            )


class YoloPane(Container):
    """Top-right: active yolo runs."""

    DEFAULT_CSS = """
    YoloPane { border: round $accent; }
    """

    def compose(self):  # type: ignore[override]
        table = DataTable(id="yolo-table")
        table.cursor_type = "row"
        table.add_columns("run", "feat", "stage", "outcome", "sync")
        yield table

    def update_rows(self, rows: list[YoloRow]) -> None:
        table = self.query_one("#yolo-table", DataTable)
        table.clear()
        if not rows:
            table.add_row("-", "-", "-", "-", "no active runs")
            return
        for r in rows:
            table.add_row(
                r.run_id[:8],
                r.feature_id,
                r.current_stage,
                r.outcome,
                "FAIL" if r.matriarch_sync_failed else "ok",
            )


class ReviewPane(Container):
    """Bottom-left: pending reviews across all features."""

    DEFAULT_CSS = """
    ReviewPane { border: round $accent; }
    """

    def compose(self):  # type: ignore[override]
        table = DataTable(id="review-table")
        table.cursor_type = "row"
        table.add_columns("feature", "review", "status")
        yield table

    def update_rows(self, rows: list[ReviewRow]) -> None:
        table = self.query_one("#review-table", DataTable)
        table.clear()
        if not rows:
            table.add_row("-", "-", "no pending reviews")
            return
        for r in rows:
            table.add_row(r.feature_id, r.review_type, r.status)


class EventFeedPane(Container):
    """Bottom-right: live event feed from yolo + matriarch."""

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
