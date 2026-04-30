from __future__ import annotations

import json
import re
import shutil
import subprocess
from importlib.metadata import version as _pkg_version
from pathlib import Path

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


def test_cli_version_flag_prints_package_version(capsys):
    rc = cli_main(["--version"])
    out = capsys.readouterr().out
    assert rc == 0
    expected = _pkg_version("orca")
    assert out.strip() == f"orca {expected}"
    assert re.match(r"orca \d+\.\d+\.\d+", out.strip())


def test_cli_version_short_flag_prints_package_version(capsys):
    rc = cli_main(["-V"])
    out = capsys.readouterr().out
    assert rc == 0
    expected = _pkg_version("orca")
    assert out.strip() == f"orca {expected}"
    assert re.match(r"orca \d+\.\d+\.\d+", out.strip())


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


def test_contradiction_detector_claude_findings_file(tmp_path: Path, capsys) -> None:
    """--claude-findings-file uses FileBackedReviewer instead of SDK."""
    new = tmp_path / "synthesis.md"
    new.write_text("X is fast.")
    prior = tmp_path / "evidence.md"
    prior.write_text("X measured slow.")

    findings = [{
        "id": "abc1234567890def",
        "category": "contradiction",
        "severity": "high",
        "confidence": "high",
        "summary": "X is fast",
        "detail": "conflicts with prior measurements",
        "evidence": ["evidence.md"],
        "suggestion": "re-measure",
        "reviewer": "claude",
    }]
    findings_file = tmp_path / "claude-findings.json"
    findings_file.write_text(json.dumps(findings), encoding="utf-8")

    rc = cli_main([
        "contradiction-detector",
        "--new-content", str(new),
        "--prior-evidence", str(prior),
        "--reviewer", "claude",
        "--claude-findings-file", str(findings_file),
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert env["ok"] is True
    assert "X is fast" in json.dumps(env["result"])
    assert rc == 0


def test_contradiction_detector_codex_findings_file(tmp_path: Path, capsys) -> None:
    """--codex-findings-file uses FileBackedReviewer for codex slot."""
    new = tmp_path / "synthesis.md"
    new.write_text("X is fast.")
    prior = tmp_path / "evidence.md"
    prior.write_text("X measured slow.")

    codex_findings = [{
        "id": "fed4321098765432",
        "category": "contradiction",
        "severity": "medium",
        "confidence": "high",
        "summary": "codex-specific claim",
        "detail": "from codex file",
        "evidence": ["evidence.md"],
        "suggestion": "",
        "reviewer": "codex",
    }]
    codex_file = tmp_path / "codex-findings.json"
    codex_file.write_text(json.dumps(codex_findings), encoding="utf-8")

    claude_file = tmp_path / "claude-findings.json"
    claude_file.write_text(json.dumps([]), encoding="utf-8")

    rc = cli_main([
        "contradiction-detector",
        "--new-content", str(new),
        "--prior-evidence", str(prior),
        "--reviewer", "cross",
        "--claude-findings-file", str(claude_file),
        "--codex-findings-file", str(codex_file),
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert env["ok"] is True
    contradictions = env["result"]["contradictions"]
    assert len(contradictions) == 1
    assert contradictions[0]["new_claim"] == "codex-specific claim"
    assert contradictions[0]["reviewers"] == ["codex"]
    assert rc == 0


def test_contradiction_detector_claude_findings_file_missing(tmp_path: Path, capsys) -> None:
    """Missing file flag returns Err(INPUT_INVALID, claude-findings-file: ...)."""
    new = tmp_path / "synthesis.md"
    new.write_text("X.")
    prior = tmp_path / "evidence.md"
    prior.write_text("Y.")

    rc = cli_main([
        "contradiction-detector",
        "--new-content", str(new),
        "--prior-evidence", str(prior),
        "--reviewer", "claude",
        "--claude-findings-file", str(tmp_path / "does-not-exist.json"),
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert env["ok"] is False
    assert env["error"]["kind"] == "input_invalid"
    assert env["error"]["message"].startswith("claude-findings-file:")
    assert "file not found" in env["error"]["message"]
    assert rc == 1


def test_contradiction_detector_claude_findings_file_symlink_rejected(tmp_path: Path, capsys) -> None:
    """Symlink target is rejected with INPUT_INVALID per spec."""
    new = tmp_path / "synthesis.md"
    new.write_text("X.")
    prior = tmp_path / "evidence.md"
    prior.write_text("Y.")

    real = tmp_path / "real.json"
    real.write_text("[]", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(real)

    rc = cli_main([
        "contradiction-detector",
        "--new-content", str(new),
        "--prior-evidence", str(prior),
        "--reviewer", "claude",
        "--claude-findings-file", str(link),
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert env["ok"] is False
    assert env["error"]["kind"] == "input_invalid"
    assert env["error"]["message"].startswith("claude-findings-file:")
    assert "symlinks rejected" in env["error"]["message"]
    assert rc == 1


def test_contradiction_detector_claude_findings_file_invalid_json(tmp_path: Path, capsys) -> None:
    """Malformed JSON surfaces as INPUT_INVALID, not BACKEND_FAILURE."""
    new = tmp_path / "synthesis.md"
    new.write_text("X.")
    prior = tmp_path / "evidence.md"
    prior.write_text("Y.")

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")

    rc = cli_main([
        "contradiction-detector",
        "--new-content", str(new),
        "--prior-evidence", str(prior),
        "--reviewer", "claude",
        "--claude-findings-file", str(bad),
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert env["ok"] is False
    assert env["error"]["kind"] == "input_invalid"
    assert env["error"]["message"].startswith("claude-findings-file:")
    assert "invalid JSON" in env["error"]["message"]
    assert rc == 1


def test_contradiction_detector_claude_findings_file_not_array(tmp_path: Path, capsys) -> None:
    """Non-array top-level JSON surfaces as INPUT_INVALID."""
    new = tmp_path / "synthesis.md"
    new.write_text("X.")
    prior = tmp_path / "evidence.md"
    prior.write_text("Y.")

    obj = tmp_path / "obj.json"
    obj.write_text('{"findings": []}', encoding="utf-8")

    rc = cli_main([
        "contradiction-detector",
        "--new-content", str(new),
        "--prior-evidence", str(prior),
        "--reviewer", "claude",
        "--claude-findings-file", str(obj),
    ])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert env["ok"] is False
    assert env["error"]["kind"] == "input_invalid"
    assert env["error"]["message"].startswith("claude-findings-file:")
    assert "expected JSON array" in env["error"]["message"]
    assert rc == 1


def test_cross_agent_review_claude_findings_file(tmp_path: Path, capsys, monkeypatch) -> None:
    """--claude-findings-file uses FileBackedReviewer instead of SDK."""
    findings = [{
        "id": "abc1234567890def",
        "category": "correctness",
        "severity": "high",
        "confidence": "high",
        "summary": "from file",
        "detail": "",
        "evidence": [],
        "suggestion": "",
        "reviewer": "claude",
    }]
    findings_file = tmp_path / "claude-findings.json"
    findings_file.write_text(json.dumps(findings), encoding="utf-8")

    target = tmp_path / "subject.txt"
    target.write_text("anything", encoding="utf-8")

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "claude",
        "--claude-findings-file", str(findings_file),
    ])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is True
    assert "from file" in json.dumps(envelope["result"])
    assert rc == 0


def test_cross_agent_review_codex_findings_file(tmp_path: Path, capsys, monkeypatch) -> None:
    """--codex-findings-file uses FileBackedReviewer for codex slot."""
    codex_findings = [{
        "id": "fed4321098765432",
        "category": "security",
        "severity": "medium",
        "confidence": "high",
        "summary": "from codex file",
        "detail": "",
        "evidence": [],
        "suggestion": "",
        "reviewer": "codex",
    }]
    codex_file = tmp_path / "codex-findings.json"
    codex_file.write_text(json.dumps(codex_findings), encoding="utf-8")

    claude_file = tmp_path / "claude-findings.json"
    claude_file.write_text(json.dumps([]), encoding="utf-8")

    target = tmp_path / "subject.txt"
    target.write_text("anything", encoding="utf-8")

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "cross",
        "--claude-findings-file", str(claude_file),
        "--codex-findings-file", str(codex_file),
    ])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is True
    assert "from codex file" in json.dumps(envelope["result"])
    assert rc == 0


def test_cross_agent_review_file_flag_wins_over_fixture(tmp_path: Path, capsys, monkeypatch) -> None:
    """When both --claude-findings-file and ORCA_FIXTURE_REVIEWER_CLAUDE are set,
    file flag takes precedence."""
    file_findings = [{
        "id": "abc1234567890def",
        "category": "correctness", "severity": "high", "confidence": "high",
        "summary": "from file flag", "detail": "", "evidence": [], "suggestion": "",
        "reviewer": "claude",
    }]
    file_path = tmp_path / "file-findings.json"
    file_path.write_text(json.dumps(file_findings), encoding="utf-8")

    # FixtureReviewer scenario shape (per existing tests):
    # {"reviewer": "<name>", "raw_findings": [<raw finding dicts>]}
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps({
        "reviewer": "claude",
        "raw_findings": [
            {"category": "correctness", "severity": "high", "confidence": "high",
             "summary": "from fixture", "detail": "",
             "evidence": ["x.py:1"], "suggestion": ""}
        ],
    }), encoding="utf-8")

    target = tmp_path / "subject.txt"
    target.write_text("anything", encoding="utf-8")

    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CLAUDE", str(fixture_path))

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "claude",
        "--claude-findings-file", str(file_path),
    ])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is True
    result_text = json.dumps(envelope["result"])
    assert "from file flag" in result_text
    assert "from fixture" not in result_text
    assert rc == 0


def test_cross_agent_review_claude_findings_file_missing(tmp_path: Path, capsys) -> None:
    """Missing file flag returns Err(INPUT_INVALID, claude-findings-file: ...)."""
    target = tmp_path / "subject.txt"
    target.write_text("anything", encoding="utf-8")

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "claude",
        "--claude-findings-file", str(tmp_path / "does-not-exist.json"),
    ])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is False
    assert envelope["error"]["kind"] == "input_invalid"
    assert envelope["error"]["message"].startswith("claude-findings-file:")
    assert "file not found" in envelope["error"]["message"]
    assert rc == 1


def test_cross_agent_review_claude_findings_file_symlink_rejected(tmp_path: Path, capsys) -> None:
    """Symlink target is rejected with INPUT_INVALID per spec."""
    real = tmp_path / "real.json"
    real.write_text("[]", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(real)

    target = tmp_path / "subject.txt"
    target.write_text("anything", encoding="utf-8")

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "claude",
        "--claude-findings-file", str(link),
    ])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is False
    assert envelope["error"]["kind"] == "input_invalid"
    assert envelope["error"]["message"].startswith("claude-findings-file:")
    assert "symlinks rejected" in envelope["error"]["message"]
    assert rc == 1


def test_cross_agent_review_claude_findings_file_invalid_json(tmp_path: Path, capsys) -> None:
    """Malformed JSON surfaces as INPUT_INVALID, not BACKEND_FAILURE."""
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    target = tmp_path / "subject.txt"
    target.write_text("anything", encoding="utf-8")

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "claude",
        "--claude-findings-file", str(bad),
    ])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is False
    assert envelope["error"]["kind"] == "input_invalid"
    assert envelope["error"]["message"].startswith("claude-findings-file:")
    assert "invalid JSON" in envelope["error"]["message"]
    assert rc == 1


def test_cross_agent_review_claude_findings_file_not_array(tmp_path: Path, capsys) -> None:
    """Non-array top-level JSON surfaces as INPUT_INVALID."""
    obj = tmp_path / "obj.json"
    obj.write_text('{"findings": []}', encoding="utf-8")
    target = tmp_path / "subject.txt"
    target.write_text("anything", encoding="utf-8")

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "claude",
        "--claude-findings-file", str(obj),
    ])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is False
    assert envelope["error"]["kind"] == "input_invalid"
    assert envelope["error"]["message"].startswith("claude-findings-file:")
    assert "expected JSON array" in envelope["error"]["message"]
    assert rc == 1


def test_cross_agent_review_empty_findings_file_flag_falls_through(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """An empty --claude-findings-file '' must fall through to fixture/live."""
    fixture_findings = [{
        "id": "fed4321098765432",
        "category": "correctness", "severity": "high", "confidence": "high",
        "summary": "from fixture", "detail": "", "evidence": [], "suggestion": "",
        "reviewer": "claude",
    }]
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps({"raw_findings": fixture_findings}), encoding="utf-8")

    target = tmp_path / "subject.txt"
    target.write_text("anything", encoding="utf-8")

    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CLAUDE", str(fixture_path))
    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "claude",
        "--claude-findings-file", "",
    ])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is True
    assert "from fixture" in json.dumps(envelope["result"])
    assert rc == 0


def test_parse_subagent_response_bare_json_array(capsys, monkeypatch) -> None:
    """Bare JSON array on stdin emits same array on stdout."""
    from orca.python_cli import main
    import io

    findings = [{
        "id": "abc1234567890def",
        "category": "correctness",
        "severity": "high",
        "confidence": "high",
        "summary": "test",
        "detail": "",
        "evidence": [],
        "suggestion": "",
        "reviewer": "claude",
    }]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(findings)))
    rc = main(["parse-subagent-response"])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed == findings
    assert rc == 0


def test_parse_subagent_response_markdown_fenced(capsys, monkeypatch) -> None:
    """JSON wrapped in markdown code fence is extracted."""
    from orca.python_cli import main
    import io

    findings = [{
        "id": "abc1234567890def",
        "category": "correctness",
        "severity": "high",
        "confidence": "high",
        "summary": "test",
        "detail": "",
        "evidence": [],
        "suggestion": "",
        "reviewer": "claude",
    }]
    raw = f"Here are my findings:\n\n```json\n{json.dumps(findings)}\n```\n\nLet me know if you need more."
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    rc = main(["parse-subagent-response"])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed == findings
    assert rc == 0


def test_parse_subagent_response_prose_only_fails(capsys, monkeypatch) -> None:
    """Pure prose with no JSON array exits 1 with specific error."""
    from orca.python_cli import main
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("I reviewed the diff and found no issues."))
    rc = main(["parse-subagent-response"])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is False
    assert envelope["error"]["kind"] == "input_invalid"
    msg = envelope["error"]["message"].lower()
    assert "could not parse" in msg or "parse-subagent" in msg
    assert rc == 1


def test_parse_subagent_response_invalid_json_fails(capsys, monkeypatch) -> None:
    """Malformed JSON-looking content exits 1."""
    from orca.python_cli import main
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("[{not: 'valid json'}]"))
    rc = main(["parse-subagent-response"])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is False
    assert rc == 1


def test_build_review_prompt_default(capsys) -> None:
    """No criteria: emits DEFAULT_REVIEW_PROMPT verbatim, no extra sections."""
    from orca.python_cli import main
    from orca.capabilities.cross_agent_review import DEFAULT_REVIEW_PROMPT

    rc = main(["build-review-prompt", "--kind", "diff"])
    out = capsys.readouterr().out
    assert out.strip() == DEFAULT_REVIEW_PROMPT.strip()
    assert rc == 0


def test_build_review_prompt_criteria_bullets(capsys) -> None:
    """--criteria flags become bullet-list under 'Criteria:' header."""
    from orca.python_cli import main

    rc = main([
        "build-review-prompt",
        "--kind", "diff",
        "--criteria", "correctness",
        "--criteria", "security",
    ])
    out = capsys.readouterr().out
    assert "Criteria:" in out
    assert "- correctness" in out
    assert "- security" in out
    assert rc == 0


def test_build_review_prompt_kind_does_not_branch(capsys) -> None:
    """v1: --kind is accepted but does not change output."""
    from orca.python_cli import main

    rc1 = main(["build-review-prompt", "--kind", "diff"])
    out1 = capsys.readouterr().out
    rc2 = main(["build-review-prompt", "--kind", "spec"])
    out2 = capsys.readouterr().out
    assert out1 == out2
    assert rc1 == 0 and rc2 == 0


def test_build_review_prompt_context_bullets(capsys) -> None:
    """--context flags become bullet-list under 'Context:' header."""
    from orca.python_cli import main

    rc = main([
        "build-review-prompt",
        "--kind", "diff",
        "--context", "stacked branch",
        "--context", "WIP commit",
    ])
    out = capsys.readouterr().out
    assert "Context:" in out
    assert "- stacked branch" in out
    assert "- WIP commit" in out
    assert rc == 0


@pytest.mark.parametrize(
    "kind",
    [
        "spec",
        "code",
        "pr",
        "diff",
        "contradiction",
        "artifact",
        "experimental-kind-x",
        "snake_case_kind",
        "kind-with-dashes",
    ],
)
def test_build_review_prompt_accepts_arbitrary_kind(capsys, kind: str) -> None:
    """Regression: --kind accepts any non-empty string (no host-side branching)."""
    from orca.python_cli import main

    rc = main(["build-review-prompt", "--kind", kind, "--criteria", "factual-accuracy"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip() != ""
