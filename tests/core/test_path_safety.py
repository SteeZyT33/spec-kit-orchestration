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


from orca.core.path_safety import validate_identifier


class TestValidateIdentifier:
    def test_valid_alphanumeric(self):
        assert validate_identifier("feature_001", field="--feature-id") == "feature_001"

    def test_valid_with_dots_dashes_underscores(self):
        assert validate_identifier("001-foo.bar_baz", field="--feature-id") == "001-foo.bar_baz"

    def test_rejects_empty_string(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_empty"
        assert exc_info.value.field == "--feature-id"

    def test_rejects_dot(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier(".", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_reserved"

    def test_rejects_double_dot(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("..", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_reserved"

    def test_rejects_leading_dash(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("-foo", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_format"

    def test_rejects_slash(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("foo/bar", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_format"

    def test_rejects_null_byte(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("foo\0bar", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_format"

    def test_rejects_traversal_attempt(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("..\\foo", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_format"

    def test_rejects_too_long(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("a" * 129, field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_too_long"

    def test_max_length_default_is_128(self):
        # Exactly 128 chars: valid
        assert validate_identifier("a" * 128, field="--feature-id") == "a" * 128
