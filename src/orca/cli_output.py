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
