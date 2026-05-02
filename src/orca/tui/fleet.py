"""The fleet table — the only main-screen widget."""
from __future__ import annotations

from rich.text import Text
from textual.widgets import DataTable

from orca.tui.models import FleetRow


_STATE_GLYPH = {
    "live":   ("●", "green"),
    "stale":  ("◐", "yellow"),
    "merged": ("◯", "cyan"),
    "failed": ("✕", "red"),
    "idle":   ("·", "dim"),
}


class FleetTable(DataTable):
    """Single-screen fleet view. Row data comes pre-rendered from collect_fleet."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = False
        self.add_column("", width=1, key="state")
        self.add_column("agent", width=6, key="agent")
        self.add_column("lane", width=22, key="lane")
        self.add_column("stage", width=23, key="stage")
        self.add_column("seen", width=5, key="seen")
        self.add_column("done", width=7, key="done")
        self.add_column("health", key="health")

    def set_rows(self, rows: list[FleetRow]) -> None:
        self.clear()
        for r in rows:
            glyph, color = _STATE_GLYPH.get(r.state, ("·", "dim"))
            health_style = "red" if r.health else ""
            self.add_row(
                Text(glyph, style=color),
                r.agent,
                _truncate(f"{r.feature_id or '-'} · {r.branch}", 22),
                Text(r.stage_strip),
                r.last_seen,
                r.done,
                Text(r.health, style=health_style),
                key=r.lane_id,
            )


def _truncate(value: str, width: int) -> str:
    return value if len(value) <= width else value[: max(0, width - 1)] + "…"
