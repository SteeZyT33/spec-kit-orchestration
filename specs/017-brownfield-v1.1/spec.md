# Feature Specification: Brownfield v1.1 — H4, H5, Rescan

**Feature Branch**: `017-brownfield-v1.1`
**Created**: 2026-04-16
**Status**: Draft
**Input**: "Extend the 017 MVP onboarding pipeline with the two deferred
heuristics (H4 ownership, H5 test coverage) and incremental rescan."

## Context

The v1.0 MVP (PR #60) shipped H1/H2/H3/H6 plus scan + commit. It
established the manifest, draft, and commit contracts against 015's
`adoption.create_record`. The two known gaps were the deferred
heuristics (H4 ownership signals, H5 test-coverage annotation) and
the `rescan` incremental-discovery command.

v1.1 closes those three gaps. It does NOT:

- mutate existing AR records (invariant from v1.0),
- introduce new runtime dependencies (pyproject.toml stays at
  `dependencies = []`),
- change the manifest / triage / draft shapes (existing runs remain
  round-trippable by the v1.1 runtime),
- bypass 015's `create_record` — rescan is an additive discovery
  phase only; committing a rescan run flows through the same
  `commit_run` as the initial scan.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Ownership Concentration Improves Discovery (Priority: P2)

A repo with a CODEOWNERS file (or clear `git blame` concentration per
directory) should surface those directories as stronger candidates.
Conversely, directories with fragmented ownership across many authors
read as "infrastructure" and should not clear threshold on their own.

**Independent Test**: Fixture repo with `src/auth/` owned by a single
author and `src/shared/` touched by eight authors equally. Run scan.
Expect the auth directory picks up an `H4:owner:<name>` signal and a
score bump; the shared directory picks up `H4:fragmented` with no
bump (and remains dropped by the grab-bag rule).

**Acceptance Scenarios**:

1. **Given** a `CODEOWNERS` file declaring `/src/auth/ @alice`,
   **When** scan runs, **Then** the auth candidate carries
   `H4:owner:alice` in its signals and its score is boosted above
   the H1-only baseline.
2. **Given** a directory with >= 5 distinct git authors and no
   CODEOWNERS entry, **When** scan runs, **Then** H4 does not
   contribute to the score for that directory (no bump) and emits
   an `H4:fragmented` signal for audit visibility.
3. **Given** the repo has no git history, **When** H4 runs, **Then**
   the heuristic returns empty — it never raises, never blocks a
   scan on a fresh `git init`.

---

### User Story 2 — Test Coverage Becomes A Signal (Priority: P2)

A directory with a dedicated test module (`tests/test_auth.py` for
`src/auth/`) is stronger evidence of a feature boundary than a
directory with zero tests or tests split across many unrelated test
files.

**Independent Test**: Fixture repo with `src/auth/` + `tests/test_auth.py`
(cohesive), `src/payments/` + no test file, `src/shared/` + tests
scattered across eight test files. Expect H5 bumps auth, leaves
payments neutral, and annotates shared as fragmented.

**Acceptance Scenarios**:

1. **Given** `src/auth/` and `tests/test_auth.py` both exist,
   **When** scan runs, **Then** the auth candidate picks up
   `H5:tests:test_auth.py` in signals and a score bump.
2. **Given** `src/payments/` with no matching test file, **When**
   scan runs, **Then** the payments candidate carries
   `H5:no-tests` as an informational annotation and receives no
   score bump.
3. **Given** a directory whose source files are split across many
   unrelated test files, **When** scan runs, **Then** the candidate
   picks up `H5:fragmented:<count>` and a `+0.05` bump (per FR-105).

---

### User Story 3 — Rescan Surfaces Only New Work (Priority: P1)

After the initial run has committed a set of ARs, the operator ships
new features and wants to onboard them without re-triaging the
already-adopted ones.

**Independent Test**: Run scan, commit some ARs. Add a new directory
`src/metrics/` with 2 source files. Run `rescan --from <initial-run>`.
Expect a NEW run directory under `adoption-runs/` with only metrics
as a fresh candidate, and the initial run's manifest / triage /
drafts are byte-identical before and after.

**Acceptance Scenarios**:

1. **Given** a prior run whose manifest lists committed ARs covering
   `src/auth/*` paths, **When** `orca adopt rescan --from <prior-run>`
   runs after `src/metrics/` is added, **Then** the new run directory
   contains only `metrics` as a new candidate; auth is skipped as
   already covered.
2. **Given** a prior run's artifacts, **When** rescan runs, **Then**
   the prior run's `manifest.yaml`, `triage.md`, and every file
   under `drafts/` are byte-identical before and after (SHA-256 +
   mtime unchanged).
3. **Given** a candidate in the rescan whose paths partially overlap
   an existing AR's Location bullets, **When** rescan classifies it,
   **Then** the candidate is marked as `changed` (score delta from
   the prior run) rather than `new`, and the new-run triage surfaces
   the existing AR id for operator context.
4. **Given** rescan completes, **When** summary prints, **Then** it
   reports `N new, M changed, K stale`.

### Edge Cases

- Prior run directory missing or malformed: rescan exits non-zero
  with a clear error pointing at `--from`.
- No new candidates discovered: rescan still writes a new run
  directory with an empty candidates list and prints `0 new`.
- CODEOWNERS parse failures: H4 swallows the error and returns no
  signals rather than blocking scan.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-101**: H4 MUST compute ownership concentration per directory
  derived from H1. Sources, in precedence order: (a) a CODEOWNERS
  entry that covers the directory, (b) `git shortlog -s -n` output
  over a bounded window. If neither source yields an author, H4
  MUST return no signal for that directory.
- **FR-102**: H4 MUST assign a bump using a concentration ratio
  (top-author commits / total commits). Thresholds: >= 0.7 bump
  +0.2, >= 0.5 bump +0.1, otherwise 0. A directory with >= 5
  distinct authors AND concentration < 0.5 MUST be tagged with
  `H4:fragmented` and receive no bump.
- **FR-103**: H4 MUST never raise on a repo with no git history —
  on `git rev-parse` failure (or git binary missing), the heuristic
  returns an empty list.
- **FR-104**: H5 MUST map each H1-style directory candidate to its
  matching test files. Matching rules (all checked; first match wins):
  `tests/test_<name>.py`, `tests/test_<name>/*.py`, `test/test_<name>.py`,
  `<dir>/tests/*.py`, `<dir>/__tests__/*` for JS/TS.
- **FR-105**: H5 bumps: +0.15 when exactly one dedicated test file
  or test directory covers the candidate; +0.05 when a test module
  exists but more than one test file references the source paths;
  0 when no test module covers the directory. Candidates with no
  tests receive an `H5:no-tests` annotation only.
- **FR-106**: `rescan` MUST accept `--from <run-slug>` pointing at a
  prior completed run under `.specify/orca/adoption-runs/`. It MUST
  create a NEW run directory named `YYYY-MM-DD-rescan-N` (N
  increments if the default name is taken).
- **FR-107**: Rescan MUST classify every newly discovered candidate
  as `new`, `changed`, or (for stale manifest inspection only)
  `stale`. Classification rules:
  - `new`: no path overlap with any existing AR Location or any
    candidate committed in the prior run.
  - `changed`: path overlap with an AR but the new paths list
    differs from the AR Location list OR the score differs from
    the prior candidate by >= 0.1.
  - `stale`: a candidate that was present in the prior run's
    `candidates` list (by slug + path overlap) but is no longer
    discovered in the rescan. Stale entries are listed in the new
    manifest for operator visibility; they do NOT produce drafts
    and never flow through commit.
- **FR-108**: Rescan MUST be additive only. It MUST NOT rewrite,
  delete, or otherwise mutate the prior run's `manifest.yaml`,
  `triage.md`, or any file under `drafts/`. It MUST NOT mutate
  any existing AR record under `.specify/orca/adopted/`.
- **FR-109**: Rescan MUST print a summary line of the form
  `N new, M changed, K stale` (exact phrasing). Summary prints
  to stdout at the end of the command.
- **FR-110**: The `rescan` CLI subcommand in
  `src/speckit_orca/onboard.py` MUST require `--from <slug>` and
  SHOULD accept `--run <new-slug>` to override the auto-generated
  rescan name.
- **FR-111**: When rescan identifies `changed` candidates that
  overlap existing ARs, the manifest's per-candidate `signals` list
  MUST include `rescan:extends:AR-NNN` for operator context (so
  the triage surface shows which AR the new paths would extend).
  017 MUST NOT modify that AR; the operator decides whether to
  update it by hand or accept the new candidate as a sibling AR.
- **FR-112**: Existing `orca adopt scan`, `commit`, `status`,
  `review` subcommands MUST continue to work identically — v1.1
  additions are strictly additive.

### Key Entities

- **OwnershipSignal**: Derived per directory from CODEOWNERS or git
  shortlog; carries top-author name, concentration ratio, author
  count.
- **TestCoverageSignal**: Per directory; carries matched test file
  paths and a "cohesive | fragmented | absent" classification.
- **RescanSummary**: `{new: int, changed: int, stale: int,
  skipped_already_covered: int}` attached to the new run's
  manifest as a top-level `rescan_summary` key.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-101**: On a repo with CODEOWNERS that covers 3 feature
  directories and fragments a `shared/` directory, H4 bumps all
  three features and leaves shared below threshold.
- **SC-102**: On a repo with `tests/test_<name>.py` cohesion for a
  feature, H5 bumps that feature's score by +0.15 exactly.
- **SC-103**: Rescan on a repo with one new directory since the
  prior run produces exactly one new candidate and zero writes to
  the prior run directory (verified by SHA-256 hash of every file
  before/after).
- **SC-104**: v1.1 ships with zero new runtime dependencies. Every
  heuristic + rescan uses stdlib + `subprocess` + `speckit_orca.adoption`.
- **SC-105**: All 471 v1.0 tests still pass after v1.1 lands.

## Documentation Impact *(mandatory)*

- **commands/adopt.md**: add the `rescan` subcommand section under
  "Bulk Onboarding". Update heuristics bullet list to note H4 and
  H5 are now live.
- **README**: no change.

## Assumptions

- The `git` binary is available in most target environments. When
  absent, H4 and H6 degrade gracefully.
- Test layout conventions across Python / JS / TS repos match the
  FR-104 matching rules in the 80% case. Unusual layouts are fine;
  they simply produce an `H5:no-tests` annotation and the operator
  can still accept the candidate.
- A prior run's manifest is the source of truth for what "already
  covered" means. If the operator retired or superseded an AR
  outside 017 after the prior run, rescan will not re-propose the
  path (it still lives in `.specify/orca/adopted/*.md` as the
  historical record).

## Out Of Scope

- Auto-updating existing ARs with new paths when a rescan finds
  `changed` candidates. The operator decides.
- LLM-based ownership or test-coverage inference. Pure heuristics.
- CODEOWNERS glob wildcards beyond simple directory-prefix
  matching. Complex OWNERS patterns are v1.2.
- Parallelism across heuristics. Single-threaded stays fast on
  repos in the MVP performance envelope.
