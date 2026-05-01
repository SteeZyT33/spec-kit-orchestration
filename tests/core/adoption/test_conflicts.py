"""Tests for slash command flat-namespace conflict detection."""
from __future__ import annotations

from pathlib import Path

from orca.core.adoption.conflicts import detect_slash_command_collisions


def test_namespaced_returns_empty_without_scanning(tmp_path: Path):
    """Non-empty namespace short-circuits — host commands are irrelevant."""
    cmds = tmp_path / ".claude" / "commands"
    cmds.mkdir(parents=True)
    (cmds / "review-spec.md").write_text("# host's review-spec\n")
    result = detect_slash_command_collisions(
        tmp_path, enabled=["review-spec", "gate"], namespace="orca",
    )
    assert result == []


def test_flat_no_host_commands_returns_empty(tmp_path: Path):
    result = detect_slash_command_collisions(
        tmp_path, enabled=["review-spec", "gate"], namespace="",
    )
    assert result == []


def test_flat_detects_project_local_collision(tmp_path: Path):
    cmds = tmp_path / ".claude" / "commands"
    cmds.mkdir(parents=True)
    (cmds / "review-spec.md").write_text("# host's review-spec\n")
    (cmds / "deploy.md").write_text("# host's deploy\n")
    result = detect_slash_command_collisions(
        tmp_path, enabled=["review-spec", "gate"], namespace="",
    )
    assert result == ["review-spec"]


def test_flat_detects_plugin_collision(tmp_path: Path):
    plugin_cmds = tmp_path / ".claude" / "plugins" / "speckit" / "commands"
    plugin_cmds.mkdir(parents=True)
    (plugin_cmds / "gate.md").write_text("# speckit's gate\n")
    result = detect_slash_command_collisions(
        tmp_path, enabled=["review-spec", "gate"], namespace="",
    )
    assert result == ["gate"]


def test_flat_collisions_are_sorted_and_deduped(tmp_path: Path):
    """Same name in both project-local and plugin dirs reports once."""
    project_cmds = tmp_path / ".claude" / "commands"
    project_cmds.mkdir(parents=True)
    (project_cmds / "review-spec.md").write_text("")
    plugin_cmds = tmp_path / ".claude" / "plugins" / "speckit" / "commands"
    plugin_cmds.mkdir(parents=True)
    (plugin_cmds / "review-spec.md").write_text("")
    (plugin_cmds / "gate.md").write_text("")
    result = detect_slash_command_collisions(
        tmp_path, enabled=["review-spec", "gate", "cite"], namespace="",
    )
    assert result == ["gate", "review-spec"]


def test_flat_ignores_non_md_files(tmp_path: Path):
    cmds = tmp_path / ".claude" / "commands"
    cmds.mkdir(parents=True)
    (cmds / "review-spec.txt").write_text("not a command")
    (cmds / "README.md").write_text("docs, not a command — but stem matches")
    result = detect_slash_command_collisions(
        tmp_path, enabled=["review-spec", "README"], namespace="",
    )
    # README.md does match by stem, but review-spec.txt is ignored
    assert result == ["README"]


def test_flat_handles_missing_claude_dir(tmp_path: Path):
    """Repo with no .claude dir should not error."""
    result = detect_slash_command_collisions(
        tmp_path, enabled=["review-spec"], namespace="",
    )
    assert result == []
