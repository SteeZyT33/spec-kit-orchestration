from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
CLARIFY_SESSION_RE = re.compile(r"^### Session (\d{4}-\d{2}-\d{2})\b", re.MULTILINE)
TASK_LINE_RE = re.compile(r"^- \[(?P<mark>[ xX])\] (?P<task>T\d+)\b(?P<body>.*)$")
ASSIGNMENT_RE = re.compile(r"\[@[^\]]+\]")
HEADING_RE = re.compile(r"^#{1,6}\s+(?P<title>.+?)\s*$")


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
class FeatureEvidence:
    feature_id: str
    feature_dir: Path
    repo_root: Path | None
    artifacts: dict[str, Path]
    task_summary: TaskSummary
    review_evidence: ReviewEvidence
    linked_brainstorms: list[Path]
    worktree_lanes: list[WorktreeLane]
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


def _read_text_if_exists(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _find_repo_root(feature_dir: Path, repo_root: Path | None = None) -> Path | None:
    if repo_root is not None:
        return repo_root.resolve()

    for candidate in (feature_dir, *feature_dir.parents):
        if (candidate / ".git").exists() or (candidate / ".specify").exists():
            return candidate.resolve()
    return None


def _slugify_heading(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _parse_tasks(path: Path) -> TaskSummary:
    summary = TaskSummary()
    text = _read_text_if_exists(path)
    if not text:
        return summary

    for line in text.splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            summary.headings.append(_slugify_heading(heading.group("title")))
            continue

        match = TASK_LINE_RE.match(line)
        if not match:
            continue

        summary.total += 1
        if match.group("mark").strip():
            summary.completed += 1
        else:
            summary.incomplete += 1
        if ASSIGNMENT_RE.search(match.group("body")):
            summary.assigned += 1
    return summary


def _extract_verdict(text: str) -> str | None:
    match = re.search(r"^- status:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def _latest_clarify_session(spec_text: str) -> str | None:
    clarifications_match = re.search(
        r"^## Clarifications\b(.*?)(?=^## |\Z)",
        spec_text,
        re.MULTILINE | re.DOTALL,
    )
    if not clarifications_match:
        return None
    sessions = CLARIFY_SESSION_RE.findall(clarifications_match.group(1))
    return max(sessions) if sessions else None


def _parse_review_spec_evidence(review_spec_path: Path, spec_path: Path) -> ReviewSpecEvidence:
    ev = ReviewSpecEvidence()
    text = _read_text_if_exists(review_spec_path)
    if not text:
        return ev
    ev.exists = True
    ev.verdict = _extract_verdict(text)
    ev.has_cross_pass = bool(re.search(r"^## Cross Pass \(", text, re.MULTILINE))

    prereq_match = re.search(r"^- Clarify session:\s*(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
    if prereq_match:
        ev.clarify_session = prereq_match.group(1)

    spec_text = _read_text_if_exists(spec_path)
    latest_session = _latest_clarify_session(spec_text)
    if ev.clarify_session and latest_session and latest_session > ev.clarify_session:
        ev.stale_against_clarify = True

    return ev


def _parse_review_code_evidence(review_code_path: Path) -> ReviewCodeEvidence:
    ev = ReviewCodeEvidence()
    text = _read_text_if_exists(review_code_path)
    if not text:
        return ev
    ev.exists = True
    ev.verdict = _extract_verdict(text)

    self_pass_re = re.compile(r"^## (.+?) Self Pass \(", re.MULTILINE)
    cross_pass_re = re.compile(r"^## (.+?) Cross Pass \(", re.MULTILINE)

    self_phases = {m.group(1) for m in self_pass_re.finditer(text)}
    cross_phases = {m.group(1) for m in cross_pass_re.finditer(text)}
    ev.phases_found = sorted(self_phases | cross_phases)
    ev.has_self_passes = bool(self_phases)
    ev.has_cross_passes = bool(cross_phases)
    ev.overall_complete = "## Overall Verdict" in text
    return ev


def _parse_review_pr_evidence(review_pr_path: Path) -> ReviewPrEvidence:
    ev = ReviewPrEvidence()
    text = _read_text_if_exists(review_pr_path)
    if not text:
        return ev
    ev.exists = True
    ev.verdict = _extract_verdict(text)
    ev.has_retro_note = "## Retro Note" in text
    return ev


def _parse_review_evidence(feature_path: Path) -> ReviewEvidence:
    return ReviewEvidence(
        review_spec=_parse_review_spec_evidence(
            feature_path / "review-spec.md",
            feature_path / "spec.md",
        ),
        review_code=_parse_review_code_evidence(feature_path / "review-code.md"),
        review_pr=_parse_review_pr_evidence(feature_path / "review-pr.md"),
    )


def _find_linked_brainstorms(repo_root: Path | None, feature_id: str) -> list[Path]:
    if repo_root is None:
        return []

    brainstorm_dir = repo_root / "brainstorm"
    if not brainstorm_dir.is_dir():
        return []

    matches: list[Path] = []
    feature_ref = f"specs/{feature_id}/"
    for path in sorted(brainstorm_dir.glob("*.md")):
        text = _read_text_if_exists(path)
        if feature_id in text or feature_ref in text:
            matches.append(path)
    return matches


def _load_worktree_lanes(repo_root: Path | None, feature_id: str) -> list[WorktreeLane]:
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

    lanes: list[WorktreeLane] = []
    for lane_id in lane_ids:
        lane_path = worktree_root / f"{lane_id}.json"
        if not lane_path.exists():
            continue
        try:
            lane = json.loads(lane_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue

        if lane.get("feature") != feature_id and lane.get("id") != feature_id:
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


def collect_feature_evidence(feature_dir: Path | str, repo_root: Path | str | None = None) -> FeatureEvidence:
    feature_path = Path(feature_dir).resolve()
    repo_path = _find_repo_root(feature_path, Path(repo_root).resolve() if repo_root else None)
    feature_id = feature_path.name

    artifacts = {
        name: feature_path / name
        for name in ("brainstorm.md", "spec.md", "plan.md", "tasks.md", "review-spec.md", "review-code.md", "review-pr.md")
    }

    task_summary = _parse_tasks(artifacts["tasks.md"])
    review_evidence = _parse_review_evidence(feature_path)
    linked_brainstorms = _find_linked_brainstorms(repo_path, feature_id)
    worktree_lanes = _load_worktree_lanes(repo_path, feature_id)

    evidence = FeatureEvidence(
        feature_id=feature_id,
        feature_dir=feature_path,
        repo_root=repo_path,
        artifacts=artifacts,
        task_summary=task_summary,
        review_evidence=review_evidence,
        linked_brainstorms=linked_brainstorms,
        worktree_lanes=worktree_lanes,
    )

    if review_evidence.review_code.exists and not artifacts["tasks.md"].exists():
        evidence.ambiguities.append("review-code.md exists without tasks.md")
    if review_evidence.review_spec.stale_against_clarify:
        evidence.ambiguities.append("review-spec.md is stale — clarify ran again after the review")

    if worktree_lanes:
        lane_descriptions = []
        for lane in worktree_lanes:
            status = lane.status or "unknown"
            branch = lane.branch or lane.lane_id
            lane_descriptions.append(f"{lane.lane_id} ({status}, {branch})")
        evidence.notes.append(
            "Worktree context available: " + ", ".join(lane_descriptions)
        )

    if linked_brainstorms:
        evidence.notes.append(
            "Linked brainstorm memory found: "
            + ", ".join(str(path.relative_to(repo_path)) if repo_path else path.name for path in linked_brainstorms)
        )

    return evidence


def _review_milestones(evidence: FeatureEvidence) -> list[ReviewMilestone]:
    rev = evidence.review_evidence
    milestones: list[ReviewMilestone] = []

    # review-spec
    if not rev.review_spec.exists:
        milestones.append(ReviewMilestone("review-spec", "missing"))
    elif rev.review_spec.stale_against_clarify:
        milestones.append(ReviewMilestone("review-spec", "stale",
                          notes=["review-spec.md is stale against a newer clarify session"]))
    elif rev.review_spec.verdict == "ready" and rev.review_spec.has_cross_pass:
        milestones.append(ReviewMilestone("review-spec", "present",
                          evidence_sources=[str(evidence.feature_dir / "review-spec.md")]))
    elif rev.review_spec.verdict == "needs-revision":
        milestones.append(ReviewMilestone("review-spec", "needs-revision"))
    elif rev.review_spec.verdict == "blocked":
        milestones.append(ReviewMilestone("review-spec", "blocked"))
    else:
        milestones.append(ReviewMilestone("review-spec", "invalid",
                          notes=["review-spec.md exists but has no recognized verdict"]))

    # review-code
    if not rev.review_code.exists:
        milestones.append(ReviewMilestone("review-code", "not_started"))
    elif (
        rev.review_code.overall_complete
        and rev.review_code.verdict in REVIEW_CODE_VERDICT_VALUES
        and rev.review_code.has_self_passes
        and rev.review_code.has_cross_passes
    ):
        milestones.append(ReviewMilestone("review-code", "overall_complete",
                          evidence_sources=[str(evidence.feature_dir / "review-code.md")]))
    elif rev.review_code.phases_found:
        milestones.append(ReviewMilestone("review-code", "phases_partial",
                          notes=[f"Phases found: {', '.join(rev.review_code.phases_found)}"]))
    else:
        milestones.append(ReviewMilestone("review-code", "invalid",
                          notes=["review-code.md exists but has no recognized phase structure"]))

    # review-pr
    if not rev.review_pr.exists:
        milestones.append(ReviewMilestone("review-pr", "not_started"))
    elif rev.review_pr.verdict == "merged" and rev.review_pr.has_retro_note:
        milestones.append(ReviewMilestone("review-pr", "complete",
                          evidence_sources=[str(evidence.feature_dir / "review-pr.md")]))
    elif rev.review_pr.verdict == "pending-merge" and rev.review_pr.has_retro_note:
        milestones.append(ReviewMilestone("review-pr", "in_progress"))
    elif rev.review_pr.verdict == "reverted":
        milestones.append(ReviewMilestone("review-pr", "reverted"))
    else:
        milestones.append(ReviewMilestone("review-pr", "invalid",
                          notes=["review-pr.md exists but has no recognized verdict"]))

    return milestones


def _stage_milestones(evidence: FeatureEvidence, reviews: list[ReviewMilestone]) -> list[FlowMilestone]:
    review_map = {item.review_type: item for item in reviews}
    tasks_path = evidence.artifacts["tasks.md"]
    milestones: list[FlowMilestone] = []

    brainstorm_sources = [str(evidence.artifacts["brainstorm.md"])] if evidence.artifacts["brainstorm.md"].exists() else []
    brainstorm_sources.extend(str(path) for path in evidence.linked_brainstorms)
    milestones.append(
        FlowMilestone(
            stage="brainstorm",
            status="complete" if brainstorm_sources else "incomplete",
            evidence_sources=brainstorm_sources,
        )
    )

    milestones.append(
        FlowMilestone(
            stage="specify",
            status="complete" if evidence.artifacts["spec.md"].exists() else "incomplete",
            evidence_sources=[str(evidence.artifacts["spec.md"])] if evidence.artifacts["spec.md"].exists() else [],
        )
    )
    milestones.append(
        FlowMilestone(
            stage="plan",
            status="complete" if evidence.artifacts["plan.md"].exists() else "incomplete",
            evidence_sources=[str(evidence.artifacts["plan.md"])] if evidence.artifacts["plan.md"].exists() else [],
        )
    )
    milestones.append(
        FlowMilestone(
            stage="tasks",
            status="complete" if tasks_path.exists() else "incomplete",
            evidence_sources=[str(tasks_path)] if tasks_path.exists() else [],
        )
    )

    assign_status = "incomplete"
    assign_sources: list[str] = []
    if tasks_path.exists() and evidence.task_summary.assigned > 0:
        assign_status = "complete"
        assign_sources.append(str(tasks_path))
    milestones.append(FlowMilestone("assign", assign_status, assign_sources))

    implement_status = "incomplete"
    implement_sources: list[str] = []
    if evidence.task_summary.has_implementation_progress:
        implement_status = "complete"
        implement_sources.append(str(tasks_path))
    elif evidence.review_evidence.review_code.exists:
        implement_status = "complete"
        implement_sources.append(str(evidence.feature_dir / "review-code.md"))
    milestones.append(FlowMilestone("implement", implement_status, implement_sources))

    for review_name in REVIEW_ARTIFACT_NAMES:
        rm = review_map[review_name]
        milestones.append(
            FlowMilestone(
                review_name,
                rm.status,
                list(rm.evidence_sources),
                list(rm.notes),
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


def _has_material_conflict(ambiguities: list[str]) -> bool:
    conflict_markers = (
        "without specification evidence",
        "without planning evidence",
        "without task breakdown evidence",
        "review-code.md exists without tasks.md",
    )
    return any(any(marker in ambiguity for marker in conflict_markers) for ambiguity in ambiguities)


def _next_step(milestones: list[FlowMilestone], ambiguities: list[str], evidence: FeatureEvidence) -> str | None:
    if len(ambiguities) >= 3:
        return None

    status_map = {item.stage: item.status for item in milestones}

    if status_map["specify"] != "complete":
        return "Create or refine spec.md before advancing the feature."
    if status_map["plan"] != "complete":
        return "Generate plan.md to lock architecture and implementation shape."
    if status_map["tasks"] != "complete":
        return "Generate tasks.md so implementation can proceed from a durable task plan."
    if status_map["assign"] != "complete" and status_map["implement"] != "complete":
        return "Run /speckit.orca.assign if this feature needs multi-agent coordination, or proceed directly to implementation."
    if status_map["implement"] != "complete":
        return "Implement the next incomplete task and keep tasks.md current."
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
_SPEC_LITE_HEADER_RE = re.compile(r"^# Spec-Lite SL-\d{3}(?::.*)?$")

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
    if _has_material_conflict(ambiguities):
        current_stage = None
    next_step = _next_step(milestones, ambiguities, evidence)
    result = FlowStateResult(
        feature_id=evidence.feature_id,
        current_stage=current_stage,
        completed_milestones=[item for item in milestones if item.status == "complete"],
        incomplete_milestones=[item for item in milestones if item.status != "complete"],
        review_milestones=reviews,
        ambiguities=ambiguities,
        next_step=next_step,
        evidence_summary=_evidence_summary(evidence, milestones, reviews),
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
