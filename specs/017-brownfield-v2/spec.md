# Feature Specification: Brownfield v2 — Per-Project Onboarding Pipeline

**Feature Branch**: `017-brownfield-v2`
**Created**: 2026-04-16
**Status**: Draft
**Input**: User description: "Per-project bulk onboarding pipeline for
brownfield codebases. Scan a repo, propose feature candidates, triage
them, commit accepted drafts as Adoption Records via 015's runtime."

## Context

015 shipped the single-record runtime: one AR file per feature,
hand-authored one at a time. That is the right minimum primitive.
Onboarding an existing codebase is a different-shape problem: a
mid-sized Python/TS repo has 30–80 recognizable features, the operator
does not know them cold, and discovery is a judgment call. Authoring
30+ ARs by hand by filling in summary/location/key-behaviors from
scratch is a multi-day slog operators bounce off before finishing.

017 builds the bulk onboarding pipeline on top of 015. It MUST NOT
reshape or bypass 015's AR runtime. It writes drafts to a scratch
directory, lets the operator triage, and calls 015's
`adoption.create_record` per accepted draft. v2 is the authoring
pipeline; v1 is the storage layer.

The MVP ships Phase 1: heuristic-driven discovery + proposal, a
markdown triage surface, and a commit pass. No LLM dependency. No
rescan (v1.1). No interactive CLI review loop (v1.1). See
`brainstorm.md` for the broader design space; this spec is the
narrower shipping contract.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bulk Onboard An Existing Repo (Priority: P1)

A developer has just installed Orca into an existing Python/TS repo
that predates Orca. The repo has ~40 recognizable features
(authentication, CLI entrypoint, data pipeline, etc.). Walking
through `adopt create` 40 times by hand is not going to happen.

**Why this priority**: This is the whole point of 017. Without it,
brownfield onboarding caps at "a couple ARs per week by hand" and
adoption never converges.

**Independent Test**: Point `orca adopt scan` at a fixture repo with
a realistic src/ layout. Verify a run directory is created under
`.specify/orca/adoption-runs/`, with a `manifest.yaml`, a `triage.md`
listing candidates, and one draft file per candidate. No ARs are
written yet. Manually mark a subset as `accept` in triage.md. Run
`orca adopt commit`. Verify the accepted drafts become real ARs via
015's `create_record` and the rest are skipped with reasons recorded.

**Acceptance Scenarios**:

1. **Given** a repo with no prior adoption runs, **When** the
   operator runs `orca adopt scan`, **Then** a new run directory is
   created with a manifest, a triage markdown surface, and one draft
   per discovered candidate, and NO ARs are written to
   `.specify/orca/adopted/`.
2. **Given** a completed scan with drafts waiting for triage, **When**
   the operator marks some candidates as `accept` and others as
   `reject` / `duplicate-of` / `edit` in triage.md, **Then**
   `orca adopt commit` calls 015's `create_record` only for the
   accepted candidates and records the outcome in the manifest.
3. **Given** a draft fails 015's validation at commit time (empty
   summary, empty location, empty key-behaviors), **When** commit
   runs, **Then** that candidate is recorded as `failed` with the
   error message, but other accepted candidates still commit
   successfully. The run does not abort globally.

---

### User Story 2 - Triage Is A Durable Markdown Surface (Priority: P1)

A developer starts triage, closes the laptop, comes back a day later,
and wants to pick up where they left off without re-deriving state.

**Why this priority**: Triage of 40 candidates is a multi-hour task.
A session-dependent CLI loop fails this user. The triage surface MUST
survive interruption.

**Independent Test**: Run `scan`, partially edit `triage.md` to mark
some candidates accept / reject / edit, close the terminal, re-open.
Run `orca adopt commit`. Verify the partial edits are honored — only
explicitly accepted candidates commit; anything still at `pending`
status blocks commit with a clear message.

**Acceptance Scenarios**:

1. **Given** a scan has produced `triage.md`, **When** the operator
   edits the file in any text editor to set `- status: accept` on
   some candidates and `- status: reject` on others, **Then** a later
   `orca adopt commit` reads those decisions deterministically.
2. **Given** any candidate remains at `pending` (unset status),
   **When** commit runs, **Then** the runtime blocks commit with a
   pointer to the pending candidates and exits non-zero. No partial
   commits happen until the operator resolves every candidate.

---

### User Story 3 - 017 Never Mutates Existing ARs (Priority: P1)

A developer runs 017 against a repo that already has hand-authored
ARs from 015. 017 MUST NOT touch the existing ARs — it only proposes
new candidates and, on commit, calls `adoption.create_record` to add
new records with fresh IDs.

**Why this priority**: Load-bearing invariant in brainstorm section
"Relationship to 015 v1". If 017 mutates committed ARs, the whole
contract unravels.

**Independent Test**: Hand-author an AR via 015's `create_record`
directly. Run 017's scan + commit cycle. Verify the original AR's
file contents, id, and status are byte-identical before and after
the 017 run. Verify the new ARs created by 017 have ids that do not
collide.

**Acceptance Scenarios**:

1. **Given** an existing AR at `.specify/orca/adopted/AR-001-foo.md`,
   **When** 017's scan + commit pipeline runs, **Then** AR-001 is
   neither opened nor rewritten (mtime and content hash unchanged).
2. **Given** committed candidates in a run, **When** 015 allocates
   the next AR id via its own advisory lock, **Then** the new ids
   are strictly greater than any existing AR id and there is no
   collision.

### Edge Cases

- What if the operator deletes a draft file between scan and commit?
  017 skips that candidate with a warning in the manifest's `failed`
  section. The run does not abort.
- What if the operator adds an unknown candidate id to `triage.md`?
  Parse error, with line-number pointer. Commit is blocked until
  triage.md is cleaned up.
- What if the repo has no recognizable features (empty src/)? Scan
  emits an empty manifest with `candidates: []` and no drafts.
  Commit is a no-op with a friendly message.
- What if heuristics produce two candidates covering the same path?
  The runtime auto-merges deterministically via `merge_candidates()`
  in `src/speckit_orca/onboard.py` when candidates share both the
  same proposed slug AND a depth->=2 directory prefix (so
  `src/auth` and `packages/auth` stay distinct). Scores combine via
  probabilistic OR and the highest-precedence heuristic wins the
  title. If the operator still wants to override or split the
  merge, they can mark one candidate with
  `duplicate-of: C-NNN` in `triage.md`.
- What if the operator edits a draft file before accepting? The
  content on disk at commit time is what 017 passes to
  `create_record`. Edits are preserved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 017 MUST scan a repo for feature candidates using
  heuristics H1 (directory grouping), H2 (entry points via
  pyproject / package.json / setup.py), H3 (README headings), and
  H6 (git history density — files touched together frequently
  across commits, clustered via union-find). Note: this
  relabels the brainstorm's H6 (package/import boundaries) to
  align with MVP scope; package-boundary discovery is already
  covered by H1 and is not shipped separately. The brainstorm's
  H4 (git history) is promoted to H6 here.
- **FR-002**: Every discovered candidate MUST have a confidence
  score in [0.0, 1.0]. Candidates with score below a configurable
  threshold (default 0.3) MUST be dropped before the triage surface
  is written.
- **FR-003**: 017 MUST persist every run under
  `.specify/orca/adoption-runs/<YYYY-MM-DD>-<slug>/` containing
  `manifest.yaml` (run state), `triage.md` (operator surface), and
  `drafts/DRAFT-NNN-<slug>.md` (one per candidate).
- **FR-004**: `manifest.yaml` MUST record run_id, created,
  repo_root, baseline_commit, heuristics_enabled, per-candidate
  state (id, draft_path, proposed_title, proposed_slug, paths,
  signals, score, triage verb, merge/duplicate target), and
  committed/rejected/failed audit sections.
- **FR-005**: `triage.md` MUST be the canonical operator review
  surface. Each candidate gets a section with the status verbs
  `pending | accept | reject | edit | duplicate-of:C-NNN`. Commit
  MUST refuse to run while any candidate is `pending`.
  `edit` and `accept` both trigger a `create_record` call — `edit`
  is semantically "operator revised the draft, now accept it";
  `reject` and `duplicate-of` never commit. Per brainstorm section
  "Review surface → Recommendation", this is intentional; the
  verbs differ in audit signal, not commit behavior.
- **FR-006**: 017 MUST call `speckit_orca.adoption.create_record`
  for every accepted candidate. 017 MUST NOT write files directly
  under `.specify/orca/adopted/`.
- **FR-007**: 017 MUST respect 015's validation. If a draft lacks
  a summary, location, or key-behaviors that pass 015's checks,
  the commit for THAT candidate fails (recorded in the manifest's
  `failed` list) but the run continues for other accepted
  candidates.
- **FR-008**: 017 MUST NOT mutate existing AR records. Commit is
  additive only; 017 calls `create_record`, nothing else.
- **FR-009**: The command surface MUST extend the existing
  `/speckit.orca.adopt` prompt with `scan`, `review`, `commit`, and
  `rescan` subcommands. 017 MUST NOT introduce a new top-level
  command.
- **FR-010**: `scan` MUST refuse to overwrite an existing run
  directory. If the operator invokes `scan` with a name that
  already exists, the runtime MUST exit non-zero and tell them to
  pick a new `--run` name or delete the existing directory.
- **FR-011**: 017 MUST be deterministic given fixed inputs. Same
  repo state + same heuristic flags MUST produce the same
  candidate list (same ids, same paths, same scores). Stable
  ordering: candidates sorted by (score desc, proposed_slug asc).
- **FR-012**: Every draft file MUST be valid-enough to pass 015's
  parser after the two documented preprocessing steps: (a) strip
  the uncommitted-draft banner (an HTML comment), and (b) rewrite
  `# Adoption Record: DRAFT-NNN:` to `# Adoption Record: AR-000:`
  in an in-memory copy so 015's id regex accepts it. Drafts share
  015's on-disk shape otherwise (title, Status, Adopted-on,
  Summary, Location, Key Behaviors) and carry a `Status: adopted`
  placeholder that 015's renderer expects at commit time. No other
  post-processing is permitted.
- **FR-013**: 017 MUST record, in the manifest, the git HEAD SHA at
  scan time as `baseline_commit` so the run has a reproducible
  anchor.
- **FR-014**: Heuristic H1 MUST emit one candidate per cohesive
  subdirectory under configurable source roots (default `src/`,
  `lib/`, `packages/`, `app/`). Directories whose name is in the
  grab-bag denylist (`utils`, `helpers`, `common`, `lib`, `shared`,
  `misc`, `internal`) MUST be scored below threshold and dropped
  unless a higher-precision heuristic (H2/H3) also fires on the
  same path.
- **FR-015**: Heuristic H2 MUST extract entry points from
  `pyproject.toml` (`[project.scripts]` and
  `[project.entry-points]`), `package.json` (`bin` field), and
  `setup.py` (`entry_points` dict). Each entry point MUST produce
  a candidate whose location points at the referenced module path
  if resolvable on disk.
- **FR-016**: Heuristic H3 MUST parse `README.md` at repo root (and
  `docs/README.md` if present) and emit one candidate per H2
  heading whose text looks like a feature name (not boilerplate
  like `Installation`, `Getting Started`, `License`, `Contributing`,
  `Usage`).
- **FR-017**: Heuristic H6 MUST compute co-change clusters from
  `git log --name-only` over a bounded window (default 180 days,
  capped at 500 commits). Files that change together frequently
  form a cluster; each cluster is scored and, if above threshold,
  proposed as a candidate.
- **FR-018**: `commit` MUST support `--dry-run` which prints the
  candidates that WOULD be committed and the `create_record`
  arguments for each, without actually creating any ARs.

### Key Entities *(include if feature involves data)*

- **ScanRun**: Durable record of one scan+triage+commit cycle.
  Identified by run_id (date-slug). State lives in
  `manifest.yaml`. Phases: `discovery | review | commit | done`.
- **CandidateRecord**: One proposed feature. Fields: id (C-NNN),
  proposed_title, proposed_slug, paths, signals (list of
  "H1:src/auth" style tags), score, triage verb, draft_path.
- **TriageEntry**: Operator decision for one candidate, expressed
  in `triage.md` as `- status: accept | reject | edit |
  duplicate-of:C-NNN`. Parsed back into the manifest at commit
  time.
- **OnboardingManifest**: The top-level YAML structure. Holds
  run_id, created, phase, repo_root, baseline_commit,
  heuristics_enabled, list of candidates, committed, rejected,
  failed, duplicates.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Scanning a repo with 10+ obvious features (distinct
  src/ subdirectories plus entry points) produces a candidate list
  that recovers ≥80% of those features on the first run.
- **SC-002**: A scan + commit cycle against a 1k-file repo
  completes in under 10 seconds wall-clock on a standard laptop
  (no LLM round trips, no network).
- **SC-003**: A commit pass that hits a validation error on one
  candidate does NOT block the other accepted candidates from
  committing. Partial success is the expected shape.
- **SC-004**: 017's MVP ships with zero new runtime dependencies
  beyond what's already in pyproject.toml. No pyyaml, no network,
  no LLM client.
- **SC-005**: Existing ARs written by 015 are bit-identical before
  and after a 017 scan + commit cycle.

## Documentation Impact *(mandatory)*

- **README Impact**: Light. Extend the brownfield section to
  mention bulk onboarding once ready.
- **Expected Updates**: `commands/adopt.md` (scan/review/commit/
  rescan subcommand guidance), README brownfield section.

## Assumptions

- 015's `adoption.create_record` is the only write path into
  `.specify/orca/adopted/`. 017 relies on its advisory lock, id
  allocation, and overview regeneration.
- Repos targeted by 017 are primarily Python and/or TypeScript
  with a recognizable `src/` (or `lib/`, `packages/`, `app/`)
  source root. Polyglot and unusual layouts are v1.1 work.
- Operators edit `triage.md` in a normal text editor and re-run
  `orca adopt commit`. No background daemon watches the file.
- A manifest format that looks like YAML but is parsed by a
  hand-written subset parser is acceptable for the MVP; adopting
  PyYAML is a v1.1 decision if the schema grows.
- The brainstorm is the source of truth for scope; this spec
  narrows MVP to what ships in the first PR.

## Out Of Scope

- LLM-aided drafting (H7 and summary/key-behavior drafting) —
  v1.2 per brainstorm sequencing.
- Interactive CLI review loop — v1.1.
- `rescan` incremental-run logic — v1.1.
- `audit` / `import` / `extend` — v2.
- Cross-repo onboarding — different spec.
- Non-spec-kit SDD format import (OpenSpec, spec-kitty) — 016.
- Auto-merge of duplicate candidates — operator-driven only.
- Mutating existing ARs — never. Hard invariant.
