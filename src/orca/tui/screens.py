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
from textual.widgets import Footer, Static

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
        padding: 1 1 0 1;
    }
    .board-column {
        width: 1fr;
        border: round $surface-lighten-1;
        padding: 1;
        margin: 0 1 0 0;
        background: $background;
    }
    .board-column:last-of-type { margin: 0; }
    .board-column:focus-within {
        border: round $accent;
    }
    .board-empty {
        color: $text-muted;
        height: 1;
        padding: 0 1;
    }
    .board-narrow-warning {
        display: none;
        color: $warning;
        height: 1fr;
        content-align: center middle;
    }
    """

    BOARD_MIN_WIDTH = 100

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
        yield Static(
            f"  Terminal too narrow for the board view "
            f"(need at least {self.BOARD_MIN_WIDTH} cols, resize or "
            "press b to return).",
            id="board-narrow-warning",
            classes="board-narrow-warning",
        )
        yield Footer()

    _last_signature: tuple = ()

    def on_mount(self) -> None:
        self._apply_width_mode()
        self.refresh_board()

    def on_resize(self, _event) -> None:
        self._apply_width_mode()

    def _apply_width_mode(self) -> None:
        """Hide the kanban grid (and show the narrow warning) when the
        terminal is too narrow for 5 columns to be readable."""
        try:
            w = self.size.width
        except Exception:  # noqa: BLE001
            return
        narrow = w < self.BOARD_MIN_WIDTH
        try:
            row = self.query_one("#board-row", Horizontal)
            warn = self.query_one("#board-narrow-warning", Static)
            row.display = not narrow
            warn.display = narrow
        except Exception:  # noqa: BLE001
            pass

    def refresh_board(self) -> None:
        """Repopulate every column from the kanban collector.

        Skips the rebuild when input is identical (kills flicker from
        watcher fires that don't change real data). Preserves the
        focused feature_id across rebuild so an actual change doesn't
        yank the operator back to the first card.
        """
        try:
            data = collect_kanban(self.app.repo_root)
        except Exception:  # noqa: BLE001
            logger.debug("collect_kanban failed", exc_info=True)
            return

        # Cheap signature: per-column, ordered tuples of card data.
        sig = tuple(
            (col, tuple((c.feature_id, c.column.value, c.branch,
                         c.worktree_status) for c in data[col]))
            for col in KanbanColumn
        )
        if sig == self._last_signature:
            return
        self._last_signature = sig

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
            if not cards:
                container.mount(Static("(empty)", classes="board-empty"))
                continue
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
