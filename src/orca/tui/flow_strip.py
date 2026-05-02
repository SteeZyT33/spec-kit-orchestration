"""Render the 8-stage flow strip as Rich Text.

Order matches orca.flow_state.STAGE_ORDER. Each stage gets a 2-letter
glyph; status drives case + color. Separator is a middle-dot.
"""
from __future__ import annotations

from rich.text import Text

from orca.flow_state import FlowMilestone, STAGE_ORDER


STAGE_GLYPHS = ["br", "sp", "pl", "ta", "im", "rs", "rc", "rp"]
assert len(STAGE_GLYPHS) == len(STAGE_ORDER), "stage glyph drift"


_STATUS_STYLE = {
    "complete":    ("lower", "bold green"),
    "in_progress": ("upper", "bold yellow"),
    "blocked":     ("upper", "bold red"),
    "not_started": ("lower", "dim"),
    "skipped":     ("lower", "dim"),
}


def _glyph_for(milestone: FlowMilestone) -> tuple[str, str]:
    """Return (glyph, style) for a milestone."""
    idx = STAGE_ORDER.index(milestone.stage)
    raw = STAGE_GLYPHS[idx]
    casing, style = _STATUS_STYLE.get(milestone.status, ("lower", "dim"))
    glyph = raw.upper() if casing == "upper" else raw
    return glyph, style


def render_strip(milestones: list[FlowMilestone]) -> Text:
    """Return Rich Text with per-stage styling."""
    by_stage = {m.stage: m for m in milestones}
    out = Text()
    for i, stage in enumerate(STAGE_ORDER):
        m = by_stage.get(stage) or FlowMilestone(stage=stage, status="not_started")
        glyph, style = _glyph_for(m)
        if i:
            out.append("·", style="dim")
        out.append(glyph, style=style)
    return out


def plain_strip(milestones: list[FlowMilestone]) -> str:
    """Plain-string variant for tests and snapshotting."""
    return render_strip(milestones).plain
