# Brainstorm

## Problem

Orca has durable artifacts for parts of the workflow, but it still lacks a
coherent way to answer:

- where is this feature in the lifecycle?
- which review stages are complete?
- what is the next likely action?
- can a later command or a fresh session resume without guessing?

Right now Orca leans too heavily on branch inference, ad hoc file presence, and
human memory. That is not enough for a workflow system, and it is definitely not
enough for later `orca-yolo`.

The repomix review of `cc-spex` made this clearer: persistent flow state is one
of the real missing foundations between memory and orchestration.

## Desired Outcome

Define an Orca-native flow-state model that:

- is durable and provider-agnostic
- can determine current stage from real artifacts
- tracks review completion separately from implementation progress
- exposes next-step guidance
- supports later resume/start-from behavior without depending on chat history
- composes cleanly with brainstorm memory, review artifacts, worktrees, and
  eventual `orca-yolo`

## Constraints

- Must remain provider-agnostic.
- Must not depend on Claude-specific statusline or session substrate.
- Must stay small and inspectable, not become a hidden automation engine.
- Must work with Orca's existing artifact model rather than requiring a total
  rewrite first.
- Must not force `orca-yolo` semantics into the system too early.
- Should tolerate partial feature state and missing artifacts gracefully.

## Existing Context

- [spec.md](spec.md) is
  intentionally minimal and currently defines only the core value:
  resume/status/next-step plus review-stage separation.
- [orca-harvest-matrix.md](../../docs/orca-harvest-matrix.md)
  already identifies flow state as one of the highest-value Spex harvest items.
- [review-artifacts spec](../006-orca-review-artifacts/spec.md)
  is adjacent and will likely become one of the main inputs to flow state.
- [brainstorm-memory spec](../002-brainstorm-memory/spec.md)
  already establishes upstream durable inputs.
- Spex appears to combine:
  - stage state
  - review-stage evidence
  - resume/start-from semantics
  - statusline rendering
  Orca should borrow the state model first, not the UI-first implementation.

Likely Orca consumers of flow state:

- `speckit.orca.assign`
- `speckit.orca.cross-review`
- `speckit.orca.pr-review`
- `speckit.orca.self-review`
- future `orca-yolo`
- future status/dashboard surface

## Options Considered

### Option A: Computed-First Flow State With Thin Durable Metadata

Flow state is derived primarily from durable workflow artifacts:

- `spec.md`
- `plan.md`
- `tasks.md`
- brainstorm memory links
- review artifacts
- worktree metadata when relevant

Then Orca writes a small normalized state artifact only where needed for:

- resume/start-from
- next-step caching
- explicit status inspection

Why this is attractive:

- keeps the system grounded in real artifacts
- avoids creating a second hidden source of truth too early
- fits Orca's preference for small runtime surfaces
- degrades better when artifacts are partial or hand-edited

Main risk:

- derived state logic can get fuzzy if review artifacts remain underspecified

### Option B: Fully Persisted Flow-State Registry As Primary Truth

Orca maintains a durable state file or directory as the primary workflow truth,
and commands update it directly as stages progress.

Why this is attractive:

- simpler status reads
- easier to support strict resume/start-from
- status UI becomes straightforward later

Why it is weaker right now:

- too easy for runtime state to drift from actual artifacts
- would force many commands to update state before the review-artifact and
  handoff layers are mature
- creates a larger hidden substrate earlier than Orca should tolerate

### Option C: Statusline/UX First

Start by rendering a visible status summary and let the data model evolve later.

Why it is tempting:

- very user-visible
- feels like fast progress

Why it should be downgraded:

- it reverses the dependency order shown by repomix
- status rendering without a durable model becomes another thin layer of
  inference
- it risks copying Spex's visible UX before Orca has the foundations

## Recommendation

Favor **Option A: computed-first flow state with thin durable metadata**.

That is the best fit for Orca right now because it:

- uses durable artifacts as the real substrate
- avoids a premature hidden state machine
- leaves room for explicit run-state later where orchestration truly needs it
- aligns cleanly with the planned `review-artifacts` and `context-handoffs`
  features

In practical terms, `005` should probably define:

1. a canonical stage model
2. a review-stage model distinct from build progress
3. a state-computation contract from existing artifacts
4. a small optional persisted state artifact only for resume/start-from or
   cached next-step guidance

## Open Questions

- Should flow state be stored under `specs/<feature>/` or under a repo-local
  Orca runtime path such as `.specify/orca/flow/`?
- What are the exact canonical stages Orca wants to track?
  Candidate set:
  brainstorm, specify, plan, tasks, assign, implement, code-review,
  cross-review, pr-review, self-review
- Should review stages be modeled as parallel sub-state to the main phase, or
  as separate milestones?
- How much of flow state can be computed before `006-orca-review-artifacts` is
  fully implemented?
- Is resume/start-from part of `005`, or does `005` only provide the state model
  that later orchestration consumes?
- Should worktree lane state appear in feature flow state, or remain a separate
  subsystem with only links into flow state?

## Ready For Spec

This is not a micro-spec. It needs a fuller feature spec and then planning.

Recommended next command: `/speckit.specify` if we want to deepen the feature
contract, or `/speckit.plan` once we accept this design center:

- computed-first flow state
- artifacts as primary truth
- thin durable metadata only where resumability genuinely needs it
