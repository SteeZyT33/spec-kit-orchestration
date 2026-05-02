"""Tests for TUI polish: pane border titles + last-refreshed stamp."""

from __future__ import annotations

import asyncio
from pathlib import Path


def test_panes_have_border_titles(tmp_path: Path):
    """Each pane carries a human-readable border title for orientation."""
    from orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test():
            from orca.tui.panes import AdoptionPane, EventFeedPane, ReviewPane
            # Border titles may carry a "· <count>" suffix once data lands;
            # the prefix is the stable orientation cue.
            assert app.query_one("#review-pane", ReviewPane).border_title.startswith("reviews")
            assert app.query_one("#event-pane", EventFeedPane).border_title.startswith("events")
            assert app.query_one("#adoption-pane", AdoptionPane).border_title.startswith("adoption")

    asyncio.run(_run())


def test_status_block_includes_refreshed_stamp(tmp_path: Path):
    """The header status block surfaces a 'refreshed' line after first refresh."""
    from orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test():
            await _async_pause(app)
            from textual.widgets import Static
            status = app.query_one("#orca-status", Static)
            text = str(status.render())
            assert "refreshed:" in text.lower()

    asyncio.run(_run())


async def _async_pause(app):
    """Yield to the event loop a couple of times so refresh can complete."""
    import asyncio as _aio
    await _aio.sleep(0)
    await _aio.sleep(0)
