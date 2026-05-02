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


def test_board_card_focus_survives_refresh(tmp_path: Path):
    """Refresh on the BoardScreen must keep the same feature focused."""
    from orca.tui import OrcaTUI
    from orca.tui.cards import FeatureCard

    (tmp_path / ".git").mkdir()
    for i in range(5):
        d = tmp_path / "specs" / f"{i:03d}-feat-{i}"
        d.mkdir(parents=True)
        (d / "spec.md").write_text("x")

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("b")
            await pilot.pause()
            await pilot.pause()
            cards = list(app.screen.query(FeatureCard))
            assert cards, "no cards mounted"
            cards[2].focus()
            await pilot.pause()
            before = app.focused.data.feature_id
            app._do_refresh()
            await pilot.pause()
            after = app.focused.data.feature_id
            assert before == after, (
                f"focus jumped on refresh: {before} -> {after}"
            )

    asyncio.run(_run())


def test_board_cards_are_focusable_via_keyboard(tmp_path: Path):
    """Tab on the board lands focus on a FeatureCard, not a column."""
    from orca.tui import OrcaTUI
    from orca.tui.cards import FeatureCard

    (tmp_path / ".git").mkdir()
    for i in range(3):
        d = tmp_path / "specs" / f"{i:03d}-feat-{i}"
        d.mkdir(parents=True)
        (d / "spec.md").write_text("x")

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("b")
            await pilot.pause()
            await pilot.pause()
            await pilot.press("tab")
            await pilot.pause()
            assert isinstance(app.focused, FeatureCard), (
                f"tab landed on {type(app.focused).__name__}, not FeatureCard"
            )

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
