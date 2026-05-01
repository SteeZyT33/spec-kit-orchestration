"""Apply idempotency + state.json correctness."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from orca.core.adoption.apply import apply


def _write_manifest(repo: Path) -> Path:
    manifest = repo / ".orca" / "adoption.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(textwrap.dedent("""
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
        section_marker = "## Orca"
        namespace_prefix = "orca:"
        [constitution]
        policy = "respect-existing"
        [reversal]
        backup_dir = ".orca/adoption-backup"
    """))
    return manifest


def test_apply_creates_state_json(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    apply(repo_root=tmp_path)
    state_json = tmp_path / ".orca" / "adoption-state.json"
    assert state_json.exists()


def test_apply_writes_claude_md_section(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# host content\n")
    apply(repo_root=tmp_path)
    out = (tmp_path / "AGENTS.md").read_text()
    assert "<!-- orca:adoption:start version=1 -->" in out
    assert "## Orca" in out


def test_apply_is_idempotent(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# host content\n")
    apply(repo_root=tmp_path)
    first = (tmp_path / "AGENTS.md").read_text()
    apply(repo_root=tmp_path)
    second = (tmp_path / "AGENTS.md").read_text()
    assert first == second


def test_apply_snapshots_pre_modification(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    apply(repo_root=tmp_path)
    backup_dir = tmp_path / ".orca" / "adoption-backup"
    snapshots = list(backup_dir.glob("*/AGENTS.md"))
    assert len(snapshots) == 1
    assert snapshots[0].read_text() == "# original\n"


def test_apply_missing_manifest(tmp_path: Path) -> None:
    """Missing manifest -> ManifestError or FileNotFoundError."""
    from orca.core.adoption.manifest import ManifestError
    with pytest.raises((ManifestError, FileNotFoundError)):
        apply(repo_root=tmp_path)


def _write_namespace_manifest(repo: Path) -> Path:
    manifest = repo / ".orca" / "adoption.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(textwrap.dedent("""
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
        policy = "namespace"
        section_marker = "## Orca"
        namespace_prefix = "orca:"
        [constitution]
        policy = "respect-existing"
        [reversal]
        backup_dir = ".orca/adoption-backup"
    """))
    return manifest


def test_namespace_apply_writes_orca_md(tmp_path: Path) -> None:
    _write_namespace_manifest(tmp_path)
    apply(repo_root=tmp_path)
    orca_md = tmp_path / "ORCA.md"
    assert orca_md.exists()
    assert "Orca is installed" in orca_md.read_text()


def test_namespace_apply_writes_agents_md_pointer(tmp_path: Path) -> None:
    _write_namespace_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# host content\n")
    apply(repo_root=tmp_path)
    agents = (tmp_path / "AGENTS.md").read_text()
    assert "ORCA.md" in agents
    assert "# host content" in agents


def test_namespace_apply_tracks_orca_md_in_state(tmp_path: Path) -> None:
    """state.json must include ORCA.md so revert can clean it up."""
    import json
    _write_namespace_manifest(tmp_path)
    apply(repo_root=tmp_path)
    state = json.loads((tmp_path / ".orca" / "adoption-state.json").read_text())
    rel_paths = {f["rel_path"] for f in state["files"]}
    assert "ORCA.md" in rel_paths
    assert "AGENTS.md" in rel_paths


def test_namespace_apply_snapshots_existing_orca_md(tmp_path: Path) -> None:
    """If user already has ORCA.md, it must be backed up before overwrite."""
    _write_namespace_manifest(tmp_path)
    (tmp_path / "ORCA.md").write_text("# user's existing ORCA notes\n")
    apply(repo_root=tmp_path)
    backup_dir = tmp_path / ".orca" / "adoption-backup"
    snapshots = list(backup_dir.glob("*/ORCA.md"))
    assert len(snapshots) == 1
    assert snapshots[0].read_text() == "# user's existing ORCA notes\n"


def test_namespace_revert_removes_orca_md(tmp_path: Path) -> None:
    """Revert with no pre-existing ORCA.md should delete the orca-created one."""
    from orca.core.adoption.revert import revert
    _write_namespace_manifest(tmp_path)
    apply(repo_root=tmp_path)
    assert (tmp_path / "ORCA.md").exists()
    revert(repo_root=tmp_path)
    assert not (tmp_path / "ORCA.md").exists()


def test_namespace_revert_restores_existing_orca_md(tmp_path: Path) -> None:
    """Revert with pre-existing ORCA.md should restore the user's version."""
    from orca.core.adoption.revert import revert
    _write_namespace_manifest(tmp_path)
    (tmp_path / "ORCA.md").write_text("# user's existing ORCA notes\n")
    apply(repo_root=tmp_path)
    revert(repo_root=tmp_path)
    assert (tmp_path / "ORCA.md").read_text() == "# user's existing ORCA notes\n"


def test_namespace_apply_is_idempotent(tmp_path: Path) -> None:
    _write_namespace_manifest(tmp_path)
    apply(repo_root=tmp_path)
    first_orca = (tmp_path / "ORCA.md").read_text()
    first_agents = (tmp_path / "AGENTS.md").read_text()
    apply(repo_root=tmp_path)
    assert (tmp_path / "ORCA.md").read_text() == first_orca
    assert (tmp_path / "AGENTS.md").read_text() == first_agents
