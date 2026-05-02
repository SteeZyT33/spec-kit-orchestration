from __future__ import annotations

import argparse
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Static

from orca.tui.fleet import FleetTable
from orca.tui.models import FleetRow


class FleetApp(App):
    """Top-level TUI app."""

    TITLE = "orca"
    SUB_TITLE = "fleet"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("q", "quit", "quit"),
        Binding("g", "refresh", "refresh"),
        Binding("enter", "drill_in", "drill", show=True),
        Binding("o", "open_shell", "shell"),
        Binding("e", "open_editor", "edit"),
        Binding("r", "close_lane", "rm"),
        Binding("n", "new_lane", "new"),
        Binding("d", "doctor", "doctor"),
    ]

    # Hide r/n/d from Footer when read_only.
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self.read_only and action in {"close_lane", "new_lane", "doctor"}:
            return False
        return True
    CSS_PATH = "theme.tcss"

    def __init__(self, repo_root: Path, read_only: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.repo_root = repo_root
        self.read_only = read_only
        self._rows: list[FleetRow] = []

    def compose(self) -> ComposeResult:  # type: ignore[override]
        yield FleetTable(id="fleet")
        yield Static("", id="status-line")
        yield Footer()

    def set_rows(self, rows: list[FleetRow]) -> None:
        fleet = self.query_one(FleetTable)
        prev_sig = fleet._last_signature
        self._rows = list(rows)
        fleet.set_rows(rows)
        if fleet._last_signature != prev_sig:
            self._update_status_line()

    def _update_status_line(self) -> None:
        n = len(self._rows)
        stale = sum(1 for r in self._rows if r.state == "stale")
        merged = sum(1 for r in self._rows if r.state == "merged")
        host = self._host_system_label()
        refresh = self._last_refresh_label()
        line = (f"  host: {host} · {n} lanes · {stale} stale · "
                f"{merged} ready-to-merge · last refresh: {refresh}")
        self.query_one("#status-line", Static).update(line)

    def _host_system_label(self) -> str:
        try:
            from orca.core.host_layout import from_manifest
            layout = from_manifest(self.repo_root)
            return layout.__class__.__name__.replace("Layout", "").lower()
        except Exception:
            pass
        try:
            from orca.core.host_layout.detect import detect
            layout = detect(self.repo_root)
            return layout.__class__.__name__.replace("Layout", "").lower()
        except Exception:
            return "?"

    def _last_refresh_label(self) -> str:
        ts = getattr(self, "_last_refresh_at", None)
        if ts is None:
            return "-"
        from datetime import datetime, timezone
        delta = (datetime.now(timezone.utc) - ts).total_seconds()
        if delta < 60:
            return f"{int(delta)}s ago"
        return f"{int(delta / 60)}m ago"

    def action_refresh(self) -> None:
        self._collect_and_set()

    def action_drill_in(self) -> None:
        from orca.tui.drilldown import LaneScreen
        from orca.tui.fleet import FleetTable
        table = self.query_one(FleetTable)
        if not self._rows:
            return
        idx = table.cursor_row
        if 0 <= idx < len(self._rows):
            row = self._rows[idx]
            self.push_screen(LaneScreen(self.repo_root, row))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_drill_in()

    def _focused_row(self) -> FleetRow | None:
        from orca.tui.fleet import FleetTable
        try:
            table = self.query_one(FleetTable)
        except Exception:
            return None
        idx = table.cursor_row
        if idx is None or not self._rows or idx >= len(self._rows):
            return None
        return self._rows[idx]

    def action_open_shell(self) -> None:
        row = self._focused_row()
        if row is None or not row.worktree_path:
            return
        from orca.tui.actions import open_shell
        with self.suspend():
            open_shell(Path(row.worktree_path))

    def action_open_editor(self) -> None:
        row = self._focused_row()
        if row is None or not row.worktree_path:
            return
        from orca.tui.actions import open_editor
        with self.suspend():
            open_editor(Path(row.worktree_path))

    def action_close_lane(self) -> None:
        if self.read_only:
            return
        row = self._focused_row()
        if row is None:
            return
        from orca.tui.modals import ConfirmModal, ResultModal
        from orca.tui.actions import close_lane
        prompt = f"Close lane {row.branch}? (deletes worktree, removes registration)"

        def on_answer(ok: bool | None) -> None:
            if not ok:
                return
            res = close_lane(self.repo_root, branch=row.branch)
            self.push_screen(ResultModal(
                title=f"close {row.branch} — rc={res.rc}",
                body=(res.stdout + ("\n" + res.stderr if res.stderr else "")),
            ))
            self._collect_and_set()
        self.push_screen(ConfirmModal(prompt), on_answer)

    def action_new_lane(self) -> None:
        if self.read_only:
            return
        from orca.tui.modals import NewLaneModal, ResultModal
        from orca.tui.actions import new_lane

        def on_submit(payload: dict | None) -> None:
            if not payload:
                return
            res = new_lane(self.repo_root, feature=payload["feature"],
                            agent=payload["agent"])
            self.push_screen(ResultModal(
                title=f"new lane {payload['feature']} — rc={res.rc}",
                body=(res.stdout + ("\n" + res.stderr if res.stderr else "")),
            ))
            self._collect_and_set()
        self.push_screen(NewLaneModal(), on_submit)

    def action_doctor(self) -> None:
        if self.read_only:
            return
        from orca.tui.modals import DoctorModal
        from orca.tui.actions import doctor
        res = doctor(self.repo_root)
        self.push_screen(DoctorModal(
            title=f"wt doctor — rc={res.rc}",
            body=(res.stdout + ("\n" + res.stderr if res.stderr else "")),
        ))
        self._collect_and_set()

    def on_mount(self) -> None:
        from orca.tui.watcher import Watcher
        self._collect_and_set()
        self._watcher = Watcher(
            self.repo_root,
            on_change=lambda _p: self.call_from_thread(self._collect_and_set),
        )

    def on_unmount(self) -> None:
        w = getattr(self, "_watcher", None)
        if w is not None:
            w.stop()

    def _collect_and_set(self) -> None:
        from datetime import datetime, timezone
        from orca.tui.collect import collect_fleet
        from orca.tui.actions import (
            tmux_alive, branch_merged, last_event, last_setup_failed,
        )
        try:
            rows = collect_fleet(
                self.repo_root,
                tmux_alive=tmux_alive,
                branch_merged=lambda b, base: branch_merged(self.repo_root, b, base),
                last_event=lambda lid: last_event(self.repo_root, lid),
                last_setup_failed=lambda lid: last_setup_failed(self.repo_root, lid),
            )
            self.set_rows(rows)
        except Exception:
            self.set_rows([])
        self._last_refresh_at = datetime.now(timezone.utc)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="orca-tui")
    p.add_argument("--repo-root", default=".", help="Path to repo root")
    p.add_argument("--read-only", action="store_true",
                   help="Suppress mutating actions (r/n/d)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    FleetApp(repo_root=Path(args.repo_root).resolve(),
             read_only=args.read_only).run()
    return 0
