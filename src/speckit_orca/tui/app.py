"""OrcaTUI - Textual App subclass and CLI entry point.

Phase 1 scope (spec 018-orca-tui):

- Read-only projection of lane / yolo / review / event-feed state.
- 4-pane grid layout with header + footer.
- Keybindings: q (quit), r (refresh), 1-4 (focus pane).
- Watchdog-preferred file watcher with 5s polling fallback.

Entry point: `python -m speckit_orca.tui`.
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

from speckit_orca.tui.collectors import CollectorResult, collect_all
from speckit_orca.tui.panes import EventFeedPane, LanePane, ReviewPane, YoloPane
from speckit_orca.tui.watcher import Watcher

logger = logging.getLogger(__name__)


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
    """Textual app hosting the 4-pane read-only Orca view."""

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
        grid-size: 2 2;
        grid-gutter: 1 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "quit", show=True),
        Binding("r", "refresh", "refresh", show=True),
        Binding("1", "focus_pane('lane-pane')", "lanes", show=True),
        Binding("2", "focus_pane('yolo-pane')", "yolo", show=True),
        Binding("3", "focus_pane('review-pane')", "reviews", show=True),
        Binding("4", "focus_pane('event-pane')", "events", show=True),
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

    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static(self.render_header_text(), id="tui-header")
        yield Grid(
            LanePane(id="lane-pane"),
            YoloPane(id="yolo-pane"),
            ReviewPane(id="review-pane"),
            EventFeedPane(id="event-pane"),
            id="tui-grid",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._start_watcher()
        self._do_refresh()

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
        # not zero out the remaining three panes. During early mount the
        # widgets may not yet be queryable; later refreshes catch up.
        for pane_id, widget_cls, rows in (
            ("#lane-pane", LanePane, result.lanes),
            ("#yolo-pane", YoloPane, result.yolo_runs),
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

    def action_focus_pane(self, pane_id: str) -> None:
        try:
            self.query_one(f"#{pane_id}").focus()
        except Exception:  # noqa: BLE001
            logger.debug("Failed to focus pane '%s'", pane_id, exc_info=True)


# ---------------------------------------------------------------------------
# CLI entry point


def _positive_float(value: str) -> float:
    v = float(value)
    if v <= 0:
        raise argparse.ArgumentTypeError("--poll-interval must be > 0")
    return v


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m speckit_orca.tui",
        description="Orca TUI - read-only 4-pane view of lane / yolo / review state.",
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
