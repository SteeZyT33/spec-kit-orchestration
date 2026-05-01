"""tmux subprocess wrapper.

All operations use args lists; never shell strings. send_keys uses
two-call pattern (text then Enter) so the keys arg never gets shell-parsed
by tmux's command parser.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from orca.core.worktrees.identifiers import sanitize_repo_name

TMUX_WINDOW_NAME_MAX = 32


def resolve_session_name(template: str, *, repo_root: Path) -> str:
    """Substitute {repo} with sanitized repo basename. Other template
    tokens are reserved for future use."""
    if "{repo}" in template:
        repo_name = sanitize_repo_name(repo_root.name)
        return template.replace("{repo}", repo_name)
    return template


def truncate_window_name(name: str) -> str:
    return name[:TMUX_WINDOW_NAME_MAX]


def has_session(session: str) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True, check=False,
    )
    return result.returncode == 0


def has_window(session: str, window: str) -> bool:
    result = subprocess.run(
        ["tmux", "list-windows", "-t", session, "-F", "#{window_name}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return False
    return window in result.stdout.splitlines()


def list_windows(session: str) -> list[str]:
    """Return list of window names in the session, or empty if missing."""
    result = subprocess.run(
        ["tmux", "list-windows", "-t", session, "-F", "#{window_name}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()


def ensure_session(session: str, *, cwd: Path) -> None:
    if has_session(session):
        return
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session, "-c", str(cwd)],
        check=True,
    )


def new_window(*, session: str, window: str, cwd: Path) -> None:
    name = truncate_window_name(window)
    subprocess.run(
        ["tmux", "new-window", "-t", session, "-n", name, "-c", str(cwd)],
        check=True,
    )


def kill_window(*, session: str, window: str) -> None:
    name = truncate_window_name(window)
    subprocess.run(
        ["tmux", "kill-window", "-t", f"{session}:{name}"],
        capture_output=True, check=False,
    )


def kill_session_if_empty(session: str) -> None:
    if not list_windows(session):
        subprocess.run(
            ["tmux", "kill-session", "-t", session],
            capture_output=True, check=False,
        )


def send_keys(*, session: str, window: str, keys: str) -> None:
    """Send a literal string then Enter. Two subprocess calls so tmux
    doesn't parse `keys` as a tmux command sequence."""
    name = truncate_window_name(window)
    subprocess.run(
        ["tmux", "send-keys", "-t", f"{session}:{name}", keys],
        check=True,
    )
    subprocess.run(
        ["tmux", "send-keys", "-t", f"{session}:{name}", "Enter"],
        check=True,
    )
