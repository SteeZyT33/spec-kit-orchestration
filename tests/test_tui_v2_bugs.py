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


def test_review_pane_cursor_survives_refresh(tmp_path: Path):
    """Cursor row stays put when _do_refresh runs (data unchanged).

    This is the *actual* scroll bug observed against the real repo:
    the watcher fires _do_refresh, which calls table.clear() and
    resets the cursor to 0. With many refreshes per second the user
    can never advance.
    """
    from orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()
    _make_n_features(tmp_path, 20)

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._do_refresh()
            await pilot.pause()
            await pilot.press("1")
            await pilot.pause()
            for _ in range(5):
                await pilot.press("down")
            await pilot.pause()
            from textual.widgets import DataTable
            t = app.query_one("#review-table", DataTable)
            before = t.cursor_row
            assert before > 0
            # Trigger refresh; data didn't change.
            app._do_refresh()
            await pilot.pause()
            assert t.cursor_row == before, (
                f"cursor lost on refresh: was {before}, now {t.cursor_row}"
            )

    asyncio.run(_run())


def test_event_pane_cursor_survives_refresh(tmp_path: Path):
    """Same invariant for the event-feed pane."""
    import os, subprocess as _sp
    from orca.tui import OrcaTUI

    env = {**os.environ,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e.com"}
    _sp.run(["git", "-C", str(tmp_path), "init", "-q", "-b", "main"], env=env, check=True)
    _sp.run(["git", "-C", str(tmp_path), "config", "user.email", "t@e.com"], env=env, check=True)
    _sp.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], env=env, check=True)
    for i in range(10):
        f = tmp_path / f"f{i}.txt"
        f.write_text(str(i))
        _sp.run(["git", "-C", str(tmp_path), "add", f.name], env=env, check=True)
        _sp.run(["git", "-C", str(tmp_path), "commit", "-q", "--no-verify",
                 "-m", f"c{i}"], env=env, check=True)

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._do_refresh()
            await pilot.pause()
            await pilot.press("2")
            await pilot.pause()
            for _ in range(3):
                await pilot.press("down")
            await pilot.pause()
            from textual.widgets import DataTable
            t = app.query_one("#event-log", DataTable)
            before = t.cursor_row
            assert before > 0
            app._do_refresh()
            await pilot.pause()
            assert t.cursor_row == before

    asyncio.run(_run())
