"""flow-state-projection capability.

Thin adapter over orca.flow_state.compute_flow_state. Exposes the existing
FlowStateResult.to_dict() shape through the standard Result[dict, Error]
envelope and pins a JSON schema for the wire format.

The heavy lifting (artifact discovery, review-milestone derivation, evidence
collection) lives in flow_state.py and is NOT duplicated here. If the
underlying shape evolves, the schema stays loose at the item level; consumers
needing strict per-milestone types should depend on orca.flow_state directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orca.core.errors import Error, ErrorKind
from orca.core.result import Err, Ok, Result
from orca.flow_state import compute_flow_state

VERSION = "0.1.0"


@dataclass(frozen=True)
class FlowStateProjectionInput:
    feature_id: str | None = None
    feature_dir: str | None = None
    repo_root: str | None = None


def flow_state_projection(inp: FlowStateProjectionInput) -> Result[dict, Error]:
    """Project an SDD feature directory into a JSON-shaped flow state snapshot.

    Accepts either `feature_dir` (absolute or relative path) or
    `feature_id` + `repo_root` (resolves to `repo_root/specs/feature_id`).

    Returns Ok(dict) matching `FlowStateResult.to_dict()`. Returns
    Err(INPUT_INVALID) for missing arguments, missing repo_root with
    feature_id, or non-existent resolved feature directory. Returns
    Err(INTERNAL) for unexpected exceptions from compute_flow_state.
    """
    feat_dir = _resolve_feature_dir(inp)
    if isinstance(feat_dir, Error):
        return Err(feat_dir)

    try:
        # repo_root is passed even when feature_dir was given directly:
        # compute_flow_state uses it for .orca/flow-state/<id>.json
        # resume-metadata lookup. Not redundant.
        result = compute_flow_state(feat_dir, repo_root=inp.repo_root)
    except Exception as exc:  # noqa: BLE001 - boundary translation for in-process call into flow_state filesystem/parser code
        return Err(Error(
            kind=ErrorKind.INTERNAL,
            message=f"compute_flow_state failed: {exc}",
            detail={"underlying": type(exc).__name__},
        ))

    return Ok(result.to_dict())


def _resolve_feature_dir(inp: FlowStateProjectionInput) -> Path | Error:
    """Resolve the feature directory, returning an Error on bad input."""
    if inp.feature_id is None and inp.feature_dir is None:
        return Error(
            kind=ErrorKind.INPUT_INVALID,
            message="must provide feature_id (with repo_root) or feature_dir",
        )

    if inp.feature_dir is not None:
        path = Path(inp.feature_dir)
        if not path.exists():
            return Error(
                kind=ErrorKind.INPUT_INVALID,
                message=f"feature_dir does not exist: {path}",
            )
        return path

    # feature_id path: requires repo_root. feature_dir was None per the
    # branch above, and the top-level check guarantees feature_id is set.
    if inp.repo_root is None:
        return Error(
            kind=ErrorKind.INPUT_INVALID,
            message="feature_id requires repo_root for resolution",
        )
    assert inp.feature_id is not None  # narrowed for pyright

    path = Path(inp.repo_root) / "specs" / inp.feature_id
    if not path.exists():
        return Error(
            kind=ErrorKind.INPUT_INVALID,
            message=f"resolved feature directory does not exist: {path}",
        )
    return path
