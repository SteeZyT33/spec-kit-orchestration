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
    """Compact 2-line focusable card.

    Layout intentionally borderless — the column already has a border;
    nesting another box looked busy. Focus shows as a left accent bar
    instead, which is calmer and reads at a glance.
    """

    DEFAULT_CSS = """
    FeatureCard {
        height: 2;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    FeatureCard:focus {
        background: $boost;
        text-style: none;
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

    @staticmethod
    def _truncate(value: str, width: int) -> str:
        if len(value) <= width:
            return value
        return value[: max(0, width - 1)] + "…"

    def _content_lines(self) -> list[str]:
        d = self.data
        # Keep lines tight enough that cards stay 2-row at the
        # narrowest realistic column width (~22 cols inner @ 140 cols /
        # 5 columns).
        line1 = self._truncate(d.feature_id, 20)
        if d.branch:
            line2 = f"{self._truncate(d.branch, 12)} · {d.worktree_status}"
        else:
            line2 = "(no worktree)"
        return [line1, line2]

    def render(self):  # type: ignore[override]
        lines = self._content_lines()
        # First line bold; second line dim for hierarchy.
        text = Text()
        text.append(lines[0], style="bold")
        text.append("\n")
        text.append(lines[1], style="dim")
        return text

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
