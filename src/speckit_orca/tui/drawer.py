"""Drawer (detail overlay) support for the Orca TUI v1.1.

Read-only detail views for rows in the lane, yolo, and review panes.
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
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from speckit_orca.tui.collectors import LaneRow, ReviewRow, YoloRow

logger = logging.getLogger(__name__)


REVIEW_PREVIEW_LINES = 40
YOLO_EVENT_TAIL = 10


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


def _as_str(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (list, tuple)):
        return f"[{len(value)} item(s)]"
    if isinstance(value, dict):
        return f"{{{len(value)} key(s)}}"
    return str(value)


def build_lane_drawer(repo_root: Path, row: LaneRow) -> DrawerContent:
    """Build a DrawerContent for a lane row via matriarch.summarize_lane.

    Graceful degradation: failures at either the fetch site OR the render
    site (malformed payload, missing keys, unexpected types) collapse to a
    placeholder body that still identifies the lane.
    """
    title = f"Lane: {row.lane_id}"
    try:
        from speckit_orca import matriarch as _matriarch
        summary = _matriarch.summarize_lane(row.lane_id, repo_root=repo_root)
    except Exception as exc:  # noqa: BLE001
        logger.debug("build_lane_drawer: summarize_lane failed", exc_info=True)
        return DrawerContent(
            title=title,
            body=[
                ("lane_id", row.lane_id),
                ("effective_state", row.effective_state),
                ("error", f"lane record unavailable: {exc!s}"),
            ],
            tail=[],
        )

    try:
        mailbox = summary.get("mailbox_counts") if isinstance(summary, dict) else None
        if not isinstance(mailbox, dict):
            mailbox = {}
        mailbox_str = (
            f"inbound={mailbox.get('inbound', 0)} "
            f"outbound={mailbox.get('outbound', 0)} "
            f"reports={mailbox.get('reports', 0)}"
        )
        deployment = summary.get("deployment") if isinstance(summary, dict) else None
        if isinstance(deployment, dict):
            # summarize_lane emits the LaneDeployment asdict() output,
            # which carries `deployment_kind` (not `kind`). Fall back
            # across both for forward/back compat.
            kind = deployment.get("deployment_kind") or deployment.get("kind") or "?"
            launcher = deployment.get("launched_by") or "?"
            deployment_str = f"{kind} by {launcher}"
        else:
            deployment_str = "-"

        def _get(key: str) -> Any:
            return summary.get(key) if isinstance(summary, dict) else None

        body: list[tuple[str, str]] = [
            ("lane_id", _as_str(_get("lane_id") or row.lane_id)),
            ("spec_id", _as_str(_get("spec_id"))),
            ("title", _as_str(_get("title"))),
            ("branch", _as_str(_get("branch"))),
            ("worktree_path", _as_str(_get("worktree_path"))),
            ("effective_state", _as_str(_get("effective_state"))),
            ("status_reason", _as_str(_get("status_reason"))),
            ("owner_type", _as_str(_get("owner_type"))),
            ("owner_id", _as_str(_get("owner_id"))),
            ("dependencies", _as_str(_get("dependencies"))),
            ("mailbox_counts", mailbox_str),
            ("delegated_work", _as_str(_get("delegated_work"))),
            ("assignment_history", _as_str(_get("assignment_history"))),
            ("deployment", deployment_str),
            ("registry_revision", _as_str(_get("registry_revision"))),
        ]
        return DrawerContent(title=title, body=body, tail=[])
    except Exception as exc:  # noqa: BLE001
        logger.debug("build_lane_drawer: rendering failed", exc_info=True)
        return DrawerContent(
            title=title,
            body=[
                ("lane_id", row.lane_id),
                ("effective_state", row.effective_state),
                ("error", f"lane payload malformed: {exc!s}"),
            ],
            tail=[],
        )


def _yolo_event_tail(repo_root: Path, run_id: str, limit: int) -> list[str]:
    """Return last `limit` event summaries for a yolo run, or [] on failure."""
    events_path = (
        repo_root / ".specify" / "orca" / "yolo" / "runs" / run_id / "events.jsonl"
    )
    try:
        from speckit_orca.tui.collectors import _tail_jsonl
        objs = _tail_jsonl(events_path, limit)
    except Exception:  # noqa: BLE001
        logger.debug("_yolo_event_tail: tail failed", exc_info=True)
        return []
    lines: list[str] = []
    for obj in objs:
        ts = obj.get("timestamp", "")
        etype = obj.get("event_type", "?")
        to_stage = obj.get("to_stage")
        entry = f"{ts} {etype}"
        if to_stage:
            entry += f" -> {to_stage}"
        reason = obj.get("reason")
        if reason:
            entry += f" ({reason})"
        lines.append(entry)
    return lines


def build_yolo_drawer(repo_root: Path, row: YoloRow) -> DrawerContent:
    """Build a DrawerContent for a yolo run via yolo.run_status.

    Graceful degradation: failures at either the fetch site OR the
    per-field render site collapse to a placeholder body. Attribute
    access is wrapped with getattr() fallbacks so a partially-populated
    RunState never raises during rendering.
    """
    title = f"Run: {row.run_id}"
    try:
        from speckit_orca import yolo as _yolo
        state = _yolo.run_status(repo_root, row.run_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("build_yolo_drawer: run_status failed", exc_info=True)
        return DrawerContent(
            title=title,
            body=[
                ("run_id", row.run_id),
                ("feature_id", row.feature_id),
                ("current_stage", row.current_stage),
                ("outcome", row.outcome),
                ("error", f"run state unavailable: {exc!s}"),
            ],
            tail=[],
        )

    def _attr(name: str, default: Any = None) -> Any:
        try:
            return getattr(state, name, default)
        except Exception:  # noqa: BLE001
            return default

    try:
        body: list[tuple[str, str]] = [
            ("run_id", _as_str(_attr("run_id", row.run_id))),
            ("feature_id", _as_str(_attr("feature_id", row.feature_id))),
            ("mode", _as_str(_attr("mode"))),
            ("lane_id", _as_str(_attr("lane_id"))),
            ("current_stage", _as_str(_attr("current_stage", row.current_stage))),
            ("outcome", _as_str(_attr("outcome", row.outcome))),
            ("block_reason", _as_str(_attr("block_reason"))),
            ("branch", _as_str(_attr("branch"))),
            ("head_commit_sha_at_last_event",
             _as_str(_attr("head_commit_sha_at_last_event"))),
            ("deployment_kind", _as_str(_attr("deployment_kind"))),
            ("review_spec_status", _as_str(_attr("review_spec_status"))),
            ("review_code_status", _as_str(_attr("review_code_status"))),
            ("review_pr_status", _as_str(_attr("review_pr_status"))),
            ("mailbox_path", _as_str(_attr("mailbox_path"))),
            ("last_mailbox_event_id", _as_str(_attr("last_mailbox_event_id"))),
            ("retry_counts", _as_str(_attr("retry_counts"))),
            ("matriarch_sync_failed", _as_str(_attr("matriarch_sync_failed"))),
            ("last_event_id", _as_str(_attr("last_event_id"))),
            ("last_event_timestamp", _as_str(_attr("last_event_timestamp"))),
        ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("build_yolo_drawer: rendering failed", exc_info=True)
        return DrawerContent(
            title=title,
            body=[
                ("run_id", row.run_id),
                ("feature_id", row.feature_id),
                ("error", f"run state malformed: {exc!s}"),
            ],
            tail=[],
        )
    tail = _yolo_event_tail(repo_root, row.run_id, YOLO_EVENT_TAIL)
    if not tail:
        tail = ["(no events)"]
    return DrawerContent(title=title, body=body, tail=tail)


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
            body.append(("artifact", str(artifact.relative_to(repo_root))))
        else:
            body.append(("artifact", "(not yet written)"))
            tail = ["(artifact not yet written)"]
    except OSError as exc:
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

    BINDINGS = [
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
