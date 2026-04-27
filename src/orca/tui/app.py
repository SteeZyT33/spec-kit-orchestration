"""OrcaTUI - Textual App subclass and CLI entry point.

Phase 1 scope (spec 018-orca-tui):

- Read-only projection of review / event-feed state.
- Multi-pane grid layout with header + footer.
- Keybindings: q (quit), r (refresh), 1-2 (focus pane).
- Watchdog-preferred file watcher with 5s polling fallback.

Entry point: `python -m orca.tui`.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.reactive import reactive
from textual.widgets import Footer, Static

from orca.tui.collectors import CollectorResult, collect_all
from orca.tui.drawer import (
    DetailDrawer,
    DrawerContent,
    build_review_drawer,
)
from orca.tui.panes import EventFeedPane, ReviewPane
from orca.tui.watcher import Watcher

logger = logging.getLogger(__name__)


# v1.1: built-in Textual themes the `t` keybinding cycles through. Any
# theme name not present in `app.available_themes` at mount time is
# dropped from the cycle (graceful degradation across Textual versions).
CONFIGURED_THEMES: list[str] = [
    "textual-dark",
    "textual-light",
    "monokai",
    "dracula",
]


def _git_branch(repo_root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2.0,
        )
        return completed.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.debug("git branch probe timed out for %s", repo_root)
        return None
    except Exception:  # noqa: BLE001
        return None


class OrcaTUI(App):
    """Textual app hosting the multi-pane read-only Orca view."""

    CSS = """
    Screen { layout: vertical; }
    #tui-header {
        dock: top;
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
    }
    #tui-grid {
        grid-size: 2 1;
        grid-gutter: 1 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "quit", show=True),
        Binding("r", "refresh", "refresh", show=True),
        Binding("1", "focus_pane('review-pane')", "reviews", show=True),
        Binding("2", "focus_pane('event-pane')", "events", show=True),
        # v1.1 additions. `enter` is marked priority so it beats
        # DataTable's default `select_cursor` binding - otherwise pressing
        # Enter on a row would fire the table's row-select and never
        # reach the app's drawer action.
        Binding("enter", "open_drawer", "drill", show=True, priority=True),
        Binding("t", "cycle_theme", "theme", show=True),
    ]

    polling_mode: reactive[bool] = reactive(False)

    def __init__(
        self,
        repo_root: Path,
        *,
        poll_interval: float = 5.0,
        force_polling_mode: bool = False,
    ) -> None:
        super().__init__()
        self.repo_root = Path(repo_root)
        self.poll_interval = poll_interval
        self._force_polling_mode = force_polling_mode
        self._watcher: Watcher | None = None
        # v1.1: theme cycle state - populated on mount once we know what
        # `available_themes` resolves to in the running Textual version.
        self._theme_cycle: list[str] = []
        self._theme_index: int = 0
        # v1.1: pane id that originated the currently-open drawer so we
        # can restore focus to the same pane after Escape / Enter close.
        self._drawer_origin_pane_id: str | None = None

    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(self.render_header_text(), id="tui-header")
        yield Grid(
            ReviewPane(id="review-pane"),
            EventFeedPane(id="event-pane"),
            id="tui-grid",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._init_theme_cycle()
        self._start_watcher()
        self._do_refresh()

    # ------------------------------------------------------------------
    # v1.1: theme cycle helpers

    def _init_theme_cycle(self) -> None:
        """Filter CONFIGURED_THEMES against Textual's available_themes.

        Themes missing from the running Textual version are dropped and
        logged at debug level. If nothing remains, the cycle collapses
        to the current app.theme so `t` is a no-op rather than a crash.
        """
        try:
            available = set(self.available_themes.keys())
        except Exception:  # noqa: BLE001
            logger.debug("app.available_themes unreadable", exc_info=True)
            available = set()
        cycle = [name for name in CONFIGURED_THEMES if name in available]
        if not cycle:
            cycle = [self.theme] if getattr(self, "theme", None) else []
        self._theme_cycle = cycle
        # Align the index with the current theme if it's in the cycle.
        try:
            current = self.theme
        except Exception:  # noqa: BLE001
            current = None
        if current in cycle:
            self._theme_index = cycle.index(current)
        else:
            self._theme_index = 0

    def on_unmount(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None

    # ------------------------------------------------------------------

    def render_header_text(self) -> str:
        branch = _git_branch(self.repo_root) or "?"
        base = f"orca-tui  repo={self.repo_root.name}  branch={branch}"
        if self.polling_mode:
            base += "   [polling mode (watchdog unavailable)]"
        return base

    def _refresh_header(self) -> None:
        try:
            hdr = self.query_one("#tui-header", Static)
            hdr.update(self.render_header_text())
        except Exception:  # noqa: BLE001
            logger.debug("Failed to refresh header widget", exc_info=True)

    # ------------------------------------------------------------------

    def _start_watcher(self) -> None:
        def _on_change(_path):
            # Schedule refresh on the Textual thread.
            try:
                self.call_from_thread(self._do_refresh)
            except Exception:  # noqa: BLE001
                logger.debug(
                    "Failed to schedule UI refresh from watcher thread",
                    exc_info=True,
                )

        self._watcher = Watcher(
            self.repo_root,
            on_change=_on_change,
            poll_interval=self.poll_interval,
            force_polling=self._force_polling_mode,
        )
        self.polling_mode = self._watcher.polling_mode
        self._refresh_header()

    def _do_refresh(self) -> None:
        result: CollectorResult = collect_all(self.repo_root, polling_mode=self.polling_mode)
        # One try per pane so a single widget lookup / update failure does
        # not zero out the remaining panes. During early mount the
        # widgets may not yet be queryable; later refreshes catch up.
        for pane_id, widget_cls, rows in (
            ("#review-pane", ReviewPane, result.reviews),
            ("#event-pane", EventFeedPane, result.event_feed),
        ):
            try:
                self.query_one(pane_id, widget_cls).update_rows(rows)
            except Exception:  # noqa: BLE001
                logger.debug(
                    "Refresh failed for pane %s", pane_id, exc_info=True
                )

    # ------------------------------------------------------------------
    # Actions

    def action_refresh(self) -> None:
        self._do_refresh()

    # Pane container ids are not focusable; map to the focusable child widget id.
    _PANE_FOCUS_TARGETS = {
        "review-pane": "#review-table",
        "event-pane": "#event-log",
    }

    def action_focus_pane(self, pane_id: str) -> None:
        target = self._PANE_FOCUS_TARGETS.get(pane_id, f"#{pane_id}")
        try:
            self.query_one(target).focus()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to focus pane '%s' via target %s", pane_id, target, exc_info=True)

    # ------------------------------------------------------------------
    # v1.1 actions

    def _find_focused_pane(self):
        """Return the currently focused review pane container with a
        row_at_cursor() method, or None.
        """
        for pane_id, cls in (("#review-pane", ReviewPane),):
            try:
                pane = self.query_one(pane_id, cls)
            except Exception:  # noqa: BLE001
                continue
            # Pane is "focused" if focus is on the pane itself or one of
            # its descendants (the DataTable inside).
            try:
                focused = self.focused
            except Exception:  # noqa: BLE001
                focused = None
            if focused is None:
                continue
            node = focused
            while node is not None:
                if node is pane:
                    return (pane_id, pane)
                node = getattr(node, "parent", None)
        return None

    def _build_drawer_for(self, pane_id: str, pane) -> DrawerContent | None:
        try:
            row = pane.row_at_cursor()
        except Exception:  # noqa: BLE001
            logger.debug("row_at_cursor failed for %s", pane_id, exc_info=True)
            return None
        if row is None:
            return None
        try:
            if pane_id == "#review-pane":
                return build_review_drawer(self.repo_root, row)
        except Exception:  # noqa: BLE001
            logger.debug("drawer builder failed for %s", pane_id, exc_info=True)
            return None
        return None

    def action_open_drawer(self) -> None:
        """Enter: open a detail drawer for the focused pane's cursor row.

        No-op when the event-feed pane is focused, when no pane is
        focused, or when the focused pane has no row under the cursor.
        """
        # If a drawer is already open, treat Enter as close (toggle).
        if isinstance(self.screen, DetailDrawer):
            self._close_drawer()
            return

        match = self._find_focused_pane()
        if match is None:
            return  # event pane or nothing focused => no-op
        pane_id, pane = match
        content = self._build_drawer_for(pane_id, pane)
        if content is None:
            return
        self._drawer_origin_pane_id = pane_id
        try:
            self.push_screen(DetailDrawer(content))
        except Exception:  # noqa: BLE001
            logger.debug("Failed to push DetailDrawer", exc_info=True)
            self._drawer_origin_pane_id = None

    def _close_drawer(self) -> None:
        """Pop the drawer screen and restore focus to the originating pane.

        Focus restoration is explicit rather than relying on Textual's
        default restore-last-focus behavior, so the pane the operator
        drilled into stays focused after Escape / Enter.
        """
        origin = self._drawer_origin_pane_id
        self._drawer_origin_pane_id = None
        try:
            self.pop_screen()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to pop drawer", exc_info=True)
            return
        if origin is None:
            return
        # origin is "#review-pane"; map back to its focusable child.
        target = self._PANE_FOCUS_TARGETS.get(origin.lstrip("#"), origin)
        try:
            self.query_one(target).focus()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to restore focus to %s (via %s)", origin, target, exc_info=True)

    def action_cycle_theme(self) -> None:
        """Advance the theme cycle one step, wrapping around the end.

        Index advancement only commits after a successful theme
        application, so a runtime theme-setter failure does not leave
        the internal cursor out of sync with the visible theme (would
        otherwise cause the next `t` press to skip an entry).
        """
        if not self._theme_cycle:
            return
        next_index = (self._theme_index + 1) % len(self._theme_cycle)
        target = self._theme_cycle[next_index]
        try:
            self.theme = target
        except Exception:  # noqa: BLE001
            logger.debug("Failed to apply theme %s", target, exc_info=True)
            return
        self._theme_index = next_index


# ---------------------------------------------------------------------------
# CLI entry point


def _positive_float(value: str) -> float:
    v = float(value)
    if v <= 0:
        raise argparse.ArgumentTypeError("--poll-interval must be > 0")
    return v


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m orca.tui",
        description="Orca TUI - read-only multi-pane view of review state.",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (defaults to current working directory).",
    )
    p.add_argument(
        "--poll-interval",
        type=_positive_float,
        default=5.0,
        help="Polling-mode refresh interval in seconds (default: 5.0).",
    )
    p.add_argument(
        "--force-polling",
        action="store_true",
        help="Force polling mode even if watchdog is importable.",
    )
    p.add_argument(
        "--no-run",
        action="store_true",
        help="Parse flags and construct the app, but do not enter the UI loop (test hook).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root or Path.cwd()
    app = OrcaTUI(
        repo_root=repo_root,
        poll_interval=args.poll_interval,
        force_polling_mode=args.force_polling,
    )
    if args.no_run:
        return 0
    app.run()
    return 0
