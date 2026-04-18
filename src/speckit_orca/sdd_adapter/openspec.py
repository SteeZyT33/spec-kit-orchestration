"""OpenSpecAdapter — Phase 2 second adapter.

019 Sub-phase C (T038-T056). Read-only adapter for OpenSpec repos
(layout: ``openspec/changes/<slug>/{proposal,design,tasks}.md`` plus a
``specs/`` delta directory, with archived changes under
``openspec/changes/archive/YYYY-MM-DD-<slug>/``).

Format-ambiguity decisions (documented here so callers can read them):

- **Task ID synthesis separator.** OpenSpec ``tasks.md`` has no
  canonical task ID shape (spec Q5 deferred). For tasks without an
  explicit ``T\\d+`` ID we synthesize ``f"{feature_id}#{N:02d}"`` where
  ``N`` is the 1-indexed checkbox position. The ``#`` separator is
  provisional; Phase 3 may revisit.
- **``spec`` filename key.** Per FR-009 we map ``filenames["spec"]`` to
  ``proposal.md`` (the narrative entry point), not the per-change
  ``specs/`` delta directory. OpenSpec's delta files are tracked in
  ``artifacts`` but not surfaced through the filename map.
- **Review kinds.** Per spec §FR-010 / plan §Design §5, we OMIT review
  kinds (``review_spec``, ``review_code``, ``review_pr``) entirely from
  ``compute_stage`` output rather than emitting a "not applicable"
  status. OpenSpec has no split-review model.
- **Missing ``design.md``.** Per plan Sub-phase C Risk #2 leaning, we
  emit a ``plan`` kind with status ``"not started"`` (not "not
  applicable") so downstream readers treat it as an incomplete stage,
  not a missing capability.
- **Worktree lanes.** OpenSpec has no lane concept; always returns
  ``[]``.
- **Review evidence.** Always returns ``NormalizedReviewEvidence`` with
  every sub-evidence ``exists=False`` (spec FR-009). Phase 3 revisits.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .base import (
    FeatureHandle,
    NormalizedArtifacts,
    NormalizedReviewEvidence,
    NormalizedTask,
    SddAdapter,
    StageProgress,
)

# Matches ``2026-04-01-<slug>`` archive dir names. Group 1 is the slug.
_ARCHIVE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(?P<slug>.+)$")

# OpenSpec tasks.md line: ``- [ ] body`` or ``- [x] body``. Captures a
# leading explicit T-ID if present (spec-kit convention) so imported
# spec-kit-style tasks still carry their original IDs.
_OS_TASK_LINE_RE = re.compile(
    r"^\s*- \[(?P<mark>[ xX])\]\s*(?:(?P<task>T\d+)\b)?\s*(?P<body>.*)$"
)
_OS_ASSIGNMENT_RE = re.compile(r"\[@([^\]]+)\]")
_OS_HEADING_RE = re.compile(r"^#{1,6}\s+(?P<title>.+?)\s*$")


def _read_text_if_exists(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _slugify_heading(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


class OpenSpecAdapter(SddAdapter):
    """Read-only adapter for OpenSpec-shaped repos (019 FR-006..FR-012).

    Phase 2 does not implement write operations (no archive, no sync, no
    propose). Feature IDs are the bare change slug for active changes
    and the post-date-prefix slug for archived changes; they are stable
    across archive moves (spec §Decisions).
    """

    @property
    def name(self) -> str:
        return "openspec"

    # -- Capability declarations ------------------------------------------

    def ordered_stage_kinds(self) -> list[str]:
        return ["spec", "plan", "tasks", "implementation", "ship"]

    def supports(self, capability: str) -> bool:
        # FR-012: only "adoption" is supported; everything else False.
        return capability == "adoption"

    # -- Detection + enumeration ------------------------------------------

    def detect(self, repo_root: Path) -> bool:
        """True when ``openspec/`` directory exists (empty counts)."""
        return (Path(repo_root) / "openspec").is_dir()

    def list_features(
        self,
        repo_root: Path,
        *,
        include_archived: bool = False,
    ) -> list[FeatureHandle]:
        changes_root = Path(repo_root) / "openspec" / "changes"
        if not changes_root.is_dir():
            return []

        handles: list[FeatureHandle] = []
        for child in sorted(changes_root.iterdir()):
            if not child.is_dir() or child.name == "archive":
                continue
            handles.append(
                FeatureHandle(
                    feature_id=child.name,
                    display_name=child.name,
                    root_path=child.resolve(),
                    adapter_name=self.name,
                    archived=False,
                )
            )

        if include_archived:
            archive_root = changes_root / "archive"
            if archive_root.is_dir():
                for child in sorted(archive_root.iterdir()):
                    if not child.is_dir():
                        continue
                    m = _ARCHIVE_DIR_RE.match(child.name)
                    slug = m.group("slug") if m else child.name
                    handles.append(
                        FeatureHandle(
                            feature_id=slug,
                            display_name=slug,
                            root_path=child.resolve(),
                            adapter_name=self.name,
                            archived=True,
                        )
                    )

        return handles

    # -- Feature loading --------------------------------------------------

    def load_feature(
        self,
        handle: FeatureHandle,
        repo_root: Path | None = None,
    ) -> NormalizedArtifacts:
        """Load a feature's artifacts.

        Signature matches ``SpecKitAdapter.load_feature`` so the registry
        can invoke either polymorphically. ``repo_root`` is accepted for
        symmetry but is not required: ``handle.root_path`` already points
        at the change directory.
        """
        feature_path = Path(handle.root_path).resolve()
        fid = handle.feature_id
        del repo_root  # unused; present for ABC-family symmetry

        proposal_path = feature_path / "proposal.md"
        design_path = feature_path / "design.md"
        tasks_path = feature_path / "tasks.md"

        artifacts: dict[str, Path] = {
            "proposal.md": proposal_path,
            "design.md": design_path,
            "tasks.md": tasks_path,
        }
        # Surface every delta file under the change's specs/ directory.
        specs_dir = feature_path / "specs"
        if specs_dir.is_dir():
            for delta in sorted(specs_dir.rglob("*.md")):
                # Key relative to feature_path for a stable, diffable key.
                rel = delta.relative_to(feature_path).as_posix()
                artifacts[rel] = delta

        filenames: dict[str, str] = {
            "spec": "proposal.md",
            "plan": "design.md",
            "tasks": "tasks.md",
        }

        tasks, task_summary = self._parse_tasks(tasks_path, fid)

        return NormalizedArtifacts(
            feature_id=fid,
            feature_dir=feature_path,
            artifacts=artifacts,
            filenames=filenames,
            tasks=tasks,
            task_summary_data=task_summary,
            review_evidence=NormalizedReviewEvidence(),
            linked_brainstorms=[],
            worktree_lanes=[],
            ambiguities=[],
            notes=[],
        )

    # -- Stage computation ------------------------------------------------

    def compute_stage(
        self, artifacts: NormalizedArtifacts
    ) -> list[StageProgress]:
        """OpenSpec lifecycle -> stage-kind projection.

        Lifecycle mapping (spec FR-010, plan Sub-phase C Risk #2):
          - proposal.md present -> ``spec`` kind (complete if exists).
          - design.md present -> ``plan`` kind (complete). Missing -> not
            started (not "not applicable"; see module docstring).
          - tasks.md has checkbox entries -> ``tasks`` kind.
          - any task ticked OR archived -> ``implementation`` kind.
          - archived feature -> additional ``ship`` kind.
        Review kinds are OMITTED entirely.
        """
        a = artifacts.artifacts
        feature_dir = artifacts.feature_dir
        summary = artifacts.task_summary_data

        proposal_path = a.get("proposal.md")
        design_path = a.get("design.md")
        tasks_path = a.get("tasks.md")

        progress: list[StageProgress] = []

        # spec: proposal.md is the narrative entry.
        if proposal_path is not None:
            exists = proposal_path.exists()
            progress.append(
                StageProgress(
                    stage="proposal",
                    status="complete" if exists else "not started",
                    evidence_sources=[str(proposal_path)] if exists else [],
                    notes=[],
                    kind="spec",
                )
            )

        # plan: design.md. Missing -> "not started" (still emit).
        if design_path is not None:
            exists = design_path.exists()
            progress.append(
                StageProgress(
                    stage="design",
                    status="complete" if exists else "not started",
                    evidence_sources=[str(design_path)] if exists else [],
                    notes=[],
                    kind="plan",
                )
            )

        # tasks: tasks.md has entries?
        if tasks_path is not None:
            total = int(summary.get("total", 0))
            tasks_exists = tasks_path.exists() and total > 0
            progress.append(
                StageProgress(
                    stage="tasks",
                    status="complete" if tasks_exists else "not started",
                    evidence_sources=[str(tasks_path)] if tasks_exists else [],
                    notes=[],
                    kind="tasks",
                )
            )

        # implementation: any task ticked off. Archived features count as
        # implemented (T046 asserts shipped archives carry both kinds).
        archived = self._is_archived_path(feature_dir)
        completed = int(summary.get("completed", 0))
        if completed > 0 or archived:
            sources: list[str] = []
            if tasks_path is not None and tasks_path.exists():
                sources.append(str(tasks_path))
            progress.append(
                StageProgress(
                    stage="apply",
                    status="complete",
                    evidence_sources=sources,
                    notes=[],
                    kind="implementation",
                )
            )
        elif tasks_path is not None:
            progress.append(
                StageProgress(
                    stage="apply",
                    status="not started",
                    evidence_sources=[],
                    notes=[],
                    kind="implementation",
                )
            )

        # ship: only for archived features.
        if archived:
            progress.append(
                StageProgress(
                    stage="archive",
                    status="complete",
                    evidence_sources=[str(feature_dir)],
                    notes=[],
                    kind="ship",
                )
            )

        return progress

    @staticmethod
    def _is_archived_path(feature_dir: Path) -> bool:
        parts = feature_dir.resolve().parts
        # Matches .../openspec/changes/archive/<...>
        try:
            idx = parts.index("archive")
        except ValueError:
            return False
        # Confirm the segment immediately before is "changes".
        return idx > 0 and parts[idx - 1] == "changes"

    # -- Path reverse lookup ----------------------------------------------

    def id_for_path(
        self, path: Path, repo_root: Path | None = None
    ) -> str | None:
        """Map a path to a feature_id, or None.

        Active changes: ``openspec/changes/<slug>/...`` -> ``<slug>``.
        Archive paths: returns ``None`` (v1 default per FR-011; archive
        enumeration is opt-in via ``list_features(include_archived=True)``
        but ``id_for_path`` does not thread that flag through).
        """
        resolved = Path(path).resolve()
        root = (
            Path(repo_root).resolve()
            if repo_root is not None
            else self._find_repo_root(resolved)
        )
        if root is None:
            return None
        changes_root = (root / "openspec" / "changes").resolve()
        try:
            rel = resolved.relative_to(changes_root)
        except ValueError:
            return None
        parts = rel.parts
        if not parts or parts[0] == "archive":
            return None
        return parts[0]

    @staticmethod
    def _find_repo_root(start: Path) -> Path | None:
        for candidate in (start, *start.parents):
            if (candidate / ".git").exists() or (candidate / ".specify").exists():
                return candidate.resolve()
            if (candidate / "openspec").is_dir():
                return candidate.resolve()
        return None

    # -- Task parsing -----------------------------------------------------

    @staticmethod
    def _parse_tasks(
        path: Path, feature_id: str
    ) -> tuple[list[NormalizedTask], dict[str, Any]]:
        """Parse an OpenSpec ``tasks.md`` into normalized rows.

        Each line matching ``- [ ]`` / ``- [x]`` at any indent becomes a
        task. Explicit ``T\\d+`` IDs are preserved; everything else gets
        a synthesized ID ``f"{feature_id}#{N:02d}"`` (N is 1-indexed per
        checkbox position). Headings are slugified into the summary
        (same convention as spec-kit).
        """
        tasks: list[NormalizedTask] = []
        summary: dict[str, Any] = {
            "total": 0,
            "completed": 0,
            "incomplete": 0,
            "assigned": 0,
            "headings": [],
        }
        text = _read_text_if_exists(path)
        if not text:
            return tasks, summary

        position = 0
        for line in text.splitlines():
            heading = _OS_HEADING_RE.match(line)
            if heading:
                summary["headings"].append(
                    _slugify_heading(heading.group("title"))
                )
                continue

            match = _OS_TASK_LINE_RE.match(line)
            if not match:
                continue

            position += 1
            explicit_id = match.group("task")
            body = match.group("body") or ""
            completed = bool(match.group("mark").strip())

            summary["total"] += 1
            if completed:
                summary["completed"] += 1
            else:
                summary["incomplete"] += 1

            assignee: str | None = None
            assign_match = _OS_ASSIGNMENT_RE.search(body)
            if assign_match:
                assignee = assign_match.group(1).strip()
                summary["assigned"] += 1

            task_id = explicit_id or f"{feature_id}#{position:02d}"

            tasks.append(
                NormalizedTask(
                    task_id=task_id,
                    text=body.strip(),
                    completed=completed,
                    assignee=assignee,
                )
            )
        return tasks, summary
