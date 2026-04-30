from __future__ import annotations

import io
import json

import pytest

from orca.cli_output import (
    main as cli_output_main,
    render_citation_markdown,
    render_completion_gate_markdown,
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
                "summary": "spec uses “smart” quotes - and CJK 中文",
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


def test_render_completion_gate_pass():
    envelope = {
        "ok": True,
        "result": {
            "status": "pass",
            "gates_evaluated": [
                {"gate": "spec_exists", "passed": True, "reason": ""},
                {"gate": "no_unclarified", "passed": True, "reason": ""},
            ],
            "blockers": [],
            "stale_artifacts": [],
        },
        "metadata": {"capability": "completion-gate", "version": "0.1.0", "duration_ms": 50},
    }
    out = render_completion_gate_markdown(envelope, target_stage="plan-ready")
    assert "## Completion Gate: plan-ready" in out
    assert "Status: **pass**" in out
    assert "spec_exists" in out
    assert "✓" in out


def test_render_completion_gate_blocked():
    envelope = {
        "ok": True,
        "result": {
            "status": "blocked",
            "gates_evaluated": [
                {"gate": "spec_exists", "passed": False, "reason": ""},
                {"gate": "no_unclarified", "passed": False, "reason": "spec.md missing"},
            ],
            "blockers": ["spec_exists", "no_unclarified"],
            "stale_artifacts": [],
        },
        "metadata": {"capability": "completion-gate", "version": "0.1.0", "duration_ms": 50},
    }
    out = render_completion_gate_markdown(envelope, target_stage="plan-ready")
    assert "Status: **blocked**" in out
    assert "spec_exists" in out
    # blocker reasons surfaced
    assert "spec.md missing" in out
    assert "✗" in out


def test_render_completion_gate_stale():
    envelope = {
        "ok": True,
        "result": {
            "status": "stale",
            "gates_evaluated": [],
            "blockers": [],
            "stale_artifacts": ["spec.md"],
        },
        "metadata": {"capability": "completion-gate", "version": "0.1.0", "duration_ms": 50},
    }
    out = render_completion_gate_markdown(envelope, target_stage="plan-ready")
    assert "Status: **stale**" in out
    assert "spec.md" in out


def test_render_completion_gate_failure():
    envelope = {
        "ok": False,
        "error": {"kind": "input_invalid", "message": "feature_dir does not exist"},
        "metadata": {"capability": "completion-gate", "version": "0.1.0", "duration_ms": 0},
    }
    out = render_completion_gate_markdown(envelope, target_stage="plan-ready")
    # Re-uses error block (round 0 since it's a single-shot, not appended round)
    assert "FAILED" in out
    assert "feature_dir does not exist" in out


def test_render_citation_full_coverage():
    envelope = {
        "ok": True,
        "result": {
            "uncited_claims": [],
            "broken_refs": [],
            "well_supported_claims": [
                {"text": "Tests prove [evidence].", "line": 3},
            ],
            "citation_coverage": 1.0,
        },
        "metadata": {"capability": "citation-validator", "version": "0.1.0", "duration_ms": 30},
    }
    out = render_citation_markdown(envelope, content_path="synthesis.md")
    assert "## Citation Report: synthesis.md" in out
    assert "Coverage: **100%**" in out
    assert "Tests prove" in out


def test_render_citation_with_uncited_and_broken():
    envelope = {
        "ok": True,
        "result": {
            "uncited_claims": [{"text": "Results show 42% gain.", "line": 1}],
            "broken_refs": [{"ref": "missing-doc", "line": 2}],
            "well_supported_claims": [],
            "citation_coverage": 0.5,
        },
        "metadata": {"capability": "citation-validator", "version": "0.1.0", "duration_ms": 30},
    }
    out = render_citation_markdown(envelope, content_path="synthesis.md")
    assert "Coverage: **50%**" in out
    assert "### Uncited Claims" in out
    assert "line 1" in out
    assert "### Broken Refs" in out
    assert "missing-doc" in out


def test_render_citation_failure():
    envelope = {
        "ok": False,
        "error": {"kind": "input_invalid", "message": "content_path does not exist: /nope"},
        "metadata": {"capability": "citation-validator", "version": "0.1.0", "duration_ms": 0},
    }
    out = render_citation_markdown(envelope, content_path="/nope")
    assert "FAILED" in out
    assert "content_path does not exist" in out


def test_render_completion_gate_no_double_blank_populated():
    """Same whitespace invariant as review renderers."""
    envelope = {
        "ok": True,
        "result": {
            "status": "blocked",
            "gates_evaluated": [{"gate": "spec_exists", "passed": False, "reason": "missing"}],
            "blockers": ["spec_exists"],
            "stale_artifacts": ["spec.md"],
        },
        "metadata": {"capability": "completion-gate", "version": "0.1.0", "duration_ms": 50},
    }
    out = render_completion_gate_markdown(envelope, target_stage="plan-ready")
    _assert_no_double_blank_before_footer(out)


@pytest.mark.parametrize("present", [
    {"gates_evaluated": [{"gate": "g1", "passed": False, "reason": "x"}], "blockers": [], "stale_artifacts": []},
    {"gates_evaluated": [], "blockers": ["b1"], "stale_artifacts": []},
    {"gates_evaluated": [], "blockers": [], "stale_artifacts": ["s1"]},
])
def test_render_completion_gate_no_double_blank_partial(present):
    envelope = {
        "ok": True,
        "result": {"status": "blocked", **present},
        "metadata": {"capability": "completion-gate", "version": "0.1.0", "duration_ms": 0},
    }
    _assert_no_double_blank_before_footer(render_completion_gate_markdown(envelope, target_stage="x"))


def test_render_citation_no_double_blank_populated():
    envelope = {
        "ok": True,
        "result": {
            "uncited_claims": [{"text": "Results show 42% gain.", "line": 1}],
            "broken_refs": [{"ref": "missing-doc", "line": 2}],
            "well_supported_claims": [{"text": "Tests prove [e].", "line": 3}],
            "citation_coverage": 0.66,
        },
        "metadata": {"capability": "citation-validator", "version": "0.1.0", "duration_ms": 30},
    }
    out = render_citation_markdown(envelope, content_path="synthesis.md")
    _assert_no_double_blank_before_footer(out)


def test_main_lists_render_subcommands_with_help(capsys):
    rc = cli_output_main(["--help"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "render-review-spec" in out
    assert "render-completion-gate" in out


def test_main_render_review_spec_from_stdin(monkeypatch, capsys):
    payload = json.dumps({
        "ok": True,
        "result": {"findings": [], "partial": False, "missing_reviewers": [], "reviewer_metadata": {}},
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 100},
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    rc = cli_output_main(["render-review-spec", "--feature-id", "001-x", "--round", "1"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "### Round 1 - Cross-Pass (001-x)" in out


def test_main_render_completion_gate_from_envelope_file(tmp_path, capsys):
    payload = {
        "ok": True,
        "result": {
            "status": "pass",
            "gates_evaluated": [{"gate": "spec_exists", "passed": True, "reason": ""}],
            "blockers": [],
            "stale_artifacts": [],
        },
        "metadata": {"capability": "completion-gate", "version": "0.1.0", "duration_ms": 50},
    }
    env_file = tmp_path / "env.json"
    env_file.write_text(json.dumps(payload))
    rc = cli_output_main([
        "render-completion-gate",
        "--target-stage", "plan-ready",
        "--envelope-file", str(env_file),
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "## Completion Gate: plan-ready" in out
    assert "Status: **pass**" in out


def test_main_render_citation_with_inline_path(monkeypatch, capsys):
    payload = json.dumps({
        "ok": True,
        "result": {
            "uncited_claims": [],
            "broken_refs": [],
            "well_supported_claims": [],
            "citation_coverage": 1.0,
        },
        "metadata": {"capability": "citation-validator", "version": "0.1.0", "duration_ms": 30},
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    rc = cli_output_main([
        "render-citation",
        "--content-path", "synthesis.md",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "## Citation Report: synthesis.md" in out


def test_main_render_unknown_subcommand_exits_3(capsys):
    rc = cli_output_main(["render-banana"])
    assert rc == 3


def test_main_render_with_invalid_json_exits_1(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("{not-json}"))
    rc = cli_output_main(["render-review-spec", "--feature-id", "x", "--round", "1"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "invalid JSON" in err.lower() or "could not parse" in err.lower()


def test_main_missing_envelope_file_exits_1(capsys):
    rc = cli_output_main([
        "render-review-spec",
        "--feature-id", "x",
        "--round", "1",
        "--envelope-file", "/does/not/exist.json",
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "could not read envelope file" in err.lower()


def test_main_missing_required_arg_exits_2():
    with pytest.raises(SystemExit) as exc:
        cli_output_main(["render-review-spec"])
    assert exc.value.code == 2


def test_main_failure_envelope_passes_through(monkeypatch, capsys):
    payload = json.dumps({
        "ok": False,
        "error": {
            "kind": "BACKEND_FAILURE",
            "message": "reviewer timeout",
            "detail": {"underlying": "timeout"},
        },
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 5000},
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    rc = cli_output_main(["render-review-spec", "--feature-id", "001-x", "--round", "2"])
    out = capsys.readouterr().out
    assert rc == 0  # dispatcher always exits 0 on a parsed envelope; failure renders into markdown
    assert "FAILED" in out
    assert "BACKEND_FAILURE" in out


# ---- Citation coverage rounding (review-code Fix 1) ------------------------


def test_render_citation_floors_almost_full_coverage():
    """0.999 must NOT render as 100% - the operator would miss listed uncited claims."""
    envelope = {
        "ok": True,
        "result": {
            "uncited_claims": [{"text": "X says Y", "line": 1}],
            "broken_refs": [],
            "well_supported_claims": [],
            "citation_coverage": 0.999,
        },
        "metadata": {"capability": "citation-validator", "version": "0.1.0", "duration_ms": 10},
    }
    out = render_citation_markdown(envelope, content_path="x.md")
    assert "Coverage: **99%**" in out
    assert "Coverage: **100%**" not in out


def test_render_citation_full_coverage_is_100_percent():
    envelope = {
        "ok": True,
        "result": {
            "uncited_claims": [],
            "broken_refs": [],
            "well_supported_claims": [],
            "citation_coverage": 1.0,
        },
        "metadata": {"capability": "citation-validator", "version": "0.1.0", "duration_ms": 10},
    }
    out = render_citation_markdown(envelope, content_path="x.md")
    assert "Coverage: **100%**" in out


def test_render_citation_partial_coverage_floors():
    """0.66 -> 66%, 0.5 -> 50% (sanity check existing partial values still work)."""
    for cov, expected in ((0.5, "50%"), (0.66, "66%"), (0.0, "0%")):
        envelope = {
            "ok": True,
            "result": {
                "uncited_claims": [],
                "broken_refs": [],
                "well_supported_claims": [],
                "citation_coverage": cov,
            },
            "metadata": {"capability": "citation-validator", "version": "0.1.0", "duration_ms": 10},
        }
        out = render_citation_markdown(envelope, content_path="x.md")
        assert f"Coverage: **{expected}**" in out, f"coverage={cov}"


# ---- Unknown severity (review-code Fix 2) ----------------------------------


def test_render_review_code_does_not_drop_unknown_severity():
    """Findings with severity outside _SEVERITY_ORDER must surface under "Other"."""
    envelope = {
        "ok": True,
        "result": {
            "findings": [
                {
                    "id": "abc1234567890def", "category": "c", "severity": "blocker",
                    "confidence": "high", "summary": "real blocker", "detail": "",
                    "evidence": [], "suggestion": "", "reviewer": "claude",
                    "reviewers": ["claude"],
                },
                {
                    "id": "xyz9876543210abc", "category": "c", "severity": "BLOCKER",
                    "confidence": "high", "summary": "uppercase severity slipped through",
                    "detail": "", "evidence": [], "suggestion": "", "reviewer": "claude",
                    "reviewers": ["claude"],
                },
                {
                    "id": "def4567890abcdef", "category": "c", "severity": "?",
                    "confidence": "high", "summary": "missing severity default",
                    "detail": "", "evidence": [], "suggestion": "", "reviewer": "claude",
                    "reviewers": ["claude"],
                },
            ],
            "partial": False, "missing_reviewers": [], "reviewer_metadata": {},
        },
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 100},
    }
    out = render_review_code_markdown(envelope, round_num=1, feature_id="001-x")
    assert "#### Blocker" in out
    assert "real blocker" in out
    # The two unknown-severity findings must appear under Other
    assert "#### Other" in out
    assert "uppercase severity slipped through" in out
    assert "missing severity default" in out


# ---- Markdown sanitizer (review-code Fix 5) --------------------------------


def test_render_review_code_collapses_newlines_in_summary():
    """A finding summary with embedded newlines must not break list structure."""
    envelope = {
        "ok": True,
        "result": {
            "findings": [{
                "id": "abc1234567890def",
                "category": "c",
                "severity": "high",
                "confidence": "high",
                "summary": "line one\n## injected heading\n- injected list",
                "detail": "",
                "evidence": [],
                "suggestion": "",
                "reviewer": "claude",
                "reviewers": ["claude"],
            }],
            "partial": False,
            "missing_reviewers": [],
            "reviewer_metadata": {},
        },
        "metadata": {"capability": "cross-agent-review", "version": "0.1.0", "duration_ms": 100},
    }
    out = render_review_code_markdown(envelope, round_num=1, feature_id="001-x")
    # The injected "## " must NOT appear at line-start anywhere in the body
    assert "\n## injected heading" not in out
    # The injected "- " must NOT appear at line-start anywhere in the body
    assert "\n- injected list" not in out
    # The summary content is preserved (collapsed to one line)
    assert "line one" in out
    assert "injected heading" in out  # still present, just inline


def test_render_citation_collapses_newlines_in_claim_text():
    envelope = {
        "ok": True,
        "result": {
            "uncited_claims": [{"text": "Claim with\n## injected heading", "line": 1}],
            "broken_refs": [],
            "well_supported_claims": [],
            "citation_coverage": 0.0,
        },
        "metadata": {"capability": "citation-validator", "version": "0.1.0", "duration_ms": 10},
    }
    out = render_citation_markdown(envelope, content_path="x.md")
    assert "\n## injected heading" not in out


def test_render_error_block_collapses_newlines_in_message():
    envelope = {
        "ok": False,
        "error": {"kind": "BACKEND_FAILURE", "message": "first line\nsecond line", "detail": {}},
        "metadata": {"capability": "x", "version": "0.1.0", "duration_ms": 0},
    }
    out = render_error_block(envelope, round_num=1)
    # Message must not break the bullet list structure
    assert "\nsecond line" not in out
    assert "first line" in out
    assert "second line" in out


def test_render_metadata_footer_subms_duration_shows_decimal():
    envelope = {
        "ok": True,
        "result": {"findings": [], "partial": False, "missing_reviewers": [], "reviewer_metadata": {}},
        "metadata": {"capability": "x", "version": "0.1.0", "duration_ms": 0.3},
    }
    out = render_review_spec_markdown(envelope, round_num=1, feature_id="x")
    assert "_duration: 0.3ms_" in out


def test_render_metadata_footer_above_one_ms_shows_integer():
    envelope = {
        "ok": True,
        "result": {"findings": [], "partial": False, "missing_reviewers": [], "reviewer_metadata": {}},
        "metadata": {"capability": "x", "version": "0.1.0", "duration_ms": 5.7},
    }
    out = render_review_spec_markdown(envelope, round_num=1, feature_id="x")
    assert "_duration: 5ms_" in out  # truncates to int for clean display


def test_render_metadata_footer_int_zero_still_shows_zero():
    """Backward compat: legacy envelopes with int duration_ms still render."""
    envelope = {
        "ok": True,
        "result": {"findings": [], "partial": False, "missing_reviewers": [], "reviewer_metadata": {}},
        "metadata": {"capability": "x", "version": "0.1.0", "duration_ms": 0},
    }
    out = render_review_spec_markdown(envelope, round_num=1, feature_id="x")
    assert "_duration: 0ms_" in out
