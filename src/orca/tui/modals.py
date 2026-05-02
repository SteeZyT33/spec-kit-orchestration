"""Modal screens for confirm + result display."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class ConfirmModal(ModalScreen[bool]):
    """Yes/no confirm. Default-no: Enter / N / Esc all cancel."""

    DEFAULT_CSS = """
    ConfirmModal { align: center middle; }
    ConfirmModal > Vertical {
        width: 60%;
        max-width: 80;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    BINDINGS = [
        Binding("y", "confirm", "yes", show=True),
        Binding("n", "cancel", "no", show=True),
        Binding("escape", "cancel", "cancel", show=True),
        Binding("enter", "cancel", "cancel", show=True),
    ]

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self.prompt),
            Static("\n[bold]y[/bold] confirm   [bold]n / Esc / Enter[/bold] cancel"),
        )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class ResultModal(ModalScreen[None]):
    """Shows a captured stdout/stderr block. Esc / Enter close."""

    DEFAULT_CSS = """
    ResultModal { align: center middle; }
    ResultModal > Vertical {
        width: 80%;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
        overflow: auto;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "close", show=True),
        Binding("enter", "close", "close", show=True),
    ]

    def __init__(self, title: str, body: str) -> None:
        super().__init__()
        self.title_text = title
        self.body_text = body

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(f"[bold]{self.title_text}[/bold]"),
            Static(self.body_text or "(empty)"),
        )

    def action_close(self) -> None:
        self.dismiss()
