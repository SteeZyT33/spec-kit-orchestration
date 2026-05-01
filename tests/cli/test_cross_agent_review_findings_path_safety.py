"""Path-safety regression tests for cross-agent-review findings-file flag."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_cli(args: list[str], cwd: Path) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", *args],
        cwd=str(cwd), capture_output=True, text=True,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, payload


def test_symlinked_findings_file_rejected_with_structured_detail(tmp_path: Path):
    feature_dir = tmp_path / "specs" / "001-foo"
    feature_dir.mkdir(parents=True)
    spec = feature_dir / "spec.md"
    spec.write_text("# spec\n", encoding="utf-8")

    real = feature_dir / "real-findings.json"
    real.write_text("[]", encoding="utf-8")
    link = feature_dir / "linked-findings.json"
    link.symlink_to(real)

    rc, payload = _run_cli(
        [
            "cross-agent-review",
            "--kind", "spec",
            "--target", str(spec),
            "--reviewer", "claude",
            "--feature-id", "001-foo",
            "--claude-findings-file", str(link),
            "--criteria", "feasibility",
        ],
        cwd=tmp_path,
    )
    assert rc != 0
    assert payload["ok"] is False
    err = payload["error"]
    assert err["kind"] == "input_invalid"
    assert err["detail"]["field"] == "--claude-findings-file"
    assert err["detail"]["rule_violated"] == "symlink_in_resolved_path"
    assert "linked-findings.json" in err["detail"]["value_redacted"]
