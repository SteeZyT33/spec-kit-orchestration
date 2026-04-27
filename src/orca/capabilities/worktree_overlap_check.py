"""worktree-overlap-check capability.

Pure-Python overlap detection for active worktrees + proposed writes. Used
by perf-lab's lease subsystem (post-Phase-4 integration shim) and by other
hosts that want to validate path-claim safety without reimplementing the
prefix-containment logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from orca.core.errors import Error, ErrorKind
from orca.core.result import Err, Ok, Result

VERSION = "0.1.0"


@dataclass(frozen=True)
class WorktreeInfo:
    path: str
    branch: str = ""
    feature_id: str = ""
    claimed_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorktreeOverlapInput:
    worktrees: list[WorktreeInfo]
    proposed_writes: list[str] = field(default_factory=list)
    repo_root: str | None = None


def worktree_overlap_check(inp: WorktreeOverlapInput) -> Result[dict, Error]:
    """Detect path conflicts among worktrees + proposed writes.

    Returns Ok with `safe`, `conflicts[]` (pair-wise), `proposed_overlaps[]`
    (per-proposed-write). Returns Err(INPUT_INVALID) if any claimed path
    is empty.
    """
    # Validate input: empty / whitespace-only / traversal paths are programmer errors.
    for wt in inp.worktrees:
        for p in wt.claimed_paths:
            if not p.strip():
                return Err(Error(
                    kind=ErrorKind.INPUT_INVALID,
                    message=f"empty claimed path on worktree {wt.path}",
                ))
            if _has_traversal(p):
                return Err(Error(
                    kind=ErrorKind.INPUT_INVALID,
                    message=f"path traversal ('..') not allowed in claimed path: {p}",
                ))
    for p in inp.proposed_writes:
        if not p.strip():
            return Err(Error(
                kind=ErrorKind.INPUT_INVALID,
                message="empty proposed_writes entry",
            ))
        if _has_traversal(p):
            return Err(Error(
                kind=ErrorKind.INPUT_INVALID,
                message=f"path traversal ('..') not allowed in proposed_writes: {p}",
            ))

    conflicts: list[dict] = []
    for i, wt_a in enumerate(inp.worktrees):
        for wt_b in inp.worktrees[i + 1:]:
            for paths in _overlapping_path_pairs(wt_a.claimed_paths, wt_b.claimed_paths):
                conflicts.append({
                    "paths": list(paths),
                    "worktrees": [wt_a.path, wt_b.path],
                })

    proposed_overlaps: list[dict] = []
    for proposed in inp.proposed_writes:
        blockers = [wt.path for wt in inp.worktrees if _path_overlaps(proposed, wt.claimed_paths)]
        if blockers:
            proposed_overlaps.append({
                "path": proposed,
                "blocked_by": blockers,
            })

    return Ok({
        "safe": not conflicts and not proposed_overlaps,
        "conflicts": conflicts,
        "proposed_overlaps": proposed_overlaps,
    })


def _has_traversal(p: str) -> bool:
    return ".." in PurePosixPath(p.rstrip("/")).parts


def _overlapping_path_pairs(a: list[str], b: list[str]) -> list[tuple[str, ...]]:
    """Return distinct path tuples for each overlapping pair.

    For exact equality, returns a 1-tuple. For prefix containment,
    returns a 2-tuple with the broader path first, more-specific second.
    """
    out: list[tuple[str, ...]] = []
    for pa in a:
        for pb in b:
            if not _paths_overlap(pa, pb):
                continue
            if pa == pb or pa.rstrip("/") == pb.rstrip("/"):
                out.append((pa,))
            else:
                # Whichever has more path segments is the more-specific one.
                pa_len = len(PurePosixPath(pa.rstrip("/")).parts)
                pb_len = len(PurePosixPath(pb.rstrip("/")).parts)
                if pa_len <= pb_len:
                    out.append((pa, pb))
                else:
                    out.append((pb, pa))
    return out


def _path_overlaps(target: str, claims: list[str]) -> bool:
    return any(_paths_overlap(target, c) for c in claims)


def _paths_overlap(a: str, b: str) -> bool:
    """Two paths overlap if equal or one is a directory prefix of the other.

    Trailing slashes are normalized; comparison uses PurePosixPath so we
    work consistently across platforms (worktree paths in orca are POSIX).
    """
    pa = PurePosixPath(a.rstrip("/"))
    pb = PurePosixPath(b.rstrip("/"))
    if pa == pb:
        return True
    try:
        pa.relative_to(pb)
        return True
    except ValueError:
        pass
    try:
        pb.relative_to(pa)
        return True
    except ValueError:
        pass
    return False
