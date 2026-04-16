"""Spec-lite runtime — the 013 intake primitive.

A spec-lite record is a single markdown file under
`.specify/orca/spec-lite/SL-NNN-<slug>.md` capturing a minimal
problem/solution/acceptance/files-affected shape. No phase gates,
no mandatory reviews, no promotion pathway.

See `specs/013-spec-lite/contracts/spec-lite-record.md` for the
on-disk contract this module implements.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import re
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterator


VALID_STATUSES: tuple[str, ...] = ("open", "implemented", "abandoned")

# Exact body-section names (case-sensitive, ordered).
REQUIRED_SECTIONS: tuple[str, ...] = (
    "Problem",
    "Solution",
    "Acceptance Scenario",
    "Files Affected",
)
OPTIONAL_SECTIONS: tuple[str, ...] = ("Verification Evidence",)
KNOWN_SECTIONS: tuple[str, ...] = REQUIRED_SECTIONS + OPTIONAL_SECTIONS

TITLE_RE = re.compile(r"^# Spec-Lite (?P<record_id>SL-\d{3}): (?P<title>.+)$")
META_RE = re.compile(
    r"^\*\*(?P<key>Source Name|Created|Status)\*\*: (?P<value>.*)$"
)
SECTION_RE = re.compile(r"^## (?P<section>.+?)\s*(?:\(optional\))?$")
ID_STEM_RE = re.compile(r"^SL-(\d{3})(?:-(.+))?$")
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


SPEC_LITE_DIRNAME = ".specify/orca/spec-lite"
OVERVIEW_FILENAME = "00-overview.md"


class SpecLiteError(Exception):
    """Raised for any spec-lite runtime or validation failure."""


class SpecLiteParseError(SpecLiteError):
    """Raised when parsing a record fails structurally."""

    def __init__(self, path: Path, line_no: int, message: str) -> None:
        self.path = path
        self.line_no = line_no
        super().__init__(f"{path}:{line_no}: {message}")


@dataclass
class SpecLiteRecord:
    record_id: str           # "SL-001"
    slug: str                # "cs2-team-stats-sync"
    title: str
    source_name: str
    created: str             # "YYYY-MM-DD"
    status: str              # open | implemented | abandoned
    problem: str
    solution: str
    acceptance_scenario: str
    files_affected: list[str]
    verification_evidence: str | None
    path: Path

    @property
    def id_with_slug(self) -> str:
        return f"{self.record_id}-{self.slug}" if self.slug else self.record_id

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["path"] = str(self.path)
        return payload


def _spec_lite_dir(repo_root: Path) -> Path:
    return repo_root / SPEC_LITE_DIRNAME


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def _spec_lite_lock(repo_root: Path) -> Iterator[None]:
    """Repo-level advisory lock covering id allocation + record write
    + overview regeneration.

    Two concurrent `create_record` calls must not race to pick the
    same `SL-NNN` id. The lock file sits at
    `.specify/orca/spec-lite/.lock` and uses `fcntl.flock` for an
    exclusive POSIX advisory lock. This serializes `create_record`
    and `update_status` across processes. Within a single process,
    it also serializes across threads because each `flock` call
    blocks until the prior lock is released.
    """
    directory = _ensure_dir(_spec_lite_dir(repo_root))
    lock_path = directory / ".lock"
    fd = None
    try:
        # Open in append mode so the file is created if missing and
        # existing contents (if any) are not truncated.
        fd = open(lock_path, "a")
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            fd.close()


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _slugify(title: str) -> str:
    lowered = title.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if not cleaned:
        raise SpecLiteError(f"Title produces empty slug: {title!r}")
    return cleaned


def _today() -> str:
    return date.today().isoformat()


def _next_record_id(repo_root: Path) -> str:
    """Return the next available SL-NNN id string.

    Scans `.specify/orca/spec-lite/SL-*.md` and picks the max NNN+1.
    Gaps are not backfilled.
    """
    directory = _spec_lite_dir(repo_root)
    max_number = 0
    if directory.is_dir():
        for entry in directory.glob("SL-*.md"):
            if entry.name == OVERVIEW_FILENAME:
                continue
            # Companion review artifacts share the record's NNN but
            # are not records themselves — don't let their presence
            # inflate the next allocated id if a record happens to
            # be missing.
            if entry.name.endswith(".self-review.md") or entry.name.endswith(".cross-review.md"):
                continue
            match = ID_STEM_RE.match(entry.stem)
            if not match:
                continue
            max_number = max(max_number, int(match.group(1)))
    return f"SL-{max_number + 1:03d}"


def _render_record(record: SpecLiteRecord) -> str:
    lines: list[str] = []
    lines.append(f"# Spec-Lite {record.record_id}: {record.title}")
    lines.append("")
    lines.append(f"**Source Name**: {record.source_name}")
    lines.append(f"**Created**: {record.created}")
    lines.append(f"**Status**: {record.status}")
    lines.append("")
    lines.append("## Problem")
    lines.append(record.problem.strip())
    lines.append("")
    lines.append("## Solution")
    lines.append(record.solution.strip())
    lines.append("")
    lines.append("## Acceptance Scenario")
    lines.append(record.acceptance_scenario.strip())
    lines.append("")
    lines.append("## Files Affected")
    for entry in record.files_affected:
        lines.append(f"- {entry}")
    lines.append("")
    if record.verification_evidence is not None:
        lines.append("## Verification Evidence")
        lines.append(record.verification_evidence.strip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _parse_record_text(path: Path, text: str) -> SpecLiteRecord:
    lines = text.splitlines()
    if not lines:
        raise SpecLiteParseError(path, 1, "empty file")

    # Title
    title_match = TITLE_RE.match(lines[0])
    if not title_match:
        raise SpecLiteParseError(
            path, 1,
            "first line must match '# Spec-Lite SL-NNN: <title>'",
        )
    record_id = title_match.group("record_id")
    title = title_match.group("title").strip()

    # Derive slug from filename stem
    stem_match = ID_STEM_RE.match(path.stem)
    slug = stem_match.group(2) if stem_match and stem_match.group(2) else ""

    # Metadata block: after title, before first ## heading
    metadata: dict[str, str] = {}
    index = 1
    while index < len(lines):
        raw = lines[index]
        if raw.startswith("## "):
            break
        if raw.strip():
            meta_match = META_RE.match(raw)
            if meta_match:
                key = meta_match.group("key")
                value = meta_match.group("value")
                if key is not None and value is not None:
                    metadata[key] = value.strip()
            # Unknown `**Other**: value` lines are tolerated but ignored,
            # per the 013 contract: "additional metadata lines are
            # ignored by parsers but discouraged."
            # Any non-empty line that isn't a recognized metadata field
            # is silently skipped.
        index += 1

    for required in ("Source Name", "Created", "Status"):
        if required not in metadata:
            raise SpecLiteParseError(
                path, 1, f"missing metadata field: {required}",
            )

    source_name = metadata["Source Name"]
    created = metadata["Created"]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", created):
        raise SpecLiteParseError(
            path, 1, f"Created must be YYYY-MM-DD, got {created!r}",
        )
    try:
        date.fromisoformat(created)
    except ValueError as exc:
        raise SpecLiteParseError(
            path, 1, f"Created must be a valid calendar date, got {created!r}",
        ) from exc
    status = metadata["Status"]
    if status not in VALID_STATUSES:
        raise SpecLiteParseError(
            path, 1,
            f"Status must be one of {VALID_STATUSES}, got {status!r}",
        )

    # Body sections — enforce order (per 013 contract), reject
    # duplicates, reject unknown sections.
    sections: dict[str, list[str]] = {}
    section_order: list[str] = []
    current: str | None = None
    section_start_line = index
    for line_no in range(index, len(lines)):
        raw = lines[line_no]
        section_match = SECTION_RE.match(raw)
        if section_match:
            section_name = (section_match.group("section") or "").strip()
            if section_name not in KNOWN_SECTIONS:
                raise SpecLiteParseError(
                    path, line_no + 1,
                    f"unknown section heading: {section_name!r}",
                )
            if section_name in sections:
                raise SpecLiteParseError(
                    path, line_no + 1,
                    f"duplicate section heading: {section_name!r}",
                )
            current = section_name
            sections[section_name] = []
            section_order.append(section_name)
        elif current is not None:
            sections[current].append(raw)

    # Verify recognized-section ordering: required sections must
    # appear in the listed relative order; the optional section
    # (if present) comes after.
    expected_order = [s for s in KNOWN_SECTIONS if s in sections]
    if section_order != expected_order:
        raise SpecLiteParseError(
            path, section_start_line + 1,
            f"section order violates contract: got {section_order}, "
            f"expected {expected_order}",
        )

    for required in REQUIRED_SECTIONS:
        if required not in sections:
            raise SpecLiteParseError(
                path, section_start_line + 1,
                f"missing required section: {required}",
            )

    body_text: dict[str, str] = {}
    for name, body_lines in sections.items():
        body = "\n".join(body_lines).strip()
        if not body:
            if name in OPTIONAL_SECTIONS:
                raise SpecLiteParseError(
                    path, 1,
                    f"optional section {name!r} present but empty",
                )
            raise SpecLiteParseError(
                path, 1, f"required section {name!r} is empty",
            )
        body_text[name] = body

    files_affected = [
        re.sub(r"^[-*]\s*", "", line).strip()
        for line in body_text["Files Affected"].splitlines()
        if line.strip() and line.strip() != "-"
    ]
    files_affected = [f for f in files_affected if f]
    if not files_affected:
        raise SpecLiteParseError(
            path, 1, "Files Affected must list at least one path",
        )

    verification = body_text.get("Verification Evidence")

    return SpecLiteRecord(
        record_id=record_id,
        slug=slug,
        title=title,
        source_name=source_name,
        created=created,
        status=status,
        problem=body_text["Problem"],
        solution=body_text["Solution"],
        acceptance_scenario=body_text["Acceptance Scenario"],
        files_affected=files_affected,
        verification_evidence=verification,
        path=path,
    )


def parse_record(path: Path) -> SpecLiteRecord:
    """Parse a spec-lite record file. Raises SpecLiteError on failure.

    IO and encoding errors from `read_text` are wrapped in
    `SpecLiteError` so callers (e.g., `compute_spec_lite_state`)
    that catch `SpecLiteError` degrade gracefully to the tolerant
    `invalid` view instead of crashing.
    """
    if not path.exists():
        raise SpecLiteError(f"Record file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SpecLiteError(f"Could not read record file: {path}") from exc
    return _parse_record_text(path, text)


def _find_record_path(repo_root: Path, record_id: str) -> Path:
    """Resolve a record path from an ID (with or without slug)."""
    directory = _spec_lite_dir(repo_root)
    if not directory.is_dir():
        raise SpecLiteError(f"No spec-lite registry at {directory}")

    stem_match = ID_STEM_RE.match(record_id)
    if not stem_match:
        raise SpecLiteError(f"Invalid record id: {record_id!r}")

    # Exact stem + extension
    candidate = directory / f"{record_id}.md"
    if candidate.exists():
        return candidate

    # Glob by NNN prefix — explicitly exclude companion review
    # artifacts so bare-ID lookups like `get_record("SL-001")` are
    # never ambiguous when reviews exist.
    prefix = f"SL-{stem_match.group(1)}"
    matches = [
        entry for entry in directory.glob(f"{prefix}*.md")
        if entry.name != OVERVIEW_FILENAME
        and not entry.name.endswith(".self-review.md")
        and not entry.name.endswith(".cross-review.md")
    ]
    # Filter to those that actually share the stem
    matches = [
        entry for entry in matches
        if entry.stem == prefix or entry.stem.startswith(prefix + "-")
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise SpecLiteError(f"Record not found: {record_id}")
    raise SpecLiteError(
        f"Record id {record_id!r} is ambiguous: {[m.name for m in matches]}"
    )


def create_record(
    *,
    repo_root: Path,
    title: str,
    problem: str,
    solution: str,
    acceptance: str,
    files_affected: list[str],
    source_name: str = "operator",
    created: str | None = None,
) -> SpecLiteRecord:
    """Create a new spec-lite record with the next available ID.

    Id allocation, the record write, and overview regeneration run
    under a repo-level advisory lock so concurrent callers cannot
    pick the same `SL-NNN` and clobber each other.
    """
    stripped_files = [f.strip() for f in files_affected if f and f.strip()]
    if not stripped_files:
        raise SpecLiteError(
            "files_affected must have at least one non-empty entry"
        )

    # Validate required body sections are non-empty after stripping.
    # If these are blank, the parser will reject the written file on
    # the next read, leaving a ghost record on disk. Fail up-front
    # instead.
    stripped_problem = problem.strip()
    stripped_solution = solution.strip()
    stripped_acceptance = acceptance.strip()
    if not stripped_problem or not stripped_solution or not stripped_acceptance:
        raise SpecLiteError(
            "problem, solution, and acceptance must each be non-empty"
        )

    # Validate optional `created` argument matches the strict
    # YYYY-MM-DD format AND is a real calendar date. `date.fromisoformat`
    # alone accepts values like `20260415` that the on-disk parser
    # regex would later reject.
    if created is not None:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", created):
            raise SpecLiteError(
                f"created must use YYYY-MM-DD format, got {created!r}"
            )
        try:
            date.fromisoformat(created)
        except ValueError as exc:
            raise SpecLiteError(
                f"created must be a valid YYYY-MM-DD date, got {created!r}"
            ) from exc

    with _spec_lite_lock(repo_root):
        directory = _ensure_dir(_spec_lite_dir(repo_root))
        record_id = _next_record_id(repo_root)
        slug = _slugify(title)
        record = SpecLiteRecord(
            record_id=record_id,
            slug=slug,
            title=title.strip(),
            source_name=source_name,
            created=created or _today(),
            status="open",
            problem=stripped_problem,
            solution=stripped_solution,
            acceptance_scenario=stripped_acceptance,
            files_affected=stripped_files,
            verification_evidence=None,
            path=directory / f"{record_id}-{slug}.md",
        )
        _atomic_write(record.path, _render_record(record))
        regenerate_overview(repo_root)
    return record


def list_records(
    *,
    repo_root: Path,
    status: str | None = None,
) -> list[SpecLiteRecord]:
    """List all records, optionally filtered by status."""
    if status is not None and status not in VALID_STATUSES:
        raise SpecLiteError(
            f"Invalid status filter {status!r}; expected one of {VALID_STATUSES}"
        )
    directory = _spec_lite_dir(repo_root)
    if not directory.is_dir():
        return []
    records: list[SpecLiteRecord] = []
    for entry in sorted(directory.glob("SL-*.md")):
        if entry.name == OVERVIEW_FILENAME:
            continue
        # Skip companion review artifacts explicitly so we don't
        # waste parse work on them (they would fail parsing anyway,
        # but skipping by name is cheaper and clearer).
        if entry.name.endswith(".self-review.md") or entry.name.endswith(".cross-review.md"):
            continue
        try:
            record = parse_record(entry)
        except SpecLiteError:
            # Broader catch (covers both SpecLiteParseError for
            # malformed markdown and the base SpecLiteError wrapping
            # read_text / UnicodeDecodeError failures) so a single
            # bad file under the registry doesn't abort listing —
            # which would also break regenerate_overview().
            continue
        if status is None or record.status == status:
            records.append(record)
    return records


def get_record(*, repo_root: Path, record_id: str) -> SpecLiteRecord:
    """Fetch a single record by its ID (with or without slug)."""
    path = _find_record_path(repo_root, record_id)
    return parse_record(path)


def update_status(
    *,
    repo_root: Path,
    record_id: str,
    new_status: str,
    verification_evidence: str | None = None,
) -> SpecLiteRecord:
    """Transition a record's status, optionally attaching verification evidence."""
    if new_status not in VALID_STATUSES:
        raise SpecLiteError(
            f"Invalid status {new_status!r}; expected one of {VALID_STATUSES}"
        )

    with _spec_lite_lock(repo_root):
        record = get_record(repo_root=repo_root, record_id=record_id)

        # Treat empty/whitespace-only verification_evidence the
        # same as None (no-op, preserving prior evidence). The
        # parser rejects optional sections with empty bodies, so
        # writing an empty section would produce a record the
        # parser later considers invalid — and callers who passed
        # whitespace-only input almost certainly did not intend to
        # wipe prior evidence.
        if verification_evidence is not None and verification_evidence.strip():
            new_evidence = verification_evidence.strip()
        else:
            new_evidence = record.verification_evidence

        updated = SpecLiteRecord(
            record_id=record.record_id,
            slug=record.slug,
            title=record.title,
            source_name=record.source_name,
            created=record.created,
            status=new_status,
            problem=record.problem,
            solution=record.solution,
            acceptance_scenario=record.acceptance_scenario,
            files_affected=record.files_affected,
            verification_evidence=new_evidence,
            path=record.path,
        )
        _atomic_write(updated.path, _render_record(updated))
        regenerate_overview(repo_root)
    return updated


def _overview_group(records: list[SpecLiteRecord], status: str) -> list[str]:
    lines: list[str] = []
    filtered = [r for r in records if r.status == status]
    for record in sorted(filtered, key=lambda r: r.record_id):
        stem = f"{record.record_id}-{record.slug}" if record.slug else record.record_id
        lines.append(
            f"- **[{record.record_id}](./{stem}.md)** — "
            f"{record.title} _(created {record.created})_"
        )
    return lines


def _render_overview(records: list[SpecLiteRecord]) -> str:
    active_lines = _overview_group(records, "open")
    implemented_lines = _overview_group(records, "implemented")
    abandoned_lines = _overview_group(records, "abandoned")

    lines: list[str] = []
    lines.append("# Spec-Lite Overview")
    lines.append("")
    lines.append(
        "_Generated by `speckit_orca.spec_lite regenerate-overview`. Do not edit by hand._"
    )
    lines.append("")
    lines.append("## Active records (`open`)")
    lines.append("")
    if active_lines:
        lines.extend(active_lines)
    else:
        lines.append("_No active records._")
    lines.append("")
    lines.append("## Implemented records")
    lines.append("")
    if implemented_lines:
        lines.extend(implemented_lines)
    else:
        lines.append("_No implemented records._")
    lines.append("")
    lines.append("## Abandoned records")
    lines.append("")
    if abandoned_lines:
        lines.extend(abandoned_lines)
    else:
        lines.append("_No abandoned records._")
    lines.append("")
    return "\n".join(lines)


def regenerate_overview(repo_root: Path) -> Path:
    """Rewrite the 00-overview.md index from the current registry state."""
    directory = _ensure_dir(_spec_lite_dir(repo_root))
    records = list_records(repo_root=repo_root)
    overview_path = directory / OVERVIEW_FILENAME
    _atomic_write(overview_path, _render_overview(records))
    return overview_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m speckit_orca.spec_lite",
        description="Spec-lite record runtime (013).",
    )
    parser.add_argument(
        "--root", default=".", help="Repository root (defaults to cwd)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list", help="List records grouped by status")
    list_p.add_argument(
        "--status", choices=list(VALID_STATUSES), default=None,
        help="Filter by status",
    )
    list_p.add_argument("--json", action="store_true", help="Emit JSON")

    create_p = sub.add_parser("create", help="Create a new record")
    create_p.add_argument("--title", required=True)
    create_p.add_argument("--problem", required=True)
    create_p.add_argument("--solution", required=True)
    create_p.add_argument("--acceptance", required=True)
    create_p.add_argument(
        "--files-affected", required=True,
        help="Comma-separated list of file paths",
    )
    create_p.add_argument(
        "--source-name", default="operator",
        help="Operator or agent identifier (default: operator)",
    )
    create_p.add_argument(
        "--created", default=None,
        help="Override the Created date (YYYY-MM-DD). Defaults to today.",
    )
    create_p.add_argument("--json", action="store_true", help="Emit JSON")

    get_p = sub.add_parser("get", help="Show a single record by id")
    get_p.add_argument("record_id")
    get_p.add_argument("--json", action="store_true", help="Emit JSON")

    update_p = sub.add_parser("update-status", help="Change a record's status")
    update_p.add_argument("record_id")
    update_p.add_argument("new_status", choices=list(VALID_STATUSES))
    update_p.add_argument(
        "--verification-evidence", default=None,
        help="Optional verification evidence text to attach",
    )
    update_p.add_argument("--json", action="store_true", help="Emit JSON")

    sub.add_parser("regenerate-overview", help="Rewrite 00-overview.md")

    return parser.parse_args(argv)


def _print_record(record: SpecLiteRecord, as_json: bool) -> None:
    if as_json:
        print(json.dumps(record.to_dict(), indent=2))
    else:
        print(f"{record.record_id}-{record.slug}  [{record.status}]  {record.title}")


def cli_main(argv: list[str] | None = None) -> int:
    args = _parse_cli_args(argv)
    repo_root = Path(args.root).resolve()

    try:
        if args.command == "list":
            records = list_records(repo_root=repo_root, status=args.status)
            if args.json:
                print(json.dumps([r.to_dict() for r in records], indent=2))
            else:
                if not records:
                    print("No spec-lite records.")
                else:
                    for record in records:
                        _print_record(record, False)
            return 0

        if args.command == "create":
            files = [f.strip() for f in args.files_affected.split(",") if f.strip()]
            record = create_record(
                repo_root=repo_root,
                title=args.title,
                problem=args.problem,
                solution=args.solution,
                acceptance=args.acceptance,
                files_affected=files,
                source_name=args.source_name,
                created=args.created,
            )
            _print_record(record, args.json)
            return 0

        if args.command == "get":
            record = get_record(repo_root=repo_root, record_id=args.record_id)
            if args.json:
                print(json.dumps(record.to_dict(), indent=2))
            else:
                print(_render_record(record).rstrip())
            return 0

        if args.command == "update-status":
            record = update_status(
                repo_root=repo_root,
                record_id=args.record_id,
                new_status=args.new_status,
                verification_evidence=args.verification_evidence,
            )
            _print_record(record, args.json)
            return 0

        if args.command == "regenerate-overview":
            path = regenerate_overview(repo_root)
            print(f"Regenerated {path}")
            return 0

    except SpecLiteError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(cli_main())
