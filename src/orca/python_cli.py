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
  --claude-findings-file / --codex-findings-file -> FileBackedReviewer (host harness)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Sequence
from importlib.metadata import version as _pkg_version
from pathlib import Path

from orca.capabilities.citation_validator import (
    VERSION as CITATION_VALIDATOR_VERSION,
    CitationValidatorInput,
    citation_validator,
)
from orca.capabilities.completion_gate import (
    VERSION as COMPLETION_GATE_VERSION,
    CompletionGateInput,
    completion_gate,
)
from orca.capabilities.contradiction_detector import (
    VERSION as CONTRADICTION_DETECTOR_VERSION,
    ContradictionDetectorInput,
    contradiction_detector,
)
from orca.capabilities.cross_agent_review import (
    DEFAULT_REVIEW_PROMPT,
    VERSION as CROSS_AGENT_REVIEW_VERSION,
    CrossAgentReviewInput,
    cross_agent_review,
)
from orca.capabilities.flow_state_projection import (
    VERSION as FLOW_STATE_PROJECTION_VERSION,
    FlowStateProjectionInput,
    flow_state_projection,
)
from orca.capabilities.worktree_overlap_check import (
    VERSION as WORKTREE_OVERLAP_CHECK_VERSION,
    WorktreeInfo,
    WorktreeOverlapInput,
    worktree_overlap_check,
)
from orca.core.adoption.apply import apply as adoption_apply
from orca.core.adoption.revert import revert as adoption_revert
from orca.core.adoption.wizard import run_adopt
from orca.core.errors import Error, ErrorKind
from orca.core.result import Err
from orca.core.reviewers._parse import parse_findings_array, validate_findings_array
from orca.core.reviewers.base import ReviewerError
from orca.core.reviewers.claude import ClaudeReviewer
from orca.core.reviewers.codex import CodexReviewer
from orca.core.reviewers.file_backed import MAX_FILE_BYTES, FileBackedReviewer
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

    if argv[0] in ("--version", "-V"):
        print(f"orca {_pkg_version('orca')}")
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
    parser.add_argument("--claude-findings-file", default=None,
                        help="path to a JSON file with pre-authored claude findings; bypasses SDK")
    parser.add_argument("--codex-findings-file", default=None,
                        help="path to a JSON file with pre-authored codex findings; bypasses SDK")
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

    # Pre-flight validation for findings-file flags. Per the Phase 4a spec
    # error-handling table, every file-flag failure mode (missing, symlink,
    # oversized, malformed JSON, non-array, bad finding shape) MUST surface
    # as Err(INPUT_INVALID, "<slot>: <reason>") with exit 1. Without this
    # preflight, those failures would leak from FileBackedReviewer.review()
    # as ReviewerError -> BACKEND_FAILURE.
    for slot, path_str in (
        ("claude-findings-file", ns.claude_findings_file),
        ("codex-findings-file", ns.codex_findings_file),
    ):
        if not path_str:
            continue
        err_msg = _validate_findings_file_eagerly(path_str)
        if err_msg is not None:
            return _emit_envelope(
                envelope=_err_envelope(
                    "cross-agent-review", CROSS_AGENT_REVIEW_VERSION,
                    ErrorKind.INPUT_INVALID, f"{slot}: {err_msg}",
                ),
                pretty=ns.pretty,
                exit_code=1,
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
    reviewers = _load_reviewers(
        claude_findings_file=ns.claude_findings_file,
        codex_findings_file=ns.codex_findings_file,
    )
    result = cross_agent_review(inp, reviewers=reviewers)
    duration_ms = round((time.monotonic() - started) * 1000, 1)  # float, 0.1ms precision

    envelope = result.to_json(
        capability="cross-agent-review",
        version=CROSS_AGENT_REVIEW_VERSION,
        duration_ms=duration_ms,
    )
    exit_code = 0 if result.ok else 1
    return _emit_envelope(envelope=envelope, pretty=ns.pretty, exit_code=exit_code)


def _load_reviewers(
    *,
    claude_findings_file: str | None = None,
    codex_findings_file: str | None = None,
) -> dict:
    """Pick reviewer backends from CLI flags or env vars.

    Precedence per reviewer slot:
      1. --<name>-findings-file flag -> FileBackedReviewer
      2. ORCA_FIXTURE_REVIEWER_<NAME> env var -> FixtureReviewer
      3. ORCA_LIVE=1 -> live SDK/CLI factory
      4. None (capability surfaces missing-reviewer as Err(INPUT_INVALID))
    """
    reviewers: dict = {}
    file_flags = {
        "claude": claude_findings_file,
        "codex": codex_findings_file,
    }
    for name, live_factory in (
        ("claude", _live_claude),
        ("codex", _live_codex),
    ):
        reviewer = _build_reviewer(name, live_factory, findings_file=file_flags[name])
        if reviewer is not None:
            reviewers[name] = reviewer
    return reviewers


def _build_reviewer(name: str, live_factory, *, findings_file: str | None = None):
    """Construct a single reviewer for `name` per precedence in _load_reviewers."""
    if findings_file:
        return FileBackedReviewer(name=name, findings_path=Path(findings_file))
    fixture = os.environ.get(f"ORCA_FIXTURE_REVIEWER_{name.upper()}")
    if fixture:
        return FixtureReviewer(scenario=Path(fixture), name=name)
    if os.environ.get("ORCA_LIVE") == "1":
        return live_factory()
    return None


def _validate_findings_file_eagerly(path_str: str) -> str | None:
    """Pre-flight validation for --*-findings-file paths.

    Returns None on success, or a human-readable error message string
    suitable for INPUT_INVALID envelopes. Mirrors FileBackedReviewer's
    own validation but runs at the CLI boundary so failures surface as
    INPUT_INVALID rather than BACKEND_FAILURE, per the Phase 4a spec
    error-handling table.
    """
    path = Path(path_str)
    if path.is_symlink():
        return f"symlinks rejected: {path}"
    if not path.exists():
        return f"file not found: {path}"
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        return f"file exceeds {MAX_FILE_BYTES} byte cap ({size} bytes): {path}"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"read error ({exc}): {path}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"invalid JSON ({exc}): {path}"
    if not isinstance(data, list):
        return f"expected JSON array, got {type(data).__name__}: {path}"
    try:
        validate_findings_array(data, source="cli-preflight")
    except Exception as exc:
        return f"finding validation failed ({exc}): {path}"
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
    duration_ms = round((time.monotonic() - started) * 1000, 1)  # float, 0.1ms precision
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


def _run_flow_state_projection(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="orca-cli flow-state-projection",
        exit_on_error=False,
    )
    parser.add_argument("--feature-id", default=None)
    parser.add_argument("--feature-dir", default=None)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--pretty", action="store_true",
                        help="emit human-readable summary instead of JSON envelope")

    try:
        ns, unknown = parser.parse_known_args(args)
    except argparse.ArgumentError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "flow-state-projection", FLOW_STATE_PROJECTION_VERSION,
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
                "flow-state-projection", FLOW_STATE_PROJECTION_VERSION,
                ErrorKind.INPUT_INVALID, "argv parse error (missing/invalid arguments)",
            ),
            pretty=False,
            exit_code=2,
        )

    if unknown:
        return _emit_envelope(
            envelope=_err_envelope(
                "flow-state-projection", FLOW_STATE_PROJECTION_VERSION,
                ErrorKind.INPUT_INVALID, f"unknown args: {unknown}",
            ),
            pretty=ns.pretty,
            exit_code=2,
        )

    inp = FlowStateProjectionInput(
        feature_id=ns.feature_id,
        feature_dir=ns.feature_dir,
        repo_root=ns.repo_root,
    )

    started = time.monotonic()
    result = flow_state_projection(inp)
    duration_ms = round((time.monotonic() - started) * 1000, 1)  # float, 0.1ms precision

    envelope = result.to_json(
        capability="flow-state-projection",
        version=FLOW_STATE_PROJECTION_VERSION,
        duration_ms=duration_ms,
    )
    return _emit_envelope(
        envelope=envelope,
        pretty=ns.pretty,
        exit_code=0 if result.ok else 1,
    )


def _run_completion_gate(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="orca-cli completion-gate",
        exit_on_error=False,
    )
    parser.add_argument("--feature-dir", required=True)
    parser.add_argument("--target-stage", required=True)
    parser.add_argument("--evidence-json", default=None,
                        help="JSON-encoded evidence dict (e.g., '{\"ci_green\": true}')")
    parser.add_argument("--pretty", action="store_true",
                        help="emit human-readable summary instead of JSON envelope")

    try:
        ns, unknown = parser.parse_known_args(args)
    except argparse.ArgumentError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "completion-gate", COMPLETION_GATE_VERSION,
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
                "completion-gate", COMPLETION_GATE_VERSION,
                ErrorKind.INPUT_INVALID, "argv parse error (missing/invalid arguments)",
            ),
            pretty=False,
            exit_code=2,
        )

    if unknown:
        return _emit_envelope(
            envelope=_err_envelope(
                "completion-gate", COMPLETION_GATE_VERSION,
                ErrorKind.INPUT_INVALID, f"unknown args: {unknown}",
            ),
            pretty=ns.pretty,
            exit_code=2,
        )

    evidence: dict = {}
    if ns.evidence_json:
        try:
            evidence = json.loads(ns.evidence_json)
            if not isinstance(evidence, dict):
                raise TypeError("evidence must be a JSON object")
        except (json.JSONDecodeError, TypeError) as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "completion-gate", COMPLETION_GATE_VERSION,
                    ErrorKind.INPUT_INVALID, f"invalid --evidence-json: {exc}",
                ),
                pretty=ns.pretty,
                exit_code=1,
            )

    inp = CompletionGateInput(
        feature_dir=ns.feature_dir,
        target_stage=ns.target_stage,
        evidence=evidence,
    )

    started = time.monotonic()
    result = completion_gate(inp)
    duration_ms = round((time.monotonic() - started) * 1000, 1)  # float, 0.1ms precision

    envelope = result.to_json(
        capability="completion-gate",
        version=COMPLETION_GATE_VERSION,
        duration_ms=duration_ms,
    )
    return _emit_envelope(
        envelope=envelope,
        pretty=ns.pretty,
        exit_code=0 if result.ok else 1,
    )


def _run_citation_validator(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="orca-cli citation-validator",
        exit_on_error=False,
    )
    parser.add_argument("--content-path", default=None)
    parser.add_argument("--content-text", default=None)
    parser.add_argument("--reference-set", action="append", default=[],
                        help="path to a reference (repeatable)")
    parser.add_argument("--mode", default="strict", choices=["strict", "lenient"])
    parser.add_argument("--skip-pattern", action="append", default=[],
                        dest="skip_patterns",
                        help="extra regex (matched per-line) for lines to skip "
                             "on top of built-in scaffolding patterns; repeatable")
    parser.add_argument("--pretty", action="store_true",
                        help="emit human-readable summary instead of JSON envelope")

    try:
        ns, unknown = parser.parse_known_args(args)
    except argparse.ArgumentError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "citation-validator", CITATION_VALIDATOR_VERSION,
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
                "citation-validator", CITATION_VALIDATOR_VERSION,
                ErrorKind.INPUT_INVALID, "argv parse error (missing/invalid arguments)",
            ),
            pretty=False,
            exit_code=2,
        )

    if unknown:
        return _emit_envelope(
            envelope=_err_envelope(
                "citation-validator", CITATION_VALIDATOR_VERSION,
                ErrorKind.INPUT_INVALID, f"unknown args: {unknown}",
            ),
            pretty=ns.pretty,
            exit_code=2,
        )

    inp = CitationValidatorInput(
        content_path=ns.content_path,
        content_text=ns.content_text,
        reference_set=ns.reference_set,
        mode=ns.mode,
        skip_patterns=ns.skip_patterns,
    )

    started = time.monotonic()
    result = citation_validator(inp)
    duration_ms = round((time.monotonic() - started) * 1000, 1)  # float, 0.1ms precision

    envelope = result.to_json(
        capability="citation-validator",
        version=CITATION_VALIDATOR_VERSION,
        duration_ms=duration_ms,
    )
    return _emit_envelope(
        envelope=envelope,
        pretty=ns.pretty,
        exit_code=0 if result.ok else 1,
    )


def _run_contradiction_detector(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="orca-cli contradiction-detector",
        exit_on_error=False,
    )
    parser.add_argument("--new-content", required=True)
    parser.add_argument("--prior-evidence", action="append", required=True, default=[],
                        help="path to prior evidence file (repeatable, at least one required)")
    parser.add_argument("--reviewer", default="cross", choices=["claude", "codex", "cross"])
    parser.add_argument("--claude-findings-file", default=None,
                        help="path to a JSON file with pre-authored claude findings; bypasses SDK")
    parser.add_argument("--codex-findings-file", default=None,
                        help="path to a JSON file with pre-authored codex findings; bypasses SDK")
    parser.add_argument("--pretty", action="store_true",
                        help="emit human-readable summary instead of JSON envelope")

    try:
        ns, unknown = parser.parse_known_args(args)
    except argparse.ArgumentError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "contradiction-detector", CONTRADICTION_DETECTOR_VERSION,
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
                "contradiction-detector", CONTRADICTION_DETECTOR_VERSION,
                ErrorKind.INPUT_INVALID, "argv parse error (missing/invalid arguments)",
            ),
            pretty=False,
            exit_code=2,
        )

    if unknown:
        return _emit_envelope(
            envelope=_err_envelope(
                "contradiction-detector", CONTRADICTION_DETECTOR_VERSION,
                ErrorKind.INPUT_INVALID, f"unknown args: {unknown}",
            ),
            pretty=ns.pretty,
            exit_code=2,
        )

    # Pre-flight validation for findings-file flags (mirrors cross-agent-review).
    for slot, path_str in (
        ("claude-findings-file", ns.claude_findings_file),
        ("codex-findings-file", ns.codex_findings_file),
    ):
        if not path_str:
            continue
        err_msg = _validate_findings_file_eagerly(path_str)
        if err_msg is not None:
            return _emit_envelope(
                envelope=_err_envelope(
                    "contradiction-detector", CONTRADICTION_DETECTOR_VERSION,
                    ErrorKind.INPUT_INVALID, f"{slot}: {err_msg}",
                ),
                pretty=ns.pretty,
                exit_code=1,
            )

    inp = ContradictionDetectorInput(
        new_content=ns.new_content,
        prior_evidence=ns.prior_evidence,
        reviewer=ns.reviewer,
    )

    started = time.monotonic()
    reviewers = _load_reviewers(
        claude_findings_file=ns.claude_findings_file,
        codex_findings_file=ns.codex_findings_file,
    )
    result = contradiction_detector(inp, reviewers=reviewers)
    duration_ms = round((time.monotonic() - started) * 1000, 1)  # float, 0.1ms precision

    envelope = result.to_json(
        capability="contradiction-detector",
        version=CONTRADICTION_DETECTOR_VERSION,
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


def _truncate(text: str, limit: int) -> str:
    """Truncate text to limit chars, appending '...' if shortened."""
    if len(text) <= limit:
        return text
    return text[:limit - 3] + "..."


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
    elif capability == "flow-state-projection":
        feature_id = result.get("feature_id", "?")
        stage = result.get("current_stage") or "ambiguous/unknown"
        next_step = result.get("next_step") or "none"
        completed = result.get("completed_milestones", [])
        incomplete = result.get("incomplete_milestones", [])
        print(f"OK feature={feature_id} stage={stage}")
        print(f"  next: {next_step}")
        if completed:
            print(f"  completed: {len(completed)}")
            for m in completed:
                stage_name = m.get("stage", "?")
                print(f"    - {stage_name}")
        if incomplete:
            print(f"  incomplete: {len(incomplete)}")
            for m in incomplete:
                stage_name = m.get("stage", "?")
                print(f"    - {stage_name}")
    elif capability == "completion-gate":
        status = result.get("status", "?")
        blockers = result.get("blockers", [])
        stale = result.get("stale_artifacts", [])
        gates = result.get("gates_evaluated", [])
        token = {"pass": "PASS", "blocked": "BLOCKED", "stale": "STALE"}.get(status, "OK")
        print(f"{token} status={status}")
        print(f"  gates: {len(gates)} evaluated")
        for g in gates:
            mark = "✓" if g.get("passed") else "✗"
            reason = f" - {g.get('reason')}" if g.get("reason") else ""
            print(f"    {mark} {g.get('gate', '?')}{reason}")
        if blockers:
            print(f"  blockers: {', '.join(blockers)}")
        if stale:
            print(f"  stale: {', '.join(stale)}")
    elif capability == "citation-validator":
        coverage = result.get("citation_coverage", 0.0)
        uncited = result.get("uncited_claims", [])
        broken = result.get("broken_refs", [])
        well = result.get("well_supported_claims", [])
        token = "OK" if not uncited and not broken else "ISSUES"
        print(f"{token} coverage={coverage}")
        print(f"  well_supported: {len(well)}")
        print(f"  uncited:        {len(uncited)}")
        for c in uncited:
            print(f"    line {c.get('line', '?')}: {_truncate(c.get('text', ''), 80)}")
        print(f"  broken_refs:    {len(broken)}")
        for r in broken:
            print(f"    line {r.get('line', '?')}: [{r.get('ref', '')}]")
    elif capability == "contradiction-detector":
        contradictions = result.get("contradictions", [])
        partial = result.get("partial", False)
        missing = result.get("missing_reviewers", [])
        token = "OK" if not contradictions else "ISSUES"
        partial_note = f" (partial; missing: {', '.join(missing)})" if partial else ""
        print(f"{token} {len(contradictions)} contradictions{partial_note}")
        for c in contradictions:
            confidence = c.get("confidence", "?")
            new_claim = _truncate(c.get("new_claim", ""), 80)
            refs = c.get("conflicting_evidence_refs", [])
            reviewers = c.get("reviewers", [])
            ref_display = ", ".join(refs) if refs else ""
            rev_display = "+".join(reviewers) if reviewers else "?"
            print(f"  [{confidence}] ({rev_display}) {new_claim}")
            if ref_display:
                print(f"    conflicts with: {ref_display}")
            resolution = c.get("suggested_resolution", "")
            if resolution:
                print(f"    resolution: {_truncate(resolution, 80)}")
    else:
        # Fallback: dump JSON for unknown capabilities
        print(json.dumps(envelope, indent=2))


def _run_parse_subagent_response(args: list[str]) -> int:
    """Validate raw subagent text on stdin, emit findings JSON on stdout.

    Reuses parse_findings_array from the SDK adapter pipeline so schema
    validation matches what the SDK adapter emits today. Failure path is
    Err(INPUT_INVALID) envelope on stdout, exit 1.
    """
    parser = argparse.ArgumentParser(
        prog="orca-cli parse-subagent-response",
        description="Extract + validate findings JSON from raw subagent text",
        exit_on_error=False,
    )
    parser.add_argument("--pretty", action="store_true",
                        help="emit human-readable summary on errors; success always emits findings JSON")
    try:
        ns, unknown = parser.parse_known_args(args)
    except argparse.ArgumentError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "parse-subagent-response", "0.1.0",
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
                "parse-subagent-response", "0.1.0",
                ErrorKind.INPUT_INVALID, "argv parse error (missing/invalid arguments)",
            ),
            pretty=False,
            exit_code=2,
        )
    if unknown:
        return _emit_envelope(
            envelope=_err_envelope(
                "parse-subagent-response", "0.1.0",
                ErrorKind.INPUT_INVALID, f"unknown args: {unknown}",
            ),
            pretty=ns.pretty,
            exit_code=2,
        )

    text = sys.stdin.read()
    try:
        findings = parse_findings_array(text, source="subagent-response")
    except ReviewerError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "parse-subagent-response", "0.1.0",
                ErrorKind.INPUT_INVALID, f"parse-subagent-response: {exc}",
            ),
            pretty=ns.pretty,
            exit_code=1,
        )

    print(json.dumps(findings))
    return 0


def _run_build_review_prompt(args: list[str]) -> int:
    """Emit the canonical review prompt on stdout (plain text, no envelope).

    v1: DEFAULT_REVIEW_PROMPT plus optional bullet-list of --criteria. Per-kind
    branching is accepted via --kind for forward-compat but does not branch in
    v1 (per Phase 4a spec; per-kind opinionation deferred).

    Used by slash commands to feed the same prompt to a Code Reviewer subagent
    that the SDK adapter would have used.
    """
    parser = argparse.ArgumentParser(
        prog="orca-cli build-review-prompt",
        description="Emit canonical review prompt for subagent dispatch",
        exit_on_error=False,
    )
    parser.add_argument("--kind", default="diff",
                        help="review subject kind; accepted for forward-compat (v1 does not branch)")
    parser.add_argument("--criteria", action="append", default=[],
                        help="review criterion (repeatable)")
    parser.add_argument("--context", action="append", default=[],
                        help="review context line (repeatable)")
    try:
        ns, unknown = parser.parse_known_args(args)
    except argparse.ArgumentError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "build-review-prompt", "0.1.0",
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
                "build-review-prompt", "0.1.0",
                ErrorKind.INPUT_INVALID, "argv parse error (missing/invalid arguments)",
            ),
            pretty=False,
            exit_code=2,
        )
    if unknown:
        return _emit_envelope(
            envelope=_err_envelope(
                "build-review-prompt", "0.1.0",
                ErrorKind.INPUT_INVALID, f"unknown args: {unknown}",
            ),
            pretty=False,
            exit_code=2,
        )

    parts: list[str] = [DEFAULT_REVIEW_PROMPT.strip()]
    if ns.criteria:
        parts.append("")
        parts.append("Criteria:")
        for c in ns.criteria:
            parts.append(f"- {c}")
    if ns.context:
        parts.append("")
        parts.append("Context:")
        for c in ns.context:
            parts.append(f"- {c}")
    print("\n".join(parts))
    return 0


def _run_adopt(args: list[str]) -> int:
    """Run the adoption wizard: detect host, write `.orca/adoption.toml`.

    Plain stdout/exit-code surface (no Result envelope) — adoption is a
    side-effecting installer step rather than a queryable capability.
    """
    parser = argparse.ArgumentParser(
        prog="orca-cli adopt",
        exit_on_error=False,
    )
    parser.add_argument("--host", default=None,
                        choices=["spec-kit", "openspec", "superpowers", "bare"])
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--repo-root", default=None,
                        help="path to repo root (default: cwd)")
    try:
        ns, unknown = parser.parse_known_args(args)
    except argparse.ArgumentError as exc:
        print(f"argv parse error: {exc}", file=sys.stderr)
        return 2
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        return 2

    if unknown:
        print(f"unknown args: {unknown}", file=sys.stderr)
        return 2

    repo_root = Path(ns.repo_root).resolve() if ns.repo_root else Path.cwd().resolve()
    try:
        manifest_path = run_adopt(
            repo_root=repo_root,
            host_override=ns.host,
            plan_only=ns.plan_only,
            force=ns.force,
            reset=ns.reset,
        )
    except (ValueError, FileExistsError) as exc:
        print(f"adopt failed: {exc}", file=sys.stderr)
        return 1

    print(f"manifest written: {manifest_path}")
    if not ns.plan_only:
        try:
            adoption_apply(repo_root=repo_root)
        except Exception as exc:
            print(f"apply after adopt failed: {exc}", file=sys.stderr)
            return 1
        print(f"applied; state: {repo_root}/.orca/adoption-state.json")
    return 0


def _run_apply(args: list[str]) -> int:
    """Execute (or revert / preview) the manifest at `.orca/adoption.toml`."""
    parser = argparse.ArgumentParser(
        prog="orca-cli apply",
        exit_on_error=False,
    )
    parser.add_argument("--revert", action="store_true")
    parser.add_argument("--keep-state", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo-root", default=None,
                        help="path to repo root (default: cwd)")
    try:
        ns, unknown = parser.parse_known_args(args)
    except argparse.ArgumentError as exc:
        print(f"argv parse error: {exc}", file=sys.stderr)
        return 2
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        return 2

    if unknown:
        print(f"unknown args: {unknown}", file=sys.stderr)
        return 2

    repo_root = Path(ns.repo_root).resolve() if ns.repo_root else Path.cwd().resolve()
    try:
        if ns.revert:
            adoption_revert(repo_root=repo_root, keep_state=ns.keep_state)
            print("reverted")
            return 0
        if ns.dry_run:
            # Read manifest; print what WOULD be applied; no writes.
            from orca.core.adoption.manifest import load_manifest
            manifest = load_manifest(repo_root / ".orca" / "adoption.toml")
            print(f"would apply manifest at {repo_root / '.orca' / 'adoption.toml'}")
            print(f"  host.system = {manifest.host.system}")
            print(f"  agents_md_path = {manifest.host.agents_md_path}")
            print(f"  claude_md.policy = {manifest.claude_md.policy}")
            return 0
        adoption_apply(repo_root=repo_root)
        print(f"applied; state: {repo_root}/.orca/adoption-state.json")
        return 0
    except Exception as exc:
        print(f"apply failed: {exc}", file=sys.stderr)
        return 1


def _run_resolve_path(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="orca-cli resolve-path",
        exit_on_error=False,
    )
    parser.add_argument("--kind", required=True,
                        choices=["feature-dir", "constitution", "agents-md",
                                 "reviews-dir", "reference-set"])
    parser.add_argument("--feature-id", default=None)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--pretty", action="store_true")

    try:
        ns, unknown = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        if isinstance(exc, SystemExit) and exc.code == 0:
            return 0
        return 2

    if unknown:
        return 2

    repo_root = Path(ns.repo_root).resolve() if ns.repo_root else Path.cwd().resolve()

    # Validate flag combinations
    requires_feature_id = ns.kind in ("feature-dir", "reference-set")
    if requires_feature_id and not ns.feature_id:
        return _emit_envelope(
            envelope=_err_envelope(
                "resolve-path", "1.0.0",
                ErrorKind.INPUT_INVALID,
                f"--feature-id is required when --kind={ns.kind}",
            ),
            pretty=ns.pretty,
            exit_code=1,
        )
    if not requires_feature_id and ns.feature_id is not None:
        return _emit_envelope(
            envelope=_err_envelope(
                "resolve-path", "1.0.0",
                ErrorKind.INPUT_INVALID,
                f"--feature-id not accepted when --kind={ns.kind}",
            ),
            pretty=ns.pretty,
            exit_code=1,
        )

    # Validate feature_id against path-safety contract Class D
    if ns.feature_id is not None:
        err = _validate_feature_id(ns.feature_id)
        if err is not None:
            return _emit_envelope(
                envelope=_err_envelope(
                    "resolve-path", "1.0.0",
                    ErrorKind.INPUT_INVALID, err,
                ),
                pretty=ns.pretty,
                exit_code=1,
            )

    # Pick adapter: manifest-driven OR detection-driven
    from orca.core.adoption.manifest import ManifestError
    from orca.core.host_layout import detect, from_manifest
    try:
        layout = from_manifest(repo_root)
    except (FileNotFoundError, ManifestError):
        layout = detect(repo_root)

    # Dispatch
    paths: list[Path] = []
    if ns.kind == "feature-dir":
        paths = [layout.resolve_feature_dir(ns.feature_id)]
    elif ns.kind == "constitution":
        cp = layout.constitution_path()
        if cp is not None:
            paths = [cp]
    elif ns.kind == "agents-md":
        paths = [layout.agents_md_path()]
    elif ns.kind == "reviews-dir":
        paths = [layout.review_artifact_dir()]
    elif ns.kind == "reference-set":
        from orca.core.host_layout.reference_set import discover
        feature_dir = layout.resolve_feature_dir(ns.feature_id)
        paths = discover(feature_dir)

    if ns.pretty:
        adapter_name = type(layout).__name__
        print(f"kind: {ns.kind}")
        print(f"adapter: {adapter_name}")
        for p in paths:
            print(p)
    else:
        for p in paths:
            print(p)

    return 0


_FEATURE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_feature_id(value: str) -> str | None:
    """Per path-safety contract Class D. Returns error message or None."""
    if not value:
        return "--feature-id is empty"
    if value in (".", ".."):
        return f"--feature-id={value!r} not allowed"
    if value.startswith("-"):
        return f"--feature-id={value!r} cannot start with '-'"
    if len(value) > 128:
        return "--feature-id exceeds 128 chars"
    if not _FEATURE_ID_RE.match(value):
        return f"--feature-id={value!r} must match [A-Za-z0-9._-]+"
    return None


_register("cross-agent-review", _run_cross_agent_review, CROSS_AGENT_REVIEW_VERSION)
_register("worktree-overlap-check", _run_worktree_overlap_check, WORKTREE_OVERLAP_CHECK_VERSION)
_register("flow-state-projection", _run_flow_state_projection, FLOW_STATE_PROJECTION_VERSION)
_register("completion-gate", _run_completion_gate, COMPLETION_GATE_VERSION)
_register("citation-validator", _run_citation_validator, CITATION_VALIDATOR_VERSION)
_register("contradiction-detector", _run_contradiction_detector, CONTRADICTION_DETECTOR_VERSION)
_register("parse-subagent-response", _run_parse_subagent_response, "0.1.0")
_register("build-review-prompt", _run_build_review_prompt, "0.1.0")
_register("adopt", _run_adopt, "1.0.0")
_register("apply", _run_apply, "1.0.0")
_register("resolve-path", _run_resolve_path, "1.0.0")


if __name__ == "__main__":
    raise SystemExit(main())
