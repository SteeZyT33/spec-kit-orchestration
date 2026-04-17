---
description: "Review-code artifact for 009 runtime + PR C/D integrations per 012 review model"
---

# Review: Code — 009-orca-yolo Runtime (PR B + C + D)

Durable record of self+cross reviews across the 009 runtime delivery.
Produced per `specs/012-review-model/contracts/review-code-artifact.md`.

**Commits covered**: `a4217e6` (core runtime) through `7f2b7be` (PR #54 round 2)
**Reviewers**: Claude Opus 4.7 (self), Codex GPT-5.4 (cross-harness), CodeRabbit Pro (line-level)

---

## Phase B (Core Runtime) Self Pass (agent: claude, date: 2026-04-16)

### Spec compliance

- FR-001 (resumable runner), FR-004 (durable state), FR-005 (stop on gates), FR-006 (start artifacts), FR-007 (stage model), FR-011 (provider-agnostic), FR-012 (PR opt-in) all satisfied.
- FR-003 (ask levels): partially — decision_required/pause serve as the mechanism; formal ask-policy config deferred.
- FR-013-FR-019 (supervised mode): deferred to PR D.

### Implementation quality

- Event, RunState, Decision frozen/explicit dataclasses.
- reduce() and next_decision() are pure functions.
- Inline ULID (40 LOC, Crockford Base32, monotonic).
- UTF-8 explicit on all I/O paths.

### Test coverage

- 65 initial tests, later grew to 87 covering reducer determinism, idempotence, invalid transitions, decision gates, retry bound, lifecycle operations, CLI.

### Regression risk

- Zero — 244→249 passed after landing.

---

## Phase B Cross Pass (agent: codex GPT-5.4, date: 2026-04-16)

### Spec compliance

- **BLOCKER**: `yolo next` command was missing — runtime was "a run ledger plus stage suggester, not a full-cycle runner" (caught what two Claude passes missed)
- **BLOCKER**: `next_decision` had no review-gate enforcement — could jump review-spec → plan with no artifact
- **BLOCKER**: Mode vocabulary wrong (`matriarch` vs contract's `matriarch-supervised`), mode inferred from lane_id instead of explicit

### Implementation quality

- **BLOCKER**: Reducer accepted impossible histories (malformed log could jump brainstorm → pr-create)
- **WARNING**: Retry bound not enforced at decision level

### Test coverage

- **WARNING**: Tests overclaimed — "stale snapshot" test only deleted status.json, didn't exercise thresholds or head_commit_sha drift. Tasks.md T027 claimed otherwise.

### Regression risk

- N/A — findings identified pre-merge.

---

## Phase B Cross Pass Resolution (commit `f208782`)

All 4 BLOCKERs + 2 WARNINGs addressed:
- Added `next_run()` driver loop with `--result success/failure/blocked`
- Added `recover_run()` for explicit override
- Added `_STAGE_PREREQ` map; next_decision blocks on review gates
- Mode now explicit parameter; vocabulary corrected
- Reducer rejects illegal forward jumps (only same/forward/backward allowed)
- Retry bound enforced (`DEFAULT_RETRY_BOUND = 2`)
- Honest tasks.md update reopened T027/T037/T038

---

## Phase B Copilot Pass (agent: copilot-pull-request-reviewer, date: 2026-04-16)

### Implementation quality

- `next_decision` off-by-one: advanced to `_NEXT_STAGE[current]` instead of executing `current_stage` — caught semantic bug my tests codified as "correct"
- `outcome == "canceled"` not handled as terminal — canceled runs could be "resumed"
- `next_run(success)` didn't persist outcome=completed when entering terminal stage — snapshot said "running" while decision said "terminal"
- `context_handoffs.CANONICAL_STAGE_IDS` missing 012/009 vocabulary — commands/review-code.md Step 3 was actively broken

### Resolution (commits `e2735f5`, `2e92024`)

All 4 issues fixed. Semantic rewrite of next_decision (returns current_stage as executable, gate map inverted to stage prerequisites). Auto-terminate on entering terminal stage. context_handoffs vocabulary reconciled.

---

## Phase C (flow-state integration) Self Pass (agent: claude, date: 2026-04-16)

### Spec compliance

- `compute_flow_state` now surfaces `YoloRunSummary` list per runtime-plan §13 PR C scope.
- 11 tests written first (TDD), all green.

### Implementation quality

- `list_yolo_runs_for_feature` replays event logs via lazy yolo import (avoids circular dep).
- `YoloRunSummary.is_terminal` property drives active-vs-terminal segmentation.

---

## Phase D (matriarch supervised mode) Self Pass (agent: claude, date: 2026-04-16)

### Spec compliance

- `append_event` dual-writes to matriarch mailbox when `lane_id` is set.
- `resume_run` consults lane registry per FR-018.
- `recover_run` is the explicit operator override path.

### Implementation quality (self-assessed)

- Mirror failures swallowed (claimed "best-effort observability"); matched test expectations.
- Used `send_mailbox_event` with `direction="to_matriarch"` for all types.
- Sender was `yolo:<run_id>`.

---

## Phase C+D Cross Pass (agent: codex GPT-5.4, date: 2026-04-16)

### Spec compliance

- **BLOCKER 3**: Wrong channels/identity. Per 010 `lane-mailbox.md` and `event-envelope.md`:
  - sender MUST be `lane_agent:<lane_id>`, not `yolo:<run_id>`
  - RUN_STARTED is a startup ACK (reports queue), not a mailbox status
  - Status events go to reports queue via `append_report_event`, NOT mailbox
  - Only blockers/questions/approvals go through `send_mailbox_event`

### Implementation quality

- **BLOCKER 1**: Dual-write swallowed failures silently. Runtime-plan §11 requires marking `matriarch_sync_failed` so lost visibility is detectable.
- **BLOCKER 2**: `recover_run` was a silent callable override. Not "explicit operator confirmation" — any script could call it. Also treated missing lane as "nothing to reconcile" (fail-open).
- **WARNING 1**: `DECISION_REQUIRED` always collapsed to mailbox `question`; review gates should emit `approval_needed` per 010.
- **NOTE**: "Active yolo runs" label included terminal runs in text output.

---

## Phase C+D Cross Pass Resolution (commit `51c07ed`)

All 3 BLOCKERs + 2 WARNINGs addressed:
- Added `_YOLO_MIRROR_ROUTE` map; sender is `lane_agent:<lane_id>`; RUN_STARTED via `emit_startup_ack`, status via `append_report_event`, blockers/questions via `send_mailbox_event`.
- Added `RunState.matriarch_sync_failed` flag + `.matriarch_sync_failed` marker file; `_load_state()` stamps the flag on all reads.
- `recover_run` now requires `confirm_reassignment=True` + non-empty `reason` when lane changed. Missing lane fails closed (ValueError).
- DECISION_REQUIRED differentiated: review gates → `approval_needed`, else `question`.
- `FlowStateResult.to_text` splits active vs terminal sections.

Added 4 tests codifying the fixes.

---

## Phase C+D CodeRabbit Pass (agent: coderabbit, date: 2026-04-16)

### Implementation quality

- **Major**: `matriarch_sync_failed` stamped in memory by `_load_state` but NOT persisted to status.json. Direct readers of snapshot would see stale "healthy" state.
- **Minor**: Terminal yolo runs dropped `block_reason` and `[matriarch_sync_failed]` tag in text output.
- **Minor**: `recover --help` advertised stale-warning and head-commit drift overrides not actually implemented.
- **Major**: tasks.md Phase 7 appeared AFTER Phase 8/9; Dependency summary stopped at Phase 7; Out of Scope still listed PR C/D as deferred.

### Resolution (commit `7f2b7be`)

All 4 addressed:
- `_write_snapshot` persists `matriarch_sync_failed`; all write paths use `_load_state()`.
- Terminal runs include block_reason + sync-failure tag on par with active runs.
- Help text + docstring aligned with actual behavior; stale/drift deferred explicitly.
- tasks.md restructured: Phase 7 before 8/9, dependency summary includes all 9 phases, Out of Scope updated.

---

## Overall Verdict

- **status**: ready-for-pr
- **rationale**: All BLOCKERs from three independent review passes (Codex×2, Copilot, CodeRabbit) addressed with evidence and test coverage. 298 tests passing, zero regressions. Governance gaps exposed by reviews (mandatory cross-harness in review-code prompt, before_pr CodeRabbit hook, context_handoffs vocabulary reconciliation) also closed.
- **follow-ups**:
  - PR E: Worktree lifecycle + head_commit_sha drift detection
  - PR F: Full operator prompt body in `commands/yolo.md` (drafted, stashed as `stash@{0}`)
  - PR G: Tasks reconciliation pass
  - Stale-run threshold warnings in `resume_run` (3d/7d)

---

## Review Discipline Lessons

1. **Same-harness reviews miss architectural gaps.** Two Claude passes on PR B both missed the missing `yolo next` command, the review gate enforcement, and the mode vocabulary error. Codex GPT-5.4 caught all of them. 012's cross-harness mandate is validated in practice.
2. **Test codification of bugs is real.** My PR B tests asserted that next_decision returns the SUCCESSOR of current_stage — codifying the off-by-one bug as correct behavior. Copilot caught this only because it reasoned from the semantic intent, not the tests.
3. **Deferral justification matters.** My initial defer on the `context_handoffs` vocabulary divergence (framed as "007-touching refactor") was wrong — the finding was that a CURRENT command (`review-code.md`) was ACTIVELY BROKEN, not a future-PR concern. Defer only when the target of the fix isn't in today's product.
4. **Best-effort ≠ acceptable-to-drop.** Calling something "best-effort" was a rationalization for swallowing failures. Tracking sync failures via a marker file + `matriarch_sync_failed` field was the right model.

---

**Artifact path**: `specs/009-orca-yolo/review-code.md`
**Summary/index**: `specs/009-orca-yolo/review.md` (refreshed separately)
