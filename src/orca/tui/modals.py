"""Confirm/Result/NewLane/Doctor modals.

ConfirmModal: 'y' returns True, 'n'/'esc' returns False.
ResultModal: shows a body; 'esc'/'enter' closes.
NewLaneModal: prompts for feature_id + agent; submit returns dict or None.
DoctorModal: result-shaped wrapper for `orca-cli wt doctor` output.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class ConfirmModal(ModalScreen[bool]):
    BINDINGS = [
        ("y", "yes", ""),
        ("n", "no", ""),
        ("escape", "no", ""),
    ]

    def __init__(self, prompt: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.prompt = prompt

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Vertical(
            Label(self.prompt),
            Static("[y]es / [n]o", classes="label"),
            id="dialog",
        )

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class ResultModal(ModalScreen[None]):
    BINDINGS = [
        ("escape", "close", ""),
        ("enter", "close", ""),
    ]

    def __init__(self, *, title: str, body: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.title_text = title
        self.body_text = body

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Vertical(
            Label(self.title_text),
            Static(self.body_text or "(no output)"),
            Static("[esc/enter] close", classes="label"),
            id="dialog",
        )

    def action_close(self) -> None:
        self.dismiss(None)


class NewLaneModal(ModalScreen[dict | None]):
    BINDINGS = [
        ("escape", "cancel", ""),
    ]

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield Vertical(
            Label("New lane"),
            Input(placeholder="feature_id (e.g. tui-v4)", id="feat"),
            Input(placeholder="agent (claude/codex/none)", id="agent",
                  value="claude"),
            Button("Create", id="ok"),
            Static("[esc] cancel", classes="label"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            feat = self.query_one("#feat", Input).value.strip()
            agent = self.query_one("#agent", Input).value.strip() or "claude"
            if not feat:
                return
            self.dismiss({"feature": feat, "agent": agent})

    def action_cancel(self) -> None:
        self.dismiss(None)


# DoctorModal is just ResultModal aliased — no extra UI needed.
DoctorModal = ResultModal
