"""Tests for orca.core.path_safety — enforces docs/superpowers/contracts/path-safety.md."""
from __future__ import annotations

import pytest

from orca.core.path_safety import PathSafetyError


def test_path_safety_error_carries_structured_fields():
    err = PathSafetyError(
        "symlinks rejected: /tmp/x",
        field="--claude-findings-file",
        rule_violated="symlink_in_resolved_path",
        value_redacted="/tmp/x",
    )
    assert str(err) == "symlinks rejected: /tmp/x"
    assert err.field == "--claude-findings-file"
    assert err.rule_violated == "symlink_in_resolved_path"
    assert err.value_redacted == "/tmp/x"


def test_path_safety_error_to_error_detail_returns_three_keys():
    err = PathSafetyError(
        "msg", field="--feature-id", rule_violated="identifier_format",
        value_redacted="bad/value",
    )
    assert err.to_error_detail() == {
        "field": "--feature-id",
        "rule_violated": "identifier_format",
        "value_redacted": "bad/value",
    }
