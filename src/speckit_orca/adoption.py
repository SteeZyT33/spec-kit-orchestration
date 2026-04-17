"""Adoption record runtime — the 015 brownfield intake primitive.

An adoption record is a single markdown file under
`.specify/orca/adopted/AR-NNN-<slug>.md` describing an existing
feature's shape, location, and observed behaviors. Reference-only:
never reviewed, never drivable by yolo, never anchors a matriarch
lane.

See `specs/015-brownfield-adoption/contracts/adoption-record.md`
for the on-disk contract this module implements.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import re
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterator


VALID_STATUSES: tuple[str, ...] = ("adopted", "superseded", "retired")

# Recognized body sections, in the relative order the 015 contract
# requires. Required sections must appear; optional sections may be
# absent. Unknown sections are tolerated and captured in an `extra`
# bucket on the parsed record.
REQUIRED_SECTIONS: tuple[str, ...] = (
    "Summary",
    "Location",
    "Key Behaviors",
)
OPTIONAL_SECTIONS: tuple[str, ...] = (
    "Known Gaps",
    "Superseded By",
    "Retirement Reason",
)
RECOGNIZED_SECTIONS: tuple[str, ...] = REQUIRED_SECTIONS + OPTIONAL_SECTIONS

TITLE_RE = re.compile(
    r"^# Adoption Record: (?P<record_id>AR-\d{3}): (?P<title>.+)$"
)
META_RE = re.compile(
    r"^\*\*(?P<key>Status|Adopted-on|Baseline Commit)\*\*: (?P<value>.*)$"
)
SECTION_RE = re.compile(r"^## (?P<section>.+?)\s*$")
ID_STEM_RE = re.compile(r"^AR-(\d{3})(?:-(.+))?$")


ADOPTED_DIRNAME = ".specify/orca/adopted"
OVERVIEW_FILENAME = "00-overview.md"


class AdoptionError(Exception):
    """Raised for any adoption runtime or validation failure."""


class AdoptionParseError(AdoptionError):
    """Raised when parsing a record fails structurally."""

    def __init__(self, path: Path, line_no: int, message: str) -> None:
        self.path = path
        self.line_no = line_no
        super().__init__(f"{path}:{line_no}: {message}")


@dataclass
class AdoptionRecord:
    record_id: str           # "AR-001"
    slug: str                # "cli-entrypoint"
    title: str
    status: str              # adopted | superseded | retired
    adopted_on: str          # "YYYY-MM-DD"
    baseline_commit: str | None
    summary: str
    location: list[str]
    key_behaviors: list[str]
    known_gaps: str | None
    superseded_by: str | None
    retirement_reason: str | None
    path: Path
    extra: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["path"] = str(self.path)
        return payload


def _adopted_dir(repo_root: Path) -> Path:
    return repo_root / ADOPTED_DIRNAME


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def _adoption_lock(repo_root: Path) -> Iterator[None]:
    """Repo-level advisory lock covering id allocation + record
    write + overview regeneration.

    Same pattern as 013's `_spec_lite_lock`: two concurrent
    `create_record` calls must not race to pick the same `AR-NNN`
    id. The lock file sits at `.specify/orca/adopted/.lock` and
    uses `fcntl.flock` for an exclusive POSIX advisory lock.
    """
    directory = _ensure_dir(_adopted_dir(repo_root))
    lock_path = directory / ".lock"
    fd = None
    try:
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
        raise AdoptionError(f"Title produces empty slug: {title!r}")
    return cleaned


def _today() -> str:
    return date.today().isoformat()


def _git_head_sha(repo_root: Path) -> str | None:
    """Return the HEAD commit SHA for pre-populating Baseline Commit.

    Defensive fallback: if the workspace is not a git repo or `git`
    is unavailable, returns None and the field is omitted (per
    plan open question 3). Never raises.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    sha = result.stdout.strip()
    return sha or None


def _next_record_id(repo_root: Path) -> str:
    """Return the next available AR-NNN id string. Gaps not backfilled."""
    directory = _adopted_dir(repo_root)
    max_number = 0
    if directory.is_dir():
        for entry in directory.glob("AR-*.md"):
            if entry.name == OVERVIEW_FILENAME:
                continue
            match = ID_STEM_RE.match(entry.stem)
            if not match:
                continue
            max_number = max(max_number, int(match.group(1)))
    return f"AR-{max_number + 1:03d}"


def _render_record(record: AdoptionRecord) -> str:
    lines: list[str] = []
    lines.append(f"# Adoption Record: {record.record_id}: {record.title}")
    lines.append("")
    lines.append(f"**Status**: {record.status}")
    lines.append(f"**Adopted-on**: {record.adopted_on}")
    if record.baseline_commit is not None:
        lines.append(f"**Baseline Commit**: {record.baseline_commit}")
    lines.append("")
    lines.append("## Summary")
    lines.append(record.summary.strip())
    lines.append("")
    lines.append("## Location")
    for entry in record.location:
        lines.append(f"- {entry}")
    lines.append("")
    lines.append("## Key Behaviors")
    for entry in record.key_behaviors:
        lines.append(f"- {entry}")
    lines.append("")
    if record.known_gaps is not None:
        lines.append("## Known Gaps")
        lines.append(record.known_gaps.strip())
        lines.append("")
    if record.superseded_by is not None:
        lines.append("## Superseded By")
        lines.append(record.superseded_by.strip())
        lines.append("")
    if record.retirement_reason is not None:
        lines.append("## Retirement Reason")
        lines.append(record.retirement_reason.strip())
        lines.append("")
    # Preserve operator-authored unknown sections that the tolerant
    # parser captured in the `extra` bucket. Without this, running
    # supersede/retire would silently drop any hand-added sections —
    # violating the tolerant-parser contract.
    for section_name, section_body in record.extra.items():
        lines.append(f"## {section_name}")
        if section_body:
            lines.append(section_body)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_record_text(path: Path, text: str) -> AdoptionRecord:
    """Public entry point for parsing an AR body without touching disk.

    Used by 017's onboarding runtime to validate drafts through the
    same parser as real records. Keeping this public gives downstream
    modules a stable contract instead of reaching for the private
    helper.
    """
    return _parse_record_text(path, text)


def _parse_record_text(path: Path, text: str) -> AdoptionRecord:
    lines = text.splitlines()
    if not lines:
        raise AdoptionParseError(path, 1, "empty file")

    # Title
    title_match = TITLE_RE.match(lines[0])
    if not title_match:
        raise AdoptionParseError(
            path, 1,
            "first line must match '# Adoption Record: AR-NNN: <title>'",
        )
    record_id = title_match.group("record_id")
    title = title_match.group("title").strip()

    # Derive slug from filename stem
    stem_match = ID_STEM_RE.match(path.stem)
    slug = stem_match.group(2) if stem_match and stem_match.group(2) else ""

    # Metadata block: after title, before first `##` heading.
    # Tolerant: unknown `**Key**: value` lines are silently
    # ignored per the 015 contract.
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
                    if key in metadata:
                        raise AdoptionParseError(
                            path, index + 1,
                            f"duplicate metadata field: {key!r}",
                        )
                    metadata[key] = value.strip()
            # Unknown metadata lines ignored.
        index += 1

    for required in ("Status", "Adopted-on"):
        if required not in metadata:
            raise AdoptionParseError(
                path, 1, f"missing required metadata field: {required}",
            )

    status = metadata["Status"]
    if status not in VALID_STATUSES:
        raise AdoptionParseError(
            path, 1,
            f"Status must be one of {VALID_STATUSES}, got {status!r}",
        )

    adopted_on = metadata["Adopted-on"]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", adopted_on):
        raise AdoptionParseError(
            path, 1,
            f"Adopted-on must be YYYY-MM-DD, got {adopted_on!r}",
        )
    try:
        date.fromisoformat(adopted_on)
    except ValueError as exc:
        raise AdoptionParseError(
            path, 1,
            f"Adopted-on must be a valid calendar date, got {adopted_on!r}",
        ) from exc

    baseline_commit = metadata.get("Baseline Commit") or None

    # Body sections — enforce relative order of recognized sections,
    # reject duplicates of recognized sections. Unknown sections go
    # into the `extra` bucket (tolerant-parser posture per 015
    # contract).
    sections: dict[str, list[str]] = {}
    extra_sections: dict[str, list[str]] = {}
    recognized_order: list[str] = []
    current: str | None = None
    current_is_recognized: bool = False
    section_start_line = index
    for line_no in range(index, len(lines)):
        raw = lines[line_no]
        section_match = SECTION_RE.match(raw)
        if section_match:
            section_name = (section_match.group("section") or "").strip()
            if section_name in RECOGNIZED_SECTIONS:
                if section_name in sections:
                    raise AdoptionParseError(
                        path, line_no + 1,
                        f"duplicate section heading: {section_name!r}",
                    )
                current = section_name
                current_is_recognized = True
                sections[section_name] = []
                recognized_order.append(section_name)
            else:
                # Unknown section — captured in extra bucket, may
                # appear in any position without violating the
                # recognized-section ordering rule. If the same
                # unknown heading repeats, append to the existing
                # list instead of overwriting.
                current = section_name
                current_is_recognized = False
                if section_name not in extra_sections:
                    extra_sections[section_name] = []
        elif current is not None:
            if current_is_recognized:
                sections[current].append(raw)
            else:
                extra_sections[current].append(raw)

    for required in REQUIRED_SECTIONS:
        if required not in sections:
            raise AdoptionParseError(
                path, section_start_line + 1,
                f"missing required section: {required}",
            )

    # Verify recognized-section relative ordering.
    expected_order = [s for s in RECOGNIZED_SECTIONS if s in sections]
    if recognized_order != expected_order:
        raise AdoptionParseError(
            path, section_start_line + 1,
            f"recognized sections must appear in order {expected_order}, "
            f"got {recognized_order}",
        )

    body_text: dict[str, str] = {}
    for name, body_lines in sections.items():
        body = "\n".join(body_lines).strip()
        if not body:
            if name in OPTIONAL_SECTIONS:
                raise AdoptionParseError(
                    path, 1,
                    f"optional section {name!r} present but empty",
                )
            raise AdoptionParseError(
                path, 1, f"required section {name!r} is empty",
            )
        body_text[name] = body

    location = [
        re.sub(r"^[-*]\s*", "", line).strip()
        for line in body_text["Location"].splitlines()
        if line.strip() and line.strip() != "-"
    ]
    location = [p for p in location if p]
    if not location:
        raise AdoptionParseError(
            path, 1, "Location must list at least one path",
        )

    key_behaviors = [
        re.sub(r"^[-*]\s*", "", line).strip()
        for line in body_text["Key Behaviors"].splitlines()
        if line.strip() and line.strip() != "-"
    ]
    key_behaviors = [b for b in key_behaviors if b]
    if not key_behaviors:
        raise AdoptionParseError(
            path, 1, "Key Behaviors must list at least one bullet",
        )

    extra_bodies: dict[str, str] = {
        name: "\n".join(body_lines).strip()
        for name, body_lines in extra_sections.items()
    }

    return AdoptionRecord(
        record_id=record_id,
        slug=slug,
        title=title,
        status=status,
        adopted_on=adopted_on,
        baseline_commit=baseline_commit,
        summary=body_text["Summary"],
        location=location,
        key_behaviors=key_behaviors,
        known_gaps=body_text.get("Known Gaps"),
        superseded_by=body_text.get("Superseded By"),
        retirement_reason=body_text.get("Retirement Reason"),
        path=path,
        extra=extra_bodies,
    )


def parse_record(path: Path) -> AdoptionRecord:
    """Parse an adoption record. Raises AdoptionError on failure.

    IO and encoding errors are wrapped so callers like
    `compute_adoption_state` can catch `AdoptionError` and degrade
    to the tolerant `invalid` view instead of crashing.
    """
    if not path.exists():
        raise AdoptionError(f"Record file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AdoptionError(f"Could not read record file: {path}") from exc
    return _parse_record_text(path, text)


def _find_record_path(repo_root: Path, record_id: str) -> Path:
    """Resolve a record path from an ID (with or without slug)."""
    directory = _adopted_dir(repo_root)
    if not directory.is_dir():
        raise AdoptionError(f"No adopted registry at {directory}")

    stem_match = ID_STEM_RE.match(record_id)
    if not stem_match:
        raise AdoptionError(f"Invalid record id: {record_id!r}")

    # Exact stem + extension
    candidate = directory / f"{record_id}.md"
    if candidate.exists():
        return candidate

    # Glob by NNN prefix, excluding the overview file.
    prefix = f"AR-{stem_match.group(1)}"
    matches = [
        entry for entry in directory.glob(f"{prefix}*.md")
        if entry.name != OVERVIEW_FILENAME
    ]
    matches = [
        entry for entry in matches
        if entry.stem == prefix or entry.stem.startswith(prefix + "-")
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise AdoptionError(f"Record not found: {record_id}")
    raise AdoptionError(
        f"Record id {record_id!r} is ambiguous: {[m.name for m in matches]}"
    )


def create_record(
    *,
    repo_root: Path,
    title: str,
    summary: str,
    location: list[str],
    key_behaviors: list[str],
    known_gaps: str | None = None,
    baseline_commit: str | None = "__HEAD__",
    adopted_on: str | None = None,
) -> AdoptionRecord:
    """Create a new adoption record with the next available ID.

    `baseline_commit` defaults to the sentinel `"__HEAD__"` which
    triggers `git rev-parse HEAD` lookup; pass `None` to explicitly
    omit the field, or pass an explicit SHA string to pin it.
    Id allocation + record write + overview regeneration run under
    an advisory lock.
    """
    stripped_location = [p.strip() for p in location if p and p.strip()]
    if not stripped_location:
        raise AdoptionError(
            "location must have at least one non-empty entry"
        )

    stripped_behaviors = [b.strip() for b in key_behaviors if b and b.strip()]
    if not stripped_behaviors:
        raise AdoptionError(
            "key_behaviors must have at least one non-empty entry"
        )

    stripped_summary = summary.strip()
    if not stripped_summary:
        raise AdoptionError("summary must be non-empty")

    if adopted_on is not None:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", adopted_on):
            raise AdoptionError(
                f"adopted_on must use YYYY-MM-DD format, got {adopted_on!r}"
            )
        try:
            date.fromisoformat(adopted_on)
        except ValueError as exc:
            raise AdoptionError(
                f"adopted_on must be a valid calendar date, got {adopted_on!r}"
            ) from exc

    with _adoption_lock(repo_root):
        directory = _ensure_dir(_adopted_dir(repo_root))
        record_id = _next_record_id(repo_root)
        slug = _slugify(title)

        # Resolve baseline_commit: "__HEAD__" sentinel → git lookup,
        # None → omit, any string → persist as-is.
        if baseline_commit == "__HEAD__":
            resolved_baseline = _git_head_sha(repo_root)
        else:
            resolved_baseline = baseline_commit

        stripped_gaps = known_gaps.strip() if known_gaps else None
        if stripped_gaps == "":
            stripped_gaps = None

        record = AdoptionRecord(
            record_id=record_id,
            slug=slug,
            title=title.strip(),
            status="adopted",
            adopted_on=adopted_on or _today(),
            baseline_commit=resolved_baseline,
            summary=stripped_summary,
            location=stripped_location,
            key_behaviors=stripped_behaviors,
            known_gaps=stripped_gaps,
            superseded_by=None,
            retirement_reason=None,
            path=directory / f"{record_id}-{slug}.md",
        )
        _atomic_write(record.path, _render_record(record))
        _regenerate_overview_unlocked(repo_root)
    return record


def list_records(
    *,
    repo_root: Path,
    status: str | None = None,
) -> list[AdoptionRecord]:
    """List all records, optionally filtered by status."""
    if status is not None and status not in VALID_STATUSES:
        raise AdoptionError(
            f"Invalid status filter {status!r}; expected one of {VALID_STATUSES}"
        )
    directory = _adopted_dir(repo_root)
    if not directory.is_dir():
        return []
    records: list[AdoptionRecord] = []
    for entry in sorted(directory.glob("AR-*.md")):
        if entry.name == OVERVIEW_FILENAME:
            continue
        try:
            record = parse_record(entry)
        except AdoptionError:
            # Broad catch: covers both parse errors and wrapped
            # read_text failures so one bad file doesn't abort
            # listing (which would cascade into
            # regenerate_overview).
            continue
        if status is None or record.status == status:
            records.append(record)
    return records


def get_record(*, repo_root: Path, record_id: str) -> AdoptionRecord:
    """Fetch a single record by its ID (with or without slug)."""
    path = _find_record_path(repo_root, record_id)
    return parse_record(path)


def supersede_record(
    *,
    repo_root: Path,
    record_id: str,
    superseded_by: str,
) -> AdoptionRecord:
    """Mark an AR as superseded by a full spec.

    Validates that `specs/<superseded_by>/spec.md` exists before
    writing. Updates Status, writes `## Superseded By` section,
    regenerates overview. Runs under the advisory lock.
    """
    superseded_by = superseded_by.strip()
    if not superseded_by:
        raise AdoptionError("superseded_by must be non-empty")

    spec_path = repo_root / "specs" / superseded_by / "spec.md"
    if not spec_path.exists():
        raise AdoptionError(
            f"Cannot supersede {record_id!r}: target spec "
            f"specs/{superseded_by}/spec.md does not exist. "
            f"Create the full spec first, then rerun supersede."
        )

    with _adoption_lock(repo_root):
        record = get_record(repo_root=repo_root, record_id=record_id)
        updated = AdoptionRecord(
            record_id=record.record_id,
            slug=record.slug,
            title=record.title,
            status="superseded",
            adopted_on=record.adopted_on,
            baseline_commit=record.baseline_commit,
            summary=record.summary,
            location=list(record.location),
            key_behaviors=list(record.key_behaviors),
            known_gaps=record.known_gaps,
            superseded_by=superseded_by,
            retirement_reason=record.retirement_reason,
            path=record.path,
            extra=dict(record.extra),
        )
        _atomic_write(updated.path, _render_record(updated))
        _regenerate_overview_unlocked(repo_root)
    return updated


def retire_record(
    *,
    repo_root: Path,
    record_id: str,
    reason: str | None = None,
) -> AdoptionRecord:
    """Mark an AR as retired.

    If `reason` is provided and non-empty-after-strip, writes a
    `## Retirement Reason` section. If omitted or empty, the
    section is NOT added (per plan open question 5 — presence of
    `Status: retired` is sufficient signal; no empty sections).
    """
    clean_reason: str | None
    if reason is not None and reason.strip():
        clean_reason = reason.strip()
    else:
        clean_reason = None

    with _adoption_lock(repo_root):
        record = get_record(repo_root=repo_root, record_id=record_id)
        updated = AdoptionRecord(
            record_id=record.record_id,
            slug=record.slug,
            title=record.title,
            status="retired",
            adopted_on=record.adopted_on,
            baseline_commit=record.baseline_commit,
            summary=record.summary,
            location=list(record.location),
            key_behaviors=list(record.key_behaviors),
            known_gaps=record.known_gaps,
            superseded_by=record.superseded_by,
            retirement_reason=clean_reason,
            path=record.path,
            extra=dict(record.extra),
        )
        _atomic_write(updated.path, _render_record(updated))
        _regenerate_overview_unlocked(repo_root)
    return updated


def _overview_group(records: list[AdoptionRecord], status: str) -> list[str]:
    lines: list[str] = []
    filtered = [r for r in records if r.status == status]
    for record in sorted(filtered, key=lambda r: r.record_id):
        stem = (
            f"{record.record_id}-{record.slug}"
            if record.slug
            else record.record_id
        )
        suffix = f"adopted {record.adopted_on}"
        if record.status == "superseded" and record.superseded_by:
            suffix = f"adopted {record.adopted_on}, superseded by {record.superseded_by}"
        elif record.status == "retired":
            suffix = f"adopted {record.adopted_on}, retired"
        lines.append(
            f"- **[{record.record_id}](./{stem}.md)** — "
            f"{record.title} _({suffix})_"
        )
    return lines


def _render_overview(records: list[AdoptionRecord]) -> str:
    adopted_lines = _overview_group(records, "adopted")
    superseded_lines = _overview_group(records, "superseded")
    retired_lines = _overview_group(records, "retired")

    lines: list[str] = []
    lines.append("# Adoption Records Overview")
    lines.append("")
    lines.append(
        "_Generated by `speckit_orca.adoption regenerate-overview`. "
        "Do not edit by hand._"
    )
    lines.append("")
    lines.append("## Adopted")
    lines.append("")
    if adopted_lines:
        lines.extend(adopted_lines)
    else:
        lines.append("_No adopted records._")
    lines.append("")
    lines.append("## Superseded")
    lines.append("")
    if superseded_lines:
        lines.extend(superseded_lines)
    else:
        lines.append("_No superseded records._")
    lines.append("")
    lines.append("## Retired")
    lines.append("")
    if retired_lines:
        lines.extend(retired_lines)
    else:
        lines.append("_No retired records._")
    lines.append("")
    return "\n".join(lines)


def _regenerate_overview_unlocked(repo_root: Path) -> Path:
    """Rewrite 00-overview.md without acquiring the lock.

    Called by mutation functions that already hold `_adoption_lock`.
    """
    directory = _ensure_dir(_adopted_dir(repo_root))
    records = list_records(repo_root=repo_root)
    overview_path = directory / OVERVIEW_FILENAME
    _atomic_write(overview_path, _render_overview(records))
    return overview_path


def regenerate_overview(repo_root: Path) -> Path:
    """Rewrite the 00-overview.md index from current registry state.

    Acquires the advisory lock to prevent races with concurrent
    create / supersede / retire calls.
    """
    with _adoption_lock(repo_root):
        return _regenerate_overview_unlocked(repo_root)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m speckit_orca.adoption",
        description="Adoption record runtime (015).",
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

    create_p = sub.add_parser("create", help="Create a new adoption record")
    create_p.add_argument("--title", required=True)
    create_p.add_argument("--summary", required=True)
    create_p.add_argument(
        "--location", action="append", required=True,
        help="File path or module (repeatable)",
    )
    create_p.add_argument(
        "--key-behavior", action="append", required=True, dest="key_behaviors",
        help="Observed behavior bullet (repeatable)",
    )
    create_p.add_argument(
        "--known-gap", action="append", default=[], dest="known_gap_lines",
        help="Known gap line (repeatable). Joined with newlines.",
    )
    create_p.add_argument(
        "--baseline-commit", default=None,
        help="Override baseline commit SHA. Defaults to HEAD short SHA.",
    )
    create_p.add_argument(
        "--no-baseline", action="store_true",
        help="Omit the Baseline Commit field entirely.",
    )
    create_p.add_argument(
        "--adopted-on", default=None,
        help="Override the Adopted-on date (YYYY-MM-DD). Defaults to today.",
    )
    create_p.add_argument("--json", action="store_true", help="Emit JSON")

    get_p = sub.add_parser("get", help="Show a single record by id")
    get_p.add_argument("record_id")
    get_p.add_argument("--json", action="store_true", help="Emit JSON")

    supersede_p = sub.add_parser(
        "supersede",
        help="Mark a record as superseded by a full spec",
    )
    supersede_p.add_argument("record_id")
    supersede_p.add_argument(
        "superseded_by",
        help="Full spec id under specs/ (e.g., 020-new-auth)",
    )
    supersede_p.add_argument("--json", action="store_true", help="Emit JSON")

    retire_p = sub.add_parser("retire", help="Mark a record as retired")
    retire_p.add_argument("record_id")
    retire_p.add_argument(
        "--reason", default=None,
        help="Retirement reason (omitted from record if not provided)",
    )
    retire_p.add_argument("--json", action="store_true", help="Emit JSON")

    sub.add_parser("regenerate-overview", help="Rewrite 00-overview.md")

    return parser.parse_args(argv)


def _print_record(record: AdoptionRecord, as_json: bool) -> None:
    if as_json:
        print(json.dumps(record.to_dict(), indent=2))
    else:
        stem = (
            f"{record.record_id}-{record.slug}"
            if record.slug
            else record.record_id
        )
        print(f"{stem}  [{record.status}]  {record.title}")


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
                    print("No adoption records.")
                else:
                    for record in records:
                        _print_record(record, False)
            return 0

        if args.command == "create":
            # --no-baseline takes precedence over --baseline-commit.
            # Otherwise: explicit --baseline-commit overrides the
            # HEAD-SHA default sentinel.
            if args.no_baseline:
                baseline = None
            elif args.baseline_commit is not None:
                baseline = args.baseline_commit
            else:
                baseline = "__HEAD__"  # sentinel → git rev-parse
            known_gaps = (
                "\n".join(args.known_gap_lines)
                if args.known_gap_lines
                else None
            )
            record = create_record(
                repo_root=repo_root,
                title=args.title,
                summary=args.summary,
                location=args.location,
                key_behaviors=args.key_behaviors,
                known_gaps=known_gaps,
                baseline_commit=baseline,
                adopted_on=args.adopted_on,
            )
            _print_record(record, args.json)
            return 0

        if args.command == "get":
            record = get_record(
                repo_root=repo_root, record_id=args.record_id
            )
            if args.json:
                print(json.dumps(record.to_dict(), indent=2))
            else:
                print(_render_record(record).rstrip())
            return 0

        if args.command == "supersede":
            record = supersede_record(
                repo_root=repo_root,
                record_id=args.record_id,
                superseded_by=args.superseded_by,
            )
            _print_record(record, args.json)
            return 0

        if args.command == "retire":
            record = retire_record(
                repo_root=repo_root,
                record_id=args.record_id,
                reason=args.reason,
            )
            _print_record(record, args.json)
            return 0

        if args.command == "regenerate-overview":
            path = regenerate_overview(repo_root)
            print(f"Regenerated {path}")
            return 0

    except AdoptionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(cli_main())
