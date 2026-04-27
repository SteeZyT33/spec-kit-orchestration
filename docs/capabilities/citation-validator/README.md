# citation-validator

Detects uncited claims and broken refs in synthesis text using rule-based heuristics. v1 is regex + filesystem only; no LLM. v2 may add LLM mode for semantic claims.

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

## CLI

`orca-cli citation-validator --content-path synthesis.md --reference-set events.jsonl --reference-set experiments.tsv`
or
`orca-cli citation-validator --content-text "Results show 42% [evidence]." --reference-set ./evidence.md`
