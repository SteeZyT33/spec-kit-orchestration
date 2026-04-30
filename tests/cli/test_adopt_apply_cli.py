"""orca-cli adopt + apply smoke tests."""
from __future__ import annotations

from pathlib import Path

from orca.python_cli import main as cli_main


def test_adopt_in_bare_repo_writes_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["adopt", "--host", "bare", "--force", "--plan-only"])
    assert rc == 0
    assert (tmp_path / ".orca" / "adoption.toml").exists()


def test_adopt_in_superpowers_repo_detects(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["adopt", "--force", "--plan-only"])
    assert rc == 0
    manifest_text = (tmp_path / ".orca" / "adoption.toml").read_text()
    assert 'system = "superpowers"' in manifest_text


def test_apply_after_adopt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    cli_main(["adopt", "--host", "bare", "--force", "--plan-only"])
    rc = cli_main(["apply"])
    assert rc == 0
    assert (tmp_path / ".orca" / "adoption-state.json").exists()


def test_apply_revert_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    cli_main(["adopt", "--host", "bare", "--force", "--plan-only"])
    cli_main(["apply"])
    rc = cli_main(["apply", "--revert"])
    assert rc == 0
    assert (tmp_path / "AGENTS.md").read_text() == "# original\n"


def test_apply_dry_run_no_writes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    cli_main(["adopt", "--host", "bare", "--force", "--plan-only"])
    rc = cli_main(["apply", "--dry-run"])
    assert rc == 0
    # AGENTS.md untouched
    assert (tmp_path / "AGENTS.md").read_text() == "# original\n"
    # state.json NOT written
    assert not (tmp_path / ".orca" / "adoption-state.json").exists()
