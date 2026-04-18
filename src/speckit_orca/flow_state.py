from __future__ import annotations

import argparse
import json
import re
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .sdd_adapter import SpecKitAdapter, registry as _adapter_registry


# 019 Sub-phase A / FR-013: dashed-key read alias on FeatureEvidence.filenames.
# Underscored keys (``review_spec``, ``review_code``, ``review_pr``) are
# canonical from this release forward. Reads through the legacy dashed keys
# still resolve for one release, emitting ``DeprecationWarning``. Writes
# through dashed keys are not supported. The alias lives here, NOT in
# `sdd_adapter.py`, so the adapter never ships deprecated semantics.
_DASHED_TO_UNDERSCORED: dict[str, str] = {
    "review-spec": "review_spec",
    "review-code": "review_code",
    "review-pr": "review_pr",
}


class _FilenamesDict(dict):
    """dict subclass that aliases dashed review keys to underscored.

    Read-only alias; dashed reads emit ``DeprecationWarning``. Writes and
    every other mapping operation behave exactly like ``dict``.
    """

    def __getitem__(self, key):  # type: ignore[override]
        if isinstance(key, str) and key in _DASHED_TO_UNDERSCORED:
            canonical = _DASHED_TO_UNDERSCORED[key]
            if canonical in self.keys():
                warnings.warn(
                    (
                        f"FeatureEvidence.filenames[{key!r}] is deprecated; "
                        f"use {canonical!r} instead. Dashed keys will be "
                        "removed in a future release."
                    ),
                    DeprecationWarning,
                    stacklevel=2,
                )
                return dict.__getitem__(self, canonical)
        return dict.__getitem__(self, key)

    def get(self, key, default=None):  # type: ignore[override]
        if isinstance(key, str) and key in _DASHED_TO_UNDERSCORED:
            canonical = _DASHED_TO_UNDERSCORED[key]
            if canonical in self.keys():
                warnings.warn(
                    (
                        f"FeatureEvidence.filenames.get({key!r}) is "
                        f"deprecated; use {canonical!r} instead."
                    ),
                    DeprecationWarning,
                    stacklevel=2,
                )
                return dict.__getitem__(self, canonical)
        return dict.get(self, key, default)

STAGE_ORDER = [
    "brainstorm",
    "specify",
    "plan",
    "tasks",
    "assign",
    "implement",
    "review-spec",
    "review-code",
    "review-pr",
]

STAGE_KIND = {
    "brainstorm": "meta",
    "specify": "build",
    "plan": "build",
    "tasks": "build",
    "assign": "meta",
    "implement": "build",
    "review-spec": "review",
    "review-code": "review",
    "review-pr": "review",
}

REVIEW_ARTIFACT_NAMES = ("review-spec", "review-code", "review-pr")
REVIEW_SPEC_VERDICT_VALUES = frozenset({"ready", "needs-revision", "blocked"})
REVIEW_CODE_VERDICT_VALUES = frozenset({"ready-for-pr", "needs-fixes", "blocked"})
REVIEW_PR_VERDICT_VALUES = frozenset({"merged", "pending-merge", "reverted"})


@dataclass(frozen=True)
class StageDefinition:
    name: str
    ordinal: int
    kind: str


@dataclass
class FlowMilestone:
    stage: str
    status: str
    evidence_sources: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # 019 Sub-phase B: propagate `StageProgress.kind` through.
    # Empty string sentinel preserves positional construction compatibility
    # for Phase 1 test fixtures. Every production build site now supplies
    # a real v1 stage-kind drawn from `SpecKitAdapter._STAGE_KIND_MAP`.
    kind: str = ""


@dataclass
class ReviewMilestone:
    review_type: str
    status: str
    evidence_sources: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class TaskSummary:
    total: int = 0
    completed: int = 0
    incomplete: int = 0
    assigned: int = 0
    headings: list[str] = field(default_factory=list)

    @property
    def has_implementation_progress(self) -> bool:
        return self.completed > 0


@dataclass
class ReviewSpecEvidence:
    exists: bool = False
    verdict: str | None = None
    clarify_session: str | None = None
    stale_against_clarify: bool = False
    has_cross_pass: bool = False


@dataclass
class ReviewCodeEvidence:
    exists: bool = False
    verdict: str | None = None
    phases_found: list[str] = field(default_factory=list)
    has_self_passes: bool = False
    has_cross_passes: bool = False
    overall_complete: bool = False


@dataclass
class ReviewPrEvidence:
    exists: bool = False
    verdict: str | None = None
    has_retro_note: bool = False


@dataclass
class ReviewEvidence:
    review_spec: ReviewSpecEvidence = field(default_factory=ReviewSpecEvidence)
    review_code: ReviewCodeEvidence = field(default_factory=ReviewCodeEvidence)
    review_pr: ReviewPrEvidence = field(default_factory=ReviewPrEvidence)


@dataclass
class WorktreeLane:
    lane_id: str
    branch: str | None
    status: str | None
    path: str | None
    task_scope: list[str] = field(default_factory=list)


@dataclass
class YoloRunSummary:
    """Summary of a yolo run surfaced in flow-state output.

    Derived from reducing the run's event log; mirrors a subset of
    `speckit_orca.yolo.RunState` sized for inline reporting.
    """

    run_id: str
    mode: str  # "standalone" | "matriarch-supervised"
    lane_id: str | None
    current_stage: str
    outcome: str  # "running" | "paused" | "blocked" | "completed" | "failed" | "canceled"
    block_reason: str | None
    last_event_timestamp: str
    matriarch_sync_failed: bool = False

    @property
    def is_terminal(self) -> bool:
        return self.outcome in {"completed", "canceled", "failed"}


@dataclass
class FeatureEvidence:
    feature_id: str
    feature_dir: Path
    repo_root: Path | None
    artifacts: dict[str, Path]
    task_summary: TaskSummary
    review_evidence: ReviewEvidence
    linked_brainstorms: list[Path]
    worktree_lanes: list[WorktreeLane]
    # Adapter-supplied map of semantic artifact keys to the filename
    # the active SDD format uses for that artifact. flow-state consumes
    # filenames through this map so it never hardcodes spec-kit
    # literals; future adapters supply their own values.
    filenames: dict[str, str] = field(default_factory=dict)
    ambiguities: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class FlowStateResult:
    feature_id: str
    current_stage: str | None
    completed_milestones: list[FlowMilestone]
    incomplete_milestones: list[FlowMilestone]
    review_milestones: list[ReviewMilestone]
    ambiguities: list[str]
    next_step: str | None
    evidence_summary: list[str]
    yolo_runs: list[YoloRunSummary] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "current_stage": self.current_stage,
            "completed_milestones": [asdict(item) for item in self.completed_milestones],
            "incomplete_milestones": [asdict(item) for item in self.incomplete_milestones],
            "review_milestones": [asdict(item) for item in self.review_milestones],
            "ambiguities": list(self.ambiguities),
            "next_step": self.next_step,
            "evidence_summary": list(self.evidence_summary),
            "yolo_runs": [asdict(run) for run in self.yolo_runs],
        }

    def to_text(self) -> str:
        lines = [
            f"Feature: {self.feature_id}",
            f"Current stage: {self.current_stage or 'ambiguous/unknown'}",
            f"Next step: {self.next_step or 'none'}",
        ]
        if self.completed_milestones:
            lines.append("Completed milestones:")
            lines.extend(
                f"- {item.stage}: {', '.join(item.evidence_sources) or 'derived'}"
                for item in self.completed_milestones
            )
        if self.incomplete_milestones:
            lines.append("Incomplete milestones:")
            lines.extend(f"- {item.stage}" for item in self.incomplete_milestones)
        if self.review_milestones:
            lines.append("Review milestones:")
            lines.extend(
                f"- {item.review_type}: {item.status}"
                for item in self.review_milestones
            )
        if self.yolo_runs:
            active = [r for r in self.yolo_runs if not r.is_terminal]
            terminal = [r for r in self.yolo_runs if r.is_terminal]
            if active:
                lines.append("Active yolo runs:")
                lines.extend(
                    f"- {run.run_id} [{run.mode}] stage={run.current_stage} outcome={run.outcome}"
                    + (f" — {run.block_reason}" if run.block_reason else "")
                    + (" [matriarch_sync_failed]" if run.matriarch_sync_failed else "")
                    for run in active
                )
            if terminal:
                lines.append("Terminal yolo runs:")
                lines.extend(
                    f"- {run.run_id} [{run.mode}] {run.outcome} at {run.current_stage}"
                    + (f" — {run.block_reason}" if run.block_reason else "")
                    + (" [matriarch_sync_failed]" if run.matriarch_sync_failed else "")
                    for run in terminal
                )
        if self.ambiguities:
            lines.append("Ambiguities:")
            lines.extend(f"- {note}" for note in self.ambiguities)
        if self.evidence_summary:
            lines.append("Evidence summary:")
            lines.extend(f"- {note}" for note in self.evidence_summary)
        return "\n".join(lines)


CANONICAL_STAGES = tuple(
    StageDefinition(name=name, ordinal=index + 1, kind=STAGE_KIND[name])
    for index, name in enumerate(STAGE_ORDER)
)


@dataclass
class AdoptionFlowState:
    """Flow-state view for an adoption record (per-file target).

    Distinct from both `FlowStateResult` and `SpecLiteFlowState`.
    Produced by `compute_adoption_state` when the target path is
    an AR file under `.specify/orca/adopted/`.

    Per the 015 adoption-record.md contract, the emitted JSON
    shape uses the key `id` (not `record_id`) and malformed
    records carry `kind: "adoption"` with `status: "invalid"`
    (not a separate `"adoption-invalid"` kind). `review_state`
    is hard-coded to `"not-applicable"` — ARs never participate
    in 012's review model.
    """

    kind: str  # always "adoption"
    record_id: str  # serialized as "id" per contract
    slug: str
    title: str
    status: str  # adopted | superseded | retired | invalid
    adopted_on: str
    baseline_commit: str | None
    location: list[str]
    key_behaviors: list[str]
    known_gaps: str | None
    superseded_by: str | None
    retirement_reason: str | None
    review_state: str  # always "not-applicable"
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.record_id,
            "slug": self.slug,
            "title": self.title,
            "status": self.status,
            "adopted_on": self.adopted_on,
            "baseline_commit": self.baseline_commit,
            "location": list(self.location),
            "key_behaviors": list(self.key_behaviors),
            "known_gaps": self.known_gaps,
            "superseded_by": self.superseded_by,
            "retirement_reason": self.retirement_reason,
            "review_state": self.review_state,
            "path": self.path,
        }

    def to_text(self) -> str:
        stem = f"{self.record_id}-{self.slug}" if self.slug else self.record_id
        lines = [
            f"Adoption record: {stem}",
            f"Title: {self.title}",
            f"Status: {self.status}",
            f"Adopted-on: {self.adopted_on}",
        ]
        if self.baseline_commit is not None:
            lines.append(f"Baseline commit: {self.baseline_commit}")
        lines.append(f"Review state: {self.review_state}")
        if self.location:
            lines.append("Location:")
            lines.extend(f"- {p}" for p in self.location)
        if self.key_behaviors:
            lines.append("Key behaviors:")
            lines.extend(f"- {b}" for b in self.key_behaviors)
        if self.superseded_by is not None:
            lines.append(f"Superseded by: {self.superseded_by}")
        if self.retirement_reason is not None:
            lines.append(f"Retirement reason: {self.retirement_reason}")
        return "\n".join(lines)


@dataclass
class SpecLiteFlowState:
    """Flow-state view for a spec-lite record (per-file target).

    Distinct from `FlowStateResult` (which interprets feature
    directories under `specs/`). Produced by
    `compute_spec_lite_state` when the target path is a spec-lite
    record file under `.specify/orca/spec-lite/`.

    Per the 013 spec-lite-record.md contract, the emitted JSON
    shape uses the key `id` (not `record_id`) and malformed records
    carry `kind: "spec-lite"` with `status: "invalid"` (not a
    separate kind). The dataclass uses `record_id` internally
    because `id` would shadow the Python builtin; `to_dict` emits
    the contracted key names.
    """

    kind: str  # always "spec-lite"
    record_id: str  # serialized as "id" per contract
    slug: str
    title: str
    source_name: str
    created: str
    status: str  # open | implemented | abandoned | invalid
    files_affected: list[str]
    has_verification_evidence: bool
    review_state: str  # unreviewed | self-reviewed | cross-reviewed
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.record_id,
            "slug": self.slug,
            "title": self.title,
            "source_name": self.source_name,
            "created": self.created,
            "status": self.status,
            "files_affected": list(self.files_affected),
            "has_verification_evidence": self.has_verification_evidence,
            "review_state": self.review_state,
            "path": self.path,
        }

    def to_text(self) -> str:
        lines = [
            f"Spec-lite: {self.record_id}-{self.slug}" if self.slug else f"Spec-lite: {self.record_id}",
            f"Title: {self.title}",
            f"Status: {self.status}",
            f"Source: {self.source_name}  (created {self.created})",
            f"Review state: {self.review_state}",
            f"Verification evidence: {'present' if self.has_verification_evidence else 'absent'}",
        ]
        if self.files_affected:
            lines.append("Files affected:")
            lines.extend(f"- {p}" for p in self.files_affected)
        return "\n".join(lines)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# 019 Sub-phase B: `_SPEC_KIT_ADAPTER` is now a deprecated alias.
#
# The canonical adapter lookup is `sdd_adapter.registry`. The legacy
# singleton stays live and synced with the registry's `SpecKitAdapter`
# instance so pre-Phase-2 consumers and tests keep working (FR-021,
# FR-034). A PEP 562 `__getattr__` on this module intercepts attribute
# access to emit a once-per-process `DeprecationWarning`; a custom
# `ModuleType` subclass intercepts `__setattr__` so
# `monkeypatch.setattr(flow_state, "_SPEC_KIT_ADAPTER", spy)` also swaps
# the adapter inside the registry.
#
# PEP 562 limitation (plan sub-phase B Risk #2): a module-scope
# `from speckit_orca.flow_state import _SPEC_KIT_ADAPTER` binds the
# attribute at import time BEFORE `__getattr__` fires, so such imports
# do not warn. The only way to reach this code path is via attribute
# access (`fs.x`, `getattr(fs, "x")`). Document this limitation in the
# migration notes; do NOT try to work around it.

_DEPRECATION_FLAG_ATTR = "_SPEC_KIT_ADAPTER"
_deprecation_warned = False


def _spec_kit_adapter_from_registry() -> SpecKitAdapter:
    """Return the live `SpecKitAdapter` instance inside the registry.

    If the registry has been cleared (test harness misuse), restore the
    default adapter set via ``reset_to_defaults`` and retry — this keeps
    the spec-kit instance singular and owned by the registry per T030.
    """
    for adapter in _adapter_registry.adapters():
        if isinstance(adapter, SpecKitAdapter):
            return adapter
    _adapter_registry.reset_to_defaults()
    for adapter in _adapter_registry.adapters():
        if isinstance(adapter, SpecKitAdapter):
            return adapter
    raise RuntimeError(
        "SpecKitAdapter missing from registry after reset_to_defaults; "
        "did a test harness overwrite registry._adapters?"
    )


def collect_feature_evidence(
    feature_dir: Path | str,
    repo_root: Path | str | None = None,
) -> FeatureEvidence:
    """Load a feature's durable artifacts into a ``FeatureEvidence``.

    Sub-phase B: adapter selection routes through
    ``sdd_adapter.registry``. ``resolve_for_path`` returns the first
    adapter that owns the path; Phase-1 fallback (directory basename)
    is preserved when no adapter anchors the path.
    """
    from .sdd_adapter import FeatureHandle

    feature_path = Path(feature_dir).resolve()
    repo_override = Path(repo_root).resolve() if repo_root is not None else None

    resolved = _adapter_registry.resolve_for_path(
        feature_path, repo_root=repo_override
    )
    if resolved is not None:
        adapter, feature_id = resolved
    else:
        # Phase-1 fallback: feature_dir outside any adapter's purview
        # (e.g., a detached fixture path). Fall back to the spec-kit
        # adapter so the legacy code path stays green.
        adapter = _spec_kit_adapter_from_registry()
        feature_id = feature_path.name

    handle = FeatureHandle(
        feature_id=feature_id,
        display_name=feature_path.name,
        root_path=feature_path,
        adapter_name=adapter.name,
    )
    normalized = adapter.load_feature(handle, repo_root=repo_override)
    return adapter.to_feature_evidence(normalized, repo_root=repo_override)


# ---------------------------------------------------------------------------
# PEP 562 `__getattr__` + module `__setattr__` for `_SPEC_KIT_ADAPTER`.
# ---------------------------------------------------------------------------


def __getattr__(name: str):
    """PEP 562 module-level attribute access hook.

    Emits a one-time `DeprecationWarning` when a consumer reads
    ``speckit_orca.flow_state._SPEC_KIT_ADAPTER``. Returns the live
    `SpecKitAdapter` in the registry.
    """
    global _deprecation_warned
    if name == _DEPRECATION_FLAG_ATTR:
        if not _deprecation_warned:
            warnings.warn(
                (
                    "speckit_orca.flow_state._SPEC_KIT_ADAPTER is deprecated; "
                    "use `from speckit_orca.sdd_adapter import registry` and "
                    "`registry.resolve_for_path(...)` instead. This alias "
                    "will be removed in a future release."
                ),
                DeprecationWarning,
                stacklevel=2,
            )
            _deprecation_warned = True
        return _spec_kit_adapter_from_registry()
    raise AttributeError(f"module 'speckit_orca.flow_state' has no attribute {name!r}")


def _install_module_setattr_hook() -> None:
    """Swap this module's class so assignments to ``_SPEC_KIT_ADAPTER``
    keep the registry in sync (FR-021 / FR-034).

    Tests that do ``monkeypatch.setattr(flow_state, "_SPEC_KIT_ADAPTER",
    spy)`` expect the spy to own subsequent `collect_feature_evidence`
    calls. Since those calls go through the registry, we intercept the
    assignment here and register the spy (or swap the existing entry).
    """
    import sys
    import types

    mod = sys.modules[__name__]

    class _SpecKitAdapterSyncingModule(types.ModuleType):
        def __setattr__(self, attr_name, value):  # type: ignore[override]
            if attr_name == _DEPRECATION_FLAG_ATTR and isinstance(
                value, SpecKitAdapter
            ):
                # Replace any existing SpecKitAdapter in the registry
                # with the assigned instance, preserving the relative
                # position so resolve order is stable.
                current = list(_adapter_registry.adapters())
                new_adapters: list = []
                replaced = False
                for existing in current:
                    if isinstance(existing, SpecKitAdapter) and not replaced:
                        new_adapters.append(value)
                        replaced = True
                    else:
                        new_adapters.append(existing)
                if not replaced:
                    new_adapters.append(value)
                _adapter_registry._adapters = tuple(new_adapters)
                # Intentionally DO NOT persist ``_SPEC_KIT_ADAPTER`` in
                # the module ``__dict__``. PEP 562 ``__getattr__`` only
                # fires for missing attributes; if we stored the value
                # here, later reads would bypass the deprecation warning
                # entirely. By routing every `_SPEC_KIT_ADAPTER` read
                # through `__getattr__` we keep the warning behavior
                # stable across monkeypatch set+undo cycles.
                # Drop any stale entry left by a prior direct assignment.
                self.__dict__.pop(attr_name, None)
                return
            super().__setattr__(attr_name, value)

        def __delattr__(self, attr_name):  # type: ignore[override]
            # Tolerate `del flow_state._SPEC_KIT_ADAPTER` even when the
            # attribute was never persisted (monkeypatch undo path).
            if attr_name == _DEPRECATION_FLAG_ATTR:
                self.__dict__.pop(attr_name, None)
                return
            super().__delattr__(attr_name)

    mod.__class__ = _SpecKitAdapterSyncingModule


_install_module_setattr_hook()


def _review_milestones(evidence: FeatureEvidence) -> list[ReviewMilestone]:
    rev = evidence.review_evidence
    review_spec_name = evidence.filenames["review_spec"]
    review_code_name = evidence.filenames["review_code"]
    review_pr_name = evidence.filenames["review_pr"]
    # Prefer the adapter's real path map over rebuilding from feature_dir.
    # `filenames` is just for display; `artifacts` is the canonical map a
    # future non-spec-kit adapter may anchor outside `feature_dir`.
    review_spec_path = evidence.artifacts.get(
        review_spec_name, evidence.feature_dir / review_spec_name
    )
    review_code_path = evidence.artifacts.get(
        review_code_name, evidence.feature_dir / review_code_name
    )
    review_pr_path = evidence.artifacts.get(
        review_pr_name, evidence.feature_dir / review_pr_name
    )
    milestones: list[ReviewMilestone] = []

    # review-spec
    if not rev.review_spec.exists:
        milestones.append(ReviewMilestone("review-spec", "missing"))
    elif rev.review_spec.stale_against_clarify:
        milestones.append(ReviewMilestone(
            "review-spec", "stale",
            notes=[f"{review_spec_name} is stale against a newer clarify session"],
        ))
    elif rev.review_spec.verdict == "ready" and rev.review_spec.has_cross_pass:
        milestones.append(ReviewMilestone(
            "review-spec", "present",
            evidence_sources=[str(review_spec_path)],
        ))
    elif rev.review_spec.verdict == "needs-revision":
        milestones.append(ReviewMilestone("review-spec", "needs-revision"))
    elif rev.review_spec.verdict == "blocked":
        milestones.append(ReviewMilestone("review-spec", "blocked"))
    else:
        milestones.append(ReviewMilestone(
            "review-spec", "invalid",
            notes=[f"{review_spec_name} exists but has no recognized verdict"],
        ))

    # review-code
    if not rev.review_code.exists:
        milestones.append(ReviewMilestone("review-code", "not_started"))
    elif (
        rev.review_code.overall_complete
        and rev.review_code.verdict in REVIEW_CODE_VERDICT_VALUES
        and rev.review_code.has_self_passes
        and rev.review_code.has_cross_passes
    ):
        milestones.append(ReviewMilestone(
            "review-code", "overall_complete",
            evidence_sources=[str(review_code_path)],
        ))
    elif rev.review_code.phases_found:
        milestones.append(ReviewMilestone(
            "review-code", "phases_partial",
            notes=[f"Phases found: {', '.join(rev.review_code.phases_found)}"],
        ))
    else:
        milestones.append(ReviewMilestone(
            "review-code", "invalid",
            notes=[f"{review_code_name} exists but has no recognized phase structure"],
        ))

    # review-pr
    if not rev.review_pr.exists:
        milestones.append(ReviewMilestone("review-pr", "not_started"))
    elif rev.review_pr.verdict == "merged" and rev.review_pr.has_retro_note:
        milestones.append(ReviewMilestone(
            "review-pr", "complete",
            evidence_sources=[str(review_pr_path)],
        ))
    elif rev.review_pr.verdict == "pending-merge" and rev.review_pr.has_retro_note:
        milestones.append(ReviewMilestone("review-pr", "in_progress"))
    elif rev.review_pr.verdict == "reverted":
        milestones.append(ReviewMilestone("review-pr", "reverted"))
    else:
        milestones.append(ReviewMilestone(
            "review-pr", "invalid",
            notes=[f"{review_pr_name} exists but has no recognized verdict"],
        ))

    return milestones


def _stage_milestones(evidence: FeatureEvidence, reviews: list[ReviewMilestone]) -> list[FlowMilestone]:
    review_map = {item.review_type: item for item in reviews}
    tasks_path = evidence.artifacts[evidence.filenames["tasks"]]
    spec_path = evidence.artifacts[evidence.filenames["spec"]]
    plan_path = evidence.artifacts[evidence.filenames["plan"]]
    brainstorm_path = evidence.artifacts[evidence.filenames["brainstorm"]]
    review_code_path = evidence.artifacts.get(
        evidence.filenames["review_code"],
        evidence.feature_dir / evidence.filenames["review_code"],
    )
    # 019 Sub-phase B: propagate the spec-kit stage-kind map into the
    # FlowMilestone `kind` field so downstream consumers (and the parity
    # snapshots) see the v1 vocabulary. The map lives on SpecKitAdapter;
    # no new literals live here.
    stage_kind = SpecKitAdapter._STAGE_KIND_MAP
    milestones: list[FlowMilestone] = []

    brainstorm_sources = [str(brainstorm_path)] if brainstorm_path.exists() else []
    brainstorm_sources.extend(str(path) for path in evidence.linked_brainstorms)
    milestones.append(
        FlowMilestone(
            stage="brainstorm",
            status="complete" if brainstorm_sources else "incomplete",
            evidence_sources=brainstorm_sources,
            kind=stage_kind["brainstorm"],
        )
    )

    milestones.append(
        FlowMilestone(
            stage="specify",
            status="complete" if spec_path.exists() else "incomplete",
            evidence_sources=[str(spec_path)] if spec_path.exists() else [],
            kind=stage_kind["specify"],
        )
    )
    milestones.append(
        FlowMilestone(
            stage="plan",
            status="complete" if plan_path.exists() else "incomplete",
            evidence_sources=[str(plan_path)] if plan_path.exists() else [],
            kind=stage_kind["plan"],
        )
    )
    milestones.append(
        FlowMilestone(
            stage="tasks",
            status="complete" if tasks_path.exists() else "incomplete",
            evidence_sources=[str(tasks_path)] if tasks_path.exists() else [],
            kind=stage_kind["tasks"],
        )
    )

    assign_status = "incomplete"
    assign_sources: list[str] = []
    if tasks_path.exists() and evidence.task_summary.assigned > 0:
        assign_status = "complete"
        assign_sources.append(str(tasks_path))
    milestones.append(
        FlowMilestone(
            "assign", assign_status, assign_sources, kind=stage_kind["assign"]
        )
    )

    implement_status = "incomplete"
    implement_sources: list[str] = []
    if evidence.task_summary.has_implementation_progress:
        implement_status = "complete"
        implement_sources.append(str(tasks_path))
    elif evidence.review_evidence.review_code.exists:
        implement_status = "complete"
        implement_sources.append(str(review_code_path))
    milestones.append(
        FlowMilestone(
            "implement",
            implement_status,
            implement_sources,
            kind=stage_kind["implement"],
        )
    )

    for review_name in REVIEW_ARTIFACT_NAMES:
        rm = review_map[review_name]
        milestones.append(
            FlowMilestone(
                review_name,
                rm.status,
                list(rm.evidence_sources),
                list(rm.notes),
                kind=stage_kind[review_name],
            )
        )
    return milestones


def _derive_ambiguities(evidence: FeatureEvidence, milestones: list[FlowMilestone], reviews: list[ReviewMilestone]) -> list[str]:
    ambiguities = list(evidence.ambiguities)
    stage_status = {item.stage: item.status for item in milestones}

    if stage_status["plan"] == "complete" and stage_status["specify"] != "complete":
        ambiguities.append("Planning evidence exists without specification evidence.")
    if stage_status["tasks"] == "complete" and stage_status["plan"] != "complete":
        ambiguities.append("Task breakdown exists without planning evidence.")
    if stage_status["implement"] == "complete" and stage_status["tasks"] != "complete":
        ambiguities.append("Implementation progress exists without task breakdown evidence.")

    for review in reviews:
        if review.status == "invalid":
            ambiguities.extend(review.notes)

    return ambiguities


def _completed_stage(milestones: list[FlowMilestone]) -> str | None:
    reached_review_statuses: dict[str, set[str]] = {
        "review-spec": {"present"},
        "review-code": {"phases_partial", "overall_complete"},
        "review-pr": {"in_progress", "complete"},
    }

    def _is_reached(item: FlowMilestone) -> bool:
        if item.status == "complete":
            return True
        return item.status in reached_review_statuses.get(item.stage, set())

    completed = [item.stage for item in milestones if _is_reached(item)]
    if not completed:
        return None
    return max(completed, key=STAGE_ORDER.index)


def _has_material_conflict(
    ambiguities: list[str], filenames: dict[str, str]
) -> bool:
    review_code_name = filenames["review_code"]
    tasks_name = filenames["tasks"]
    conflict_markers = (
        "without specification evidence",
        "without planning evidence",
        "without task breakdown evidence",
        f"{review_code_name} exists without {tasks_name}",
    )
    return any(any(marker in ambiguity for marker in conflict_markers) for ambiguity in ambiguities)


def _next_step(milestones: list[FlowMilestone], ambiguities: list[str], evidence: FeatureEvidence) -> str | None:
    if len(ambiguities) >= 3:
        return None

    status_map = {item.stage: item.status for item in milestones}
    spec_name = evidence.filenames["spec"]
    plan_name = evidence.filenames["plan"]
    tasks_name = evidence.filenames["tasks"]

    if status_map["specify"] != "complete":
        return f"Create or refine {spec_name} before advancing the feature."
    if status_map["plan"] != "complete":
        return f"Generate {plan_name} to lock architecture and implementation shape."
    if status_map["tasks"] != "complete":
        return f"Generate {tasks_name} so implementation can proceed from a durable task plan."
    if status_map["assign"] != "complete" and status_map["implement"] != "complete":
        return "Run /speckit.orca.assign if this feature needs multi-agent coordination, or proceed directly to implementation."
    if status_map["implement"] != "complete":
        return f"Implement the next incomplete task and keep {tasks_name} current."
    review_spec_status = status_map.get("review-spec", "missing")
    if review_spec_status in {"missing", "stale", "needs-revision"}:
        return "Run /speckit.orca.review-spec for an adversarial cross-pass review of the spec."
    review_code_status = status_map.get("review-code", "not_started")
    if review_code_status in {"not_started", "phases_partial"}:
        return "Run /speckit.orca.review-code on the implemented work (self-pass then cross-pass per phase)."
    review_pr_status = status_map.get("review-pr", "not_started")
    if review_pr_status in {"not_started", "in_progress"}:
        return "Run /speckit.orca.review-pr to handle PR creation and external comments."
    if evidence.worktree_lanes:
        return "Retire or merge the active Orca lane once the reviewed work is integrated."
    return None


def _evidence_summary(evidence: FeatureEvidence, milestones: list[FlowMilestone], reviews: list[ReviewMilestone]) -> list[str]:
    summary: list[str] = []
    resume_metadata = _load_resume_metadata(evidence.feature_dir, evidence.repo_root)

    artifact_names = [name for name, path in evidence.artifacts.items() if path.exists()]
    if artifact_names:
        summary.append("Artifacts present: " + ", ".join(sorted(artifact_names)))

    if evidence.task_summary.total:
        summary.append(
            "Task status: "
            f"{evidence.task_summary.completed}/{evidence.task_summary.total} completed, "
            f"{evidence.task_summary.assigned} assigned."
        )

    terminal_statuses = {"present", "overall_complete", "complete"}
    completed_reviews = [item.review_type for item in reviews if item.status in terminal_statuses]
    if completed_reviews:
        summary.append("Completed reviews: " + ", ".join(completed_reviews))

    if evidence.worktree_lanes:
        lanes = ", ".join(f"{lane.lane_id}:{lane.status or 'unknown'}" for lane in evidence.worktree_lanes)
        summary.append("Worktree lanes: " + lanes)

    if resume_metadata:
        last_stage = resume_metadata.get("last_computed_stage")
        updated_at = resume_metadata.get("updated_at")
        summary.append(
            "Resume metadata available"
            + (f" from {updated_at}" if updated_at else "")
            + (f" (last stage: {last_stage})" if last_stage else "")
        )

    summary.extend(evidence.notes)

    last_stage = _completed_stage(milestones)
    if last_stage:
        summary.append(f"Highest completed stage: {last_stage}")

    return summary


def _resume_metadata_path(feature_dir: Path, repo_root: Path | None) -> Path:
    if repo_root is not None:
        return repo_root / ".specify" / "orca" / "flow-state" / f"{feature_dir.name}.json"
    return feature_dir / ".flow-state.json"


def _load_resume_metadata(feature_dir: Path, repo_root: Path | None) -> dict[str, Any] | None:
    path = _resume_metadata_path(feature_dir, repo_root)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_resume_metadata(result: FlowStateResult, feature_dir: Path, repo_root: Path | None) -> Path:
    path = _resume_metadata_path(feature_dir, repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "feature_id": result.feature_id,
        "last_computed_stage": result.current_stage,
        "last_next_step": result.next_step,
        "updated_at": _now_utc(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


# Stricter than `^SL-\d{3}(?:-.+)?$`: disallows `.` in the slug so
# companion filenames like `SL-001-foo.self-review` and
# `SL-001-foo.cross-review` don't match when we look at `Path.stem`
# (which strips only the final `.md` extension). Slug shape mirrors
# `_slugify()` output: lowercase alphanumerics separated by hyphens.
_SPEC_LITE_FILENAME_RE = re.compile(r"^SL-\d{3}(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?$")
# Header fallback — STRICTER than the 013 contract's documented
# detection regex (`^# Spec-Lite SL-\d{3}(:.*)?$`) per the codex
# cross-review finding in PR #40: requires a non-empty title after
# the colon so titleless stubs don't trip detection. The runtime
# is intentionally stricter than the contract; the contract may be
# tightened in a future 013 revision to match.
_SPEC_LITE_HEADER_RE = re.compile(r"^# Spec-Lite SL-\d{3}:\s+\S.*$")

# Same structural shape as `_SPEC_LITE_FILENAME_RE`: disallows `.`
# in the slug so companion-style names with extra dotted suffixes
# don't false-match. ARs in v1 don't have review companions (015
# explicitly disallows review participation), but the stricter
# regex is defensive and matches 013's pattern for consistency.
_ADOPTION_FILENAME_RE = re.compile(r"^AR-\d{3}(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?$")
# Header fallback requires the full contracted title shape per 015
# adoption-record.md: `# Adoption Record: AR-NNN: <title>`.
_ADOPTION_HEADER_RE = re.compile(r"^# Adoption Record: AR-\d{3}:\s+\S.*$")


def _is_spec_lite_target(target: Path) -> bool:
    """Return True if the given path is a spec-lite record file.

    Uses a path prefix check under `.specify/orca/spec-lite/` as the
    primary signal, falling back to a header match for misplaced
    files (mirrors the detection rule in 013's spec-lite-record
    contract).
    """
    if not target.is_file() or target.suffix != ".md":
        return False
    if target.name == "00-overview.md":
        return False

    # 1. Path match — canonical location. Require the file to sit
    #    IMMEDIATELY inside `.specify/orca/spec-lite/` with no
    #    intermediate directories (no archive/, no nested
    #    subfolders). Combined with the stricter
    #    `_SPEC_LITE_FILENAME_RE`, this excludes companion review
    #    files and any non-record content under the registry dir.
    if (
        target.parent.name == "spec-lite"
        and target.parent.parent.name == "orca"
        and target.parent.parent.parent.name == ".specify"
        and _SPEC_LITE_FILENAME_RE.match(target.stem)
    ):
        return True

    # 2. Header match fallback (defensive against misplaced files)
    try:
        first_line = next(
            (line for line in target.read_text(encoding="utf-8").splitlines() if line.strip()),
            "",
        )
    except (OSError, UnicodeDecodeError):
        return False
    return bool(_SPEC_LITE_HEADER_RE.match(first_line))


def _derive_spec_lite_review_state(record_path: Path, record_id: str, slug: str) -> str:
    """Compute `review_state` for a spec-lite record from sibling review files.

    Per 013 contract, review sibling files share the record's ID stem:
      SL-NNN-<slug>.self-review.md
      SL-NNN-<slug>.cross-review.md
    """
    stem = f"{record_id}-{slug}" if slug else record_id
    directory = record_path.parent
    self_review = directory / f"{stem}.self-review.md"
    cross_review = directory / f"{stem}.cross-review.md"
    if cross_review.is_file():
        return "cross-reviewed"
    if self_review.is_file():
        return "self-reviewed"
    return "unreviewed"


def compute_spec_lite_state(record_path: Path | str) -> SpecLiteFlowState:
    """Interpret a spec-lite record file and return its flow-state view.

    Parse failures produce `kind: "spec-lite"` with `status: "invalid"`
    (per the 013 contract), so flow-state callers can tolerate
    malformed records without crashing.
    """
    from . import spec_lite as _spec_lite  # local import to avoid cycle

    path = Path(record_path).resolve()
    path_str = str(path)
    try:
        record = _spec_lite.parse_record(path)
    except _spec_lite.SpecLiteError as exc:
        # Extract record_id from filename stem if possible
        stem_match = _spec_lite.ID_STEM_RE.match(path.stem)
        record_id = f"SL-{stem_match.group(1)}" if stem_match else ""
        slug = stem_match.group(2) if stem_match and stem_match.group(2) else ""
        return SpecLiteFlowState(
            kind="spec-lite",
            record_id=record_id,
            slug=slug,
            title=f"<invalid: {exc}>",
            source_name="",
            created="",
            status="invalid",
            files_affected=[],
            has_verification_evidence=False,
            review_state="unreviewed",
            path=path_str,
        )

    review_state = _derive_spec_lite_review_state(path, record.record_id, record.slug)
    return SpecLiteFlowState(
        kind="spec-lite",
        record_id=record.record_id,
        slug=record.slug,
        title=record.title,
        source_name=record.source_name,
        created=record.created,
        status=record.status,
        files_affected=list(record.files_affected),
        has_verification_evidence=bool(record.verification_evidence),
        review_state=review_state,
        path=path_str,
    )


def _is_adoption_target(target: Path) -> bool:
    """Return True if the given path is an adoption record file.

    Mirrors `_is_spec_lite_target`'s detection strategy: strict
    filename regex + immediate-parent path check, with a defensive
    header-match fallback for misplaced files. Unlike spec-lite,
    ARs in v1 don't have review companions, but the regex still
    disallows `.` in the stem for consistency and future-proofing.
    """
    if not target.is_file() or target.suffix != ".md":
        return False
    if target.name == "00-overview.md":
        return False

    # 1. Path match — canonical location. File must sit IMMEDIATELY
    #    inside `.specify/orca/adopted/` with no intermediate
    #    subdirectories.
    if (
        target.parent.name == "adopted"
        and target.parent.parent.name == "orca"
        and target.parent.parent.parent.name == ".specify"
        and _ADOPTION_FILENAME_RE.match(target.stem)
    ):
        return True

    # 2. Header match fallback (defensive against misplaced files).
    try:
        first_nonblank = next(
            (
                line
                for line in target.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ),
            "",
        )
    except (OSError, UnicodeDecodeError):
        return False
    return bool(_ADOPTION_HEADER_RE.match(first_nonblank))


def compute_adoption_state(record_path: Path | str) -> AdoptionFlowState:
    """Interpret an adoption record file and return its flow-state view.

    Parse failures produce `kind: "adoption"` with `status: "invalid"`
    (per the 015 contract), so flow-state callers can tolerate
    malformed records without crashing.
    """
    from . import adoption as _adoption  # local import to avoid cycle

    path = Path(record_path).resolve()
    path_str = str(path)
    try:
        record = _adoption.parse_record(path)
    except _adoption.AdoptionError as exc:
        stem_match = _adoption.ID_STEM_RE.match(path.stem)
        record_id = f"AR-{stem_match.group(1)}" if stem_match else ""
        slug = stem_match.group(2) if stem_match and stem_match.group(2) else ""
        return AdoptionFlowState(
            kind="adoption",
            record_id=record_id,
            slug=slug,
            title=f"<invalid: {exc}>",
            status="invalid",
            adopted_on="",
            baseline_commit=None,
            location=[],
            key_behaviors=[],
            known_gaps=None,
            superseded_by=None,
            retirement_reason=None,
            review_state="not-applicable",
            path=path_str,
        )

    return AdoptionFlowState(
        kind="adoption",
        record_id=record.record_id,
        slug=record.slug,
        title=record.title,
        status=record.status,
        adopted_on=record.adopted_on,
        baseline_commit=record.baseline_commit,
        location=list(record.location),
        key_behaviors=list(record.key_behaviors),
        known_gaps=record.known_gaps,
        superseded_by=record.superseded_by,
        retirement_reason=record.retirement_reason,
        review_state="not-applicable",
        path=path_str,
    )


def list_yolo_runs_for_feature(
    repo_root: Path | None, feature_id: str
) -> list[YoloRunSummary]:
    """Find all yolo runs whose RUN_STARTED event carries `feature_id`.

    Discovers runs by replaying `.specify/orca/yolo/runs/*/events.jsonl`.
    Returns empty list if no runs directory exists or no matching runs
    are found. status.json is not consulted — the event log is
    authoritative, and status.json is only a derived snapshot.
    """
    if repo_root is None:
        return []
    runs_dir = repo_root / ".specify" / "orca" / "yolo" / "runs"
    if not runs_dir.exists():
        return []

    # Import lazily to keep flow_state standalone-importable in contexts
    # where yolo isn't configured.
    try:
        from speckit_orca.yolo import load_events, reduce
    except ImportError:
        return []

    try:
        from speckit_orca.yolo import EventType, sync_failed as _sync_failed
    except ImportError:
        return []

    summaries: list[YoloRunSummary] = []
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        events_path = run_dir / "events.jsonl"
        if not events_path.exists():
            continue
        try:
            events = load_events(repo_root, run_dir.name)
            if not events:
                continue
            # Explicitly locate RUN_STARTED instead of assuming events[0]
            # is it. Sort order usually guarantees it, but a corrupted log
            # with bad lamport clocks could put another event first.
            started = next(
                (e for e in events if e.event_type == EventType.RUN_STARTED),
                None,
            )
            if started is None or started.feature_id != feature_id:
                continue
            state = reduce(events)
        except (ValueError, KeyError, OSError):
            continue

        summaries.append(
            YoloRunSummary(
                run_id=state.run_id,
                mode=state.mode,
                lane_id=state.lane_id,
                current_stage=state.current_stage,
                outcome=state.outcome,
                block_reason=state.block_reason,
                last_event_timestamp=state.last_event_timestamp,
                matriarch_sync_failed=_sync_failed(repo_root, run_dir.name),
            )
        )

    return summaries


def compute_flow_state(
    feature_dir: Path | str,
    repo_root: Path | str | None = None,
    *,
    write_resume: bool = False,
) -> FlowStateResult:
    evidence = collect_feature_evidence(feature_dir, repo_root)
    reviews = _review_milestones(evidence)
    milestones = _stage_milestones(evidence, reviews)
    ambiguities = _derive_ambiguities(evidence, milestones, reviews)
    current_stage = _completed_stage(milestones)
    if _has_material_conflict(ambiguities, evidence.filenames):
        current_stage = None
    next_step = _next_step(milestones, ambiguities, evidence)
    yolo_runs = list_yolo_runs_for_feature(evidence.repo_root, evidence.feature_id)
    result = FlowStateResult(
        feature_id=evidence.feature_id,
        current_stage=current_stage,
        completed_milestones=[item for item in milestones if item.status == "complete"],
        incomplete_milestones=[item for item in milestones if item.status != "complete"],
        review_milestones=reviews,
        ambiguities=ambiguities,
        next_step=next_step,
        evidence_summary=_evidence_summary(evidence, milestones, reviews),
        yolo_runs=yolo_runs,
    )

    if write_resume:
        write_resume_metadata(result, evidence.feature_dir, evidence.repo_root)

    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compute Orca flow state from durable feature artifacts.")
    parser.add_argument(
        "target",
        help=(
            "Path to the feature directory (e.g., specs/005-orca-flow-state), "
            "a spec-lite record (e.g., .specify/orca/spec-lite/SL-001-foo.md), "
            "or an adoption record (e.g., .specify/orca/adopted/AR-001-foo.md)."
        ),
    )
    parser.add_argument("--repo-root", help="Optional repo root override for fixture validation or detached feature paths")
    parser.add_argument("--format", choices=("json", "text"), default="json", help="Output format")
    parser.add_argument(
        "--write-resume-metadata",
        action="store_true",
        help="Write thin cached resume metadata under .specify/orca/flow-state/ when a repo root is available.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    target = Path(args.target)

    # Dispatch on target type — file paths pointing at a spec-lite
    # record get the spec-lite view, AR file paths get the adoption
    # view, everything else goes through the full-spec
    # feature-directory interpreter.
    if _is_spec_lite_target(target):
        sl_result = compute_spec_lite_state(target)
        if args.format == "text":
            print(sl_result.to_text())
        else:
            print(json.dumps(sl_result.to_dict(), indent=2))
        return 0

    if _is_adoption_target(target):
        ad_result = compute_adoption_state(target)
        if args.format == "text":
            print(ad_result.to_text())
        else:
            print(json.dumps(ad_result.to_dict(), indent=2))
        return 0

    result = compute_flow_state(
        args.target,
        repo_root=args.repo_root,
        write_resume=args.write_resume_metadata,
    )
    if args.format == "text":
        print(result.to_text())
    else:
        print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
