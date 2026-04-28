from __future__ import annotations

import pytest

from orca.cli_output import (
    render_error_block,
    render_metadata_footer,
    render_review_code_markdown,
    render_review_pr_markdown,
    render_review_spec_markdown,
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


_CROSS_AGENT_REVIEW_ENVELOPE = {
    "ok": True,
    "result": {
        "findings": [
            {
                "id": "0123456789abcdef",
                "category": "correctness",
                "severity": "high",
                "confidence": "high",
                "summary": "Off-by-one in loop",
                "detail": "range(n) skips the last element.",
                "evidence": ["src/foo.py:42"],
                "suggestion": "Use range(n+1)",
                "reviewer": "claude",
                "reviewers": ["claude", "codex"],
            }
        ],
        "partial": False,
        "missing_reviewers": [],
        "reviewer_metadata": {"claude": {}, "codex": {}},
    },
    "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 4567},
}


def test_render_review_spec_includes_round_header():
    out = render_review_spec_markdown(
        _CROSS_AGENT_REVIEW_ENVELOPE, round_num=1, feature_id="001-example",
    )
    assert "### Round 1 - Cross-Pass" in out
    assert "001-example" in out
    assert "Off-by-one in loop" in out
    assert "[high]" in out


def test_render_review_spec_no_findings():
    envelope = {
        "ok": True,
        "result": {"findings": [], "partial": False, "missing_reviewers": [], "reviewer_metadata": {}},
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 100},
    }
    out = render_review_spec_markdown(envelope, round_num=2, feature_id="x")
    assert "### Round 2 - Cross-Pass" in out
    assert "no findings" in out.lower()


def test_render_review_spec_partial_surfaces_missing():
    envelope = {
        "ok": True,
        "result": {
            "findings": [],
            "partial": True,
            "missing_reviewers": ["codex"],
            "reviewer_metadata": {"claude": {}},
        },
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 1000},
    }
    out = render_review_spec_markdown(envelope, round_num=1, feature_id="x")
    assert "partial" in out.lower()
    assert "codex" in out


def test_render_review_spec_failure_uses_error_block():
    envelope = {
        "ok": False,
        "error": {"kind": "backend_failure", "message": "all reviewers failed"},
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 1000},
    }
    out = render_review_spec_markdown(envelope, round_num=1, feature_id="x")
    assert "### Round 1 - FAILED" in out
    assert "all reviewers failed" in out


def test_render_review_code_groups_by_severity():
    envelope = {
        "ok": True,
        "result": {
            "findings": [
                {
                    "id": "aaa", "category": "c", "severity": "blocker",
                    "confidence": "high", "summary": "blocker thing",
                    "detail": "d", "evidence": ["x:1"], "suggestion": "s",
                    "reviewer": "claude", "reviewers": ["claude"],
                },
                {
                    "id": "bbb", "category": "c", "severity": "low",
                    "confidence": "high", "summary": "low thing",
                    "detail": "d", "evidence": ["x:2"], "suggestion": "s",
                    "reviewer": "codex", "reviewers": ["codex"],
                },
            ],
            "partial": False, "missing_reviewers": [], "reviewer_metadata": {},
        },
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 100},
    }
    out = render_review_code_markdown(envelope, round_num=1, feature_id="001-x")
    # Severity grouping: blockers before lows
    blocker_idx = out.index("blocker thing")
    low_idx = out.index("low thing")
    assert blocker_idx < low_idx
    # Tier headers present
    assert "#### Blocker" in out


def test_render_review_pr_has_disposition_table():
    envelope = {
        "ok": True,
        "result": {
            "findings": [
                {
                    "id": "abc", "category": "c", "severity": "medium",
                    "confidence": "high", "summary": "a comment",
                    "detail": "d", "evidence": ["x:1"], "suggestion": "s",
                    "reviewer": "claude", "reviewers": ["claude"],
                }
            ],
            "partial": False, "missing_reviewers": [], "reviewer_metadata": {},
        },
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 100},
    }
    out = render_review_pr_markdown(envelope, round_num=1, feature_id="001-x")
    # Pipe-separated columns present (markdown table)
    assert "| id |" in out or "| Severity |" in out
    assert "abc" in out


def test_render_review_spec_handles_unicode_in_summary():
    """Unicode (smart quotes, CJK, em-dash from LLM output) passes through cleanly."""
    envelope = {
        "ok": True,
        "result": {
            "findings": [{
                "id": "abc1234567890def",
                "category": "c",
                "severity": "high",
                "confidence": "high",
                "summary": "spec uses “smart” quotes — and CJK 中文",
                "detail": "d",
                "evidence": [],
                "suggestion": "s",
                "reviewer": "claude",
                "reviewers": ["claude"],
            }],
            "partial": False, "missing_reviewers": [], "reviewer_metadata": {},
        },
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 100},
    }
    out = render_review_spec_markdown(envelope, round_num=1, feature_id="x")
    assert "“smart”" in out
    assert "中文" in out


def test_render_review_pr_escapes_newlines_in_summary():
    """Multi-line summary collapses to single line so table doesn't corrupt."""
    envelope = {
        "ok": True,
        "result": {
            "findings": [{
                "id": "abc",
                "category": "c",
                "severity": "high",
                "confidence": "high",
                "summary": "line one\nline two",
                "detail": "d",
                "evidence": [],
                "suggestion": "s",
                "reviewer": "claude",
                "reviewers": ["claude"],
            }],
            "partial": False, "missing_reviewers": [], "reviewer_metadata": {},
        },
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 100},
    }
    out = render_review_pr_markdown(envelope, round_num=1, feature_id="x")
    # Find the table row containing this finding's id
    row = next(line for line in out.splitlines() if line.startswith("| abc |"))
    # Newline collapsed to space; row stays a single line
    assert "line one line two" in row
    assert "\n" not in row


def _populated_cross_agent_envelope() -> dict:
    return {
        "ok": True,
        "result": {
            "findings": [
                {
                    "id": "aaa", "category": "c", "severity": "blocker",
                    "confidence": "high", "summary": "blocker thing",
                    "detail": "d", "evidence": ["x:1"], "suggestion": "s",
                    "reviewer": "claude", "reviewers": ["claude"],
                },
                {
                    "id": "bbb", "category": "c", "severity": "high",
                    "confidence": "high", "summary": "high thing",
                    "detail": "d", "evidence": ["x:2"], "suggestion": "s",
                    "reviewer": "codex", "reviewers": ["codex"],
                },
            ],
            "partial": False, "missing_reviewers": [], "reviewer_metadata": {},
        },
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 100},
    }


def _assert_no_double_blank_before_footer(out: str):
    """No two consecutive blank lines anywhere in the rendered output.

    Catches whitespace regressions where a renderer accidentally appends
    a stray blank between sections.
    """
    lines = out.split("\n")
    for i in range(len(lines) - 1):
        if lines[i] == "" and lines[i + 1] == "":
            raise AssertionError(
                f"double blank at lines {i}-{i + 1} in:\n{out!r}"
            )


def test_render_review_spec_no_double_blank_populated():
    out = render_review_spec_markdown(
        _populated_cross_agent_envelope(), round_num=1, feature_id="x",
    )
    _assert_no_double_blank_before_footer(out)


def test_render_review_code_no_double_blank_populated():
    """Regression: per-severity loop used to append a trailing blank that
    collided with the unconditional pre-footer blank."""
    out = render_review_code_markdown(
        _populated_cross_agent_envelope(), round_num=1, feature_id="x",
    )
    _assert_no_double_blank_before_footer(out)


def test_render_review_pr_no_double_blank_populated():
    out = render_review_pr_markdown(
        _populated_cross_agent_envelope(), round_num=1, feature_id="x",
    )
    _assert_no_double_blank_before_footer(out)
    assert "\n" not in row
