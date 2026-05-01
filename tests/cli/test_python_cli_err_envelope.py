"""Tests for _err_envelope detail-passthrough.

Verifies that path-safety failures can attach structured detail
(field/rule_violated/value_redacted) to the INPUT_INVALID envelope.
"""
from __future__ import annotations

from orca.core.errors import ErrorKind
from orca.python_cli import _err_envelope


def test_err_envelope_without_detail_omits_detail_key():
    env = _err_envelope("cap", "1.0.0", ErrorKind.INPUT_INVALID, "boom")
    assert env["error"]["kind"] == "input_invalid"
    assert env["error"]["message"] == "boom"
    assert "detail" not in env["error"]


def test_err_envelope_with_detail_includes_detail_dict():
    env = _err_envelope(
        "cap", "1.0.0", ErrorKind.INPUT_INVALID, "boom",
        detail={"field": "--feature-id", "rule_violated": "identifier_format",
                "value_redacted": "bad/value"},
    )
    assert env["error"]["detail"] == {
        "field": "--feature-id",
        "rule_violated": "identifier_format",
        "value_redacted": "bad/value",
    }
