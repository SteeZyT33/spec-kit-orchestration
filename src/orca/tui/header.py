"""TUI header: orca logo + repo/branch/polling status side-by-side.

The logo is the canonical 6-row ASCII art from `orca.banner_anim`
(`FINAL_ART`), rendered statically. The right side shows repo,
branch, and polling-mode status. Read-only, recomputed only when
the host calls `update_status`.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from orca.banner_anim import FINAL_ART

LOGO_TEXT = "\n".join(FINAL_ART)


class LogoHeader(Horizontal):
    """Two-column header: logo on the left, status block on the right."""

    DEFAULT_CSS = """
    LogoHeader {
        height: 6;
        dock: top;
        background: $surface;
        color: $text;
    }
    LogoHeader > #orca-logo {
        width: 28;
        content-align: left top;
        color: $accent;
        padding: 0 1;
    }
    LogoHeader > #orca-status {
        width: 1fr;
        content-align: left top;
        padding: 0 1;
    }
    """

    def __init__(self, status_text: str = "", *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._status_text = status_text

    def compose(self) -> ComposeResult:
        yield Static(LOGO_TEXT, id="orca-logo")
        yield Static(self._status_text, id="orca-status")

    def update_status(self, status_text: str) -> None:
        self._status_text = status_text
        try:
            self.query_one("#orca-status", Static).update(status_text)
        except Exception:  # noqa: BLE001
            pass
