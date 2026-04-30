"""Apply + revert produces byte-identical original tree."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from orca.core.adoption.apply import apply
from orca.core.adoption.revert import RevertError, revert


def _write_manifest(repo: Path) -> None:
    (repo / ".orca").mkdir(parents=True, exist_ok=True)
    (repo / ".orca" / "adoption.toml").write_text(textwrap.dedent("""
        schema_version = 1
        [host]
        system = "superpowers"
        feature_dir_pattern = "docs/superpowers/specs/{feature_id}"
        agents_md_path = "AGENTS.md"
        review_artifact_dir = "docs/superpowers/reviews"
        [orca]
        state_dir = ".orca"
        installed_capabilities = ["cross-agent-review"]
        [slash_commands]
        namespace = "orca"
        enabled = ["review-spec"]
        disabled = []
        [claude_md]
        policy = "section"
        [constitution]
        policy = "respect-existing"
        [reversal]
        backup_dir = ".orca/adoption-backup"
    """))


def test_revert_restores_original(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    apply(repo_root=tmp_path)
    revert(repo_root=tmp_path)
    assert (tmp_path / "AGENTS.md").read_text() == "# original\n"


def test_revert_apply_apply_revert_idempotent(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    apply(repo_root=tmp_path)
    apply(repo_root=tmp_path)
    revert(repo_root=tmp_path)
    assert (tmp_path / "AGENTS.md").read_text() == "# original\n"


def test_revert_refuses_when_state_missing(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    with pytest.raises(RevertError, match="state"):
        revert(repo_root=tmp_path)


def test_revert_refuses_hand_edited_file(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    apply(repo_root=tmp_path)
    # User hand-edits inside the orca block
    contents = (tmp_path / "AGENTS.md").read_text()
    (tmp_path / "AGENTS.md").write_text(contents + "\nuser-edit\n")

    with pytest.raises(RevertError, match="hand-edit|hash"):
        revert(repo_root=tmp_path)


def test_revert_keep_state_preserves_backup(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    apply(repo_root=tmp_path)
    revert(repo_root=tmp_path, keep_state=True)
    backup_root = tmp_path / ".orca" / "adoption-backup"
    assert backup_root.exists()
    assert any(backup_root.iterdir())
