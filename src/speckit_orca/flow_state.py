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
    "code-review",
    "cross-review",
    "pr-review",
    "self-review",
]

STAGE_KIND = {
    "brainstorm": "meta",
    "specify": "build",
    "plan": "build",
    "tasks": "build",
    "assign": "meta",
    "implement": "build",
    "code-review": "review",
    "cross-review": "review",
    "pr-review": "review",
    "self-review": "review",
}

REVIEW_TYPES = ("spec", "plan", "code", "cross", "pr", "self")
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
class ReviewEvidence:
    headings: list[str] = field(default_factory=list)
    scope_design: bool = False
    scope_code: bool = False
    has_review_file: bool = False
    has_self_review_file: bool = False
    is_late_stage: bool = False


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


def _collect_markdown_headings(path: Path) -> list[str]:
    headings: list[str] = []
    for line in _read_text_if_exists(path).splitlines():
        match = HEADING_RE.match(line)
        if match:
            headings.append(_slugify_heading(match.group("title")))
    return headings


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


def _parse_review_evidence(review_path: Path, self_review_path: Path) -> ReviewEvidence:
    review_text = _read_text_if_exists(review_path)
    headings = _collect_markdown_headings(review_path)
    if self_review_path.exists():
        headings.extend(_collect_markdown_headings(self_review_path))

    lowered = review_text.lower()
    is_late_stage = (
        "requested scope**: code" in lowered
        or (("effective review input" in lowered) and ("code" in lowered))
        or "code review" in lowered
        or "cross-harness review" in lowered
        or "cross-review" in lowered
        or "pr-review" in lowered
        or "external comment responses" in lowered
    )
    return ReviewEvidence(
        headings=headings,
        scope_design=("requested scope**: design" in lowered)
        or (("effective review input" in lowered) and ("design" in lowered)),
        scope_code=("requested scope**: code" in lowered)
        or (("effective review input" in lowered) and ("code" in lowered)),
        has_review_file=review_path.exists(),
        has_self_review_file=self_review_path.exists(),
        is_late_stage=is_late_stage,
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
        for name in ("brainstorm.md", "spec.md", "plan.md", "tasks.md", "review.md", "self-review.md")
    }

    task_summary = _parse_tasks(artifacts["tasks.md"])
    review_evidence = _parse_review_evidence(artifacts["review.md"], artifacts["self-review.md"])
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

    if review_evidence.has_review_file and review_evidence.is_late_stage and not artifacts["tasks.md"].exists():
        evidence.ambiguities.append("review.md exists without tasks.md")
    if review_evidence.has_self_review_file and not artifacts["review.md"].exists():
        evidence.ambiguities.append("self-review.md exists without review.md")

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
    headings = set(evidence.review_evidence.headings)
    review_file = evidence.artifacts["review.md"]
    self_review_file = evidence.artifacts["self-review.md"]

    def review_status(review_type: str) -> ReviewMilestone:
        if review_type == "self":
            if self_review_file.exists():
                return ReviewMilestone("self", "complete", [str(self_review_file)])
            return ReviewMilestone("self", "incomplete", [])

        if not review_file.exists():
            return ReviewMilestone(review_type, "incomplete", [])

        heading_map = {
            "spec": {"spec-review", "review-spec", "spec-review-findings"},
            "plan": {"plan-review", "review-plan", "design-review"},
            "code": {"code-review", "review-code"},
            "cross": {"cross-harness-review", "cross-review"},
            "pr": {"pr-review", "external-comment-responses"},
        }

        def has_heading_prefix(candidates: set[str]) -> bool:
            return any(
                heading == candidate or heading.startswith(f"{candidate}-")
                for heading in headings
                for candidate in candidates
            )

        status = "incomplete"
        notes: list[str] = []
        if review_type == "code" and evidence.review_evidence.scope_code:
            status = "complete"
        elif review_type == "spec" and evidence.review_evidence.scope_design and "spec-review" in headings:
            status = "complete"
        elif review_type == "plan" and evidence.review_evidence.scope_design and (
            "plan-review" in headings or "design-review" in headings
        ):
            status = "complete"
        elif has_heading_prefix(heading_map[review_type]):
            status = "complete"
        elif review_type in {"spec", "plan"} and evidence.review_evidence.scope_design:
            status = "unknown"
            notes.append("Design review exists but the review artifact does not split spec and plan explicitly.")

        return ReviewMilestone(review_type, status, [str(review_file)] if status != "incomplete" else [], notes)

    return [review_status(review_type) for review_type in REVIEW_TYPES]


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
    elif any(review.status == "complete" for review in reviews if review.review_type in {"code", "cross", "pr", "self"}):
        implement_status = "complete"
        for review in reviews:
            if review.review_type in {"code", "cross", "pr", "self"} and review.status == "complete":
                implement_sources.extend(review.evidence_sources)
                break
    milestones.append(FlowMilestone("implement", implement_status, implement_sources))

    milestones.append(
        FlowMilestone(
            "code-review",
            review_map["code"].status if review_map["code"].status != "unknown" else "incomplete",
            list(review_map["code"].evidence_sources),
            list(review_map["code"].notes),
        )
    )
    milestones.append(
        FlowMilestone(
            "cross-review",
            review_map["cross"].status if review_map["cross"].status != "unknown" else "incomplete",
            list(review_map["cross"].evidence_sources),
            list(review_map["cross"].notes),
        )
    )
    milestones.append(
        FlowMilestone(
            "pr-review",
            review_map["pr"].status if review_map["pr"].status != "unknown" else "incomplete",
            list(review_map["pr"].evidence_sources),
            list(review_map["pr"].notes),
        )
    )
    milestones.append(
        FlowMilestone(
            "self-review",
            review_map["self"].status if review_map["self"].status != "unknown" else "incomplete",
            list(review_map["self"].evidence_sources),
            list(review_map["self"].notes),
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
    if stage_status["cross-review"] == "complete" and stage_status["implement"] != "complete":
        ambiguities.append("Cross-review evidence exists before implementation evidence is complete.")
    if stage_status["pr-review"] == "complete" and stage_status["cross-review"] != "complete":
        ambiguities.append("PR-review evidence exists without cross-review evidence.")
    if stage_status["self-review"] == "complete" and stage_status["code-review"] != "complete":
        ambiguities.append("Self-review exists without a completed code-review milestone.")

    for review in reviews:
        if review.status == "unknown":
            ambiguities.extend(review.notes)

    return ambiguities


def _completed_stage(milestones: list[FlowMilestone]) -> str | None:
    completed = [item.stage for item in milestones if item.status == "complete"]
    if not completed:
        return None
    return max(completed, key=STAGE_ORDER.index)


def _has_material_conflict(ambiguities: list[str]) -> bool:
    conflict_markers = (
        "without specification evidence",
        "without planning evidence",
        "without task breakdown evidence",
        "before implementation evidence is complete",
        "without cross-review evidence",
        "without a completed code-review milestone",
        "review.md exists without tasks.md",
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
    if status_map["code-review"] != "complete":
        return "Run /speckit.orca.code-review on the implemented work."
    if status_map["cross-review"] != "complete":
        return "Run /speckit.orca.cross-review for an external adversarial pass."
    if status_map["pr-review"] != "complete":
        return "Run /speckit.orca.pr-review to handle PR creation and external comments."
    if status_map["self-review"] != "complete":
        return "Run /speckit.orca.self-review to capture process improvements."
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

    completed_review_types = [item.review_type for item in reviews if item.status == "complete"]
    if completed_review_types:
        summary.append("Completed reviews: " + ", ".join(completed_review_types))

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
    parser.add_argument("feature_dir", help="Path to the feature directory, for example specs/005-orca-flow-state")
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
    result = compute_flow_state(
        args.feature_dir,
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
