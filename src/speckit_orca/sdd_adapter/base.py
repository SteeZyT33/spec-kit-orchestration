"""SDD Adapter ABC + normalized dataclasses.

019 Sub-phase C (T033): extracted from the original ``sdd_adapter.py``.
Holds the adapter contract (`SddAdapter`) and the adapter-independent
data shapes that cross the adapter boundary. No concrete adapter lives
here; importing this module alone MUST NOT construct any adapter
instance (NFR-005).

Everything public here is re-exported from ``speckit_orca.sdd_adapter``
so pre-split imports keep working unchanged (FR-020, NFR-003).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FeatureHandle:
    """Opaque handle to a feature discovered by an adapter.

    The handle is what callers pass back to `load_feature` and
    `compute_stage`. Different adapters may encode different semantics
    in `feature_id`; callers should treat it as a stable key, not parse it.

    ``archived`` is an adapter-populated flag (OpenSpec uses it for
    handles surfaced via ``list_features(include_archived=True)``).
    Spec-kit never sets it today; the default ``False`` keeps Phase 1
    positional construction sites working unchanged (019 FR-008, T042).
    """

    feature_id: str
    display_name: str
    root_path: Path
    adapter_name: str
    archived: bool = False


@dataclass
class NormalizedTask:
    """A single task row normalized across SDD formats.

    Spec-kit stores tasks as `- [x] T001 [US1] [@agent] description`
    lines in tasks.md. Other formats (Taskmaster graph, OpenSpec
    proposals) normalize to this same shape.
    """

    task_id: str
    text: str
    completed: bool
    assignee: str | None


@dataclass
class StageProgress:
    """One stage's progress in the feature's lifecycle.

    The list of stages is adapter-specific. For spec-kit, this is the
    nine-stage model (brainstorm through pr-review). For other formats,
    the stage names and ordering differ; callers should not assume
    spec-kit semantics.

    ``kind`` is the v1 stage-kind the adapter maps this stage to (spec,
    plan, tasks, implementation, review_spec, review_code, review_pr,
    ship). Every construction site sets it explicitly; there is no
    default. Additive per FR-003; adapters narrow via ``ordered_stage_kinds``.
    """

    stage: str
    status: str
    evidence_sources: list[str]
    notes: list[str]
    kind: str


@dataclass
class NormalizedReviewSpec:
    """Adapter-owned shape for spec-review evidence.

    Fields mirror the legacy ``flow_state.ReviewSpecEvidence`` dataclass
    but are defined in this module so adapters never have to import
    flow_state internals. ``SpecKitAdapter.to_feature_evidence`` is the
    single translation point back to ``flow_state.ReviewSpecEvidence``.
    """

    exists: bool = False
    verdict: str | None = None
    clarify_session: str | None = None
    stale_against_clarify: bool = False
    has_cross_pass: bool = False


@dataclass
class NormalizedReviewCode:
    """Adapter-owned shape for code-review evidence."""

    exists: bool = False
    verdict: str | None = None
    phases_found: list[str] = field(default_factory=list)
    has_self_passes: bool = False
    has_cross_passes: bool = False
    overall_complete: bool = False


@dataclass
class NormalizedReviewPr:
    """Adapter-owned shape for PR-review evidence."""

    exists: bool = False
    verdict: str | None = None
    has_retro_note: bool = False


@dataclass
class NormalizedReviewEvidence:
    """Adapter-owned container for a feature's three review-stage evidences.

    Mirrors ``flow_state.ReviewEvidence`` but lives in the adapter
    module. Phase 1.5 introduces this type so Phase 2 adapters (OpenSpec,
    BMAD, Taskmaster) can populate review evidence without reaching into
    ``flow_state`` internals. ``SpecKitAdapter.to_feature_evidence``
    translates instances back into the legacy flow_state types at the
    adapter boundary.
    """

    review_spec: NormalizedReviewSpec = field(default_factory=NormalizedReviewSpec)
    review_code: NormalizedReviewCode = field(default_factory=NormalizedReviewCode)
    review_pr: NormalizedReviewPr = field(default_factory=NormalizedReviewPr)


@dataclass
class NormalizedWorktreeLane:
    """Adapter-owned shape for a worktree lane record.

    Mirrors ``flow_state.WorktreeLane``. Adapters populate this type
    directly; ``to_feature_evidence`` translates into the legacy
    ``flow_state.WorktreeLane`` at the boundary.
    """

    lane_id: str
    branch: str | None
    status: str | None
    path: str | None
    task_scope: list[str] = field(default_factory=list)


@dataclass
class NormalizedArtifacts:
    """Adapter-independent view of a feature's durable artifacts.

    This is the shape `flow_state.FeatureEvidence` gets built from.
    Phase 1.5 tightens ``review_evidence`` and ``worktree_lanes`` to
    adapter-owned types (``NormalizedReviewEvidence`` and
    ``NormalizedWorktreeLane``) so a second adapter never has to import
    ``flow_state`` to populate them. Translation back to the legacy
    flow_state dataclasses happens in
    ``SpecKitAdapter.to_feature_evidence``.

    `filenames` maps adapter-agnostic semantic keys (e.g. ``"spec"``,
    ``"tasks"``, ``"review-code"``) to the display/path filename the
    adapter uses for that artifact. Callers that need to render a
    filename in operator guidance or build a path under ``feature_dir``
    should resolve through this map instead of hardcoding spec-kit
    literals, so a future non-spec-kit adapter can supply different
    filenames without touching flow-state code.
    """

    feature_id: str
    feature_dir: Path
    artifacts: dict[str, Path]
    tasks: list[NormalizedTask]
    task_summary_data: dict[str, Any]
    review_evidence: NormalizedReviewEvidence
    linked_brainstorms: list[Path]
    worktree_lanes: list[NormalizedWorktreeLane]
    filenames: dict[str, str] = field(default_factory=dict)
    ambiguities: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class SddAdapter(ABC):
    """Abstract base class for an SDD format adapter.

    One subclass per SDD format. Orca subsystems that used to parse
    spec-kit directly now go through an adapter instance. See
    specs/016-multi-sdd-layer/ for the full contract.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier for this adapter (e.g. 'spec-kit')."""

    @abstractmethod
    def detect(self, repo_root: Path) -> bool:
        """Return True if this adapter recognizes the repo layout."""

    @abstractmethod
    def list_features(self, repo_root: Path) -> list[FeatureHandle]:
        """Return all features this adapter can see in the repo."""

    @abstractmethod
    def load_feature(self, handle: FeatureHandle) -> NormalizedArtifacts:
        """Load a feature's artifacts into the normalized shape."""

    @abstractmethod
    def compute_stage(
        self, artifacts: NormalizedArtifacts
    ) -> list[StageProgress]:
        """Compute per-stage progress from loaded artifacts."""

    @abstractmethod
    def id_for_path(
        self, path: Path, repo_root: Path | None = None
    ) -> str | None:
        """Map a file path to a feature_id if it lives under one.

        `repo_root` is optional: when provided, the adapter uses it as
        the anchor; when omitted, the adapter should walk the path's
        parents looking for a format-specific marker. Returns None if
        `path` is not inside any feature this adapter manages.
        """

    # 019 Sub-phase A: non-abstract defaults. Concrete adapters override
    # to return a native-order subset / their true capability matrix.

    def ordered_stage_kinds(self) -> list[str]:
        """Return this adapter's ordered view of the v1 stage-kind vocabulary.

        The default returns the canonical v1 eight-kind list per FR-001.
        Adapters override to narrow to a native subset in native order.
        """
        return [
            "spec",
            "plan",
            "tasks",
            "implementation",
            "review_spec",
            "review_code",
            "review_pr",
            "ship",
        ]

    def supports(self, capability: str) -> bool:
        """Report whether this adapter supports the named capability.

        The v1 vocabulary is ``{"lanes", "yolo", "review_code",
        "review_pr", "adoption"}`` (FR-002). Unknown capabilities always
        return ``False``. The default returns ``False`` for every string;
        concrete adapters override to declare their truth table.
        """
        return False
