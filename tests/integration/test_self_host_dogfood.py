"""orca dogfood: orca-cli adopt against the orca repo itself succeeds."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_self_host_adopt_detects_superpowers(tmp_path: Path) -> None:
    """Copy the orca repo's superpowers signal into a temp dir; ensure detection works.

    We don't run against the real worktree because adopt would write .orca/adoption.toml
    and we don't want to perturb dev state. Instead we create a tiny fixture that
    mimics the orca repo's superpowers signature.
    """
    # Mimic superpowers signal
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "constitution.md").write_text("# c\n")

    # Run orca-cli adopt --plan-only
    result = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "adopt",
         "--repo-root", str(tmp_path), "--force", "--plan-only"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    manifest = (tmp_path / ".orca" / "adoption.toml").read_text()
    assert 'system = "superpowers"' in manifest
    assert "docs/superpowers/specs/{feature_id}" in manifest


@pytest.mark.integration
def test_self_host_apply_revert_round_trip(tmp_path: Path) -> None:
    """End-to-end: adopt + apply + revert against a fresh fixture leaves no trace."""
    (tmp_path / "AGENTS.md").write_text("# original AGENTS.md\n")
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)

    # adopt
    subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "adopt",
         "--repo-root", str(tmp_path), "--force"],
        check=True,
    )
    # AGENTS.md should now have the orca block
    after_apply = (tmp_path / "AGENTS.md").read_text()
    assert "<!-- orca:adoption:start" in after_apply

    # revert
    result = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "apply",
         "--repo-root", str(tmp_path), "--revert"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

    # AGENTS.md byte-identical to original
    assert (tmp_path / "AGENTS.md").read_text() == "# original AGENTS.md\n"
    # .orca/ removed
    assert not (tmp_path / ".orca").exists()
