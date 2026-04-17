"""SDD Adapter interface for 016 multi-SDD-layer Phase 1.

Defines the adapter contract and normalized data shapes that let Orca
operate over multiple Spec-Driven Development repo formats. Phase 1
adds the interface and a spec-kit reference adapter without changing
any user-visible behavior.

Contracts:
  - SddAdapter: abstract base class. One adapter per SDD format.
  - FeatureHandle: opaque reference to a feature owned by an adapter.
  - NormalizedArtifacts: adapter-independent view of a feature's
    durable artifacts.
  - NormalizedTask: single task entry from the feature's task list.
  - StageProgress: one stage-row in the feature's progress model.
  - SpecKitAdapter: concrete adapter for spec-kit repos (Phase B).

Later phases add concrete adapters (OpenSpec, BMAD, Taskmaster).
"""

from __future__ import annotations

import json
import re
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
    """

    feature_id: str
    display_name: str
    root_path: Path
    adapter_name: str


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
    """

    stage: str
    status: str
    evidence_sources: list[str]
    notes: list[str]


@dataclass
class NormalizedArtifacts:
    """Adapter-independent view of a feature's durable artifacts.

    This is the shape `flow_state.FeatureEvidence` gets built from in
    Phase 1. Phase 1 keeps `review_evidence` typed as `Any` so adapters
    can return the existing spec-kit ReviewEvidence object without
    forcing an immediate shape change. Later phases can tighten the
    type as the refactor stabilizes.

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
    review_evidence: Any
    linked_brainstorms: list[Path]
    worktree_lanes: list[Any]
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


# ---------------------------------------------------------------------------
# SpecKitAdapter — concrete Phase B implementation.
# ---------------------------------------------------------------------------
# Module-level spec-kit constants. Phase C makes this module the sole home
# of spec-kit artifact filename literals; `flow_state.py` imports the named
# constants below and never encodes the raw "*.md" filenames itself. The
# T030 anti-leak test enforces that invariant.
SPEC_KIT_BRAINSTORM_FILENAME: str = "brainstorm.md"
SPEC_KIT_SPEC_FILENAME: str = "spec.md"
SPEC_KIT_PLAN_FILENAME: str = "plan.md"
SPEC_KIT_TASKS_FILENAME: str = "tasks.md"
SPEC_KIT_REVIEW_SPEC_FILENAME: str = "review-spec.md"
SPEC_KIT_REVIEW_CODE_FILENAME: str = "review-code.md"
SPEC_KIT_REVIEW_PR_FILENAME: str = "review-pr.md"

_SPEC_KIT_ARTIFACT_NAMES: tuple[str, ...] = (
    SPEC_KIT_BRAINSTORM_FILENAME,
    SPEC_KIT_SPEC_FILENAME,
    SPEC_KIT_PLAN_FILENAME,
    SPEC_KIT_TASKS_FILENAME,
    SPEC_KIT_REVIEW_SPEC_FILENAME,
    SPEC_KIT_REVIEW_CODE_FILENAME,
    SPEC_KIT_REVIEW_PR_FILENAME,
)

# Adapter-agnostic semantic keys used across NormalizedArtifacts.filenames
# and FeatureEvidence.filenames. flow_state looks up artifacts through
# these keys so it never encodes spec-kit-specific filenames. New
# adapters (OpenSpec, BMAD, Taskmaster) must supply the same key set with
# their own filename values.
_SPEC_KIT_FILENAMES: dict[str, str] = {
    "brainstorm": SPEC_KIT_BRAINSTORM_FILENAME,
    "spec": SPEC_KIT_SPEC_FILENAME,
    "plan": SPEC_KIT_PLAN_FILENAME,
    "tasks": SPEC_KIT_TASKS_FILENAME,
    "review-spec": SPEC_KIT_REVIEW_SPEC_FILENAME,
    "review-code": SPEC_KIT_REVIEW_CODE_FILENAME,
    "review-pr": SPEC_KIT_REVIEW_PR_FILENAME,
}

_SPEC_KIT_TASK_LINE_RE = re.compile(
    r"^- \[(?P<mark>[ xX])\] (?P<task>T\d+)\b(?P<body>.*)$"
)
_SPEC_KIT_ASSIGNMENT_RE = re.compile(r"\[@([^\]]+)\]")
_SPEC_KIT_HEADING_RE = re.compile(r"^#{1,6}\s+(?P<title>.+?)\s*$")
_SPEC_KIT_CLARIFY_SESSION_RE = re.compile(
    r"^### Session (\d{4}-\d{2}-\d{2})\b", re.MULTILINE
)


def _sk_read_text_if_exists(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _sk_slugify_heading(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


class SpecKitAdapter(SddAdapter):
    """Concrete adapter for spec-kit repos.

    Owns all spec-kit-flavored parsing: artifact filename list, task line
    regex, assignment regex, review-verdict/cross-pass/self-pass detection,
    brainstorm link resolution, worktree lane loading, and the nine-stage
    model.

    During Phase B, `flow_state.py` still contains parallel helpers. Phase
    C deletes them and rewires `collect_feature_evidence` through this
    adapter. Phase B's only job is to land the adapter with a passing
    parity gate against the legacy code path.
    """

    @property
    def name(self) -> str:
        return "spec-kit"

    # -- Detection & enumeration -------------------------------------------

    def detect(self, repo_root: Path) -> bool:
        specs_root = Path(repo_root) / "specs"
        if not specs_root.is_dir():
            return False
        # A spec-kit repo has at least one specs/<feature>/spec.md.
        for child in specs_root.iterdir():
            if child.is_dir() and (child / "spec.md").is_file():
                return True
        return False

    def list_features(self, repo_root: Path) -> list[FeatureHandle]:
        specs_root = Path(repo_root) / "specs"
        if not specs_root.is_dir():
            return []
        handles: list[FeatureHandle] = []
        for child in sorted(specs_root.iterdir()):
            if not child.is_dir():
                continue
            if not (child / SPEC_KIT_SPEC_FILENAME).is_file():
                # Skip helper directories under specs/ that are not real
                # feature dirs (they lack the canonical spec.md anchor).
                continue
            handles.append(
                FeatureHandle(
                    feature_id=child.name,
                    display_name=child.name,
                    root_path=child.resolve(),
                    adapter_name=self.name,
                )
            )
        return handles

    # -- Feature loading ---------------------------------------------------

    def load_feature(
        self,
        handle: FeatureHandle,
        repo_root: Path | None = None,
    ) -> NormalizedArtifacts:
        feature_path = Path(handle.root_path).resolve()
        repo_path = self._find_repo_root(
            feature_path, Path(repo_root).resolve() if repo_root else None
        )

        artifacts = {
            name: feature_path / name for name in _SPEC_KIT_ARTIFACT_NAMES
        }

        tasks, task_summary_data = self._parse_tasks(artifacts["tasks.md"])
        review_evidence = self._parse_review_evidence(feature_path)
        linked_brainstorms = self._find_linked_brainstorms(
            repo_path, handle.feature_id
        )
        worktree_lanes = self._load_worktree_lanes(repo_path, handle.feature_id)

        ambiguities: list[str] = []
        notes: list[str] = []

        if review_evidence.review_code.exists and not artifacts["tasks.md"].exists():
            ambiguities.append("review-code.md exists without tasks.md")
        if review_evidence.review_spec.stale_against_clarify:
            ambiguities.append(
                "review-spec.md is stale — clarify ran again after the review"
            )

        if worktree_lanes:
            lane_descriptions = []
            for lane in worktree_lanes:
                status = lane.status or "unknown"
                branch = lane.branch or lane.lane_id
                lane_descriptions.append(
                    f"{lane.lane_id} ({status}, {branch})"
                )
            notes.append(
                "Worktree context available: " + ", ".join(lane_descriptions)
            )

        if linked_brainstorms:
            notes.append(
                "Linked brainstorm memory found: "
                + ", ".join(
                    str(path.relative_to(repo_path))
                    if repo_path
                    else path.name
                    for path in linked_brainstorms
                )
            )

        return NormalizedArtifacts(
            feature_id=handle.feature_id,
            feature_dir=feature_path,
            artifacts=artifacts,
            filenames=dict(_SPEC_KIT_FILENAMES),
            tasks=tasks,
            task_summary_data=task_summary_data,
            review_evidence=review_evidence,
            linked_brainstorms=linked_brainstorms,
            worktree_lanes=worktree_lanes,
            ambiguities=ambiguities,
            notes=notes,
        )

    # -- Stage computation -------------------------------------------------

    def compute_stage(
        self, artifacts: NormalizedArtifacts
    ) -> list[StageProgress]:
        """Return spec-kit's nine-stage progress view for a feature.

        Status values match the legacy flow-state vocabulary so parity with
        `_stage_milestones` is preserved when Phase C rewires through here.
        """
        a = artifacts.artifacts
        rev = artifacts.review_evidence
        task_summary = artifacts.task_summary_data
        feature_dir = artifacts.feature_dir

        progress: list[StageProgress] = []

        # brainstorm
        brainstorm_sources: list[str] = []
        if a["brainstorm.md"].exists():
            brainstorm_sources.append(str(a["brainstorm.md"]))
        brainstorm_sources.extend(
            str(p) for p in artifacts.linked_brainstorms
        )
        progress.append(
            StageProgress(
                stage="brainstorm",
                status="complete" if brainstorm_sources else "incomplete",
                evidence_sources=brainstorm_sources,
                notes=[],
            )
        )

        # specify
        progress.append(
            StageProgress(
                stage="specify",
                status="complete" if a["spec.md"].exists() else "incomplete",
                evidence_sources=[str(a["spec.md"])]
                if a["spec.md"].exists()
                else [],
                notes=[],
            )
        )
        # plan
        progress.append(
            StageProgress(
                stage="plan",
                status="complete" if a["plan.md"].exists() else "incomplete",
                evidence_sources=[str(a["plan.md"])]
                if a["plan.md"].exists()
                else [],
                notes=[],
            )
        )
        # tasks
        tasks_path = a["tasks.md"]
        progress.append(
            StageProgress(
                stage="tasks",
                status="complete" if tasks_path.exists() else "incomplete",
                evidence_sources=[str(tasks_path)]
                if tasks_path.exists()
                else [],
                notes=[],
            )
        )

        # assign
        assign_status = "incomplete"
        assign_sources: list[str] = []
        if tasks_path.exists() and task_summary.get("assigned", 0) > 0:
            assign_status = "complete"
            assign_sources.append(str(tasks_path))
        progress.append(
            StageProgress(
                stage="assign",
                status=assign_status,
                evidence_sources=assign_sources,
                notes=[],
            )
        )

        # implement
        implement_status = "incomplete"
        implement_sources: list[str] = []
        if task_summary.get("completed", 0) > 0:
            implement_status = "complete"
            implement_sources.append(str(tasks_path))
        elif rev.review_code.exists:
            implement_status = "complete"
            implement_sources.append(str(feature_dir / "review-code.md"))
        progress.append(
            StageProgress(
                stage="implement",
                status=implement_status,
                evidence_sources=implement_sources,
                notes=[],
            )
        )

        # review-spec
        rs_status = self._review_spec_status(rev.review_spec)
        progress.append(
            StageProgress(
                stage="review-spec",
                status=rs_status,
                evidence_sources=[str(feature_dir / "review-spec.md")]
                if rev.review_spec.exists
                else [],
                notes=[],
            )
        )
        # review-code
        rc_status = self._review_code_status(rev.review_code)
        rc_sources: list[str] = []
        if rev.review_code.exists:
            rc_sources.append(str(feature_dir / "review-code.md"))
        progress.append(
            StageProgress(
                stage="review-code",
                status=rc_status,
                evidence_sources=rc_sources,
                notes=[],
            )
        )
        # review-pr
        rp_status = self._review_pr_status(rev.review_pr)
        rp_sources: list[str] = []
        if rev.review_pr.exists:
            rp_sources.append(str(feature_dir / "review-pr.md"))
        progress.append(
            StageProgress(
                stage="review-pr",
                status=rp_status,
                evidence_sources=rp_sources,
                notes=[],
            )
        )

        return progress

    @staticmethod
    def _review_spec_status(ev: Any) -> str:
        if not ev.exists:
            return "missing"
        if ev.stale_against_clarify:
            return "stale"
        if ev.verdict == "ready" and ev.has_cross_pass:
            return "present"
        if ev.verdict == "needs-revision":
            return "needs-revision"
        if ev.verdict == "blocked":
            return "blocked"
        return "invalid"

    @staticmethod
    def _review_code_status(ev: Any) -> str:
        if not ev.exists:
            return "not_started"
        from .flow_state import REVIEW_CODE_VERDICT_VALUES  # reuse the set

        if (
            ev.overall_complete
            and ev.verdict in REVIEW_CODE_VERDICT_VALUES
            and ev.has_self_passes
            and ev.has_cross_passes
        ):
            return "overall_complete"
        if ev.phases_found:
            return "phases_partial"
        return "invalid"

    @staticmethod
    def _review_pr_status(ev: Any) -> str:
        if not ev.exists:
            return "not_started"
        if ev.verdict == "merged" and ev.has_retro_note:
            return "complete"
        if ev.verdict == "pending-merge" and ev.has_retro_note:
            return "in_progress"
        if ev.verdict == "reverted":
            return "reverted"
        return "invalid"

    # -- Path reverse lookup -----------------------------------------------

    def id_for_path(
        self, path: Path, repo_root: Path | None = None
    ) -> str | None:
        """Return the feature_id if `path` lives under `specs/<id>/...`.

        The repo_root argument is optional — when omitted the method walks
        parents looking for a `.git`/`.specify` anchor. This shape matches
        the plan's Design Decisions §1 signature while keeping the Phase A
        ABC's single-arg contract backwards-compatible.
        """
        resolved = Path(path).resolve()
        root = (
            Path(repo_root).resolve()
            if repo_root is not None
            else self._find_repo_root(resolved, None)
        )
        if root is None:
            return None
        specs_root = root / "specs"
        try:
            rel = resolved.relative_to(specs_root)
        except ValueError:
            return None
        parts = rel.parts
        if not parts:
            return None
        # Reject paths that live directly under specs/ but are not inside
        # a feature directory (e.g., specs/README.md).
        feature_root = specs_root / parts[0]
        if not feature_root.is_dir():
            return None
        return parts[0]

    # -- Internal parsing helpers (ported from flow_state.py) --------------

    @staticmethod
    def _find_repo_root(
        feature_dir: Path, repo_root: Path | None
    ) -> Path | None:
        if repo_root is not None:
            return repo_root.resolve()
        for candidate in (feature_dir, *feature_dir.parents):
            if (candidate / ".git").exists() or (candidate / ".specify").exists():
                return candidate.resolve()
        return None

    @staticmethod
    def _parse_tasks(path: Path) -> tuple[list[NormalizedTask], dict[str, Any]]:
        """Parse tasks.md into both NormalizedTask entries and the legacy
        task-summary dict shape (total/completed/incomplete/assigned/headings).
        """
        tasks: list[NormalizedTask] = []
        summary: dict[str, Any] = {
            "total": 0,
            "completed": 0,
            "incomplete": 0,
            "assigned": 0,
            "headings": [],
        }
        text = _sk_read_text_if_exists(path)
        if not text:
            return tasks, summary

        for line in text.splitlines():
            heading = _SPEC_KIT_HEADING_RE.match(line)
            if heading:
                summary["headings"].append(
                    _sk_slugify_heading(heading.group("title"))
                )
                continue

            match = _SPEC_KIT_TASK_LINE_RE.match(line)
            if not match:
                continue

            task_id = match.group("task")
            body = match.group("body")
            completed = bool(match.group("mark").strip())

            summary["total"] += 1
            if completed:
                summary["completed"] += 1
            else:
                summary["incomplete"] += 1

            assignee: str | None = None
            assign_match = _SPEC_KIT_ASSIGNMENT_RE.search(body)
            if assign_match:
                assignee = assign_match.group(1).strip()
                summary["assigned"] += 1

            tasks.append(
                NormalizedTask(
                    task_id=task_id,
                    text=body.strip(),
                    completed=completed,
                    assignee=assignee,
                )
            )
        return tasks, summary

    @staticmethod
    def _extract_verdict(text: str) -> str | None:
        match = re.search(r"^- status:\s*(.+)$", text, re.MULTILINE)
        return match.group(1).strip() if match else None

    @classmethod
    def _latest_clarify_session(cls, spec_text: str) -> str | None:
        clarifications_match = re.search(
            r"^## Clarifications\b(.*?)(?=^## |\Z)",
            spec_text,
            re.MULTILINE | re.DOTALL,
        )
        if not clarifications_match:
            return None
        sessions = _SPEC_KIT_CLARIFY_SESSION_RE.findall(
            clarifications_match.group(1)
        )
        return max(sessions) if sessions else None

    @classmethod
    def _parse_review_spec_evidence(
        cls, review_spec_path: Path, spec_path: Path
    ) -> Any:
        from .flow_state import ReviewSpecEvidence

        ev = ReviewSpecEvidence()
        text = _sk_read_text_if_exists(review_spec_path)
        if not text:
            return ev
        ev.exists = True
        ev.verdict = cls._extract_verdict(text)
        ev.has_cross_pass = bool(
            re.search(r"^## Cross Pass \(", text, re.MULTILINE)
        )

        prereq_match = re.search(
            r"^- Clarify session:\s*(\d{4}-\d{2}-\d{2})",
            text,
            re.MULTILINE,
        )
        if prereq_match:
            ev.clarify_session = prereq_match.group(1)

        spec_text = _sk_read_text_if_exists(spec_path)
        latest_session = cls._latest_clarify_session(spec_text)
        if (
            ev.clarify_session
            and latest_session
            and latest_session > ev.clarify_session
        ):
            ev.stale_against_clarify = True
        return ev

    @classmethod
    def _parse_review_code_evidence(cls, review_code_path: Path) -> Any:
        from .flow_state import ReviewCodeEvidence

        ev = ReviewCodeEvidence()
        text = _sk_read_text_if_exists(review_code_path)
        if not text:
            return ev
        ev.exists = True
        ev.verdict = cls._extract_verdict(text)

        self_pass_re = re.compile(r"^## (.+?) Self Pass \(", re.MULTILINE)
        cross_pass_re = re.compile(r"^## (.+?) Cross Pass \(", re.MULTILINE)
        self_phases = {m.group(1) for m in self_pass_re.finditer(text)}
        cross_phases = {m.group(1) for m in cross_pass_re.finditer(text)}
        ev.phases_found = sorted(self_phases | cross_phases)
        ev.has_self_passes = bool(self_phases)
        ev.has_cross_passes = bool(cross_phases)
        ev.overall_complete = "## Overall Verdict" in text
        return ev

    @classmethod
    def _parse_review_pr_evidence(cls, review_pr_path: Path) -> Any:
        from .flow_state import ReviewPrEvidence

        ev = ReviewPrEvidence()
        text = _sk_read_text_if_exists(review_pr_path)
        if not text:
            return ev
        ev.exists = True
        ev.verdict = cls._extract_verdict(text)
        ev.has_retro_note = "## Retro Note" in text
        return ev

    @classmethod
    def _parse_review_evidence(cls, feature_path: Path) -> Any:
        from .flow_state import ReviewEvidence

        return ReviewEvidence(
            review_spec=cls._parse_review_spec_evidence(
                feature_path / "review-spec.md",
                feature_path / "spec.md",
            ),
            review_code=cls._parse_review_code_evidence(
                feature_path / "review-code.md"
            ),
            review_pr=cls._parse_review_pr_evidence(
                feature_path / "review-pr.md"
            ),
        )

    @staticmethod
    def _find_linked_brainstorms(
        repo_root: Path | None, feature_id: str
    ) -> list[Path]:
        if repo_root is None:
            return []
        brainstorm_dir = repo_root / "brainstorm"
        if not brainstorm_dir.is_dir():
            return []
        matches: list[Path] = []
        feature_ref = f"specs/{feature_id}/"
        for path in sorted(brainstorm_dir.glob("*.md")):
            text = _sk_read_text_if_exists(path)
            if feature_id in text or feature_ref in text:
                matches.append(path)
        return matches

    @staticmethod
    def _load_worktree_lanes(
        repo_root: Path | None, feature_id: str
    ) -> list[Any]:
        from .flow_state import WorktreeLane

        if repo_root is None:
            return []

        worktree_root = repo_root / ".specify" / "orca" / "worktrees"
        registry_path = worktree_root / "registry.json"
        if not registry_path.exists():
            return []

        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        lane_ids = registry.get("lanes", [])
        if not isinstance(lane_ids, list):
            return []

        lanes: list[Any] = []
        for lane_id in lane_ids:
            lane_path = worktree_root / f"{lane_id}.json"
            if not lane_path.exists():
                continue
            try:
                lane = json.loads(lane_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue

            if (
                lane.get("feature") != feature_id
                and lane.get("id") != feature_id
            ):
                continue

            task_scope = lane.get("task_scope", [])
            lanes.append(
                WorktreeLane(
                    lane_id=lane.get("id", lane_id),
                    branch=lane.get("branch"),
                    status=lane.get("status"),
                    path=lane.get("path"),
                    task_scope=task_scope if isinstance(task_scope, list) else [],
                )
            )
        return lanes

    # -- Normalized -> FeatureEvidence bridge ------------------------------

    def to_feature_evidence(
        self,
        normalized: NormalizedArtifacts,
        repo_root: Path | None = None,
    ) -> Any:
        """Convert a NormalizedArtifacts into a legacy FeatureEvidence.

        Used by the T016 parity gate and, in Phase C, by
        `collect_feature_evidence` to keep downstream consumers untouched.
        """
        from .flow_state import FeatureEvidence, TaskSummary

        resolved_repo = (
            Path(repo_root).resolve()
            if repo_root is not None
            else self._find_repo_root(normalized.feature_dir, None)
        )

        ts_data = normalized.task_summary_data
        task_summary = TaskSummary(
            total=int(ts_data.get("total", 0)),
            completed=int(ts_data.get("completed", 0)),
            incomplete=int(ts_data.get("incomplete", 0)),
            assigned=int(ts_data.get("assigned", 0)),
            headings=list(ts_data.get("headings", [])),
        )

        return FeatureEvidence(
            feature_id=normalized.feature_id,
            feature_dir=normalized.feature_dir,
            repo_root=resolved_repo,
            artifacts=dict(normalized.artifacts),
            filenames=dict(normalized.filenames),
            task_summary=task_summary,
            review_evidence=normalized.review_evidence,
            linked_brainstorms=list(normalized.linked_brainstorms),
            worktree_lanes=list(normalized.worktree_lanes),
            ambiguities=list(normalized.ambiguities),
            notes=list(normalized.notes),
        )
