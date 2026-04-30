"""Regression: slash commands MUST consult orca-cli resolve-path.

These tests grep each refactored command for the canonical invocation
pattern. Drift from `orca-cli resolve-path --kind feature-dir` back to
hardcoded `specs/<id>/` would break adoption for non-spec-kit hosts.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "plugins" / "claude-code" / "commands"

# Commands that resolve --feature-id to a feature-dir
HOST_AWARE_COMMANDS = [
    "review-spec.md",
    "review-code.md",
    "review-pr.md",
    "gate.md",
    "cite.md",
]


@pytest.mark.parametrize("filename", HOST_AWARE_COMMANDS)
def test_command_invokes_resolve_path_feature_dir(filename: str) -> None:
    text = (COMMANDS_DIR / filename).read_text()
    assert "orca-cli resolve-path --kind feature-dir" in text, (
        f"{filename} must call `orca-cli resolve-path --kind feature-dir`"
    )


def test_cite_uses_reference_set_discovery() -> None:
    """cite.md MUST use `--kind reference-set` for auto-discovery (not the
    legacy bash `for f in plan.md...` loop)."""
    text = (COMMANDS_DIR / "cite.md").read_text()
    assert "orca-cli resolve-path --kind reference-set" in text, (
        "cite.md must call orca-cli resolve-path --kind reference-set"
    )
