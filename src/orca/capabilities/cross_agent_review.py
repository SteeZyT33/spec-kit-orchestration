from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, TypedDict

from orca.core.bundle import BundleError, ReviewBundle, build_bundle
from orca.core.errors import Error, ErrorKind
from orca.core.findings import Findings, convert_raw_findings
from orca.core.result import Err, Ok, Result
from orca.core.reviewers.base import Reviewer, ReviewerError
from orca.core.reviewers.cross import CrossReviewer, CrossResult

VERSION = "0.1.0"

_VALID_REVIEWERS = {"claude", "codex", "cross"}

DEFAULT_REVIEW_PROMPT = "Review the following content. Return a JSON array of findings."


class ReviewEnvelope(TypedDict):
    """JSON envelope returned by cross_agent_review on success.

    This is the wire-boundary contract - CLI (Task 9), perf-lab integration
    (Phase 4), and other consumers depend on this shape. Changes here are
    breaking changes for downstream.
    """

    findings: list[dict[str, Any]]
    partial: bool
    missing_reviewers: list[str]
    reviewer_metadata: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class CrossAgentReviewInput:
    kind: str
    target: list[str]
    reviewer: str
    feature_id: str | None = None
    criteria: list[str] = field(default_factory=list)
    context: list[str] = field(default_factory=list)
    prompt: str = DEFAULT_REVIEW_PROMPT


def cross_agent_review(
    inp: CrossAgentReviewInput,
    *,
    reviewers: Mapping[str, Reviewer],
) -> Result[ReviewEnvelope, Error]:
    """Run cross-agent review and return a JSON-envelope-shaped Result.

    Three reviewer modes:
    - "claude" / "codex": single reviewer; findings carry that reviewer name.
    - "cross": delegates to CrossReviewer (requires both "claude" and "codex"
      configured); findings collapse via stable dedupe id with combined
      reviewers tuple.

    Errors map cleanly to ErrorKind:
    - INPUT_INVALID: unknown reviewer, missing target file, malformed kind,
      missing backend reviewer for cross mode
    - BACKEND_FAILURE: reviewer raised ReviewerError, all-cross-failed,
      reviewer returned malformed findings (KeyError/ValueError from
      Finding.from_raw)
    """
    if inp.reviewer not in _VALID_REVIEWERS:
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message=f"unknown reviewer: {inp.reviewer}",
        ))

    try:
        bundle = build_bundle(
            kind=inp.kind,
            target=inp.target,
            feature_id=inp.feature_id,
            criteria=inp.criteria,
            context=inp.context,
        )
    except BundleError as exc:
        return Err(Error(kind=ErrorKind.INPUT_INVALID, message=str(exc)))
    except OSError as exc:
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message=f"failed to read bundle target: {exc}",
            detail={"errno": getattr(exc, "errno", None), "filename": getattr(exc, "filename", None)},
        ))

    if inp.reviewer == "cross":
        return _run_cross(bundle, inp, reviewers)
    return _run_single(bundle, inp, reviewers)


def _run_cross(
    bundle: ReviewBundle,
    inp: CrossAgentReviewInput,
    reviewers: Mapping[str, Reviewer],
) -> Result[ReviewEnvelope, Error]:
    """Cross-mode dispatch: run claude+codex via CrossReviewer and merge.

    All-fail path: if every backend reviewer raises ReviewerError, the
    CrossReviewer raises 'all reviewers failed' which we surface as
    BACKEND_FAILURE. The semantic is "reviewers responded but produced
    nothing usable" -- still a backend problem, not user error.

    Partial-fail: if at least one reviewer succeeds, returns Ok with
    `partial=True` and `missing_reviewers` listing failed names.
    """
    try:
        cross = CrossReviewer(reviewers=[reviewers["claude"], reviewers["codex"]])
    except KeyError as exc:
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message=f"missing reviewer for cross mode: {exc}",
        ))
    try:
        cross_result = cross.review(bundle, inp.prompt)
    except ReviewerError as exc:
        return Err(Error(
            kind=ErrorKind.BACKEND_FAILURE,
            message=str(exc),
            detail={"underlying": exc.underlying, "retryable": exc.retryable},
        ))

    return Ok(_render_cross(cross_result))


def _render_cross(result: CrossResult) -> ReviewEnvelope:
    return {
        "findings": result.findings.to_json(),
        "partial": result.partial,
        "missing_reviewers": list(result.missing_reviewers),
        "reviewer_metadata": result.reviewer_metadata,
    }


def _run_single(
    bundle: ReviewBundle,
    inp: CrossAgentReviewInput,
    reviewers: Mapping[str, Reviewer],
) -> Result[ReviewEnvelope, Error]:
    if inp.reviewer not in reviewers:
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message=f"reviewer not configured: {inp.reviewer}",
        ))

    try:
        raw = reviewers[inp.reviewer].review(bundle, inp.prompt)
    except ReviewerError as exc:
        return Err(Error(
            kind=ErrorKind.BACKEND_FAILURE,
            message=str(exc),
            detail={"underlying": exc.underlying, "retryable": exc.retryable},
        ))

    try:
        findings_list = convert_raw_findings(raw.findings, reviewer=raw.reviewer)
    except ReviewerError as exc:
        return Err(Error(
            kind=ErrorKind.BACKEND_FAILURE,
            message=str(exc),
            detail={
                "underlying": exc.underlying,
                "retryable": exc.retryable,
                "reviewer": raw.reviewer,
            },
        ))
    findings = Findings(findings_list)

    return Ok({
        "findings": findings.to_json(),
        "partial": False,
        "missing_reviewers": [],
        "reviewer_metadata": {raw.reviewer: raw.metadata},
    })
