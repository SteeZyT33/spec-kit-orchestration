"""Tests for the adoption-state TUI collector + pane.

The adoption surface summarizes what `.orca/adoption.toml` declares
and what `.orca/adoption-state.json` shows as the last apply outcome.
Read-only, pure function of `repo_root`. Empty / absent files yield
an `AdoptionInfo(present=False, ...)` sentinel rather than raising.
"""

from __future__ import annotations

import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_manifest(repo_root: Path, body: str) -> None:
    orca_dir = repo_root / ".orca"
    orca_dir.mkdir(parents=True, exist_ok=True)
    (orca_dir / "adoption.toml").write_text(body)


def _write_state(repo_root: Path, payload: dict) -> None:
    orca_dir = repo_root / ".orca"
    orca_dir.mkdir(parents=True, exist_ok=True)
    (orca_dir / "adoption-state.json").write_text(json.dumps(payload))


# ---------------------------------------------------------------------------
# Collector contract
# ---------------------------------------------------------------------------


def test_adoption_absent_returns_sentinel(tmp_path: Path):
    """No .orca/adoption.toml => present=False, all fields blank/zero."""
    from orca.tui.adoption import collect_adoption

    info = collect_adoption(tmp_path)
    assert info.present is False
    assert info.host_system == ""
    assert info.installed_capabilities == 0
    assert info.applied is False


def test_adoption_manifest_only(tmp_path: Path):
    """Manifest present, state.json absent => present=True, applied=False."""
    from orca.tui.adoption import collect_adoption

    _write_manifest(tmp_path, """\
schema_version = 1

[host]
system = "superpowers"
agents_md_path = "AGENTS.md"

[orca]
state_dir = ".orca"
installed_capabilities = ["a", "b", "c"]

[slash_commands]
namespace = "orca"
enabled = ["review-spec", "review-code"]
disabled = []

[constitution]
policy = "respect-existing"
""")

    info = collect_adoption(tmp_path)
    assert info.present is True
    assert info.host_system == "superpowers"
    assert info.installed_capabilities == 3
    assert info.slash_namespace == "orca"
    assert info.slash_enabled == 2
    assert info.constitution_policy == "respect-existing"
    assert info.applied is False
    assert info.applied_files == 0


def test_adoption_with_state(tmp_path: Path):
    """Both files present => applied=True, applied_files reflects state."""
    from orca.tui.adoption import collect_adoption

    _write_manifest(tmp_path, """\
schema_version = 1

[host]
system = "bare"

[orca]
state_dir = ".orca"
installed_capabilities = ["one"]

[slash_commands]
namespace = ""
enabled = []
disabled = []

[constitution]
policy = "respect-existing"
""")
    _write_state(tmp_path, {
        "applied_at": "2026-05-01T15:19:31+00:00",
        "files": [
            {"rel_path": "AGENTS.md"},
            {"rel_path": ".claude/commands/orca-review-spec.md"},
        ],
    })

    info = collect_adoption(tmp_path)
    assert info.present is True
    assert info.applied is True
    assert info.applied_files == 2
    assert info.applied_at.startswith("2026-05-01")


def test_adoption_corrupt_manifest_does_not_raise(tmp_path: Path):
    """Malformed TOML => present=True (file exists) but fields blank, no crash."""
    from orca.tui.adoption import collect_adoption

    _write_manifest(tmp_path, "not = [valid toml")

    info = collect_adoption(tmp_path)
    assert info.present is True  # file exists; just unreadable
    assert info.host_system == ""
    assert info.installed_capabilities == 0


def test_adoption_corrupt_state_does_not_raise(tmp_path: Path):
    """Malformed JSON state => applied=False, applied_files=0, no crash."""
    from orca.tui.adoption import collect_adoption

    _write_manifest(tmp_path, """\
schema_version = 1
[host]
system = "bare"
[orca]
state_dir = ".orca"
installed_capabilities = []
[slash_commands]
namespace = ""
enabled = []
disabled = []
[constitution]
policy = "respect-existing"
""")
    (tmp_path / ".orca" / "adoption-state.json").write_text("{ not json")

    info = collect_adoption(tmp_path)
    assert info.applied is False
    assert info.applied_files == 0


# ---------------------------------------------------------------------------
# Render contract (pure-function rows for the pane)
# ---------------------------------------------------------------------------


def test_adoption_render_rows_absent(tmp_path: Path):
    from orca.tui.adoption import collect_adoption, render_rows

    info = collect_adoption(tmp_path)
    rows = render_rows(info)
    assert any("not adopted" in r.value.lower()
               or "not adopted" in r.label.lower() for r in rows)


def test_adoption_render_rows_present(tmp_path: Path):
    from orca.tui.adoption import collect_adoption, render_rows

    _write_manifest(tmp_path, """\
schema_version = 1
[host]
system = "superpowers"
[orca]
state_dir = ".orca"
installed_capabilities = ["a", "b"]
[slash_commands]
namespace = "orca"
enabled = ["x", "y", "z"]
disabled = []
[constitution]
policy = "respect-existing"
""")
    _write_state(tmp_path, {
        "applied_at": "2026-05-01T12:00:00+00:00",
        "files": [{"rel_path": "AGENTS.md"}],
    })

    info = collect_adoption(tmp_path)
    rows = render_rows(info)
    labels = {r.label for r in rows}
    # The pane surfaces these key facts:
    assert "host" in labels
    assert "capabilities" in labels
    assert "slash commands" in labels
    assert "applied" in labels


# ---------------------------------------------------------------------------
# App integration (Pilot harness)
# ---------------------------------------------------------------------------


def test_app_mounts_adoption_pane(tmp_path: Path):
    """The adoption pane is mounted on app launch."""
    import asyncio
    from orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test():
            assert app.query_one("#adoption-pane") is not None

    asyncio.run(_run())


def test_app_renders_adoption_rows_on_refresh(tmp_path: Path):
    """When .orca/adoption.toml exists, the pane shows real rows."""
    import asyncio
    from orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()
    _write_manifest(tmp_path, """\
schema_version = 1
[host]
system = "superpowers"
[orca]
state_dir = ".orca"
installed_capabilities = ["a", "b"]
[slash_commands]
namespace = "orca"
enabled = ["x"]
disabled = []
[constitution]
policy = "respect-existing"
""")

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test():
            from textual.widgets import DataTable
            table = app.query_one("#adoption-table", DataTable)
            # 5 rows when manifest is present (host/caps/slash/constitution/applied)
            assert table.row_count >= 4

    asyncio.run(_run())


def test_app_logo_header_renders_logo(tmp_path: Path):
    """The header includes the orca FINAL_ART logo."""
    import asyncio
    from orca.tui import OrcaTUI
    from orca.banner_anim import FINAL_ART

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test():
            from textual.widgets import Static
            logo_widget = app.query_one("#orca-logo", Static)
            rendered = str(logo_widget.render())
            # The wave line is a visually unmistakable signature of FINAL_ART.
            assert FINAL_ART[-1] in rendered

    asyncio.run(_run())
