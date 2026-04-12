# Contract: `review-code.md` Artifact

**Status**: Draft
**Parent**: [012-review-model plan.md](../plan.md)

Defines the durable shape of a `review-code.md` file — the review
of implementation work against the spec. Unlike `review-spec`,
`review-code` supports **both self-pass and cross-pass modes** and
is **append-only across phases** (user stories from `tasks.md`).

## Location

One `review-code.md` per feature, living in the feature directory:

```text
specs/NNN-<slug>/
├── spec.md
├── review-spec.md
├── plan.md
├── tasks.md
├── review-code.md   ← this artifact
├── ...
```

## Append-only across phases

User stories in `tasks.md` (US1, US2, US3, …) each get their own
review-code sections. The file grows append-only:

```markdown
# Review: Code

## US1 Self Pass (agent: claude, date: 2026-04-11)
...

## US1 Cross Pass (agent: codex, date: 2026-04-11)
...

## US2 Self Pass (agent: claude, date: 2026-04-12)
...

## US2 Cross Pass (agent: codex, date: 2026-04-12)
...

## Overall Verdict
- status: ready-for-pr
- rationale: ...
```

Phase names (**US1**, **US2**, …) come from `tasks.md`'s user
story structure, not from 009's run-stage names. This is the
resolution of 012 open question 2.

## Required sections

### `# Review: Code`

Top-level heading. Fixed.

### `## <phase> Self Pass (agent: <name>, date: YYYY-MM-DD)`

Required for each reviewed phase. Parameterized with:

- **phase**: the user story name (`US1`, `US2`, or a custom
  user-story label from `tasks.md`). Must match exactly a user
  story section header in `tasks.md`. The literal string `Overall`
  is NOT a valid phase name — `## Overall Verdict` is a dedicated
  section with its own shape, not a Self/Cross Pass pair.
- **agent**: the agent that authored the implementation being
  reviewed. Self-pass means the author reviews their own work.
- **date**: RFC3339 date the pass was run.

Self-pass body covers:

```markdown
## US1 Self Pass (agent: claude, date: 2026-04-11)

### Spec compliance
- ...

### Implementation quality
- ...

### Test coverage
- ...

### Regression risk
- ...
```

Four required subsections. A pass declaring "no issues" in a
category MUST still include the subheading with an explicit
bullet.

### `## <phase> Cross Pass (agent: <name>, date: YYYY-MM-DD)`

Required for each phase that had a self-pass, UNLESS the lane's
review policy explicitly exempts cross-pass (not available in v1;
cross-pass is always required).

Parameterized like self-pass. The **agent MUST be different** from
the self-pass agent for the same phase. Enforced by the cross-pass
agent routing policy.

Cross-pass body mirrors self-pass structure (same four
subsections) but is framed adversarially — the cross-pass agent
looks for spec-compliance gaps the author missed, implementation
quality issues the author rationalized away, untested branches,
and non-obvious regression surfaces.

If the cross-pass agent disagrees with a self-pass finding, the
disagreement MUST be called out inline:

```markdown
## US1 Cross Pass (agent: codex, date: 2026-04-11)

### Spec compliance
- **Disagreement with self-pass**: self-pass claimed FR-005 was
  satisfied by line 42, but line 42 only handles the happy path.
  FR-005 explicitly names the empty-input case which is not
  covered.
- ...
```

### `## Overall Verdict`

Required at the end of the file once all phases have been
reviewed. Required fields:

- `- status: ready-for-pr | needs-fixes | blocked`
- `- rationale: <one-paragraph aggregate summary across all phases>`
- `- follow-ups: <bulleted list or "none">`

**`ready-for-pr`** means the overall implementation is ready to
advance to `pr-create`. All phases have both self-pass and
cross-pass, all verdicts align.

**`needs-fixes`** means at least one phase has a blocking finding
that requires code changes before PR.

**`blocked`** means the review cannot complete without an external
decision.

## Append-only rule

**Sections are append-only.** A second review of US1 (after the
author fixed issues from the first round) appends a new
`## US1 Self Pass` and `## US1 Cross Pass` with the current date
rather than editing the previous ones. Example:

```markdown
## US1 Self Pass (agent: claude, date: 2026-04-11)
... initial review ...

## US1 Cross Pass (agent: codex, date: 2026-04-11)
... finding: "FR-005 empty-input case not covered" ...

## US1 Self Pass (agent: claude, date: 2026-04-12)
... re-review after fix ...
### Spec compliance
- FR-005 empty-input case now covered by line 67 (commit abc123)
- ...

## US1 Cross Pass (agent: codex, date: 2026-04-12)
... re-review confirms fix ...
```

The first round stays visible. Flow-state and the `Overall Verdict`
always use the **latest** self+cross pair for each phase when
aggregating.

## Forbidden patterns

- No phase may have a cross-pass without a preceding self-pass
- No phase's cross-pass may have the same agent as its self-pass
- `## Overall Verdict` MUST NOT be written before all declared
  user stories have both self-pass and cross-pass
- Self-pass agents MUST NOT be the string `user` or `human` — the
  self-pass is for the agent that wrote the code, and human review
  is not a self-pass in this model

## Invariants

- Artifact is valid only if `# Review: Code` exists as the top
  heading
- Every `## <phase> Self Pass` MUST be followed by a corresponding
  `## <phase> Cross Pass` with a different agent (or the phase is
  not yet complete, in which case `Overall Verdict` MUST NOT exist)
- `## Overall Verdict` MUST NOT exist without the full phase
  coverage above
- Phase names MUST match a user story name from `tasks.md` —
  `Overall` is NOT a valid phase name (it is reserved for the
  `## Overall Verdict` section which has a different shape)
- `status` in `Overall Verdict` MUST be one of the three enum values
- Cross-pass subsection body MUST cover all four required
  subheadings (spec compliance, implementation quality, test
  coverage, regression risk)

## Flow-state interpretation

`flow_state.py` reads `review-code.md` and produces:

```python
{
    "review_code_status": "not_started" | "phases_partial" | "overall_complete" | "invalid",
    "phases_reviewed": [
        {
            "phase": "US1",
            "self_pass_agent": "claude",
            "self_pass_date": "2026-04-11",
            "cross_pass_agent": "codex",
            "cross_pass_date": "2026-04-11",
        },
        ...
    ],
    "overall_verdict": "ready-for-pr" | "needs-fixes" | "blocked" | None,
    "latest_pass_date": "2026-04-12",
}
```

The `review_code_status` is `overall_complete` only when every
user story declared in `tasks.md` has both a self-pass and a
cross-pass, AND `## Overall Verdict` exists.

## Supersedes

This contract supersedes the portions of
`specs/006-orca-review-artifacts/` that defined the old
`review-code.md` and `review-cross.md` shapes. It consolidates
self-review's code-review function (the "did I build what the
spec said?" part) into this artifact's Self Pass subsection;
self-review's process-retro function moves to `review-pr.md`.
