from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


SECTION_NAMES = [
    "Problem",
    "Desired Outcome",
    "Constraints",
    "Existing Context",
    "Options Considered",
    "Recommendation",
    "Open Questions",
    "Ready For Spec",
    "Revisions",
]
REQUIRED_SECTIONS = SECTION_NAMES[:-1]
VALID_STATUSES = {"active", "parked", "abandoned", "spec-created"}
ALLOWED_STATE_TRANSITIONS = {
    "active": {"parked", "abandoned", "spec-created"},
    "parked": {"active", "spec-created"},
    "abandoned": {"parked", "active"},
    "spec-created": {"spec-created"},
}
TITLE_RE = re.compile(r"^# Brainstorm (?P<number>\d+): (?P<title>.+)$")
META_RE = re.compile(r"^\*\*(?P<key>Status|Created|Updated|Downstream)\*\*: (?P<value>.*)$")
SECTION_RE = re.compile(r"^## (?P<section>.+)$")


@dataclass
class BrainstormRecord:
    number: str
    title: str
    slug: str
    status: str
    created: str
    updated: str
    downstream: str
    sections: dict[str, str]
    path: Path


@dataclass
class MatchCandidate:
    number: str
    title: str
    slug: str
    status: str
    match_reason: str


def _today() -> str:
    return date.today().isoformat()


def _normalize_downstream(value: str | None) -> str:
    if not value or value.strip() in {"", "none"}:
        return "none"
    cleaned = value.strip()
    if ":" not in cleaned:
        raise ValueError(f"Downstream must be 'none' or '<type>:<ref>', got: {cleaned}")
    return cleaned


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned or "untitled"


def _significant_length(sections: dict[str, str]) -> int:
    return len(
        re.sub(
            r"\s+",
            "",
            "".join(
            sections.get(name, "").strip()
            for name in ("Problem", "Desired Outcome", "Options Considered", "Recommendation", "Open Questions")
            ),
        )
    )


def is_meaningful_session(sections: dict[str, str], explicit_preserve: bool = False) -> bool:
    if explicit_preserve:
        return True
    populated = sum(1 for name in ("Problem", "Desired Outcome", "Options Considered", "Recommendation", "Open Questions") if sections.get(name, "").strip())
    return populated >= 2 or _significant_length(sections) >= 100


def brainstorm_dir(root: Path) -> Path:
    return root / "brainstorm"


def overview_path(root: Path) -> Path:
    return brainstorm_dir(root) / "00-overview.md"


def _brainstorm_files(root: Path) -> list[Path]:
    directory = brainstorm_dir(root)
    if not directory.is_dir():
        return []
    return sorted(
        (
            path
            for path in directory.glob("*.md")
            if path.name != "00-overview.md" and re.match(r"^\d+-.*\.md$", path.name)
        ),
        key=lambda path: int(path.name.split("-", 1)[0]),
    )


def next_number(root: Path) -> int:
    highest = 0
    for path in _brainstorm_files(root):
        number = int(path.name.split("-", 1)[0])
        highest = max(highest, number)
    return highest + 1


def _number_width(number: int) -> int:
    return max(2, len(str(number)))


def next_number_string(root: Path) -> str:
    number = next_number(root)
    return str(number).zfill(_number_width(number))


def _ensure_sections(sections: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for name in SECTION_NAMES:
        value = sections.get(name, "").rstrip()
        if name == "Open Questions" and not value:
            value = "- none"
        if name == "Revisions" and not value:
            value = "(none yet)"
        normalized[name] = value
    return normalized


def _validate_section_keys(record: BrainstormRecord) -> None:
    missing = [name for name in SECTION_NAMES if name not in record.sections]
    if missing:
        raise ValueError(f"Missing required section headings {missing} in {record.path}")


def _validate_filename_prefix(record: BrainstormRecord) -> None:
    prefix = record.path.name.split("-", 1)[0]
    if prefix != record.number:
        raise ValueError(
            f"Brainstorm header number '{record.number}' does not match filename prefix '{prefix}' in {record.path}"
        )


def _validate_state_transition(current: str, target: str) -> None:
    if current == target:
        return
    allowed = ALLOWED_STATE_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(f"Illegal brainstorm status transition '{current}' -> '{target}'")


def root_from_record_path(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.parent.name != "brainstorm":
        raise ValueError(f"Brainstorm record must live under a 'brainstorm/' directory: {path}")
    return resolved.parent.parent


def render_record(record: BrainstormRecord) -> str:
    lines = [
        f"# Brainstorm {record.number}: {record.title}",
        "",
        f"**Status**: {record.status}",
        f"**Created**: {record.created}",
        f"**Updated**: {record.updated}",
        f"**Downstream**: {record.downstream}",
        "",
    ]
    sections = _ensure_sections(record.sections)
    for name in SECTION_NAMES:
        lines.append(f"## {name}")
        value = sections[name]
        if value:
            lines.append(value)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _escape_table_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def parse_record(path: Path) -> BrainstormRecord:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines:
        raise ValueError(f"Empty brainstorm record: {path}")
    title_match = TITLE_RE.match(lines[0].strip())
    if not title_match:
        raise ValueError(f"Invalid brainstorm title line in {path}")

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
            section_name = section_match.group("section")
            if section_name is not None:
                current_section = section_name
                sections.setdefault(section_name, [])
            continue
        if current_section is not None:
            sections[current_section].append(line)

    present_sections = [name for name in sections if name in SECTION_NAMES]
    if present_sections != SECTION_NAMES:
        raise ValueError(f"Brainstorm record must contain section headings in canonical order in {path}")

    rendered_sections: dict[str, str] = {
        name: "\n".join(sections.get(name, [])).strip()
        for name in SECTION_NAMES
    }
    record = BrainstormRecord(
        number=title_match.group("number"),
        title=title_match.group("title").strip(),
        slug=path.stem.split("-", 1)[1] if "-" in path.stem else slugify(title_match.group("title")),
        status=metadata.get("Status", "active"),
        created=metadata.get("Created", ""),
        updated=metadata.get("Updated", ""),
        downstream=_normalize_downstream(metadata.get("Downstream")),
        sections=_ensure_sections(rendered_sections),
        path=path,
    )
    validate_record(record)
    return record


def validate_record(record: BrainstormRecord) -> None:
    if record.status not in VALID_STATUSES:
        raise ValueError(f"Invalid brainstorm status '{record.status}' in {record.path}")
    if not record.number.isdigit():
        raise ValueError(f"Invalid brainstorm number '{record.number}' in {record.path}")
    if not record.slug:
        raise ValueError(f"Empty brainstorm slug in {record.path}")
    if not record.created or not record.updated:
        raise ValueError(f"Missing created/updated metadata in {record.path}")
    if record.updated < record.created:
        raise ValueError(f"Updated date precedes created date in {record.path}")
    if record.status == "spec-created" and record.downstream == "none":
        raise ValueError(f"spec-created brainstorm must include downstream metadata in {record.path}")
    _validate_filename_prefix(record)
    _validate_section_keys(record)


def create_record(
    root: Path,
    title: str,
    status: str,
    sections: dict[str, str],
    downstream: str = "none",
    created: str | None = None,
    updated: str | None = None,
) -> BrainstormRecord:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid brainstorm status '{status}'")
    created = created or _today()
    updated = updated or created
    number_str = next_number_string(root)
    slug = slugify(title)
    path = brainstorm_dir(root) / f"{number_str}-{slug}.md"
    record = BrainstormRecord(
        number=number_str,
        title=title.strip() or "Untitled Brainstorm",
        slug=slug,
        status=status,
        created=created,
        updated=updated,
        downstream=_normalize_downstream(downstream),
        sections=_ensure_sections(sections),
        path=path,
    )
    validate_record(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_record(record), encoding="utf-8")
    return record


def append_revision(
    path: Path,
    revision_summary: str,
    status: str | None = None,
    downstream: str | None = None,
    open_questions: Iterable[str] | None = None,
    ready_for_spec: str | None = None,
) -> BrainstormRecord:
    record = parse_record(path)
    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid brainstorm status '{status}'")
        _validate_state_transition(record.status, status)
        record.status = status
    if downstream is not None:
        record.downstream = _normalize_downstream(downstream)
    if ready_for_spec is not None:
        record.sections["Ready For Spec"] = ready_for_spec.strip()
    if open_questions:
        additions = [q.strip() for q in open_questions if q.strip()]
        existing = record.sections.get("Open Questions", "").strip()
        if existing in {"", "- none"}:
            existing = ""
        lines = [existing] if existing else []
        lines.extend(f"- {question}" for question in additions)
        record.sections["Open Questions"] = "\n".join(line for line in lines if line)
    existing_revisions = record.sections.get("Revisions", "").strip()
    if existing_revisions == "(none yet)":
        existing_revisions = ""
    revision_block = f"### {_today()} - Update\n{revision_summary.strip()}"
    record.sections["Revisions"] = f"{existing_revisions}\n\n{revision_block}".strip() if existing_revisions else revision_block
    record.updated = _today()
    validate_record(record)
    path.write_text(render_record(record), encoding="utf-8")
    return record


def find_matches(root: Path, title: str) -> list[MatchCandidate]:
    title_tokens = set(token for token in slugify(title).split("-") if token)
    candidates: list[MatchCandidate] = []
    for path in _brainstorm_files(root):
        record = parse_record(path)
        record_tokens = set(token for token in record.slug.split("-") if token)
        overlap = sorted(title_tokens & record_tokens)
        if overlap:
            candidates.append(
                MatchCandidate(
                    number=record.number,
                    title=record.title,
                    slug=record.slug,
                    status=record.status,
                    match_reason=f"keyword overlap: {', '.join(overlap)}",
                )
            )
    return candidates


def regenerate_overview(root: Path) -> Path:
    directory = brainstorm_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    records = [parse_record(path) for path in _brainstorm_files(root)]
    lines = [
        "# Brainstorm Overview",
        "",
        f"Last updated: {_today()}",
        "",
        "## Sessions",
        "",
        "| # | Date | Topic | Status | Downstream |",
        "|---|------|-------|--------|------------|",
    ]
    if records:
        for record in records:
            lines.append(
                "| "
                f"{record.number} | "
                f"{record.updated} | "
                f"{_escape_table_cell(record.title)} | "
                f"{record.status} | "
                f"{_escape_table_cell(record.downstream)} |"
            )
    else:
        lines.append("| (none) | - | - | - | - |")

    open_threads: list[str] = []
    parked: list[str] = []
    for record in records:
        raw = record.sections.get("Open Questions", "").strip()
        if raw and raw != "- none":
            for line in raw.splitlines():
                cleaned = line.strip()
                if cleaned.startswith("- "):
                    cleaned = cleaned[2:]
                if cleaned:
                    open_threads.append(f"- {cleaned} (from #{record.number})")
        if record.status == "parked":
            parked.append(f"- #{record.number} {record.title}")

    lines.extend(["", "## Open Threads"])
    lines.extend(open_threads or ["(none)"])
    lines.extend(["", "## Parked Ideas"])
    lines.extend(parked or ["(none)"])

    target = overview_path(root)
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return target


def build_record_sections(args: argparse.Namespace) -> dict[str, str]:
    return _ensure_sections(
        {
            "Problem": args.problem,
            "Desired Outcome": args.desired_outcome,
            "Constraints": args.constraints,
            "Existing Context": args.existing_context,
            "Options Considered": args.options_considered,
            "Recommendation": args.recommendation,
            "Open Questions": "\n".join(f"- {item}" for item in (args.open_question or [])).strip(),
            "Ready For Spec": args.ready_for_spec,
            "Revisions": "",
        }
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Brainstorm memory helper utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a brainstorm record")
    create.add_argument("--root", type=Path, default=Path.cwd())
    create.add_argument("--title", required=True)
    create.add_argument("--status", default="active")
    create.add_argument("--downstream", default="none")
    create.add_argument("--problem", default="")
    create.add_argument("--desired-outcome", default="")
    create.add_argument("--constraints", default="")
    create.add_argument("--existing-context", default="")
    create.add_argument("--options-considered", default="")
    create.add_argument("--recommendation", default="")
    create.add_argument("--ready-for-spec", default="")
    create.add_argument("--open-question", action="append", default=[])
    create.add_argument("--explicit-preserve", action="store_true")

    update = subparsers.add_parser("update", help="Append a revision to a brainstorm record")
    update.add_argument("--path", type=Path, required=True)
    update.add_argument("--revision-summary", required=True)
    update.add_argument("--status")
    update.add_argument("--downstream")
    update.add_argument("--ready-for-spec")
    update.add_argument("--open-question", action="append", default=[])

    overview = subparsers.add_parser("regenerate-overview", help="Regenerate brainstorm overview")
    overview.add_argument("--root", type=Path, default=Path.cwd())

    matches = subparsers.add_parser("matches", help="Find matching brainstorms")
    matches.add_argument("--root", type=Path, default=Path.cwd())
    matches.add_argument("--title", required=True)

    inspect_cmd = subparsers.add_parser("inspect", help="Inspect a brainstorm record as JSON")
    inspect_cmd.add_argument("--path", type=Path, required=True)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "create":
        sections = build_record_sections(args)
        if not is_meaningful_session(sections, explicit_preserve=args.explicit_preserve):
            print(json.dumps({"created": False, "reason": "trivial-session"}))
            return 0
        record = create_record(
            root=args.root,
            title=args.title,
            status=args.status,
            sections=sections,
            downstream=args.downstream,
        )
        overview = regenerate_overview(args.root)
        print(json.dumps({"created": True, "path": str(record.path), "overview": str(overview)}, indent=2))
        return 0
    if args.command == "update":
        root = root_from_record_path(args.path)
        record = append_revision(
            args.path,
            revision_summary=args.revision_summary,
            status=args.status,
            downstream=args.downstream,
            open_questions=args.open_question,
            ready_for_spec=args.ready_for_spec,
        )
        overview = regenerate_overview(root)
        print(json.dumps({"updated": True, "path": str(record.path), "overview": str(overview)}, indent=2))
        return 0
    if args.command == "regenerate-overview":
        path = regenerate_overview(args.root)
        print(json.dumps({"overview": str(path)}, indent=2))
        return 0
    if args.command == "matches":
        candidates = [asdict(candidate) for candidate in find_matches(args.root, args.title)]
        print(json.dumps({"matches": candidates}, indent=2))
        return 0
    if args.command == "inspect":
        record = parse_record(args.path)
        payload = asdict(record)
        payload["path"] = str(record.path)
        print(json.dumps(payload, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
