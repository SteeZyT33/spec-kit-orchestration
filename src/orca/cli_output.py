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
import sys
from typing import Any

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
    kind = err.get("kind", "unknown")
    message = err.get("message", "(no message)")
    detail = err.get("detail") or {}

    lines = [
        f"### Round {round_num} - FAILED",
        "",
        f"- kind: {kind}",
        f"- message: {message}",
    ]
    for key, value in sorted(detail.items(), key=_detail_sort_key):
        lines.append(f"- {key}: {value}")
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
    lines = [
        f"_capability: {capability}_  ",
        f"_version: {version}_  ",
        f"_duration: {duration_ms}ms_",
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
    severity = f.get("severity", "?")
    summary = f.get("summary", "?")
    evidence = ", ".join(f.get("evidence", []))
    reviewers = "+".join(f.get("reviewers", []))
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
    missing = result.get("missing_reviewers", [])
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
        for severity in _SEVERITY_ORDER:
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
            # No per-group trailing blank: the unconditional trailing blank
            # before the metadata footer (below) provides the only separator.
            # Adding one here would produce a double-blank in the populated
            # case (caught by the whitespace-shape regression test).

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
            fid = f.get("id", "?")
            severity = f.get("severity", "?")
            summary = (
                f.get("summary", "?")
                .replace("|", "\\|")
                .replace("\r\n", " ")
                .replace("\n", " ")
                .replace("\r", " ")
            )
            reviewers = "+".join(f.get("reviewers", []))
            lines.append(f"| {fid} | {severity} | {summary} | {reviewers} | _pending_ |")

    partial = _render_partial_note(envelope)
    if partial:
        lines.append("")
        lines.append(partial)
    lines.append("")
    lines.append(render_metadata_footer(envelope))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: `python -m orca.cli_output render-{type} ...`.

    Skeleton: Task 4 will replace with proper subparsers + stdin/file
    dispatch for the 5 render-* subcommands. Current behavior is
    print-help-or-error so the module is importable.
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
