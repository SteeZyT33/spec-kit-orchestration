"""Parse `.cmux/setup` to produce a ContractProposal.

Per docs/superpowers/specs/2026-05-01-orca-worktree-contract-design.md
§"Migration helpers" — strict pattern matcher with tolerance for
documented idiomatic variations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Loop iterable: literal bareword tokens only
# Tokens: [A-Za-z0-9._/-]+ (no $, no ${, no quotes, no ()
_BAREWORD_RE = r"[A-Za-z0-9._/-]+"
_LOOP_RE = re.compile(
    r"for\s+(?P<var>\w+)\s+in\s+(?P<items>(?:" + _BAREWORD_RE + r"\s+)*"
    + _BAREWORD_RE + r")\s*;\s*do\s*\n"
    r"(?P<body>(?:.|\n)*?)"
    r"\bdone\b",
    re.MULTILINE,
)

# Body shape — symlink-or-replace pattern with tolerated variations.
# We accept any of: [, [[, test predicates with -e/-f/-d/-L
# We accept ln -s, ln -sf, ln -snf, ln -sfn
# Must reference $f or $d (the loop var) on the right-hand side
_BODY_PRED = (
    r"(?:\[\[?\s*-[efdL]\s+|\btest\s+-[efdL]\s+)"
    r"\"?\$\{?(?:REPO_ROOT/)?\w+\}?\"?\s*\]?\]?"
)
_BODY_LN = r"\bln\s+-s[fn]{0,2}\b"


@dataclass
class ParseResult:
    symlink_paths: list[str] = field(default_factory=list)
    symlink_files: list[str] = field(default_factory=list)
    init_script_body: str = ""
    warnings: list[str] = field(default_factory=list)


def _body_matches_symlink_pattern(body: str) -> bool:
    """Check if the body contains the documented symlink-or-replace shape.

    Tolerates inline comments, blank lines, line continuations, and the
    tolerated test/[[/[ forms.
    """
    # Strip comments and blank lines
    cleaned = "\n".join(
        line for line in body.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )
    has_pred = re.search(_BODY_PRED, cleaned) is not None
    has_ln = re.search(_BODY_LN, cleaned) is not None
    return has_pred and has_ln


def parse_cmux_setup(content: str) -> ParseResult:
    """Parse a `.cmux/setup` script and extract symlink lists + build steps.

    Strict pattern: requires bareword-list iterables; warns on non-matching
    loops. Build steps (non-loop content) are preserved as `init_script_body`.
    """
    result = ParseResult()
    handled_spans: list[tuple[int, int]] = []

    for match in _LOOP_RE.finditer(content):
        items = match.group("items").split()
        body = match.group("body")
        var_name = match.group("var")
        start, end = match.span()

        if not _body_matches_symlink_pattern(body):
            line_start = content[:start].count("\n") + 1
            line_end = content[:end].count("\n") + 1
            result.warnings.append(
                f"cmux setup line {line_start}-{line_end}: cannot extract "
                f"symlinks; hand-migrate this block"
            )
            continue

        # Heuristic: var name "d" → path; var "f" → file; otherwise
        # fall back to inspecting items (a leading "." suggests a file).
        if var_name == "d":
            is_file_loop = False
        elif var_name == "f":
            is_file_loop = True
        else:
            is_file_loop = any(it.startswith(".") for it in items)
        if is_file_loop:
            result.symlink_files.extend(items)
        else:
            result.symlink_paths.extend(items)
        handled_spans.append((start, end))

    # Now check for non-extracted `for` loops the regex didn't catch
    # (quoted iterables, $(...) iterables, etc.) — emit warnings.
    for m in re.finditer(r"for\s+\w+\s+in\s+([^;]+);\s*do", content):
        span = m.span()
        if any(start <= span[0] < end for start, end in handled_spans):
            continue
        line_start = content[:span[0]].count("\n") + 1
        # Non-bareword iterable
        result.warnings.append(
            f"cmux setup line {line_start}: cannot extract symlinks "
            f"(non-bareword iterable); hand-migrate this block"
        )

    # Preserve everything except the handled loop spans as init_script_body
    if handled_spans:
        handled_spans.sort()
        kept_chunks: list[str] = []
        cursor = 0
        for start, end in handled_spans:
            kept_chunks.append(content[cursor:start])
            cursor = end
        kept_chunks.append(content[cursor:])
        result.init_script_body = "".join(kept_chunks).strip()
    else:
        result.init_script_body = content.strip()

    return result
