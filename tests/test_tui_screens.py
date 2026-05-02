"""Tests for BoardScreen + b toggle.

The list view is the default screen; BoardScreen overlays via push.
"""
from __future__ import annotations

import asyncio
from pathlib import Path


def test_app_starts_on_default_screen(tmp_path: Path):
    """No BoardScreen on launch."""
    from orca.tui import OrcaTUI
    from orca.tui.screens import BoardScreen

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not isinstance(app.screen, BoardScreen)

    asyncio.run(_run())


def test_b_toggles_to_board_screen(tmp_path: Path):
    from orca.tui import OrcaTUI
    from orca.tui.screens import BoardScreen

    (tmp_path / ".git").mkdir()
    (tmp_path / "specs" / "001-foo").mkdir(parents=True)
    (tmp_path / "specs" / "001-foo" / "spec.md").write_text("# spec\n")

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not isinstance(app.screen, BoardScreen)
            await pilot.press("b")
            await pilot.pause()
            assert isinstance(app.screen, BoardScreen)
            await pilot.press("b")
            await pilot.pause()
            assert not isinstance(app.screen, BoardScreen)

    asyncio.run(_run())


def test_board_screen_renders_columns(tmp_path: Path):
    """BoardScreen mounts a column container per KanbanColumn."""
    from orca.tui import OrcaTUI
    from orca.tui.kanban import KanbanColumn

    (tmp_path / ".git").mkdir()
    (tmp_path / "specs" / "001-foo").mkdir(parents=True)
    (tmp_path / "specs" / "001-foo" / "spec.md").write_text("# spec\n")

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("b")
            await pilot.pause()
            for col in KanbanColumn:
                assert app.screen.query_one(f"#col-{col.name.lower()}") is not None

    asyncio.run(_run())
