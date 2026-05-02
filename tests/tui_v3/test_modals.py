"""Modals: Confirm + Result mounted via push_screen, dismissed via keys."""
from __future__ import annotations

import asyncio
from pathlib import Path


def test_confirm_modal_y_returns_true(tmp_path: Path) -> None:
    asyncio.run(_run_confirm_yes(tmp_path))


async def _run_confirm_yes(tmp_path: Path) -> None:
    from orca.tui.app import FleetApp
    from orca.tui.modals import ConfirmModal
    app = FleetApp(repo_root=tmp_path, read_only=True)
    answer: list[bool | None] = []
    async with app.run_test() as pilot:
        app.push_screen(ConfirmModal("Proceed?"), answer.append)
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    assert answer == [True]


def test_confirm_modal_n_returns_false(tmp_path: Path) -> None:
    asyncio.run(_run_confirm_no(tmp_path))


async def _run_confirm_no(tmp_path: Path) -> None:
    from orca.tui.app import FleetApp
    from orca.tui.modals import ConfirmModal
    app = FleetApp(repo_root=tmp_path, read_only=True)
    answer: list[bool | None] = []
    async with app.run_test() as pilot:
        app.push_screen(ConfirmModal("Proceed?"), answer.append)
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
    assert answer == [False]
