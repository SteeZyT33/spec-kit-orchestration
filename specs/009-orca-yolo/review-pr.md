# PR Review — 009-orca-yolo

**PR**: [#49](https://github.com/SteeZyT33/spec-kit-orca/pull/49)
**Title**: feat(009): yolo runtime — event-sourced single-lane execution driver
**Status**: open, mergeable
**Reviewer**: coderabbitai[bot] (automated)
**Local pre-PR review**: CodeRabbit (via `.githooks/pre-push` chain) — "No findings ✔"
**Remote post-push review**: CodeRabbit — 4 actionable + 4 nitpicks + 1 warning

## PR: #49 — review-in-progress

- Comments: 9 | Addressed: 7 | Rejected: 1 | Issued: 0 | Clarify: 0 | Informational: 1

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
