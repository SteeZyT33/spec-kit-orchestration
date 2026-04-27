from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


VALID_KINDS = {"spec", "diff", "pr", "claim-output"}


class BundleError(Exception):
    """Raised by build_bundle on invalid input or missing files."""


@dataclass(frozen=True)
class ReviewBundle:
    """Snapshot of review inputs.

    The `_target_bytes` and `_context_bytes` tuples store file contents
    captured at build time so `render_text()` and `bundle_hash` always
    refer to identical bytes — even if the underlying files change on
    disk between `build_bundle()` and reviewer invocation. Treat them as
    private; only `render_text()` reads them.
    """

    kind: str
    target_paths: tuple[Path, ...]
    feature_id: str | None
    criteria: tuple[str, ...]
    context_paths: tuple[Path, ...]
    bundle_hash: str
    _target_bytes: tuple[bytes, ...]
    _context_bytes: tuple[bytes, ...]

    def render_text(self) -> str:
        """Render bundle into a single string for reviewer prompts.

        Renders criteria, context files, and target files in that order
        so reviewers see the user-supplied focus before raw content. The
        snapshotted bytes (`_target_bytes`/`_context_bytes`) are decoded
        as UTF-8 with `errors='replace'` so binary or mixed-encoding
        inputs produce a deterministic string rather than raising.
        """
        chunks: list[str] = []
        if self.criteria:
            chunks.append(
                "## Review Criteria\n" + "\n".join(f"- {c}" for c in self.criteria)
            )
        if self.context_paths:
            ctx_blocks: list[str] = []
            for path, raw in zip(self.context_paths, self._context_bytes):
                text = raw.decode("utf-8", errors="replace")
                ctx_blocks.append(f"### {path}\n{text}")
            chunks.append("## Context\n\n" + "\n\n".join(ctx_blocks))
        target_blocks: list[str] = []
        for path, raw in zip(self.target_paths, self._target_bytes):
            text = raw.decode("utf-8", errors="replace")
            target_blocks.append(f"### {path}\n{text}")
        chunks.append("## Target\n\n" + "\n\n".join(target_blocks))
        return "\n\n".join(chunks)


def build_bundle(
    *,
    kind: str,
    target: Iterable[str],
    feature_id: str | None,
    criteria: Iterable[str],
    context: Iterable[str],
) -> ReviewBundle:
    if kind not in VALID_KINDS:
        raise BundleError(f"unknown kind: {kind}; expected one of {sorted(VALID_KINDS)}")

    # Materialize iterables exactly once. The caller may pass a generator;
    # we both hash and store the contents, so consume into tuples up front.
    target_paths = tuple(Path(p) for p in target)
    context_paths = tuple(Path(p) for p in context)
    criteria_tuple = tuple(criteria)

    for p in target_paths:
        if not p.exists():
            raise BundleError(f"target not found: {p}")

    for p in context_paths:
        if not p.exists():
            raise BundleError(f"context not found: {p}")

    # Read each file exactly once. The hash AND render_text() both refer
    # to these snapshotted bytes, so there's no window in which a file
    # could change on disk between hashing and rendering.
    target_bytes = tuple(p.read_bytes() for p in target_paths)
    context_bytes = tuple(p.read_bytes() for p in context_paths)

    hash_payload = {
        "kind": kind,
        "feature_id": feature_id,  # None encodes naturally as null in JSON
        "targets": [(str(p), b.hex()) for p, b in zip(target_paths, target_bytes)],
        "context": [(str(p), b.hex()) for p, b in zip(context_paths, context_bytes)],
        "criteria": list(criteria_tuple),
    }
    bundle_hash = hashlib.sha256(
        json.dumps(hash_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:32]

    return ReviewBundle(
        kind=kind,
        target_paths=target_paths,
        feature_id=feature_id,
        criteria=criteria_tuple,
        context_paths=context_paths,
        bundle_hash=bundle_hash,
        _target_bytes=target_bytes,
        _context_bytes=context_bytes,
    )
