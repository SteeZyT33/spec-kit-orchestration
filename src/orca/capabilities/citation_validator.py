"""citation-validator capability (rule-based, v1).

Detects uncited assertion-shaped sentences and broken `[ref]` brackets in
synthesis text. Pure Python: regex + filesystem ref index. No LLM. v2 may
add an LLM mode for semantic claims that aren't surface-syntactic.

Citation coverage is `cited_assertions / total_assertions`, defined as 1.0
when there are zero assertions (vacuous truth, not a divide-by-zero).

Markdown-aware preprocessing strips fenced code blocks (``` and ~~~), skips
table rows, and skips spec-kit scaffolding patterns (FR-NNN bullets, session
headers, **Field**: lines, Run N/M tags) before assertion detection. The
ref-shape filter ignores bracket contents that look like prose
(`[all: 1440 1438 1445]`) so they are neither flagged as broken nor counted
as citations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from orca.core.errors import Error, ErrorKind
from orca.core.result import Err, Ok, Result

VERSION = "0.1.0"

_VALID_MODES = ("strict", "lenient")

# Sentence with strong-claim verbs.
_ASSERTION_VERBS = re.compile(
    r"\b(shows?|demonstrates?|proves?|confirms?|indicates?|establishes?)\b",
    re.IGNORECASE,
)

# Numerical claim: percentage or double-digit-or-larger number.
_NUMERIC_CLAIM = re.compile(r"\b\d+(?:\.\d+)?\s*%|\b\d{2,}\b")

# `[ref]` bracket pattern. Non-greedy, no nested brackets.
_REF_PATTERN = re.compile(r"\[([^\[\]]+?)\]")

# Fence open/close marker: line that starts (after optional whitespace) with
# triple backticks or triple tildes. The rest of the line (language tag) is
# allowed.
_FENCE_PATTERN = re.compile(r"^\s*(```+|~~~+)")

# Markdown table row: line that starts and ends with a pipe (allowing
# trailing whitespace).
_TABLE_ROW_PATTERN = re.compile(r"^\s*\|.*\|\s*$")

# Spec-kit / generic scaffolding patterns that are not prose claims and
# should be excluded from assertion detection.
_SCAFFOLDING_PATTERNS: tuple[re.Pattern[str], ...] = (
    # **FR-001**: requirement (allows leading `- ` bullets, blockquote `>`,
    # or any whitespace).
    re.compile(r"^[\s\->*]*\*\*FR-\d+\*\*\s*:", re.IGNORECASE),
    # ### Session 2026-04-27 (with optional 2-5 hashes)
    re.compile(r"^\s*#{2,5}\s+Session\s+\d{4}-\d{2}-\d{2}", re.IGNORECASE),
    # **Field**: value (catches Field, Status, etc.) - also tolerates
    # leading bullet/blockquote markers.
    re.compile(r"^[\s\->*]*\*\*[A-Z][\w-]*\*\*\s*:", re.IGNORECASE),
    # Run 1/3: ...
    re.compile(r"^\s*Run\s+\d+\s*/\s*\d+\s*:", re.IGNORECASE),
)


@dataclass(frozen=True)
class CitationValidatorInput:
    content_text: str | None = None
    content_path: str | None = None
    reference_set: list[str] = field(default_factory=list)
    mode: str = "strict"
    skip_patterns: list[str] = field(default_factory=list)


def citation_validator(inp: CitationValidatorInput) -> Result[dict, Error]:
    """Validate citations in synthesis text.

    Returns Ok with uncited_claims, broken_refs, well_supported_claims,
    citation_coverage. INPUT_INVALID for missing/conflicting content sources,
    bad mode, non-existent content_path, or an uncompilable skip_pattern.
    """
    # Mutual exclusion at the capability boundary, matching schema oneOf.
    if inp.content_text is None and inp.content_path is None:
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message="must provide content_text or content_path",
        ))
    if inp.content_text is not None and inp.content_path is not None:
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message="content_text and content_path are mutually exclusive",
        ))

    if inp.mode not in _VALID_MODES:
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message=f"mode must be one of {list(_VALID_MODES)}, got {inp.mode!r}",
        ))

    # Compile operator-supplied skip patterns. Defaults always apply; custom
    # patterns extend the default list.
    custom_patterns: list[re.Pattern[str]] = []
    for pat in inp.skip_patterns:
        try:
            custom_patterns.append(re.compile(pat))
        except re.error as exc:
            return Err(Error(
                kind=ErrorKind.INPUT_INVALID,
                message=f"invalid skip_pattern: {pat!r}: {exc}",
            ))

    if inp.content_path is not None:
        path = Path(inp.content_path)
        if not path.exists():
            return Err(Error(
                kind=ErrorKind.INPUT_INVALID,
                message=f"content_path does not exist: {path}",
            ))
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        text = inp.content_text or ""

    available_refs = _index_refs(inp.reference_set)

    # Strip fenced code blocks first so their lines don't reach the
    # assertion detector. We replace fenced lines with empty lines so line
    # numbers in the output stay aligned with the input.
    cleaned = _strip_code_fences(text)

    uncited: list[dict] = []
    broken: list[dict] = []
    well_supported: list[dict] = []
    total_assertions = 0

    for line_num, line in enumerate(cleaned.splitlines(), start=1):
        # Skip table rows wholesale. Pipe-delimited cells are not prose.
        if _is_table_row(line):
            continue
        # Skip spec-kit scaffolding patterns.
        if _is_scaffolding(line, custom_patterns):
            continue

        for sentence in _split_sentences(line):
            if not _is_assertion(sentence, mode=inp.mode):
                continue
            total_assertions += 1
            refs = _REF_PATTERN.findall(sentence)
            # A "real" ref is a footnote-marker digit OR a ref-shaped
            # bracket. Prose-shaped brackets like `[all: 1440 1438]` are
            # ignored entirely.
            real_refs = [
                r for r in refs
                if r.strip().isdigit() or _is_reflike(r)
            ]
            if not real_refs:
                uncited.append({"text": sentence.strip(), "line": line_num})
                continue
            sentence_well_supported = True
            for ref in real_refs:
                # Pure-digit brackets are footnote markers ([1], [42]),
                # not file refs; skip without flagging as broken.
                if ref.strip().isdigit():
                    continue
                if not _ref_resolves(ref, available_refs):
                    broken.append({"ref": ref, "line": line_num})
                    sentence_well_supported = False
            if sentence_well_supported:
                well_supported.append({"text": sentence.strip(), "line": line_num})

    # Vacuous truth: no assertions -> full coverage (not 0/0).
    coverage = 1.0 if total_assertions == 0 else (total_assertions - len(uncited)) / total_assertions

    return Ok({
        "uncited_claims": uncited,
        "broken_refs": broken,
        "well_supported_claims": well_supported,
        "citation_coverage": round(coverage, 3),
    })


def _index_refs(reference_set: list[str]) -> set[str]:
    """Index reference paths by full path, basename, and stem for lookup."""
    out: set[str] = set()
    for ref in reference_set:
        p = Path(ref)
        out.add(str(p))
        out.add(p.name)
        out.add(p.stem)
    return out


# Common abbreviations that contain a period but should not end a sentence.
# English-centric and non-exhaustive; matches the v1 rule-based scope.
_ABBREVIATIONS = (
    "Dr.", "Mr.", "Mrs.", "Ms.", "St.", "Inc.", "Ltd.", "Co.",
    "e.g.", "i.e.", "etc.", "vs.", "cf.", "Fig.", "Eq.",
)


def _strip_code_fences(text: str) -> str:
    """Replace lines inside fenced code blocks with empty lines.

    Detects both triple-backtick (```) and triple-tilde (~~~) fences,
    optionally indented, optionally followed by a language tag. Tracks
    fence state across the whole document; a new fence opens, the next
    matching marker closes. Mismatched fence types are tolerated by only
    matching the same marker type that opened the current block.

    Preserves line count so downstream line numbers stay aligned. An
    unclosed fence at EOF simply leaves the remaining lines stripped.
    """
    lines = text.splitlines()
    out: list[str] = []
    in_fence = False
    fence_marker: str | None = None  # "`" or "~"

    for line in lines:
        m = _FENCE_PATTERN.match(line)
        if not in_fence:
            if m:
                # Open a new fence. Record marker char (first char of match).
                in_fence = True
                fence_marker = m.group(1)[0]
                out.append("")  # strip the fence opener line itself
            else:
                out.append(line)
        else:
            # Inside a fence. Check if this line closes the same marker.
            if m and fence_marker is not None and m.group(1)[0] == fence_marker:
                in_fence = False
                fence_marker = None
                out.append("")  # strip the closing fence line
            else:
                out.append("")  # strip code-block line
    return "\n".join(out)


def _is_table_row(line: str) -> bool:
    """Return True for pipe-delimited markdown table rows.

    Matches lines that both start and end with `|` (allowing surrounding
    whitespace). Header separator rows like `| --- | --- |` match too.
    """
    return bool(_TABLE_ROW_PATTERN.match(line))


def _is_scaffolding(line: str, custom: list[re.Pattern[str]]) -> bool:
    """Return True if the line matches any default or custom scaffolding regex."""
    for pat in _SCAFFOLDING_PATTERNS:
        if pat.search(line):
            return True
    for pat in custom:
        if pat.search(line):
            return True
    return False


def _is_reflike(s: str) -> bool:
    """A ref candidate must be path-like, anchor-like, or ref:-prefixed.

    - Pure digits are caught earlier (footnote markers, skipped).
    - Spaces disqualify (rules out `[all: 1440 1438]`).
    - Colons disqualify UNLESS it's an explicit `ref:NAME` form.
    - Anchors `#name` are accepted as ref-like.
    """
    s = s.strip()
    if not s:
        return False
    if any(c.isspace() for c in s):
        return False
    if s.startswith("ref:"):
        return bool(s[4:])
    if s.startswith("#"):
        return len(s) > 1
    if ":" in s:
        return False
    return True


def _split_sentences(line: str) -> list[str]:
    """Split a line on sentence-ending punctuation, with a small
    abbreviation guard to avoid mid-sentence false splits.

    Naive but fits the rule-based scope. v2 (LLM mode) would handle this
    correctly via tokenization.
    """
    # Mask abbreviations so the splitter doesn't treat their dots as sentence
    # boundaries. Use a placeholder that survives the regex split, then unmask.
    masked = line
    placeholders: dict[str, str] = {}
    for i, abbr in enumerate(_ABBREVIATIONS):
        placeholder = f"\x00ABBR{i}\x00"
        if abbr in masked:
            placeholders[placeholder] = abbr
            masked = masked.replace(abbr, placeholder)

    parts = [s for s in re.split(r"(?<=[.!?])\s+", masked) if s]
    if not placeholders:
        return parts

    return [_unmask(p, placeholders) for p in parts]


def _unmask(text: str, placeholders: dict[str, str]) -> str:
    for placeholder, original in placeholders.items():
        text = text.replace(placeholder, original)
    return text


def _is_assertion(sentence: str, *, mode: str) -> bool:
    if mode == "lenient":
        return bool(_NUMERIC_CLAIM.search(sentence))
    return bool(_ASSERTION_VERBS.search(sentence) or _NUMERIC_CLAIM.search(sentence))


def _ref_resolves(ref: str, available: set[str]) -> bool:
    candidate = ref.strip()
    # Strip explicit `ref:` prefix for resolution. The prefix is a marker
    # that signals "this bracket is intentionally a citation"; the actual
    # name to resolve is what follows.
    if candidate.startswith("ref:"):
        candidate = candidate[4:]
    return (
        candidate in available
        or Path(candidate).name in available
        or Path(candidate).stem in available
    )
