"""Path-safety regression tests for misc CLI flags."""
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


def test_contradiction_detector_rejects_symlinked_prior_evidence(tmp_path: Path):
    new = tmp_path / "new.md"
    new.write_text("# new")
    real = tmp_path / "real.md"
    real.write_text("# real")
    link = tmp_path / "link.md"
    link.symlink_to(real)

    rc, payload = _run_cli(
        [
            "contradiction-detector",
            "--new-content", str(new),
            "--prior-evidence", str(link),
            "--reviewer", "claude",
        ],
        cwd=tmp_path,
    )
    assert rc != 0
    err = payload["error"]
    assert err["detail"]["field"] == "--prior-evidence"
    assert err["detail"]["rule_violated"] == "symlink_in_resolved_path"


def test_completion_gate_rejects_symlinked_feature_dir(tmp_path: Path):
    real = tmp_path / "real-feature"
    real.mkdir()
    link = tmp_path / "link-feature"
    link.symlink_to(real, target_is_directory=True)

    rc, payload = _run_cli(
        [
            "completion-gate",
            "--feature-dir", str(link),
            "--target-stage", "spec",
        ],
        cwd=tmp_path,
    )
    assert rc != 0
    err = payload["error"]
    assert err["detail"]["field"] == "--feature-dir"
    assert err["detail"]["rule_violated"] == "symlink_in_resolved_path"
