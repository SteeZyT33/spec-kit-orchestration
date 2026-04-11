from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any


VALID_DECISIONS = {"direct-take", "adapt-heavily", "defer", "reject"}
VALID_STATUSES = {"open", "mapped", "implemented", "deferred", "rejected"}
VALID_ENTRY_KINDS = {"pattern", "wrapper-capability"}
VALID_TARGET_KINDS = {"existing-spec", "future-feature", "capability-pack", "roadmap", "none"}
VALID_ADOPTION_SCOPES = {"portable-principle", "host-specific-detail", "mixed"}
SECTION_NAMES = ["Summary", "Rationale", "Mapping Notes"]
TITLE_RE = re.compile(r"^# Evolve Entry (?P<entry_id>EV-\d+): (?P<title>.+)$")
META_RE = re.compile(
    r"^\*\*(?P<key>"
    r"Source Name|Source Ref|Decision|Status|Entry Kind|Target Kind|Target Ref|Follow Up Ref|"
    r"Adoption Scope|External Dependency|Ownership Boundary|Created|Updated"
    r")\*\*: (?P<value>.*)$"
)
SECTION_RE = re.compile(r"^## (?P<section>.+)$")


@dataclass
class HarvestEntry:
    entry_id: str
    number: str
    title: str
    slug: str
    source_name: str
    source_ref: str
    summary: str
    decision: str
    rationale: str
    entry_kind: str
    target_kind: str
    target_ref: str | None
    status: str
    follow_up_ref: str | None
    external_dependency: str | None
    ownership_boundary: str | None
    adoption_scope: str
    mapping_notes: str
    created_at: str
    updated_at: str
    path: Path

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["path"] = str(self.path)
        return payload


@dataclass(frozen=True)
class SeedEntry:
    title: str
    source_name: str
    source_ref: str
    summary: str
    decision: str
    rationale: str
    entry_kind: str = "pattern"
    target_kind: str = "none"
    target_ref: str | None = None
    status: str | None = None
    follow_up_ref: str | None = None
    external_dependency: str | None = None
    ownership_boundary: str | None = None
    adoption_scope: str = "portable-principle"
    mapping_notes: str = ""


SEED_ENTRIES: tuple[SeedEntry, ...] = (
    SeedEntry(
        title="Brainstorm Memory Model",
        source_name="cc-spex",
        source_ref="docs/orca-harvest-matrix.md#1-brainstorm-memory-model",
        summary="Durable brainstorm records, overview regeneration, revisit behavior, and parked ideas.",
        decision="direct-take",
        rationale="This is high-value daily-use memory and is already a core Orca direction.",
        target_kind="existing-spec",
        target_ref="002-brainstorm-memory",
        status="implemented",
        follow_up_ref="specs/002-brainstorm-memory/spec.md",
    ),
    SeedEntry(
        title="Split Review Artifacts",
        source_name="cc-spex",
        source_ref="docs/orca-harvest-matrix.md#2-split-review-artifacts",
        summary="Separate durable artifacts for different review stages instead of one overloaded review file.",
        decision="direct-take",
        rationale="Split review artifacts simplify flow tracking and downstream orchestration.",
        target_kind="existing-spec",
        target_ref="006-orca-review-artifacts",
        status="implemented",
        follow_up_ref="specs/006-orca-review-artifacts/spec.md",
    ),
    SeedEntry(
        title="Resume And Start-From Controls",
        source_name="cc-spex",
        source_ref="docs/orca-harvest-matrix.md#3-resume-start-from-pipeline-controls",
        summary="Resume/start-from orchestration controls backed by durable run state.",
        decision="direct-take",
        rationale="These controls are important, but they belong downstream of stable workflow primitives.",
        target_kind="existing-spec",
        target_ref="009-orca-yolo",
        status="mapped",
        follow_up_ref="specs/009-orca-yolo/spec.md",
    ),
    SeedEntry(
        title="Branch-Based Artifact Resolution",
        source_name="cc-spex",
        source_ref="docs/orca-harvest-matrix.md#4-branch-based-artifact-resolution",
        summary="Use the current feature branch as a default artifact lookup key after context resets.",
        decision="direct-take",
        rationale="This reduces friction in fresh-session and cross-branch work.",
        target_kind="existing-spec",
        target_ref="007-orca-context-handoffs",
        status="implemented",
        follow_up_ref="specs/007-orca-context-handoffs/spec.md",
    ),
    SeedEntry(
        title="Self-Evolution Discipline",
        source_name="cc-spex",
        source_ref="docs/orca-harvest-matrix.md#5-self-evolution-discipline",
        summary="Track adoption work explicitly instead of leaving worthwhile patterns in chat history.",
        decision="direct-take",
        rationale="Orca is already complex enough to need a durable adoption-control system.",
        target_kind="existing-spec",
        target_ref="011-orca-evolve",
        status="open",
        follow_up_ref="specs/011-orca-evolve/spec.md",
    ),
    SeedEntry(
        title="Capability Packs Instead Of Trait Sprawl",
        source_name="cc-spex",
        source_ref="docs/orca-harvest-matrix.md#1-traits-overlays",
        summary="Use explicit optional capability boundaries without cloning Spex trait layering.",
        decision="adapt-heavily",
        rationale="The principle is useful, but Orca needs a simpler provider-agnostic mechanism.",
        target_kind="existing-spec",
        target_ref="008-orca-capability-packs",
        status="implemented",
        follow_up_ref="specs/008-orca-capability-packs/spec.md",
        adoption_scope="mixed",
    ),
    SeedEntry(
        title="Portable Team Coordination Patterns",
        source_name="omx-team-worker",
        source_ref="specs/011-orca-evolve/brainstorm.md",
        summary="State-first mailbox coordination, durable acknowledgments, and claim-safe delegated work.",
        decision="adapt-heavily",
        rationale="Orca wants the coordination principles but not the OMX runtime contract.",
        target_kind="existing-spec",
        target_ref="010-orca-matriarch",
        status="implemented",
        follow_up_ref="specs/010-orca-matriarch/spec.md",
        adoption_scope="portable-principle",
    ),
    SeedEntry(
        title="Deep Optimize",
        source_name="autoresearch",
        source_ref="specs/011-orca-evolve/brainstorm.md",
        summary="Thin Orca-native wrapper for hard optimization work delegated to autoresearch.",
        decision="adapt-heavily",
        rationale="Orca should own routing, scoping, and artifact expectations but not the underlying optimization engine.",
        entry_kind="wrapper-capability",
        target_kind="future-feature",
        target_ref="deep-optimize",
        status="mapped",
        external_dependency="autoresearch",
        ownership_boundary="Orca owns the wrapper contract, scoping, and artifact expectations; autoresearch owns the deep optimization engine.",
        follow_up_ref="specs/011-orca-evolve/spec.md",
    ),
    SeedEntry(
        title="Deep Research",
        source_name="external-specialist-skill",
        source_ref="specs/011-orca-evolve/brainstorm.md",
        summary="Thin Orca-native wrapper for deep multi-source research when ordinary context gathering is not enough.",
        decision="defer",
        rationale="The wrapper shape is promising, but the target external engine and workflow contract still need refinement.",
        entry_kind="wrapper-capability",
        target_kind="future-feature",
        target_ref="deep-research",
        status="deferred",
        external_dependency="external specialist research tooling",
        ownership_boundary="Orca would own entrypoint naming, scoping, and artifact rules while delegating deep research execution.",
        follow_up_ref="specs/011-orca-evolve/spec.md",
    ),
    SeedEntry(
        title="Deep Review",
        source_name="external-specialist-skill",
        source_ref="specs/011-orca-evolve/brainstorm.md",
        summary="Thin Orca-native wrapper for deeper multi-perspective review when standard review surfaces are not enough.",
        decision="defer",
        rationale="Useful as a future wrapper capability, but not mature enough to treat as core Orca review yet.",
        entry_kind="wrapper-capability",
        target_kind="future-feature",
        target_ref="deep-review",
        status="deferred",
        external_dependency="external deep-review tooling",
        ownership_boundary="Orca would own when and how deep review is invoked; the external system would own the underlying review engine.",
        follow_up_ref="specs/011-orca-evolve/spec.md",
    ),
)


def _resolve_date(current_date: str | None = None) -> str:
    if current_date is None:
        raise ValueError("current_date must be provided explicitly")
    cleaned = current_date.strip()
    if not cleaned:
        raise ValueError("current_date must not be empty")
    date.fromisoformat(cleaned)
    return cleaned


def _validate_date_metadata(entry: HarvestEntry) -> None:
    try:
        created = date.fromisoformat(entry.created_at)
    except ValueError as exc:
        raise ValueError(f"{entry.path}: invalid Created date '{entry.created_at}'") from exc
    try:
        updated = date.fromisoformat(entry.updated_at)
    except ValueError as exc:
        raise ValueError(f"{entry.path}: invalid Updated date '{entry.updated_at}'") from exc
    if updated < created:
        raise ValueError(f"{entry.path}: Updated date '{entry.updated_at}' must not be earlier than Created date '{entry.created_at}'")


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or "untitled"


def evolve_dir(root: Path) -> Path:
    return root / ".specify" / "orca" / "evolve"


def entries_dir(root: Path) -> Path:
    return evolve_dir(root) / "entries"


def overview_path(root: Path) -> Path:
    return evolve_dir(root) / "00-overview.md"


def _entry_files(root: Path) -> list[Path]:
    directory = entries_dir(root)
    if not directory.is_dir():
        return []
    return sorted(
        (path for path in directory.glob("*.md") if re.match(r"^\d+-.*\.md$", path.name)),
        key=lambda path: int(path.name.split("-", 1)[0]),
    )


def _next_number(root: Path) -> int:
    highest = 0
    for path in _entry_files(root):
        highest = max(highest, int(path.name.split("-", 1)[0]))
    return highest + 1


def _number_string(root: Path) -> str:
    number = _next_number(root)
    return str(number).zfill(max(3, len(str(number))))


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _default_status(decision: str, target_kind: str) -> str:
    if decision == "reject":
        return "rejected"
    if decision == "defer":
        return "deferred"
    if target_kind != "none":
        return "mapped"
    return "open"


def _validate_entry(entry: HarvestEntry) -> None:
    if entry.decision not in VALID_DECISIONS:
        raise ValueError(f"Invalid decision '{entry.decision}'")
    if entry.status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{entry.status}'")
    if entry.entry_kind not in VALID_ENTRY_KINDS:
        raise ValueError(f"Invalid entry kind '{entry.entry_kind}'")
    if entry.target_kind not in VALID_TARGET_KINDS:
        raise ValueError(f"Invalid target kind '{entry.target_kind}'")
    if entry.adoption_scope not in VALID_ADOPTION_SCOPES:
        raise ValueError(f"Invalid adoption scope '{entry.adoption_scope}'")
    if not entry.source_name.strip():
        raise ValueError("source_name must not be empty")
    if not entry.source_ref.strip():
        raise ValueError("source_ref must not be empty")
    if not entry.summary.strip():
        raise ValueError("summary must not be empty")
    if not entry.rationale.strip():
        raise ValueError("rationale must not be empty")
    _validate_date_metadata(entry)
    if entry.entry_kind == "wrapper-capability":
        if not entry.external_dependency:
            raise ValueError("wrapper-capability entries require external_dependency")
        if not entry.ownership_boundary:
            raise ValueError("wrapper-capability entries require ownership_boundary")
    if entry.status in {"mapped", "implemented"} and entry.target_kind == "none":
        raise ValueError(f"status '{entry.status}' requires a target mapping")
    if entry.decision == "reject" and entry.status != "rejected":
        raise ValueError("reject entries must use status 'rejected'")
    if entry.decision == "defer" and entry.status != "deferred":
        raise ValueError("defer entries must use status 'deferred'")
    if entry.status == "rejected" and entry.decision != "reject":
        raise ValueError("status 'rejected' must use decision 'reject'")
    if entry.status == "deferred" and entry.decision != "defer":
        raise ValueError("status 'deferred' must use decision 'defer'")
    if entry.target_kind == "none" and entry.target_ref is not None:
        raise ValueError("target_ref must be omitted when target_kind is 'none'")
    if entry.target_kind != "none" and not entry.target_ref:
        raise ValueError(f"target_kind '{entry.target_kind}' requires target_ref")
    entry_id_match = re.match(r"^EV-(\d+)$", entry.entry_id)
    if not entry_id_match:
        raise ValueError(f"Invalid entry id '{entry.entry_id}'")
    entry_id_number = entry_id_match.group(1)
    if entry_id_number != entry.number:
        raise ValueError(f"Entry id '{entry.entry_id}' does not match entry number '{entry.number}'")
    prefix = entry.path.name.split("-", 1)[0]
    if prefix != entry.number:
        raise ValueError(f"Filename prefix '{prefix}' does not match entry number '{entry.number}'")


def render_entry(entry: HarvestEntry) -> str:
    lines = [
        f"# Evolve Entry {entry.entry_id}: {entry.title}",
        "",
        f"**Source Name**: {entry.source_name}",
        f"**Source Ref**: {entry.source_ref}",
        f"**Decision**: {entry.decision}",
        f"**Status**: {entry.status}",
        f"**Entry Kind**: {entry.entry_kind}",
        f"**Target Kind**: {entry.target_kind}",
        f"**Target Ref**: {entry.target_ref or 'none'}",
        f"**Follow Up Ref**: {entry.follow_up_ref or 'none'}",
        f"**Adoption Scope**: {entry.adoption_scope}",
        f"**External Dependency**: {entry.external_dependency or 'none'}",
        f"**Ownership Boundary**: {entry.ownership_boundary or 'none'}",
        f"**Created**: {entry.created_at}",
        f"**Updated**: {entry.updated_at}",
        "",
        "## Summary",
        entry.summary.strip(),
        "",
        "## Rationale",
        entry.rationale.strip(),
        "",
        "## Mapping Notes",
        entry.mapping_notes.strip() or "(none)",
        "",
    ]
    return "\n".join(lines)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def parse_entry(path: Path) -> HarvestEntry:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"Empty evolve entry: {path}")
    title_match = TITLE_RE.match(lines[0].strip())
    if not title_match:
        raise ValueError(f"Invalid evolve entry title line in {path}")

    metadata: dict[str, str] = {}
    idx = 1
    while idx < len(lines):
        line = lines[idx].strip()
        idx += 1
        if not line:
            continue
        meta_match = META_RE.match(line)
        if not meta_match:
            idx -= 1
            break
        metadata[meta_match.group("key")] = meta_match.group("value").strip()

    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    for line in lines[idx:]:
        section_match = SECTION_RE.match(line)
        if section_match:
            current_section = section_match.group("section")
            sections.setdefault(current_section, [])
            continue
        if current_section is not None:
            sections[current_section].append(line)
    if [name for name in sections if name in SECTION_NAMES] != SECTION_NAMES:
        raise ValueError(f"Evolve entry must contain section headings in canonical order in {path}")

    number = path.name.split("-", 1)[0]
    mapping_notes = "\n".join(sections["Mapping Notes"]).strip()
    if mapping_notes == "(none)":
        mapping_notes = ""

    entry = HarvestEntry(
        entry_id=title_match.group("entry_id"),
        number=number,
        title=title_match.group("title").strip(),
        slug=path.stem.split("-", 1)[1] if "-" in path.stem else slugify(title_match.group("title")),
        source_name=metadata.get("Source Name", ""),
        source_ref=metadata.get("Source Ref", ""),
        summary="\n".join(sections["Summary"]).strip(),
        decision=metadata.get("Decision", ""),
        rationale="\n".join(sections["Rationale"]).strip(),
        entry_kind=metadata.get("Entry Kind", ""),
        target_kind=metadata.get("Target Kind", ""),
        target_ref=_normalize_optional(metadata.get("Target Ref")),
        status=metadata.get("Status", ""),
        follow_up_ref=_normalize_optional(metadata.get("Follow Up Ref")),
        external_dependency=_normalize_optional(metadata.get("External Dependency")),
        ownership_boundary=_normalize_optional(metadata.get("Ownership Boundary")),
        adoption_scope=metadata.get("Adoption Scope", ""),
        mapping_notes=mapping_notes,
        created_at=metadata.get("Created", ""),
        updated_at=metadata.get("Updated", ""),
        path=path,
    )
    if entry.target_ref == "none":
        entry.target_ref = None
    if entry.follow_up_ref == "none":
        entry.follow_up_ref = None
    if entry.external_dependency == "none":
        entry.external_dependency = None
    if entry.ownership_boundary == "none":
        entry.ownership_boundary = None
    _validate_entry(entry)
    return entry


def list_entries(root: Path) -> list[HarvestEntry]:
    return [parse_entry(path) for path in _entry_files(root)]


def create_entry(
    root: Path,
    *,
    title: str,
    source_name: str,
    source_ref: str,
    summary: str,
    decision: str,
    rationale: str,
    entry_kind: str = "pattern",
    target_kind: str = "none",
    target_ref: str | None = None,
    status: str | None = None,
    follow_up_ref: str | None = None,
    external_dependency: str | None = None,
    ownership_boundary: str | None = None,
    adoption_scope: str = "portable-principle",
    mapping_notes: str = "",
    current_date: str | None = None,
) -> HarvestEntry:
    resolved_date = _resolve_date(current_date)
    number = _number_string(root)
    slug = slugify(title)
    path = entries_dir(root) / f"{number}-{slug}.md"
    entry = HarvestEntry(
        entry_id=f"EV-{number}",
        number=number,
        title=title.strip(),
        slug=slug,
        source_name=source_name.strip(),
        source_ref=source_ref.strip(),
        summary=summary.strip(),
        decision=decision,
        rationale=rationale.strip(),
        entry_kind=entry_kind,
        target_kind=target_kind,
        target_ref=_normalize_optional(target_ref),
        status=status or _default_status(decision, target_kind),
        follow_up_ref=_normalize_optional(follow_up_ref),
        external_dependency=_normalize_optional(external_dependency),
        ownership_boundary=_normalize_optional(ownership_boundary),
        adoption_scope=adoption_scope,
        mapping_notes=mapping_notes.strip(),
        created_at=resolved_date,
        updated_at=resolved_date,
        path=path,
    )
    _validate_entry(entry)
    _write_text(path, render_entry(entry))
    return entry


def update_entry(
    path: Path,
    *,
    decision: str | None = None,
    rationale: str | None = None,
    target_kind: str | None = None,
    target_ref: str | None = None,
    status: str | None = None,
    follow_up_ref: str | None = None,
    external_dependency: str | None = None,
    ownership_boundary: str | None = None,
    adoption_scope: str | None = None,
    mapping_notes: str | None = None,
    current_date: str | None = None,
) -> HarvestEntry:
    entry = parse_entry(path)
    old_status = entry.status
    if decision is not None:
        entry.decision = decision
    if rationale is not None:
        entry.rationale = rationale.strip()
    if target_kind is not None:
        entry.target_kind = target_kind
        entry.target_ref = _normalize_optional(target_ref) if target_ref is not None else None
    elif target_ref is not None:
        entry.target_ref = _normalize_optional(target_ref)
    if status is not None:
        entry.status = status
    elif decision is not None and entry.decision in {"reject", "defer"}:
        entry.status = _default_status(entry.decision, entry.target_kind)
    elif (
        decision is not None
        and entry.decision not in {"reject", "defer"}
        and old_status in {"deferred", "rejected"}
    ):
        entry.status = _default_status(entry.decision, entry.target_kind)
    if follow_up_ref is not None:
        entry.follow_up_ref = _normalize_optional(follow_up_ref)
    if external_dependency is not None:
        entry.external_dependency = _normalize_optional(external_dependency)
    if ownership_boundary is not None:
        entry.ownership_boundary = _normalize_optional(ownership_boundary)
    if adoption_scope is not None:
        entry.adoption_scope = adoption_scope
    if mapping_notes is not None:
        entry.mapping_notes = mapping_notes.strip()
    entry.updated_at = _resolve_date(current_date)
    _validate_entry(entry)
    _write_text(entry.path, render_entry(entry))
    return entry


def _escape_table_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def regenerate_overview(root: Path) -> Path:
    entries = list_entries(root)
    counts = {
        "open": sum(1 for entry in entries if entry.status == "open"),
        "mapped": sum(1 for entry in entries if entry.status == "mapped"),
        "implemented": sum(1 for entry in entries if entry.status == "implemented"),
        "deferred": sum(1 for entry in entries if entry.status == "deferred"),
        "rejected": sum(1 for entry in entries if entry.status == "rejected"),
    }
    lines = [
        "# Orca Evolve Overview",
        "",
        "This inventory tracks external patterns, wrapper capabilities, and adoption decisions Orca wants to preserve.",
        "",
        "## Status Counts",
        "",
        f"- open: {counts['open']}",
        f"- mapped: {counts['mapped']}",
        f"- implemented: {counts['implemented']}",
        f"- deferred: {counts['deferred']}",
        f"- rejected: {counts['rejected']}",
        "",
        "## Entries",
        "",
        "| ID | Title | Decision | Status | Kind | Target | Source |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in entries:
        target = entry.target_ref or "none"
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_table_cell(entry.entry_id),
                    _escape_table_cell(entry.title),
                    _escape_table_cell(entry.decision),
                    _escape_table_cell(entry.status),
                    _escape_table_cell(entry.entry_kind),
                    _escape_table_cell(f"{entry.target_kind}:{target}"),
                    _escape_table_cell(entry.source_name),
                ]
            )
            + " |"
        )
    overview = overview_path(root)
    _write_text(overview, "\n".join(lines))
    return overview


def seed_initial_entries(root: Path, *, current_date: str | None = None) -> list[HarvestEntry]:
    existing = {entry.title: entry for entry in list_entries(root)}
    created: list[HarvestEntry] = []
    resolved_date = _resolve_date(current_date)
    for seed in SEED_ENTRIES:
        if seed.title in existing:
            created.append(existing[seed.title])
            continue
        created.append(
            create_entry(
                root,
                title=seed.title,
                source_name=seed.source_name,
                source_ref=seed.source_ref,
                summary=seed.summary,
                decision=seed.decision,
                rationale=seed.rationale,
                entry_kind=seed.entry_kind,
                target_kind=seed.target_kind,
                target_ref=seed.target_ref,
                status=seed.status,
                follow_up_ref=seed.follow_up_ref,
                external_dependency=seed.external_dependency,
                ownership_boundary=seed.ownership_boundary,
                adoption_scope=seed.adoption_scope,
                mapping_notes=seed.mapping_notes,
                current_date=resolved_date,
            )
        )
    regenerate_overview(root)
    return created


def _root(value: Path | str | None) -> Path:
    return Path(value or ".").resolve()


def _render_list_text(entries: list[HarvestEntry]) -> str:
    if not entries:
        return "No evolve entries found."
    return "\n".join(
        f"{entry.entry_id} {entry.title} [{entry.status}] -> {entry.target_kind}:{entry.target_ref or 'none'}"
        for entry in entries
    )


def _resolve_update_path(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    allowed_root = entries_dir(root).resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(f"update path must live under {allowed_root}") from exc
    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m speckit_orca.evolve")
    parser.add_argument("--root", type=Path, default=Path("."))
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--title", required=True)
    create.add_argument("--source-name", required=True)
    create.add_argument("--source-ref", required=True)
    create.add_argument("--summary", required=True)
    create.add_argument("--decision", required=True)
    create.add_argument("--rationale", required=True)
    create.add_argument("--entry-kind", default="pattern")
    create.add_argument("--target-kind", default="none")
    create.add_argument("--target-ref")
    create.add_argument("--status")
    create.add_argument("--follow-up-ref")
    create.add_argument("--external-dependency")
    create.add_argument("--ownership-boundary")
    create.add_argument("--adoption-scope", default="portable-principle")
    create.add_argument("--mapping-notes", default="")
    create.add_argument("--date", required=True)

    update = subparsers.add_parser("update")
    update.add_argument("path", type=Path)
    update.add_argument("--decision")
    update.add_argument("--rationale")
    update.add_argument("--target-kind")
    update.add_argument("--target-ref")
    update.add_argument("--status")
    update.add_argument("--follow-up-ref")
    update.add_argument("--external-dependency")
    update.add_argument("--ownership-boundary")
    update.add_argument("--adoption-scope")
    update.add_argument("--mapping-notes")
    update.add_argument("--date", required=True)

    list_cmd = subparsers.add_parser("list")
    list_cmd.add_argument("--format", choices={"text", "json"}, default="text")

    subparsers.add_parser("regenerate-overview")
    seed = subparsers.add_parser("seed-initial")
    seed.add_argument("--date", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = _root(args.root)
    try:
        if args.command == "create":
            entry = create_entry(
                root,
                title=args.title,
                source_name=args.source_name,
                source_ref=args.source_ref,
                summary=args.summary,
                decision=args.decision,
                rationale=args.rationale,
                entry_kind=args.entry_kind,
                target_kind=args.target_kind,
                target_ref=args.target_ref,
                status=args.status,
                follow_up_ref=args.follow_up_ref,
                external_dependency=args.external_dependency,
                ownership_boundary=args.ownership_boundary,
                adoption_scope=args.adoption_scope,
                mapping_notes=args.mapping_notes,
                current_date=args.date,
            )
            regenerate_overview(root)
            print(json.dumps(entry.to_dict(), indent=2, sort_keys=True))
            return 0
        if args.command == "update":
            entry = update_entry(
                _resolve_update_path(root, (root / args.path) if not args.path.is_absolute() else args.path),
                decision=args.decision,
                rationale=args.rationale,
                target_kind=args.target_kind,
                target_ref=args.target_ref,
                status=args.status,
                follow_up_ref=args.follow_up_ref,
                external_dependency=args.external_dependency,
                ownership_boundary=args.ownership_boundary,
                adoption_scope=args.adoption_scope,
                mapping_notes=args.mapping_notes,
                current_date=args.date,
            )
            regenerate_overview(root)
            print(json.dumps(entry.to_dict(), indent=2, sort_keys=True))
            return 0
        if args.command == "list":
            entries = list_entries(root)
            if args.format == "json":
                print(json.dumps([entry.to_dict() for entry in entries], indent=2, sort_keys=True))
            else:
                print(_render_list_text(entries))
            return 0
        if args.command == "regenerate-overview":
            print(str(regenerate_overview(root)))
            return 0
        if args.command == "seed-initial":
            seeded = seed_initial_entries(root, current_date=args.date)
            print(json.dumps([entry.to_dict() for entry in seeded], indent=2, sort_keys=True))
            return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
