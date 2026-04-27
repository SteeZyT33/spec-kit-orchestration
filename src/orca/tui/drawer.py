"""Drawer (detail overlay) support for the Orca TUI v1.1.

Read-only detail views for rows in the review pane.
Drawer content is a pure-data `DrawerContent` payload built by a
per-row-type builder function; the `DetailDrawer` ModalScreen renders
that payload and binds Escape / Enter to close itself.

Builders degrade gracefully: any exception while fetching source data
is caught and surfaced as an `error:` line in the drawer body rather
than propagated. This preserves the v1 invariant that one bad file
never crashes the TUI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from orca.tui.collectors import ReviewRow

logger = logging.getLogger(__name__)


REVIEW_PREVIEW_LINES = 40


@dataclass(frozen=True)
class DrawerContent:
    """Pure-data payload a drawer renders.

    - `title`: header string.
    - `body`: ordered list of (label, value) pairs (both strings).
    - `tail`: optional trailing block of lines (event log tail, artifact
      preview, etc.). Empty list means "no tail section".
    """
    title: str
    body: list[tuple[str, str]]
    tail: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Builders - pure functions, no Textual imports at call path
# ---------------------------------------------------------------------------


def _review_artifact_path(repo_root: Path, row: ReviewRow) -> Path:
    # Known review-artifact filenames: review-spec.md, review-code.md,
    # review-pr.md. The review_type string from flow-state matches these
    # names (sans .md) in practice; fall back to review_type as-is if not.
    name = row.review_type
    if not name.endswith(".md"):
        name = f"{name}.md"
    return repo_root / "specs" / row.feature_id / name


def build_review_drawer(repo_root: Path, row: ReviewRow) -> DrawerContent:
    """Build a DrawerContent for a review row with an artifact preview."""
    title = f"Review: {row.feature_id} / {row.review_type}"
    body: list[tuple[str, str]] = [
        ("feature_id", row.feature_id),
        ("review_type", row.review_type),
        ("status", row.status),
    ]

    artifact = _review_artifact_path(repo_root, row)
    tail: list[str] = []
    try:
        if artifact.exists():
            raw = artifact.read_text(encoding="utf-8", errors="replace")
            lines = raw.splitlines()
            tail = lines[:REVIEW_PREVIEW_LINES]
            try:
                rel_path = str(artifact.relative_to(repo_root))
            except ValueError:
                rel_path = str(artifact)
            body.append(("artifact", rel_path))
        else:
            body.append(("artifact", "(not yet written)"))
            tail = ["(artifact not yet written)"]
    except (OSError, ValueError) as exc:
        logger.debug("build_review_drawer: artifact read failed", exc_info=True)
        body.append(("error", f"artifact unavailable: {exc!s}"))
        tail = []

    return DrawerContent(title=title, body=body, tail=tail)


# ---------------------------------------------------------------------------
# ModalScreen
# ---------------------------------------------------------------------------


class DetailDrawer(ModalScreen[None]):
    """Read-only modal drawer that renders a DrawerContent payload.

    Escape and Enter both pop the screen (toggle-close semantics).
    """

    DEFAULT_CSS = """
    DetailDrawer {
        align: center middle;
    }
    DetailDrawer > Vertical {
        width: 80%;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
        overflow: auto;
    }
    #drawer-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #drawer-body, #drawer-tail {
        height: auto;
    }
    #drawer-tail-header {
        text-style: italic;
        margin-top: 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "close", "close", show=True),
        Binding("enter", "close", "close", show=True),
    ]

    def __init__(self, content: DrawerContent) -> None:
        super().__init__()
        self._content = content

    def compose(self) -> ComposeResult:
        body_text = "\n".join(
            f"{label:>24}  {value}" for (label, value) in self._content.body
        )
        container = Vertical()
        yield container
        # Children of the Vertical are mounted via on_mount to keep
        # compose() minimal and avoid assumptions about generator order.

    def on_mount(self) -> None:
        try:
            v = self.query_one(Vertical)
            v.mount(Static(self._content.title, id="drawer-title"))
            body_text = "\n".join(
                f"{label:>24}  {value}"
                for (label, value) in self._content.body
            )
            v.mount(Static(body_text or "(no fields)", id="drawer-body"))
            if self._content.tail:
                v.mount(Static("--- tail ---", id="drawer-tail-header"))
                v.mount(Static("\n".join(self._content.tail), id="drawer-tail"))
        except Exception:  # noqa: BLE001
            logger.debug("DetailDrawer mount failed", exc_info=True)

    def action_close(self) -> None:
        """Delegate close to the app so focus restoration happens."""
        close = getattr(self.app, "_close_drawer", None)
        if callable(close):
            try:
                close()
                return
            except Exception:  # noqa: BLE001
                logger.debug("DetailDrawer _close_drawer delegation failed",
                             exc_info=True)
        # Fallback: legacy behavior - just pop the screen.
        try:
            self.app.pop_screen()
        except Exception:  # noqa: BLE001
            logger.debug("DetailDrawer pop_screen failed", exc_info=True)
