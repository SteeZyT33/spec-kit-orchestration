# Orca Phase 3: Plugin Formats + SDD Opinion-Layer Slash Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Phase 2 capability layer into the personal SDD opinion-layer slash commands and ship a Codex consumption surface, so `/orca:review-code` etc. actually invoke the capability layer instead of describing it.

**Architecture:** A new `src/orca/cli_output.py` module exposes per-artifact markdown renderers (`render_review_spec`, `render_review_code`, `render_review_pr`, `render_completion_gate`, `render_citation`) plus a `python -m orca.cli_output render-{type}` CLI surface. Slash commands shell to `orca-cli <capability>` to get JSON envelopes, pipe them through `python -m orca.cli_output render-{type}` to get markdown, then append to artifacts. Codex consumes orca via a single `plugins/codex/AGENTS.md` pointer doc.

**Tech Stack:** Python 3.10+, no new runtime deps (uses stdlib only for the renderer module). Markdown shapes are append-friendly (idempotent round-N headers). Tests use snapshot-style assertions on rendered markdown.

**Starting state:** Phase 2 has landed (PR #69). 346 tests passing. `orca-cli` exposes 6 capability subcommands. Existing slash commands describe workflows but do not invoke the capability layer. `extension.yml` registers 5 commands; `orca-main.sh:generate_extension_skills` auto-wraps any `plugins/claude-code/commands/*.md` into a SKILL.md so new commands are picked up automatically.

---

## File Structure

### New files

- `src/orca/cli_output.py` — five markdown renderers + module CLI dispatcher
- `tests/cli/test_cli_output.py` — renderer unit tests
- `plugins/claude-code/commands/gate.md` — new `/orca:gate` slash command
- `plugins/claude-code/commands/cite.md` — new `/orca:cite` slash command
- `plugins/codex/AGENTS.md` — Codex-side capability pointer doc
- `tests/cli/test_codex_agents_md.py` — verifies the Codex doc lists every `orca-cli --list` capability

### Modified files

- `plugins/claude-code/commands/review-spec.md` — rewire to `orca-cli cross-agent-review --kind spec`
- `plugins/claude-code/commands/review-code.md` — rewire to `orca-cli cross-agent-review --kind diff`
- `plugins/claude-code/commands/review-pr.md` — rewire to `orca-cli cross-agent-review --kind pr`
- `extension.yml` — register `orca:gate` and `orca:cite` commands

### Why this layout

- `cli_output.py` is one focused module (~200 lines target) because the 5 renderers share envelope-handling helpers (header rendering, error block rendering, metadata footer). Splitting them into separate files would duplicate the helpers.
- Slash command markdown stays in `plugins/claude-code/commands/` — Phase 1's `generate_extension_skills` already picks up files from there.
- Codex AGENTS.md lives in `plugins/codex/` (new dir) so it's discoverable alongside the Claude Code plugin assets.
- Renderer tests live under `tests/cli/` (alongside `test_python_cli.py` and `test_schema_validation.py`) since they exercise the wire-format boundary.

---

## Task 1: cli_output module skeleton + error rendering

**Why first:** Every renderer needs the shared error-block format and header convention. Building these once with tests prevents the per-renderer duplication.

**Files:**
- Create: `src/orca/cli_output.py`
- Create: `tests/cli/test_cli_output.py`

- [ ] **Step 1: Write failing tests for shared helpers**

```python
# tests/cli/test_cli_output.py
from __future__ import annotations

import json

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
    assert "### Round 2 — FAILED" in out
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
    assert "### Round 1 — FAILED" in out
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
    assert "### Round 0 — FAILED" in out
```

- [ ] **Step 2: Verify failure**

Run: `uv run python -m pytest tests/cli/test_cli_output.py -v`
Expected: ImportError on `orca.cli_output`.

(Use `uv run python -m pytest`, NOT `uv run pytest`.)

- [ ] **Step 3: Implement skeleton + helpers**

```python
# src/orca/cli_output.py
"""Markdown renderers for orca-cli capability outputs.

Slash commands shell to `orca-cli <capability>` for JSON envelopes,
then pipe through `python -m orca.cli_output render-{type}` to get
the markdown that appends to the on-disk artifact.

This module is the boundary between machine-readable JSON contracts
and operator-readable markdown artifacts. Slash commands stay
declarative; capability output stays JSON; this module translates.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def render_error_block(envelope: dict[str, Any], *, round_num: int) -> str:
    """Render a failure envelope as a Round-N labeled markdown block.

    Common to all artifact renderers. Includes ErrorKind, message, and
    detail block (underlying + retryable when present).
    """
    err = envelope.get("error", {})
    kind = err.get("kind", "unknown")
    message = err.get("message", "(no message)")
    detail = err.get("detail") or {}

    lines = [
        f"### Round {round_num} — FAILED",
        "",
        f"- kind: {kind}",
        f"- message: {message}",
    ]
    for key, value in sorted(detail.items()):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append(render_metadata_footer(envelope))
    return "\n".join(lines)


def render_metadata_footer(envelope: dict[str, Any]) -> str:
    """Render the trailing metadata block all artifacts share."""
    meta = envelope.get("metadata", {})
    capability = meta.get("capability", "?")
    version = meta.get("version", "?")
    duration_ms = meta.get("duration_ms", 0)
    return (
        f"_capability: {capability}_  \n"
        f"_version: {version}_  \n"
        f"_duration: {duration_ms}ms_"
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: `python -m orca.cli_output render-{type} ...`.

    Wired up in Task 4. Skeleton here so the module is importable.
    """
    parser = argparse.ArgumentParser(prog="python -m orca.cli_output")
    parser.add_argument("subcommand", nargs="?", help="render-{type}")
    args, _ = parser.parse_known_args(argv if argv is not None else sys.argv[1:])
    if args.subcommand is None:
        parser.print_help()
        return 0
    print(f"unknown subcommand: {args.subcommand}", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run python -m pytest tests/cli/test_cli_output.py -v`
Expected: 4 PASS.

Then full suite: `uv run python -m pytest -q`
Expected: 350 (346 + 4) PASS.

- [ ] **Step 5: Commit**

```bash
git add src/orca/cli_output.py tests/cli/test_cli_output.py
git commit -m "feat(cli_output): module skeleton + shared error/metadata renderers"
```

---

## Task 2: review-spec / review-code / review-pr renderers

**Why grouped:** All three consume the same `cross-agent-review` envelope (`{findings, partial, missing_reviewers, reviewer_metadata}`). The output markdown shape differs per artifact (review-spec is concise; review-code has tier maps; review-pr has comment-disposition columns), but the input shape is identical. Sharing context.

**Files:**
- Modify: `src/orca/cli_output.py`
- Modify: `tests/cli/test_cli_output.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/cli/test_cli_output.py`:

```python
from orca.cli_output import (
    render_review_spec_markdown,
    render_review_code_markdown,
    render_review_pr_markdown,
)


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
    assert "### Round 1 — Cross-Pass" in out
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
    assert "### Round 2 — Cross-Pass" in out
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
    assert "### Round 1 — FAILED" in out
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
    assert "#### Blocker" in out or "#### blocker" in out.lower()


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
```

(6 new tests covering review-spec, review-code, review-pr renderers.)

- [ ] **Step 2: Verify failure**

Run: `uv run python -m pytest tests/cli/test_cli_output.py -v`
Expected: 4 PASS (existing) + 6 ImportError on the 3 new render functions.

- [ ] **Step 3: Implement renderers**

Append to `src/orca/cli_output.py`:

```python
def _severity_rank(severity: str) -> int:
    return {"blocker": 0, "high": 1, "medium": 2, "low": 3, "nit": 4}.get(severity, 99)


def _findings_sorted(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(findings, key=lambda f: (_severity_rank(f.get("severity", "nit")), f.get("id", "")))


def _render_finding_oneline(f: dict[str, Any]) -> str:
    severity = f.get("severity", "?")
    summary = f.get("summary", "?")
    evidence = ", ".join(f.get("evidence", []))
    reviewers = "+".join(f.get("reviewers", []))
    suffix = f" ({reviewers})" if reviewers else ""
    line = f"- [{severity}] {summary}"
    if evidence:
        line += f" — {evidence}"
    return line + suffix


def _render_partial_note(envelope: dict[str, Any]) -> str:
    result = envelope.get("result", {})
    if not result.get("partial"):
        return ""
    missing = result.get("missing_reviewers", [])
    return f"\n_partial run: missing reviewers = {', '.join(missing)}_\n"


def render_review_spec_markdown(
    envelope: dict[str, Any], *, round_num: int, feature_id: str,
) -> str:
    """Render a cross-agent-review envelope as a review-spec.md round block."""
    if not envelope.get("ok"):
        return render_error_block(envelope, round_num=round_num)

    result = envelope.get("result", {})
    findings = _findings_sorted(result.get("findings", []))

    lines = [
        f"### Round {round_num} — Cross-Pass ({feature_id})",
        "",
    ]
    if not findings:
        lines.append("_no findings_")
    else:
        for f in findings:
            lines.append(_render_finding_oneline(f))
    partial = _render_partial_note(envelope)
    if partial:
        lines.append(partial)
    lines.append("")
    lines.append(render_metadata_footer(envelope))
    return "\n".join(lines)


def render_review_code_markdown(
    envelope: dict[str, Any], *, round_num: int, feature_id: str,
) -> str:
    """Render a cross-agent-review envelope as a review-code.md round block.

    Groups findings under severity-tier subheadings so operators can scan
    blockers first.
    """
    if not envelope.get("ok"):
        return render_error_block(envelope, round_num=round_num)

    result = envelope.get("result", {})
    findings = _findings_sorted(result.get("findings", []))

    lines = [
        f"### Round {round_num} — Cross-Pass ({feature_id})",
        "",
    ]
    if not findings:
        lines.append("_no findings_")
    else:
        # Group by severity for operator scan-ability
        by_severity: dict[str, list[dict[str, Any]]] = {}
        for f in findings:
            by_severity.setdefault(f.get("severity", "?"), []).append(f)
        for severity in ("blocker", "high", "medium", "low", "nit"):
            group = by_severity.get(severity)
            if not group:
                continue
            lines.append(f"#### {severity.capitalize()}")
            lines.append("")
            for f in group:
                summary = f.get("summary", "?")
                detail = f.get("detail", "")
                evidence = ", ".join(f.get("evidence", []))
                suggestion = f.get("suggestion", "")
                reviewers = "+".join(f.get("reviewers", []))
                lines.append(f"- **{summary}** ({reviewers})")
                if detail:
                    lines.append(f"  - {detail}")
                if evidence:
                    lines.append(f"  - evidence: {evidence}")
                if suggestion:
                    lines.append(f"  - suggestion: {suggestion}")
            lines.append("")

    partial = _render_partial_note(envelope)
    if partial:
        lines.append(partial)
    lines.append(render_metadata_footer(envelope))
    return "\n".join(lines)


def render_review_pr_markdown(
    envelope: dict[str, Any], *, round_num: int, feature_id: str,
) -> str:
    """Render a cross-agent-review envelope as a review-pr.md round block.

    Uses a markdown table so PR-comment dispositions can be tracked next
    to each finding row.
    """
    if not envelope.get("ok"):
        return render_error_block(envelope, round_num=round_num)

    result = envelope.get("result", {})
    findings = _findings_sorted(result.get("findings", []))

    lines = [
        f"### Round {round_num} — Cross-Pass ({feature_id})",
        "",
    ]
    if not findings:
        lines.append("_no findings_")
    else:
        lines.append("| id | Severity | Summary | Reviewers | Disposition |")
        lines.append("|----|----------|---------|-----------|-------------|")
        for f in findings:
            fid = f.get("id", "?")
            severity = f.get("severity", "?")
            summary = f.get("summary", "?").replace("|", "\\|")
            reviewers = "+".join(f.get("reviewers", []))
            lines.append(f"| {fid} | {severity} | {summary} | {reviewers} | _pending_ |")

    partial = _render_partial_note(envelope)
    if partial:
        lines.append(partial)
    lines.append("")
    lines.append(render_metadata_footer(envelope))
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run python -m pytest tests/cli/test_cli_output.py -v`
Expected: 10 PASS (4 prior + 6 new).

Then full suite: `uv run python -m pytest -q`
Expected: 356 (350 + 6) PASS.

- [ ] **Step 5: Commit**

```bash
git add src/orca/cli_output.py tests/cli/test_cli_output.py
git commit -m "feat(cli_output): add review-spec/code/pr markdown renderers"
```

---

## Task 3: completion-gate + citation-validator renderers

**Why grouped:** Different envelope shapes from review-* but similar implementation pattern (success branch + error branch + metadata footer).

**Files:**
- Modify: `src/orca/cli_output.py`
- Modify: `tests/cli/test_cli_output.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/cli/test_cli_output.py`:

```python
from orca.cli_output import (
    render_completion_gate_markdown,
    render_citation_markdown,
)


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
    assert "Coverage: **1.0**" in out
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
    assert "Coverage: **0.5**" in out
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
```

- [ ] **Step 2: Verify failure**

Run: `uv run python -m pytest tests/cli/test_cli_output.py -v`
Expected: 10 PASS (prior) + 7 ImportError on the 2 new renderers.

- [ ] **Step 3: Implement renderers**

Append to `src/orca/cli_output.py`:

```python
def render_completion_gate_markdown(
    envelope: dict[str, Any], *, target_stage: str,
) -> str:
    """Render a completion-gate envelope as a Markdown report.

    Used by /orca:gate slash command. Single-shot (not round-appended);
    operators capture stdout or pipe into gate-history.md.
    """
    if not envelope.get("ok"):
        return render_error_block(envelope, round_num=0)

    result = envelope.get("result", {})
    status = result.get("status", "?")
    gates = result.get("gates_evaluated", [])
    blockers = result.get("blockers", [])
    stale = result.get("stale_artifacts", [])

    lines = [
        f"## Completion Gate: {target_stage}",
        "",
        f"Status: **{status}**",
        "",
        "### Gates",
        "",
    ]
    for g in gates:
        gate = g.get("gate", "?")
        passed = g.get("passed", False)
        reason = g.get("reason", "")
        mark = "✓" if passed else "✗"
        line = f"- {mark} `{gate}`"
        if reason:
            line += f" — {reason}"
        lines.append(line)

    if blockers:
        lines.append("")
        lines.append("### Blockers")
        lines.append("")
        for b in blockers:
            lines.append(f"- `{b}`")

    if stale:
        lines.append("")
        lines.append("### Stale Artifacts")
        lines.append("")
        for s in stale:
            lines.append(f"- `{s}`")

    lines.append("")
    lines.append(render_metadata_footer(envelope))
    return "\n".join(lines)


def render_citation_markdown(
    envelope: dict[str, Any], *, content_path: str,
) -> str:
    """Render a citation-validator envelope as a Markdown report.

    Used by /orca:cite slash command. Single-shot (not round-appended).
    """
    if not envelope.get("ok"):
        return render_error_block(envelope, round_num=0)

    result = envelope.get("result", {})
    coverage = result.get("citation_coverage", 0)
    uncited = result.get("uncited_claims", [])
    broken = result.get("broken_refs", [])
    well = result.get("well_supported_claims", [])

    lines = [
        f"## Citation Report: {content_path}",
        "",
        f"Coverage: **{coverage}**",
        "",
        f"- well-supported: {len(well)}",
        f"- uncited: {len(uncited)}",
        f"- broken refs: {len(broken)}",
    ]

    if uncited:
        lines.append("")
        lines.append("### Uncited Claims")
        lines.append("")
        for c in uncited:
            text = c.get("text", "")
            line = c.get("line", "?")
            lines.append(f"- line {line}: {text}")

    if broken:
        lines.append("")
        lines.append("### Broken Refs")
        lines.append("")
        for b in broken:
            ref = b.get("ref", "?")
            line = b.get("line", "?")
            lines.append(f"- line {line}: `[{ref}]`")

    if well:
        lines.append("")
        lines.append("### Well-Supported Claims")
        lines.append("")
        for w in well:
            text = w.get("text", "")
            line = w.get("line", "?")
            lines.append(f"- line {line}: {text}")

    lines.append("")
    lines.append(render_metadata_footer(envelope))
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run python -m pytest tests/cli/test_cli_output.py -v`
Expected: 17 PASS (10 + 7).

Full suite: `uv run python -m pytest -q`
Expected: 363 (356 + 7) PASS.

- [ ] **Step 5: Commit**

```bash
git add src/orca/cli_output.py tests/cli/test_cli_output.py
git commit -m "feat(cli_output): add completion-gate + citation renderers"
```

---

## Task 4: cli_output CLI dispatcher

**Why:** Slash commands shell out and need a CLI surface to feed envelopes into. `python -m orca.cli_output render-{type}` reads JSON from stdin (or `--envelope-file`) and emits markdown to stdout.

**Files:**
- Modify: `src/orca/cli_output.py`
- Modify: `tests/cli/test_cli_output.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/cli/test_cli_output.py`:

```python
import io

from orca.cli_output import main as cli_output_main


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
    assert "### Round 1 — Cross-Pass (001-x)" in out


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
```

- [ ] **Step 2: Verify failure**

Run: `uv run python -m pytest tests/cli/test_cli_output.py -v`
Expected: 17 PASS (prior) + 6 fail/error on the new dispatcher tests.

- [ ] **Step 3: Replace the placeholder `main` in cli_output.py**

Replace the existing `main()` and `if __name__ == "__main__"` block at the bottom of `src/orca/cli_output.py`:

```python
RENDERERS = {
    "render-review-spec": "_render_review_spec_cli",
    "render-review-code": "_render_review_code_cli",
    "render-review-pr": "_render_review_pr_cli",
    "render-completion-gate": "_render_completion_gate_cli",
    "render-citation": "_render_citation_cli",
}


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: `python -m orca.cli_output render-{type} ...`.

    Each render-* subcommand reads a Result envelope from stdin (or
    --envelope-file) and writes markdown to stdout. Exit codes follow
    the universal Result contract:
      0 success, 1 input error (bad JSON), 3 unknown subcommand.
    """
    argv = list(argv) if argv is not None else sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help"):
        _print_help()
        return 0

    subcmd = argv[0]
    if subcmd not in RENDERERS:
        print(f"unknown subcommand: {subcmd}", file=sys.stderr)
        print(f"available: {', '.join(RENDERERS)}", file=sys.stderr)
        return 3

    handler = globals()[RENDERERS[subcmd]]
    return handler(argv[1:])


def _print_help() -> None:
    print("python -m orca.cli_output — render orca-cli envelopes as markdown")
    print()
    print("Usage: python -m orca.cli_output <subcommand> [options]")
    print()
    print("Subcommands:")
    for name in RENDERERS:
        print(f"  {name}")
    print()
    print("Each subcommand reads a Result envelope from stdin or --envelope-file.")


def _read_envelope(envelope_file: str | None) -> dict[str, Any] | None:
    """Read JSON envelope from --envelope-file or stdin. Returns None on parse error."""
    if envelope_file:
        try:
            raw = open(envelope_file, "r", encoding="utf-8").read()
        except OSError as exc:
            print(f"could not read envelope file: {exc}", file=sys.stderr)
            return None
    else:
        raw = sys.stdin.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"invalid JSON: {exc}", file=sys.stderr)
        return None


def _render_review_spec_cli(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m orca.cli_output render-review-spec")
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--envelope-file", default=None)
    ns = parser.parse_args(args)
    envelope = _read_envelope(ns.envelope_file)
    if envelope is None:
        return 1
    print(render_review_spec_markdown(envelope, round_num=ns.round, feature_id=ns.feature_id))
    return 0


def _render_review_code_cli(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m orca.cli_output render-review-code")
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--envelope-file", default=None)
    ns = parser.parse_args(args)
    envelope = _read_envelope(ns.envelope_file)
    if envelope is None:
        return 1
    print(render_review_code_markdown(envelope, round_num=ns.round, feature_id=ns.feature_id))
    return 0


def _render_review_pr_cli(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m orca.cli_output render-review-pr")
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--envelope-file", default=None)
    ns = parser.parse_args(args)
    envelope = _read_envelope(ns.envelope_file)
    if envelope is None:
        return 1
    print(render_review_pr_markdown(envelope, round_num=ns.round, feature_id=ns.feature_id))
    return 0


def _render_completion_gate_cli(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m orca.cli_output render-completion-gate")
    parser.add_argument("--target-stage", required=True)
    parser.add_argument("--envelope-file", default=None)
    ns = parser.parse_args(args)
    envelope = _read_envelope(ns.envelope_file)
    if envelope is None:
        return 1
    print(render_completion_gate_markdown(envelope, target_stage=ns.target_stage))
    return 0


def _render_citation_cli(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m orca.cli_output render-citation")
    parser.add_argument("--content-path", required=True)
    parser.add_argument("--envelope-file", default=None)
    ns = parser.parse_args(args)
    envelope = _read_envelope(ns.envelope_file)
    if envelope is None:
        return 1
    print(render_citation_markdown(envelope, content_path=ns.content_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Update the existing skeleton `main` test**

The skeleton test from Task 1 (`test_render_error_block_*` etc.) is fine. The new tests in Task 4's Step 1 cover the full dispatcher.

Run: `uv run python -m pytest tests/cli/test_cli_output.py -v`
Expected: 23 PASS (17 prior + 6 new).

Full suite: `uv run python -m pytest -q`
Expected: 369 (363 + 6) PASS.

- [ ] **Step 5: Smoke-test the module CLI**

```bash
echo '{"ok":true,"result":{"findings":[],"partial":false,"missing_reviewers":[],"reviewer_metadata":{}},"metadata":{"capability":"cross-agent-review","version":"0.1.0","duration_ms":100}}' | uv run python -m orca.cli_output render-review-spec --feature-id 001-smoke --round 1
```
Expected: `### Round 1 — Cross-Pass (001-smoke)` followed by `_no findings_` and metadata footer.

- [ ] **Step 6: Commit**

```bash
git add src/orca/cli_output.py tests/cli/test_cli_output.py
git commit -m "feat(cli_output): add module CLI dispatcher for renderers"
```

---

## Task 5: Rewire `/orca:review-spec` slash command

**Why:** First of three rewires. review-spec is smallest (55 lines), easiest to inspect post-rewire.

**Files:**
- Modify: `plugins/claude-code/commands/review-spec.md`

- [ ] **Step 1: Read the current file**

Read `plugins/claude-code/commands/review-spec.md` fully. Identify the `## Outline` section that currently describes "Read spec.md... evaluate against criteria... write findings to review-spec.md". This is what gets rewired.

- [ ] **Step 2: Replace the Outline section**

Find the `## Outline` section in `plugins/claude-code/commands/review-spec.md` and replace it with:

```markdown
## Outline

1. Resolve `<feature-dir>` from user input or current branch (e.g., `specs/001-foo/`).

2. Resolve `<feature-id>` (basename of feature dir, e.g., `001-foo`).

3. Determine the next round number: count existing `### Round N — ` headers in `<feature-dir>/review-spec.md` (if it exists), N+1 is the new round; otherwise round 1.

4. Invoke `orca-cli cross-agent-review` against the spec:

   ```bash
   uv run orca-cli cross-agent-review \
     --kind spec \
     --target "<feature-dir>/spec.md" \
     --feature-id "<feature-id>" \
     --reviewer cross \
     --criteria "cross-spec-consistency" \
     --criteria "feasibility" \
     --criteria "security" \
     --criteria "dependencies" \
     --criteria "industry-patterns" \
     > /tmp/orca-review-spec-envelope.json
   ```

   Live mode (real LLM calls) requires `ORCA_LIVE=1`. For dry-run/testing
   set `ORCA_FIXTURE_REVIEWER_CLAUDE` and `ORCA_FIXTURE_REVIEWER_CODEX`
   to JSON fixture paths.

5. Translate the JSON envelope into a markdown round-block:

   ```bash
   uv run python -m orca.cli_output render-review-spec \
     --feature-id "<feature-id>" \
     --round <N> \
     --envelope-file /tmp/orca-review-spec-envelope.json \
     >> "<feature-dir>/review-spec.md"
   ```

6. Read the resulting `review-spec.md` and report verdict to the user:
   - `ready` if the round had no findings
   - `needs-revision` if there are blocker/high findings
   - `blocked` if the envelope was a failure (`ok: false`)

7. If a handoff is appropriate, route via the existing `handoffs` block in this file's frontmatter.
```

- [ ] **Step 3: Verify the file is still valid markdown**

Run: `head -20 plugins/claude-code/commands/review-spec.md`
Expected: frontmatter and `## User Input` section intact at top.

- [ ] **Step 4: Smoke-test against a fixture feature dir**

```bash
mkdir -p /tmp/orca-r3-smoke/specs/001-rewire/{,review-spec-trial}
echo "# Spec" > /tmp/orca-r3-smoke/specs/001-rewire/spec.md
echo '{"reviewer":"claude","raw_findings":[]}' > /tmp/orca-r3-smoke/empty.json
ORCA_FIXTURE_REVIEWER_CLAUDE=/tmp/orca-r3-smoke/empty.json \
ORCA_FIXTURE_REVIEWER_CODEX=/tmp/orca-r3-smoke/empty.json \
uv run orca-cli cross-agent-review \
  --kind spec \
  --target /tmp/orca-r3-smoke/specs/001-rewire/spec.md \
  --feature-id 001-rewire \
  --reviewer cross \
  > /tmp/orca-r3-smoke/env.json
uv run python -m orca.cli_output render-review-spec \
  --feature-id 001-rewire \
  --round 1 \
  --envelope-file /tmp/orca-r3-smoke/env.json
```
Expected: `### Round 1 — Cross-Pass (001-rewire)` with `_no findings_`.

- [ ] **Step 5: Commit**

```bash
git add plugins/claude-code/commands/review-spec.md
git commit -m "feat(slash): rewire /orca:review-spec to call orca-cli"
```

---

## Task 6: Rewire `/orca:review-code` slash command

**Why:** Largest of the three rewires (396 lines). Existing file invokes the legacy `crossreview.sh` backend; replace with `orca-cli cross-agent-review --kind diff`.

**Files:**
- Modify: `plugins/claude-code/commands/review-code.md`

- [ ] **Step 1: Read and identify the rewire surface**

Read `plugins/claude-code/commands/review-code.md` fully. The cross-pass section is around line 130-191 (currently describes `crossreview.sh` invocation). That section gets rewired. Other sections (self-pass, tier maps, conflict resolution, output contract) stay.

- [ ] **Step 2: Replace the cross-pass section (Step 8 in the file)**

Find the section that begins with `8. **MANDATORY: Run the cross-harness cross-pass.**` and ends just before `## Merge Conflict Resolution Protocol`. Replace ONLY that step's body with:

```markdown
8. **MANDATORY: Run the cross-agent-review capability.**

   The self-pass alone is not a complete review-code artifact per 012.

   a. Build the diff for the cross-pass. `$BASE_REF` is the merge-base
      with the target branch (default `main`):

      ```bash
      BASE_REF=$(git merge-base "${ORCA_BASE_BRANCH:-main}" HEAD)
      git diff "$BASE_REF"...HEAD > "$FEATURE_DIR/.cross-pass-patch"
      ```

   b. Determine the next round number from existing `### Round N — `
      headers in `$FEATURE_DIR/review-code.md`. New round = count + 1.

   c. Invoke `orca-cli cross-agent-review` against the diff. Both
      reviewers run by default (`--reviewer cross`):

      ```bash
      uv run orca-cli cross-agent-review \
        --kind diff \
        --target "$FEATURE_DIR/.cross-pass-patch" \
        --feature-id "$(basename $FEATURE_DIR)" \
        --reviewer cross \
        --criteria "correctness" \
        --criteria "security" \
        --criteria "maintainability" \
        > "$FEATURE_DIR/.review-code-envelope.json"
      ```

      Live mode requires `ORCA_LIVE=1`. For dry-run set
      `ORCA_FIXTURE_REVIEWER_CLAUDE` / `_CODEX` to fixture paths.

   d. If the envelope is a failure (`ok: false`), STOP and report it
      as a review-code blocker. Do NOT fall back to a same-agent
      second pass. Same-agent cross-passes are explicitly forbidden
      by the 012 contract.

   e. Translate the envelope into a markdown round-block and append:

      ```bash
      uv run python -m orca.cli_output render-review-code \
        --feature-id "$(basename $FEATURE_DIR)" \
        --round <N> \
        --envelope-file "$FEATURE_DIR/.review-code-envelope.json" \
        >> "$FEATURE_DIR/review-code.md"
      ```

   f. The artifact's `Round N` block contains all findings grouped by
      severity tier (blocker / high / medium / low / nit). Self-pass
      findings stay in their own section above the round-block.

   g. Both passes (self + cross-via-orca) MUST appear in the final
      review-code.md before the artifact is considered complete.
```

(Removes the legacy `crossreview.sh` invocation, the `ACTIVE_AGENT` detection block, and the `if claude then codex` alternate-agent rule, since `orca-cli cross-agent-review --reviewer cross` handles all that natively.)

- [ ] **Step 3: Smoke-test**

Same fixture pattern as Task 5; verify the rendered markdown contains severity-tier groupings (`#### Blocker`, etc.) when findings have those severities.

- [ ] **Step 4: Commit**

```bash
git add plugins/claude-code/commands/review-code.md
git commit -m "feat(slash): rewire /orca:review-code to call orca-cli"
```

---

## Task 7: Rewire `/orca:review-pr` slash command

**Why:** Third of three rewires. review-pr currently describes its own cross-review reuse pattern; rewire to call `orca-cli cross-agent-review --kind pr` and render via `render-review-pr` (markdown table format for disposition tracking).

**Files:**
- Modify: `plugins/claude-code/commands/review-pr.md`

- [ ] **Step 1: Read and identify the rewire surface**

Read `plugins/claude-code/commands/review-pr.md` fully. Find the section that describes invoking the cross-review (likely Step 3 or 4 of the Outline). That's the rewire surface.

- [ ] **Step 2: Replace the cross-review section**

Find the section in the Outline that describes invoking `crossreview.sh` or otherwise running a cross-pass for PR feedback, and replace it with:

```markdown
**Cross-Pass Review via orca-cli**

If a cross-pass review is needed (per `--phase`, `--external-comments`, or
the PR has substantive new diff since last review):

1. Build the PR diff for review:

   ```bash
   gh pr diff "$PR_NUM" > "$FEATURE_DIR/.pr-pass-patch"
   ```

2. Determine the next round number from existing `### Round N — `
   headers in `$FEATURE_DIR/review-pr.md`.

3. Invoke `orca-cli cross-agent-review`:

   ```bash
   uv run orca-cli cross-agent-review \
     --kind pr \
     --target "$FEATURE_DIR/.pr-pass-patch" \
     --feature-id "$(basename $FEATURE_DIR)" \
     --reviewer cross \
     --criteria "comment-disposition" \
     --criteria "regression-risk" \
     > "$FEATURE_DIR/.review-pr-envelope.json"
   ```

4. Translate to markdown table for disposition tracking:

   ```bash
   uv run python -m orca.cli_output render-review-pr \
     --feature-id "$(basename $FEATURE_DIR)" \
     --round <N> \
     --envelope-file "$FEATURE_DIR/.review-pr-envelope.json" \
     >> "$FEATURE_DIR/review-pr.md"
   ```

5. The rendered markdown includes a disposition column (`_pending_` by
   default). After processing each comment / finding, edit the row's
   Disposition cell to one of: `ADDRESSED`, `REJECTED`, `ISSUED #N`,
   `CLARIFY`. The existing comment-response protocol governs which
   disposition applies.
```

- [ ] **Step 3: Smoke-test**

Same fixture pattern; verify rendered markdown has the disposition table.

- [ ] **Step 4: Commit**

```bash
git add plugins/claude-code/commands/review-pr.md
git commit -m "feat(slash): rewire /orca:review-pr to call orca-cli"
```

---

## Task 8: New `/orca:gate` slash command

**Why:** First of two new slash commands. Wraps `completion-gate` capability.

**Files:**
- Create: `plugins/claude-code/commands/gate.md`

- [ ] **Step 1: Write the slash command markdown**

Create `plugins/claude-code/commands/gate.md`:

```markdown
---
description: Check whether an SDD-managed feature has cleared gates for a target stage. Wraps the orca completion-gate capability.
handoffs:
  - label: Re-Run Once Blockers Are Addressed
    agent: orca:gate
    prompt: Re-run the completion gate after fixing blockers
  - label: Fix Spec
    agent: speckit.specify
    prompt: Address spec-stage blockers (missing spec, [NEEDS CLARIFICATION], etc.)
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

`gate` is the personal SDD wrapper around the orca `completion-gate`
capability. It evaluates whether a feature has cleared the artifact +
evidence gates for a given stage transition (`plan-ready`,
`implement-ready`, `pr-ready`, `merge-ready`).

This is a **lint, not formal verification**. A `pass` status means the
documented gates passed; the operator decides whether to proceed.

## Workflow Contract

- Read user input for `--target-stage` (one of `plan-ready`,
  `implement-ready`, `pr-ready`, `merge-ready`). Default: `plan-ready`.
- Read user input for `--persist` (write to `<feature-dir>/gate-history.md`).
- Resolve `<feature-dir>` from user input or current branch.
- Invoke `orca-cli completion-gate` and render results.
- Report status to the user.

## Outline

1. Resolve `<feature-dir>` from user input or current branch.

2. Determine `--target-stage` from user input (default `plan-ready`).

3. If the operator provided `--evidence-json` (e.g., `'{"ci_green": true}'`),
   pass it through. Otherwise omit.

4. Invoke `orca-cli completion-gate`:

   ```bash
   uv run orca-cli completion-gate \
     --feature-dir "<feature-dir>" \
     --target-stage "<stage>" \
     [--evidence-json "<json>"] \
     > /tmp/orca-gate-envelope.json
   ```

5. Render markdown:

   ```bash
   uv run python -m orca.cli_output render-completion-gate \
     --target-stage "<stage>" \
     --envelope-file /tmp/orca-gate-envelope.json \
     > /tmp/orca-gate-report.md
   cat /tmp/orca-gate-report.md
   ```

6. If `--persist` was passed, append the report to
   `<feature-dir>/gate-history.md`:

   ```bash
   cat /tmp/orca-gate-report.md >> "<feature-dir>/gate-history.md"
   ```

7. Report status to the user (one of `pass`, `blocked`, `stale`) and
   list any blockers / stale artifacts. If `blocked`, recommend the
   appropriate handoff (e.g., spec revision for `spec_exists` /
   `no_unclarified` blockers).

## Errors

If `orca-cli completion-gate` returns `Err(...)`:

- `INPUT_INVALID`: report the message verbatim; the gate did not run.
- Other kinds: surface the `detail.underlying` if present.
```

- [ ] **Step 2: Smoke-test against a fixture feature dir**

```bash
mkdir -p /tmp/orca-gate-smoke/specs/001-test
echo "# Spec" > /tmp/orca-gate-smoke/specs/001-test/spec.md
uv run orca-cli completion-gate \
  --feature-dir /tmp/orca-gate-smoke/specs/001-test \
  --target-stage plan-ready \
  > /tmp/orca-gate-smoke/env.json
uv run python -m orca.cli_output render-completion-gate \
  --target-stage plan-ready \
  --envelope-file /tmp/orca-gate-smoke/env.json
```
Expected: `## Completion Gate: plan-ready` with `Status: **pass**`.

- [ ] **Step 3: Commit**

```bash
git add plugins/claude-code/commands/gate.md
git commit -m "feat(slash): add /orca:gate slash command"
```

---

## Task 9: New `/orca:cite` slash command

**Why:** Second of two new slash commands. Wraps `citation-validator` capability.

**Files:**
- Create: `plugins/claude-code/commands/cite.md`

- [ ] **Step 1: Write the slash command markdown**

Create `plugins/claude-code/commands/cite.md`:

```markdown
---
description: Validate citations and ref hygiene in synthesis text using rule-based heuristics. Wraps the orca citation-validator capability.
handoffs:
  - label: Address Uncited Claims
    agent: orca:cite
    prompt: Re-run after adding refs to flagged claims
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

`cite` is the personal SDD wrapper around the orca `citation-validator`
capability. It scans synthesis prose for assertion-shaped sentences
without `[ref]` brackets and `[ref]` brackets that don't resolve to a
known reference path.

This is a **lint, not scientific validation** of the underlying claims.
Rule-based heuristics catch surface-syntactic patterns (assertion verbs,
numerical claims) and miss semantic claims. See
`docs/capabilities/citation-validator/README.md` for limitations
(year false-positives, abbreviation handling, ref normalization).

## Workflow Contract

- Read user input for `--content-path` (the synthesis file).
- Read user input for `--reference-set` (repeatable; paths to refs).
- Read user input for `--mode` (`strict` or `lenient`; default `strict`).
- Read user input for `--write` (append to `<feature-dir>/cite-report.md`).
- Invoke `orca-cli citation-validator` and render results.

## Outline

1. Resolve `--content-path` from user input. Required.

2. Resolve `--reference-set` paths from user input. If none provided,
   default to `events.jsonl`, `experiments.tsv`, and any
   `specs/<feature>/research.md` files present in the repo root.

3. Determine `--mode` from user input (default `strict`).

4. Invoke `orca-cli citation-validator`:

   ```bash
   uv run orca-cli citation-validator \
     --content-path "<content-path>" \
     --reference-set "<ref1>" \
     --reference-set "<ref2>" \
     --mode "<mode>" \
     > /tmp/orca-cite-envelope.json
   ```

5. Render markdown:

   ```bash
   uv run python -m orca.cli_output render-citation \
     --content-path "<content-path>" \
     --envelope-file /tmp/orca-cite-envelope.json \
     > /tmp/orca-cite-report.md
   cat /tmp/orca-cite-report.md
   ```

6. If `--write` was passed, append the report to a `cite-report.md`
   artifact (under the feature dir if resolvable, else the repo root):

   ```bash
   cat /tmp/orca-cite-report.md >> "<feature-dir>/cite-report.md"
   ```

7. Report coverage + counts to the user. If coverage < 1.0, list the
   uncited claims with line numbers so the operator can address them.

## Errors

If `orca-cli citation-validator` returns `Err(...)`:

- `INPUT_INVALID`: report the message verbatim (typical: missing
  `--content-path` or non-existent file).
```

- [ ] **Step 2: Smoke-test**

```bash
echo "x" > /tmp/orca-cite-smoke-evidence.md
uv run orca-cli citation-validator \
  --content-text "Results show 42% [evidence]." \
  --reference-set /tmp/orca-cite-smoke-evidence.md \
  > /tmp/orca-cite-smoke-env.json
uv run python -m orca.cli_output render-citation \
  --content-path /tmp/orca-cite-smoke-evidence.md \
  --envelope-file /tmp/orca-cite-smoke-env.json
```
Expected: `## Citation Report: ...` with `Coverage: **1.0**`.

- [ ] **Step 3: Commit**

```bash
git add plugins/claude-code/commands/cite.md
git commit -m "feat(slash): add /orca:cite slash command"
```

---

## Task 10: Update `extension.yml` registry

**Why:** Add the 2 new commands so spec-kit's `extension add orca` registers them and the auto-generated SKILL.md picks them up.

**Files:**
- Modify: `extension.yml`

- [ ] **Step 1: Read current extension.yml**

Read `extension.yml`. Find the `provides.commands` array (existing 5 entries: brainstorm, review-spec, review-code, review-pr, tui).

- [ ] **Step 2: Add 2 new entries**

In `extension.yml`, append to the `provides.commands` array (after the `tui` entry):

```yaml
    - name: "orca:gate"
      file: "plugins/claude-code/commands/gate.md"
      description: "Check whether an SDD-managed feature has cleared gates for a target stage. Wraps the orca completion-gate capability."

    - name: "orca:cite"
      file: "plugins/claude-code/commands/cite.md"
      description: "Validate citations and ref hygiene in synthesis text using rule-based heuristics. Wraps the orca citation-validator capability."
```

Bump `extension.version` from `2.1.0` to `2.2.0` (Phase 3 ships a new minor version):

```yaml
extension:
  ...
  version: "2.2.0"
  ...
```

- [ ] **Step 3: Verify YAML still parses**

```bash
uv run python -c "import yaml; yaml.safe_load(open('extension.yml'))"
```
Expected: no error.

- [ ] **Step 4: Verify the generator function still works**

Run a syntax check on the bash function that consumes this:
```bash
bash -n src/orca/assets/orca-main.sh
```
Expected: clean exit.

- [ ] **Step 5: Commit**

```bash
git add extension.yml
git commit -m "chore(extension): register orca:gate + orca:cite + bump to 2.2.0"
```

---

## Task 11: Codex AGENTS.md pointer doc

**Why:** Codex consumption surface — a single document that codex reads to discover the orca-cli capability layer.

**Files:**
- Create: `plugins/codex/AGENTS.md`
- Create: `tests/cli/test_codex_agents_md.py`

- [ ] **Step 1: Write failing test**

Create `tests/cli/test_codex_agents_md.py`:

```python
"""Verify the Codex AGENTS.md doc lists every orca-cli capability.

Drift between orca-cli --list and the AGENTS.md doc is a build break:
codex would otherwise miss new capabilities.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_MD = REPO_ROOT / "plugins" / "codex" / "AGENTS.md"


def test_codex_agents_md_exists():
    assert AGENTS_MD.exists(), f"missing {AGENTS_MD}"


def test_codex_agents_md_lists_every_capability():
    """The doc must mention every capability orca-cli --list reports.

    Tests at the structural-text level since the actual orca-cli --list
    invocation requires the script entry to be installed; this test
    runs in any environment.
    """
    text = AGENTS_MD.read_text(encoding="utf-8")
    expected_capabilities = [
        "cross-agent-review",
        "worktree-overlap-check",
        "flow-state-projection",
        "completion-gate",
        "citation-validator",
        "contradiction-detector",
    ]
    for cap in expected_capabilities:
        assert cap in text, f"AGENTS.md missing capability: {cap}"


def test_codex_agents_md_documents_envelope_shape():
    text = AGENTS_MD.read_text(encoding="utf-8")
    # Universal Result contract elements
    assert "ok" in text
    assert "result" in text or "error" in text
    assert "metadata" in text


def test_codex_agents_md_documents_exit_codes():
    text = AGENTS_MD.read_text(encoding="utf-8")
    # Exit code mapping
    assert "0" in text and "1" in text and "2" in text and "3" in text
    assert "exit" in text.lower()


def test_codex_agents_md_documents_fixture_env_vars():
    text = AGENTS_MD.read_text(encoding="utf-8")
    assert "ORCA_FIXTURE_REVIEWER_" in text
    assert "ORCA_LIVE" in text


def test_codex_agents_md_documents_what_orca_is_not():
    """jcode positioning: the doc must clarify orca is not a runtime."""
    text = AGENTS_MD.read_text(encoding="utf-8")
    # Some form of "not a scheduler/runtime/control plane" should appear
    text_lower = text.lower()
    assert (
        "not a runtime" in text_lower
        or "not a scheduler" in text_lower
        or "does not execute" in text_lower
    )
```

- [ ] **Step 2: Verify failure**

Run: `uv run python -m pytest tests/cli/test_codex_agents_md.py -v`
Expected: 6 FAIL (file does not exist).

- [ ] **Step 3: Write the AGENTS.md doc**

Create `plugins/codex/AGENTS.md`:

```markdown
# Orca for Codex

Orca is a repo-backed capability library for agentic engineering governance. It does NOT execute host runtimes; it provides JSON-in JSON-out capabilities you can shell out to from within a Codex session.

## What Orca Is NOT

- Not a scheduler, worker runtime, supervisor, or control plane
- Not a daemon, presence system, or live state watcher
- Not a primary store for review or flow state (the host or repo owns that)

LLM-backed capabilities (`cross-agent-review`, `contradiction-detector`) produce **findings and hypotheses, not formal proof**. Hosts decide how findings affect actions.

## CLI Surface

The canonical entry point is `orca-cli`. Six capabilities are available:

| Capability | What it does | README |
|------------|--------------|--------|
| `cross-agent-review` | Bundle a review subject (spec, diff, pr, claim-output), dispatch to claude/codex/cross, return structured findings with stable dedupe IDs | `docs/capabilities/cross-agent-review/README.md` |
| `worktree-overlap-check` | Pure-Python detection of path conflicts between active worktrees and proposed writes | `docs/capabilities/worktree-overlap-check/README.md` |
| `flow-state-projection` | Project an SDD feature directory into a JSON snapshot of stage / milestones / next step | `docs/capabilities/flow-state-projection/README.md` |
| `completion-gate` | Decide whether a feature has cleared gates for a target stage (`plan-ready`, `implement-ready`, `pr-ready`, `merge-ready`) | `docs/capabilities/completion-gate/README.md` |
| `citation-validator` | Rule-based detection of uncited claims and broken refs in synthesis text | `docs/capabilities/citation-validator/README.md` |
| `contradiction-detector` | Cross-agent-review with a fixed contradiction prompt; surfaces conflicts between new content and prior evidence | `docs/capabilities/contradiction-detector/README.md` |

Each capability has an input schema (`docs/capabilities/<name>/schema/input.json`) and output schema (`docs/capabilities/<name>/schema/output.json`).

## Universal Result Envelope

Every `orca-cli` invocation returns this JSON shape on stdout:

```json
{
  "ok": true,
  "result": { /* capability-specific shape, see output.json schemas */ },
  "metadata": {
    "capability": "...",
    "version": "0.1.0",
    "duration_ms": 123
  }
}
```

On failure:

```json
{
  "ok": false,
  "error": {
    "kind": "input_invalid" | "backend_failure" | "timeout" | "internal",
    "message": "...",
    "detail": { /* optional structured context */ }
  },
  "metadata": { ... }
}
```

## Exit Codes

- `0` — success
- `1` — capability returned `Err(...)` (input/backend/internal error)
- `2` — argv parse error (missing required flag, bad value)
- `3` — unknown capability subcommand

## Reviewer Backend Selection

LLM-backed capabilities (`cross-agent-review`, `contradiction-detector`) need reviewer backends configured via env vars:

- `ORCA_FIXTURE_REVIEWER_CLAUDE=<path>` — replay a JSON fixture as if it were a Claude response (test mode)
- `ORCA_FIXTURE_REVIEWER_CODEX=<path>` — replay a JSON fixture as if it were a Codex response (test mode)
- `ORCA_LIVE=1` — enable real backends (Anthropic SDK for claude, `codex` CLI shellout for codex)

If neither is set, the capability returns `Err(INPUT_INVALID)` with `message="reviewer not configured"`.

## Invocation Patterns

### Single capability call

```bash
orca-cli cross-agent-review \
  --kind diff \
  --target src/foo.py \
  --feature-id 001-foo \
  --reviewer cross
```

### Pretty mode (human-readable)

Append `--pretty` to any subcommand for a human-friendly summary instead of JSON. Useful for interactive sessions; do not parse the pretty output.

### Reading from stdin

`worktree-overlap-check` reads JSON from stdin (or `--input <file>`):

```bash
echo '{"worktrees":[]}' | orca-cli worktree-overlap-check
```

### Listing capabilities

```bash
orca-cli --list
```

## Don't

- Don't parse the `--pretty` output. JSON is the contract.
- Don't assume any capability "blocks" by itself; orca returns Result envelopes, the caller decides.
- Don't extend orca by adding new state stores. Add new capabilities (small functions returning Result) instead.
- Don't import from `orca.capabilities.*` modules across capability boundaries; each capability is independent.

## Where Things Live

- Capability sources: `src/orca/capabilities/`
- Reviewer adapters: `src/orca/core/reviewers/`
- JSON schemas: `docs/capabilities/<name>/schema/`
- Capability READMEs: `docs/capabilities/<name>/README.md`
- This doc: `plugins/codex/AGENTS.md`
```

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run python -m pytest tests/cli/test_codex_agents_md.py -v`
Expected: 6 PASS.

Full suite: `uv run python -m pytest -q`
Expected: 375 (369 + 6) PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/codex/AGENTS.md tests/cli/test_codex_agents_md.py
git commit -m "feat(codex): add AGENTS.md pointer doc + drift test"
```

---

## Task 12: Final verification + tag

**Why:** Phase 3 done. Smoke each new+rewired command end-to-end, verify CI surface, tag.

- [ ] **Step 1: Full test suite**

Run: `uv run python -m pytest -q`
Expected: ~375 PASS (Phase 2 baseline 346 + 29 new).

- [ ] **Step 2: Verify all slash command files exist + parse**

```bash
for f in plugins/claude-code/commands/*.md; do
  echo "$f: $(head -1 $f)"
done
```
Expected: 7 files, each starting with `---` (YAML frontmatter).

- [ ] **Step 3: Verify cli_output module help works**

```bash
uv run python -m orca.cli_output --help
```
Expected: lists all 5 render-* subcommands.

- [ ] **Step 4: End-to-end smoke for each new+rewired command**

For each of the 5 commands wired to a capability (review-spec, review-code, review-pr, gate, cite), run the documented bash invocation pattern from the slash command markdown against a tiny fixture feature dir. Confirm the rendered markdown matches expected shape.

- [ ] **Step 5: Verify Codex AGENTS.md is not stale**

```bash
uv run python -m pytest tests/cli/test_codex_agents_md.py -v
```
Expected: 6 PASS.

- [ ] **Step 6: Verify extension.yml + bash launcher**

```bash
uv run python -c "import yaml; d = yaml.safe_load(open('extension.yml')); cmds = d['provides']['commands']; print(f'{len(cmds)} commands registered: {[c[\"name\"] for c in cmds]}')"
bash -n src/orca/assets/orca-main.sh
```
Expected: 7 commands (5 prior + gate + cite), no shell syntax errors.

- [ ] **Step 7: Tag**

```bash
git tag orca-v0.3.0
```
(Local tag; push only if user asks.)

- [ ] **Step 8: Open PR**

```bash
git push -u origin orca-phase-3-plugin-formats
gh pr create --base orca-phase-2-capability-cores --title "feat: orca v1 phase 3 — plugin formats + SDD slash commands" --body "$(cat <<'EOF'
## Summary

Phase 3 of the orca v1 rebuild: wires the Phase 2 capability layer into the personal SDD opinion-layer slash commands, plus a Codex consumption surface. Stacked on top of Phase 2 (#69); merge that first.

### What's here

- **5 slash commands** (3 rewired + 2 new) actually invoke `orca-cli` instead of describing it:
  - `/orca:review-spec` → `orca-cli cross-agent-review --kind spec`
  - `/orca:review-code` → `orca-cli cross-agent-review --kind diff`
  - `/orca:review-pr` → `orca-cli cross-agent-review --kind pr`
  - `/orca:gate <stage>` (NEW) → `orca-cli completion-gate`
  - `/orca:cite <path>` (NEW) → `orca-cli citation-validator`
- **`src/orca/cli_output.py`** — markdown renderers for 5 artifact shapes; CLI surface via `python -m orca.cli_output render-{type}`. Translates orca-cli JSON envelopes into the established review-X.md / gate / citation markdown formats.
- **`plugins/codex/AGENTS.md`** — Codex consumption surface. Single pointer doc listing every capability, envelope shape, exit codes, env-var conventions. Drift test ensures it stays in sync with `orca-cli --list`.
- **`extension.yml`** registers `orca:gate` and `orca:cite`; bumped to v2.2.0.

### Test plan

- [ ] `uv run python -m pytest -q` — ~375 tests passing (Phase 2 baseline 346 + 29 new)
- [ ] `uv run python -m orca.cli_output --help` lists all 5 render subcommands
- [ ] End-to-end smoke per slash command works with fixture reviewers
- [ ] CI green

### Out of scope (Phase 4+)

- Per-host integration shims (perf-lab — Phase 4)
- Bash convenience launchers (deferred per design)
- `contradiction-detector` slash command (research-loop primary; perf-lab will invoke directly)
- `worktree-overlap-check` slash command (host machinery, not personal SDD)
- TUI changes
EOF
)"
```

(Skip the push if user prefers manual remote ops.)

---

## Self-Review

### Spec coverage

| Spec section | Tasks |
|---|---|
| Rewire 3 existing slash commands | Tasks 5, 6, 7 |
| 2 new slash commands (`gate`, `cite`) | Tasks 8, 9 |
| `cli_output` module + 5 renderers | Tasks 1, 2, 3 |
| `cli_output` `python -m` CLI surface | Task 4 |
| Codex `AGENTS.md` pointer doc | Task 11 |
| `extension.yml` updated for new commands | Task 10 |
| Test coverage per testing strategy | Tasks 1-4 (renderer unit tests), 5-9 (slash command smokes), 11 (drift test) |
| Resolved decision: `python -m orca.cli_output` (not `orca-cli` subcommand) | Task 4 |
| Resolved decision: `--persist` / `--write` operator-controlled | Tasks 8, 9 |
| Resolved decision: Codex AGENTS.md in-place (not generated) | Task 11 |

### Placeholder scan

No placeholders / TBDs / "implement later" found. The two slash command rewires (Tasks 6, 7) point at specific section boundaries in the existing files rather than rewriting from scratch — this matches the spec's "translation, not replacement" constraint. Bash code blocks contain real commands; markdown code blocks contain real markdown.

### Type consistency

- `render_*_markdown(envelope, ...)` signature consistent across all 5 renderers (envelope is positional dict, kwargs are renderer-specific).
- `_read_envelope(envelope_file: str | None) -> dict | None` — returns None on parse error; callers branch on None.
- CLI subcommand handlers all have signature `_render_*_cli(args: list[str]) -> int`.
- `RENDERERS` dict maps render-* subcommand → handler function name (string, not callable, to allow late binding).
- `cli_output.main(argv)` matches `orca.python_cli.main` signature pattern.

### Scope check

One phase, one branch. 12 tasks, ~1 week as estimated. Tasks 5-9 (slash commands + new commands) can partly parallelize after Task 4 lands but the plan keeps them sequential for review-cycle clarity.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-27-orca-phase-3-plugin-formats.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Same flow that worked for Phase 1 + 2.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
