from __future__ import annotations

import pytest

from orca.cli_output import (
    render_error_block,
    render_metadata_footer,
)


def test_render_error_block_input_invalid():
    envelope = {
        "ok": False,
        "error": {
            "kind": "input_invalid",
            "message": "feature_dir does not exist: /nope",
        },
        "metadata": {"capability": "completion-gate", "version": "0.1.0", "duration_ms": 0},
    }
    out = render_error_block(envelope, round_num=2)
    assert "### Round 2 - FAILED" in out
    assert "kind: input_invalid" in out
    assert "feature_dir does not exist" in out


def test_render_error_block_with_detail():
    envelope = {
        "ok": False,
        "error": {
            "kind": "backend_failure",
            "message": "claude failed",
            "detail": {"underlying": "RateLimitError", "retryable": True},
        },
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 1234},
    }
    out = render_error_block(envelope, round_num=1)
    assert "### Round 1 - FAILED" in out
    assert "kind: backend_failure" in out
    assert "underlying: RateLimitError" in out
    assert "retryable: True" in out


def test_render_metadata_footer():
    envelope = {
        "ok": True,
        "result": {},
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 4567},
    }
    out = render_metadata_footer(envelope)
    assert "_capability: cross-agent-review" in out
    assert "_duration: 4567ms" in out
    assert "_version: 0.1.0" in out


def test_render_error_block_round_zero():
    """Round 0 is allowed (first attempt before append)."""
    envelope = {
        "ok": False,
        "error": {"kind": "input_invalid", "message": "missing"},
        "metadata": {"capability": "x", "version": "0", "duration_ms": 0},
    }
    out = render_error_block(envelope, round_num=0)
    assert "### Round 0 - FAILED" in out


def test_render_error_block_rejects_ok_envelope():
    """render_error_block is for failures only; Ok envelope must raise."""
    envelope = {
        "ok": True,
        "result": {},
        "metadata": {"capability": "x", "version": "0", "duration_ms": 0},
    }
    with pytest.raises(ValueError, match="failure envelope"):
        render_error_block(envelope, round_num=1)


def test_render_error_block_detail_diagnosis_order():
    """`underlying` should appear BEFORE `retryable` (diagnosis-first ordering)."""
    envelope = {
        "ok": False,
        "error": {
            "kind": "backend_failure",
            "message": "rate limited",
            "detail": {"retryable": True, "underlying": "RateLimitError", "after_seconds": 30},
        },
        "metadata": {"capability": "x", "version": "0", "duration_ms": 0},
    }
    out = render_error_block(envelope, round_num=1)
    underlying_idx = out.index("underlying:")
    retryable_idx = out.index("retryable:")
    after_idx = out.index("after_seconds:")
    assert underlying_idx < retryable_idx < after_idx, (
        "diagnosis-order: underlying -> retryable -> after_seconds"
    )


def test_render_error_block_unknown_detail_keys_sorted_alphabetically():
    """Unknown keys (not in _DETAIL_ORDER) fall back to alphabetical sort."""
    envelope = {
        "ok": False,
        "error": {
            "kind": "internal",
            "message": "boom",
            "detail": {"zzz_field": "z", "aaa_field": "a"},
        },
        "metadata": {"capability": "x", "version": "0", "duration_ms": 0},
    }
    out = render_error_block(envelope, round_num=1)
    aaa_idx = out.index("aaa_field:")
    zzz_idx = out.index("zzz_field:")
    assert aaa_idx < zzz_idx


def test_render_metadata_footer_preserves_two_space_breaks():
    """Markdown hard breaks require trailing two spaces; CommonMark spec.

    A future 'helpful' whitespace strip would break rendering.
    """
    envelope = {
        "ok": True,
        "result": {},
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 100},
    }
    out = render_metadata_footer(envelope)
    assert "_capability: cross-agent-review_  \n" in out
    assert "_version: 0.1.0_  \n" in out
