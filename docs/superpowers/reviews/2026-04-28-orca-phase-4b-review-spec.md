# Review-Spec: Orca Phase 4b (Perf-Lab Integration Spec Contribution)

**Spec under review:** `docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md` (commit `bb78733`)
**Date:** 2026-04-28
**Reviewers:** Code Reviewer subagent (claude, 16 findings) + codex via legacy crossreview.sh (6 blocking + 5 non-blocking)
**Verdict:** **NEEDS-REVISION** (substantial)

---

## Round 1 - Cross-Pass

### Convergent blockers (both reviewers found these)

**B1. Event payload schemas conflict with existing perf-lab spec.md lines 436-438.**
The existing perf-lab Future Integration Notes already define payloads for the same three event types: `synthesis_validated -> {uncited_spans, broken_refs, citation_coverage}`, `contradiction_detected -> {contradictions[]}`, `quality_gate -> {gate_result_ref, blockers, target_stage}`. Phase 4b proposes incompatible shapes (`uncited_count`, `coverage`, `severity_breakdown`, etc.) and silently reassigns `quality_gate` semantics from completion-gate to cross-agent-review. The "one-paragraph addition" framing hides the conflict; the existing 25-line block must be rewritten or aligned, not appended to.

**B2. Subagent dispatch from a bash `entry.sh` is architecturally impossible.**
Phase 4a was explicit: subagent dispatch is the host LLM's responsibility, NOT something `orca-cli` or any non-LLM process can do. Phase 4b's perf-contradict and perf-review skills are bash scripts running under flock inside a devcontainer; they cannot call Claude Code's Agent tool. The skill convention (`/opt/perf-lab/skills/<name>/entry.sh`, one-shot, exit 0/1) cannot host subagent dispatch. Phase 4b silently breaks Phase 4a's framing.

**B3. `lease_overlap_check` wired into the wrong layer.**
perf-lab's `perf-lease` worker skill only exposes `check`/`info` operations. Lease *grants* are scheduler/host-side (`scripts/runtime-v6/lease.sh` per perf-lab T017-T018). Phase 4b directs operators to integrate `worktree-overlap-check` into a non-existent in-container grant flow.

**B4. `contradiction-detector --claude-findings-file` is unverified and load-bearing.**
Phase 4b admits the flag may not exist; if it doesn't, perf-contradict cannot be implemented at all, voiding T0Z04. The "verify and file orca PR if needed" framing makes this a Phase 4b merge blocker, not a follow-up.

**B5. Existing perf-lab spec.md contradicts Phase 4b's shim location.**
spec.md lines 442-444 explicitly say "the integration shim lives in the orca repo under integrations/perf_lab/." Phase 4b says the opposite without acknowledging the contradiction. The deliverable's "one-paragraph addition" doesn't fix the existing text.

### Codex-only blockers

**B6. orca-cli compatibility contract underspecified.**
Version-pin alone doesn't give implementers a contract for Phase 5/6 envelope changes. Need: minimum required capabilities/flags, expected envelope version, startup feature probe, fixture test matrix.

**B7. No timeout policy.**
v1 north-star line 449 mandates "Failed orca calls MUST NOT block perf-lab rounds indefinitely... default fallback is to emit feedback_needed rather than hang." Phase 4b is silent on timeouts and feedback_needed. A hanging subagent in synthesis_validators would hold synthesis.lock indefinitely.

### Claude-only highs

**H1. Model-tier policy from spec.md line 450 unaddressed.**
"Cheap tier worker invoking cross-agent-review MUST NOT escalate to a strong reviewer without explicit policy allowance." Phase 4b's perf-review has no model-tier inheritance.

**H2. feedback_needed fallback + synthesis-lock deadlock.**
Per spec.md line 449. Phase 4b doesn't release synthesis.lock on validator failure or emit feedback_needed; LLM-backed validators run while synthesis.lock is held, risking minutes-long lock-holds.

**H3. Event-type-before-emission ordering not enforced.**
perf-event rejects unknown types with exit 3. T0Z02 (FR-008 amendment) must be a hard prerequisite for skill-emission tasks T0Z03/04/05; Phase 4b doesn't declare this dependency.

**H4. Path validation gaps.**
`--evidence-path`, `--reference-set`, `--target` lack symlink rejection and resolved-path checks. `--evidence-path` allows directories (potential traversal). Phase 4a established defense-in-depth; Phase 4b regresses.

**H5. Two unverified upstream orca-cli capabilities are load-bearing.**
contradiction-detector --claude-findings-file (B4 above), orca-cli --version, and build-review-prompt accepting `--kind contradiction`. All three should be verified before opening the perf-lab PR.

### Convergent suggestions / mediums

- **opt-in default-off has no discovery path.** Without recommended profiles or template defaults, `orca_policy` will stay unset; perf-cite is largely aspirational.
- **Devcontainer install line uses `spec-kit-orca` package name** which may be wrong post-rename; not verified to publish to PyPI.
- **Test plan conflates spec-PR review with downstream implementation tests.** Bats smoke tests and runtime integration tests can't run against a code-less spec PR.
- **Capability/version metadata in payload conflicts with perf-event's `payload_version` convention** (data-model.md line 264-265). Naming collision.
- **`/shared/orca/<claim-id>/` path conventions undefined.** Who creates? Permissions? Cleanup? Race handling? Phase 4a uses timestamp suffixes; Phase 4b doesn't.
- **perf-cite's "compute coverage" duplicates orca-cli citation-validator's own output.** Should read from the envelope, not recompute.
- **perf-contradict on Codex hosts always fails.** Phase 4b acknowledges in failure-mode table but doesn't tell operators what to do (claim-config-level, fallback, or restrict to claude-code hosts).
- **`review_required_kind` underspecified.** Needs target_sha256, criteria_hash, reviewed_at, claim_id, kind to bind the event to content; otherwise stale events can satisfy gates.

---

## Recommended Path Forward

The spec is directionally right (perf-lab owns translation, orca stays opaque, opt-in defaults match perf-lab v1 compatibility), but it has too many architecturally-unsound details to ship as a perf-lab spec PR. Specifically:

1. **Rework subagent dispatch.** Restructure perf-contradict and perf-review so the LLM-backed step is host-side BEFORE skill invocation; the skill becomes pure orca-cli wrapping with `--claude-findings-file` passthrough. Mirror Phase 4a's slash-command pattern exactly.

2. **Move `lease_overlap_check` to host-side scheduler/lease.sh.** Worker `perf-lease` is read-only.

3. **Reconcile event payloads with spec.md 436-438.** Either align names or include a unified-diff replacement of the existing block.

4. **Verify or file orca PRs for the three load-bearing flags** (contradiction-detector --claude-findings-file, orca-cli --version, build-review-prompt --kind contradiction). Treat as merge prerequisites.

5. **Add timeout/feedback_needed/lease-release policy** per spec.md line 449.

6. **Add model-tier inheritance** per spec.md line 450.

7. **Split test plan** into "spec-PR review checks" (markdown lint, schema validation, no broken cross-refs) and "downstream T0Z implementation tests."

8. **Replace `quality_gate` reuse** with a new event type (e.g., `cross_review_summary`).

9. **Verify devcontainer install line** against actual orca PyPI publication state.

10. **Add path-validation rigor** to all path flags (symlinks rejected, resolved-path checks, directory-symlink rejection for `--evidence-path`).

This is a substantial v2 of the spec, not a polish pass.

---

## Verdict

**NEEDS-REVISION.** Recommend NOT proceeding to subagent-driven implementation until the spec is revised. Two paths:

- **A. Revise the spec inline now** addressing the 7 blockers + key highs. Then re-run /orca:review-spec. Estimated 1-2 sessions.
- **B. Defer Phase 4b.** Mark Phase 4 as fully closed with 4a as the substantive deliverable. Re-engage Phase 4b later, after perf-lab v6 ships skill foundation + lease.sh, with concrete answers to the model-tier / timeout / lease-release policy questions.

Phase 4a is shipped and unblocks the in-session reviewer use case. Phase 4b's value-add is integrating orca into perf-lab's runtime, but perf-lab v6 is mid-build (T000a-j unfinished) so the integration would land into a moving target. Option B may be the right call.

---

## Round 2 - Cross-Pass (v2 spec)

**Spec under review:** v2 of the Phase 4b spec (commit `513e418`)
**Reviewer:** Code Reviewer subagent (claude side only this round)
**Date:** 2026-04-29
**Verdict:** **NEEDS-REVISION (minor)**

### Per-blocker disposition vs Round 1

All 7 convergent blockers (B1-B7) and all 5 high findings (H1-H5) from Round 1 are properly addressed. The architectural rework (subagent dispatch out of skills, lease check out of worker skill, payload reconciliation, diff-replacement of spec.md) is real, not cosmetic.

| Round 1 | v2 disposition |
|--------|---------------|
| B1 (event payload schema collision) | ADDRESSED — Event Types reconciliation section preserves existing field names; orca-runtime fields additive; `cross_review_summary` is new type; `quality_gate` reserved |
| B2 (subagent dispatch from bash impossible) | ADDRESSED — Three-Layer Architecture explicitly moves dispatch to host-side wrappers outside devcontainer; T0Z06 implements wrappers |
| B3 (lease_overlap_check wrong layer) | ADDRESSED — host-side `scripts/runtime-v6/lease.sh`, not perf-lease worker; T0Z09 enforces |
| B4 (--claude-findings-file unverified) | ADDRESSED via Phase 4b-pre-1 prerequisite gate |
| B5 (existing spec.md contradicts) | ADDRESSED — unified diff replaces "Shim location" paragraph |
| B6 (orca-cli compat contract underspecified) | ADDRESSED — capability matrix, startup probe, fixture matrix |
| B7 (no timeout policy) | ADDRESSED — lock-window discipline + per-capability timeouts + feedback_needed + dispatch sentinel + stall detection |
| H1 (model-tier policy unaddressed) | ADDRESSED — `model_tier_floor` field with explicit semantics |
| H2 (synthesis-lock deadlock) | ADDRESSED — validators run before lock acquisition |
| H3 (event-type ordering) | ADDRESSED — T0Z02 marked prerequisite for T0Z03/04/05 |
| H4 (path validation gaps) | ADDRESSED via path-safety contract reference |
| H5 (three unverified flags load-bearing) | PARTIALLY ADDRESSED — see N1 below; `build-review-prompt --kind contradiction` not in pre tasks |

### New findings introduced in v2

**N1 (BLOCKER — narrow):** `build-review-prompt --kind contradiction` is still load-bearing (line 78, 377 in v2) but has no Phase 4b-pre task. Round 1 H5 listed three flags; v2 covers two. Either add Phase 4b-pre-5 to verify/extend, or weaken the dispatch wrapper to construct the prompt without `--kind`.

**N2 (BLOCKER — small):** `cross_review_summary` event payload (v2 line 152, 171) lacks `criteria_hash` — yet `review_required.criteria_hash` (v2 line 263) requires it to satisfy a gate. Without the field in the event, the binding mechanism fails. Add `criteria_hash` to the event payload.

**N3 (MEDIUM):** Inconsistency between v2's "Path Validation" (line 320) and the path-safety contract Class C: v2 says findings-file resolves inside `/shared/orca/<claim_id>/`, contract specifies `/shared/orca/<claim_id>/<round_id>/<kind>-findings-<timestamp>.json` and adds CLAIM_ID env-match rule. Tighten v2 or defer to contract explicitly.

**N4 (MEDIUM):** `<round_id>/` directory creation owner unspecified. v2 says `perf-claim` creates `<claim_id>/` (line 340); round subdirs are unaddressed. Pick an owner.

**N5 (MEDIUM):** Phase 4b-pre-4 builds `orca-dispatch-helper.sh` in the orca repo (line 464) but the dispatch wrappers themselves live in the perf-lab repo (line 78). Cross-repo bash sourcing is fragile. Either move the helper into perf-lab or define how it's installed into the devcontainer.

**N6 (LOW):** "Phase 3.2 backlog item 2" cited at lines 99 and 269 with no link. Add a path.

**N7 (LOW):** T0Z10/T0Z11 task-numbering reference: line 354 says "T0Z10 verifies" the Dockerfile install line, but T0Z10 is the `review_required` task; the install line task is T0Z11. Fix the cross-reference.

### Cross-doc consistency

- **Path-safety contract:** v2 cites correctly. Class A/B/C/D mappings match exactly. Class C depth/CLAIM_ID gap noted in N3.
- **perf-lab spec.md unified diff:** "before" text matches actual current text in perf-lab `spec.md` lines 423-444; diff applies cleanly. Minor: diff doesn't acknowledge the `### Constraints` section (perf-lab spec.md lines 446-451) survives unchanged — add a hunk marker or explicit note to prevent implementer confusion.
- **Internal:** task list T0Z00-T0Z13 prerequisite gating is consistent. Event payloads consistent across Skill Contracts and Event Types table except the `criteria_hash` gap (N2).
- **Symphony note:** stall-timeout cite (Symphony §10.6, 300s default) is consistent.

### Verdict

**NEEDS-REVISION (minor).** Architectural blockers fully resolved; remaining gaps are bounded and fixable in <1 session of editing.

Two narrow blockers (N1 + N2) plus four mediums/lows. None require restructuring.

### Recommended path

**A. Inline-fix the 7 N-findings now** (estimate: 30-60 min of editing). Specifically:
1. Add Phase 4b-pre-5 (verify `build-review-prompt --kind contradiction`) OR remove the flag from the dispatch wrapper design.
2. Add `criteria_hash` to `cross_review_summary` event payload in both Skill Contract (line 152) and Event Types table (line 171).
3. Tighten "Path Validation" (line 314-324) to either match contract Class C depth/CLAIM_ID rule or defer with "see contract Class C for full rules."
4. Specify `<round_id>/` directory creation owner (line 340 area).
5. Either move `orca-dispatch-helper.sh` to perf-lab repo, or add devcontainer install instructions for the orca-side helper.
6. Replace "Phase 3.2 backlog item 2" with a path link.
7. Fix T0Z10/T0Z11 cross-reference at line 354.

After fixes, spec is ready for writing-plans. No third review round required for this scale of edit.

---

## Round 3 - Cross-Pass (v2.1 spec, post round-2 fixes)

**Spec under review:** v2.1 (commit `806877e`)
**Reviewer:** Code Reviewer subagent
**Date:** 2026-04-29
**Verdict:** **NEEDS-REVISION (minor)** — addressed inline same session as v2.2

### Round 2 N-findings disposition

| # | Disposition |
|---|-------------|
| N1 | ADDRESSED — Phase 4b-pre-5 added; T0Z00 wait gate updated |
| N2 | ADDRESSED — `criteria_hash` in skill contract + Event Types table |
| N3 | ADDRESSED — Path Validation defers to contract Class B/C |
| N4 | ADDRESSED — `<round_id>/` owner is perf-claim round-increment |
| N5 | ADDRESSED — pre-4 reframed as algorithm-spec doc; no cross-repo helper |
| N6 | PARTIALLY ADDRESSED — first occurrence fixed; second (line 269) missed → **N12** |
| N7 | ADDRESSED — T0Z11 cross-reference fixed |

### New findings introduced by Round 2 edits

- **N8 (LOW):** Line 27 stale "three load-bearing flags" → should be "five orca-repo prerequisites".
- **N9 (MEDIUM):** Line 354 — "T0Z11 verifies before this lands" creates a self-reference (T0Z11 IS the install task). Should reference Phase 4b-pre-3 (decides) and Phase 4b-pre-3 only.
- **N10 (MEDIUM):** Path-shape namespace collision. `/shared/orca/<claim_id>/<round_id>/review-<kind>-findings-<timestamp>.json` overloads `<kind>` between skill-name kind (cite/contradict/review) and perf-review's `--kind` argument (spec/diff/pr/artifact). Path-safety contract Class C says `<kind>-findings-<timestamp>.json` (single segment).
- **N11 (MEDIUM):** `cross_review_summary` payload (lines 152, 171) does not carry `claim_id`, but `review_required.claim_id` is a binding field. Either `claim_id` is on the perf-event envelope (likely true; spec should say so) or it must be added to the payload.
- **N12 (LOW):** Line 269 still says "Phase 3.2 item 2 conventions" without path link — second occurrence of N6 was missed.
- **N13 (LOW):** T0Z06 task description (line 448) does not mention `orca-dispatch-lib.sh` introduced at line 314.

### v2.2 fixes (this session, commit forthcoming)

- N8: Line 27 reworded to "five orca-repo prerequisites (Phase 4b-pre-1 through pre-5)".
- N9: Dockerfile comment + paragraph below now reference Phase 4b-pre-3 (the decision) and T0Z11 (the implementation) separately, no self-reference.
- N10: Path conventions now use skill-shortname (`cite-findings-...`, `contradict-findings-...`, `review-findings-...`) consistently; perf-review's `--kind` value lives in the event payload, not the filename. Explanatory paragraph added.
- N11: Added explicit clarification that `claim_id` lives on the `perf-event` envelope (alongside event_id/timestamp/harness/image_digest) and gates verify it from there, not from the per-event payload. Avoids state duplication.
- N12: Second occurrence (line 269) now carries the same path link as line 99.
- N13: T0Z06 description extended to include `orca-dispatch-lib.sh` and cite the dispatch-algorithm contract by path.

### Verdict (v2.2)

After these fixes, all flagged issues from Rounds 1, 2, and 3 are addressed. Spec is ready to drive subagent-driven implementation of Plan 1 (orca prereqs). No further review round needed before execution.
