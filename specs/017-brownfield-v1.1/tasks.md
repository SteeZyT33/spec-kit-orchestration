# Tasks: Brownfield v1.1 — H4, H5, Rescan

**Input**: `specs/017-brownfield-v1.1/plan.md`, `spec.md`
**Prerequisites**: v1.0 MVP (PR #60) landed; `src/speckit_orca/onboard.py`
shipped with H1/H2/H3/H6 + scan + commit.
**TDD**: every GREEN has a RED predecessor.

**Target file**: `src/speckit_orca/onboard.py`
**Test file**: `tests/test_onboard.py`

## Sub-phase F — H4 Ownership Signals (TDD)

- [ ] T101 RED: test `heuristic_h4_ownership` with a CODEOWNERS
      file declaring `/src/auth/ @alice` — expect the auth
      candidate carries `H4:owner:alice` signal AND score > H1
      baseline.
- [ ] T102 GREEN: implement `_parse_codeowners` + the CODEOWNERS
      branch of `heuristic_h4_ownership`.
- [ ] T103 RED: test H4 against a repo with no CODEOWNERS but
      concentrated git shortlog (one author has 80% of commits on
      the directory) — expect an owner signal + bump.
- [ ] T104 GREEN: implement `_git_shortlog_authors` + git branch of
      `heuristic_h4_ownership`.
- [ ] T105 RED: test H4 with many authors, low concentration —
      expect `H4:fragmented` signal, no bump.
- [ ] T106 GREEN: implement fragmentation classification.
- [ ] T107 RED: test H4 on a repo with no git history — expect
      empty annotations, no raise.
- [ ] T108 GREEN: confirm graceful degradation path.

**Checkpoint F**: H4 annotates deterministically across all four
branches. `uv run python -m pytest tests/test_onboard.py -k H4` green.

## Sub-phase G — H5 Test Coverage (TDD)

- [ ] T109 RED: test `heuristic_h5_test_coverage` with
      `src/auth/` + `tests/test_auth.py` — expect
      `H5:tests:test_auth.py` signal and +0.15 bump.
- [ ] T110 GREEN: implement `_find_test_files` + cohesive branch.
- [ ] T111 RED: test H5 with multiple test files referencing the
      same source paths — expect `H5:fragmented`, +0.05 bump.
- [ ] T112 GREEN: implement fragmentation classification.
- [ ] T113 RED: test H5 with no matching test file — expect
      `H5:no-tests`, no bump.
- [ ] T114 GREEN: implement absent branch.
- [ ] T115 RED: test H5 on TS/JS repo with `__tests__/` directory —
      expect cohesive match.
- [ ] T116 GREEN: extend matching rules for TS/JS conventions.

**Checkpoint G**: H5 classifies every branch deterministically.

## Sub-phase H — Rescan (TDD)

- [ ] T117 RED: test rescan with one new directory added since the
      prior run — expect the new run contains exactly the new
      candidate and summary prints `1 new, 0 changed, 0 stale`.
- [ ] T118 GREEN: implement `rescan()` plus the minimal
      `_load_ar_coverage_index`.
- [ ] T119 RED: test prior run is byte-identical before/after
      rescan (SHA-256 of every file in the prior run dir).
- [ ] T120 GREEN: confirm; add explicit hash-preservation assertion
      inside `rescan()`.
- [ ] T121 RED: test `changed` classification — same slug, prior
      candidate score drifted beyond threshold delta.
- [ ] T122 GREEN: implement `_classify_rescan_candidate`.
- [ ] T123 RED: test `stale` classification — prior candidate no
      longer discoverable.
- [ ] T124 GREEN: implement stale listing.
- [ ] T125 RED: test missing `--from` run directory → OnboardError.
- [ ] T126 GREEN: implement validation.
- [ ] T127 RED: test rescan summary line exact format from FR-109.
- [ ] T128 GREEN: implement `_format_rescan_summary`.
- [ ] T129 RED: test rescan + commit pipeline — new ARs get fresh
      ids, existing ARs untouched.
- [ ] T130 GREEN: confirm path wires through existing `commit_run`.

**Checkpoint H**: Rescan deterministically classifies new / changed
/ stale and preserves prior artifacts.

## Sub-phase I — CLI Wiring + Docs

- [ ] T131 RED: test CLI `rescan --from <prior>` creates a new run
      and exits 0 with summary in stdout.
- [ ] T132 GREEN: wire `rescan` into `cli_main`, require
      `--from`, accept `--run` + `--heuristics`.
- [ ] T133 Extend `commands/adopt.md` with `rescan` subcommand
      docs + update the heuristics bullet list to include H4/H5.
- [ ] T134 Run full suite: `uv run python -m pytest --tb=short`.
      471 v1.0 tests + new v1.1 tests all green.

**Checkpoint I**: CLI works, docs updated, full suite green.

## Dependencies & Execution Order

- F → G → H → I. Heuristics land before rescan; rescan reads the
  discovery pipeline but doesn't need to hold off on I.
- Within F / G / H: RED always before GREEN.

## Parallel Opportunities

- T101/T103/T105/T107 RED tests can be drafted in one pass; then
  implement T102/T104/T106/T108 sequentially.
- F and G are independent once dataclasses exist — can overlap if
  two agents pair.
- H depends on F + G (rescan uses the same discover + heuristic
  pipeline).

## Out Of Scope (v1.2+)

- `adopt audit`, `adopt extend`, LLM-aided drafting.
- Complex CODEOWNERS glob support.
- Coverage-report-based test coverage (vs. file-path matching).
