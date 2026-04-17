# PR Review — 009-orca-yolo

**PR**: [#49](https://github.com/SteeZyT33/spec-kit-orca/pull/49)
**Title**: feat(009): yolo runtime — event-sourced single-lane execution driver
**Status**: open, mergeable
**Reviewer**: coderabbitai[bot] (automated)
**Local pre-PR review**: CodeRabbit (via `.githooks/pre-push` chain) — "No findings ✔"
**Remote post-push review**: CodeRabbit — 4 actionable + 4 nitpicks + 1 warning

## PR: #49 — review-in-progress

- Round 1 (CodeRabbit): 9 comments (7 ADDRESSED, 1 REJECTED, 1 informational)
- Round 2 (CodeRabbit): 3 comments (3 ADDRESSED)
- Round 3 (Copilot initial): 5 comments (4 ADDRESSED, 1 DUPLICATE)
- Round 4 (Copilot deeper pass): 4 comments (4 ADDRESSED — initial defer on #21 reversed after user verification pushback)
- Total across rounds: 21 dispositions, all resolved

## External Comment Responses

| # | Reviewer | File | Line | Severity | Status | Detail |
|---|---|---|---|---|---|---|
| 1 | coderabbitai | `commands/review-code.md` | 149 | Minor | ADDRESSED in a8f3ab2 | `BASE_REF` now defined via `git merge-base "${ORCA_BASE_BRANCH:-main}" HEAD` |
| 2 | coderabbitai | `commands/yolo.md` | 23 | Minor | ADDRESSED in a8f3ab2 | Added `next` and `recover` to runtime invocation examples |
| 3 | coderabbitai | `specs/009-orca-yolo/brainstorm.md` | 46 | Nit | ADDRESSED in a8f3ab2 | Word order: "adoption records always excluded" |
| 4 | coderabbitai | `specs/009-orca-yolo/spec.md` | 125 | Major | ADDRESSED in a8f3ab2 | FR-007 now marks assign as `(optional)` |
| 5 | coderabbitai | `src/speckit_orca/yolo.py` | 850-873 | Nit | REJECTED | `append_event` raises synchronously on I/O failure; no silent-corruption path exists. The hypothetical race assumes partial writes can be observed by `reduce`, but the OS-level append is atomic and the exception propagates. Adding try/except would only hide real I/O errors. |
| 6 | coderabbitai | `src/speckit_orca/yolo.py` | 182 | Nit | ADDRESSED in a8f3ab2 | Explicit `encoding="utf-8"` on all file I/O (append_event, load_events, _write_snapshot) |
| 7 | coderabbitai | `src/speckit_orca/yolo.py` | 124 | Nit | ADDRESSED in a8f3ab2 | Docstring notes NOT thread-safe per single-writer-per-run contract (runtime-plan section 6). Lock is over-engineering for v1. |
| 8 | coderabbitai | `tests/test_yolo.py` | 570+ | Nit | ADDRESSED in a8f3ab2 | All `pytest.raises(match=...)` now use raw strings |
| 9 | coderabbitai | — | — | Warning | ADDRESSED in a8f3ab2 | Docstring coverage improved: all public API classes/functions now documented |

### Round 2 (after a8f3ab2 push)

| # | Reviewer | File | Line | Severity | Status | Detail |
|---|---|---|---|---|---|---|
| 10 | coderabbitai | `src/speckit_orca/yolo.py` | 895-898 | Actionable | ADDRESSED | `cancel_run` now raises ValueError on empty event log, consistent with resume/next/status/recover |
| 11 | coderabbitai | `src/speckit_orca/yolo.py` | 615-632 | Nit | ADDRESSED | `_write_snapshot` now serializes `mailbox_path` and `last_mailbox_event_id` |
| 12 | coderabbitai | `src/speckit_orca/yolo.py` | 394-412 | Nit | ADDRESSED | `retry_counts` now increments on STAGE_FAILED only (not STAGE_ENTERED). Matches orchestration-policies "2 attempts per fix-loop" semantics. Test renamed accordingly. |

### Round 3 — Copilot (copilot-pull-request-reviewer[bot])

| # | Reviewer | File | Line | Severity | Status | Detail |
|---|---|---|---|---|---|---|
| 13 | copilot | `src/speckit_orca/yolo.py` | 907 | Actionable | DUPLICATE/ADDRESSED | Already fixed by CodeRabbit round 2 in `1aaf6de` — `cancel_run` raises ValueError |
| 14 | copilot | `src/speckit_orca/yolo.py` | 994 | Nit | ADDRESSED | `--evidence` changed from `nargs="*"` to `action="append"` for consistency with adoption.py/context_handoffs.py |
| 15 | copilot | `src/speckit_orca/yolo.py` | 468 | Nit | ADDRESSED | Mojibake (`���`) replaced with ASCII `-` in section comment |
| 16 | copilot | `commands/review-code.md` | 143 | Actionable | ADDRESSED | `ACTIVE_AGENT` now properly defined via jq+fallback+export, and the Python single-quote expansion works correctly (shell expands `$ACTIVE_AGENT` before Python sees it) |
| 17 | copilot | `specs/009-orca-yolo/tasks.md` | 88 | Actionable | ADDRESSED | T027/T028 updated to reflect actual shipped scope: replay + snapshot reconciliation only. Drift detection and stale thresholds DEFERRED to stale-detection PR. |

### Round 4 — Copilot deeper pass

| # | Reviewer | File | Line | Severity | Status | Detail |
|---|---|---|---|---|---|---|
| 18 | copilot | `src/speckit_orca/yolo.py` | 528-593 | **Actionable** | ADDRESSED | `next_decision` was off-by-one — advanced to _NEXT_STAGE[current] instead of executing current_stage. Fixed: when outcome=running, returns `step` with `next_stage=current_stage`. Review gate map inverted to stage-prerequisite map (at plan → need review_spec_status complete; at pr-ready → need review_code_status complete). 11 tests updated to match correct semantics, 1 new test added for auto-terminate. |
| 19 | copilot | `src/speckit_orca/yolo.py` | 491-527 | **Actionable** | ADDRESSED | `outcome == "canceled"` now handled as terminal. Previously a canceled run could be "resumed" by resume_run. New test `test_running_with_canceled_outcome_yields_terminal` verifies. |
| 20 | copilot | `src/speckit_orca/yolo.py` | 806-821 | **Actionable** | ADDRESSED | `next_run(success)` now auto-emits TERMINAL when the next stage is a terminal stage (pr-ready, review-pr). Previously snapshot would say outcome=running while next_decision said terminal. New test `test_next_success_into_terminal_stage_auto_completes` verifies. |
| 21 | copilot | `src/speckit_orca/yolo.py` | 266-287 | Actionable | **ADDRESSED** (round 5) | Re-verified on user pushback: this is actively breaking `commands/review-code.md:109-110` (invokes `context_handoffs resolve --target-stage review-code` which raises ValueError today). Fixed in round 5: extended `CANONICAL_STAGE_IDS`, `TRANSITION_ORDER`, `TRANSITION_REQUIRED_INPUTS`, and `_embedded_search_paths` with 012/009 vocabulary. Legacy 006 names kept for backward compat. Added cross-module invariant test. My initial "defer" verdict was wrong — the break is real in the current product, not just a future-PR concern. |

## Checks

| Check | Result |
|---|---|
| Analyze (python) | pass |
| CodeQL | pass |
| CodeRabbit | pass |
| validate | pass |

## Process Retro

**What worked:**
- Cross-harness review via `codex exec -m gpt-5.4` caught 4 BLOCKERs that two Claude-on-Claude passes missed (run ledger without driver loop, missing gate enforcement, wrong mode vocabulary, no invalid-transition rejection)
- CodeRabbit's line-level review was complementary — caught style/encoding/docstring issues the Codex pass ignored
- Governance fix (mandatory cross-harness in `review-code.md` Step 8) shipped in the same PR, so next implementation PR will have this enforced automatically

**What needs improvement:**
- `review-code` skill did not automatically invoke cross-harness review until operator intervention. Fixed in this PR.
- CodeRabbit local review via `--plain` without `--base-commit` failed on 427-file branch churn. Documented the correct invocation: `--type committed --base <merge-base>`.
- Initial tasks.md claimed T027/T037/T038 were complete but tests didn't exercise drift detection or the `next`/`recover` commands. Reopened and resolved in the post-Codex fix commit.

**Lessons learned:**
- Claude-on-Claude cross-pass is structurally weaker than cross-harness. 012's contract mandate is validated.
- Line-level (CodeRabbit) and architectural (Codex) reviews are complementary, not overlapping. Both belong in the gate chain.
- Prompt-only review enforcement is insufficient; the prompt must contain executable tool calls that fail loudly if the wrong thing happens.

## Post-Merge Verification

Pending merge. Will verify on post-merge:

- Diff merged main against HEAD of branch (`a8f3ab2`)
- Detect any silent reversions
- Record REVERTED/OK counts
- Confirm `.githooks/pre-push` still fires CodeRabbit on subsequent pushes

---

**Artifact paths:**
- `specs/009-orca-yolo/review-pr.md` (this file)
