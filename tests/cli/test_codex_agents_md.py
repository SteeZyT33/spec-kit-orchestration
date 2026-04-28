"""Drift tests for plugins/codex/AGENTS.md.

This file is the canonical Codex consumption surface for orca: a single
document that describes every capability, the universal Result envelope,
exit codes, reviewer backend selection, and the "Orca is not a runtime"
boundary. These tests guard against drift: if a new capability is added
or the envelope shape changes, the doc must be updated in lockstep.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_MD = REPO_ROOT / "plugins" / "codex" / "AGENTS.md"

EXPECTED_CAPABILITIES = [
    "cross-agent-review",
    "worktree-overlap-check",
    "flow-state-projection",
    "completion-gate",
    "citation-validator",
    "contradiction-detector",
]


def _read_agents_md() -> str:
    if not AGENTS_MD.exists():
        pytest.fail(f"plugins/codex/AGENTS.md missing at {AGENTS_MD}")
    return AGENTS_MD.read_text(encoding="utf-8")


def test_codex_agents_md_exists():
    assert AGENTS_MD.exists(), (
        "plugins/codex/AGENTS.md must exist as the Codex consumption surface"
    )


def test_codex_agents_md_lists_every_capability():
    content = _read_agents_md()
    missing = [cap for cap in EXPECTED_CAPABILITIES if cap not in content]
    assert not missing, (
        f"plugins/codex/AGENTS.md is missing capabilities: {missing}. "
        f"Every orca-cli capability must be documented in the Codex pointer doc."
    )


def test_codex_agents_md_documents_envelope_shape():
    content = _read_agents_md()
    required_envelope_keys = ['"ok"', '"result"', '"metadata"', '"error"']
    missing = [k for k in required_envelope_keys if k not in content]
    assert not missing, (
        f"plugins/codex/AGENTS.md must document the universal Result envelope "
        f"keys; missing: {missing}"
    )


def test_codex_agents_md_documents_exit_codes():
    content = _read_agents_md()
    # Exit codes 0/1/2/3 must be documented
    for code in ("`0`", "`1`", "`2`", "`3`"):
        assert code in content, (
            f"plugins/codex/AGENTS.md must document exit code {code}"
        )


def test_codex_agents_md_documents_fixture_env_vars():
    content = _read_agents_md()
    required_env_vars = [
        "ORCA_FIXTURE_REVIEWER_CLAUDE",
        "ORCA_FIXTURE_REVIEWER_CODEX",
        "ORCA_LIVE",
    ]
    missing = [v for v in required_env_vars if v not in content]
    assert not missing, (
        f"plugins/codex/AGENTS.md must document reviewer fixture env vars; "
        f"missing: {missing}"
    )


def test_codex_agents_md_documents_what_orca_is_not():
    content = _read_agents_md().lower()
    # Must include explicit "not a runtime / not a scheduler" framing
    assert (
        "not a scheduler" in content
        or "not a runtime" in content
        or "does not execute" in content
    ), (
        "plugins/codex/AGENTS.md must explicitly state orca is not a runtime "
        "or scheduler (the boundary that keeps it a capability library)."
    )
