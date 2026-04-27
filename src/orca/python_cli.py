"""Canonical Python CLI for orca capabilities.

This is a sibling to `cli.py` (the bash launcher kept for the opinion layer's
slash commands). `python_cli.py` is the wire-format-canonical surface: each
capability gets a subcommand, args parse to the capability's input dataclass,
the Result envelope is emitted as JSON to stdout (or pretty-printed via
`--pretty`), and the exit code follows the design's universal Result contract:

  0  success
  1  capability returned Err (input_invalid / backend_failure / etc.)
  2  CLI argv parse error
  3  unknown capability

Reviewer backends are loaded from environment:
  ORCA_FIXTURE_REVIEWER_CLAUDE / _CODEX  -> FixtureReviewer (tests)
  ORCA_LIVE=1                            -> real backends (manual verification)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from orca.capabilities.cross_agent_review import (
    DEFAULT_REVIEW_PROMPT,
    VERSION as CROSS_AGENT_REVIEW_VERSION,
    CrossAgentReviewInput,
    cross_agent_review,
)
from orca.capabilities.worktree_overlap_check import (
    VERSION as WORKTREE_OVERLAP_CHECK_VERSION,
    WorktreeInfo,
    WorktreeOverlapInput,
    worktree_overlap_check,
)
from orca.core.errors import Error, ErrorKind
from orca.core.result import Err
from orca.core.reviewers.claude import ClaudeReviewer
from orca.core.reviewers.codex import CodexReviewer
from orca.core.reviewers.fixtures import FixtureReviewer

# capability name -> (subcommand handler, version string).
# Add capabilities here when wiring CLI for new ones.
CAPABILITIES: dict[str, tuple] = {}


def _register(name: str, handler, version: str) -> None:
    CAPABILITIES[name] = (handler, version)


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]

    if not argv:
        _print_help()
        return 0

    if argv[0] in ("--list", "-l"):
        for name in CAPABILITIES:
            print(name)
        return 0

    if argv[0] in ("-h", "--help"):
        _print_help()
        return 0

    capability = argv[0]
    if capability not in CAPABILITIES:
        print(f"unknown capability: {capability}", file=sys.stderr)
        print(f"available: {', '.join(CAPABILITIES) or '<none>'}", file=sys.stderr)
        return 3

    handler, _version = CAPABILITIES[capability]
    return handler(argv[1:])


def _print_help() -> None:
    print("orca-cli - orca capability runner")
    print()
    print("Usage: orca-cli <capability> [options]")
    print()
    print("Capabilities:")
    for name in CAPABILITIES:
        print(f"  {name}")
    print()
    print("Run `orca-cli <capability> --help` for capability-specific flags.")


def _run_cross_agent_review(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="orca-cli cross-agent-review",
        exit_on_error=False,
    )
    parser.add_argument("--kind", required=True)
    parser.add_argument("--target", action="append", required=True, default=[])
    parser.add_argument("--reviewer", default="cross")
    parser.add_argument("--feature-id", default=None)
    parser.add_argument("--criteria", action="append", default=[])
    parser.add_argument("--context", action="append", default=[])
    parser.add_argument("--prompt", default=DEFAULT_REVIEW_PROMPT)
    parser.add_argument("--pretty", action="store_true",
                        help="emit human-readable summary instead of JSON envelope")

    try:
        ns, unknown = parser.parse_known_args(args)
    except argparse.ArgumentError as exc:
        # exit_on_error=False raises ArgumentError for unknown/missing args.
        return _emit_envelope(
            envelope=_err_envelope(
                "cross-agent-review", CROSS_AGENT_REVIEW_VERSION,
                ErrorKind.INPUT_INVALID, f"argv parse error: {exc}",
            ),
            pretty=False,  # ns isn't built yet; default to JSON
            exit_code=2,  # universal Result contract: 2 = argv parse error
        )
    except SystemExit as exc:
        # Some argparse paths (missing required args, -h/--help) still call
        # sys.exit even with exit_on_error=False. Successful --help exits
        # with code 0 after argparse already printed the help text; let it
        # pass through. Other codes are real parse failures.
        if exc.code == 0:
            return 0
        return _emit_envelope(
            envelope=_err_envelope(
                "cross-agent-review", CROSS_AGENT_REVIEW_VERSION,
                ErrorKind.INPUT_INVALID, "argv parse error (missing/invalid arguments)",
            ),
            pretty=False,
            exit_code=2,
        )

    if unknown:
        # Unknown argv tokens are an argv parse error per the universal
        # Result contract (exit 2), distinct from a capability-side
        # INPUT_INVALID (exit 1). Same kind in the envelope, different
        # exit code.
        return _emit_envelope(
            envelope=_err_envelope(
                "cross-agent-review", CROSS_AGENT_REVIEW_VERSION,
                ErrorKind.INPUT_INVALID, f"unknown args: {unknown}",
            ),
            pretty=ns.pretty,
            exit_code=2,
        )

    inp = CrossAgentReviewInput(
        kind=ns.kind,
        target=ns.target,
        feature_id=ns.feature_id,
        reviewer=ns.reviewer,
        criteria=ns.criteria,
        context=ns.context,
        prompt=ns.prompt,
    )

    started = time.monotonic()
    reviewers = _load_reviewers()
    result = cross_agent_review(inp, reviewers=reviewers)
    duration_ms = int((time.monotonic() - started) * 1000)

    envelope = result.to_json(
        capability="cross-agent-review",
        version=CROSS_AGENT_REVIEW_VERSION,
        duration_ms=duration_ms,
    )
    exit_code = 0 if result.ok else 1
    return _emit_envelope(envelope=envelope, pretty=ns.pretty, exit_code=exit_code)


def _load_reviewers() -> dict:
    """Pick reviewer backends from env vars.

    Fixture overrides (ORCA_FIXTURE_REVIEWER_<NAME>) win for tests; if none,
    ORCA_LIVE=1 enables the real backend factory. If neither is set, the
    capability layer surfaces missing-reviewer as Err(INPUT_INVALID).
    """
    reviewers: dict = {}
    for name, live_factory in (
        ("claude", _live_claude),
        ("codex", _live_codex),
    ):
        reviewer = _build_reviewer(name, live_factory)
        if reviewer is not None:
            reviewers[name] = reviewer
    return reviewers


def _build_reviewer(name: str, live_factory):
    """Construct a single reviewer for `name`: fixture override first,
    then live factory if ORCA_LIVE=1, otherwise None."""
    fixture = os.environ.get(f"ORCA_FIXTURE_REVIEWER_{name.upper()}")
    if fixture:
        return FixtureReviewer(scenario=Path(fixture), name=name)
    if os.environ.get("ORCA_LIVE") == "1":
        return live_factory()
    return None


def _live_claude():
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None
    return ClaudeReviewer(client=anthropic.Anthropic())


def _live_codex():
    return CodexReviewer()


def _err_envelope(capability: str, version: str, kind: ErrorKind, message: str) -> dict:
    """Build a CLI-side error envelope (e.g., for argparse failures).

    Routes through Err(Error).to_json so envelope shape stays consistent
    with capability-returned envelopes. duration_ms is 0 for CLI-side errors
    since no capability ran.
    """
    return Err(Error(kind=kind, message=message)).to_json(
        capability=capability,
        version=version,
        duration_ms=0,
    )


def _run_worktree_overlap_check(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="orca-cli worktree-overlap-check",
        exit_on_error=False,
    )
    parser.add_argument("--input", default="-",
                        help="path to JSON input file, or '-' for stdin")
    parser.add_argument("--pretty", action="store_true",
                        help="emit human-readable summary instead of JSON envelope")

    try:
        ns, unknown = parser.parse_known_args(args)
    except argparse.ArgumentError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "worktree-overlap-check", WORKTREE_OVERLAP_CHECK_VERSION,
                ErrorKind.INPUT_INVALID, f"argv parse error: {exc}",
            ),
            pretty=False,
            exit_code=2,
        )
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        return _emit_envelope(
            envelope=_err_envelope(
                "worktree-overlap-check", WORKTREE_OVERLAP_CHECK_VERSION,
                ErrorKind.INPUT_INVALID, "argv parse error (missing/invalid arguments)",
            ),
            pretty=False,
            exit_code=2,
        )

    if unknown:
        return _emit_envelope(
            envelope=_err_envelope(
                "worktree-overlap-check", WORKTREE_OVERLAP_CHECK_VERSION,
                ErrorKind.INPUT_INVALID, f"unknown args: {unknown}",
            ),
            pretty=ns.pretty,
            exit_code=2,
        )

    started = time.monotonic()
    try:
        if ns.input == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(ns.input).read_text(encoding="utf-8")
    except OSError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "worktree-overlap-check", WORKTREE_OVERLAP_CHECK_VERSION,
                ErrorKind.INPUT_INVALID, f"cannot read input: {exc}",
            ),
            pretty=ns.pretty,
            exit_code=1,
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "worktree-overlap-check", WORKTREE_OVERLAP_CHECK_VERSION,
                ErrorKind.INPUT_INVALID, f"invalid JSON: {exc}",
            ),
            pretty=ns.pretty,
            exit_code=1,
        )

    try:
        inp = WorktreeOverlapInput(
            worktrees=[WorktreeInfo(**wt) for wt in data.get("worktrees", [])],
            proposed_writes=data.get("proposed_writes", []),
            repo_root=data.get("repo_root"),
        )
    except (TypeError, KeyError) as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "worktree-overlap-check", WORKTREE_OVERLAP_CHECK_VERSION,
                ErrorKind.INPUT_INVALID, f"invalid worktree input shape: {exc}",
            ),
            pretty=ns.pretty,
            exit_code=1,
        )

    result = worktree_overlap_check(inp)
    duration_ms = int((time.monotonic() - started) * 1000)
    envelope = result.to_json(
        capability="worktree-overlap-check",
        version=WORKTREE_OVERLAP_CHECK_VERSION,
        duration_ms=duration_ms,
    )
    return _emit_envelope(
        envelope=envelope,
        pretty=ns.pretty,
        exit_code=0 if result.ok else 1,
    )


def _emit_envelope(*, envelope: dict, pretty: bool, exit_code: int) -> int:
    if pretty:
        if envelope["ok"]:
            _print_pretty_success(envelope)
        else:
            print(f"ERROR ({envelope['error']['kind']}): {envelope['error']['message']}")
    else:
        print(json.dumps(envelope, indent=2))
    return exit_code


def _print_pretty_success(envelope: dict) -> None:
    """Render success envelope based on capability shape."""
    capability = envelope.get("metadata", {}).get("capability", "")
    result = envelope.get("result", {})

    if capability == "cross-agent-review":
        findings = result.get("findings", [])
        print(f"OK ({len(findings)} findings)")
        for f in findings:
            evidence = ",".join(f.get("evidence", []))
            suffix = f" - {evidence}" if evidence else ""
            print(f"  [{f['severity']}] {f['summary']}{suffix}")
    elif capability == "worktree-overlap-check":
        if result.get("safe"):
            print("OK (safe: no conflicts)")
        else:
            print(f"OK (NOT safe: {len(result.get('conflicts', []))} conflicts, "
                  f"{len(result.get('proposed_overlaps', []))} proposed overlaps)")
            for c in result.get("conflicts", []):
                print(f"  conflict: {c['path']} between {', '.join(c['worktrees'])}")
            for o in result.get("proposed_overlaps", []):
                print(f"  proposed: {o['path']} blocked by {o['blocked_by']}")
    else:
        # Fallback: dump JSON for unknown capabilities
        print(json.dumps(envelope, indent=2))


_register("cross-agent-review", _run_cross_agent_review, CROSS_AGENT_REVIEW_VERSION)
_register("worktree-overlap-check", _run_worktree_overlap_check, WORKTREE_OVERLAP_CHECK_VERSION)


if __name__ == "__main__":
    raise SystemExit(main())
