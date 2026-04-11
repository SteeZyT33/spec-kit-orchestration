# Plan: Review Model v2 — Three Artifact-Based Reviews

**Feature Branch**: `012-review-model`
**Created**: 2026-04-11
**Status**: Draft
**Brainstorm**: [brainstorm.md](./brainstorm.md)
**Research inputs**:
- [`docs/research/speckit-clarify-integration.md`](../../docs/research/speckit-clarify-integration.md)
  (integration contract for `review-spec` delegation to `speckit.clarify`)
- [`docs/refinement-reviews/2026-04-11-product-surface.md`](../../docs/refinement-reviews/2026-04-11-product-surface.md)
  (product-surface origin for collapsing the four reviews)

---

## 1. Summary

Collapse Orca's current four-review model (`code-review`, `cross-review`,
`pr-review`, `self-review`) into three artifact-keyed reviews plus
modes as in-artifact subsections. Supersede `006-orca-review-artifacts`,
update the 009 run-stage-model, rewrite `flow_state.py` and
`matriarch.py` review vocabulary, and defer command-prompt rewrites
until this plan and its contracts are locked.

The three reviews are **`review-spec`**, **`review-code`**, and
**`review-pr`**. Cross-mode is recorded as a required `## Cross Pass`
subsection inside the review artifact (with agent name inline),
never a hidden flag. Process retrospective folds into `review-pr.md`
as a required one-paragraph `## Retro Note` section.

This is a **breaking change**. Atomic rollout per the brainstorm's
Option A — no dual-vocabulary coexistence window. Only in-flight
work at migration time is Orca's own specs; none are shipped
externally.

## 2. Resolved questions (from 2026-04-11 session)

The six open questions in the brainstorm were resolved by the user.
Binding answers, captured here so the plan remains self-contained:

| # | Question | Resolution |
|---|---|---|
| 1 | `review-spec` file location | **Feature directory** next to `spec.md`, matching the other review artifacts |
| 2 | `review-code` phase naming | **User-story names** (US1, US2, US3) from `tasks.md`, not run-stage names |
| 3 | Cross-pass agent selection | **Always a different agent**, preferably highest tier; downgrade model only on timeout; no explicit override |
| 4 | Retro note optionality | **Required section, allowed to contain "no notes"** — forcing function without demanding substance |
| 5 | Feature abandonment path | **Accept the loss.** Abandoned features do not get a retro. |
| 6 | Template consolidation | **Retire the four old templates**, ship three new templates (`review-spec-template.md`, `review-code-template.md`, `review-pr-template.md`) in the same breaking wave |

**Question 3 is sharper than the brainstorm's proposed lean.** The
user's answer establishes a real policy, not just a default. See
section 6 below for the full cross-pass routing policy.

## 3. Scope

### In scope

- Define the three-review artifact contracts in
  `specs/012-review-model/contracts/` (contract work in follow-up task)
- Supersede `006-orca-review-artifacts` with a pointer to this spec
- Rewrite `specs/009-orca-yolo/contracts/run-stage-model.md` review
  stages from four names to three
- Rewrite `src/speckit_orca/flow_state.py` `_review_status_map` and
  review-milestone interpretation to the new vocabulary
- Rewrite `src/speckit_orca/matriarch.py` review-status consumer to
  the new vocabulary
- Update `.specify/orca/evolve/entries/013-spec-compliance-first-code-review.md`
  `target_ref` from `code-review` to `review-code`
- Retire the four old review templates under `templates/review-*-template.md`
- Ship the three new templates in the same wave
- Update `README.md`'s four-concept workflow "Review" section to list
  the three new reviews
- Define the cross-pass agent routing policy (new in this plan)
- Define the `speckit.clarify` integration contract for `review-spec`

### Explicitly out of scope

- **Command prompt rewrites** (`commands/code-review.md`,
  `commands/cross-review.md`, `commands/pr-review.md`,
  `commands/self-review.md`, plus any new `commands/review-spec.md`,
  `commands/review-code.md`, `commands/review-pr.md`). Deferred per
  user instruction: *"don't change review prompts until we have
  really dialed this in."* Prompt rewrites happen in a separate
  implementation task after contracts are locked.
- Migration of existing in-flight review artifacts. Orca has none
  that aren't owned by specs 001-011 which have already shipped; any
  future review artifacts generated before 012 lands use the old
  vocabulary and get re-run in the new shape.
- Renaming `review.md` umbrella summary. It stays as the rollup
  index pointing at the three artifact-specific reviews.
- Adding event-sourced state for review artifacts. That's tied to
  014 yolo runtime's event log, not this spec.
- Integration with capability packs. If a pack needs to extend
  review behavior, it does so through the command prompts (which
  this plan does not touch) not through the artifact contracts.

## 4. Migration strategy

**Atomic breaking change. Option A from the brainstorm.**

Rationale: the only in-flight work at migration time is Orca's own
specs, and none are shipped externally. The cost of re-running
review passes on whatever is in flight is lower than the cost of
maintaining dual vocabulary. Dual-vocabulary coexistence (Option B
in the brainstorm) is explicitly rejected because the refinement
review warned against exactly that kind of surface growth.

The migration lands as a single wave of commits in one PR, not a
sequence of partial PRs. Each commit in the wave is reviewable on
its own, but the wave merges atomically.

## 5. File-by-file change list

### Contracts to supersede

- **`specs/006-orca-review-artifacts/spec.md`** — mark `Status` as
  `Superseded by 012-review-model` with a pointer paragraph
  explaining that the four-review model is retired and the new
  model lives in `specs/012-review-model/`. Leave the rest of the
  content intact as a historical record.
- **`specs/006-orca-review-artifacts/contracts/*.md`** — leave
  alone as historical record. Add a `SUPERSEDED.md` file at the
  top of the contracts directory pointing at 012.

### Contracts to write (in follow-up task after plan approval)

- **`specs/012-review-model/contracts/review-spec-artifact.md`** —
  the `review-spec.md` shape, required sections, prerequisites
  block referencing `speckit.clarify`, verdict field enum
- **`specs/012-review-model/contracts/review-code-artifact.md`** —
  the `review-code.md` shape, append-only section rules for
  phase-level passes (using user-story names from `tasks.md`),
  self-pass and cross-pass subsection requirements, overall
  verdict aggregation rule
- **`specs/012-review-model/contracts/review-pr-artifact.md`** —
  the `review-pr.md` shape, comment-disposition section, retro
  note requirements (required section, allowed empty)
- **`specs/012-review-model/contracts/cross-pass-agent-routing.md`** —
  the cross-pass agent routing policy (see section 6 below), codified
  as a contract that binds both the runtime (`matriarch.py` agent
  selection) and the command prompts
- **`specs/012-review-model/contracts/clarify-integration.md`** —
  the `speckit.clarify` precondition check, scope boundary table,
  staleness detection rule (see section 7 below)

### Runtime to rewrite

- **`src/speckit_orca/flow_state.py`**:
  - Current `_review_status_map` looks for `review-code.md`,
    `review-cross.md`, `review-pr.md`, `self-review.md`
  - Update to look for `review-spec.md`, `review-code.md`, `review-pr.md`
  - Update review-milestone interpretation to parse `review-code.md`'s
    phase-level sections (US1, US2, US3 subsections) instead of
    treating it as a single-pass artifact
  - Update `FlowStateResult` contract so downstream consumers
    (matriarch, commands) see the new vocabulary

- **`src/speckit_orca/matriarch.py`**:
  - Update `_review_status_map` consumer to the new three-review vocabulary
  - Add awareness of cross-pass presence as a readiness signal: a
    `review-code.md` without a `## Cross Pass` section must not be
    treated as review-ready for lanes that declared cross-pass
    requirement
  - Implement the cross-pass agent routing policy (section 6) as
    part of lane agent selection. Matriarch is the authority that
    decides which agent runs the cross-pass.

- **`.specify/orca/evolve/entries/013-spec-compliance-first-code-review.md`** —
  update `target_ref` field from `code-review` to `review-code`.
  Also consider whether the entry's title still makes sense — the
  new `review-code` IS the compliance-first review, so the entry
  may be resolvable as `implemented` after 012 lands.

### 009 downstream vocabulary

- **`specs/009-orca-yolo/contracts/run-stage-model.md`**:
  - Current vocabulary names four review stages: `self-review`,
    `code-review`, `cross-review`, `pr-review`
  - Update to three: `review-spec`, `review-code`, `review-pr`
  - Phase progression: `review-spec` happens between `plan` and
    `implement` (sharpening gate), `review-code` happens at phase
    boundaries and overall after implementation, `review-pr`
    happens after `pr-ready`
  - Cross-pass is an in-artifact requirement, not a separate stage
    transition, so the stage model does not explicitly name
    cross-review stages anymore

- **`specs/009-orca-yolo/data-model.md`**:
  - Run Outcome entity currently references the four review stages
    in its status enum; update to the three new names
  - No structural change; vocabulary only

- **`specs/009-orca-yolo/spec.md`**:
  - Look for FRs that reference the four review stages by name and
    update to the new three. The Lane Agent supervised-mode FRs
    (FR-013 through FR-019) reference review artifacts; verify
    they still read correctly with the new vocabulary.

### Templates

- **`templates/review-code-template.md`** — retire
- **`templates/review-cross-template.md`** — retire
- **`templates/review-pr-template.md`** — retire (old content)
- **`templates/review-self-template.md`** — retire
- **`templates/review-template.md`** — keep as the umbrella
  `review.md` rollup template
- **`templates/review-spec-template.md`** — new
- **`templates/review-code-template.md`** — new (replaces retired)
- **`templates/review-pr-template.md`** — new (replaces retired)

The retired templates are deleted, not archived. Historical record
is captured in the 006 spec directory which stays intact.

### README

- **`README.md`** four-concept workflow "Review" section:
  - Currently lists the four reviews: `code-review`, `cross-review`,
    `pr-review`, `self-review` with `review` as the compatibility
    entrypoint
  - Update to the three new reviews with a note that cross-mode is
    in-artifact, self-mode is in-artifact (where applicable), and
    retro lives in `review-pr.md`

### Extension manifest

- **`extension.yml`** — currently registers four command names:
  `speckit.orca.code-review`, `speckit.orca.cross-review`,
  `speckit.orca.pr-review`, `speckit.orca.self-review`
- Update to three: `speckit.orca.review-spec`,
  `speckit.orca.review-code`, `speckit.orca.review-pr`
- File path pointers updated to the new command prompt locations
- Descriptions rewritten to match the new scopes

### Command prompts (deferred)

The following command prompt files exist today and will need
rewrites in a follow-up task **after the plan and contracts land**:

- Retire: `commands/code-review.md`, `commands/cross-review.md`,
  `commands/pr-review.md`, `commands/self-review.md`,
  `commands/review.md` (stays as compatibility router, may need
  rewiring)
- Create: `commands/review-spec.md`, `commands/review-code.md`,
  `commands/review-pr.md`

**The plan does not propose specific prompt content.** That is the
scope of the next implementation task after this plan is approved.
The plan only locks the contracts the prompts must conform to.

## 6. Cross-pass agent routing policy (new, from question 3 answer)

This is the policy that binds both `matriarch.py`'s runtime
agent-selection logic and the command prompts that run cross-pass
reviews. It is codified as a contract file
(`contracts/cross-pass-agent-routing.md`) in the follow-up task but
defined here as the source of truth.

### Policy

1. **Cross-pass always runs with a different agent than the one that
   authored the reviewed artifact.** The author agent is recorded
   in the artifact's Self Pass subsection (`review-code.md`) or in
   the clarified spec's session metadata (`review-spec.md`). The
   cross-pass agent MUST NOT be the same as the author.

2. **Agent selection prefers the highest-tier agent available.**
   "Highest tier" is defined by the cross-review backend's existing
   tier model from `003-cross-review-agent-selection` — Tier-1
   agents (codex, claude, gemini) are selected over Tier-2 and
   Tier-3 when available.

3. **Downgrade happens only on timeout.** If a highest-tier agent
   times out on a cross-pass, the next-highest available agent is
   selected and the pass is retried. The retry is recorded in the
   artifact as a second Cross Pass subsection with the lower-tier
   agent name — the original timeout is not hidden.

4. **No explicit override at the command level.** Operators do not
   pass `--agent codex` to a review command. The routing is
   deterministic based on author-agent exclusion and tier
   preference. If an operator needs a specific agent, they must
   change the author agent upstream (e.g., by running the implement
   phase with a different agent) rather than overriding at review
   time.

5. **No fallback to same-agent review.** If all tiers are
   unavailable or time out, the review pass **fails** with an
   explicit error message. It does not fall back to running the
   cross-pass with the author agent. Rationale: a same-agent
   cross-pass is indistinguishable from a self-pass and therefore
   provides no adversarial value.

### Interaction with 003 cross-review agent selection

The existing `003-cross-review-agent-selection` spec and its
runtime (`scripts/bash/crossreview-backend.py`) already handle tier
classification and agent routing for cross-reviews. The 012
cross-pass policy **reuses 003's tier model and routing backend**.
What 012 adds:

- The explicit "highest tier first, downgrade on timeout" preference
  (003 did not specify a preference)
- The "no same-agent fallback" rule (003 allowed fallback in some
  cases)
- The recording of retries as additional Cross Pass subsections in
  the review artifact

These additions should be back-ported to 003 as a contract amendment
so the two specs stay aligned, or 012 should explicitly supersede
the relevant 003 contract sections. Decision deferred to the
contract-writing task.

### Interaction with matriarch lane agents

In matriarch-supervised mode, the lane agent (per 010) is often
different from the cross-pass agent. Matriarch is the authority
that routes cross-pass agents based on this policy. The author
agent is whichever agent wrote the artifact under review; the lane
agent is whichever agent is currently supervising the lane. They
may be the same or different depending on the lane's configuration.

## 7. `speckit.clarify` integration contract (for `review-spec`)

Full details in
[`docs/research/speckit-clarify-integration.md`](../../docs/research/speckit-clarify-integration.md).
The plan references rather than duplicates.

### Precondition check (enforced at command start)

`review-spec` verifies that `speckit.clarify` has run on the target
spec before the review begins:

```python
spec_text = Path(spec_path).read_text(encoding="utf-8")
if "## Clarifications" not in spec_text:
    raise ReviewSpecError(...)
# Also verify at least one ### Session YYYY-MM-DD subheader
```

A stub `## Clarifications` heading with no session subheaders is
not sufficient. The check must find at least one
`### Session <date>` subheader.

### Scope split

| Owned by clarify (upstream) | Owned by `review-spec` |
|---|---|
| Functional scope & behavior | Cross-spec consistency |
| Domain & data model | Feasibility / tradeoff analysis |
| Interaction & UX flow | Security / compliance audit |
| Non-functional quality attributes | Dependency graph analysis |
| Integration & external dependencies | Industry-pattern comparison |
| Edge cases & failure handling | |
| Constraints & tradeoffs | |
| Terminology & consistency | |
| Completion signals | |
| Misc / placeholders | |

The review-spec command prompt (written later, in the follow-up
task) must explicitly instruct the cross-pass agent to **not**
re-ask questions covered by clarify's 10 categories. The
prerequisites block of `review-spec.md` records which clarify
session was most recent at review time.

### Staleness detection

`review-spec` records the latest clarify session date in its
`## Prerequisites` block. If clarify runs again after review-spec
(new questions asked, new answers recorded under a new
`### Session` subheader), `flow_state.py` should surface the
review-spec as **stale**. The verdict is no longer current until
review-spec is re-run.

Staleness is a flow-state concern, not a matriarch concern — the
review artifact is still present, it just needs re-running. The
staleness logic goes in `flow_state.py`'s review-milestone
interpretation.

## 8. Rollout sequence

Atomic breaking change. One PR, multiple commits grouped for review.
Suggested commit sequence:

### Commit 1 — Contracts

- Write all five new contract files under
  `specs/012-review-model/contracts/`
- Write `specs/012-review-model/data-model.md` describing the
  three artifact shapes as entities
- Write `specs/012-review-model/quickstart.md` showing operator
  flow

### Commit 2 — Supersede 006

- Update `specs/006-orca-review-artifacts/spec.md` Status to
  `Superseded by 012-review-model`
- Add `specs/006-orca-review-artifacts/contracts/SUPERSEDED.md`
  pointer

### Commit 3 — Runtime rewrite

- Update `src/speckit_orca/flow_state.py` review vocabulary and
  phase-section parsing
- Update `src/speckit_orca/matriarch.py` review vocabulary and
  cross-pass routing policy enforcement
- Add tests for the new review-artifact parsing
- Add tests for the cross-pass routing policy edge cases
  (timeout → downgrade, all-tiers-unavailable → fail)

### Commit 4 — 009 vocabulary

- Update `specs/009-orca-yolo/contracts/run-stage-model.md` to the
  three-review vocabulary
- Update `specs/009-orca-yolo/data-model.md` run outcome enum
- Scan `specs/009-orca-yolo/spec.md` for review-name references and
  update

### Commit 5 — Templates

- Retire the four old `templates/review-*-template.md` files
- Create the three new templates
- Keep `templates/review-template.md` as the umbrella

### Commit 6 — Extension manifest and README

- Update `extension.yml` command registrations
- Update `README.md` four-concept workflow Review section
- Update `.specify/orca/evolve/entries/013-spec-compliance-first-code-review.md`
  target_ref

### Commit 7 — Tasks file

- Write `specs/012-review-model/tasks.md` listing the
  implementation tasks (including command prompt rewrites as a
  final task)

**Command prompt rewrites are NOT in this rollout.** They land in a
separate implementation PR after this plan and its contracts are
approved.

## 9. Testing approach

### Unit tests

- `tests/test_flow_state.py` (may need creation if it does not exist)
  — verify the new `_review_status_map` vocabulary, phase-section
  parsing in `review-code.md`, staleness detection for `review-spec`
- `tests/test_matriarch.py` — verify cross-pass agent routing policy
  (different agent, tier preference, timeout downgrade, no
  same-agent fallback)

### Integration tests

- Run the three review artifact validators against example
  `review-spec.md`, `review-code.md`, `review-pr.md` fixture files
  and verify they accept valid artifacts and reject invalid ones
- Verify a `review-code.md` with a Self Pass but no Cross Pass is
  correctly reported as not-cross-reviewed by flow-state
- Verify a `review-spec.md` without a clarify precondition block is
  rejected by the command's precondition check (this test lives in
  the command-prompt implementation task, noted here for coverage)

### Manual verification

- Walk the `quickstart.md` scenarios end-to-end against a real
  feature spec
- Verify the `speckit.clarify` precondition check works against a
  real spec.md file that has and has not been clarified

## 10. Dependencies and sequencing

### Hard prerequisites (must merge before this plan's implementation wave)

- **PR #28** (audits) — already open, merging when convenient. Not
  strictly blocking the plan, but the `speckit-clarify-integration.md`
  research doc lives there and should be on main before the plan's
  implementation cites it.

### Soft prerequisites

- `013-spec-lite` plan.md — independent, but the two breaking waves
  can share coordination (README updates, etc.). No hard dependency.
- Matriarch v1.1 refinements — orthogonal, can ship in parallel.

### What this plan blocks

- **`014-yolo-runtime` plan.md** — 014 consumes the new review
  vocabulary. 014's plan should be written AFTER 012's plan lands
  so the review-stage references are correct from the start.
- **Command prompt rewrites for all review commands** — explicitly
  deferred to a follow-up implementation task after 012 plan and
  contracts are approved.

### Explicit sequencing

1. **Now**: this plan merges into main (as a plan PR, reviewable)
2. **Next**: contracts-and-data-model PR for 012 (the five contract
   files + data-model.md + quickstart.md)
3. **Then**: runtime rewrite PR for 012 (flow_state.py + matriarch.py +
   tests)
4. **In parallel**: 013 plan and 013 contracts can proceed independently
5. **After 012 runtime lands**: 014 plan.md can be drafted with the
   correct review vocabulary
6. **Then**: command prompt rewrites for all review commands in a
   single dedicated PR
7. **Atomic merge moment**: 006 supersede + 009 vocabulary update +
   README update + extension.yml update + template retire+create +
   evolve entry target_ref update — one wave, one PR

## 11. Success criteria

- `flow_state.py` `_review_status_map` reports review state in
  the new three-review vocabulary without reference to the old
  four names
- `matriarch.py` lane readiness considers cross-pass presence, not
  just review-file presence
- `speckit.clarify` precondition check on `review-spec` rejects a
  spec without a valid `## Clarifications` session
- Cross-pass agent routing policy enforced: no same-agent
  fallbacks, highest tier first, timeout downgrade recorded in
  artifact
- All 45 existing tests still pass after runtime rewrite
- New tests cover the cross-pass routing edge cases
- 009's run-stage-model vocabulary matches 012's artifact names
- Zero references to `review-code.md`, `review-cross.md`,
  `review-pr.md`, `self-review.md` as stage-level artifacts in
  runtime code (grep -r should find only historical references in
  `specs/006-*/` and `docs/`)
- README four-concept workflow accurately describes the three
  reviews plus cross/self as modes
- Extension.yml registers the three new commands and no longer
  registers the four old ones

## 12. Explicit non-goals

- Not changing how `speckit.clarify` works (delegates to upstream)
- Not adding a fourth review under any circumstances (process retro
  stays inside `review-pr.md`)
- Not rewriting review command prompts in this plan (deferred)
- Not adding mode flags as hidden CLI options (modes are
  artifact-section-based)
- Not introducing an event log for reviews (tied to 014, not 012)
- Not retaining backward compatibility with the four-review
  vocabulary (breaking change)
- Not preserving abandoned-feature review state (accepted loss)

## 13. Open questions for the contract-writing task

These are questions that surface naturally during plan drafting but
are properly answered during the contract-writing task, not now:

1. **Artifact schema**: Should the review artifacts use YAML
   frontmatter + markdown body, or pure markdown with strict
   section naming? My lean: pure markdown with strict sections —
   matches the current review template style and avoids a parser
   dependency.
2. **Cross-pass retry limit**: How many tier-downgrade retries
   before hard fail? My lean: three retries max (Tier-1 timeout →
   Tier-2 → Tier-3 → fail), matching the tier model from 003.
3. **`review.md` umbrella rewrite**: Should the umbrella
   `review.md` template (kept in this plan) also update its
   pointers to the new three artifacts? Obviously yes. But should
   it gain new fields? My lean: no new fields; same rollup shape
   pointing at the three artifact-specific files.
4. **Matriarch lane consumer signature**: Does matriarch's
   `_review_status_map` return the same shape (dict-of-status) or
   a new structured type? My lean: same shape, just with new keys,
   to minimize downstream matriarch changes.

## 14. Suggested next steps

1. Merge this plan PR (after review)
2. Start the contract-writing task: five contract files,
   data-model, quickstart — all under `specs/012-review-model/`
3. In parallel, start the `013-spec-lite` plan (independent)
4. After 012 contracts approved, start the runtime rewrite
5. After 012 runtime lands, draft 014 plan with correct vocabulary
6. After all the above, write the new command prompts in one
   dedicated PR and retire the old ones
