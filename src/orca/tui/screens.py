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

        columns = []
        for col in KanbanColumn:
            vs = VerticalScroll(
                classes="board-column",
                id=f"col-{col.name.lower()}",
            )
            # Columns are layout containers, not focus targets. Without
            # this the VerticalScroll absorbs Tab + arrow-key focus
            # before it can reach the inner FeatureCard widgets, leaving
            # the c/o/e action keybindings unreachable from the keyboard.
            vs.can_focus = False
            columns.append(vs)
        yield Horizontal(*columns, id="board-row")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_board()

    def refresh_board(self) -> None:
        """Repopulate every column from the kanban collector.

        Preserves the focused feature_id across rebuild so the watcher
        firing during navigation doesn't yank the operator back to the
        first card.
        """
        try:
            data = collect_kanban(self.app.repo_root)
        except Exception:  # noqa: BLE001
            logger.debug("collect_kanban failed", exc_info=True)
            return

        focused_feature_id: str | None = None
        try:
            f = self.app.focused
            if isinstance(f, FeatureCard):
                focused_feature_id = f.data.feature_id
        except Exception:  # noqa: BLE001
            pass

        new_focus_target: FeatureCard | None = None
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
                w = FeatureCard(cd)
                container.mount(w)
                if focused_feature_id and cd.feature_id == focused_feature_id:
                    new_focus_target = w
        if new_focus_target is not None:
            try:
                new_focus_target.focus()
            except Exception:  # noqa: BLE001
                logger.debug("re-focus after refresh failed", exc_info=True)
