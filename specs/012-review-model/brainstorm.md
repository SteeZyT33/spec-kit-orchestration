# Brainstorm: Review Model v2 — Three Artifact-Based Reviews

**Feature Branch**: `012-review-model`
**Created**: 2026-04-11
**Status**: Brainstorm
**Supersedes**: `006-orca-review-artifacts` (breaking change — see Rollout section)
**Informed by**:
- `docs/refinement-reviews/2026-04-11-product-surface.md` (GPT Pro product-surface review)
- Session research on `github/spec-kit` `/speckit.clarify` command
- Session research on `spec-kitty` and `OpenSpec` architectures

---

## Problem

Orca's current review model has four top-level reviews — `code-review`,
`cross-review`, `pr-review`, `self-review` — plus `review.md` as an
umbrella. That's a lot of named subsystems competing for mindshare, and
the GPT Pro refinement review specifically called this out as one of the
places the product surface becomes too heavy.

Two things are wrong with the current shape:

1. **Cross-review is a top-level artifact.** Whether a different agent
   ran an adversarial pass is structurally indistinguishable from
   whether the code compiles — both are separate review files competing
   for the same narrative space. That's the wrong axis. Cross-review is
   a **mode** (same review done by a different agent), not a new thing
   to review.
2. **Self-review mixes two functions.** It's simultaneously "author
   checks their own code" (a mode of code review) and "how did this
   workflow go?" (a process retrospective). Different audiences,
   different questions, same command.

The four-review sprawl also leaks into downstream subsystems:
`flow_state.py` names all four as review milestones, `matriarch.py`
consumes a `_review_status_map` built from the same four, and `009
orca-yolo`'s `run-stage-model.md` contract names all four as explicit
run stages. Collapsing the four upstream requires touching every
downstream.

## Proposed Model

**Three reviews, keyed to the three artifacts that actually matter:**

| Review | Artifact reviewed | Primary question | Mode support |
|---|---|---|---|
| `review-spec` | `spec.md` (after `clarify` ran) | *Is this the right thing to build, and is it feasible?* | Cross-only (see Rationale) |
| `review-code` | Implementation — runs at phase boundary OR overall | *Is the built thing correct against the spec?* | Self **and** cross |
| `review-pr` | External PR comments | *How do we disposition the comments on this PR?* | Neither mode; narrow scope |

Cross-mode is not a flag. It's a **required named subsection** inside
each review artifact. Reading `review-code.md` answers *"was this
cross-reviewed?"* without any hunting — the Cross Pass section is
either present (with the agent name) or it's absent, and the verdict
field has to acknowledge either way.

### Artifact shapes

Each review artifact lives in the feature directory and has a fixed
section layout. Cross-pass and self-pass (where applicable) are
append-only — a second cross-pass adds a new `## Cross Pass`
subsection rather than overwriting the first.

**`review-spec.md`** (written after `speckit.clarify` has run over `spec.md`):

```markdown
# Review: Spec

## Prerequisites
- Clarify session: YYYY-MM-DD (required — block if missing)

## Cross Pass (agent: <name>)
- Cross-spec consistency findings
- Feasibility / tradeoff findings
- Security / compliance findings
- Dependency graph findings
- Industry-pattern comparison notes

## Verdict
- status: ready | needs-revision | blocked
- rationale: ...
- follow-ups: ...
```

**`review-code.md`** (append-only across phases, overall verdict at the end):

```markdown
# Review: Code

## Phase 1 Self Pass (agent: <name>, date: YYYY-MM-DD)
- Spec-compliance check
- Implementation quality
- Test coverage
- Regression risk

## Phase 1 Cross Pass (agent: <name>, date: YYYY-MM-DD)
- Same scope, adversarial framing
- Disagreements with self-pass explicitly called out

## Phase 2 Self Pass (agent: <name>, date: YYYY-MM-DD)
...

## Overall Verdict
- status: ready-for-pr | needs-fixes | blocked
- rationale: aggregates all phase passes
- follow-ups: ...
```

**`review-pr.md`** (narrow):

```markdown
# Review: PR Comments

## External Comments (source: GitHub PR #NN)
- comment 1: ... → disposition: addressed | rejected | deferred
- comment 2: ... → ...

## Retro Note
- one paragraph on how the PR review cycle went
- workflow improvements worth capturing

## Verdict
- status: merged | pending-merge | reverted
```

### Where process retrospective lives

The current `self-review` command has two functions: code self-check
(already covered by `review-code` Self Pass) and process retrospective
(how did the workflow go, where did we waste time).

**Decision: fold process retrospective into `review-pr.md` as a required
one-paragraph `## Retro Note` section.** Post-merge is when you
naturally look back — the PR closing out a feature is the right trigger
for a retro note. This preserves the function without adding a fourth
review artifact.

Trade-off: if a feature never makes it to a PR (e.g., abandoned,
archived, promoted to a different feature), there's no post-merge
moment. For now, accept that those cases don't get a process retro —
they're rare and the loss is small. Revisit if it becomes painful.

## Rationale for the hard decisions

### Why `review-spec` is cross-only (no self-pass)

`speckit.clarify` already runs an interactive sharpening pass over
`spec.md` and records answers durably under `## Clarifications`. That
IS the self-pass — the author walking through clarifying questions
against their own spec. Adding a formal `review-spec` self-pass on top
would be redundant paperwork.

`review-spec` is therefore **cross-only by design**: it's the moment
when a *different agent* challenges the clarified spec against
cross-spec consistency, feasibility, security/compliance, dependency
graph, and industry-pattern comparison. These five scopes are the
things `clarify` explicitly does not cover (confirmed via session audit
of `github/spec-kit`).

Downstream benefit: `review-spec` doesn't need mode flags at all. It's
always an adversarial pass. That removes a whole class of "did you run
it with the right mode?" friction.

### Why `review-code` supports both modes (self AND cross)

Unlike specs, code can legitimately be self-reviewed before a cross-pass
— the author can and should check their own implementation for
spec-compliance and obvious regressions before handing it to another
agent. Skipping self-pass to go straight to cross-pass would be
wasteful: cross-review is expensive and should be reserved for what
the author couldn't catch.

`review-code` is also the only review that supports **phase-level
granularity**. A feature with three user stories can have three rounds
of code review (one per phase completion) plus an overall verdict. The
single `review-code.md` file grows append-only across phases. Flow-state
reads the file once and sees the timeline.

### Why `review-pr` has no mode support

PR comment processing is a different beast from spec or code review. It
doesn't need an adversarial pass — the external PR reviewers are
already the cross-pass. The job is to disposition their comments, not
to second-guess them. Mode support would be dead weight.

The narrow scope also prevents `review-pr` from becoming the third
"full review gate" the current `pr-review` drifts into. By design it's
a thin command: walk the PR comments, mark each one addressed /
rejected / deferred, write the retro note, done.

## Downstream impact (what breaks)

This is a breaking change. The following need updates, and they are
the reason `012` is a new spec rather than an amendment to `006`:

### `specs/006-orca-review-artifacts/`
- Marked **superseded** with a pointer to `012`
- Existing artifacts (`review-code-template.md`, `review-cross-template.md`, `review-pr-template.md`, `review-self-template.md`) retired from active use
- Existing `commands/*-review.md` command prompts marked deprecated (deletion deferred per user instruction: *"i don't want to change the review prompts until we've really dialed this in"*)

### `specs/009-orca-yolo/contracts/run-stage-model.md`
- Current text names four review stages (`self-review`, `code-review`, `cross-review`, `pr-review`) in the stage vocabulary
- Collapse to three: `review-spec`, `review-code`, `review-pr`
- Update phase progression rules so cross-pass is an in-artifact requirement, not a stage transition

### `src/speckit_orca/flow_state.py`
- `_review_status_map` currently looks for `review-code.md`, `review-cross.md`, `review-pr.md`, `self-review.md` in the feature directory
- Update to look for `review-spec.md`, `review-code.md`, `review-pr.md`
- Update review-milestone interpretation to understand phase-level sections inside `review-code.md`
- Update "review progress" output in the machine-readable `FlowStateResult` contract

### `src/speckit_orca/matriarch.py`
- `_review_status_map` consumer currently aggregates the four-review shape into lane readiness
- Update to the three-review shape
- Add awareness of cross-pass presence as a readiness signal (a `review-code.md` without a `## Cross Pass` section should not be treated as review-ready for lanes that declared a cross-pass requirement)

### `.specify/orca/evolve/entries/013-spec-compliance-first-code-review.md`
- Currently targets `code-review`. After migration, targets `review-code`. Adjust `target_ref`.

### `commands/` prompts
- **Deferred.** User instruction: prompts do not change until the model is dialed in. This brainstorm proposes the model; command-prompt rewrites happen in a later task after the plan and contracts are locked.

### `README.md`
- The four-concept workflow section in PR #24 already has a "Review — durable evidence at every gate" block listing the current four reviews. After `012` merges, update that block to list the three new reviews and note that cross-pass is in-artifact.

## Rollout

### Option A — atomic breaking change (recommended)

Ship all the runtime, contract, and documentation changes in one wave
after the brainstorm is approved. Feature branches in flight at the
migration moment re-create their review artifacts in the new shape. No
coexistence period, no dual-vocabulary code paths.

Pros: no two-model drift, downstream code stays simple, migration is a
single moment.

Cons: any work already in flight loses its existing review artifacts
and has to re-run reviews in the new shape.

### Option B — dual-vocabulary coexistence

`flow_state.py` and `matriarch.py` accept BOTH the old and new review
filenames during a transition window, with deprecation warnings.
Feature branches written under the old model continue to work until
archived. New features use the new model.

Pros: no disruption to in-flight work.

Cons: two models live side by side, exactly the complexity the
refinement review warned against. Also twice the test surface.

**Recommendation: Option A.** The only in-flight work at migration time
is Orca's own specs (001-011 plus this 012). None of them are shipped
externally. The cost of re-running a review pass on whatever's in
flight is lower than the cost of maintaining dual vocabulary.

## Open questions (to resolve before plan.md)

1. **`review-spec` output location.** Is it one `review-spec.md` per
   feature in the feature dir, or does it live alongside the clarify
   session output? My lean: feature dir, next to `spec.md`, matching
   the other review artifacts.

2. **`review-code` phase naming.** Phases in 009-orca-yolo's run-stage
   model are named (`implement`, `self-review`, etc.), but user stories
   inside a feature (US1, US2, US3) have their own phase-like structure.
   Does `review-code` use the run-stage names or the US names? My lean:
   US names, because that's what matches `tasks.md` structure.

3. **Cross-pass agent selection.** When someone runs `review-code` in
   cross-mode, which agent runs the pass? Today `cross-review` has
   agent routing logic that picks a *different* agent than the one
   that wrote the code. Does `review-code --cross` preserve that
   routing or become explicit (`--cross --agent codex`)? My lean:
   preserve the auto-different-agent routing, but allow explicit
   override.

4. **Retro note optionality.** Is the `## Retro Note` in `review-pr.md`
   required or optional? My lean: required-but-can-be-"no notes" — the
   section must exist, but the content can be one sentence ("no
   workflow changes needed this cycle"). That makes the section a
   forcing function without demanding substance.

5. **Feature abandonment path.** If a feature is abandoned before PR,
   where does its retro go? My lean: accept the loss. Abandoned
   features are rare and the retro value is low.

6. **Template consolidation.** Do we ship new templates under
   `templates/review-spec-template.md`, `templates/review-code-template.md`,
   `templates/review-pr-template.md`, and retire the old four? Or do
   we skip templates entirely and let the command prompts render the
   shape inline? My lean: ship three templates and retire the four
   old ones in the same breaking wave.

## Explicit non-goals

- Not changing how `speckit.clarify` works. Orca delegates sharpening
  to upstream `github/spec-kit` and only adds adversarial review on
  top.
- Not adding a fourth review. Process retro lives inside `review-pr`.
- Not rewriting the review command prompts in this brainstorm. That
  comes after the model is approved and the plan lands.
- Not adding mode flags as hidden CLI options. All modes are surfaced
  as named artifact sections.
- Not introducing an event log for reviews in this feature. That's a
  separate question tied to `014-yolo-runtime` and spec-kitty harvest
  work.
- Not replacing `review.md` as an umbrella summary. `review.md`
  continues to exist as the rollup index pointing at the three
  artifact-specific reviews — same role it has today, just pointing at
  a shorter list.

## Dependencies on other in-flight work

- **PR #23** (deployment-readiness cleanup) — no direct dependency,
  but the `010 tasks.md` reconciliation in #23 and the four-review
  vocabulary in this brainstorm need to not conflict. Plan: write 012
  plan + contracts after #23 merges so the 010 tasks.md state is
  final.
- **PR #24** (product-surface refinement) — same file (`README.md`)
  is touched but in different sections. #24's Review block names the
  current four reviews; after 012 ships, update that block. Plan: 012
  plan lands after #24 merges to avoid conflict.
- **`013 spec-lite`** — independent. `spec-lite` may or may not
  participate in `review-spec` (open question for that brainstorm).
- **`014 yolo-runtime`** — depends on 012's run-stage collapse in 009.
  Plan: 012 plan lands before 014 brainstorm runs.

## Suggested next steps

1. Review this brainstorm (both for content and for the open questions
   above)
2. Resolve the six open questions
3. Write `specs/012-review-model/plan.md` with migration sequence,
   contract updates, and explicit file-by-file change list
4. Write `specs/012-review-model/data-model.md` and contract files
5. Then, only then, rewrite the review command prompts
