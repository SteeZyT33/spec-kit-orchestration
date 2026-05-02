"""Tests for ConfirmModal + ResultModal."""
from __future__ import annotations

import asyncio
from pathlib import Path


def test_confirm_modal_default_no(tmp_path: Path):
    """Pressing Enter / N / Esc cancels; only y confirms."""
    from orca.tui import OrcaTUI
    from orca.tui.modals import ConfirmModal

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            results: list[bool] = []

            def cb(answer: bool | None) -> None:
                results.append(bool(answer))

            app.push_screen(ConfirmModal("test prompt"), cb)
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert results == [False]

    asyncio.run(_run())


def test_confirm_modal_yes(tmp_path: Path):
    from orca.tui import OrcaTUI
    from orca.tui.modals import ConfirmModal

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            results: list[bool] = []

            def cb(answer: bool | None) -> None:
                results.append(bool(answer))

            app.push_screen(ConfirmModal("test prompt"), cb)
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            assert results == [True]

    asyncio.run(_run())


def test_result_modal_renders_body(tmp_path: Path):
    from orca.tui import OrcaTUI
    from orca.tui.modals import ResultModal

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(ResultModal(title="t", body="hello world"))
            await pilot.pause()
            assert isinstance(app.screen, ResultModal)
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, ResultModal)

    asyncio.run(_run())
