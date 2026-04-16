from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CANONICAL_STAGE_IDS = (
    # Full-spec pipeline stages (009 + 012 vocabulary is authoritative)
    "brainstorm",
    "specify",
    "clarify",          # 012 mandatory pre-review step (spec-kit /clarify)
    "review-spec",      # 012 cross-only adversarial spec review
    "plan",
    "tasks",
    "assign",
    "implement",
    "review-code",      # 012 self+cross code review per phase
    "pr-ready",         # 009 default terminal (branch ready for PR)
    "pr-create",        # 009 explicit opt-in PR creation
    "review-pr",        # 012 post-merge PR comment disposition + retro
    # Legacy 006-era names kept for backward compatibility — pre-012
    # handoff records on disk use these, so we still accept them.
    "self-review",
    "code-review",
    "cross-review",
    "pr-review",
)

TRANSITION_ORDER = (
    # 009 + 012 happy path
    ("brainstorm", "specify"),
    ("specify", "clarify"),
    ("clarify", "review-spec"),
    ("review-spec", "plan"),
    ("plan", "tasks"),
    ("tasks", "assign"),
    ("tasks", "implement"),
    ("assign", "implement"),
    ("implement", "review-code"),
    ("review-code", "pr-ready"),
    ("review-code", "pr-create"),
    ("pr-create", "review-pr"),
    # Legacy transitions (kept so old handoffs still parse)
    ("specify", "plan"),                # pre-012 skip of clarify/review-spec
    ("implement", "code-review"),       # pre-012
    ("cross-review", "pr-review"),      # pre-012
    ("code-review", "pr-review"),       # pre-012
)

TRANSITION_REQUIRED_INPUTS = {
    # 009 + 012 transitions
    ("brainstorm", "specify"): ("brainstorm.md",),
    ("specify", "clarify"): ("spec.md",),
    ("clarify", "review-spec"): ("spec.md",),
    ("review-spec", "plan"): ("spec.md", "review-spec.md"),
    ("plan", "tasks"): ("plan.md", "research.md", "data-model.md", "contracts"),
    ("tasks", "assign"): ("tasks.md",),
    ("tasks", "implement"): ("tasks.md",),
    ("assign", "implement"): ("tasks.md",),
    ("implement", "review-code"): ("tasks.md", "plan.md", "spec.md"),
    ("review-code", "pr-ready"): ("review-code.md", "review.md"),
    ("review-code", "pr-create"): ("review-code.md", "review.md"),
    ("pr-create", "review-pr"): ("review-code.md", "review.md"),
    # Legacy — required inputs for pre-012 transitions
    ("specify", "plan"): ("spec.md",),
    ("implement", "code-review"): ("tasks.md", "plan.md", "spec.md"),
    ("cross-review", "pr-review"): ("review-cross.md", "review.md"),
    ("code-review", "pr-review"): ("review-code.md", "review.md"),
}

TOP_LEVEL_KEYS = ("Source", "Target", "Branch", "Lane", "Created")
SECTION_TITLES = ("Summary", "Upstream Artifacts", "Open Questions")


@dataclass
class HandoffRecord:
    source_stage: str
    target_stage: str
    summary: str
    upstream_artifacts: list[str]
    open_questions: list[str]
    branch: str | None
    lane_id: str | None
    created_at: str
    storage_shape: str
    locator: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResolutionResult:
    target_stage: str
    resolved_source_stage: str | None
    resolved_handoff: str | None
    resolved_artifacts: list[str]
    resolution_reason: str
    used_branch_context: bool
    used_lane_context: bool
    winning_storage_shape: str
    ambiguity_detected: bool
    uniqueness_violation_detected: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_text(self) -> str:
        lines = [
            f"Target stage: {self.target_stage}",
            f"Resolved source stage: {self.resolved_source_stage or 'none'}",
            f"Resolved handoff: {self.resolved_handoff or 'none'}",
            f"Winning storage shape: {self.winning_storage_shape}",
            f"Used branch context: {'yes' if self.used_branch_context else 'no'}",
            f"Used lane context: {'yes' if self.used_lane_context else 'no'}",
            f"Ambiguity detected: {'yes' if self.ambiguity_detected else 'no'}",
            f"Uniqueness violation: {'yes' if self.uniqueness_violation_detected else 'no'}",
            "Resolved artifacts:",
        ]
        if self.resolved_artifacts:
            lines.extend(f"- {artifact}" for artifact in self.resolved_artifacts)
        else:
            lines.append("- none")
        lines.append("Reason:")
        lines.append(self.resolution_reason)
        return "\n".join(lines)


def _now_rfc3339() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_rfc3339(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Created timestamp must be RFC3339, got: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"Created timestamp must include timezone offset, got: {value}")
    return parsed


def _find_repo_root(path: Path) -> Path | None:
    for candidate in (path.resolve(), *path.resolve().parents):
        if (candidate / ".git").exists() or (candidate / ".specify").exists():
            return candidate
    return None


def _git_current_branch(repo_root: Path | None) -> str | None:
    if repo_root is None:
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    branch = completed.stdout.strip()
    return branch or None


def _ensure_stage(stage: str) -> str:
    if stage not in CANONICAL_STAGE_IDS:
        raise ValueError(f"Unsupported stage id: {stage}")
    return stage


def _ensure_transition(source_stage: str, target_stage: str) -> tuple[str, str]:
    source = _ensure_stage(source_stage)
    target = _ensure_stage(target_stage)
    transition = (source, target)
    if transition not in TRANSITION_ORDER:
        raise ValueError(f"Unsupported transition: {source} -> {target}")
    return transition


def _repo_relative(path: Path, repo_root: Path | None, feature_dir: Path) -> str:
    resolved = path.resolve()
    if repo_root is not None:
        try:
            return resolved.relative_to(repo_root).as_posix()
        except ValueError:
            pass
    try:
        return resolved.relative_to(feature_dir.parent.parent).as_posix()
    except ValueError:
        return resolved.as_posix()


def handoff_dir(feature_dir: Path) -> Path:
    return feature_dir / "handoffs"


def handoff_file_path(feature_dir: Path, source_stage: str, target_stage: str) -> Path:
    source, target = _ensure_transition(source_stage, target_stage)
    return handoff_dir(feature_dir) / f"{source}-to-{target}.md"


def _render_handoff(record: HandoffRecord) -> str:
    lines = [
        f"# Handoff: {record.source_stage} -> {record.target_stage}",
        "",
        f"Source: {record.source_stage}",
        f"Target: {record.target_stage}",
        f"Branch: {record.branch or ''}",
        f"Lane: {record.lane_id or ''}",
        f"Created: {record.created_at}",
        "",
        "## Summary",
        record.summary.strip(),
        "",
        "## Upstream Artifacts",
    ]
    if record.upstream_artifacts:
        lines.extend(f"- {path}" for path in record.upstream_artifacts)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Open Questions",
        ]
    )
    if record.open_questions:
        lines.extend(f"- {question}" for question in record.open_questions)
    else:
        lines.append("- None")
    return "\n".join(lines).rstrip() + "\n"


def create_handoff(
    feature_dir: Path | str,
    *,
    source_stage: str,
    target_stage: str,
    summary: str,
    upstream_artifacts: list[str | Path],
    open_questions: list[str] | None = None,
    branch: str | None = None,
    lane_id: str | None = None,
    created_at: str | None = None,
) -> HandoffRecord:
    feature_path = Path(feature_dir).resolve()
    source, target = _ensure_transition(source_stage, target_stage)
    if not summary.strip():
        raise ValueError("Handoff summary must not be empty.")
    repo_root = _find_repo_root(feature_path)
    created = created_at or _now_rfc3339()
    _parse_rfc3339(created)

    normalized_artifacts: list[str] = []
    for artifact in upstream_artifacts:
        artifact_path = Path(artifact)
        if not artifact_path.is_absolute():
            artifact_path = (repo_root / artifact_path).resolve() if repo_root else (feature_path / artifact_path).resolve()
        normalized_artifacts.append(_repo_relative(artifact_path, repo_root, feature_path))

    record_path = handoff_file_path(feature_path, source, target)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    locator = _repo_relative(record_path, repo_root, feature_path)
    record = HandoffRecord(
        source_stage=source,
        target_stage=target,
        summary=summary.strip(),
        upstream_artifacts=normalized_artifacts,
        open_questions=[question.strip() for question in (open_questions or []) if question.strip()],
        branch=branch.strip() if branch and branch.strip() else None,
        lane_id=lane_id.strip() if lane_id and lane_id.strip() else None,
        created_at=created,
        storage_shape="file",
        locator=locator,
    )
    record_path.write_text(_render_handoff(record), encoding="utf-8")
    return record


def _parse_metadata(lines: list[str]) -> tuple[dict[str, str], int]:
    metadata: dict[str, str] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("## "):
            break
        if ":" not in line:
            raise ValueError(f"Invalid handoff metadata line: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        if key not in TOP_LEVEL_KEYS:
            raise ValueError(f"Unexpected handoff metadata key: {key}")
        metadata[key] = value.strip()
        index += 1
    return metadata, index


def _parse_sections(lines: list[str]) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        if line.startswith("## "):
            title = line[3:].strip()
            if title not in SECTION_TITLES:
                raise ValueError(f"Unexpected handoff section title: {title}")
            current = title
            sections.setdefault(title, [])
            continue
        if current is not None:
            sections[current].append(line)

    missing = [title for title in SECTION_TITLES if title not in sections]
    if missing:
        raise ValueError(f"Missing handoff sections: {missing}")
    return {title: "\n".join(value).strip() for title, value in sections.items()}


def parse_handoff_file(path: Path, *, feature_dir: Path | None = None) -> HandoffRecord:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# Handoff: "):
        raise ValueError(f"Invalid handoff file heading in {path}")
    title = lines[0][len("# Handoff: ") :]
    if " -> " not in title:
        raise ValueError(f"Invalid handoff title in {path}")
    source_stage, target_stage = [part.strip() for part in title.split(" -> ", 1)]
    _ensure_transition(source_stage, target_stage)
    metadata, start_index = _parse_metadata(lines[1:])
    if metadata.get("Source") and metadata["Source"] != source_stage:
        raise ValueError(f"Handoff source metadata/title mismatch in {path}")
    if metadata.get("Target") and metadata["Target"] != target_stage:
        raise ValueError(f"Handoff target metadata/title mismatch in {path}")
    sections = _parse_sections(lines[1 + start_index :])
    created = metadata.get("Created", "")
    _parse_rfc3339(created)
    feature_path = feature_dir.resolve() if feature_dir else path.parent.parent.resolve()
    repo_root = _find_repo_root(feature_path)
    artifacts = [
        item[2:].strip()
        for item in sections["Upstream Artifacts"].splitlines()
        if item.strip().startswith("- ") and item[2:].strip().lower() != "none"
    ]
    questions = [
        item[2:].strip()
        for item in sections["Open Questions"].splitlines()
        if item.strip().startswith("- ") and item[2:].strip().lower() != "none"
    ]
    return HandoffRecord(
        source_stage=source_stage,
        target_stage=target_stage,
        summary=sections["Summary"],
        upstream_artifacts=artifacts,
        open_questions=questions,
        branch=metadata.get("Branch") or None,
        lane_id=metadata.get("Lane") or None,
        created_at=created,
        storage_shape="file",
        locator=_repo_relative(path, repo_root, feature_path),
    )


def _extract_embedded_section(path: Path, source_stage: str, target_stage: str) -> HandoffRecord | None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    target_title = f"Handoff: {source_stage} -> {target_stage}"
    heading_indices: list[tuple[int, int]] = []

    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            continue
        level = len(stripped) - len(stripped.lstrip("#"))
        title = stripped[level:].strip()
        if title == target_title:
            heading_indices.append((index, level))

    if not heading_indices:
        return None

    start_index, level = heading_indices[0]
    end_index = len(lines)
    for index in range(start_index + 1, len(lines)):
        stripped = lines[index].lstrip()
        if not stripped.startswith("#"):
            continue
        next_level = len(stripped) - len(stripped.lstrip("#"))
        title = stripped[next_level:].strip()
        if title in SECTION_TITLES:
            continue
        if next_level <= level:
            end_index = index
            break

    body = lines[start_index + 1 : end_index]
    metadata, body_index = _parse_metadata(body)
    sections = _parse_sections(body[body_index:])
    created = metadata.get("Created", "")
    _parse_rfc3339(created)
    repo_root = _find_repo_root(path)
    feature_dir = path.parent if path.parent.name.startswith("00") else path.parent
    artifacts = [
        item[2:].strip()
        for item in sections["Upstream Artifacts"].splitlines()
        if item.strip().startswith("- ") and item[2:].strip().lower() != "none"
    ]
    questions = [
        item[2:].strip()
        for item in sections["Open Questions"].splitlines()
        if item.strip().startswith("- ") and item[2:].strip().lower() != "none"
    ]
    feature_path = _feature_dir_from_artifact(path)
    locator = f"{_repo_relative(path, repo_root, feature_path)}::section-title=Handoff: {source_stage} -> {target_stage}"
    return HandoffRecord(
        source_stage=source_stage,
        target_stage=target_stage,
        summary=sections["Summary"],
        upstream_artifacts=artifacts,
        open_questions=questions,
        branch=metadata.get("Branch") or None,
        lane_id=metadata.get("Lane") or None,
        created_at=created,
        storage_shape="embedded",
        locator=locator,
    )


def _feature_dir_from_artifact(path: Path) -> Path:
    for candidate in (path.parent, *path.parents):
        if candidate.name.startswith(tuple(str(index).zfill(3) for index in range(1000))):
            return candidate
    # Normal feature directories follow specs/<feature>; fallback to specs parent.
    for candidate in (path.parent, *path.parents):
        if candidate.parent.name == "specs":
            return candidate
    return path.parent


def _embedded_search_paths(feature_dir: Path, source_stage: str) -> list[Path]:
    names = {
        # 009 + 012 vocabulary
        "brainstorm": ("brainstorm.md",),
        "specify": ("spec.md",),
        "clarify": ("spec.md",),  # clarify annotates spec.md in-place
        "review-spec": ("review-spec.md", "review.md"),
        "plan": ("plan.md",),
        "tasks": ("tasks.md",),
        "assign": ("tasks.md",),
        "implement": ("tasks.md", "plan.md", "spec.md"),
        "review-code": ("review-code.md", "review.md"),
        "pr-ready": ("review-code.md", "review.md"),
        "pr-create": ("review-code.md", "review.md"),
        "review-pr": ("review-pr.md", "review.md"),
        # Legacy 006-era names
        "code-review": ("review-code.md", "review.md"),
        "cross-review": ("review-cross.md", "review.md"),
        "pr-review": ("review-pr.md", "review.md"),
        "self-review": ("self-review.md",),
    }[source_stage]
    return [feature_dir / name for name in names if (feature_dir / name).exists()]


def _fallback_source_order(feature_dir: Path, target_stage: str) -> list[str]:
    if target_stage == "implement":
        tasks_text = (feature_dir / "tasks.md").read_text(encoding="utf-8") if (feature_dir / "tasks.md").exists() else ""
        if "[@" in tasks_text:
            return ["assign", "tasks"]
        return ["tasks", "assign"]
    if target_stage == "pr-review":
        if (feature_dir / "review-cross.md").exists():
            return ["cross-review", "code-review"]
        return ["code-review", "cross-review"]
    return [source for source, target in TRANSITION_ORDER if target == target_stage]


def _fallback_artifacts(feature_dir: Path, source_stage: str, repo_root: Path | None) -> list[str]:
    candidates: tuple[str, ...]
    if source_stage == "brainstorm":
        candidates = ("brainstorm.md",)
    elif source_stage == "specify":
        candidates = ("spec.md",)
    elif source_stage == "plan":
        candidates = ("plan.md", "research.md", "data-model.md", "contracts")
    elif source_stage in {"tasks", "assign"}:
        candidates = ("tasks.md",)
    elif source_stage == "implement":
        candidates = ("tasks.md", "plan.md", "spec.md")
    elif source_stage == "code-review":
        candidates = ("review-code.md", "review.md")
    elif source_stage == "cross-review":
        candidates = ("review-cross.md", "review.md")
    elif source_stage == "pr-review":
        candidates = ("review-pr.md", "review.md")
    elif source_stage == "self-review":
        candidates = ("self-review.md",)
    else:
        candidates = ()

    resolved: list[str] = []
    for name in candidates:
        path = feature_dir / name
        if path.exists():
            resolved.append(_repo_relative(path, repo_root, feature_dir))
    return resolved


def _sort_candidates(candidates: list[HandoffRecord], branch: str | None, lane_id: str | None) -> tuple[list[HandoffRecord], bool]:
    def key(record: HandoffRecord) -> tuple[int, int, int, float, str]:
        branch_match = int(bool(branch and record.branch == branch))
        lane_match = int(bool(lane_id and record.lane_id == lane_id))
        storage_rank = 1 if record.storage_shape == "file" else 0
        timestamp = _parse_rfc3339(record.created_at).timestamp()
        return (storage_rank, branch_match, lane_match, timestamp, record.locator)

    ranked = sorted(candidates, key=key, reverse=True)
    ambiguity = len(ranked) > 1 and key(ranked[0]) == key(ranked[1])
    return ranked, ambiguity


def resolve_handoff(
    feature_dir: Path | str,
    *,
    target_stage: str,
    source_stage: str | None = None,
    branch: str | None = None,
    lane_id: str | None = None,
) -> ResolutionResult:
    feature_path = Path(feature_dir).resolve()
    repo_root = _find_repo_root(feature_path)
    resolved_branch = branch.strip() if branch and branch.strip() else _git_current_branch(repo_root)
    target = _ensure_stage(target_stage)

    candidate_transitions = [
        (source, transition_target)
        for source, transition_target in TRANSITION_ORDER
        if transition_target == target and (source_stage is None or source == source_stage)
    ]
    if source_stage is not None and not candidate_transitions:
        _ensure_transition(source_stage, target)

    explicit_candidates: list[HandoffRecord] = []
    uniqueness_violation_detected = False
    for source, transition_target in candidate_transitions:
        file_path = handoff_file_path(feature_path, source, transition_target)
        if file_path.exists():
            explicit_candidates.append(parse_handoff_file(file_path, feature_dir=feature_path))
        for artifact in _embedded_search_paths(feature_path, source):
            embedded = _extract_embedded_section(artifact, source, transition_target)
            if embedded is not None:
                explicit_candidates.append(embedded)

    if explicit_candidates:
        ranked, ambiguity = _sort_candidates(explicit_candidates, resolved_branch, lane_id)
        uniqueness_violation_detected = ambiguity
        winner = ranked[0]
        return ResolutionResult(
            target_stage=target,
            resolved_source_stage=winner.source_stage,
            resolved_handoff=winner.locator,
            resolved_artifacts=list(winner.upstream_artifacts),
            resolution_reason=(
                f"Resolved explicit {winner.storage_shape} handoff "
                f"{winner.source_stage} -> {winner.target_stage}."
            ),
            used_branch_context=bool(resolved_branch and winner.branch == resolved_branch),
            used_lane_context=bool(lane_id and winner.lane_id == lane_id),
            winning_storage_shape=winner.storage_shape,
            ambiguity_detected=ambiguity,
            uniqueness_violation_detected=uniqueness_violation_detected,
        )

    fallback_sources = [source_stage] if source_stage else _fallback_source_order(feature_path, target)
    resolved_source: str | None = None
    resolved_artifacts: list[str] = []
    for candidate_source in fallback_sources:
        if candidate_source is None:
            continue
        artifacts = _fallback_artifacts(feature_path, candidate_source, repo_root)
        resolved_source = candidate_source
        resolved_artifacts = artifacts
        if artifacts:
            break

    if resolved_source is None and fallback_sources:
        resolved_source = fallback_sources[0]

    reason = "Inferred transition from durable feature artifacts."
    if resolved_source:
        reason = f"Inferred {resolved_source} -> {target} from durable feature artifacts; no explicit handoff was found."
        if not resolved_artifacts:
            reason += " No expected upstream artifacts were present."

    return ResolutionResult(
        target_stage=target,
        resolved_source_stage=resolved_source,
        resolved_handoff=None,
        resolved_artifacts=resolved_artifacts,
        resolution_reason=reason,
        used_branch_context=False,
        used_lane_context=False,
        winning_storage_shape="artifact-only",
        ambiguity_detected=False,
        uniqueness_violation_detected=uniqueness_violation_detected,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and resolve Orca context handoffs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create or update a canonical handoff file")
    create.add_argument("--feature-dir", required=True, help="Path to the feature directory")
    create.add_argument("--source-stage", required=True, choices=CANONICAL_STAGE_IDS)
    create.add_argument("--target-stage", required=True, choices=CANONICAL_STAGE_IDS)
    create.add_argument("--summary", required=True, help="Short transition summary")
    create.add_argument("--artifact", action="append", default=[], help="Repo-relative or absolute upstream artifact path")
    create.add_argument("--open-question", action="append", default=[], help="Open question to serialize")
    create.add_argument("--branch", help="Feature branch name")
    create.add_argument("--lane-id", help="Optional Orca lane/worktree id")
    create.add_argument("--created-at", help="Optional RFC3339 timestamp override")

    resolve = subparsers.add_parser("resolve", help="Resolve upstream context for a target stage")
    resolve.add_argument("--feature-dir", required=True, help="Path to the feature directory")
    resolve.add_argument("--target-stage", required=True, choices=CANONICAL_STAGE_IDS)
    resolve.add_argument("--source-stage", choices=CANONICAL_STAGE_IDS)
    resolve.add_argument("--branch", help="Optional current git branch override")
    resolve.add_argument("--lane-id", help="Optional Orca lane/worktree id")
    resolve.add_argument("--format", choices=("json", "text"), default="json")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "create":
        record = create_handoff(
            args.feature_dir,
            source_stage=args.source_stage,
            target_stage=args.target_stage,
            summary=args.summary,
            upstream_artifacts=args.artifact,
            open_questions=args.open_question,
            branch=args.branch,
            lane_id=args.lane_id,
            created_at=args.created_at,
        )
        print(json.dumps(record.to_dict(), indent=2))
        return 0

    result = resolve_handoff(
        args.feature_dir,
        target_stage=args.target_stage,
        source_stage=args.source_stage,
        branch=args.branch,
        lane_id=args.lane_id,
    )
    if args.format == "text":
        print(result.to_text())
    else:
        print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
