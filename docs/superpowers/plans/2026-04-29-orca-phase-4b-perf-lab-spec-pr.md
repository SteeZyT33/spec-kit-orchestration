# Orca Phase 4b — Perf-Lab Spec PR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open a spec contribution PR against the perf-lab repo that adds `orca-integration.md`, replaces the existing "Future Integration Notes" subsection in `spec.md` with reconciled v2 text via unified diff, and adds a T0Z task block (T0Z00-T0Z13) to `tasks.md`. No running code. Pure spec authoring.

**Architecture:** Phase 4b lives in perf-lab repo, not orca repo. Per Phase 4a's "orca = JSON-in JSON-out library" framing, perf-lab-specific event translation belongs in perf-lab. The PR adds 3 thin agent-visible skill contracts (perf-cite, perf-contradict, perf-review) that wrap orca-cli, plus host-side dispatch wrappers running OUTSIDE the devcontainer. Subagent dispatch is host-LLM responsibility, never inside `entry.sh` (the v1 plan got this wrong; v2 fixes).

**Tech Stack:** Markdown only. No code in this PR. Perf-lab's existing spec/contract conventions (see `perf-lab/specs/010-self-organizing-research-runtime/contracts/skills.md`).

**Source spec:** `docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md` (v2.1 at commit `806877e`).

**Target repo:** `/home/taylor/perf-lab` (separate repo from orca; clone is at `~/perf-lab`).

**Prerequisites:** All 5 orca repo prereqs (Phase 4b-pre-1 through pre-5) must merge before this PR can claim "ready." See `docs/superpowers/plans/2026-04-29-orca-phase-4b-pre-prereqs.md`.

---

## File Structure

### New files (in perf-lab repo)

- `perf-lab/specs/010-self-organizing-research-runtime/orca-integration.md` (new sibling spec, ~600 lines)

### Files to modify (in perf-lab repo)

- `perf-lab/specs/010-self-organizing-research-runtime/spec.md` (replace "Future Integration Notes" subsection at lines 420-444 via unified diff; preserve `### Constraints` at lines 446-451 unchanged)
- `perf-lab/specs/010-self-organizing-research-runtime/tasks.md` (append T0Z block: T0Z00 through T0Z13)

### Files NOT touched

- `perf-lab/specs/010-self-organizing-research-runtime/data-model.md` — schema additions for the 3 new event types are tracked as part of T0Z02 (in-implementation), not part of this spec PR
- `perf-lab/specs/010-self-organizing-research-runtime/contracts/skills.md` — skill conventions cited by `orca-integration.md`, not modified

---

## Task 1: Pre-flight verification + branch setup

Verify orca prereqs merged and current perf-lab spec.md hasn't drifted from the v2 spec's expected baseline.

**Files:**
- None modified

- [ ] **Step 1.1: Confirm orca prereqs are merged**

```bash
cd /home/taylor/spec-kit-orca   # or wherever orca lives
git log --oneline --grep "Phase 4b-pre" main | head -10
```

Expected: 5 commits, one per pre-task. If fewer than 5, STOP — do not open the perf-lab PR until all 5 prereqs are merged.

- [ ] **Step 1.2: Verify the three load-bearing flags actually work in the merged orca**

```bash
uv run --project /home/taylor/spec-kit-orca orca-cli --version
uv run --project /home/taylor/spec-kit-orca orca-cli contradiction-detector --help | grep -- --claude-findings-file
uv run --project /home/taylor/spec-kit-orca orca-cli build-review-prompt --kind contradiction --criteria test
```

Expected:
- First command: `spec-kit-orca <semver>` exit 0
- Second command: `--claude-findings-file` listed in help
- Third command: prompt text emitted, exit 0

If any fail, the prereq did not actually land — STOP and fix.

- [ ] **Step 1.3: Read perf-lab spec.md current state at lines 420-451**

```bash
sed -n '420,451p' ~/perf-lab/specs/010-self-organizing-research-runtime/spec.md
```

Compare against the "before" half of the unified diff in the orca v2 spec (`docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md` § "Unified-diff replacement"). If the actual perf-lab text has drifted from the diff's "before" baseline, the diff won't apply cleanly — adjust the diff in the orca v2 spec OR adjust the implementation here, but do NOT silently overwrite mismatched text.

- [ ] **Step 1.4: Create the perf-lab branch**

```bash
cd ~/perf-lab
git fetch origin
git checkout -b orca-integration-spec origin/main
git status
```

Expected: clean working tree on new branch off origin/main.

- [ ] **Step 1.5: Confirm sibling spec files exist (anchor for orca-integration.md placement)**

```bash
ls ~/perf-lab/specs/010-self-organizing-research-runtime/
```

Expected: at minimum `spec.md`, `tasks.md`, `data-model.md`, `runtime-mechanics.md`. `orca-integration.md` will live next to these.

- [ ] **Step 1.6: Commit pre-flight notes (optional)**

If anything in 1.3 surprised you (drift, missing prereqs, etc.), capture in a `pre-flight-notes.md` at the orca repo's `notes/` dir before proceeding. Otherwise skip.

---

## Task 2: Author `orca-integration.md`

This is the bulk of the deliverable. Mirror the structure of the v2 orca spec but written for the perf-lab audience (perf-lab maintainers, not orca maintainers).

**Files:**
- Create: `~/perf-lab/specs/010-self-organizing-research-runtime/orca-integration.md`

- [ ] **Step 2.1: Create the file with header + table of contents**

```markdown
# Orca Integration

**Status:** Spec contribution; integration ships when perf-lab v6 reaches T000i (skill foundation) and orca repo merges Phase 4b-pre-1 through pre-5.
**Source:** Orca v2.1 design (`spec-kit-orca` commit `806877e`).
**Sibling specs:** `spec.md` § "Future Integration Notes", `data-model.md`, `runtime-mechanics.md`, `contracts/skills.md`.

## Contents

1. Why orca integration
2. Three-layer architecture
3. Skill contracts (perf-cite, perf-contradict, perf-review)
4. Host-side dispatch wrappers
5. Event types (extends FR-008)
6. Claim config additions (`orca_policy` block)
7. Lock and timeout policy
8. Path validation (refers to orca's path-safety contract)
9. /shared/orca/ path conventions
10. Devcontainer installation
11. orca-cli compatibility contract
12. Failure modes
13. Test plan
14. Out of scope
```

- [ ] **Step 2.2: Author § "Why orca integration"**

Write 200-400 words explaining:
- The motivation (cross-agent review, citation hygiene, contradiction detection are valuable for perf-lab's research synthesis loop).
- The constraint (perf-lab v1 must work without orca; orca is opt-in via `orca_policy`).
- The Phase 4a unblocker (no API key needed inside devcontainer; host LLM dispatches subagents and writes findings file).

Source: orca v2 spec §§ "Context" and "Three-Layer Architecture" intro.

- [ ] **Step 2.3: Author § "Three-layer architecture"**

Reproduce the diagram from orca v2 spec lines 39-67. Plain-text ASCII box diagram showing host-LLM-session → skill (in devcontainer, under flock) → orca-cli (opaque). Explicitly state: skill never holds a subagent in flight.

- [ ] **Step 2.4: Author § "Skill contracts"**

For each of `perf-cite`, `perf-contradict`, `perf-review`: include CLI signature, required/optional flags, behavior steps, concurrency (flock paths), path classes the flags belong to (Class B / C from orca's path-safety contract). Mirror orca v2 spec §§ "perf-cite", "perf-contradict", "perf-review" exactly. Use the actual orca-cli flag names: `--new-content`, `--prior-evidence` (skill normalizes from `--content-path`/`--evidence-path`).

- [ ] **Step 2.5: Author § "Host-side dispatch wrappers"**

Document `scripts/perf-lab/orca-dispatch-contradict.sh` and `scripts/perf-lab/orca-dispatch-review.sh`. Each:
- Lives in perf-lab repo, not orca repo (decision per Phase 4b-pre-4).
- Implements the dispatch algorithm specified in `spec-kit-orca`'s `docs/superpowers/contracts/dispatch-algorithm.md`.
- Sources a perf-lab-internal helper `scripts/perf-lab/orca-dispatch-lib.sh` for stall-detection and timeout logic.
- Writes findings file to `/shared/orca/<claim_id>/<round_id>/<kind>-findings-<timestamp>.json`.
- Exits 0 on findings written, 1 on dispatch failure (sentinel findings file populated), 2 on config error.

Cross-reference: orca v2 spec lines 76-81 + `docs/superpowers/contracts/dispatch-algorithm.md` (orca repo).

- [ ] **Step 2.6: Author § "Event types (extends FR-008)"**

Reproduce orca v2 spec § "Event Types — Reconciliation with Existing spec.md" table verbatim. The four types: `synthesis_validated`, `contradiction_detected`, `cross_review_summary`, `quality_gate` (reserved). Include the explicit note that `quality_gate` is reserved for future completion-gate work and NOT emitted in this Phase. Include `criteria_hash` in the `cross_review_summary` payload.

- [ ] **Step 2.7: Author § "Claim config additions"**

Reproduce orca v2 spec § "Claim Config Additions" verbatim, including the `review_required` binding object (with `target_sha256`, `criteria_hash`, `claim_id`), `model_tier_floor` semantics, discoverability via mission template.

- [ ] **Step 2.8: Author § "Lock and timeout policy"**

Reproduce orca v2 spec § "Lock and Timeout Policy" verbatim. Sections: lock window for synthesis_validators, per-capability timeouts (with the table), stall detection on subagent dispatch.

- [ ] **Step 2.9: Author § "Path validation"**

Defer to orca's path-safety contract. State: "Path-shaped flags follow the path-safety contract at `<orca-repo>/docs/superpowers/contracts/path-safety.md`. In Phase 4b's context, `--content-path`/`--evidence-path`/`--target` are Class B; findings-file paths are Class C; `--reference-set` is Class A within feature dir; identifiers (CLAIM_ID, --feature-id) are Class D."

Then list the validation outcomes specific to perf-lab: skill exits 1 with `error.kind = "INPUT_INVALID"`, includes `rule_violated`, `field`, on any contract violation.

- [ ] **Step 2.10: Author § "/shared/orca/ path conventions"**

Reproduce orca v2 spec § "/shared/orca/ Path Conventions" verbatim. Include the directory structure, owner-of-`<claim_id>/` (perf-claim claim-create), owner-of-`<round_id>/` (perf-claim round-increment, atomic, mode 0775), timestamp suffix format, cleanup hook (perf-claim close).

- [ ] **Step 2.11: Author § "Devcontainer installation"**

Reproduce orca v2 spec § "Devcontainer Installation" with both the PyPI option and the bind-mount option. Cite the PyPI publication decision artifact at `<orca-repo>/docs/superpowers/notes/2026-04-29-pypi-publication-decision.md`. T0Z11 verifies which path is real before this PR can claim "merged."

- [ ] **Step 2.12: Author § "orca-cli compatibility contract"**

Reproduce orca v2 spec § "Orca-CLI Compatibility Contract" including the capability matrix table, startup probe behavior (T0Z12), fixture test matrix.

- [ ] **Step 2.13: Author § "Failure modes"**

Reproduce orca v2 spec § "Failure Modes" table verbatim. Include the Codex-host limitation (no Agent tool → cite-only or empty `synthesis_validators`).

- [ ] **Step 2.14: Author § "Test plan"**

Reproduce orca v2 spec § "Test Plan — Split". The spec-PR review checks (markdown lint, cross-ref check, schema-doc validation, diff-conflict check, front-matter validation) run on this PR; the downstream implementation tests are T0Z03+ work and out of scope here.

- [ ] **Step 2.15: Author § "Out of scope"**

Reproduce orca v2 spec § "Out of Scope (Phase 4b)" verbatim, scoped to perf-lab framing.

- [ ] **Step 2.16: Run markdown lint locally**

```bash
cd ~/perf-lab
mdformat --check specs/010-self-organizing-research-runtime/orca-integration.md
```

Fix any formatting issues.

- [ ] **Step 2.17: Verify all internal cross-refs resolve**

For each `<file>#<anchor>` reference in `orca-integration.md`, confirm the file exists and the anchor matches a heading. Use:

```bash
grep -oE "\[[^\]]+\]\(([^)]+)\)" specs/010-self-organizing-research-runtime/orca-integration.md
```

Manually check each link. No broken links allowed.

- [ ] **Step 2.18: Commit**

```bash
git add specs/010-self-organizing-research-runtime/orca-integration.md
git commit -m "docs(spec-010): add orca-integration.md (Phase 4b)

Adds the orca integration sibling spec defining three thin skills
(perf-cite, perf-contradict, perf-review), host-side dispatch
wrappers, opt-in claim_policy block, four event-type extensions to
FR-008, and the orca-cli compatibility contract. No running code;
implementation tasks in T0Z block (added in next commit).

Source spec: spec-kit-orca commit 806877e."
```

---

## Task 3: Apply unified-diff replacement to spec.md "Future Integration Notes"

**Files:**
- Modify: `~/perf-lab/specs/010-self-organizing-research-runtime/spec.md` lines 420-444

The "Constraints" subsection at lines 446-451 is preserved unchanged; only "v1 orca catalog consumed by perf-lab", "New event types introduced when orca integration is enabled", and "Shim location and ownership" are replaced.

- [ ] **Step 3.1: Read the diff from the orca v2 spec**

```bash
sed -n '/^### Unified-diff replacement/,/^## /p' /home/taylor/spec-kit-orca/docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md
```

This prints the unified diff. The "after" lines are what should land in spec.md.

- [ ] **Step 3.2: Apply the replacement manually**

Don't use `patch` — the diff format in the orca spec is illustrative, not patchable. Open `~/perf-lab/specs/010-self-organizing-research-runtime/spec.md`, locate the three subsections, and replace each with the "after" text from the orca v2 spec. Preserve `### Constraints` at the end unchanged.

- [ ] **Step 3.3: Verify the result**

```bash
sed -n '420,451p' ~/perf-lab/specs/010-self-organizing-research-runtime/spec.md
```

Expected:
- "v1 orca catalog consumed by perf-lab" mentions three skills, four capabilities consumed, host-side `lease.sh` (NOT perf-lease worker)
- "New event types" mentions the four types (synthesis_validated, contradiction_detected, cross_review_summary, quality_gate-reserved)
- "Shim location and ownership" says "lives in the perf-lab repo"
- `### Constraints` (lines 446-451) is unchanged

- [ ] **Step 3.4: Run mdformat on spec.md**

```bash
mdformat --check specs/010-self-organizing-research-runtime/spec.md
```

Fix any formatting drift introduced.

- [ ] **Step 3.5: Commit**

```bash
git add specs/010-self-organizing-research-runtime/spec.md
git commit -m "docs(spec-010): reconcile Future Integration Notes with orca v2

Replaces three subsections (v1 catalog, new event types, shim location)
to align with orca-integration.md. Notable changes:

- shim now lives in perf-lab repo, not orca repo (per Phase 4a 'orca
  is opaque' framing)
- worktree-overlap-check invoked from host-side scripts/runtime-v6/
  lease.sh, not from perf-lease worker skill (which is read-only)
- new event type cross_review_summary added; quality_gate reserved
  for future completion-gate work, not emitted in Phase 4b

The ### Constraints subsection (timeouts, model-tier inheritance,
host-only invocation) is preserved unchanged; Phase 4b policies are
additive on top of those constraints."
```

---

## Task 4: Append T0Z block to tasks.md

**Files:**
- Modify: `~/perf-lab/specs/010-self-organizing-research-runtime/tasks.md`

T0Z00 through T0Z13. T0Z00 is a wait gate on the orca prereqs. T0Z02 is a hard prerequisite for T0Z03/04/05. T0Z03/04/05 are the three skill implementations.

- [ ] **Step 4.1: Read the current tail of tasks.md to find the right insertion point**

```bash
tail -20 ~/perf-lab/specs/010-self-organizing-research-runtime/tasks.md
```

Identify the end of the existing task list; T0Z block appends after.

- [ ] **Step 4.2: Reproduce the T0Z block from the orca v2 spec**

The block is at orca v2 spec § "Implementation Tasks (added to perf-lab tasks.md)". Append it verbatim with perf-lab's standard task formatting (description, files, acceptance criteria per task — match the convention used in the existing tasks.md).

```markdown
## T0Z: Orca Integration (blocked on T000i)

All T0Z tasks are blocked on T000i (perf-event skill foundation). T0Z00 is also blocked on the orca repo merging Phase 4b-pre-1 through Phase 4b-pre-5.

### T0Z00: Wait gate — orca prereqs merged

**Description:** Confirm spec-kit-orca commits Phase 4b-pre-1 through pre-5 are merged before starting T0Z03+. Verify each via:
- `orca-cli --version` exits 0 (pre-2)
- `orca-cli contradiction-detector --help | grep -- --claude-findings-file` returns a hit (pre-1)
- `orca-cli build-review-prompt --kind contradiction --criteria test` exits 0 (pre-5)
- PyPI decision doc exists at `spec-kit-orca/docs/superpowers/notes/2026-04-29-pypi-publication-decision.md` (pre-3)
- Dispatch algorithm doc exists at `spec-kit-orca/docs/superpowers/contracts/dispatch-algorithm.md` (pre-4)

**Files:** none modified; verification only.
**Acceptance:** all five checks pass.

### T0Z01: Author orca-integration.md

(Already done as part of this PR; this task tracks the artifact.)
**Files:** `specs/010-self-organizing-research-runtime/orca-integration.md`
**Acceptance:** sibling spec exists, mdformat passes, all cross-refs resolve.

### T0Z02: Add new event types to FR-008 canonical list

**Description:** Extend `spec.md` FR-008 list with `synthesis_validated`, `contradiction_detected`, `cross_review_summary`. Reserve `quality_gate` (no emission yet). Add corresponding payload schemas to `data-model.md`. **Hard prerequisite for T0Z03/04/05** — `perf-event` rejects unknown types with exit 3.
**Files:** `spec.md`, `data-model.md`
**Acceptance:** four event types in FR-008 list with payload schemas; `tests/events/test_event_schema.py` extended.

### T0Z03: Implement perf-cite skill

**Description:** Skill at `/opt/perf-lab/skills/perf-cite/`. entry.sh wraps `orca-cli citation-validator`. SKILL.md, Bats tests.
**Files:** `skills/perf-cite/entry.sh`, `skills/perf-cite/SKILL.md`, `tests/skills/test_perf_cite.bats`
**Acceptance:** smoke tests pass against fixture orca-cli; emits `synthesis_validated` events; flock writes to `/shared/locks/cite.lock`.

### T0Z04: Implement perf-contradict skill

**Description:** Skill wrapping `orca-cli contradiction-detector --claude-findings-file`. Skill is THIN — does not dispatch subagent. Findings file is precondition.
**Files:** `skills/perf-contradict/entry.sh`, `skills/perf-contradict/SKILL.md`, `tests/skills/test_perf_contradict.bats`
**Acceptance:** rejects missing findings file with exit 2 INPUT_INVALID; emits `contradiction_detected`.

### T0Z05: Implement perf-review skill

**Description:** Skill wrapping `orca-cli cross-agent-review --claude-findings-file`. Same thin-wrapper pattern as T0Z04.
**Files:** `skills/perf-review/entry.sh`, `skills/perf-review/SKILL.md`, `tests/skills/test_perf_review.bats`
**Acceptance:** emits `cross_review_summary` with `criteria_hash` field; exits 0 always.

### T0Z06: Implement host-side dispatch wrappers

**Description:** `scripts/perf-lab/orca-dispatch-contradict.sh` and `orca-dispatch-review.sh` plus shared `orca-dispatch-lib.sh` for stall detection. Implements the dispatch algorithm per orca's `docs/superpowers/contracts/dispatch-algorithm.md`.
**Files:** `scripts/perf-lab/orca-dispatch-{contradict,review,lib}.sh`, `tests/scripts/test_orca_dispatch.bats`
**Acceptance:** stall detection trips at 300s with sentinel findings file; hard timeout at 600s with separate sentinel; `parse-subagent-response` failure produces `PARSE_FAILURE` sentinel.

### T0Z07: Extend claim config schema for orca_policy

**Description:** Add `orca_policy` block recognition + validation. Includes `synthesis_validators`, `lease_overlap_check`, `review_required` (with binding fields target_sha256/criteria_hash/claim_id), `cite_threshold`, `cite_reference_set`, `model_tier_floor`.
**Files:** claim-config validator code, `tests/config/test_orca_policy_schema.py`
**Acceptance:** invalid policy values rejected; valid policies accepted; `review_required.criteria_hash` matches event payload.

### T0Z08: Wire synthesis_validators into perf-synthesis

**Description:** Validators run BEFORE acquiring `synthesis.lock`; lock is held only for the commit window. On validator failure, emit `feedback_needed` and abort commit.
**Files:** perf-synthesis flow code, `tests/integration/test_orca_synthesis_gate.bats`, `tests/integration/test_orca_synthesis_lock_window.bats`
**Acceptance:** lock-window test confirms synthesis.lock is NOT held during validator runs.

### T0Z09: Wire lease_overlap_check into scripts/runtime-v6/lease.sh

**Description:** Host-side scheduler integration (NOT perf-lease worker, which stays read-only). On overlap with active lease, scheduler shells to `orca-cli worktree-overlap-check`; conflict drives `lease_rejected` event.
**Files:** `scripts/runtime-v6/lease.sh`, `tests/integration/test_orca_lease_overlap.bats`
**Acceptance:** overlap detected → orca-cli invoked → conflict result drives event.

### T0Z10: Wire review_required into commit flows

**Description:** perf-synthesis and perf-artifact commit flows check claim's `orca_policy.review_required`. If set, require a `cross_review_summary` event whose payload `target_sha256` + `criteria_hash` + `claim_id` match.
**Files:** commit-flow code, `tests/integration/test_orca_review_required.bats`
**Acceptance:** stale events (mismatched binding fields) do NOT satisfy gate; matching events do.

### T0Z11: Add orca-cli install line to .devcontainer/Dockerfile

**Description:** Implements whichever path the PyPI decision doc selected (PyPI install, alternate-name PyPI, or bind-mount). Documents the alternate path in `docs/runtime/orca-policy.md`.
**Files:** `.devcontainer/Dockerfile`, `docs/runtime/orca-policy.md`
**Acceptance:** devcontainer build succeeds; `orca-cli --version` works inside container.

### T0Z12: Implement scripts/perf-lab/orca-probe.sh

**Description:** Compatibility probe runs at devcontainer build and (when orca_policy is set) at claim start. Verifies `--version`, capability matrix, writes probe report.
**Files:** `scripts/perf-lab/orca-probe.sh`, `tests/scripts/test_orca_probe.bats`
**Acceptance:** missing flag → probe fails; orca_policy disabled with warning event; tests cover happy path + each fail mode.

### T0Z13: Document operator guide

**Description:** `docs/runtime/orca-policy.md` covering: how to enable orca_policy per claim, mission-template defaults, model-tier policy semantics, Codex-host limitation (3 explicit operator paths), failure-mode reference.
**Files:** `docs/runtime/orca-policy.md`
**Acceptance:** doc covers all opt-in fields, all failure modes, and the Codex-host caveat.
```

- [ ] **Step 4.3: Run mdformat**

```bash
mdformat --check specs/010-self-organizing-research-runtime/tasks.md
```

- [ ] **Step 4.4: Commit**

```bash
git add specs/010-self-organizing-research-runtime/tasks.md
git commit -m "docs(spec-010): add T0Z task block for orca integration

T0Z00 through T0Z13: wait gate for orca prereqs, sibling spec
authoring, FR-008 amendment (hard prerequisite for skill emissions),
three thin skills, host-side dispatch wrappers, claim-config
schema extension, three policy wirings, Dockerfile install,
compatibility probe, operator guide.

All T0Z tasks blocked on T000i (perf-event skill foundation).
T0Z00 also blocked on orca repo Phase 4b-pre-1 through pre-5
merging."
```

---

## Task 5: Spec self-review + push + open PR

**Files:**
- None modified; documentation/process work only.

- [ ] **Step 5.1: Self-review the orca-integration.md and spec.md changes**

Run through the spec-PR review checks listed in orca v2 spec § "Test Plan — Split":
- `mdformat --check` on both files (ran in Tasks 2, 3, 4 — re-run here for cleanliness)
- Cross-ref check on `orca-integration.md`
- Schema-doc validation: the four event types defined match the JSON schema document syntax used in `data-model.md` (visual inspection)
- Diff-conflict check: re-read `spec.md` lines 420-451 and confirm `### Constraints` at 446-451 is unchanged

- [ ] **Step 5.2: Re-confirm prereqs status**

```bash
cd /home/taylor/spec-kit-orca
git log --oneline --grep "Phase 4b-pre" main | wc -l
```

Expected: 5. If less, do not push the perf-lab PR yet.

- [ ] **Step 5.3: Push the perf-lab branch**

```bash
cd ~/perf-lab
git push -u origin orca-integration-spec
```

- [ ] **Step 5.4: Open PR with structured description**

```bash
gh pr create --title "docs(spec-010): add orca integration spec contribution (Phase 4b)" --body "$(cat <<'EOF'
## Summary

- Adds new sibling spec `orca-integration.md` defining three thin skills (perf-cite, perf-contradict, perf-review), host-side dispatch wrappers, opt-in `orca_policy` block, four event-type extensions to FR-008, and the orca-cli compatibility contract.
- Reconciles `spec.md` Future Integration Notes with the new architecture (shim moves to perf-lab repo; worktree-overlap-check moves to host-side `lease.sh`; new `cross_review_summary` event type; `quality_gate` reserved for future completion-gate work).
- Adds T0Z block (T0Z00-T0Z13) to tasks.md, blocked on T000i (perf-event skill foundation).

This is a **spec contribution PR**. No running code in this PR; implementation tasks are tracked in the T0Z block and ship after T000i lands.

## Prerequisites (orca repo)

The following five commits in spec-kit-orca must be merged before T0Z00 can pass:

- Phase 4b-pre-1: `--claude-findings-file` / `--codex-findings-file` on `contradiction-detector`
- Phase 4b-pre-2: `orca-cli --version` flag
- Phase 4b-pre-3: PyPI publication decision artifact
- Phase 4b-pre-4: dispatch algorithm spec doc
- Phase 4b-pre-5: regression test for `build-review-prompt --kind <arbitrary>`

orca SHAs: <fill in actual SHAs from `git log --oneline --grep "Phase 4b-pre"` in the orca repo>

## Test plan

- [ ] `mdformat --check` passes on `orca-integration.md` and `spec.md`
- [ ] All internal cross-refs in `orca-integration.md` resolve
- [ ] `spec.md` § "Constraints" (lines 446-451 in pre-PR baseline) is unchanged by this PR
- [ ] Four new event types in FR-008 list match payload-schema syntax in `data-model.md`
- [ ] T0Z block dependencies (T0Z02 → T0Z03/04/05; T0Z00 wait gate; all blocked on T000i) are explicit
- [ ] orca repo prereqs are all merged (verify via `git log --grep "Phase 4b-pre"`)

## Out of scope

- Implementation of T0Z03+ (waits on T000i)
- Cross-repo CI between perf-lab and orca (manual probe today)
- Migration from perf-lab v5 (no migration; v6 is fresh runtime)

Source spec: `spec-kit-orca` commit `806877e`.
EOF
)"
```

- [ ] **Step 5.5: Capture the PR URL and note in orca repo**

Record the perf-lab PR URL in a follow-up commit to the orca repo:

```bash
cd /home/taylor/spec-kit-orca
# Edit docs/superpowers/notes/2026-04-29-symphony-readout.md or similar to record:
# "perf-lab spec PR: <url>"
git commit -am "docs: record perf-lab spec PR URL"
git push
```

---

## Self-Review Checklist

Before declaring this plan complete:

1. **Spec coverage:** Every section of orca v2.1 spec is reflected somewhere in `orca-integration.md` (with appropriate perf-lab-audience reframing). ✓
2. **Diff applies:** spec.md "before" baseline at lines 420-451 matches the orca v2 spec's diff "before" half. ✓
3. **Constraints preserved:** lines 446-451 of spec.md (Constraints subsection) unchanged in the PR. ✓
4. **T0Z dependency graph:** T0Z00 → all; T0Z02 → T0Z03/04/05; all blocked on T000i. ✓
5. **No code in this PR:** verify via `git diff origin/main --stat` — only `.md` files modified. ✓
6. **Prereqs cited:** PR description names all 5 orca SHAs explicitly. ✓

## Honest Risk Notes

- The biggest risk is `spec.md` drift between when the orca v2.1 spec was written (2026-04-29) and when this PR lands. Pre-flight Step 1.3 catches it. If drift is large, regenerate the diff from the actual current `spec.md` baseline.
- T0Z task numbers conflict with existing perf-lab task numbers if T000-T0Y are denser than expected. Verify in Step 4.1 that T0Z is unused before this PR; rename to T0Z' or similar if collision.
- Cross-repo PR coordination: this perf-lab PR cannot merge until the orca prereqs land. If orca prereqs hit unexpected review delays, the perf-lab PR sits in queue. Mitigation: open as draft until prereqs merge.
- The orca spec being cited (`806877e`) may itself revise; pin the cited SHA in the perf-lab PR description and update if a v2.2 lands.
- Markdown lint flavor: `mdformat` config differs between repos. Use perf-lab's `.mdformat.toml` (or equivalent) when running checks; don't import orca's.

## Estimated Effort

- Task 1 (pre-flight): 30 min
- Task 2 (orca-integration.md authoring): 3-4 hours (~600 lines, careful translation from orca v2 spec)
- Task 3 (spec.md unified diff): 30 min
- Task 4 (T0Z block in tasks.md): 1 hour
- Task 5 (self-review + PR): 30 min

Total: ~5-6 hours of focused work. Single sitting if uninterrupted.
