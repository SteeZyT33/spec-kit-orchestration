"""citation-validator capability (rule-based, v1).

Detects uncited assertion-shaped sentences and broken `[ref]` brackets in
synthesis text. Pure Python: regex + filesystem ref index. No LLM. v2 may
add an LLM mode for semantic claims that aren't surface-syntactic.

Citation coverage is `cited_assertions / total_assertions`, defined as 1.0
when there are zero assertions (vacuous truth, not a divide-by-zero).
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


@dataclass(frozen=True)
class CitationValidatorInput:
    content_text: str | None = None
    content_path: str | None = None
    reference_set: list[str] = field(default_factory=list)
    mode: str = "strict"


def citation_validator(inp: CitationValidatorInput) -> Result[dict, Error]:
    """Validate citations in synthesis text.

    Returns Ok with uncited_claims, broken_refs, well_supported_claims,
    citation_coverage. INPUT_INVALID for missing/conflicting content sources,
    bad mode, or non-existent content_path.
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

    uncited: list[dict] = []
    broken: list[dict] = []
    well_supported: list[dict] = []
    total_assertions = 0

    for line_num, line in enumerate(text.splitlines(), start=1):
        for sentence in _split_sentences(line):
            if not _is_assertion(sentence, mode=inp.mode):
                continue
            total_assertions += 1
            refs = _REF_PATTERN.findall(sentence)
            if not refs:
                uncited.append({"text": sentence.strip(), "line": line_num})
                continue
            sentence_well_supported = True
            for ref in refs:
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
    return (
        candidate in available
        or Path(candidate).name in available
        or Path(candidate).stem in available
    )
