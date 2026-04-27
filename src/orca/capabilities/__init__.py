"""Orca v1 capability catalog. Each capability is a pure function returning Result."""

from orca.capabilities.contradiction_detector import (
    ContradictionDetectorInput,
    contradiction_detector,
)
from orca.capabilities.cross_agent_review import (
    CrossAgentReviewInput,
    cross_agent_review,
)

__all__ = [
    "ContradictionDetectorInput",
    "CrossAgentReviewInput",
    "contradiction_detector",
    "cross_agent_review",
]
