"""Bug regression tests discovered during TUI v2 sweep."""
from __future__ import annotations

import asyncio
from pathlib import Path


def _make_n_features(repo_root: Path, n: int) -> None:
    for i in range(n):
        feat = repo_root / "specs" / f"{i:03d}-feat-{i}"
        feat.mkdir(parents=True)
        (feat / "spec.md").write_text(f"# spec {i}\n")


def test_review_pane_responds_to_arrow_keys(tmp_path: Path):
    """Pressing 'down' on a focused review pane moves the cursor."""
    from orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()
    _make_n_features(tmp_path, 30)

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._do_refresh()
            await pilot.pause()
            await pilot.press("1")  # focus review pane
            await pilot.pause()
            from textual.widgets import DataTable
            t = app.query_one("#review-table", DataTable)
            start = t.cursor_row
            for _ in range(5):
                await pilot.press("down")
            await pilot.pause()
            assert t.cursor_row > start, (
                f"cursor did not move: start={start}, now={t.cursor_row}"
            )

    asyncio.run(_run())
