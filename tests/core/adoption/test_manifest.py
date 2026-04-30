"""Manifest round-trip + schema validation."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from orca.core.adoption.manifest import (
    Manifest,
    ManifestError,
    load_manifest,
    write_manifest,
)


def test_manifest_round_trip(tmp_path: Path) -> None:
    src = tmp_path / "adoption.toml"
    src.write_text(textwrap.dedent("""
        schema_version = 1

        [host]
        system = "superpowers"
        feature_dir_pattern = "docs/superpowers/specs/{feature_id}"
        constitution_path = "docs/superpowers/constitution.md"
        agents_md_path = "AGENTS.md"
        review_artifact_dir = "docs/superpowers/reviews"

        [orca]
        state_dir = ".orca"
        installed_capabilities = ["cross-agent-review", "citation-validator"]

        [slash_commands]
        namespace = "orca"
        enabled = ["review-spec", "review-code"]
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

    m = load_manifest(src)
    assert m.host.system == "superpowers"
    assert m.host.feature_dir_pattern == "docs/superpowers/specs/{feature_id}"
    assert m.orca.installed_capabilities == ["cross-agent-review", "citation-validator"]
    assert m.slash_commands.namespace == "orca"
    assert m.claude_md.policy == "section"

    dst = tmp_path / "out.toml"
    write_manifest(m, dst)
    m2 = load_manifest(dst)
    assert m2 == m


def test_unknown_host_system_rejected(tmp_path: Path) -> None:
    src = tmp_path / "adoption.toml"
    src.write_text(textwrap.dedent("""
        schema_version = 1
        [host]
        system = "unknown-system"
        feature_dir_pattern = "x/{feature_id}"
        agents_md_path = "AGENTS.md"
        review_artifact_dir = "x"
        [orca]
        state_dir = ".orca"
        installed_capabilities = []
        [slash_commands]
        namespace = "orca"
        enabled = []
        disabled = []
        [claude_md]
        policy = "section"
        [constitution]
        policy = "respect-existing"
        [reversal]
        backup_dir = ".orca/adoption-backup"
    """))

    with pytest.raises(ManifestError, match="host.system"):
        load_manifest(src)


def test_feature_dir_pattern_must_contain_feature_id(tmp_path: Path) -> None:
    src = tmp_path / "adoption.toml"
    src.write_text(textwrap.dedent("""
        schema_version = 1
        [host]
        system = "spec-kit"
        feature_dir_pattern = "specs/feature"
        agents_md_path = "AGENTS.md"
        review_artifact_dir = "x"
        [orca]
        state_dir = ".orca"
        installed_capabilities = []
        [slash_commands]
        namespace = "orca"
        enabled = []
        disabled = []
        [claude_md]
        policy = "section"
        [constitution]
        policy = "respect-existing"
        [reversal]
        backup_dir = ".orca/adoption-backup"
    """))

    with pytest.raises(ManifestError, match="feature_id"):
        load_manifest(src)


def test_schema_version_unsupported(tmp_path: Path) -> None:
    src = tmp_path / "adoption.toml"
    src.write_text("schema_version = 99\n")
    with pytest.raises(ManifestError, match="schema_version"):
        load_manifest(src)


def test_namespace_format_validated(tmp_path: Path) -> None:
    src = tmp_path / "adoption.toml"
    src.write_text(textwrap.dedent("""
        schema_version = 1
        [host]
        system = "spec-kit"
        feature_dir_pattern = "specs/{feature_id}"
        agents_md_path = "AGENTS.md"
        review_artifact_dir = "x"
        [orca]
        state_dir = ".orca"
        installed_capabilities = []
        [slash_commands]
        namespace = "Bad Namespace!"
        enabled = []
        disabled = []
        [claude_md]
        policy = "section"
        [constitution]
        policy = "respect-existing"
        [reversal]
        backup_dir = ".orca/adoption-backup"
    """))
    with pytest.raises(ManifestError, match="namespace"):
        load_manifest(src)
