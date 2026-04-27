# citation-validator

Detects uncited claims and broken refs in synthesis text using rule-based heuristics. v1 is regex + filesystem only; no LLM. v2 may add LLM mode for semantic claims.

## Status: Lint, Not Scientific Validation

This is a **lint check**, not formal validation of scientific or factual claims. Rule-based assertion detection is imprecise: it flags surface-syntactic patterns (verbs, numerics) and misses semantic claims, while occasionally flagging non-claims that happen to match. Treat the output as an editorial pass over citation hygiene, not as proof that all claims in the document are well-supported.

## Heuristics

- **Assertion-shaped sentence:** sentences containing strong-claim verbs ("shows", "demonstrates", "proves", "confirms", "indicates", "establishes") OR numerical claims (percentages, double-digit numbers).
- **Citation:** the `[ref]` bracket pattern at any position in the sentence. Each match is a candidate ref name to resolve against the `reference_set`.
- **Broken ref:** any `[ref]` whose name does not resolve to a path in the `reference_set` by exact match, basename, or filename stem.

## Modes

- `strict`: every assertion-shaped sentence requires a citation.
- `lenient`: only sentences with numerical claims require citation.

## Input

See `schema/input.json`. Either `content_text` (inline string) OR `content_path` (file path), never both. `reference_set` is the list of paths against which `[ref]` brackets are resolved. `mode` defaults to `strict`.

## Output

See `schema/output.json`.
- `uncited_claims[]`: assertion sentences without any `[ref]` bracket.
- `broken_refs[]`: `[ref]` brackets that did not resolve.
- `well_supported_claims[]`: assertion sentences whose every `[ref]` resolved.
- `citation_coverage`: ratio in [0, 1] of cited assertions vs total assertions. `1.0` when there are zero assertions.

## Errors

- `INPUT_INVALID`: neither `content_text` nor `content_path` set; both set; bad mode value; non-existent `content_path`.

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
