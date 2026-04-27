from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


def _normalize_summary_for_digest(summary: str) -> str:
    """Normalize a finding summary for dedupe-id computation.

    Cross-reviewer prose differs in trivial ways (trailing punctuation,
    extra whitespace, case). The dedupe_id must treat those as equivalent
    so identical findings from claude and codex collapse into one row.
    """
    s = re.sub(r"\s+", " ", summary).strip().lower()
    return s.rstrip(".,;:!?")


class Severity(str, Enum):
    BLOCKER = "blocker"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NIT = "nit"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


_SEVERITY_ALIASES = {
    "critical": "blocker",
    "warning": "medium",
    "info": "nit",
    "informational": "nit",
    "moderate": "medium",
    "minor": "low",
}

_CONFIDENCE_ALIASES = {
    "very_high": "high",
    "very high": "high",
    "certain": "high",
    "uncertain": "low",
}


def _normalize_severity(raw: str) -> "Severity":
    """Normalize an LLM-emitted severity string to a Severity enum.

    Accepts canonical values directly; maps common variants via an alias
    table. Unknown values still raise ValueError so brand-new severities
    surface loudly rather than silently degrading to a default.
    """
    s = raw.strip().lower()
    s = _SEVERITY_ALIASES.get(s, s)
    return Severity(s)


def _normalize_confidence(raw: str) -> "Confidence":
    """Normalize an LLM-emitted confidence string to a Confidence enum."""
    c = raw.strip().lower()
    c = _CONFIDENCE_ALIASES.get(c, c)
    return Confidence(c)


@dataclass(frozen=True)
class Finding:
    category: str
    severity: Severity
    confidence: Confidence
    summary: str
    detail: str
    evidence: tuple[str, ...]
    suggestion: str
    reviewer: str
    reviewers: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        # Coerce evidence to immutable tuple of strings. Mutable evidence on a
        # frozen dataclass would let dedupe_id drift between merge time and
        # to_json time. Stringifying defends sorted() against future structured
        # evidence inputs.
        object.__setattr__(self, "evidence", tuple(str(e) for e in self.evidence))
        if not self.reviewers:
            object.__setattr__(self, "reviewers", (self.reviewer,))

    @classmethod
    def from_raw(cls, raw: dict[str, Any], *, reviewer: str) -> "Finding":
        """Construct a Finding from a raw reviewer-output dict.

        Used by CrossReviewer and capability code (Task 8) to convert raw
        finding dicts (from `RawFindings.findings`) into typed Findings.
        Severity strings are normalized for common LLM-output variants
        ("critical" -> "blocker", "informational" -> "nit", etc.); unknown
        severities still raise ValueError.

        Raises KeyError if a required key is missing from `raw`.
        """
        return cls(
            category=raw["category"],
            severity=_normalize_severity(raw["severity"]),
            confidence=_normalize_confidence(raw["confidence"]),
            summary=raw["summary"],
            detail=raw["detail"],
            evidence=tuple(raw.get("evidence", ())),
            suggestion=raw.get("suggestion", ""),
            reviewer=reviewer,
        )

    def dedupe_id(self) -> str:
        """Return a stable 16-char id for cross-reviewer dedupe.

        The 16-char prefix is the JSON-schema coupling for cross-agent-review
        outputs (`findings[].id`). Changing the slice length is a wire-format
        breaking change; update the schema's minLength/maxLength to match.
        """
        payload = {
            "category": self.category,
            "severity": self.severity.value,
            "summary": _normalize_summary_for_digest(self.summary),
            "evidence": sorted(self.evidence),
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return digest[:16]

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.dedupe_id(),
            "category": self.category,
            "severity": self.severity.value,
            "confidence": self.confidence.value,
            "summary": self.summary,
            "detail": self.detail,
            "evidence": list(self.evidence),
            "suggestion": self.suggestion,
            "reviewer": self.reviewer,
            "reviewers": list(self.reviewers),
        }


class Findings(list):
    @staticmethod
    def merge(*groups: Iterable[Finding]) -> "Findings":
        by_id: dict[str, Finding] = {}
        for group in groups:
            for f in group:
                key = f.dedupe_id()
                if key in by_id:
                    existing = by_id[key]
                    combined = tuple(sorted(set(existing.reviewers) | set(f.reviewers)))
                    by_id[key] = Finding(
                        category=existing.category,
                        severity=existing.severity,
                        confidence=existing.confidence,
                        summary=existing.summary,
                        detail=existing.detail,
                        evidence=existing.evidence,
                        suggestion=existing.suggestion,
                        reviewer=existing.reviewer,
                        reviewers=combined,
                    )
                else:
                    by_id[key] = f
        return Findings(by_id.values())

    def to_json(self) -> list[dict[str, Any]]:
        return [f.to_json() for f in self]


def convert_raw_findings(
    raw: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    reviewer: str,
) -> list[Finding]:
    """Convert raw finding dicts to typed Findings.

    Used by CrossReviewer (multi-reviewer combiner) and capability code
    (single-reviewer mode) to centralize the raw-dict -> Finding boundary.
    Wraps KeyError (missing required key), ValueError (unknown enum value),
    and TypeError (non-dict item, e.g., a bare string) as
    ReviewerError(underlying='malformed_finding') so callers can route
    every malformed-input shape into the existing failure path uniformly.
    """
    from orca.core.reviewers.base import ReviewerError  # late import to break cycle

    try:
        return [Finding.from_raw(f, reviewer=reviewer) for f in raw]
    except (KeyError, ValueError, TypeError) as exc:
        raise ReviewerError(
            f"{reviewer} returned malformed finding: {exc}",
            retryable=False,
            underlying="malformed_finding",
        ) from exc
