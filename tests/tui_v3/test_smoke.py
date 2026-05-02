"""Phase 0 smoke: app instantiates and quits cleanly."""
from __future__ import annotations

import asyncio
from pathlib import Path


def test_app_launches_and_quits(tmp_path: Path) -> None:
    from orca.tui.app import FleetApp

    async def _run() -> None:
        app = FleetApp(repo_root=tmp_path, read_only=True)
        async with app.run_test() as pilot:
            await pilot.press("q")

    asyncio.run(_run())
    # If we got here without raising, the scaffold runs.
