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


def test_cli_worktree_overlap_check_via_stdin(monkeypatch, capsys):
    """worktree-overlap-check reads JSON from stdin and emits envelope."""
    import io
    payload = json.dumps({
        "worktrees": [
            {"path": "/a", "branch": "f1", "feature_id": "001",
             "claimed_paths": ["src/foo.py"]},
            {"path": "/b", "branch": "f2", "feature_id": "002",
             "claimed_paths": ["src/foo.py"]},
        ],
        "proposed_writes": [],
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    rc = cli_main(["worktree-overlap-check"])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 0  # Result is Ok; "safe: false" is business logic, not a Result Err
    assert env["ok"] is True
    assert env["result"]["safe"] is False
    assert len(env["result"]["conflicts"]) == 1


def test_cli_worktree_overlap_check_invalid_input(monkeypatch, capsys):
    """Bad JSON on stdin returns INPUT_INVALID with exit 1."""
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("{not-json}"))
    rc = cli_main(["worktree-overlap-check"])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 1
    assert env["ok"] is False
    assert env["error"]["kind"] == "input_invalid"


def test_cli_flow_state_projection(tmp_path, capsys):
    """flow-state-projection capability works via CLI."""
    feat = tmp_path / "specs" / "001-test"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("# Spec\n")

    rc = cli_main([
        "flow-state-projection",
        "--feature-dir", str(feat),
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 0
    assert env["ok"] is True
    assert env["result"]["feature_id"] == "001-test"


def test_cli_flow_state_projection_missing_dir(tmp_path, capsys):
    rc = cli_main([
        "flow-state-projection",
        "--feature-dir", str(tmp_path / "nonexistent"),
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 1
    assert env["ok"] is False
    assert env["error"]["kind"] == "input_invalid"


def test_cli_flow_state_projection_via_feature_id(tmp_path, capsys):
    """flow-state-projection via --feature-id + --repo-root resolves to specs/<id>."""
    feat = tmp_path / "specs" / "002-via-id"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("# Spec\n")

    rc = cli_main([
        "flow-state-projection",
        "--feature-id", "002-via-id",
        "--repo-root", str(tmp_path),
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 0
    assert env["ok"] is True
    assert env["result"]["feature_id"] == "002-via-id"


def test_cli_completion_gate_pass(tmp_path, capsys):
    feat = tmp_path / "specs" / "001"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("# Spec\n")

    rc = cli_main([
        "completion-gate",
        "--feature-dir", str(feat),
        "--target-stage", "plan-ready",
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 0
    assert env["ok"] is True
    assert env["result"]["status"] == "pass"


def test_cli_completion_gate_with_evidence_json(tmp_path, capsys):
    feat = tmp_path / "specs" / "001"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("# Spec\n")
    (feat / "plan.md").write_text("# Plan\n")
    (feat / "tasks.md").write_text("# Tasks\n")

    rc = cli_main([
        "completion-gate",
        "--feature-dir", str(feat),
        "--target-stage", "merge-ready",
        "--evidence-json", '{"ci_green": true}',
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 0
    assert env["ok"] is True
    assert env["result"]["status"] == "pass"


def test_cli_completion_gate_invalid_evidence_json(tmp_path, capsys):
    feat = tmp_path / "specs" / "001"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("# Spec\n")

    rc = cli_main([
        "completion-gate",
        "--feature-dir", str(feat),
        "--target-stage", "plan-ready",
        "--evidence-json", "{not-json}",
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 1
    assert env["ok"] is False
    assert env["error"]["kind"] == "input_invalid"


def test_cli_completion_gate_evidence_json_must_be_object(tmp_path, capsys):
    """--evidence-json must parse to a JSON object; arrays/scalars rejected."""
    feat = tmp_path / "specs" / "001"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("# Spec\n")

    rc = cli_main([
        "completion-gate",
        "--feature-dir", str(feat),
        "--target-stage", "plan-ready",
        "--evidence-json", "[]",  # valid JSON, but not an object
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 1
    assert env["ok"] is False
    assert env["error"]["kind"] == "input_invalid"
    assert "object" in env["error"]["message"]


def test_cli_citation_validator_inline_text(tmp_path, capsys):
    ref = tmp_path / "evidence.md"
    ref.write_text("x")

    rc = cli_main([
        "citation-validator",
        "--content-text", "Results show 42% [evidence].",
        "--reference-set", str(ref),
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 0
    assert env["ok"] is True
    assert env["result"]["citation_coverage"] == 1.0


def test_cli_citation_validator_uncited_claim(tmp_path, capsys):
    ref = tmp_path / "evidence.md"
    ref.write_text("x")

    rc = cli_main([
        "citation-validator",
        "--content-text", "Results show 42% improvement.",
        "--reference-set", str(ref),
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 0  # capability returned Ok; coverage<1.0 is business outcome
    assert env["ok"] is True
    assert len(env["result"]["uncited_claims"]) == 1
    assert env["result"]["citation_coverage"] < 1.0


def test_cli_citation_validator_invalid_mode(tmp_path, capsys):
    ref = tmp_path / "evidence.md"
    ref.write_text("x")

    rc = cli_main([
        "citation-validator",
        "--content-text", "Results show 42%.",
        "--reference-set", str(ref),
        "--mode", "aggressive",
    ])
    # argparse rejects via choices, exit 2 (argv parse error)
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 2
    assert env["ok"] is False
    assert env["error"]["kind"] == "input_invalid"


def test_cli_contradiction_detector_with_fixture_reviewer(tmp_path, capsys, monkeypatch):
    """contradiction-detector via CLI with FixtureReviewer-backed env."""
    new = tmp_path / "synthesis.md"
    new.write_text("X is fast.")
    prior = tmp_path / "evidence.md"
    prior.write_text("X measured slow.")

    fixture = tmp_path / "scenario.json"
    fixture.write_text(json.dumps({
        "reviewer": "claude",
        "raw_findings": [
            {"category": "contradiction", "severity": "high", "confidence": "high",
             "summary": "X is fast", "detail": "conflicts with prior measurements",
             "evidence": ["evidence.md"], "suggestion": "re-measure"}
        ],
    }))

    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CLAUDE", str(fixture))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CODEX", str(fixture))

    rc = cli_main([
        "contradiction-detector",
        "--new-content", str(new),
        "--prior-evidence", str(prior),
        "--reviewer", "cross",
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 0
    assert env["ok"] is True
    # Cross mode dedupes the contradiction across reviewers
    assert len(env["result"]["contradictions"]) == 1
    assert env["result"]["contradictions"][0]["new_claim"] == "X is fast"


def test_cli_contradiction_detector_invalid_reviewer(tmp_path, capsys):
    """argparse choices rejects bogus reviewer with exit 2."""
    new = tmp_path / "synthesis.md"
    new.write_text("X.")
    prior = tmp_path / "evidence.md"
    prior.write_text("Y.")

    rc = cli_main([
        "contradiction-detector",
        "--new-content", str(new),
        "--prior-evidence", str(prior),
        "--reviewer", "bogus",
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 2
    assert env["ok"] is False
    assert env["error"]["kind"] == "input_invalid"


def test_cli_contradiction_detector_single_reviewer(tmp_path, capsys, monkeypatch):
    """contradiction-detector via --reviewer claude (single mode) at the CLI boundary."""
    new = tmp_path / "synthesis.md"
    new.write_text("X.")
    prior = tmp_path / "evidence.md"
    prior.write_text("Y.")
    fixture = tmp_path / "scenario.json"
    fixture.write_text(json.dumps({
        "reviewer": "claude",
        "raw_findings": [
            {"category": "contradiction", "severity": "high", "confidence": "high",
             "summary": "X", "detail": "d", "evidence": ["evidence.md"], "suggestion": "s"}
        ],
    }))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CLAUDE", str(fixture))

    rc = cli_main([
        "contradiction-detector",
        "--new-content", str(new),
        "--prior-evidence", str(prior),
        "--reviewer", "claude",
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 0
    assert env["ok"] is True
    assert len(env["result"]["contradictions"]) == 1
    assert env["result"]["contradictions"][0]["reviewers"] == ["claude"]
    assert env["result"]["missing_reviewers"] == []
