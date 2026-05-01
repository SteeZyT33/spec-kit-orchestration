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
from orca.core.path_safety import PathSafetyError, validate_findings_file, validate_identifier, validate_repo_dir, validate_repo_file
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

    if ns.feature_id is not None:
        try:
            validate_identifier(ns.feature_id, field="--feature-id")
        except PathSafetyError as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "cross-agent-review", CROSS_AGENT_REVIEW_VERSION,
                    ErrorKind.INPUT_INVALID, str(exc),
                    detail=exc.to_error_detail(),
                ),
                pretty=ns.pretty,
                exit_code=1,
            )

    target_root = Path.cwd().resolve()
    for t in ns.target:
        try:
            t_path = Path(t).resolve()
            if t_path.is_dir():
                validate_repo_dir(t, root=target_root, field="--target")
            else:
                validate_repo_file(t, root=target_root, field="--target")
        except PathSafetyError as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "cross-agent-review", CROSS_AGENT_REVIEW_VERSION,
                    ErrorKind.INPUT_INVALID, str(exc),
                    detail=exc.to_error_detail(),
                ),
                pretty=ns.pretty,
                exit_code=1,
            )

    # Pre-flight validation for findings-file flags. Per the Phase 4a spec
    # error-handling table, every file-flag failure mode (missing, symlink,
    # oversized, malformed JSON, non-array, bad finding shape) MUST surface
    # as Err(INPUT_INVALID, "<slot>: <reason>") with exit 1. Without this
    # preflight, those failures would leak from FileBackedReviewer.review()
    # as ReviewerError -> BACKEND_FAILURE.
    findings_root = Path.cwd().resolve()
    for slot, path_str in (
        ("--claude-findings-file", ns.claude_findings_file),
        ("--codex-findings-file", ns.codex_findings_file),
    ):
        if not path_str:
            continue
        err_msg, detail = _validate_findings_file_eagerly(
            path_str, root=findings_root, field=slot,
        )
        if err_msg is not None:
            return _emit_envelope(
                envelope=_err_envelope(
                    "cross-agent-review", CROSS_AGENT_REVIEW_VERSION,
                    ErrorKind.INPUT_INVALID, f"{slot}: {err_msg}",
                    detail=detail,
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


def _validate_findings_file_eagerly(
    path_str: str, *, root: Path, field: str,
) -> tuple[str | None, dict | None]:
    """Pre-flight validation for --*-findings-file paths.

    Path-shape checks delegate to orca.core.path_safety.validate_findings_file.
    Content-layer checks (JSON parse, array shape, finding schema) stay here
    because they emit distinct rule_violated values.

    Returns (error_message, detail_dict_or_None) — None on success.
    """
    try:
        path = validate_findings_file(path_str, root=root, field=field)
    except PathSafetyError as exc:
        return str(exc), exc.to_error_detail()

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"read error ({exc}): {path}", {
            "field": field, "rule_violated": "missing_findings_file",
            "value_redacted": str(path),
        }
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"invalid JSON ({exc}): {path}", {
            "field": field, "rule_violated": "malformed_findings_file",
            "value_redacted": str(path),
        }
    if not isinstance(data, list):
        return f"expected JSON array, got {type(data).__name__}: {path}", {
            "field": field, "rule_violated": "malformed_findings_file",
            "value_redacted": str(path),
        }
    try:
        validate_findings_array(data, source="cli-preflight")
    except Exception as exc:
        return f"finding validation failed ({exc}): {path}", {
            "field": field, "rule_violated": "malformed_findings_file",
            "value_redacted": str(path),
        }
    return None, None


def _live_claude():
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None
    return ClaudeReviewer(client=anthropic.Anthropic())


def _live_codex():
    return CodexReviewer()


def _err_envelope(
    capability: str,
    version: str,
    kind: ErrorKind,
    message: str,
    *,
    detail: dict | None = None,
) -> dict:
    """Build a CLI-side error envelope (e.g., for argparse failures).

    Routes through Err(Error).to_json so envelope shape stays consistent
    with capability-returned envelopes. duration_ms is 0 for CLI-side errors
    since no capability ran. Optional `detail` carries structured fields
    for path-safety violations (field/rule_violated/value_redacted).
    """
    return Err(Error(kind=kind, message=message, detail=detail)).to_json(
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

    if not isinstance(data, dict):
        return _emit_envelope(
            envelope=_err_envelope(
                "worktree-overlap-check", WORKTREE_OVERLAP_CHECK_VERSION,
                ErrorKind.INPUT_INVALID,
                f"expected JSON object, got {type(data).__name__}",
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

    if ns.feature_id is not None:
        try:
            validate_identifier(ns.feature_id, field="--feature-id")
        except PathSafetyError as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "flow-state-projection", FLOW_STATE_PROJECTION_VERSION,
                    ErrorKind.INPUT_INVALID, str(exc),
                    detail=exc.to_error_detail(),
                ),
                pretty=ns.pretty,
                exit_code=1,
            )

    if ns.feature_dir is not None:
        fsp_root = Path.cwd().resolve()
        try:
            validate_repo_dir(ns.feature_dir, root=fsp_root, field="--feature-dir")
        except PathSafetyError as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "flow-state-projection", FLOW_STATE_PROJECTION_VERSION,
                    ErrorKind.INPUT_INVALID, str(exc),
                    detail=exc.to_error_detail(),
                ),
                pretty=ns.pretty,
                exit_code=1,
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

    feature_root = Path.cwd().resolve()
    try:
        validate_repo_dir(ns.feature_dir, root=feature_root, field="--feature-dir")
    except PathSafetyError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "completion-gate", COMPLETION_GATE_VERSION,
                ErrorKind.INPUT_INVALID, str(exc),
                detail=exc.to_error_detail(),
            ),
            pretty=ns.pretty,
            exit_code=1,
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

    citation_root = Path.cwd().resolve()
    if ns.content_path is not None:
        try:
            validate_repo_file(ns.content_path, root=citation_root, field="--content-path")
        except PathSafetyError as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "citation-validator", CITATION_VALIDATOR_VERSION,
                    ErrorKind.INPUT_INVALID, str(exc),
                    detail=exc.to_error_detail(),
                ),
                pretty=ns.pretty,
                exit_code=1,
            )

    for ref in ns.reference_set:
        try:
            ref_path = Path(ref).resolve()
            if ref_path.is_dir():
                validate_repo_dir(ref, root=citation_root, field="--reference-set")
            else:
                validate_repo_file(ref, root=citation_root, field="--reference-set")
        except PathSafetyError as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "citation-validator", CITATION_VALIDATOR_VERSION,
                    ErrorKind.INPUT_INVALID, str(exc),
                    detail=exc.to_error_detail(),
                ),
                pretty=ns.pretty,
                exit_code=1,
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

    evidence_root = Path.cwd().resolve()
    try:
        validate_repo_file(ns.new_content, root=evidence_root, field="--new-content")
    except PathSafetyError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "contradiction-detector", CONTRADICTION_DETECTOR_VERSION,
                ErrorKind.INPUT_INVALID, str(exc),
                detail=exc.to_error_detail(),
            ),
            pretty=ns.pretty,
            exit_code=1,
        )

    for ev in ns.prior_evidence:
        try:
            validate_repo_file(ev, root=evidence_root, field="--prior-evidence")
        except PathSafetyError as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "contradiction-detector", CONTRADICTION_DETECTOR_VERSION,
                    ErrorKind.INPUT_INVALID, str(exc),
                    detail=exc.to_error_detail(),
                ),
                pretty=ns.pretty,
                exit_code=1,
            )

    # Pre-flight validation for findings-file flags (mirrors cross-agent-review).
    findings_root = Path.cwd().resolve()
    for slot, path_str in (
        ("--claude-findings-file", ns.claude_findings_file),
        ("--codex-findings-file", ns.codex_findings_file),
    ):
        if not path_str:
            continue
        err_msg, detail = _validate_findings_file_eagerly(
            path_str, root=findings_root, field=slot,
        )
        if err_msg is not None:
            return _emit_envelope(
                envelope=_err_envelope(
                    "contradiction-detector", CONTRADICTION_DETECTOR_VERSION,
                    ErrorKind.INPUT_INVALID, f"{slot}: {err_msg}",
                    detail=detail,
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
        try:
            validate_identifier(ns.feature_id, field="--feature-id")
        except PathSafetyError as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "resolve-path", "1.0.0",
                    ErrorKind.INPUT_INVALID, str(exc),
                    detail=exc.to_error_detail(),
                ),
                pretty=ns.pretty,
                exit_code=1,
            )

    # Pick adapter: manifest-driven OR detection-driven.
    # Only fall back to detection when there's no manifest file at all.
    # A malformed manifest (ManifestError) must surface to the operator
    # rather than silently being ignored.
    from orca.core.adoption.manifest import ManifestError
    from orca.core.host_layout import detect, from_manifest
    try:
        layout = from_manifest(repo_root)
    except FileNotFoundError:
        layout = detect(repo_root)
    except ManifestError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "resolve-path", "1.0.0",
                ErrorKind.INPUT_INVALID, f"invalid adoption manifest: {exc}",
            ),
            pretty=ns.pretty,
            exit_code=1,
        )

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



def _run_wt(args: list[str]) -> int:
    """Top-level wt dispatcher. Routes wt <verb> to _run_wt_<verb>."""
    if not args:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0",
                ErrorKind.INPUT_INVALID,
                "wt requires a subverb (new|start|cd|ls|merge|rm|init|"
                "config|version|doctor)",
            ),
            pretty=False,
            exit_code=2,
        )
    verb = args[0]
    handlers = {
        "new": _run_wt_new,
        "start": _run_wt_start,
        "cd": _run_wt_cd,
        "ls": _run_wt_ls,
        "rm": _run_wt_rm,
        "merge": _run_wt_merge,
        "init": _run_wt_init,
        "config": _run_wt_config,
        "version": _run_wt_version,
        "doctor": _run_wt_doctor,
    }
    handler = handlers.get(verb)
    if handler is None:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0",
                ErrorKind.INPUT_INVALID,
                f"unknown wt verb: {verb}",
            ),
            pretty=False,
            exit_code=2,
        )
    return handler(args[1:])


def _state_root(repo_root: Path) -> Path:
    """State directory for orca worktrees: registry/sidecars/events/lock/hooks.

    Always at ``<repo>/.orca/worktrees/`` regardless of ``cfg.base``.
    ``cfg.base`` controls only the worktree CHECKOUT location.
    """
    return repo_root / ".orca" / "worktrees"


def _trust_hooks_from_env_or_flag(flag_value: bool) -> bool:
    """Resolve --trust-hooks: CLI flag OR ORCA_TRUST_HOOKS env var."""
    if flag_value:
        return True
    return os.environ.get("ORCA_TRUST_HOOKS", "") in {"1", "true", "yes"}


def _detect_host_system(repo_root: Path) -> str:
    """Detect host system; falls back to 'bare' if no manifest or marker."""
    manifest = repo_root / ".orca" / "adoption.toml"
    if manifest.exists():
        try:
            from orca.core.adoption.manifest import load_manifest
            m = load_manifest(manifest)
            return m.host.system
        except Exception:
            pass
    # Detection fallback
    if (repo_root / ".specify").is_dir():
        return "spec-kit"
    if (repo_root / "openspec" / "changes").is_dir():
        return "openspec"
    if (repo_root / "docs" / "superpowers").is_dir():
        return "superpowers"
    return "bare"


def _run_wt_new(args: list[str]) -> int:
    import argparse
    from orca.core.path_safety import PathSafetyError
    from orca.core.worktrees.config import load_config
    from orca.core.worktrees.manager import (
        WorktreeManager, IdempotencyError,
    )
    from orca.core.worktrees.protocol import CreateRequest

    parser = argparse.ArgumentParser(prog="orca-cli wt new", exit_on_error=False)
    parser.add_argument("branch")
    parser.add_argument("--from", dest="from_branch", default=None)
    parser.add_argument("--feature", default=None)
    parser.add_argument("--lane", default=None)
    parser.add_argument("--agent", choices=["claude", "codex", "none"], default=None)
    parser.add_argument("--no-tmux", dest="no_tmux", action="store_true")
    parser.add_argument("--no-setup", dest="no_setup", action="store_true")
    parser.add_argument("--reuse-branch", dest="reuse_branch", action="store_true")
    parser.add_argument("--recreate-branch", dest="recreate_branch", action="store_true")
    parser.add_argument("--trust-hooks", dest="trust_hooks", action="store_true")
    parser.add_argument("--record", dest="record_trust", action="store_true")
    parser.add_argument("-p", dest="prompt", default=None)

    try:
        ns, extra = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0", ErrorKind.INPUT_INVALID,
                f"argv parse error: {exc}",
            ),
            pretty=False, exit_code=2,
        )

    # Pop out '--' separator if present; trailing args are agent extras
    extra_args: list[str] = []
    if "--" in extra:
        sep = extra.index("--")
        extra_args = extra[sep + 1:]
        extra = extra[:sep]
    if extra:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0", ErrorKind.INPUT_INVALID,
                f"unknown args: {extra}",
            ),
            pretty=False, exit_code=2,
        )

    repo_root = Path.cwd().resolve()
    cfg = load_config(repo_root)
    host = _detect_host_system(repo_root)
    agent = ns.agent or cfg.default_agent
    trust_hooks = _trust_hooks_from_env_or_flag(ns.trust_hooks)

    mgr = WorktreeManager(
        repo_root=repo_root, cfg=cfg, host_system=host,
        run_tmux=not ns.no_tmux, run_setup=not ns.no_setup,
    )
    req = CreateRequest(
        branch=ns.branch, from_branch=ns.from_branch,
        feature=ns.feature, lane=ns.lane,
        agent=agent, prompt=ns.prompt, extra_args=extra_args,
        reuse_branch=ns.reuse_branch, recreate_branch=ns.recreate_branch,
        no_setup=ns.no_setup,
        trust_hooks=trust_hooks, record_trust=ns.record_trust,
    )
    try:
        result = mgr.create(req)
    except (IdempotencyError, PathSafetyError) as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0", ErrorKind.INPUT_INVALID, str(exc),
            ),
            pretty=False, exit_code=1,
        )
    except RuntimeError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0", ErrorKind.BACKEND_FAILURE, str(exc),
            ),
            pretty=False, exit_code=1,
        )

    print(str(result.worktree_path))
    return 0


# Stub the other verbs (filled in next tasks)
def _run_wt_start(args: list[str]) -> int:
    import argparse
    import os
    from orca.core.worktrees.config import load_config
    from orca.core.worktrees.registry import (
        read_registry, read_sidecar, sidecar_path, write_sidecar, Sidecar,
        acquire_registry_lock,
    )
    from orca.core.worktrees.events import emit_event
    from orca.core.worktrees.hooks import HookEnv, hook_sha, run_hook
    from orca.core.worktrees.tmux import (
        ensure_session, has_window, new_window, send_keys,
        resolve_session_name,
    )

    parser = argparse.ArgumentParser(prog="orca-cli wt start", exit_on_error=False)
    parser.add_argument("branch")
    parser.add_argument("--agent", choices=["claude", "codex", "none"], default=None)
    parser.add_argument("-p", dest="prompt", default=None)
    parser.add_argument("--rerun-setup", dest="rerun_setup", action="store_true")
    parser.add_argument("--no-tmux", dest="no_tmux", action="store_true")
    parser.add_argument("--no-setup", dest="no_setup", action="store_true")
    parser.add_argument("--trust-hooks", dest="trust_hooks", action="store_true")
    try:
        ns, _ = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"argv parse error: {exc}"),
            pretty=False, exit_code=2,
        )

    repo_root = Path.cwd().resolve()
    cfg = load_config(repo_root)
    wt_root = _state_root(repo_root)
    trust_hooks = _trust_hooks_from_env_or_flag(ns.trust_hooks)

    view = read_registry(wt_root)
    row = next((l for l in view.lanes if l.branch == ns.branch), None)
    if row is None:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"no lane for branch {ns.branch!r}; "
                                    f"run wt new first"),
            pretty=False, exit_code=1,
        )

    wt_path = Path(row.worktree_path)

    if not ns.no_tmux:
        session = resolve_session_name(cfg.tmux_session, repo_root=repo_root)
        ensure_session(session, cwd=wt_path)
        window = row.lane_id[:32]
        if not has_window(session, window):
            new_window(session=session, window=window, cwd=wt_path)

    # Read sidecar inside the lock so the read-modify-write of
    # last_attached_at + setup_version is atomic vs concurrent wt start.
    setup_sha_after = ""
    with acquire_registry_lock(wt_root):
        sc = read_sidecar(sidecar_path(wt_root, row.lane_id))

        env = HookEnv(
            repo_root=repo_root, worktree_dir=wt_path, branch=ns.branch,
            lane_id=row.lane_id,
            lane_mode=("lane" if (sc and sc.feature_id and sc.lane_name)
                       else "branch"),
            feature_id=(sc.feature_id if sc else None),
            host_system=(sc.host_system if sc else "bare"),
        )

        # Stage 2 re-run: only when --rerun-setup AND sidecar's setup_version
        # differs from the current after_create SHA. Per spec line 158.
        ac = wt_root / cfg.after_create_hook
        if ns.rerun_setup and ac.exists():
            current_sha = hook_sha(ac)
            if sc is None or sc.setup_version != current_sha:
                from orca.core.worktrees.trust import (
                    TrustDecision, TrustOutcome, check_or_prompt,
                    resolve_repo_key,
                )
                outcome = check_or_prompt(
                    repo_key=resolve_repo_key(repo_root),
                    script_path=str(ac), sha=current_sha,
                    script_text=ac.read_text(encoding="utf-8"),
                    decision=TrustDecision(
                        trust_hooks=trust_hooks, record=False,
                    ),
                    interactive=os.isatty(0),
                )
                if outcome in (TrustOutcome.DECLINED,
                               TrustOutcome.REFUSED_NONINTERACTIVE):
                    return _emit_envelope(
                        envelope=_err_envelope(
                            "wt", "1.0.0", ErrorKind.INPUT_INVALID,
                            f"after_create untrusted; --rerun-setup aborted "
                            f"(outcome={outcome.value})",
                        ),
                        pretty=False, exit_code=1,
                    )
                emit_event(wt_root, event="setup.after_create.started",
                           lane_id=row.lane_id)
                ac_result = run_hook(script_path=ac, env=env)
                emit_event(
                    wt_root,
                    event=("setup.after_create.completed"
                           if ac_result.status == "completed"
                           else "setup.after_create.failed"),
                    lane_id=row.lane_id, exit_code=ac_result.exit_code,
                    duration_ms=ac_result.duration_ms,
                )
                if ac_result.status == "failed":
                    return _emit_envelope(
                        envelope=_err_envelope(
                            "wt", "1.0.0", ErrorKind.BACKEND_FAILURE,
                            f"after_create re-run failed "
                            f"(exit {ac_result.exit_code})",
                        ),
                        pretty=False, exit_code=1,
                    )
                setup_sha_after = current_sha

        # Stage 3 (before_run) — runs every wt start; trust-gated
        br = wt_root / cfg.before_run_hook
        if br.exists():
            from orca.core.worktrees.trust import (
                TrustDecision as _TD, TrustOutcome as _TO,
                check_or_prompt as _cop, resolve_repo_key as _rrk,
            )
            br_sha = hook_sha(br)
            br_outcome = _cop(
                repo_key=_rrk(repo_root),
                script_path=str(br), sha=br_sha,
                script_text=br.read_text(encoding="utf-8"),
                decision=_TD(trust_hooks=trust_hooks, record=False),
                interactive=os.isatty(0),
            )
            if br_outcome in (_TO.DECLINED, _TO.REFUSED_NONINTERACTIVE):
                emit_event(wt_root,
                           event="setup.before_run.skipped_untrusted",
                           lane_id=row.lane_id)
            else:
                emit_event(wt_root, event="setup.before_run.started",
                           lane_id=row.lane_id)
                result = run_hook(script_path=br, env=env)
                emit_event(
                    wt_root,
                    event=("setup.before_run.completed"
                           if result.status == "completed"
                           else "setup.before_run.failed"),
                    lane_id=row.lane_id, exit_code=result.exit_code,
                    duration_ms=result.duration_ms,
                )

        # Update last_attached_at + setup_version
        if sc is not None:
            from datetime import datetime, timezone
            updates = {
                "last_attached_at": datetime.now(timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            if setup_sha_after:
                updates["setup_version"] = setup_sha_after
            new_sc = Sidecar(**{**sc.__dict__, **updates})
            write_sidecar(wt_root, new_sc)

    emit_event(wt_root, event="lane.attached", lane_id=row.lane_id)
    print(str(wt_path))
    return 0
def _run_wt_cd(args: list[str]) -> int:
    """Print worktree path (or repo root). Operator wraps in $(...)."""
    import argparse
    from orca.core.worktrees.registry import read_registry, sidecar_path, read_sidecar

    parser = argparse.ArgumentParser(prog="orca-cli wt cd", exit_on_error=False)
    parser.add_argument("target", nargs="?", default=None)
    try:
        ns, _ = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit):
        ns = parser.parse_args([])

    repo_root = Path.cwd().resolve()
    if not ns.target:
        print(str(repo_root))
        return 0

    wt_root = _state_root(repo_root)
    # Try lane-id first
    sc = read_sidecar(sidecar_path(wt_root, ns.target))
    if sc is not None:
        print(sc.worktree_path)
        return 0
    # Fall back to branch lookup
    view = read_registry(wt_root)
    for row in view.lanes:
        if row.branch == ns.target:
            print(row.worktree_path)
            return 0

    return _emit_envelope(
        envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                f"no worktree for {ns.target!r}"),
        pretty=False, exit_code=1,
    )
def _compute_tmux_state(window: str, live_windows: set[str]) -> str:
    """Pure function for tmux-state derivation; testable without subprocess."""
    if not live_windows:
        return "session-missing"
    if window in live_windows:
        return "attached"
    return "stale"


def _run_wt_ls(args: list[str]) -> int:
    import argparse
    from orca.core.worktrees.events import emit_event, read_events
    from orca.core.worktrees.registry import (
        read_registry, sidecar_path, read_sidecar,
    )
    from orca.core.worktrees.tmux import (
        list_windows, resolve_session_name,
    )
    from orca.core.worktrees.config import load_config

    parser = argparse.ArgumentParser(prog="orca-cli wt ls", exit_on_error=False)
    parser.add_argument("--json", dest="as_json", action="store_true")
    parser.add_argument("--all", dest="show_all", action="store_true")
    try:
        ns, _ = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit):
        ns = parser.parse_args([])

    repo_root = Path.cwd().resolve()
    cfg = load_config(repo_root)
    wt_root = _state_root(repo_root)
    view = read_registry(wt_root)
    session = resolve_session_name(cfg.tmux_session, repo_root=repo_root)
    live_windows = set(list_windows(session))

    # Emit tmux.session.killed once per lane on first observed
    # session-missing transition. Idempotent: re-runs of wt ls don't
    # spam the log because we check past events for an already-emitted
    # killed marker.
    prior_events = read_events(wt_root) if wt_root.exists() else []
    killed_lanes = {
        e.get("lane_id") for e in prior_events
        if e.get("event") == "tmux.session.killed"
    }
    attached_lanes = {
        e.get("lane_id") for e in prior_events
        if e.get("event") in ("lane.attached", "tmux.window.created")
    }

    rows = []
    for lane in view.lanes:
        sc = read_sidecar(sidecar_path(wt_root, lane.lane_id))
        window = lane.lane_id[:32]
        tmux_state = _compute_tmux_state(window, live_windows)
        # First-observation event emission per spec line 473.
        if (tmux_state == "session-missing"
                and lane.lane_id in attached_lanes
                and lane.lane_id not in killed_lanes):
            emit_event(wt_root, event="tmux.session.killed",
                       lane_id=lane.lane_id, session=session)
            killed_lanes.add(lane.lane_id)
        rows.append({
            "lane_id": lane.lane_id,
            "branch": lane.branch,
            "worktree_path": lane.worktree_path,
            "feature_id": lane.feature_id,
            "tmux_state": tmux_state,
            "agent": (sc.agent if sc else "none"),
            "last_attached_at": (sc.last_attached_at if sc else None),
            "setup_version": (sc.setup_version if sc else None),
        })

    if ns.as_json:
        print(json.dumps({"schema_version": 1, "lanes": rows},
                         indent=2, sort_keys=True))
        return 0

    # Human table
    if not rows:
        print("(no lanes)")
        return 0
    headers = ["LANE_ID", "BRANCH", "TMUX", "AGENT", "PATH"]
    widths = [max(len(h), max((len(str(r[k])) for r in rows), default=0))
              for h, k in zip(headers,
                              ["lane_id", "branch", "tmux_state", "agent",
                               "worktree_path"])]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    for r in rows:
        print(fmt.format(r["lane_id"], r["branch"], r["tmux_state"],
                          r["agent"] or "none", r["worktree_path"]))
    return 0
def _run_wt_rm(args: list[str]) -> int:
    import argparse
    from orca.core.worktrees.config import load_config
    from orca.core.worktrees.manager import (
        WorktreeManager, IdempotencyError,
    )
    from orca.core.worktrees.protocol import RemoveRequest

    parser = argparse.ArgumentParser(prog="orca-cli wt rm", exit_on_error=False)
    parser.add_argument("branch", nargs="?", default=None)
    parser.add_argument(
        "--all", dest="all_lanes", action="store_true",
        help=("remove ALL registered lanes (best-effort: lanes registered "
              "concurrently may be missed; rerun if needed)"),
    )
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("--keep-branch", dest="keep_branch", action="store_true")
    parser.add_argument("--no-tmux", dest="no_tmux", action="store_true")
    parser.add_argument("--no-setup", dest="no_setup", action="store_true")
    parser.add_argument("--trust-hooks", dest="trust_hooks", action="store_true")
    parser.add_argument("--record", dest="record_trust", action="store_true")

    try:
        ns, extra = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"argv parse error: {exc}"),
            pretty=False, exit_code=2,
        )
    if extra:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"unknown args: {extra}"),
            pretty=False, exit_code=2,
        )
    if not ns.branch and not ns.all_lanes:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    "wt rm requires <branch> or --all"),
            pretty=False, exit_code=2,
        )

    repo_root = Path.cwd().resolve()
    cfg = load_config(repo_root)
    host = _detect_host_system(repo_root)
    trust_hooks = _trust_hooks_from_env_or_flag(ns.trust_hooks)
    mgr = WorktreeManager(
        repo_root=repo_root, cfg=cfg, host_system=host,
        run_tmux=not ns.no_tmux, run_setup=not ns.no_setup,
    )

    def _mk_req(branch: str) -> RemoveRequest:
        return RemoveRequest(
            branch=branch, force=ns.force, keep_branch=ns.keep_branch,
            all_lanes=False, no_setup=ns.no_setup,
            trust_hooks=trust_hooks, record_trust=ns.record_trust,
        )

    try:
        if ns.all_lanes:
            from orca.core.worktrees.registry import read_registry
            view = read_registry(_state_root(repo_root))
            for lane in view.lanes:
                mgr.remove(_mk_req(lane.branch))
        else:
            mgr.remove(_mk_req(ns.branch))
    except IdempotencyError as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID, str(exc)),
            pretty=False, exit_code=1,
        )
    return 0
def _run_wt_merge(args: list[str]) -> int:
    import argparse
    import subprocess
    parser = argparse.ArgumentParser(prog="orca-cli wt merge", exit_on_error=False)
    parser.add_argument("branch")
    parser.add_argument("--into", dest="into", default=None)
    # Swallow common no-op flags forwarded by test runners / wrappers.
    parser.add_argument("--no-tmux", dest="_no_tmux", action="store_true")
    parser.add_argument("--no-setup", dest="_no_setup", action="store_true")
    try:
        ns, extra = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"argv parse error: {exc}"),
            pretty=False, exit_code=2,
        )
    repo_root = Path.cwd().resolve()
    target = ns.into
    if target is None:
        # Try origin HEAD first.
        result = subprocess.run(
            ["git", "-C", str(repo_root), "symbolic-ref",
             "--short", "refs/remotes/origin/HEAD"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            target = result.stdout.strip().split("/")[-1]
        else:
            # Fall back to local main, then master, then current HEAD.
            for cand in ("main", "master"):
                check = subprocess.run(
                    ["git", "-C", str(repo_root), "show-ref", "--verify",
                     "--quiet", f"refs/heads/{cand}"],
                    check=False,
                )
                if check.returncode == 0:
                    target = cand
                    break
            if target is None:
                head = subprocess.run(
                    ["git", "-C", str(repo_root), "symbolic-ref",
                     "--short", "HEAD"],
                    capture_output=True, text=True, check=False,
                )
                target = head.stdout.strip() if head.returncode == 0 else "main"
    # Switch to target then merge
    sw = subprocess.run(
        ["git", "-C", str(repo_root), "switch", target],
        capture_output=True, text=True, check=False,
    )
    if sw.returncode != 0:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.BACKEND_FAILURE,
                                    f"git switch failed: {sw.stderr}"),
            pretty=False, exit_code=1,
        )
    cmd = ["git", "-C", str(repo_root), "merge", *extra, ns.branch]
    mr = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if mr.returncode != 0:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.BACKEND_FAILURE,
                                    f"git merge failed: {mr.stderr}"),
            pretty=False, exit_code=1,
        )
    print(mr.stdout)
    return 0
def _run_wt_init(args: list[str]) -> int:
    import argparse
    from orca.core.worktrees.config import write_default_config
    from orca.core.worktrees.init_script import generate_after_create

    parser = argparse.ArgumentParser(prog="orca-cli wt init", exit_on_error=False)
    parser.add_argument("--replace", action="store_true")
    try:
        ns, _ = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit):
        ns = parser.parse_args([])

    repo_root = Path.cwd().resolve()
    write_default_config(repo_root)
    try:
        generate_after_create(repo_root, replace=ns.replace)
    except FileExistsError as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID, str(exc)),
            pretty=False, exit_code=1,
        )

    print("wrote .orca/worktrees.toml and .orca/worktrees/after_create")
    if (repo_root / "worktrees").is_dir():
        print("note: orca worktrees live at .orca/worktrees/; "
              "this is unrelated to the existing worktrees/ directory in your repo")
    return 0
def _run_wt_config(args: list[str]) -> int:
    import argparse
    from orca.core.worktrees.config import load_config
    from dataclasses import asdict

    parser = argparse.ArgumentParser(prog="orca-cli wt config", exit_on_error=False)
    parser.add_argument("--json", dest="as_json", action="store_true")
    try:
        ns, _ = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit):
        ns = parser.parse_args([])

    repo_root = Path.cwd().resolve()
    cfg = load_config(repo_root)
    payload = {
        "schema_version": 1,
        "effective": asdict(cfg),
        "sources": {
            "committed": ".orca/worktrees.toml",
            "local": ".orca/worktrees.local.toml",
        },
    }
    if ns.as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"base               {cfg.base}")
    print(f"lane_id_mode       {cfg.lane_id_mode}")
    print(f"tmux_session       {cfg.tmux_session}")
    print(f"default_agent      {cfg.default_agent}")
    return 0


def _run_wt_version(args: list[str]) -> int:
    from orca.core.worktrees.registry import SCHEMA_VERSION
    print(f"orca {_pkg_version('orca')} wt-schema={SCHEMA_VERSION}")
    return 0
def _run_wt_doctor(args: list[str]) -> int:
    import argparse
    import subprocess
    from orca.core.worktrees.config import load_config
    from orca.core.worktrees.registry import (
        read_registry, sidecar_path, read_sidecar,
    )
    from orca.core.worktrees.tmux import (
        list_windows, resolve_session_name,
    )

    parser = argparse.ArgumentParser(prog="orca-cli wt doctor", exit_on_error=False)
    parser.add_argument("--reap", action="store_true")
    parser.add_argument("-y", dest="assume_yes", action="store_true")
    # Swallow no-op flags from wrappers/test runners.
    parser.add_argument("--no-tmux", dest="_no_tmux", action="store_true")
    parser.add_argument("--no-setup", dest="_no_setup", action="store_true")
    try:
        ns, _ = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit):
        ns = parser.parse_args([])

    repo_root = Path.cwd().resolve()
    cfg = load_config(repo_root)
    wt_root = _state_root(repo_root)
    view = read_registry(wt_root)
    issues: list[str] = []

    # Check git worktrees vs registry
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, check=True,
        )
        git_paths = []
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                git_paths.append(line[len("worktree "):].strip())
    except subprocess.CalledProcessError:
        git_paths = []

    registered_paths = {l.worktree_path for l in view.lanes}
    for gp in git_paths:
        # Skip primary checkout
        if gp == str(repo_root):
            continue
        # Skip already-registered paths
        if gp in registered_paths:
            continue
        # Any unregistered worktree git knows about is an orphan, regardless
        # of whether the operator parked it inside or outside .orca/worktrees/.
        # Reporting external worktrees is intentional: the operator may have
        # forgotten about them.
        issues.append(f"orphan-git: worktree {gp} not in registry")

    for lane in view.lanes:
        if not Path(lane.worktree_path).exists():
            issues.append(
                f"orphan-sidecar: worktree {lane.worktree_path} missing on "
                f"disk for {lane.lane_id}"
            )

    # Sidecar without registry
    if wt_root.exists():
        for sc_file in wt_root.glob("*.json"):
            if sc_file.name == "registry.json":
                continue
            sc = read_sidecar(sc_file)
            if sc is None:
                continue
            if not any(l.lane_id == sc.lane_id for l in view.lanes):
                issues.append(
                    f"orphan-sidecar: {sc.lane_id} has sidecar but no "
                    f"registry entry"
                )

    # tmux liveness
    session = resolve_session_name(cfg.tmux_session, repo_root=repo_root)
    live = set(list_windows(session))
    for lane in view.lanes:
        window = lane.lane_id[:32]
        if live and window not in live:
            issues.append(
                f"tmux-stale: lane {lane.lane_id} has no live tmux window"
            )

    if not issues:
        print("ok: no issues detected")
        return 0

    for issue in issues:
        print(issue)

    if ns.reap:
        # Atomic reap: re-read inside the lock so we operate on fresh
        # state (avoids TOCTOU vs concurrent wt new); prompt the operator
        # under the lock (this is operator-driven, so blocking is OK);
        # unlink sidecars + rewrite registry as one transaction.
        from orca.core.worktrees.registry import (
            write_registry, acquire_registry_lock,
        )
        reaped: list[str] = []
        with acquire_registry_lock(wt_root):
            fresh = read_registry(wt_root)
            keep: list = []
            for lane in fresh.lanes:
                if Path(lane.worktree_path).exists():
                    keep.append(lane)
                    continue
                if not ns.assume_yes:
                    print(f"reap orphan {lane.lane_id}? [y/N]: ",
                          end="", flush=True)
                    answer = sys.stdin.readline().strip().lower()
                    if answer != "y":
                        keep.append(lane)
                        continue
                scp = sidecar_path(wt_root, lane.lane_id)
                if scp.exists():
                    scp.unlink()
                reaped.append(lane.lane_id)
            if len(keep) != len(fresh.lanes):
                write_registry(wt_root, keep)
        for lid in reaped:
            print(f"reaped {lid}")

    return 1


def _stub_unimplemented(verb: str) -> int:
    return _emit_envelope(
        envelope=_err_envelope(
            "wt", "1.0.0", ErrorKind.INPUT_INVALID,
            f"wt {verb} not yet implemented",
        ),
        pretty=False, exit_code=2,
    )


_register("wt", _run_wt, "1.0.0")
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
