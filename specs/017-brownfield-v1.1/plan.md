# Implementation Plan: Brownfield v1.1 — H4, H5, Rescan

**Branch**: `017-brownfield-v1.1` | **Date**: 2026-04-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/017-brownfield-v1.1/spec.md`

## Summary

Extend `src/speckit_orca/onboard.py` with three features:

1. **H4 ownership signals** — computes per-directory top-author
   concentration from CODEOWNERS or `git shortlog -s -n`. Bumps H1
   candidates whose directory has a concentrated owner; flags
   fragmented directories without bumping.
2. **H5 test coverage** — maps H1 candidates to co-located test
   files (Python and TS/JS conventions). Bumps cohesive mappings,
   annotates fragmented or absent mappings.
3. **Rescan** — `orca adopt rescan --from <prior-run>` creates a new
   timestamped run, classifies candidates as new / changed / stale
   against the prior run + existing AR registry, and prints a
   summary. Strictly additive; never mutates prior manifests or AR
   records.

All three features preserve the v1.0 invariants: no new runtime
dependencies, no direct writes to `.specify/orca/adopted/`, retry
idempotence on commit, and per-candidate failure isolation.

## Technical Context

**Language/Version**: Python 3.10+ (unchanged)
**Primary Dependencies**: `speckit_orca.adoption` via import (unchanged)
**Storage**: `.specify/orca/adoption-runs/<slug>/` — same shape as
v1.0; rescan writes a fresh sibling directory, never mutates the
prior one.
**Testing**: pytest; TDD red-green per sub-phase; fixture-based
end-to-end tests targeting each new heuristic + the rescan flow.
**Performance Goals**: same SC-002 envelope (scan + commit under
10s on a 1k-file repo). H4 shells out to `git shortlog`; should add
<100ms on repos we target.
**Constraints**: zero new deps, deterministic output, v1.0 shapes
unchanged.

## Constitution Check

Pre-design gates:

1. **Provider-agnostic orchestration** — pass. Local Python only.
2. **Spec-driven delivery** — pass. spec.md + this plan land ahead
   of implementation.
3. **Safe parallel work** — pass. Rescan writes a NEW directory;
   no shared mutable state with the prior run.
4. **Verification before convenience** — pass. Rescan does not auto-
   update any AR; operator still drives every commit through
   triage + `create_record`.
5. **Small, composable runtime surfaces** — pass. Three new pure
   functions (`heuristic_h4_ownership`, `heuristic_h5_test_coverage`,
   `rescan`), wired into the existing `discover` + `cli_main`.

Post-design check:

- No existing AR file is opened for write.
- No new dependency in pyproject.toml.
- Every AR still lands via 015's `create_record`.
- Retry idempotence (already-committed / already-rejected skip) is
  preserved — the commit flow is unchanged; only discovery grows.
- Per-candidate failure isolation preserved — H4 and H5 failures
  swallow at the heuristic boundary; rescan failures abort rescan
  but never leave the prior run corrupt.

## Project Structure

```text
specs/017-brownfield-v1.1/
├── spec.md
├── plan.md
└── tasks.md

src/speckit_orca/
└── onboard.py           (EXTENDED — new functions, no refactors)

tests/
└── test_onboard.py      (EXTENDED — new test classes)

commands/
└── adopt.md             (EXTENDED — rescan subcommand section)
```

No new files. No new packages. The v1.0 module grows by ~250 LOC.

## Design Decisions

### 1. H4 is an annotator, not a primary discoverer

Rationale: ownership signal is meaningful only against a known
feature boundary. A directory with one owner but no source files is
still not a feature. Feeding H4 the H1 candidate list as input and
letting it return a `(signal, score_bump)` per candidate keeps the
heuristic tight and deterministic.

Shape:

```python
def heuristic_h4_ownership(
    repo_root: Path,
    candidates: list[CandidateRecord],
) -> list[CandidateRecord]:
    """Returns a list of augmented candidates with H4 signals/bumps.
    Never emits new candidates; never removes existing ones."""
```

The `discover` orchestrator calls H4 AFTER H1/H2/H3/H6 so its
annotations ride on whatever candidates merged out of those four.

### 2. H5 likewise annotates H1 candidates only

Same rationale. Matching test files to unknown candidates is a
less reliable signal than matching them to a known directory
boundary. H5 runs after H4, both in annotator mode.

### 3. CODEOWNERS parsing is a 20-line subset

Supported shape (matches GitHub's documented simple case):

```text
# comments start with #
/src/auth/ @alice
/src/payments/ @bob @carol
docs/       @docs-team
```

Not supported (silently ignored): glob wildcards beyond trailing
`/**`, email addresses (`name@example.com`), team references with
nested scopes. Unrecognized lines fall through without raising.

Precedence: most specific path wins. A `CODEOWNERS` entry always
overrides `git shortlog` for that directory.

### 4. Rescan design

Rescan is a new top-level operation, not a mutation of scan. The
core flow:

```python
def rescan(
    repo_root: Path,
    from_run: str,        # slug of prior run
    new_run: str | None,  # new run slug; auto-generated if None
    heuristics: Iterable[str] = HEURISTICS_V1_1,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> Path:
    """Classify new candidates against prior run + AR registry.
    Writes a new run directory; returns its path.
    """
```

Classification flow:

1. Load prior manifest.
2. Build `covered_paths` = union of (prior run committed AR
   Location bullets) ∪ (prior run rejected candidate paths that
   remain valid signals of "operator said no").
3. Run `discover()` against current repo HEAD.
4. For each new candidate:
   - overlap with `covered_paths` + exact match of prior slug →
     skip (drop silently; recorded in rescan_summary as
     "skipped_already_covered").
   - partial overlap + slug match → `changed`; annotate with
     `rescan:extends:AR-NNN` signal if an AR is found.
   - partial overlap with no slug match but substantial path
     overlap → `changed`.
   - no overlap → `new`.
5. For each prior candidate NOT re-emitted: record in
   `rescan_stale` list on the new manifest (no draft produced).
6. Write new manifest, triage.md (only `new` + `changed` get
   sections), drafts/ (only for `new` + `changed`).
7. Emit summary line.

**Hard invariant**: before returning, rescan re-hashes the prior
run directory's contents and asserts byte-identical to its pre-run
hash. If any file changed, raise OnboardError — this is a
belt-and-braces guard for the "never mutate prior run" invariant.

### 5. Wiring into `discover`

`HEURISTICS_V1_1 = ("H1", "H2", "H3", "H4", "H5", "H6")`.
The v1.0 `HEURISTICS_MVP` stays as-is for back-compat; callers that
pass an explicit list (including tests) keep their behavior. The
CLI default shifts to `HEURISTICS_V1_1`. A single new flag
`--heuristics H1,H2,...` still works.

Orchestration order:

1. Run H1, H2, H3, H6 as today → produce base candidates.
2. Merge via `merge_candidates` (unchanged).
3. Run H4 on the merged list → annotations/bumps.
4. Run H5 on the merged list → annotations/bumps.
5. Apply `score_threshold`, sort, re-id (unchanged).

This keeps H4/H5 out of the merge problem: they never emit
duplicates because they never emit new candidates.

## Implementation Sub-Phases

### Sub-phase F — H4 ownership (TDD)

Functions:

- `_parse_codeowners(path: Path) -> dict[str, list[str]]`
- `_git_shortlog_authors(repo_root, directory) -> list[tuple[str, int]]`
- `_ownership_bump(author_count, concentration) -> tuple[float, str]`
- `heuristic_h4_ownership(repo_root, candidates) -> list[CandidateRecord]`

Tests:

- CODEOWNERS with single owner → signal + bump
- no CODEOWNERS, git shortlog concentrated → signal + bump
- no CODEOWNERS, many authors, low concentration → `H4:fragmented`,
  no bump
- no git history → empty annotations, no raise

### Sub-phase G — H5 test coverage (TDD)

Functions:

- `_find_test_files(repo_root, candidate) -> list[Path]`
- `_coverage_classification(matches, paths) -> str` (cohesive /
  fragmented / absent)
- `heuristic_h5_test_coverage(repo_root, candidates) -> list[CandidateRecord]`

Tests:

- cohesive: `tests/test_auth.py` only → bump +0.15
- fragmented: `tests/test_auth.py` + `tests/test_login.py` both
  reference auth → bump +0.05
- absent: no tests reference auth → `H5:no-tests`, no bump
- JS/TS conventions: `__tests__/` directory works

### Sub-phase H — Rescan (TDD)

Functions:

- `_load_ar_coverage_index(repo_root) -> dict[str, str]` (path → AR id)
- `_classify_rescan_candidate(c, prior_cands, ar_index) -> tuple[str, str | None]`
- `rescan(repo_root, from_run, new_run, ...) -> Path`

Tests:

- new candidate classification (new path added since prior run)
- changed candidate classification (prior candidate, different
  score)
- stale candidate classification (prior candidate missing now)
- prior run directory is byte-identical before/after (hash set
  assertion)
- missing `--from` target → OnboardError
- rescan + commit → new ARs get fresh ids via 015's allocator
- summary line format matches FR-109 exactly

### Sub-phase I — CLI + docs wiring

- Wire `rescan` into `cli_main`, require `--from`, accept `--run`
  and `--heuristics`. Remove the v1.0 deferred-message branch.
- Extend `commands/adopt.md` rescan section with the new surface.
- Update the heuristics bullet list in adopt.md to list H4 and H5.

## Verification Strategy

### Primary

1. `uv run python -m pytest tests/test_onboard.py -v` — new tests green.
2. `uv run python -m pytest --tb=short` — all 471 v1.0 tests still
   green.
3. Manually run `python -m speckit_orca.onboard scan` against a
   fixture with CODEOWNERS + tests/ + git history; inspect signals
   and scores.
4. Manually run `rescan --from <initial>` after adding a new
   directory; inspect rescan_summary.

### Secondary

1. Confirm prior run hash invariant via the test from sub-phase H.
2. Confirm zero new dependencies: `uv tree | wc -l` unchanged
   between v1.0 and v1.1 (no new transitive pulls).
3. Re-run v1.0 idempotence tests to confirm retry behavior intact.

### Cross-harness verification

Run the codex read-only review after all tests pass. Address
BLOCKERs before push.

## Out Of Scope (Explicit)

- `adopt audit` (stale AR detection) — deferred to 017-brownfield-v2.
- LLM-aided drafting (H7) — deferred to v1.2.
- `adopt extend <ar-id>` — no in-place AR updates.
- CODEOWNERS glob patterns beyond trailing `/**` — v1.2.
- Operator-identity capture in the manifest — not needed for v1.1.

## Open Questions (Deferred)

- Should rescan support `--from <prior-run>` pointing at an
  incomplete run? v1.1 answer: no — require prior phase `done` or
  `commit`. Scanning against a prior `review`-phase run makes the
  "already covered" signal unreliable.
- Should H5 also consume coverage reports (`.coverage`,
  `coverage.xml`)? Deferred — heuristic test-file matching is the
  cheap-and-deterministic first cut.
