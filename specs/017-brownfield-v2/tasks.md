# Tasks: Brownfield v2 — Per-Project Onboarding Pipeline (MVP)

**Input**: `specs/017-brownfield-v2/plan.md`, `spec.md`, `brainstorm.md`
**Prerequisites**: 015 runtime (`src/speckit_orca/adoption.py`) shipped.
**TDD**: All runtime code follows red-green-refactor. Tests before
implementation. Every GREEN task has a RED predecessor.

**Organization**: Tasks follow the plan's five sub-phases (A–E). Each
sub-phase lands tests first, then implementation. Phase checkpoints
verify via `uv run pytest tests/test_onboard.py`.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)

**Target file**: `src/speckit_orca/onboard.py`
**Test file**: `tests/test_onboard.py`

---

## Sub-phase A — Manifest Dataclasses + File I/O (TDD)

**Purpose**: Durable on-disk run state. The foundation everything
else reads and writes.

- [ ] T001 RED: Write tests for `CandidateRecord` dataclass — id
      format `C-NNN`, proposed_title/slug/paths/signals/score fields,
      triage verb enum, duplicate_of optional, draft_path string.
- [ ] T002 GREEN: Implement `CandidateRecord` dataclass.
- [ ] T003 RED: Write tests for `OnboardingManifest` dataclass —
      run_id, phase enum, baseline_commit, heuristics_enabled,
      candidates list, committed/rejected/failed audit lists.
- [ ] T004 GREEN: Implement `OnboardingManifest` dataclass.
- [ ] T005 RED: Write tests for YAML subset emit — round-trip a
      manifest to YAML text and back, produce identical fields.
      Cover: scalars, lists of strings, lists of dicts, nested
      dicts one level deep, ISO dates, null values.
- [ ] T006 GREEN: Implement `_emit_yaml(manifest)` and
      `_parse_yaml(text) → dict`. Subset only. Unknown keys
      tolerated. Strict on indentation (2 spaces).
- [ ] T007 RED: Write tests for `write_manifest` (atomic) and
      `read_manifest` (raises on missing, raises on malformed).
- [ ] T008 GREEN: Implement file I/O. Use the same tmp-file +
      rename atomic-write pattern as 015.

**Checkpoint A**: Manifest round-trips durably. Tests green.

---

## Sub-phase B — Heuristics H1 + H2 + H3 + H6 (TDD)

**Purpose**: Walk the repo, emit candidate list. Pure functions
`repo_root → list[CandidateRecord]`. Deterministic.

- [ ] T009 RED: Write tests for `heuristic_h1_directories` —
      fixture repo with `src/auth/`, `src/payments/`, `src/utils/`
      under `tmp_path`. Expect H1 fires on auth and payments,
      drops utils (grab-bag denylist).
- [ ] T010 GREEN: Implement H1. Walk source roots, emit one
      candidate per subdirectory with ≥2 source files (by
      extension: .py .ts .tsx .js .jsx .go). Apply grab-bag
      denylist by multiplying score by 0.3.
- [ ] T011 RED: Write tests for `heuristic_h2_entry_points` —
      fixture with `pyproject.toml` declaring two entry points and
      a `package.json` with one `bin`. Expect three candidates.
- [ ] T012 GREEN: Implement H2. Parse pyproject via `tomllib`
      (stdlib 3.11+ — fall back to hand parse for 3.10); parse
      `package.json` via stdlib `json`. No third-party deps.
- [ ] T013 RED: Write tests for `heuristic_h3_readme` — fixture
      README with `## Authentication`, `## Data Pipeline`, and
      `## Installation` (boilerplate). Expect two candidates.
- [ ] T014 GREEN: Implement H3. Read README.md; extract H2
      headings; drop boilerplate (`Installation`, `Getting Started`,
      `Usage`, `License`, `Contributing`, `Quickstart`, `Setup`).
- [ ] T015 RED: Write tests for `heuristic_h6_git_cochange` — a
      fake git log (provided via a stub) that co-changes two files
      frequently. Expect one cluster candidate.
- [ ] T016 GREEN: Implement H6. Run `git log --name-only
      --pretty=format: --max-count=500 --since=180.days.ago`,
      parse into per-commit file sets, score file pairs by
      co-occurrence. Merge pairs into clusters via union-find.
      If git missing or the repo has no history: return empty list.
- [ ] T017 RED: Write tests for `merge_candidates` — same-path
      candidates from different heuristics combine signals,
      combine scores via `1 - prod(1 - s_i)`. H3 title wins when
      present; H2 title wins otherwise; H1 is fallback.
- [ ] T018 GREEN: Implement `merge_candidates`.
- [ ] T019 RED: Write tests for `discover(repo_root, heuristics,
      score_threshold)` — orchestrates all four heuristics, merges,
      applies threshold, returns sorted candidate list (score desc,
      slug asc).
- [ ] T020 GREEN: Implement `discover`.

**Checkpoint B**: Discovery is deterministic and covers the MVP
heuristics. Tests green.

---

## Sub-phase C — Proposal Generator (TDD)

**Purpose**: Emit one draft AR per candidate, parseable by 015.

- [ ] T021 RED: Write tests for `render_draft(candidate, signals)`
      — draft has title heading matching 015's format, Status:
      adopted, Adopted-on today, Summary (TODO placeholder),
      Location list, Key Behaviors (TODO placeholder).
- [ ] T022 GREEN: Implement `render_draft`. Reuse 015's header +
      body shape exactly. Prepend an HTML comment banner warning
      it is uncommitted.
- [ ] T023 RED: Write a round-trip test — draft rendered by 017,
      re-parsed by 015's `parse_record`, compare fields.
- [ ] T024 GREEN: Fix any shape drift (MUST be byte-identical to
      015's renderer for the parsed fields).
- [ ] T025 RED: Write tests for `write_drafts(manifest, repo_root)`
      — one file per candidate under
      `.specify/orca/adoption-runs/<run-id>/drafts/`.
- [ ] T026 GREEN: Implement `write_drafts`.

**Checkpoint C**: Drafts round-trip through 015's parser. Tests
green.

---

## Sub-phase D — Triage.md Parser + Commit Flow (TDD)

**Purpose**: Operator decisions flow back into the manifest; commit
calls 015's `create_record`.

- [ ] T027 RED: Write tests for `render_triage(manifest)` — one
      section per candidate, status line defaults to `pending`,
      signals + score + draft link listed.
- [ ] T028 GREEN: Implement `render_triage`.
- [ ] T029 RED: Write tests for `parse_triage(text, manifest)` —
      returns `dict[candidate_id, TriageEntry]`. Cover: accept,
      reject, edit, duplicate-of:C-NNN, pending. Error on unknown
      verbs, missing sections, unknown candidate ids.
- [ ] T030 GREEN: Implement `parse_triage`.
- [ ] T031 RED: Write tests for `commit_run(run_dir, dry_run=False)`
      — pending candidates block commit (non-zero exit / exception).
      Accepted candidates call `adoption.create_record` and append
      to manifest.committed. Rejected / duplicate-of append to
      manifest.rejected. create_record failures land in
      manifest.failed without aborting the run.
- [ ] T032 GREEN: Implement `commit_run`.
- [ ] T033 RED: Write test confirming existing ARs are untouched
      — hash+mtime before and after a commit cycle.
- [ ] T034 GREEN: Verify via assertion.
- [ ] T035 RED: Write test for `--dry-run` — prints planned
      create_record calls, creates zero AR files, leaves manifest
      in review phase.
- [ ] T036 GREEN: Implement dry-run branch in `commit_run`.

**Checkpoint D**: Commit flow works end-to-end through 015's
create_record. Tests green. Zero mutation of existing ARs.

---

## Sub-phase E — CLI Integration (Docs + Module Entry Point)

**Purpose**: Operator-facing surface via `commands/adopt.md` + a
`python -m speckit_orca.onboard` entry point.

- [ ] T037 RED: Write tests for `cli_main(argv)` — subcommands
      `scan`, `review`, `commit`, `rescan`, `status`. `rescan`
      returns non-zero with "v1.1 deferred" message. `scan`
      writes manifest + drafts + triage. `commit` reads triage,
      calls create_record. `status` prints phase + counts.
- [ ] T038 GREEN: Implement `cli_main`. Argparse. Follows the same
      shape as 015's `adoption.cli_main`.
- [ ] T039 Extend `commands/adopt.md` with a new section
      explaining scan/review/commit/rescan subcommands. Keep the
      existing 015 create/list/supersede/retire guidance intact.
- [ ] T040 Run full suite: `uv run pytest --tb=short`. All
      existing tests (320+) plus new onboard tests green.

**Checkpoint E**: CLI works, command prompt documents it, full
suite green.

---

## Dependencies & Execution Order

### Sub-phase dependencies

- **A** (Manifest I/O): foundation.
- **B** (Heuristics): depends on A (CandidateRecord).
- **C** (Drafts): depends on A + B (takes a manifest, reads
  candidates, writes drafts).
- **D** (Triage + Commit): depends on A + C (reads manifest,
  reads drafts, writes audit back to manifest).
- **E** (CLI): depends on A–D.

### Parallel opportunities

- T001/T002 ↔ T003/T004: independent dataclasses.
- T009/T011/T013/T015 (heuristic RED tests) can be drafted in
  parallel as long as they target different fixtures.
- T027/T029 (render + parse triage) can overlap if skeleton
  dataclasses exist.

### TDD Execution Rule

Every GREEN task MUST have its RED predecessor complete and
verified failing first. No production code without a failing test.

---

## Out Of Scope (Deferred to v1.1+)

- `rescan` real logic (only stub message in MVP).
- Interactive CLI review loop.
- H4 (test co-location), H5 (file imports), H7 (LLM reviewer).
- Auto-merge of duplicate candidates.
- Operator identity capture in manifest.
- Contract files under `contracts/`.
- README brownfield section updates.
