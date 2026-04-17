"""Brownfield v2 — per-project onboarding pipeline (017 MVP).

Layers on top of 015's `adoption.create_record` to enable bulk
onboarding of existing codebases. Walks a repo, applies heuristics
H1/H2/H3/H6, emits draft ARs and a triage.md surface. After the
operator triages, `commit_run` calls 015 per accepted draft. 017
never writes under `.specify/orca/adopted/` directly.

Contracts:
  specs/017-brownfield-v2/spec.md
  specs/017-brownfield-v2/plan.md
  specs/017-brownfield-v2/brainstorm.md

Invariants:
  - No third-party runtime dependencies. YAML is a hand-written
    subset serializer/parser.
  - Existing ARs are never mutated. Every new AR goes through
    `adoption.create_record`.
  - Draft files live under `.specify/orca/adoption-runs/*/drafts/`,
    a path 015's parser does not walk.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from speckit_orca import adoption


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADOPTION_RUNS_DIRNAME = ".specify/orca/adoption-runs"

VALID_TRIAGE_VERBS = (
    "pending", "accept", "reject", "edit", "duplicate",
)
VALID_PHASES = ("discovery", "review", "commit", "done")

HEURISTICS_MVP = ("H1", "H2", "H3", "H6")

DEFAULT_SCORE_THRESHOLD = 0.3

# Directory-name denylist: grab-bag names that should not anchor a
# feature record on their own. Applied AFTER scoring — the penalty
# multiplier drops them below threshold unless a higher-precision
# heuristic reinforces them.
GRAB_BAG_NAMES = {
    "utils", "helpers", "common", "lib", "shared", "misc",
    "internal", "infra", "infrastructure",
}

# README section names that are boilerplate, not features.
README_BOILERPLATE = {
    "installation", "install", "getting started", "usage",
    "license", "contributing", "quickstart", "setup", "requirements",
    "prerequisites", "overview", "readme", "about",
}

# Source file extensions for H1 directory-grouping counts.
SOURCE_EXTS = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java")

# Default source-root candidates to walk for H1.
SOURCE_ROOTS = ("src", "lib", "packages", "app", "cmd")

# Git history window for H6.
GIT_WINDOW_COMMITS = 500
GIT_WINDOW_DAYS = 180
H6_MIN_COOCCURRENCE = 3  # min times a pair must co-change to cluster


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
CAND_ID_RE = re.compile(r"^C-\d{3}$")
TRIAGE_HEADING_RE = re.compile(r"^##\s+(C-\d{3}):\s*(.*)$")
TRIAGE_STATUS_RE = re.compile(r"^-\s*status:\s*(.+?)\s*$")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class OnboardError(Exception):
    """Raised for any 017 onboarding runtime failure."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CandidateRecord:
    """One proposed feature from heuristic discovery."""

    id: str                  # "C-NNN"
    proposed_title: str
    proposed_slug: str
    paths: list[str]
    signals: list[str]
    score: float
    draft_path: str          # relative to run_dir
    triage: str              # one of VALID_TRIAGE_VERBS
    duplicate_of: str | None

    def __post_init__(self) -> None:
        if not CAND_ID_RE.match(self.id):
            raise ValueError(f"Invalid candidate id: {self.id!r}")
        if self.triage not in VALID_TRIAGE_VERBS:
            raise ValueError(
                f"Invalid triage verb: {self.triage!r}; "
                f"expected one of {VALID_TRIAGE_VERBS}"
            )


@dataclass
class TriageEntry:
    """Operator's decision for one candidate, parsed from triage.md."""

    candidate_id: str
    verb: str
    duplicate_of: str | None = None


@dataclass
class OnboardingManifest:
    """Durable state of one adoption run."""

    run_id: str
    created: str                      # RFC3339 UTC
    phase: str                        # VALID_PHASES
    repo_root: str
    baseline_commit: str | None
    heuristics_enabled: list[str]
    score_threshold: float
    candidates: list[CandidateRecord]
    committed: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.phase not in VALID_PHASES:
            raise ValueError(
                f"Invalid phase: {self.phase!r}; expected one of {VALID_PHASES}"
            )


# ---------------------------------------------------------------------------
# YAML subset serializer / parser
# ---------------------------------------------------------------------------
#
# Scope: scalars (str, int, float, bool, None), lists of scalars, lists of
# dicts whose values are scalars or lists of scalars, and top-level maps.
# Indentation is exactly 2 spaces per nesting level. No anchors, no aliases,
# no flow style (except for the empty-list marker `[]`), no multi-line
# scalars. Strings are always double-quoted on emit; on parse, both quoted
# and bare scalars are accepted.


def _yaml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\"", "\\\"")


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f"\"{_yaml_escape(value)}\""
    raise OnboardError(f"Unsupported scalar type: {type(value).__name__}")


def _emit_list(key: str, items: list[Any], indent: int) -> list[str]:
    """Emit a block list. Items are indented by 2 spaces relative to the key.

    The parser requires list items at indent > parent. Keep the convention
    consistent: key at indent N, items at indent N+2.
    """
    prefix = " " * indent
    if not items:
        return [f"{prefix}{key}: []"]
    lines = [f"{prefix}{key}:"]
    item_prefix = " " * (indent + 2)
    for item in items:
        if isinstance(item, dict):
            if not item:
                lines.append(f"{item_prefix}- {{}}")
                continue
            first = True
            for k, v in item.items():
                if isinstance(v, list):
                    # nested list under a dict item
                    if not v:
                        if first:
                            lines.append(f"{item_prefix}- {k}: []")
                            first = False
                        else:
                            lines.append(f"{item_prefix}  {k}: []")
                    else:
                        if first:
                            lines.append(f"{item_prefix}- {k}:")
                            first = False
                        else:
                            lines.append(f"{item_prefix}  {k}:")
                        # Items nested under the dict key are at item_prefix + 4 spaces
                        for sub in v:
                            lines.append(f"{item_prefix}    - {_yaml_scalar(sub)}")
                else:
                    if first:
                        lines.append(f"{item_prefix}- {k}: {_yaml_scalar(v)}")
                        first = False
                    else:
                        lines.append(f"{item_prefix}  {k}: {_yaml_scalar(v)}")
        else:
            lines.append(f"{item_prefix}- {_yaml_scalar(item)}")
    return lines


def _emit_yaml(manifest: OnboardingManifest) -> str:
    """Serialize a manifest to YAML subset text."""
    lines: list[str] = []
    lines.append(f"run_id: {_yaml_scalar(manifest.run_id)}")
    lines.append(f"created: {_yaml_scalar(manifest.created)}")
    lines.append(f"phase: {_yaml_scalar(manifest.phase)}")
    lines.append(f"repo_root: {_yaml_scalar(manifest.repo_root)}")
    lines.append(f"baseline_commit: {_yaml_scalar(manifest.baseline_commit)}")
    lines.append(f"score_threshold: {_yaml_scalar(manifest.score_threshold)}")
    lines.extend(_emit_list("heuristics_enabled", manifest.heuristics_enabled, 0))

    cand_dicts = [
        {
            "id": c.id,
            "proposed_title": c.proposed_title,
            "proposed_slug": c.proposed_slug,
            "paths": list(c.paths),
            "signals": list(c.signals),
            "score": round(c.score, 4),
            "draft_path": c.draft_path,
            "triage": c.triage,
            "duplicate_of": c.duplicate_of,
        }
        for c in manifest.candidates
    ]
    lines.extend(_emit_list("candidates", cand_dicts, 0))
    lines.extend(_emit_list("committed", manifest.committed, 0))
    lines.extend(_emit_list("rejected", manifest.rejected, 0))
    lines.extend(_emit_list("failed", manifest.failed, 0))
    return "\n".join(lines) + "\n"


def _parse_scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw == "null" or raw == "~" or raw == "":
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw.startswith("\"") and raw.endswith("\"") and len(raw) >= 2:
        inner = raw[1:-1]
        # Undo simple escapes
        return inner.replace("\\\"", "\"").replace("\\\\", "\\")
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1]
    # Numeric?
    try:
        if "." in raw or "e" in raw or "E" in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_dict_item_start(payload: str) -> bool:
    """Decide whether a `- ...` payload starts a dict item (key: value)
    or is a pure scalar. Quoted strings are always scalars even when
    they contain colons.
    """
    payload = payload.strip()
    if payload.startswith("\"") or payload.startswith("'"):
        return False
    if ":" not in payload:
        return False
    key, _, _ = payload.partition(":")
    # Keys are bare identifiers (alnum, underscore, dash)
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_\-]*$", key.strip()))


def _parse_yaml(text: str) -> dict[str, Any]:
    """Parse YAML subset text into a nested dict.

    Restricted shapes recognized:
      key: scalar
      key:
        - scalar
        - scalar
      key:
        - key: scalar
          key: scalar
          key:
            - scalar
      key: []
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    # Strip pure-whitespace and comment-only lines.
    lines = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
    out: dict[str, Any] = {}
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _indent_of(line) != 0:
            raise OnboardError(
                f"Top-level key expected at indent 0, got: {line!r}"
            )
        if ":" not in line:
            raise OnboardError(f"Expected 'key: value' at line: {line!r}")
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest == "[]":
            out[key] = []
            i += 1
            continue
        if rest == "":
            # list-of-scalars OR list-of-dicts follows
            i += 1
            items, i = _parse_list(lines, i, base_indent=0)
            out[key] = items
            continue
        out[key] = _parse_scalar(rest)
        i += 1
    return out


def _parse_list(
    lines: list[str], start: int, base_indent: int,
) -> tuple[list[Any], int]:
    """Parse a list block. Returns (items, next_index).

    The list items are at indent > base_indent, each starting with
    '- '. Scalar items: `- value`. Dict items: `- key: value` then
    subsequent `  key: value` lines at deeper indent.
    """
    items: list[Any] = []
    i = start
    n = len(lines)
    if i >= n:
        return items, i
    first_indent = _indent_of(lines[i])
    if first_indent <= base_indent:
        return items, i
    item_indent = first_indent
    while i < n:
        line = lines[i]
        indent = _indent_of(line)
        if indent < item_indent:
            break
        if indent != item_indent:
            raise OnboardError(
                f"Unexpected indent at line: {line!r} "
                f"(got {indent}, want {item_indent})"
            )
        stripped = line.lstrip()
        if not stripped.startswith("- "):
            break
        payload = stripped[2:]
        # Check if this is a dict item (starts with `key:`) or a scalar.
        # Quoted-string scalars contain colons inside the quotes, so a
        # bare colon at top-of-payload is only a dict marker if the key
        # portion is not a quoted string.
        if _is_dict_item_start(payload):
            # dict item
            d: dict[str, Any] = {}
            key, _, rest = payload.partition(":")
            key = key.strip()
            rest = rest.strip()
            if rest == "[]":
                d[key] = []
            elif rest == "":
                # nested list inside this dict item
                i += 1
                sub_items, i = _parse_list(lines, i, base_indent=item_indent + 2)
                d[key] = sub_items
                # Continue collecting more keys from this dict item
                while i < n:
                    cont = lines[i]
                    cont_indent = _indent_of(cont)
                    if cont_indent != item_indent + 2:
                        break
                    cont_stripped = cont.lstrip()
                    if cont_stripped.startswith("- "):
                        break
                    if ":" not in cont_stripped:
                        break
                    k2, _, v2 = cont_stripped.partition(":")
                    k2 = k2.strip()
                    v2 = v2.strip()
                    if v2 == "":
                        i += 1
                        sub2, i = _parse_list(lines, i, base_indent=item_indent + 2)
                        d[k2] = sub2
                    elif v2 == "[]":
                        d[k2] = []
                        i += 1
                    else:
                        d[k2] = _parse_scalar(v2)
                        i += 1
                items.append(d)
                continue
            else:
                d[key] = _parse_scalar(rest)
            i += 1
            # Additional keys for this dict item at indent = item_indent + 2.
            while i < n:
                cont = lines[i]
                cont_indent = _indent_of(cont)
                if cont_indent != item_indent + 2:
                    break
                cont_stripped = cont.lstrip()
                if cont_stripped.startswith("- "):
                    break
                if ":" not in cont_stripped:
                    break
                k2, _, v2 = cont_stripped.partition(":")
                k2 = k2.strip()
                v2 = v2.strip()
                if v2 == "":
                    i += 1
                    sub2, i = _parse_list(lines, i, base_indent=item_indent + 2)
                    d[k2] = sub2
                elif v2 == "[]":
                    d[k2] = []
                    i += 1
                else:
                    d[k2] = _parse_scalar(v2)
                    i += 1
            items.append(d)
        else:
            # scalar item
            items.append(_parse_scalar(payload))
            i += 1
    return items, i


# ---------------------------------------------------------------------------
# Manifest file I/O
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def write_manifest(run_dir: Path, manifest: OnboardingManifest) -> Path:
    """Write manifest.yaml atomically under run_dir."""
    path = run_dir / "manifest.yaml"
    _atomic_write(path, _emit_yaml(manifest))
    return path


def read_manifest(run_dir: Path) -> OnboardingManifest:
    path = run_dir / "manifest.yaml"
    if not path.exists():
        raise OnboardError(f"No manifest at {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OnboardError(f"Could not read manifest: {path}") from exc
    try:
        raw = _parse_yaml(text)
        cands_raw = raw.get("candidates", []) or []
        cands: list[CandidateRecord] = []
        for d in cands_raw:
            if "id" not in d:
                raise OnboardError(
                    f"manifest candidate missing required 'id' field: {d!r}"
                )
            cands.append(
                CandidateRecord(
                    id=d["id"],
                    proposed_title=d.get("proposed_title", ""),
                    proposed_slug=d.get("proposed_slug", ""),
                    paths=list(d.get("paths", []) or []),
                    signals=list(d.get("signals", []) or []),
                    score=float(d.get("score", 0.0)),
                    draft_path=d.get("draft_path", ""),
                    triage=d.get("triage", "pending") or "pending",
                    duplicate_of=d.get("duplicate_of"),
                )
            )
        if "run_id" not in raw:
            raise OnboardError("manifest missing required 'run_id' field")
        if "created" not in raw:
            raise OnboardError("manifest missing required 'created' field")
        return OnboardingManifest(
            run_id=raw["run_id"],
            created=raw["created"],
            phase=raw.get("phase", "discovery"),
            repo_root=raw.get("repo_root", ""),
            baseline_commit=raw.get("baseline_commit"),
            heuristics_enabled=list(raw.get("heuristics_enabled", []) or []),
            score_threshold=float(raw.get("score_threshold", DEFAULT_SCORE_THRESHOLD)),
            candidates=cands,
            committed=list(raw.get("committed", []) or []),
            rejected=list(raw.get("rejected", []) or []),
            failed=list(raw.get("failed", []) or []),
        )
    except OnboardError:
        raise
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise OnboardError(f"Malformed manifest at {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unnamed"


def _next_id(i: int) -> str:
    return f"C-{i:03d}"


def _count_source_files(directory: Path) -> int:
    count = 0
    for entry in directory.rglob("*"):
        if entry.is_file() and entry.suffix in SOURCE_EXTS:
            count += 1
    return count


def _relative_paths(base: Path, files: Iterable[Path]) -> list[str]:
    out: list[str] = []
    for f in files:
        try:
            out.append(str(f.relative_to(base)))
        except ValueError:
            out.append(str(f))
    return sorted(out)


def heuristic_h1_directories(
    repo_root: Path,
    *,
    source_roots: Iterable[str] = SOURCE_ROOTS,
    max_files_per_candidate: int = 20,
) -> list[CandidateRecord]:
    """H1 — directory grouping. One candidate per cohesive subdirectory.

    Emits a candidate for every direct child of a recognized source
    root that contains ≥2 source files. Grab-bag names are scored
    with a 0.3 multiplier so the default threshold (0.3) drops them
    unless another heuristic reinforces.
    """
    candidates: list[CandidateRecord] = []
    counter = 1
    for root_name in source_roots:
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith(".") or child.name.startswith("_"):
                continue
            n_files = _count_source_files(child)
            if n_files < 2:
                continue
            # Base score 0.5, +0.1 per extra file beyond 2, capped at +0.2
            bump = min(0.2, 0.1 * max(0, n_files - 2))
            score = 0.5 + bump
            if child.name.lower() in GRAB_BAG_NAMES:
                score *= 0.3
            paths = [
                str(f.relative_to(repo_root))
                for f in sorted(child.rglob("*"))
                if f.is_file() and f.suffix in SOURCE_EXTS
            ][:max_files_per_candidate]
            candidates.append(CandidateRecord(
                id=_next_id(counter),
                proposed_title=child.name,
                proposed_slug=_slugify(child.name),
                paths=paths,
                signals=[f"H1:{root_name}/{child.name}"],
                score=round(score, 4),
                draft_path="",  # filled later
                triage="pending",
                duplicate_of=None,
            ))
            counter += 1
    return candidates


def heuristic_h2_entry_points(repo_root: Path) -> list[CandidateRecord]:
    """H2 — scripts / entry points.

    Parses pyproject.toml `[project.scripts]` and
    `[project.entry-points]`, plus package.json `bin`. Each entry
    point becomes a candidate. Uses stdlib `tomllib` (Python 3.11+)
    with a minimal regex fallback for 3.10.
    """
    candidates: list[CandidateRecord] = []
    counter = 1

    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        try:
            scripts = _read_pyproject_scripts(pyproject)
        except Exception:
            scripts = {}
        for name, target in scripts.items():
            slug = _slugify(name)
            paths = _resolve_python_entry_target(repo_root, target)
            candidates.append(CandidateRecord(
                id=_next_id(counter),
                proposed_title=name,
                proposed_slug=slug,
                paths=paths,
                signals=[f"H2:entry-point:{name}"],
                score=0.6,
                draft_path="",
                triage="pending",
                duplicate_of=None,
            ))
            counter += 1

    setup_py = repo_root / "setup.py"
    if setup_py.exists():
        sp_entries = _read_setup_py_entry_points(setup_py)
        for name, target in sp_entries.items():
            slug = _slugify(name)
            paths = _resolve_python_entry_target(repo_root, target)
            candidates.append(CandidateRecord(
                id=_next_id(counter),
                proposed_title=name,
                proposed_slug=slug,
                paths=paths,
                signals=[f"H2:entry-point:{name}"],
                score=0.6,
                draft_path="",
                triage="pending",
                duplicate_of=None,
            ))
            counter += 1

    pkg_json = repo_root / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        bin_field = data.get("bin") if isinstance(data, dict) else None
        if isinstance(bin_field, str):
            bins = {data.get("name", "bin"): bin_field}
        elif isinstance(bin_field, dict):
            bins = bin_field
        else:
            bins = {}
        for name, target in bins.items():
            slug = _slugify(str(name))
            target_str = str(target).lstrip("./")
            paths: list[str] = []
            candidate_file = repo_root / target_str
            if candidate_file.exists():
                try:
                    paths = [str(candidate_file.relative_to(repo_root))]
                except ValueError:
                    paths = [target_str]
            else:
                paths = [target_str]
            candidates.append(CandidateRecord(
                id=_next_id(counter),
                proposed_title=str(name),
                proposed_slug=slug,
                paths=paths,
                signals=[f"H2:entry-point:{name}"],
                score=0.6,
                draft_path="",
                triage="pending",
                duplicate_of=None,
            ))
            counter += 1

    return candidates


def _read_pyproject_scripts(path: Path) -> dict[str, str]:
    """Return entries from [project.scripts] and [project.entry-points.*]
    and [project.gui-scripts]; supports tomllib and regex fallback.
    """
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    try:
        import tomllib  # type: ignore[import-not-found]
        data = tomllib.loads(text)
        project = data.get("project", {}) if isinstance(data, dict) else {}
        for table in ("scripts", "gui-scripts"):
            table_val = project.get(table, {}) or {}
            if isinstance(table_val, dict):
                for k, v in table_val.items():
                    out[str(k)] = str(v)
        entry_points = project.get("entry-points", {}) or {}
        if isinstance(entry_points, dict):
            for _group, eps in entry_points.items():
                if isinstance(eps, dict):
                    for k, v in eps.items():
                        out[str(k)] = str(v)
        return out
    except ModuleNotFoundError:
        pass
    # Fallback for Python 3.10: regex-sniff the recognized tables.
    in_table: str | None = None
    recognized = ("[project.scripts]", "[project.gui-scripts]")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if stripped in recognized or stripped.startswith("[project.entry-points"):
                in_table = stripped
            else:
                in_table = None
            continue
        if in_table is None:
            continue
        # Accept both "double" and 'single' quoted string values.
        m = re.match(
            r"^([A-Za-z0-9_\-\.]+)\s*=\s*"
            r'(?:"([^"]+)"|\'([^\']+)\')',
            stripped,
        )
        if m:
            out[m.group(1)] = m.group(2) or m.group(3)
    return out


def _read_setup_py_entry_points(path: Path) -> dict[str, str]:
    """Best-effort regex scan of a setup.py `entry_points={...}` dict.

    Only recognizes the simple `console_scripts = ["name = mod:fn"]` shape.
    setup.py exec is intentionally avoided for safety.
    """
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    # Find all strings matching `name = mod:fn` inside the file
    # (may over-match but entries like this are almost always
    # console_scripts style).
    for m in re.finditer(
        r'["\']([A-Za-z0-9_\-\.]+)\s*=\s*([A-Za-z0-9_\.]+:[A-Za-z0-9_]+)["\']',
        text,
    ):
        out[m.group(1)] = m.group(2)
    return out


def _resolve_python_entry_target(repo_root: Path, target: str) -> list[str]:
    """Given e.g. `pkg.mod:main`, return [path/to/pkg/mod.py] if it exists."""
    mod, _, _func = target.partition(":")
    rel_parts = mod.split(".")
    for root in ("", "src"):
        base = repo_root / root if root else repo_root
        candidate_pkg = base.joinpath(*rel_parts, "__init__.py")
        candidate_mod = base.joinpath(*rel_parts).with_suffix(".py")
        for p in (candidate_mod, candidate_pkg):
            if p.exists():
                try:
                    return [str(p.relative_to(repo_root))]
                except ValueError:
                    return [str(p)]
    return [mod.replace(".", "/")]


def heuristic_h3_readme(repo_root: Path) -> list[CandidateRecord]:
    """H3 — README H2 headings.

    Emits one candidate per `## Heading` that does NOT match the
    boilerplate denylist (Installation, License, etc.).
    """
    candidates: list[CandidateRecord] = []
    counter = 1
    seen_slugs: set[str] = set()
    for rel in ("README.md", "docs/README.md"):
        path = repo_root / rel
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^##\s+(.+?)\s*$", line)
            if not m:
                continue
            heading = m.group(1).strip()
            if heading.lower() in README_BOILERPLATE:
                continue
            slug = _slugify(heading)
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            candidates.append(CandidateRecord(
                id=_next_id(counter),
                proposed_title=heading,
                proposed_slug=slug,
                paths=[rel],
                signals=[f"H3:{heading}"],
                score=0.7,
                draft_path="",
                triage="pending",
                duplicate_of=None,
            ))
            counter += 1
    return candidates


def _resolve_git() -> str | None:
    """Return the absolute path to the user's `git`, or None if missing.

    Resolving once via shutil.which keeps subprocess invocations off of
    a partial executable path (Ruff S607) while still honouring the
    user's own PATH — 017 intentionally defers to whatever git the
    operator has installed.
    """
    return shutil.which("git")


def heuristic_h6_cochange(
    repo_root: Path,
    *,
    max_commits: int = GIT_WINDOW_COMMITS,
    since_days: int = GIT_WINDOW_DAYS,
    min_cooccurrence: int = H6_MIN_COOCCURRENCE,
) -> list[CandidateRecord]:
    """H6 — git co-change clusters.

    Runs `git log --name-only` with a bounded window and groups
    files that change together. Files that co-occur in ≥N commits
    form a cluster; each cluster becomes a candidate.
    """
    git_bin = _resolve_git()
    if git_bin is None:
        return []
    try:
        result = subprocess.run(
            [
                git_bin, "-C", str(repo_root), "log",
                f"--max-count={max_commits}",
                f"--since={since_days}.days.ago",
                "--name-only",
                "--pretty=format:COMMIT",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError,
            subprocess.TimeoutExpired):
        return []

    commits: list[set[str]] = []
    current: set[str] = set()
    for line in result.stdout.splitlines():
        if line == "COMMIT":
            if current:
                commits.append(current)
                current = set()
            continue
        line = line.strip()
        if not line:
            continue
        if Path(line).suffix not in SOURCE_EXTS:
            continue
        current.add(line)
    if current:
        commits.append(current)

    if not commits:
        return []

    # Count co-occurrences
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for files in commits:
        if len(files) < 2 or len(files) > 15:
            # Skip mega-commits (refactors) that pollute clusters
            if len(files) > 15:
                continue
            continue
        files_sorted = sorted(files)
        for i, a in enumerate(files_sorted):
            for b in files_sorted[i + 1:]:
                pair_counts[(a, b)] += 1

    # Union-find on pairs above threshold
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent.get(x, x), x)
            x = parent.get(x, x)
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for (a, b), count in pair_counts.items():
        if count >= min_cooccurrence:
            parent.setdefault(a, a)
            parent.setdefault(b, b)
            union(a, b)

    clusters: dict[str, set[str]] = defaultdict(set)
    for node in list(parent.keys()):
        root = find(node)
        clusters[root].add(node)

    candidates: list[CandidateRecord] = []
    counter = 1
    for members in clusters.values():
        if len(members) < 2:
            continue
        sorted_members = sorted(members)
        slug = _slugify("-".join(Path(m).stem for m in sorted_members[:2]))
        # Base 0.4, +0.1 per additional member beyond 2, capped at +0.3
        bump = min(0.3, 0.1 * max(0, len(sorted_members) - 2))
        score = 0.4 + bump
        candidates.append(CandidateRecord(
            id=_next_id(counter),
            proposed_title=f"Co-change cluster ({len(sorted_members)} files)",
            proposed_slug=f"cochange-{slug}",
            paths=sorted_members,
            signals=[f"H6:cluster:{len(sorted_members)}"],
            score=round(score, 4),
            draft_path="",
            triage="pending",
            duplicate_of=None,
        ))
        counter += 1
    return candidates


def _title_precedence(signals: list[str]) -> int:
    """Higher is better — H3 > H2 > H1 > H6."""
    priorities = {"H3": 3, "H2": 2, "H1": 1, "H6": 0}
    best = -1
    for s in signals:
        prefix = s.split(":", 1)[0]
        best = max(best, priorities.get(prefix, -1))
    return best


def _path_prefixes(p: str) -> set[str]:
    """Return all directory prefixes of a path, depth >= 1.

    `src/auth/middleware.py` -> {`src`, `src/auth`, `src/auth/middleware.py`}.
    Used for path-overlap clustering: two candidates cluster if they
    share any directory prefix of depth >= 2, which distinguishes
    `src/auth` from `packages/auth` while still merging
    `src/auth/__init__.py` with `src/auth/middleware.py`.
    """
    norm = p.replace("\\", "/").strip("/").lower()
    if not norm:
        return set()
    parts = norm.split("/")
    return {"/".join(parts[: i + 1]) for i in range(len(parts))}


def merge_candidates(
    candidates: list[CandidateRecord],
) -> list[CandidateRecord]:
    """Merge candidates that identify the same feature.

    Two candidates cluster together when they share the same slug AND
    at least one directory-prefix (depth >= 2) across their paths.
    Keying on slug alone is insufficient: unrelated areas like
    `src/auth` and `packages/auth` slugify identically and would
    otherwise collapse into one candidate with a union of paths.
    Requiring a shared directory prefix keeps distinct features
    distinct while still merging H1/H2/H3/H6 hits on the same area.

    Scores combine via probabilistic OR: 1 - prod(1 - s_i).
    Title comes from the highest-precedence heuristic: H3 > H2 > H1 > H6.
    """
    # Union-find: indices link when they share slug AND a dir prefix.
    n = len(candidates)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    # Group first by slug to keep union-find bounded.
    by_slug: dict[str, list[int]] = defaultdict(list)
    for idx, c in enumerate(candidates):
        by_slug[c.proposed_slug].append(idx)

    for indices in by_slug.values():
        if len(indices) < 2:
            continue
        # Index each candidate's directory prefixes (depth >= 2) within
        # this slug bucket. A single-segment prefix like "src" is too
        # coarse — `src/auth` and `src/payments` both contain it.
        prefix_to_idx: dict[str, set[int]] = defaultdict(set)
        for idx in indices:
            cand_prefixes: set[str] = set()
            for p in candidates[idx].paths:
                for pref in _path_prefixes(p):
                    if "/" in pref:  # depth >= 2
                        cand_prefixes.add(pref)
            for pref in cand_prefixes:
                prefix_to_idx[pref].add(idx)
        # Also allow single-file paths (depth 1) to merge only with
        # themselves — they still go through the shared-prefix check
        # via _path_prefixes; slug-only collisions without any shared
        # prefix stay as separate candidates.
        for sharers in prefix_to_idx.values():
            if len(sharers) < 2:
                continue
            sharers_list = sorted(sharers)
            first = sharers_list[0]
            for other in sharers_list[1:]:
                union(first, other)

    # Group by cluster root, preserving original order for stability.
    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)

    # Emit clusters in a deterministic order: sort by the slug of the
    # first candidate in the cluster, then by first-index.
    def cluster_sort_key(item: tuple[int, list[int]]) -> tuple[str, int]:
        root, idxs = item
        first_idx = min(idxs)
        return (candidates[first_idx].proposed_slug, first_idx)

    merged: list[CandidateRecord] = []
    counter = 1
    for _root, idxs in sorted(clusters.items(), key=cluster_sort_key):
        group = [candidates[i] for i in sorted(idxs)]
        if len(group) == 1:
            c = group[0]
            merged.append(CandidateRecord(
                id=_next_id(counter),
                proposed_title=c.proposed_title,
                proposed_slug=c.proposed_slug,
                paths=list(c.paths),
                signals=list(c.signals),
                score=c.score,
                draft_path="",
                triage="pending",
                duplicate_of=None,
            ))
            counter += 1
            continue
        # Combine scores
        product = 1.0
        for c in group:
            product *= (1.0 - c.score)
        combined_score = round(1.0 - product, 4)
        # Combine signals (dedup, preserve order)
        signals: list[str] = []
        for c in group:
            for s in c.signals:
                if s not in signals:
                    signals.append(s)
        # Combine paths (dedup, preserve order)
        paths: list[str] = []
        for c in group:
            for p in c.paths:
                if p not in paths:
                    paths.append(p)
        # Title precedence
        best = max(group, key=lambda c: _title_precedence(c.signals))
        merged.append(CandidateRecord(
            id=_next_id(counter),
            proposed_title=best.proposed_title,
            proposed_slug=best.proposed_slug,
            paths=paths,
            signals=signals,
            score=combined_score,
            draft_path="",
            triage="pending",
            duplicate_of=None,
        ))
        counter += 1
    return merged


def discover(
    repo_root: Path,
    heuristics: Iterable[str] = HEURISTICS_MVP,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> list[CandidateRecord]:
    """Run the enabled heuristics, merge, filter, sort."""
    heuristics = tuple(heuristics)
    all_candidates: list[CandidateRecord] = []
    if "H1" in heuristics:
        all_candidates.extend(heuristic_h1_directories(repo_root))
    if "H2" in heuristics:
        all_candidates.extend(heuristic_h2_entry_points(repo_root))
    if "H3" in heuristics:
        all_candidates.extend(heuristic_h3_readme(repo_root))
    if "H6" in heuristics:
        all_candidates.extend(heuristic_h6_cochange(repo_root))

    merged = merge_candidates(all_candidates)
    filtered = [c for c in merged if c.score >= score_threshold]

    # Stable sort: score desc, slug asc
    filtered.sort(key=lambda c: (-c.score, c.proposed_slug))

    # Re-id sequentially after sort
    out: list[CandidateRecord] = []
    for i, c in enumerate(filtered, start=1):
        out.append(CandidateRecord(
            id=_next_id(i),
            proposed_title=c.proposed_title,
            proposed_slug=c.proposed_slug,
            paths=c.paths,
            signals=c.signals,
            score=c.score,
            draft_path=f"drafts/DRAFT-{i:03d}-{c.proposed_slug}.md",
            triage="pending",
            duplicate_of=None,
        ))
    return out


# ---------------------------------------------------------------------------
# Proposal generator
# ---------------------------------------------------------------------------


DRAFT_BANNER = (
    "<!-- DRAFT — NOT YET COMMITTED. Edit Summary and Key Behaviors "
    "before accepting in triage.md. -->"
)


def render_draft(candidate: CandidateRecord, draft_number: int) -> str:
    """Emit draft AR markdown. Shape mirrors 015's renderer so commit
    can pass the parsed fields to `create_record` without transformation.
    """
    today = date.today().isoformat()
    lines: list[str] = []
    lines.append(DRAFT_BANNER)
    lines.append("")
    lines.append(
        f"# Adoption Record: DRAFT-{draft_number:03d}: {candidate.proposed_title}"
    )
    lines.append("")
    lines.append("**Status**: adopted")
    lines.append(f"**Adopted-on**: {today}")
    lines.append("")
    lines.append("## Summary")
    lines.append("TODO: describe what this feature does")
    lines.append("")
    lines.append("## Location")
    for p in candidate.paths:
        lines.append(f"- {p}")
    lines.append("")
    lines.append("## Key Behaviors")
    lines.append("- TODO: fill in an observed behavior before accepting")
    lines.append("")
    lines.append("## Known Gaps")
    lines.append(
        f"Discovered by heuristics {', '.join(candidate.signals)}. "
        f"Confidence {candidate.score:.2f}. Review before accepting."
    )
    lines.append("")
    return "\n".join(lines)


def write_drafts(run_dir: Path, candidates: list[CandidateRecord]) -> list[Path]:
    """Write one draft file per candidate. Returns list of written paths."""
    drafts_dir = run_dir / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for i, c in enumerate(candidates, start=1):
        fname = f"DRAFT-{i:03d}-{c.proposed_slug}.md"
        path = drafts_dir / fname
        _atomic_write(path, render_draft(c, draft_number=i))
        written.append(path)
    return written


# ---------------------------------------------------------------------------
# Triage.md render / parse
# ---------------------------------------------------------------------------


def render_triage(manifest: OnboardingManifest) -> str:
    lines: list[str] = []
    lines.append(f"# Adoption Run — {manifest.run_id}")
    lines.append("")
    lines.append(
        f"Phase: **{manifest.phase}**. {len(manifest.candidates)} candidates."
    )
    lines.append("")
    lines.append(
        "Mark each candidate with `- status: accept | reject | edit "
        "| duplicate-of:C-NNN`. Then run "
        f"`python -m speckit_orca.onboard commit --run {manifest.run_id}`."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    for c in manifest.candidates:
        lines.append(f"## {c.id}: {c.proposed_title}")
        lines.append("")
        lines.append(f"- draft: [{Path(c.draft_path).name}]({c.draft_path})")
        lines.append(f"- slug: `{c.proposed_slug}`")
        lines.append(f"- score: {c.score:.2f}")
        lines.append(f"- signals: {', '.join(c.signals)}")
        if c.paths:
            lines.append("- paths:")
            for p in c.paths[:8]:
                lines.append(f"  - `{p}`")
            if len(c.paths) > 8:
                lines.append(f"  - ... ({len(c.paths) - 8} more)")
        lines.append(f"- status: {c.triage}")
        lines.append("")
    return "\n".join(lines)


def parse_triage(text: str, manifest: OnboardingManifest) -> dict[str, TriageEntry]:
    """Return dict candidate_id → TriageEntry. Raises on invalid content.

    Rules:
      - One `## C-NNN: <title>` section per candidate.
      - Each section must have exactly one `- status: <verb>` line.
      - Verbs: accept | reject | edit | pending | duplicate-of:C-NNN.
      - Unknown candidate ids in triage → error.
      - Candidates present in manifest but absent from triage → pending.
    """
    known_ids = {c.id for c in manifest.candidates}
    entries: dict[str, TriageEntry] = {}
    # Track headings we've already opened, independent of whether a
    # `- status:` line has been parsed yet. Keying the duplicate check
    # off `entries` alone lets a malformed file with two `## C-001`
    # headings before any status line slip through silently.
    seen_sections: set[str] = set()
    current: str | None = None
    for lineno, raw in enumerate(text.splitlines(), start=1):
        heading = TRIAGE_HEADING_RE.match(raw)
        if heading:
            cid = heading.group(1)
            if cid not in known_ids:
                raise OnboardError(
                    f"triage.md line {lineno}: unknown candidate {cid}. "
                    f"Remove the section or re-scan."
                )
            if cid in seen_sections:
                raise OnboardError(
                    f"triage.md line {lineno}: duplicate section for {cid}"
                )
            seen_sections.add(cid)
            current = cid
            continue
        if current is None:
            continue
        status_m = TRIAGE_STATUS_RE.match(raw.strip())
        if not status_m:
            continue
        verb_raw = status_m.group(1).strip()
        verb, duplicate_of = _parse_verb(verb_raw, lineno)
        if current in entries:
            raise OnboardError(
                f"triage.md line {lineno}: duplicate status for {current}. "
                f"Keep exactly one `- status:` line per section."
            )
        if duplicate_of is not None and duplicate_of not in known_ids:
            raise OnboardError(
                f"triage.md line {lineno}: duplicate-of target "
                f"{duplicate_of} is not a known candidate in this run."
            )
        entries[current] = TriageEntry(
            candidate_id=current,
            verb=verb,
            duplicate_of=duplicate_of,
        )

    # Fill in pending for any candidate absent from triage
    for cid in known_ids:
        if cid not in entries:
            entries[cid] = TriageEntry(candidate_id=cid, verb="pending")
    return entries


def _parse_verb(raw: str, lineno: int) -> tuple[str, str | None]:
    raw_lower = raw.lower()
    if raw_lower in ("pending", "accept", "reject", "edit"):
        return raw_lower, None
    if raw_lower.startswith("duplicate-of:"):
        _, _, target = raw.partition(":")
        target = target.strip()
        if not CAND_ID_RE.match(target):
            raise OnboardError(
                f"triage.md line {lineno}: duplicate-of target must be C-NNN, "
                f"got {target!r}"
            )
        return "duplicate", target
    raise OnboardError(
        f"triage.md line {lineno}: unknown status verb {raw!r}. "
        f"Expected one of: accept, reject, edit, pending, duplicate-of:C-NNN"
    )


# ---------------------------------------------------------------------------
# Draft → 015 record field extraction
# ---------------------------------------------------------------------------


def _parse_draft_fields(draft_path: Path) -> dict[str, Any]:
    """Extract title, summary, location, key_behaviors, known_gaps from a
    draft file by routing through 015's canonical parser.

    Drafts use `DRAFT-NNN` in the title; 015's parser requires `AR-NNN`.
    We rewrite the prefix to `AR-000` in a stripped in-memory copy (the
    banner HTML comment is also removed) and call
    `adoption.parse_record_text`. This keeps 017 honest to the
    contract: drafts share 015's on-disk shape, and commit-time
    validation is exactly the validation that will run again on the
    real record.
    """
    # Wrap the read + normalization + parse together so that I/O and
    # decoding errors (OSError, UnicodeDecodeError) surface as
    # OnboardError. commit_run() catches OnboardError per-candidate,
    # so a single unreadable draft no longer aborts the whole batch
    # (per-candidate failure isolation contract).
    try:
        raw = draft_path.read_text(encoding="utf-8")
        # Strip banner comment lines (HTML comments like the draft
        # banner) AND any blank padding those produced. The banner is
        # purely cosmetic; 015's parser would accept it as an
        # unknown-metadata line but we keep the parse clean.
        kept = []
        for ln in raw.splitlines():
            s = ln.strip()
            if s.startswith("<!--") or s.endswith("-->") or s == "<!--" or s == "-->":
                continue
            kept.append(ln)
        # Drop leading blank lines
        while kept and not kept[0].strip():
            kept.pop(0)
        text = "\n".join(kept) + "\n"
        # Rewrite DRAFT-NNN → AR-000 for 015 parser compatibility. The
        # actual AR id is allocated by 015 at commit time; this
        # sentinel is discarded.
        text = re.sub(
            r"^# Adoption Record: DRAFT-\d{3}:",
            "# Adoption Record: AR-000:",
            text,
            count=1,
            flags=re.MULTILINE,
        )
        # Parse via 015's canonical parser. This delegates ALL field
        # extraction and validation to 015 so drafts never drift.
        record = adoption.parse_record_text(draft_path, text)
    except (OSError, UnicodeDecodeError) as exc:
        raise OnboardError(
            f"{draft_path}: could not read draft: {exc}"
        ) from exc
    except adoption.AdoptionError as exc:
        raise OnboardError(
            f"{draft_path}: draft failed 015 parser: {exc}"
        ) from exc

    return {
        "title": record.title,
        "summary": record.summary,
        "location": record.location,
        "key_behaviors": record.key_behaviors,
        "known_gaps": record.known_gaps,
    }


# ---------------------------------------------------------------------------
# Scan + commit
# ---------------------------------------------------------------------------


def _git_head_sha(repo_root: Path) -> str | None:
    git_bin = _resolve_git()
    if git_bin is None:
        return None
    try:
        result = subprocess.run(
            [git_bin, "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            check=True, capture_output=True, text=True, timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError,
            subprocess.TimeoutExpired):
        return None
    sha = result.stdout.strip()
    return sha or None


def _default_run_name() -> str:
    return f"{date.today().isoformat()}-initial"


def _run_dir_for(repo_root: Path, run_name: str) -> Path:
    return repo_root / ADOPTION_RUNS_DIRNAME / run_name


def scan(
    repo_root: Path,
    *,
    run_name: str | None = None,
    heuristics: Iterable[str] = HEURISTICS_MVP,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> Path:
    """Phase 1+2 combined: discover candidates, write manifest + triage + drafts."""
    run_name = run_name or _default_run_name()
    run_dir = _run_dir_for(repo_root, run_name)
    if run_dir.exists():
        raise OnboardError(
            f"Run directory already exists: {run_dir}. "
            f"Pass --run <new-name> or delete the existing directory."
        )
    run_dir.mkdir(parents=True)

    candidates = discover(
        repo_root=repo_root,
        heuristics=heuristics,
        score_threshold=score_threshold,
    )
    manifest = OnboardingManifest(
        run_id=run_name,
        created=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        phase="review",
        repo_root=str(repo_root),
        baseline_commit=_git_head_sha(repo_root),
        heuristics_enabled=list(heuristics),
        score_threshold=score_threshold,
        candidates=candidates,
    )
    write_drafts(run_dir, candidates)
    write_manifest(run_dir, manifest)
    _atomic_write(run_dir / "triage.md", render_triage(manifest))
    return run_dir


def commit_run(
    run_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Phase 4: read triage, call 015's create_record for accepts.

    Idempotent on retry: candidates already in `manifest.committed` or
    `manifest.rejected` are skipped. Parsed triage decisions are
    written back into `manifest.candidates[*].triage` so a subsequent
    re-read preserves operator intent.

    Returns a summary dict with committed / rejected / failed / dry_run.
    """
    manifest = read_manifest(run_dir)
    triage_path = run_dir / "triage.md"
    if not triage_path.exists():
        raise OnboardError(f"No triage.md at {triage_path}")
    triage_text = triage_path.read_text(encoding="utf-8")
    entries = parse_triage(triage_text, manifest)

    already_committed = {
        e.get("candidate_id") for e in manifest.committed
        if isinstance(e, dict)
    }
    already_rejected = {
        e.get("candidate_id") for e in manifest.rejected
        if isinstance(e, dict)
    }

    # Persist triage decisions onto the manifest candidates so the YAML
    # round-trips operator intent (BLOCKER fix).
    for c in manifest.candidates:
        entry = entries.get(c.id)
        if entry is None:
            continue
        c.triage = entry.verb
        c.duplicate_of = entry.duplicate_of

    # Block commit while any candidate is still pending — but exclude
    # candidates already fully resolved in a prior run.
    pending = [
        cid for cid, e in entries.items()
        if e.verb == "pending"
        and cid not in already_committed
        and cid not in already_rejected
    ]
    if pending:
        raise OnboardError(
            f"Cannot commit while {len(pending)} candidate(s) pending: "
            f"{sorted(pending)}. Mark each with accept/reject/edit/"
            f"duplicate-of in triage.md."
        )

    repo_root = Path(manifest.repo_root)
    planned: list[dict[str, Any]] = []
    for c in manifest.candidates:
        entry = entries[c.id]
        # Idempotence: never re-commit something already in the audit trail.
        if c.id in already_committed or c.id in already_rejected:
            continue
        if entry.verb in ("reject", "duplicate"):
            record = {
                "candidate_id": c.id,
                "reason": entry.verb,
                "duplicate_of": entry.duplicate_of,
            }
            if not dry_run:
                manifest.rejected.append(record)
                # Flush so a crash mid-batch doesn't drop this decision.
                write_manifest(run_dir, manifest)
            else:
                planned.append({"action": entry.verb, "candidate_id": c.id})
            continue
        # accept or edit — both require a commit call
        draft_path = run_dir / c.draft_path
        if not draft_path.exists():
            manifest.failed.append({
                "candidate_id": c.id,
                "error": f"missing draft file: {draft_path}",
            })
            if not dry_run:
                write_manifest(run_dir, manifest)
            continue
        try:
            fields = _parse_draft_fields(draft_path)
        except OnboardError as exc:
            manifest.failed.append({
                "candidate_id": c.id,
                "error": str(exc),
            })
            if not dry_run:
                write_manifest(run_dir, manifest)
            continue
        if dry_run:
            planned.append({
                "action": "create_record",
                "candidate_id": c.id,
                "title": fields["title"],
                "location": fields["location"],
            })
            continue
        try:
            record = adoption.create_record(
                repo_root=repo_root,
                title=fields["title"],
                summary=fields["summary"],
                location=fields["location"],
                key_behaviors=fields["key_behaviors"],
                known_gaps=fields["known_gaps"],
                baseline_commit=manifest.baseline_commit,
            )
        except adoption.AdoptionError as exc:
            manifest.failed.append({
                "candidate_id": c.id,
                "error": str(exc),
            })
            write_manifest(run_dir, manifest)
            continue
        manifest.committed.append({
            "candidate_id": c.id,
            "ar_id": record.record_id,
            "ar_path": str(record.path.relative_to(repo_root)),
        })
        # Flush immediately after each external write so a crash between
        # create_record and the end-of-batch write_manifest doesn't cause
        # duplicate ARs on retry — the manifest is the idempotence source.
        write_manifest(run_dir, manifest)

    if not dry_run:
        # Phase transition: done if every candidate is resolved.
        resolved_ids = (
            {e["candidate_id"] for e in manifest.committed if isinstance(e, dict)}
            | {e["candidate_id"] for e in manifest.rejected if isinstance(e, dict)}
            | {e["candidate_id"] for e in manifest.failed if isinstance(e, dict)}
        )
        all_ids = {c.id for c in manifest.candidates}
        failed_ids = {
            e["candidate_id"] for e in manifest.failed if isinstance(e, dict)
        }
        # Only transition to `done` when every candidate is committed or
        # rejected. `failed` candidates are retriable, so leaving the
        # phase at `commit` keeps the run visibly incomplete until the
        # operator re-runs commit with the failures fixed.
        if resolved_ids >= all_ids and not failed_ids:
            manifest.phase = "done"
        write_manifest(run_dir, manifest)

    return {
        "committed": len(manifest.committed),
        "rejected": len(manifest.rejected),
        "failed": len(manifest.failed),
        "pending": 0,
        "dry_run": dry_run,
        "planned": planned if dry_run else [],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m speckit_orca.onboard",
        description="Brownfield v2 onboarding pipeline (017).",
    )
    parser.add_argument("--root", default=".",
                        help="Repository root (defaults to cwd)")
    sub = parser.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser("scan", help="Phase 1+2: discover + propose drafts")
    scan_p.add_argument("--run", default=None, help="Run name (default: YYYY-MM-DD-initial)")
    scan_p.add_argument(
        "--heuristics", default=",".join(HEURISTICS_MVP),
        help="Comma-separated list of heuristic ids (MVP: H1,H2,H3,H6)",
    )
    scan_p.add_argument("--score-threshold", type=float, default=DEFAULT_SCORE_THRESHOLD,
                        help=f"Drop candidates below this score (default {DEFAULT_SCORE_THRESHOLD})")

    review_p = sub.add_parser("review", help="Print triage.md path and phase status")
    review_p.add_argument("--run", required=True)

    commit_p = sub.add_parser("commit", help="Phase 4: create ARs for accepted drafts")
    commit_p.add_argument("--run", required=True)
    commit_p.add_argument("--dry-run", action="store_true")

    status_p = sub.add_parser("status", help="Print run summary")
    status_p.add_argument("--run", required=True)

    sub.add_parser("rescan", help="Re-scan for new candidates (v1.1 — deferred in MVP)")

    return parser


def cli_main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.root).resolve()

    try:
        if args.command == "scan":
            heuristics = [h.strip() for h in args.heuristics.split(",") if h.strip()]
            run_dir = scan(
                repo_root=repo_root,
                run_name=args.run,
                heuristics=heuristics,
                score_threshold=args.score_threshold,
            )
            m = read_manifest(run_dir)
            print(f"scan: wrote {run_dir}")
            print(f"scan: phase={m.phase} candidates={len(m.candidates)}")
            print(f"scan: edit {run_dir / 'triage.md'} then run commit")
            return 0

        if args.command == "review":
            run_dir = _run_dir_for(repo_root, args.run)
            m = read_manifest(run_dir)
            print(f"review: phase={m.phase}")
            print(f"review: triage path={run_dir / 'triage.md'}")
            print(f"review: {len(m.candidates)} candidates awaiting decision")
            return 0

        if args.command == "commit":
            run_dir = _run_dir_for(repo_root, args.run)
            summary = commit_run(run_dir, dry_run=args.dry_run)
            print(f"commit: committed={summary['committed']} "
                  f"rejected={summary['rejected']} failed={summary['failed']} "
                  f"dry_run={summary['dry_run']}")
            if summary["dry_run"]:
                for p in summary["planned"]:
                    print(f"  plan: {p}")
            return 0

        if args.command == "status":
            run_dir = _run_dir_for(repo_root, args.run)
            m = read_manifest(run_dir)
            print(f"status: run_id={m.run_id}")
            print(f"status: phase={m.phase}")
            print(f"status: candidates={len(m.candidates)}")
            print(f"status: committed={len(m.committed)}")
            print(f"status: rejected={len(m.rejected)}")
            print(f"status: failed={len(m.failed)}")
            return 0

        if args.command == "rescan":
            print(
                "rescan: deferred to v1.1. MVP only supports initial scans.\n"
                "Workaround: pass --run <new-name> to `scan` for a second run.",
                file=sys.stderr,
            )
            return 2

    except OnboardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(cli_main())
