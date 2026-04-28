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
from typing import Any, Callable

from orca.core.findings import Severity


# Operator diagnosis order: WHAT failed (underlying) before WHAT TO DO (retryable).
# Unknown keys fall back to alphabetical to keep the rendering deterministic.
_DETAIL_ORDER = ("underlying", "retryable", "round", "after_seconds", "filename", "errno")


def _detail_sort_key(item: tuple[str, Any]) -> tuple[int, str]:
    key = item[0]
    try:
        return (_DETAIL_ORDER.index(key), key)
    except ValueError:
        return (len(_DETAIL_ORDER), key)


def _normalize_inline(s: object) -> str:
    """Normalize an envelope-supplied string for safe inline markdown emission.

    Collapses newlines and carriage returns to single spaces so a multi-line
    string can't inject headings, list items, or break a containing list/header
    structure. Trailing/leading whitespace is stripped. Non-string values are
    coerced via str().
    """
    if not isinstance(s, str):
        s = str(s)
    return s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()


def _normalize_table_cell(s: object) -> str:
    """Normalize a string for safe markdown-table-cell emission.

    Collapses newlines (so the row stays on one line) and escapes pipes
    (so they don't terminate a cell prematurely).
    """
    return _normalize_inline(s).replace("|", "\\|")


def render_error_block(envelope: dict[str, Any], *, round_num: int) -> str:
    """Render a failure envelope as a Round-N labeled markdown block.

    Common to all artifact renderers. Includes ErrorKind, message, and
    detail block (underlying + retryable when present).

    Raises ValueError if the envelope is not a failure (ok != False).
    """
    if envelope.get("ok") is not False:
        raise ValueError(
            "render_error_block requires a failure envelope (ok=False); "
            f"got ok={envelope.get('ok')!r}"
        )
    err = envelope.get("error", {})
    kind = _normalize_inline(err.get("kind", "unknown"))
    message = _normalize_inline(err.get("message", "(no message)"))
    detail = err.get("detail") or {}

    lines = [
        f"### Round {round_num} - FAILED",
        "",
        f"- kind: {kind}",
        f"- message: {message}",
    ]
    for key, value in sorted(detail.items(), key=_detail_sort_key):
        lines.append(f"- {_normalize_inline(key)}: {_normalize_inline(value)}")
    lines.append("")
    lines.append(render_metadata_footer(envelope))
    return "\n".join(lines)


def render_metadata_footer(envelope: dict[str, Any]) -> str:
    """Render the trailing metadata block all artifacts share.

    Defaults ('?', 0) are reachable only from hand-built envelopes;
    Result.to_json() always populates these.
    """
    meta = envelope.get("metadata", {})
    capability = meta.get("capability", "?")
    version = meta.get("version", "?")
    duration_ms = meta.get("duration_ms", 0)
    if isinstance(duration_ms, float) and duration_ms < 1:
        duration_str = f"{duration_ms:.1f}ms"
    else:
        # Integer or >=1ms float - render as integer for clean display
        duration_str = f"{int(duration_ms)}ms"
    lines = [
        f"_capability: {capability}_  ",
        f"_version: {version}_  ",
        f"_duration: {duration_str}_",
    ]
    return "\n".join(lines)


# Severity sort order derived from Severity enum (single source of truth).
# Unknown values rank last (99) for deterministic placement.
_SEVERITY_RANK: dict[str, int] = {s.value: i for i, s in enumerate(Severity)}
_SEVERITY_ORDER: tuple[str, ...] = tuple(s.value for s in Severity)


def _severity_rank(severity: str) -> int:
    """Lower rank = more severe; for sort ordering."""
    return _SEVERITY_RANK.get(severity, 99)


def _findings_sorted(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stable severity-then-id sort so renderers produce deterministic output."""
    return sorted(findings, key=lambda f: (_severity_rank(f.get("severity", "nit")), f.get("id", "")))


def _render_finding_oneline(f: dict[str, Any]) -> str:
    """One-line finding rendering for review-spec.

    Shape: `- [severity] summary - evidence (reviewers)`. Hyphens, no em-dashes.
    """
    severity = _normalize_inline(f.get("severity", "?"))
    summary = _normalize_inline(f.get("summary", "?"))
    evidence = ", ".join(_normalize_inline(e) for e in f.get("evidence", []))
    reviewers = "+".join(_normalize_inline(r) for r in f.get("reviewers", []))
    suffix = f" ({reviewers})" if reviewers else ""
    line = f"- [{severity}] {summary}"
    if evidence:
        line += f" - {evidence}"
    return line + suffix


def _render_partial_note(envelope: dict[str, Any]) -> str:
    """Bare partial-run note string (no surrounding whitespace).

    Renderers wrap with their own blank lines so all renderers produce
    consistent whitespace shape.
    """
    result = envelope.get("result", {})
    if not result.get("partial"):
        return ""
    missing = [_normalize_inline(m) for m in result.get("missing_reviewers", [])]
    return f"_partial run: missing reviewers = {', '.join(missing)}_"


def render_review_spec_markdown(
    envelope: dict[str, Any], *, round_num: int, feature_id: str,
) -> str:
    """Render a cross-agent-review envelope as a review-spec.md round block.

    Concise one-line per finding; suitable for spec-stage adversarial review
    where operator scanning matters more than full diagnostic detail.
    """
    if not envelope.get("ok"):
        return render_error_block(envelope, round_num=round_num)

    result = envelope.get("result", {})
    findings = _findings_sorted(result.get("findings", []))

    lines = [
        f"### Round {round_num} - Cross-Pass ({feature_id})",
        "",
    ]
    if not findings:
        lines.append("_no findings_")
    else:
        for f in findings:
            lines.append(_render_finding_oneline(f))
    partial = _render_partial_note(envelope)
    if partial:
        lines.append("")
        lines.append(partial)
    lines.append("")
    lines.append(render_metadata_footer(envelope))
    return "\n".join(lines)


def render_review_code_markdown(
    envelope: dict[str, Any], *, round_num: int, feature_id: str,
) -> str:
    """Render a cross-agent-review envelope as a review-code.md round block.

    Groups findings under severity-tier subheadings so operators can scan
    blockers first. Each finding gets multi-line detail (summary, detail,
    evidence, suggestion).
    """
    if not envelope.get("ok"):
        return render_error_block(envelope, round_num=round_num)

    result = envelope.get("result", {})
    findings = _findings_sorted(result.get("findings", []))

    lines = [
        f"### Round {round_num} - Cross-Pass ({feature_id})",
        "",
    ]
    if not findings:
        lines.append("_no findings_")
    else:
        # Group by severity for operator scan-ability
        by_severity: dict[str, list[dict[str, Any]]] = {}
        for f in findings:
            by_severity.setdefault(f.get("severity", "?"), []).append(f)

        def _emit_group(group: list[dict[str, Any]]) -> None:
            for f in group:
                summary = _normalize_inline(f.get("summary", "?"))
                detail = _normalize_inline(f.get("detail", ""))
                evidence = ", ".join(_normalize_inline(e) for e in f.get("evidence", []))
                suggestion = _normalize_inline(f.get("suggestion", ""))
                reviewers = "+".join(_normalize_inline(r) for r in f.get("reviewers", []))
                lines.append(f"- **{summary}** ({reviewers})")
                if detail:
                    lines.append(f"  - {detail}")
                if evidence:
                    lines.append(f"  - evidence: {evidence}")
                if suggestion:
                    lines.append(f"  - suggestion: {suggestion}")

        known_severities = set(_SEVERITY_ORDER)
        for severity in _SEVERITY_ORDER:
            group = by_severity.get(severity)
            if not group:
                continue
            lines.append(f"#### {severity.capitalize()}")
            lines.append("")
            _emit_group(group)
            # No per-group trailing blank: the unconditional trailing blank
            # before the metadata footer (below) provides the only separator.
            # Adding one here would produce a double-blank in the populated
            # case (caught by the whitespace-shape regression test).

        # Catch findings whose severity is not in the known set (e.g.
        # uppercase slip, "?", or any future value not in _SEVERITY_ORDER)
        # so they don't silently disappear from the artifact.
        unknown = [f for f in findings if f.get("severity") not in known_severities]
        if unknown:
            lines.append("#### Other")
            lines.append("")
            _emit_group(unknown)

    partial = _render_partial_note(envelope)
    if partial:
        lines.append("")
        lines.append(partial)
    lines.append("")
    lines.append(render_metadata_footer(envelope))
    return "\n".join(lines)


def render_review_pr_markdown(
    envelope: dict[str, Any], *, round_num: int, feature_id: str,
) -> str:
    """Render a cross-agent-review envelope as a review-pr.md round block.

    Markdown table with id, severity, summary, reviewers, and a pending
    Disposition column. Operator edits the Disposition cell after
    processing each finding (ADDRESSED / REJECTED / ISSUED #N / CLARIFY).
    """
    if not envelope.get("ok"):
        return render_error_block(envelope, round_num=round_num)

    result = envelope.get("result", {})
    findings = _findings_sorted(result.get("findings", []))

    lines = [
        f"### Round {round_num} - Cross-Pass ({feature_id})",
        "",
    ]
    if not findings:
        lines.append("_no findings_")
    else:
        lines.append("| id | Severity | Summary | Reviewers | Disposition |")
        lines.append("|----|----------|---------|-----------|-------------|")
        for f in findings:
            fid = _normalize_table_cell(f.get("id", "?"))
            severity = _normalize_table_cell(f.get("severity", "?"))
            summary = _normalize_table_cell(f.get("summary", "?"))
            reviewers = _normalize_table_cell(
                "+".join(_normalize_inline(r) for r in f.get("reviewers", []))
            )
            lines.append(f"| {fid} | {severity} | {summary} | {reviewers} | _pending_ |")

    partial = _render_partial_note(envelope)
    if partial:
        lines.append("")
        lines.append(partial)
    lines.append("")
    lines.append(render_metadata_footer(envelope))
    return "\n".join(lines)


def render_completion_gate_markdown(
    envelope: dict[str, Any], *, target_stage: str,
) -> str:
    """Render a completion-gate envelope as a Markdown report.

    Used by /orca:gate slash command. Single-shot (not round-appended);
    failure envelopes use round_num=0 in the error block.
    """
    if not envelope.get("ok"):
        return render_error_block(envelope, round_num=0)

    result = envelope.get("result", {})
    status = _normalize_inline(result.get("status", "?"))
    gates = result.get("gates_evaluated", [])
    blockers = result.get("blockers", [])
    stale = result.get("stale_artifacts", [])

    lines = [
        f"## Completion Gate: {_normalize_inline(target_stage)}",
        "",
        f"Status: **{status}**",
    ]
    if gates:
        lines.append("")
        lines.append("### Gates")
        lines.append("")
        for g in gates:
            gate = _normalize_inline(g.get("gate", "?"))
            passed = g.get("passed", False)
            reason = _normalize_inline(g.get("reason", ""))
            mark = "✓" if passed else "✗"
            line = f"- {mark} `{gate}`"
            if reason:
                line += f" - {reason}"
            lines.append(line)

    if blockers:
        lines.append("")
        lines.append("### Blockers")
        lines.append("")
        for b in blockers:
            lines.append(f"- `{_normalize_inline(b)}`")

    if stale:
        lines.append("")
        lines.append("### Stale Artifacts")
        lines.append("")
        for s in stale:
            lines.append(f"- `{_normalize_inline(s)}`")

    lines.append("")
    lines.append(render_metadata_footer(envelope))
    return "\n".join(lines)


def render_citation_markdown(
    envelope: dict[str, Any], *, content_path: str,
) -> str:
    """Render a citation-validator envelope as a Markdown report.

    Used by /orca:cite slash command. Single-shot (not round-appended);
    failure envelopes use round_num=0 in the error block.
    """
    if not envelope.get("ok"):
        return render_error_block(envelope, round_num=0)

    result = envelope.get("result", {})
    coverage = result.get("citation_coverage", 0.0)
    uncited = result.get("uncited_claims", [])
    broken = result.get("broken_refs", [])
    well = result.get("well_supported_claims", [])

    # Floor (not round) to percent so 0.999 renders as 99% - an operator
    # scanning the header must NOT see "100%" while the body lists uncited
    # claims. int() of a positive float floors it; 1.0 -> 100 exactly.
    coverage_pct = int(coverage * 100)

    lines = [
        f"## Citation Report: {_normalize_inline(content_path)}",
        "",
        f"Coverage: **{coverage_pct}%**",
        "",
        f"- uncited: {len(uncited)}",
        f"- broken refs: {len(broken)}",
        f"- well-supported: {len(well)}",
    ]

    if uncited:
        lines.append("")
        lines.append("### Uncited Claims")
        lines.append("")
        for c in uncited:
            text = _normalize_inline(c.get("text", ""))
            line = _normalize_inline(c.get("line", "?"))
            lines.append(f"- line {line}: {text}")

    if broken:
        lines.append("")
        lines.append("### Broken Refs")
        lines.append("")
        for b in broken:
            ref = _normalize_inline(b.get("ref", "?"))
            line = _normalize_inline(b.get("line", "?"))
            lines.append(f"- line {line}: `[{ref}]`")

    if well:
        lines.append("")
        lines.append("### Well-Supported Claims")
        lines.append("")
        for w in well:
            text = _normalize_inline(w.get("text", ""))
            line = _normalize_inline(w.get("line", "?"))
            lines.append(f"- line {line}: {text}")

    lines.append("")
    lines.append(render_metadata_footer(envelope))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: `python -m orca.cli_output render-{type} ...`.

    Each render-* subcommand reads a Result envelope from stdin (or
    --envelope-file) and writes markdown to stdout. Exit codes:
      0 success
      1 input error (bad JSON, missing envelope file)
      2 argparse usage error (missing or invalid CLI flag)
      3 unknown subcommand
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

    return RENDERERS[subcmd](argv[1:])


def _print_help() -> None:
    print("python -m orca.cli_output - render orca-cli envelopes as markdown")
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
            with open(envelope_file, "r", encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as exc:
            print(f"could not read envelope file: {exc}", file=sys.stderr)
            return None
    else:
        raw = sys.stdin.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"invalid JSON envelope; could not parse: {exc}", file=sys.stderr)
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
    # target-stage is a passthrough label; orca-cli completion-gate
    # validates against the plan-ready/implement-ready/pr-ready/merge-ready enum.
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


RENDERERS: dict[str, Callable[[list[str]], int]] = {
    "render-review-spec": _render_review_spec_cli,
    "render-review-code": _render_review_code_cli,
    "render-review-pr": _render_review_pr_cli,
    "render-completion-gate": _render_completion_gate_cli,
    "render-citation": _render_citation_cli,
}


if __name__ == "__main__":
    raise SystemExit(main())
