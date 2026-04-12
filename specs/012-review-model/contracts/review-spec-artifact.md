# Contract: `review-spec.md` Artifact

**Status**: Draft
**Parent**: [012-review-model plan.md](../plan.md)

Defines the durable shape of a `review-spec.md` file — the
adversarial review of a clarified spec. `review-spec` is
**cross-only**: there is no self-pass because `speckit.clarify`
already handles the author-facing sharpening loop.

## Location

One `review-spec.md` per feature, living in the feature directory
alongside `spec.md`:

```text
specs/NNN-<slug>/
├── spec.md
├── review-spec.md   ← this artifact
├── plan.md
├── ...
```

## Required sections

Every valid `review-spec.md` MUST contain these sections, in this
order, with the exact heading text shown:

### `# Review: Spec`

Top-level heading. Fixed text, not parameterized.

### `## Prerequisites`

Records the exact `speckit.clarify` session the review was run
against. Required so staleness detection can compare review age
against clarify age.

Required bullet:
- `- Clarify session: YYYY-MM-DD`

The date must match the latest `### Session` subheader inside
`spec.md`'s `## Clarifications` section at review time. If
multiple sessions exist, `review-spec` MUST target the most recent.

Missing prerequisites block or missing date → artifact is
**invalid** and treated by flow-state as not present.

### `## Cross Pass (agent: <name>, date: YYYY-MM-DD)`

The adversarial review pass itself. The heading is parameterized
with the agent identifier (e.g., `claude`, `codex`, `gemini`) and
the date the pass was run. Multiple cross-pass subsections are
allowed (e.g., if a downgrade retry happened per the cross-pass
agent routing policy); each is a separate `## Cross Pass (...)`
heading.

The agent identifier MUST be different from the agent that
authored `spec.md`. This is enforced by matriarch's cross-pass
agent routing policy (see [cross-pass-agent-routing.md](./cross-pass-agent-routing.md)).

### Cross Pass body structure

Inside each `## Cross Pass` section, the body MUST cover the five
categories that are out of `speckit.clarify`'s scope (per the
clarify integration contract). Recommended subheadings:

```markdown
## Cross Pass (agent: codex, date: 2026-04-11)

### Cross-spec consistency
- ...

### Feasibility / tradeoff
- ...

### Security / compliance
- ...

### Dependency graph
- ...

### Industry-pattern comparison
- ...
```

Each subheading is required. A pass that declares "no findings"
for a category MUST still include the subheading with a single
bullet indicating this (e.g., `- No cross-spec conflicts found.`).
Omitting a subheading is interpreted as **pass not run** for that
category and the artifact is flagged as incomplete.

**Exception: TIMEOUT-only cross-pass entries.** When a cross-pass
times out before completing (per Rule 3 of the cross-pass agent
routing contract), the recorded timeout entry is allowed to omit
the five category subheadings entirely. The body instead contains
only the single line `TIMEOUT: review did not complete within
runtime budget`. A TIMEOUT-only entry is valid on its own because
it represents a run that never produced category findings in the
first place; the completed retry cross-pass (a separate
subsection) carries the five required subheadings.

### `## Verdict`

Final judgment on the review. Required fields:

- `- status: ready | needs-revision | blocked`
- `- rationale: <one-paragraph summary>`
- `- follow-ups: <bulleted list or "none">`

`status` must be one of the three enum values:

- **`ready`**: spec is approved to advance to plan/implement
- **`needs-revision`**: spec needs updates, author re-runs
  `speckit.clarify` and then re-requests review
- **`blocked`**: spec cannot advance without external input or a
  non-review decision

## Append-only WITHIN a single review cycle; file-replace ACROSS cycles

The file has two different append/replace behaviors depending on
what triggered the new pass:

**Within a single review cycle (timeout-downgrade retry):** if
the cross-pass routing policy triggers a downgrade retry
(e.g., Tier-1 agent timed out, the next agent ran the retry), the
retry is **appended** as a new `## Cross Pass` subsection, not
overwriting the first. The verdict is computed from the most
recent non-TIMEOUT pass, but the timeout and retry history stays
visible in the same file.

**Across review cycles (author revised spec, fresh review
requested):** if the author updates `spec.md` after a
`needs-revision` verdict (typically by re-running
`speckit.clarify` and getting a newer `### Session YYYY-MM-DD`),
the previous `review-spec.md` becomes **stale** and is
**overwritten** with a fresh review. The previous review's
content is not preserved in-file; git history is the historical
record. This matches the quickstart walkthrough's "written fresh
(it's stale, the old one is superseded)" language.

Staleness is detected by comparing `## Prerequisites` clarify
session date against the latest `### Session` subheader in
`spec.md`; a stale file MUST be overwritten, not appended to.

Example of the timeout-retry case (append within a single cycle).
The spec was authored by a non-`codex` agent in this scenario, so
the downgrade target `gemini` still satisfies the
different-agent-from-author rule:

```markdown
# Review: Spec

## Prerequisites
- Clarify session: 2026-04-11

## Cross Pass (agent: codex, date: 2026-04-11)
TIMEOUT: review did not complete within runtime budget

## Cross Pass (agent: gemini, date: 2026-04-11)
### Cross-spec consistency
- No cross-spec conflicts found.
### Feasibility / tradeoff
- ...
### Security / compliance
- ...
### Dependency graph
- ...
### Industry-pattern comparison
- ...

## Verdict
- status: ready
- rationale: Review completed successfully on retry after initial codex timeout.
- follow-ups: none
```

## Forbidden sections

A `review-spec.md` MUST NOT contain:

- `## Self Pass` — `review-spec` is cross-only by design
- Any clarifying questions — if the reviewer thinks clarify
  missed something, the correct response is to request a clarify
  re-run, not to ask the author here
- Any edits to `spec.md` — `review-spec` is read-only against
  the spec

## Invariants

- Artifact is valid only if all three top-level sections
  (`## Prerequisites`, at least one `## Cross Pass`, `## Verdict`)
  are present with the exact heading text
- Every `## Cross Pass` MUST name the agent inline in its heading
- Verdict status MUST be one of the three enum values
- Multiple `## Cross Pass` sections MUST NOT reuse the same agent
  name unless at least one timed out (downgrade retry case)
- `## Prerequisites` MUST reference a clarify session that exists
  in the target `spec.md`

## Flow-state interpretation

`flow_state.py` reads `review-spec.md` and produces:

```python
{
    "review_spec_status": "present" | "missing" | "invalid" | "stale",
    "verdict": "ready" | "needs-revision" | "blocked" | None,
    "latest_cross_pass_agent": str | None,
    "latest_cross_pass_date": str | None,
    "clarify_session_referenced": str | None,
    "stale_against_clarify": bool,  # True if clarify ran again after this review
}
```

The `stale_against_clarify` flag is set when `spec.md`'s
`## Clarifications` section contains a `### Session` subheader
with a date later than the `## Prerequisites` clarify session in
`review-spec.md`.

## Supersedes

This contract supersedes the portions of
`specs/006-orca-review-artifacts/` that defined the old
`review-cross.md` shape. The 006 contract is marked
`Superseded by 012-review-model` in the 012 implementation wave.
