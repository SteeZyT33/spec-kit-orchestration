from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from orca.core.bundle import ReviewBundle
from orca.core.findings import Finding, Findings, convert_raw_findings
from orca.core.reviewers.base import Reviewer, ReviewerError


@dataclass(frozen=True)
class CrossResult:
    """Output of CrossReviewer.review: merged findings + partial-success flags.

    `findings` are typed Finding objects (already converted from raw dicts).
    `partial=True` when at least one reviewer failed but at least one
    succeeded; `missing_reviewers` lists ALL failed reviewer names sorted.
    `reviewer_metadata` maps reviewer name -> the RawFindings.metadata dict
    for downstream observability.

    On dedupe collisions, the field values from the first reviewer in
    `reviewers=` are retained; only the `reviewers` tuple accumulates
    across collapsed findings.
    """

    findings: Findings
    partial: bool
    missing_reviewers: tuple[str, ...]
    reviewer_metadata: dict[str, dict[str, Any]]


class CrossReviewer:
    """Runs N reviewers (>= 2) on the same bundle, merges findings via
    stable dedupe id, and returns a CrossResult with partial-success flags.

    Unlike ClaudeReviewer/CodexReviewer/FixtureReviewer, CrossReviewer is
    a higher-level adapter — it produces typed Finding objects (via
    Findings.merge) rather than raw dicts. It does NOT itself implement
    the bare Reviewer protocol because review() returns CrossResult,
    not RawFindings. The capability layer (Task 8) calls CrossReviewer
    directly when reviewer=cross is requested.
    """

    # Identifier used by capability code when emitting metadata. CrossReviewer
    # is not a Reviewer (returns CrossResult, not RawFindings) but downstream
    # observers may want to tag findings with the combiner identity.
    name = "cross"

    def __init__(self, *, reviewers: Sequence[Reviewer]):
        if len(reviewers) < 2:
            raise ValueError(
                f"CrossReviewer requires at least 2 reviewers, got {len(reviewers)}"
            )
        names = [r.name for r in reviewers]
        if len(set(names)) != len(names):
            raise ValueError(
                f"CrossReviewer reviewers must have unique names; got {names}"
            )
        self.reviewers = list(reviewers)

    def review(self, bundle: ReviewBundle, prompt: str) -> CrossResult:
        per_reviewer_findings: list[list[Finding]] = []
        failures: list[tuple[str, ReviewerError]] = []
        metadata: dict[str, dict[str, Any]] = {}

        for reviewer in self.reviewers:
            try:
                raw = reviewer.review(bundle, prompt)
            except ReviewerError as exc:
                failures.append((reviewer.name, exc))
                continue

            try:
                findings = convert_raw_findings(raw.findings, reviewer=reviewer.name)
            except ReviewerError as exc:
                # convert_raw_findings already wraps KeyError/ValueError as
                # ReviewerError(underlying='malformed_finding'); route into
                # the same failure-path as a backend-side review error.
                failures.append((reviewer.name, exc))
                continue

            metadata[reviewer.name] = raw.metadata
            per_reviewer_findings.append(findings)

        if not per_reviewer_findings:
            # Aggregate per-reviewer failure shape into the structured
            # ReviewerError fields. `retryable` aggregates as any() so the
            # capability layer can pick a retry policy without re-parsing.
            # `underlying='all_reviewers_failed'` is a stable sentinel for
            # downstream observers; per-reviewer detail is still available
            # via str(exc) (which carries the joined messages).
            failures_detail = [
                {
                    "name": name,
                    "message": str(err),
                    "retryable": err.retryable,
                    "underlying": err.underlying,
                }
                for name, err in failures
            ]
            messages = "; ".join(f"{name}: {err}" for name, err in failures)
            raise ReviewerError(
                f"all reviewers failed: {messages}",
                retryable=any(f["retryable"] for f in failures_detail),
                underlying="all_reviewers_failed",
            )

        merged = Findings.merge(*per_reviewer_findings)
        partial = len(failures) > 0
        missing_reviewers = tuple(sorted(name for name, _ in failures))

        return CrossResult(
            findings=merged,
            partial=partial,
            missing_reviewers=missing_reviewers,
            reviewer_metadata=metadata,
        )
