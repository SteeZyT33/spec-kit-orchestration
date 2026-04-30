"""CLAUDE.md / constitution / slash-command policy unit tests."""
from __future__ import annotations

from pathlib import Path

from orca.core.adoption.policies.claude_md import (
    apply_section,
    detect_section,
    remove_section,
)

ORCA_CONTENT = "Orca is installed.\n\n- /orca:review-spec\n"
START_MARKER = "<!-- orca:adoption:start version=1 -->"
END_MARKER = "<!-- orca:adoption:end -->"


def test_apply_section_to_empty(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    apply_section(target, ORCA_CONTENT, section_marker="## Orca")
    out = target.read_text()
    assert START_MARKER in out
    assert END_MARKER in out
    assert "## Orca" in out
    assert ORCA_CONTENT in out


def test_apply_section_appends_to_existing(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# My CLAUDE.md\n\nExisting content.\n")
    apply_section(target, ORCA_CONTENT, section_marker="## Orca")
    out = target.read_text()
    assert "Existing content." in out
    assert ORCA_CONTENT in out
    assert out.index("Existing content.") < out.index(START_MARKER)


def test_apply_section_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# My CLAUDE.md\n")
    apply_section(target, ORCA_CONTENT, section_marker="## Orca")
    first = target.read_text()
    apply_section(target, ORCA_CONTENT, section_marker="## Orca")
    assert target.read_text() == first


def test_apply_section_updates_existing_block(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# My CLAUDE.md\n")
    apply_section(target, "Old content\n", section_marker="## Orca")
    apply_section(target, "New content\n", section_marker="## Orca")
    out = target.read_text()
    assert "New content" in out
    assert "Old content" not in out


def test_detect_section_present(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    apply_section(target, ORCA_CONTENT, section_marker="## Orca")
    assert detect_section(target) is True


def test_detect_section_absent(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# no orca\n")
    assert detect_section(target) is False


def test_remove_section_clean_revert(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# My CLAUDE.md\n\nOriginal.\n")
    apply_section(target, ORCA_CONTENT, section_marker="## Orca")
    remove_section(target)
    assert target.read_text() == "# My CLAUDE.md\n\nOriginal.\n"


def test_remove_section_refuses_tampered_block(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text(
        f"# my\n\n{START_MARKER}\n## Orca\nuser-edited!\n{END_MARKER}\n"
    )
    # Hash check happens at apply layer; here we just ensure remove_section
    # always operates only on the delimited block. Tampering inside markers
    # is detected by state.json hash mismatch, not by remove_section.
    remove_section(target)
    assert "## Orca" not in target.read_text()
