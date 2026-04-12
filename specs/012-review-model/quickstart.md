# Quickstart: 012 Review Model

**Status**: Draft
**Parent**: [plan.md](./plan.md)

Walked-through example of a full feature cycle through the three
reviews. Shows what each artifact looks like at each stage, which
agents run which passes, and how flow-state aggregates the whole
thing. Written from the operator's point of view.

---

## The feature

Say you're shipping a new Orca feature: **`020-example-feature`**.
The feature has two user stories (US1 and US2) and needs to go
through the full workflow: spec → clarify → review-spec → plan →
tasks → implement → review-code → pr-create → review-pr.

The default agent for your repo is **`claude`**. Cross-pass
routing prefers Tier-1 agents per 012's policy, so cross-passes
will be routed to **`codex`** (different from `claude`, Tier 1).

## Step 0 — Write the spec

You use `/speckit.specify` to draft `specs/020-example-feature/spec.md`.
The spec has Functional Requirements, User Stories, Success
Criteria — all the usual sections. `claude` does the drafting.

At this point there is no `## Clarifications` section yet.

## Step 1 — Run `/speckit.clarify`

You run `/speckit.clarify` against the new spec. `claude` (or
whoever you have configured for clarify) walks through its 10
taxonomy categories, asks up to 5 targeted questions where
coverage is partial or missing, and records answers into
`spec.md` under a new `## Clarifications` section.

After clarify runs, `spec.md` looks like this (abbreviated):

```markdown
# Feature Specification: Example Feature

**Status**: Draft

## User Scenarios & Testing
...

## Functional Requirements
- **FR-001**: ...
- **FR-002**: ...

## Clarifications

### Session 2026-04-12
- Q: Should the feature support concurrent access? → A: Yes, with
  optimistic locking per the session answer.
- Q: What happens when input is empty? → A: Return a well-formed
  empty result, do not error.
- ...
```

Clarify also writes inline updates into the FR section as
ambiguities are resolved — e.g., FR-002 might gain a sentence
about empty input behavior.

## Step 2 — Run `review-spec` (cross-only)

Now you run `/speckit.review-spec specs/020-example-feature/`.
The command starts by enforcing its precondition check — both
conditions per the clarify integration contract:

```python
if "## Clarifications" not in spec_text:
    raise ReviewSpecError("spec.md missing ## Clarifications section; run /speckit.clarify first")
if not re.search(r"^### Session \d{4}-\d{2}-\d{2}", spec_text, re.MULTILINE):
    raise ReviewSpecError("## Clarifications section has no ### Session YYYY-MM-DD subheader; run /speckit.clarify first")
```

The spec has a `## Clarifications` section with one
`### Session 2026-04-12` subheader, so both checks pass.

The command then calls into matriarch's
`select_cross_pass_agent(author_agent="claude")`. Matriarch walks
the Tier-1 list, excludes `claude` (the author), and picks the
first available Tier-1 agent: **`codex`**.

`codex` runs the cross-pass. It specifically looks at the five
categories clarify doesn't cover: cross-spec consistency,
feasibility, security/compliance, dependency graph, industry
patterns. It writes `review-spec.md`:

```markdown
# Review: Spec

## Prerequisites
- Clarify session: 2026-04-12

## Cross Pass (agent: codex, date: 2026-04-12)

### Cross-spec consistency
- FR-003 conflicts with `specs/018-neighbor-feature/spec.md` FR-005 —
  both define what happens on the same event in incompatible ways.
  Recommend resolving before plan phase.

### Feasibility / tradeoff
- FR-002's optimistic locking assumes the underlying datastore
  supports compare-and-swap. spec-kit-orca's current matriarch
  lane registry uses advisory locks, not CAS. Implementation cost
  is non-trivial — worth discussing tradeoff of alternative
  (pessimistic locking with timeout).

### Security / compliance
- No findings. Feature does not touch PII or secret management.

### Dependency graph
- No new external API dependencies introduced by this spec.

### Industry-pattern comparison
- The FR-002 pattern matches the standard optimistic-concurrency
  pattern from DDD literature (Evans, "Domain-Driven Design").
  Implementation guidance in chapter 5.

## Verdict
- status: needs-revision
- rationale: Cross-spec conflict with 018's FR-005 must be resolved before plan phase. Feasibility tradeoff on FR-002 is worth a brief discussion but not blocking.
- follow-ups:
  - Resolve 018 vs 020 FR conflict explicitly in 020's spec
  - Document the optimistic-locking tradeoff in 020's plan
```

Flow-state now reports `review_spec_status: "present"` with
`verdict: "needs-revision"`. Matriarch treats the lane as
**not review-ready** until the follow-ups are addressed.

## Step 3 — Author responds

You update `spec.md` to resolve the 018 conflict. Since the
content change is substantive, you re-run `/speckit.clarify`
(optional but good practice) and it adds a second session:

```markdown
## Clarifications

### Session 2026-04-12
- Q: ...
- ...

### Session 2026-04-13
- Q: How should 020 handle the event that 018 also claims? →
  A: 018's handler runs first, 020 fallbacks to no-op if 018 handled.
```

Now `review-spec.md` is **stale** — its prerequisites reference
`2026-04-12` but the current latest clarify session is
`2026-04-13`. Flow-state sets `stale_against_clarify: True` and
matriarch blocks the lane from advancing.

You re-run `/speckit.review-spec`. The new review-spec.md is
written fresh (it's stale, the old one is superseded). It passes
this time:

```markdown
# Review: Spec

## Prerequisites
- Clarify session: 2026-04-13

## Cross Pass (agent: codex, date: 2026-04-13)
### Cross-spec consistency
- 018 vs 020 conflict resolved via the clarify answer. No
  remaining cross-spec issues.
### Feasibility / tradeoff
- Optimistic locking tradeoff documented in spec. OK.
### Security / compliance
- No findings.
### Dependency graph
- No new dependencies.
### Industry-pattern comparison
- Pattern alignment confirmed.

## Verdict
- status: ready
- rationale: Cross-spec conflict resolved; all other categories clean.
- follow-ups: none
```

Flow-state now reports the review as ready. Lane is review-spec-clear.

## Step 4 — Plan, tasks, and implement US1

You run `/speckit.plan`, which produces `plan.md`. You run
`/speckit.tasks`, which produces `tasks.md` with US1 and US2.
You begin implementing US1.

During implementation, `claude` writes code and tests for US1.
You verify locally, commit, and declare US1 done for review.

## Step 5 — Run `review-code` for US1

You run `/speckit.review-code --phase US1`. The command walks
the self-pass first. The self-pass agent is `claude` (author).
`claude` reviews its own US1 work:

```markdown
# Review: Code

## US1 Self Pass (agent: claude, date: 2026-04-14)

### Spec compliance
- FR-001 satisfied by `src/speckit_orca/example.py:42-78`
- FR-002 (optimistic locking) satisfied by `src/speckit_orca/example.py:95`
- FR-003 no-op fallback satisfied by `src/speckit_orca/example.py:120`

### Implementation quality
- Functions are pure, no side effects outside the declared I/O
- Error handling covers the empty-input case per the clarify
  answer

### Test coverage
- `tests/test_example.py` covers happy path, empty input, and
  concurrent access scenarios
- Coverage: 92% lines in `example.py`

### Regression risk
- Touches `flow_state.py` indirectly via new event type; existing
  `test_flow_state.py` still passes
```

Then the cross-pass. The command calls
`select_cross_pass_agent(author_agent="claude")` again →
returns **`codex`**. `codex` runs the cross-pass adversarially:

```markdown
## US1 Cross Pass (agent: codex, date: 2026-04-14)

### Spec compliance
- **Disagreement with self-pass**: self-pass claimed FR-003 no-op
  fallback was covered by line 120, but line 120 only handles the
  case where 018's handler returned success. It does NOT handle
  the case where 018's handler raised an exception and the
  exception was swallowed upstream. The clarify answer requires
  fallback on ALL paths, not just the success path.

### Implementation quality
- Agreement with self-pass.

### Test coverage
- Missing test: 018-raises-exception → 020-falls-back. Should be
  in `tests/test_example.py`.
- Coverage number is fine, but the uncovered branches include
  the exception-handling path noted above.

### Regression risk
- No new concerns beyond the missing test case.
```

The cross-pass found a real gap. Flow-state reports
`review_code_status: "phases_partial"` with the US1 cross-pass
disagreeing. No `## Overall Verdict` exists yet because US2 is
not reviewed.

## Step 6 — Author fixes US1 and re-runs review-code

You fix the exception-handling path and add the missing test.
You re-run `/speckit.review-code --phase US1`. New self-pass and
cross-pass sections are appended (append-only rule):

```markdown
## US1 Self Pass (agent: claude, date: 2026-04-14)
... (first pass, unchanged)

## US1 Cross Pass (agent: codex, date: 2026-04-14)
... (first pass with finding, unchanged)

## US1 Self Pass (agent: claude, date: 2026-04-15)

### Spec compliance
- FR-003 no-op fallback now covers both success and exception
  paths (commit abc123).

### Implementation quality
- No changes from first pass.

### Test coverage
- New test `test_fallback_on_018_exception` added at
  `tests/test_example.py:145`. Coverage: 97% lines.

### Regression risk
- No changes.

## US1 Cross Pass (agent: codex, date: 2026-04-15)

### Spec compliance
- Fix verified. FR-003 fallback is now complete.

### Implementation quality
- Agreement with self-pass.

### Test coverage
- New test exercises the exception path as expected. No gaps.

### Regression risk
- Clean.
```

US1 is now reviewed clean.

## Step 7 — Implement US2 and run its review-code

You implement US2. Same pattern: self-pass by `claude`, cross-pass
by `codex`. First round finds a small issue, second round clears
it. Append-only.

After US2's second round clears, `review-code.md` contains:

- US1 Self Pass (1st round)
- US1 Cross Pass (1st round, with finding)
- US1 Self Pass (2nd round, fixed)
- US1 Cross Pass (2nd round, clean)
- US2 Self Pass (1st round)
- US2 Cross Pass (1st round, with finding)
- US2 Self Pass (2nd round, fixed)
- US2 Cross Pass (2nd round, clean)

With all phases reviewed, you write the `## Overall Verdict`:

```markdown
## Overall Verdict
- status: ready-for-pr
- rationale: Both user stories completed two review rounds. Initial cross-pass findings were legitimate and were addressed. Final passes are clean across spec compliance, implementation quality, test coverage, and regression risk.
- follow-ups: none
```

Flow-state now reports `review_code_status: "overall_complete"`
with verdict `ready-for-pr`.

## Step 8 — Open the PR

You run `/speckit.pr-create`. This opens a GitHub PR against
main. Matriarch's lane state advances to `for_pr_review`.

## Step 9 — External review comments arrive

A reviewer (human `alice`) leaves two comments on the PR. You
run `/speckit.review-pr specs/020-example-feature/`. The command
creates `review-pr.md`:

```markdown
# Review: PR Comments

## PR Identifier
- repository: SteeZyT33/spec-kit-orca
- number: 42
- opened: 2026-04-16

## External Comments

### Round 1 (2026-04-16)
- **Comment #3** (reviewer: alice, date: 2026-04-16)
  - thread: "this should use the existing helper in utils.py rather than a new local function"
  - disposition: addressed
  - commit: def456
- **Comment #4** (reviewer: alice, date: 2026-04-16)
  - thread: "nit: variable name `x` should be `item`"
  - disposition: deferred
  - response: will be handled in follow-up PR #45 (readability pass)

## Retro Note

This cycle surfaced one real cross-spec conflict at review-spec
time (018 vs 020) that was worth resolving before plan. Review-
code caught both US1 and US2 exception-path gaps that the
self-pass missed. Overall: the 3-review model paid off here,
especially the cross-pass finding on US1 that clarified the FR-003
language itself.

## Verdict
- status: pending-merge
```

Flow-state reports `review_pr_status: "in_progress"` because
verdict is `pending-merge`.

## Step 10 — PR merges

alice approves, CI is green, and the PR is merged. You update
`review-pr.md`'s `## Verdict`:

```markdown
## Verdict
- status: merged
- merged-at: 2026-04-16
```

Flow-state reports `review_pr_status: "complete"` and
`overall_ready_for_merge: True` (all three reviews terminal).

## What the operator learned

- **`review-spec` caught a real cross-spec conflict** (020 vs
  018's FR-005) before plan work started. That alone saved the
  author from rewriting plan.md.
- **`review-code` cross-pass caught two exception-path gaps** that
  the author's self-pass rationalized as "handled" but actually
  weren't. The cross-agent adversarial framing made the
  difference.
- **`review-pr` stayed narrow**: comment disposition + retro note,
  no duplicate "is this code good?" review. The heavy review
  work happened in `review-code`, not at PR time.
- **The retro note captured what worked** for the next cycle
  without adding a fourth review artifact.
- **No operator ever passed `--agent <name>` to a review command.**
  Cross-pass routing was automatic via matriarch, and it always
  picked `codex` (different from the `claude` author, Tier 1,
  available in the repo).

## What this walkthrough does NOT cover

- **Timeout downgrades**: if `codex` had timed out during a
  cross-pass, matriarch would have returned the next Tier-1
  agent (`gemini`) and the artifact would record both the
  timeout entry and the retry entry. Covered in
  `contracts/cross-pass-agent-routing.md`.
- **Abandoned features**: if you'd killed 020 partway through,
  there would be no retro note (accepted loss per 012 question 5
  resolution). Review artifacts for abandoned features stay on
  disk but are never aggregated into a completed verdict.
- **Matriarch-supervised mode**: in supervised mode, yolo (014)
  would orchestrate the whole walkthrough automatically,
  advancing stages based on flow-state's aggregate. The operator
  would see fewer individual command invocations. Same artifacts,
  different driver.

## Validation against the contracts

Each step above conforms to the contracts under `./contracts/`:

- Step 2's `review-spec.md` matches `review-spec-artifact.md`:
  cross-only, prerequisites block present, five body
  subsections, verdict enum value
- Step 5-7's `review-code.md` matches `review-code-artifact.md`:
  append-only across phases, self-pass before cross-pass, agents
  differ, all four body subsections, overall verdict after all
  phases
- Step 9's `review-pr.md` matches `review-pr-artifact.md`:
  PR identifier, external comments with dispositions, required
  retro note (non-empty this cycle), verdict enum value
- Cross-pass agent selection in steps 2, 5, and 7 matches
  `cross-pass-agent-routing.md`: different from author, highest
  tier available, no operator override
- Clarify precondition in step 2 matches `clarify-integration.md`:
  `## Clarifications` with at least one `### Session` subheader,
  and the stale-against-clarify detection fires in step 3 when
  the operator re-runs clarify
