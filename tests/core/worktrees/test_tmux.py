from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from orca.core.worktrees.tmux import (
    has_session, has_window, ensure_session, new_window,
    kill_window, kill_session_if_empty, list_windows,
    send_keys, resolve_session_name,
)


class TestResolveSessionName:
    def test_literal_passes_through(self):
        assert resolve_session_name("orca", repo_root=Path("/x/foo")) == "orca"

    def test_template_substitutes_sanitized_repo(self):
        assert resolve_session_name("orca-{repo}",
                                     repo_root=Path("/x/my.repo")) == "orca-my_repo"

    def test_template_truncates_long_repo_name(self):
        long_name = "a" * 200
        result = resolve_session_name("{repo}",
                                       repo_root=Path(f"/x/{long_name}"))
        assert len(result) <= 64


class TestHasSession:
    def test_returns_true_when_tmux_succeeds(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            assert has_session("orca") is True

    def test_returns_false_when_tmux_fails(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=1)
            assert has_session("orca") is False


class TestEnsureSession:
    def test_no_op_when_session_exists(self):
        with patch("orca.core.worktrees.tmux.has_session", return_value=True), \
             patch("subprocess.run") as run:
            ensure_session("orca", cwd=Path("/x"))
            assert run.call_count == 0

    def test_creates_when_missing(self):
        with patch("orca.core.worktrees.tmux.has_session", return_value=False), \
             patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            ensure_session("orca", cwd=Path("/x"))
            assert run.called
            args = run.call_args[0][0]
            assert args[:4] == ["tmux", "new-session", "-d", "-s"]


class TestNewWindow:
    def test_invokes_tmux_new_window(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            new_window(session="orca", window="015-wiz", cwd=Path("/x"))
            assert run.called
            args = run.call_args[0][0]
            assert "new-window" in args
            assert "015-wiz" in args


class TestSendKeys:
    def test_sends_string_then_enter(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            send_keys(session="orca", window="x", keys="bash run.sh")
            # First call types the string, second sends Enter
            assert run.call_count == 2
            first_args = run.call_args_list[0][0][0]
            assert "send-keys" in first_args
            assert "bash run.sh" in first_args
            second_args = run.call_args_list[1][0][0]
            assert "Enter" in second_args
