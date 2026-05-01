"""orca-cli resolve-path: per-kind dispatch + manifest/detection fallback."""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from orca.python_cli import main as cli_main


@pytest.fixture
def run_cli():
    """Return a helper that invokes orca.python_cli as a subprocess.

    Returns (returncode, payload_dict). Uses subprocess so cwd is respected
    independently of the in-process test's monkeypatch state.
    """
    def _run(args: list[str], cwd: Path) -> tuple[int, dict]:
        proc = subprocess.run(
            [sys.executable, "-m", "orca.python_cli", *args],
            cwd=str(cwd), capture_output=True, text=True,
        )
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
        return proc.returncode, payload
    return _run


def _write_manifest(repo: Path, system: str = "superpowers") -> None:
    pattern_map = {
        "spec-kit": "specs/{feature_id}",
        "openspec": "openspec/changes/{feature_id}",
        "superpowers": "docs/superpowers/specs/{feature_id}",
        "bare": "docs/orca-specs/{feature_id}",
    }
    (repo / ".orca").mkdir(parents=True, exist_ok=True)
    (repo / ".orca" / "adoption.toml").write_text(textwrap.dedent(f"""
        schema_version = 1
        [host]
        system = "{system}"
        feature_dir_pattern = "{pattern_map[system]}"
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


def test_resolve_feature_dir_via_manifest(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_manifest(tmp_path, system="superpowers")
    rc = cli_main(["resolve-path", "--kind", "feature-dir",
                    "--feature-id", "001-x"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.endswith("docs/superpowers/specs/001-x")
    assert Path(out).is_absolute()


def test_resolve_feature_dir_via_detection_no_manifest(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "openspec" / "changes").mkdir(parents=True)
    rc = cli_main(["resolve-path", "--kind", "feature-dir",
                    "--feature-id", "add-x"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.endswith("openspec/changes/add-x")


def test_resolve_feature_dir_bare_fallback(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "feature-dir",
                    "--feature-id", "001-x"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.endswith("docs/orca-specs/001-x")


def test_resolve_constitution_present(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "constitution.md").write_text("# c\n")
    rc = cli_main(["resolve-path", "--kind", "constitution"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.endswith("docs/superpowers/constitution.md")


def test_resolve_constitution_absent_returns_empty(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "openspec" / "changes").mkdir(parents=True)
    rc = cli_main(["resolve-path", "--kind", "constitution"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out == "" or out == "\n"


def test_resolve_agents_md(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "agents-md"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.endswith("AGENTS.md")


def test_resolve_reviews_dir(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    rc = cli_main(["resolve-path", "--kind", "reviews-dir"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.endswith("docs/superpowers/reviews")


def test_resolve_reference_set(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fd = tmp_path / "docs" / "superpowers" / "specs" / "001-x"
    fd.mkdir(parents=True)
    (fd / "plan.md").write_text("# p\n")
    (fd / "tasks.md").write_text("# t\n")
    rc = cli_main(["resolve-path", "--kind", "reference-set",
                    "--feature-id", "001-x"])
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.strip()]
    assert rc == 0
    assert len(lines) == 2
    assert any(l.endswith("plan.md") for l in lines)
    assert any(l.endswith("tasks.md") for l in lines)


def test_resolve_path_invalid_kind(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "bogus"])
    assert rc == 2  # argv parse error


def test_resolve_feature_dir_missing_feature_id(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "feature-dir"])
    assert rc == 1
    out = capsys.readouterr().out
    import json
    env = json.loads(out)
    assert env["ok"] is False
    assert env["error"]["kind"] == "input_invalid"


def test_resolve_constitution_rejects_feature_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "constitution",
                    "--feature-id", "x"])
    assert rc == 1


def test_resolve_feature_id_with_dotdot_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "feature-dir",
                    "--feature-id", ".."])
    assert rc == 1


def test_resolve_feature_id_with_slash_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "feature-dir",
                    "--feature-id", "../etc/passwd"])
    assert rc == 1


def test_resolve_path_rejects_traversal_feature_id(tmp_path: Path, run_cli):
    rc, payload = run_cli(["resolve-path", "--kind", "feature-dir", "--feature-id", ".."], cwd=tmp_path)
    assert rc != 0
    err = payload["error"]
    assert err["kind"] == "input_invalid"
    assert err["detail"]["rule_violated"] == "identifier_reserved"
    assert err["detail"]["field"] == "--feature-id"


def test_resolve_path_rejects_slash_in_feature_id(tmp_path: Path, run_cli):
    rc, payload = run_cli(
        ["resolve-path", "--kind", "feature-dir", "--feature-id", "foo/bar"], cwd=tmp_path,
    )
    assert rc != 0
    err = payload["error"]
    assert err["detail"]["rule_violated"] == "identifier_format"
