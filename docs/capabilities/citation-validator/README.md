# citation-validator

Detects uncited claims and broken refs in synthesis text using rule-based heuristics. v1 is regex + filesystem only; no LLM. v2 may add LLM mode for semantic claims.

## Status: Lint, Not Scientific Validation

This is a **lint check**, not formal validation of scientific or factual claims. Rule-based assertion detection is imprecise: it flags surface-syntactic patterns (verbs, numerics) and misses semantic claims, while occasionally flagging non-claims that happen to match. Treat the output as an editorial pass over citation hygiene, not as proof that all claims in the document are well-supported.

## Heuristics

- **Assertion-shaped sentence:** sentences containing strong-claim verbs ("shows", "demonstrates", "proves", "confirms", "indicates", "establishes") OR numerical claims (percentages, double-digit numbers).
- **Citation:** the `[ref]` bracket pattern at any position in the sentence. Each match is checked for ref-shape (see below) before being treated as a citation candidate.
- **Broken ref:** any ref-shaped `[ref]` whose name does not resolve to a path in the `reference_set` by exact match, basename, or filename stem.

### Markdown-aware preprocessing

Before assertion detection runs, the validator strips chrome that is not prose:

- **Fenced code blocks** (` ``` ` and ` ~~~ `, indented or not, with or without a language tag) are skipped wholesale. Line numbers in the output stay aligned because fenced lines are blanked, not removed. Unclosed fences at EOF are tolerated.
- **Markdown table rows** (lines starting and ending with `|`) are skipped. Header separators like `| --- | --- |` skip too.
- **Spec-kit scaffolding patterns** are skipped via a built-in regex list:
  - `**FR-NNN**: ...` requirement bullets
  - `### Session YYYY-MM-DD` log headers (2-5 hashes)
  - `**Field**: value` style bullets (any `**Capitalized**:` label)
  - `Run N/M: ...` verification-run tags
- **Custom skip patterns** can be added via the `skip_patterns` input. Each entry is a Python regex matched per line; matches are skipped on top of the built-in list.

### Ref-shape rules

Bracket contents are classified before any resolution:

- **Pure digits** (`[1]`, `[42]`) are footnote markers - the bracket counts as a citation but never produces a broken_ref.
- **Path-like** (no whitespace, no colons): `[evidence.md]`, `[docs/foo]`, `[my-evidence]`. Resolved against the reference_set.
- **Anchor** (`[#section]`): treated as a ref candidate; resolves only if the anchor name appears in the reference_set.
- **Explicit `ref:NAME`** (`[ref:my-evidence]`): the `ref:` prefix is stripped for resolution, so the rest follows the path-like rules.
- **Prose-shaped** (contains spaces, or contains `:` without the `ref:` prefix): for example `[all: 1440 1438 1445]`. These are ignored entirely - neither flagged as broken nor counted as citations. A sentence whose only brackets are prose-shaped is treated as having no refs at all (uncited if it is otherwise an assertion).

### Example

```markdown
**FR-001**: System shows 50% improvement.   <- skipped (FR scaffolding)

| Metric | Value |                          <- skipped (table row)
| ------ | ----- |                          <- skipped (table row)
| Speed  | 50%   |                          <- skipped (table row)

```bash
echo "Results show 99% throughput"          <- skipped (code fence)
```

Results show 42% improvement [evidence.md]. <- well-supported (path-like ref)
Results show 42% [all: 1440 1438 1445].     <- uncited (prose-shaped bracket ignored)
```

## Modes

- `strict`: every assertion-shaped sentence requires a citation.
- `lenient`: only sentences with numerical claims require citation.

## Input

See `schema/input.json`. Either `content_text` (inline string) OR `content_path` (file path), never both. `reference_set` is the list of paths against which `[ref]` brackets are resolved. `mode` defaults to `strict`. Optional `skip_patterns` is a list of Python regex strings; matching lines are skipped on top of the built-in scaffolding patterns. Invalid regex strings produce `INPUT_INVALID`.

## Output

See `schema/output.json`.
- `uncited_claims[]`: assertion sentences without any `[ref]` bracket.
- `broken_refs[]`: `[ref]` brackets that did not resolve.
- `well_supported_claims[]`: assertion sentences whose every `[ref]` resolved.
- `citation_coverage`: ratio in [0, 1] of cited assertions vs total assertions. `1.0` when there are zero assertions.

## Errors

- `INPUT_INVALID`: neither `content_text` nor `content_path` set; both set; bad mode value; non-existent `content_path`; uncompilable `skip_patterns` entry.

## Limitations (v1)

- Rule-based; semantic claims that aren't surface-syntactic slip through.
- The assertion-verb list is fixed and English-centric.
- Refs match by exact / basename / stem only; no fuzzy matching, no anchor-checking inside ref files.
- Numeric-claim regex flags any double-digit number, including years (e.g., "Released in 2024" produces an uncited assertion). Operators can avoid this by phrasing prose without bare year numerals or by switching to `lenient` mode (which also reduces false positives in non-numeric prose).
- `[path:line]` form does not resolve in v1; use plain `[path]` brackets. Pure-digit brackets like `[42]` are treated as footnote markers (cited) and never produce broken_refs.
- Sentence splitter has a small abbreviation guard for `Dr.`, `Mr.`, `Mrs.`, `Ms.`, `St.`, `Inc.`, `Ltd.`, `Co.`, `e.g.`, `i.e.`, `etc.`, `vs.`, `cf.`, `Fig.`, `Eq.`. Other abbreviations (e.g., domain-specific) may produce mid-sentence false splits.

## CLI

`orca-cli citation-validator --content-path synthesis.md --reference-set events.jsonl --reference-set experiments.tsv`
or
`orca-cli citation-validator --content-text "Results show 42% [evidence]." --reference-set ./evidence.md`
