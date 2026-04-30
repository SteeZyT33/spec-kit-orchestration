from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from orca.core.bundle import ReviewBundle


class ReviewerError(Exception):
    """Raised by a reviewer when its backend fails. Caller wraps in Result.

    Carries optional context for capability-level translation:
    - `retryable`: hint to schedulers; the reviewer believes a retry might succeed
    - `underlying`: name of the underlying exception class for diagnostics
    """

    def __init__(self, message: str, *, retryable: bool = False, underlying: str | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.underlying = underlying


@dataclass(frozen=True)
class RawFindings:
    reviewer: str
    findings: list[dict[str, Any]]
    metadata: dict[str, Any]


class Reviewer(Protocol):
    @property
    def name(self) -> str: ...

    def review(self, bundle: ReviewBundle, prompt: str) -> RawFindings: ...
