from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from orca.python_cli import main as cli_main


def test_cli_lists_capabilities(capsys):
    rc = cli_main(["--list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "cross-agent-review" in out


def test_cli_unknown_capability_exits_3(capsys):
    rc = cli_main(["banana"])
    assert rc == 3


def test_cli_no_args_prints_help(capsys):
    rc = cli_main([])
    out = capsys.readouterr().out
    assert rc == 0 or rc == 2
    assert "orca-cli" in out or "usage" in out.lower()


def test_cli_help_flag_prints_help(capsys):
    rc = cli_main(["--help"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "cross-agent-review" in out


def test_cli_cross_agent_review_with_fixture_reviewer(tmp_path, capsys, monkeypatch):
    target = tmp_path / "x.py"
    target.write_text("pass\n")

    fixture = tmp_path / "scenario.json"
    fixture.write_text(json.dumps({
        "reviewer": "claude",
        "raw_findings": [
            {"category": "c", "severity": "high", "confidence": "high",
             "summary": "S", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s"}
        ],
    }))

    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CLAUDE", str(fixture))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CODEX", str(fixture))

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "claude",
    ])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["metadata"]["capability"] == "cross-agent-review"
    assert len(payload["result"]["findings"]) == 1


def test_cli_invalid_input_exits_1_with_error_json(tmp_path, capsys, monkeypatch):
    fixture = tmp_path / "scenario.json"
    fixture.write_text(json.dumps({"reviewer": "claude", "raw_findings": []}))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CLAUDE", str(fixture))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CODEX", str(fixture))

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(tmp_path / "missing.py"),
        "--reviewer", "claude",
    ])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 1
    assert payload["ok"] is False
    assert payload["error"]["kind"] == "input_invalid"


def test_cli_pretty_mode_prints_findings(tmp_path, capsys, monkeypatch):
    target = tmp_path / "x.py"
    target.write_text("pass\n")
    fixture = tmp_path / "scenario.json"
    fixture.write_text(json.dumps({
        "reviewer": "claude",
        "raw_findings": [
            {"category": "c", "severity": "high", "confidence": "high",
             "summary": "Off-by-one", "detail": "d",
             "evidence": ["x.py:1"], "suggestion": "s"}
        ],
    }))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CLAUDE", str(fixture))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CODEX", str(fixture))

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "claude",
        "--pretty",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK (1 findings)" in out
    assert "[high]" in out
    assert "Off-by-one" in out


def test_cli_pretty_mode_prints_error(tmp_path, capsys, monkeypatch):
    fixture = tmp_path / "scenario.json"
    fixture.write_text(json.dumps({"reviewer": "claude", "raw_findings": []}))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CLAUDE", str(fixture))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CODEX", str(fixture))

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(tmp_path / "missing.py"),
        "--reviewer", "claude",
        "--pretty",
    ])
    out = capsys.readouterr().out
    assert rc == 1
    assert "ERROR" in out
    assert "input_invalid" in out


def test_cli_capability_help_exits_clean(capsys):
    """`orca-cli cross-agent-review --help` must exit 0 without emitting
    a spurious error envelope. Argparse prints the help text itself.
    """
    rc = cli_main(["cross-agent-review", "--help"])
    out = capsys.readouterr().out
    assert rc == 0
    # argparse-generated help text mentions the subcommand name
    assert "cross-agent-review" in out


def test_cli_unknown_subcommand_arg_exits_2(tmp_path, capsys, monkeypatch):
    """Unknown argv tokens are an argv parse error (exit 2 per the
    universal Result contract), not a capability-side INPUT_INVALID
    (exit 1)."""
    target = tmp_path / "x.py"
    target.write_text("pass\n")
    fixture = tmp_path / "scenario.json"
    fixture.write_text(json.dumps({"reviewer": "claude", "raw_findings": []}))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CLAUDE", str(fixture))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CODEX", str(fixture))

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "claude",
        "--bogus-flag",
    ])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 2
    assert payload["ok"] is False
    assert payload["error"]["kind"] == "input_invalid"
    assert "unknown args" in payload["error"]["message"]


def test_orca_cli_script_entry_lists_capabilities():
    """Verify the pyproject.toml [project.scripts] entry actually wires
    'orca-cli' to orca.python_cli:main. This catches packaging
    regressions that the in-process tests can't see."""
    if shutil.which("orca-cli") is None:
        pytest.skip("orca-cli script not on PATH; run `uv sync` first")
    completed = subprocess.run(
        ["orca-cli", "--list"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
    assert "cross-agent-review" in completed.stdout
