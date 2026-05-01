"""Lane-id derivation + repo-key sanitization for worktree manager."""
from __future__ import annotations

import re
from typing import Literal

from orca.core.path_safety import validate_identifier

LaneIdMode = Literal["branch", "lane", "auto"]

_BRANCH_SLASH_RE = re.compile(r"/")
_BRANCH_OTHER_RE = re.compile(r"[^A-Za-z0-9._-]")
_REPO_RE = re.compile(r"[^A-Za-z0-9_-]")  # NOTE: . and : both excluded
_REPO_MAX = 64


def _sanitize_branch(branch: str) -> str:
    s = _BRANCH_SLASH_RE.sub("-", branch)
    s = _BRANCH_OTHER_RE.sub("_", s)
    return s


def derive_lane_id(
    *,
    branch: str,
    mode: LaneIdMode,
    feature: str | None = None,
    lane: str | None = None,
) -> str:
    """Derive a lane-id per the configured mode. Validates against path-safety
    Class D (`[A-Za-z0-9._-]+`, max 128, not `.` / `..`)."""
    if mode == "lane":
        if not feature or not lane:
            raise ValueError(
                "lane mode requires both feature and lane arguments"
            )
        candidate = f"{feature}-{lane}"
    elif mode == "auto":
        if feature and lane:
            candidate = f"{feature}-{lane}"
        else:
            candidate = _sanitize_branch(branch)
    else:  # "branch"
        candidate = _sanitize_branch(branch)

    return validate_identifier(candidate, field="lane_id", max_length=128)


def sanitize_repo_name(name: str) -> str:
    """Sanitize a repo basename for safe tmux session-name templating.

    More restrictive than lane-id sanitization: also replaces `.` and `:`
    (tmux target syntax). Truncated to 64 chars.
    """
    s = _REPO_RE.sub("_", name)
    return s[:_REPO_MAX]
