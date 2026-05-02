"""FeatureCard - 4-line block widget for the kanban board.

Each card is a focusable Static. Read-only content; the c/o/e
keybindings (close worktree / shell / editor) are added in Phase 2.
"""
from __future__ import annotations

import logging
from pathlib import Path

from rich.text import Text
from textual.binding import Binding
from textual.widgets import Static

from orca.tui.kanban import CardData

logger = logging.getLogger(__name__)


class FeatureCard(Static, can_focus=True):
    """4-line focusable card."""

    DEFAULT_CSS = """
    FeatureCard {
        height: 5;
        border: round $surface;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    FeatureCard:focus {
        border: round $accent;
    }
    """

    BINDINGS = [
        Binding("c", "close_worktree", "close", show=True),
        Binding("o", "open_shell", "shell", show=True),
        Binding("e", "open_editor", "edit", show=True),
    ]

    def __init__(self, data: CardData, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.data = data

    def on_mount(self) -> None:
        # When the app declares read_only, suppress the mutating
        # keybindings so the footer doesn't advertise actions that
        # would no-op.
        if getattr(self.app, "read_only", False):
            try:
                # Best-effort removal across Textual API variants.
                self._bindings.key_to_bindings = {
                    k: v for k, v in self._bindings.key_to_bindings.items()
                    if k not in {"c", "o", "e"}
                }
            except Exception:  # noqa: BLE001
                pass

    def _content_lines(self) -> list[str]:
        d = self.data
        line1 = d.feature_id
        line2 = f"branch:   {d.branch or '(no worktree)'}"
        line3 = f"worktree: {d.worktree_status}"
        line4 = f"reviews:  {d.review_summary or '-'}"
        return [line1, line2, line3, line4]

    def render(self):  # type: ignore[override]
        return Text("\n".join(self._content_lines()))

    # ------------------------------------------------------------------
    # Phase 2 actions

    def action_close_worktree(self) -> None:
        from orca.tui.actions import close_worktree
        from orca.tui.modals import ConfirmModal, ResultModal

        if not self.data.worktree_path:
            return
        prompt = (
            f"Close worktree {self.data.branch}?\n"
            "This deletes the worktree directory and removes the registration."
        )

        def on_answer(answer: bool | None) -> None:
            if not answer:
                return
            result = close_worktree(
                self.app.repo_root,
                self.data.branch or self.data.feature_id,
            )
            self.app.push_screen(ResultModal(
                title=f"close worktree {self.data.branch} — rc={result.rc}",
                body=(result.stdout or "") + (
                    "\n" + result.stderr if result.stderr else ""
                ),
            ))

        self.app.push_screen(ConfirmModal(prompt), on_answer)

    def action_open_shell(self) -> None:
        from orca.tui.actions import open_shell

        if not self.data.worktree_path:
            return
        try:
            with self.app.suspend():
                open_shell(Path(self.data.worktree_path))
        except Exception:  # noqa: BLE001
            logger.debug("open_shell failed", exc_info=True)

    def action_open_editor(self) -> None:
        from orca.tui.actions import open_editor

        if not self.data.worktree_path:
            return
        try:
            with self.app.suspend():
                open_editor(Path(self.data.worktree_path))
        except Exception:  # noqa: BLE001
            logger.debug("open_editor failed", exc_info=True)
