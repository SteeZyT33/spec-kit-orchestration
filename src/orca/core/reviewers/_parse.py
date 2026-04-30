"""Shared JSON-array extraction logic for reviewer adapters.

Both ClaudeReviewer and CodexReviewer call into LLM-or-CLI-backed agents
and parse a JSON array of finding dicts from the output text. Centralizing
that parser here prevents drift and keeps test coverage in one place.

The parser is resilient to chatty output: greedy regex first (catches the
typical "single array, possibly fenced" case), then a balanced-bracket
scan that picks the LAST list-of-dicts (final-answer convention) when
the greedy match fails.
"""
from __future__ import annotations

import json
import re
from typing import Any

from orca.core.reviewers.base import ReviewerError


_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)


def parse_findings_array(text: str, *, source: str = "response") -> list[dict[str, Any]]:
    """Extract a JSON array of finding dicts from agent output.

    Returns raw `list[dict[str, Any]]`; per-finding schema validation is the
    caller's job (capability code constructs `Finding` instances).

    `source` is interpolated into error messages so callers can localize
    diagnostic context (e.g., "response", "codex output").
    """
    match = _JSON_ARRAY.search(text)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return _validate_findings_array(data, source)
        except json.JSONDecodeError:
            pass  # fall through to balanced-scan

    for candidate in reversed(_balanced_arrays(text)):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list) and (not data or isinstance(data[0], dict)):
            return _validate_findings_array(data, source)

    raise ReviewerError(
        f"could not parse JSON array from {source}: {text[:200]}"
    )


def validate_findings_array(data: list[Any], *, source: str) -> list[dict[str, Any]]:
    """Validate a pre-parsed list of findings (e.g., from a trusted source).

    Use this instead of parse_findings_array when the caller has already
    parsed the JSON and just needs per-finding shape validation. Skips the
    regex-extract step parse_findings_array does for chatty LLM output.

    Raises ReviewerError on shape violations (matches parse_findings_array's
    contract).
    """
    return _validate_findings_array(data, source)


def _validate_findings_array(
    data: list[Any], source: str
) -> list[dict[str, Any]]:
    """Enforce list-of-dicts at the parser boundary.

    Downstream Finding.from_raw uses dict subscripting (raw["category"]),
    which raises TypeError on non-dict input. Catching it here keeps the
    capability layer's failure path uniform: malformed reviewer output
    becomes ReviewerError(underlying='malformed_finding'), not a TypeError
    crash that escapes the Result contract.
    """
    if not all(isinstance(item, dict) for item in data):
        raise ReviewerError(
            f"non-dict item in findings array from {source}",
            retryable=False,
            underlying="malformed_finding",
        )
    return data


def _balanced_arrays(text: str) -> list[str]:
    """Find all top-level balanced [...] spans, ignoring brackets in JSON
    strings. Naive scanner; good enough for LLM/CLI output."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "[":
            i += 1
            continue
        depth = 0
        in_string = False
        escape = False
        start = i
        while i < n:
            c = text[i]
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = not in_string
            elif not in_string:
                if c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                    if depth == 0:
                        out.append(text[start:i + 1])
                        i += 1
                        break
            i += 1
        else:
            # Unterminated [ ran to end-of-text. The remainder cannot
            # contain a balanced top-level array, so abandon scanning.
            break
    return out
