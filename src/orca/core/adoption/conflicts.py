"""Slash command collision detection for flat-namespace adoption.

When `slash_commands.namespace = ""` (flat mode), orca commands live at
the top level (e.g. `/review-spec`) and may collide with commands the
host has installed from other plugins. This module walks the host's
known Claude Code command directories and returns any colliding names.

Detection is best-effort and uses Claude Code's standard layout:
- `<repo>/.claude/commands/*.md`         (project-local user commands)
- `<repo>/.claude/plugins/*/commands/*.md` (plugin-installed commands)

The orca plugin's own command files (under `plugins/claude-code/commands/`
in the orca repo) are NOT scanned: they aren't installed in the host's
.claude tree until adoption ships, and the conflict check exists
precisely to decide whether that installation is safe.
"""
from __future__ import annotations

from pathlib import Path


def detect_slash_command_collisions(
    repo_root: Path,
    *,
    enabled: list[str],
    namespace: str,
) -> list[str]:
    """Return orca commands that already exist as host slash commands.

    Returns empty list when namespace is non-empty (commands live under
    `/<namespace>:` and can't collide) OR when no host commands are found.

    Only filename collisions are checked; this is a name-shadowing test,
    not a behavioral comparison. The caller (apply executor) is expected
    to refuse to proceed if the returned list is non-empty.
    """
    if namespace:
        return []
    host_command_names = _discover_host_command_names(repo_root)
    return sorted(set(enabled) & host_command_names)


def _discover_host_command_names(repo_root: Path) -> set[str]:
    """Walk the host's .claude tree and return slash command filenames (no .md)."""
    names: set[str] = set()
    project_commands = repo_root / ".claude" / "commands"
    if project_commands.is_dir():
        for md in project_commands.glob("*.md"):
            names.add(md.stem)
    plugins_root = repo_root / ".claude" / "plugins"
    if plugins_root.is_dir():
        for plugin_dir in plugins_root.iterdir():
            if not plugin_dir.is_dir():
                continue
            commands_dir = plugin_dir / "commands"
            if not commands_dir.is_dir():
                continue
            for md in commands_dir.glob("*.md"):
                names.add(md.stem)
    return names
