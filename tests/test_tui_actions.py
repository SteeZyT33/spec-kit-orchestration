"""Tests for action shell-out helpers."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch


def test_close_worktree_invokes_orca_cli_wt_rm(tmp_path: Path):
    from orca.tui.actions import close_worktree

    fake = type(
        "Result", (), {"returncode": 0, "stdout": "ok\n", "stderr": ""},
    )()
    with patch("orca.tui.actions.subprocess.run", return_value=fake) as mock:
        result = close_worktree(tmp_path, "001-foo")
        assert result.rc == 0
        assert "ok" in result.stdout
        args = mock.call_args[0][0]
        assert args[0] == "orca-cli"
        assert "wt" in args
        assert "rm" in args
        assert "001-foo" in args


def test_close_worktree_captures_stderr_on_failure(tmp_path: Path):
    from orca.tui.actions import close_worktree

    fake = type(
        "Result", (), {"returncode": 1, "stdout": "", "stderr": "boom\n"},
    )()
    with patch("orca.tui.actions.subprocess.run", return_value=fake):
        result = close_worktree(tmp_path, "001-foo")
        assert result.rc == 1
        assert "boom" in result.stderr


def test_close_worktree_handles_missing_binary(tmp_path: Path):
    from orca.tui.actions import close_worktree

    with patch("orca.tui.actions.subprocess.run",
               side_effect=FileNotFoundError("orca-cli not in PATH")):
        result = close_worktree(tmp_path, "001-foo")
        assert result.rc == -1
        assert "orca-cli not in PATH" in result.stderr


def test_read_only_flag_suppresses_card_action_keybindings(tmp_path: Path):
    """When read_only=True, focused card's c/o/e bindings disappear."""
    from orca.tui import OrcaTUI
    from orca.tui.cards import FeatureCard
    from orca.tui.kanban import CardData, KanbanColumn

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path, read_only=True)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("b")
            await pilot.pause()
            data = CardData(feature_id="001-foo", column=KanbanColumn.SPEC,
                            branch="001-foo",
                            worktree_path="/tmp/throwaway",
                            worktree_status="clean")
            card = FeatureCard(data)
            await app.screen.mount(card)
            await pilot.pause()
            keys = list(card._bindings.key_to_bindings.keys())
            for k in ("c", "o", "e"):
                assert k not in keys, (
                    f"read_only mode failed to suppress key {k!r}: bindings={keys}"
                )

    asyncio.run(_run())
