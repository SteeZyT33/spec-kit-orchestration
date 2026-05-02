"""Screen subclasses for orca TUI v2.

The default screen IS the v1.2 list view (panes mounted directly on
App). BoardScreen overlays the list view as a separately-pushed
screen when the operator presses `b`. This keeps `app.query_one`
working against the panes (they live on the default screen).
"""
from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer

from orca.tui.cards import FeatureCard
from orca.tui.header import LogoHeader
from orca.tui.kanban import KanbanColumn, collect_kanban

logger = logging.getLogger(__name__)


class BoardScreen(Screen):
    """Kanban view: 5 columns of FeatureCard widgets."""

    DEFAULT_CSS = """
    BoardScreen { layout: vertical; }
    #board-row {
        layout: horizontal;
        height: 1fr;
    }
    .board-column {
        width: 1fr;
        border: round $accent;
        padding: 0 1;
        margin: 0 1 0 0;
    }
    """

    def compose(self) -> ComposeResult:
        # Carry the same logo header and footer that the default screen
        # mounts, so the operator sees a consistent chrome on toggle.
        yield LogoHeader(self.app.render_header_text(), id="board-header")
        yield Horizontal(
            *[
                VerticalScroll(
                    classes="board-column",
                    id=f"col-{col.name.lower()}",
                )
                for col in KanbanColumn
            ],
            id="board-row",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_board()

    def refresh_board(self) -> None:
        """Repopulate every column from the kanban collector."""
        try:
            data = collect_kanban(self.app.repo_root)
        except Exception:  # noqa: BLE001
            logger.debug("collect_kanban failed", exc_info=True)
            return
        for col in KanbanColumn:
            cards = data[col]
            try:
                container = self.query_one(
                    f"#col-{col.name.lower()}", VerticalScroll,
                )
            except Exception:  # noqa: BLE001
                continue
            container.border_title = f"{col.value} · {len(cards)}"
            container.remove_children()
            for cd in cards:
                container.mount(FeatureCard(cd))
