# Data Model: 012 Review Model

**Status**: Draft
**Parent**: [plan.md](./plan.md)

Entities, relationships, and field-level definitions for the
three-review artifact model. Derived from the five contract files
under `contracts/`. This document is the canonical
cross-reference for runtime code that constructs, reads, or
validates review artifacts.

---

## Entity: `Review Spec Artifact`

**Description**: The durable adversarial review of a clarified
feature spec. Always cross-mode. One per feature.

**File**: `specs/<NNN-slug>/review-spec.md`
**Contract**: [review-spec-artifact.md](./contracts/review-spec-artifact.md)

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `prerequisites.clarify_session` | date (YYYY-MM-DD) | yes | `## Prerequisites` section |
| `cross_passes` | list[`Cross Pass Entry`] | at least 1 | parsed `## Cross Pass (...)` sections |
| `verdict.status` | enum (`ready`, `needs-revision`, `blocked`) | yes | `## Verdict` status field |
| `verdict.rationale` | string (one paragraph) | yes | `## Verdict` rationale field |
| `verdict.follow_ups` | list[string] or "none" | yes | `## Verdict` follow-ups field |

### Relationships

- References exactly one `spec.md` in the same feature directory
- Prerequisites date MUST reference a `### Session` subheader in
  that `spec.md`'s `## Clarifications` section
- Optionally references downstream specs in cross-spec consistency
  findings (not tracked as a formal relationship; free text in
  cross-pass body)

### Invariants

- Always cross-mode only; no self-pass subsection allowed
- Multiple `## Cross Pass` subsections within the same file are
  allowed only for timeout-downgrade retries in a single review
  cycle. After an author revises `spec.md` and re-runs clarify,
  the resulting re-review **replaces** (overwrites) the
  `review-spec.md` file rather than appending a new cross-pass.
  See the "Append-only WITHIN, file-replace ACROSS" section in
  `review-spec-artifact.md` for the exact mechanism
- Verdict status is one of exactly three enum values

---

## Entity: `Review Code Artifact`

**Description**: The durable review of implementation work,
covering both self-pass and cross-pass modes across user-story
phases.

**File**: `specs/<NNN-slug>/review-code.md`
**Contract**: [review-code-artifact.md](./contracts/review-code-artifact.md)

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `phases` | list[`Phase Review Entry`] | at least 1 | parsed `## <phase> Self Pass` and `## <phase> Cross Pass` sections |
| `overall_verdict.status` | enum (`ready-for-pr`, `needs-fixes`, `blocked`) | yes when all phases complete | `## Overall Verdict` status |
| `overall_verdict.rationale` | string | yes when present | `## Overall Verdict` rationale |
| `overall_verdict.follow_ups` | list[string] or "none" | yes when present | `## Overall Verdict` follow-ups |

### Relationships

- References exactly one `tasks.md` in the same feature directory
- Each phase name matches a user story in `tasks.md` (`Overall`
  is NOT a valid phase name — it is reserved for the dedicated
  `## Overall Verdict` section)
- Each cross-pass references the matching self-pass by phase name
- Self-pass agent and cross-pass agent in the same phase MUST be
  different

### Invariants

- Append-only across review rounds — old passes are NEVER
  overwritten, only augmented
- Every phase has a self-pass before a cross-pass
- `## Overall Verdict` MUST NOT exist until all declared phases
  have both passes
- Cross-pass agent always differs from self-pass agent for the
  same phase (enforced by the cross-pass agent routing policy)

---

## Entity: `Phase Review Entry`

**Description**: A self+cross pair for one user-story phase inside
`review-code.md`.

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `phase_name` | string (matches `tasks.md` user story; `Overall` is NOT valid) | yes | section heading |
| `self_pass.agent` | string (agent id) | yes | `## <phase> Self Pass (agent: ...)` |
| `self_pass.date` | date | yes | inline in Self Pass heading |
| `self_pass.body` | structured (spec compliance, impl quality, test coverage, regression risk) | yes | Self Pass body |
| `cross_pass.agent` | string (agent id, != self_pass.agent) | yes | `## <phase> Cross Pass (agent: ...)` |
| `cross_pass.date` | date | yes | inline in Cross Pass heading |
| `cross_pass.body` | structured (same four subsections, adversarial framing) | yes | Cross Pass body |
| `cross_pass.timed_out` | bool | no | inferred from body containing `TIMEOUT:` marker |

### Invariants

- `self_pass` exists before `cross_pass` chronologically and
  textually (the Self Pass section appears before its matching
  Cross Pass in the file)
- `self_pass.agent != cross_pass.agent`
- Both passes declare all four required body subsections
  (spec compliance, impl quality, test coverage, regression risk)

---

## Entity: `Review PR Artifact`

**Description**: The durable record of external PR comment
processing plus a required one-paragraph process retrospective.

**File**: `specs/<NNN-slug>/review-pr.md`
**Contract**: [review-pr-artifact.md](./contracts/review-pr-artifact.md)

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `pr_identifier.repository` | string (`<owner>/<repo>`) | yes | `## PR Identifier` |
| `pr_identifier.number` | positive integer | yes | `## PR Identifier` |
| `pr_identifier.opened` | date | yes | `## PR Identifier` |
| `comments` | list[`PR Comment Entry`] | 0 or more | `## External Comments` |
| `retro_note` | string (one paragraph, allowed empty placeholder) | yes | `## Retro Note` body |
| `verdict.status` | enum (`merged`, `pending-merge`, `reverted`) | yes | `## Verdict` status |
| `verdict.merged_at` | date | required iff status=`merged` | `## Verdict` merged-at |
| `verdict.notes` | string | no | `## Verdict` notes |

### Relationships

- References exactly one GitHub PR by `pr_identifier.number` in
  the named repository
- Each `PR Comment Entry` references a specific comment in that
  PR, optionally with a commit sha linking to the fix

### Invariants

- `## Retro Note` section exists even when body is the literal
  sentence "No workflow changes needed this cycle."
- `verdict.merged_at` is present iff `verdict.status == "merged"`
- Comments may be appended across multiple "rounds" (new comment
  rounds after a round of fixes) — the round structure is
  optional, and the comment list is append-only across rounds

---

## Entity: `PR Comment Entry`

**Description**: A single external PR comment plus its
disposition.

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `id` | string (matches GitHub comment id) | yes | `Comment #<id>` |
| `reviewer` | string | yes | inline in bullet |
| `date` | date | yes | inline in bullet |
| `thread` | string (short quote or summary) | yes | `thread:` sub-bullet |
| `disposition` | enum (`addressed`, `rejected`, `deferred`) | yes | `disposition:` sub-bullet |
| `response` | string | required iff disposition != `addressed` | `response:` sub-bullet |
| `commit` | sha | required iff disposition == `addressed` | `commit:` sub-bullet |

### Invariants

- Disposition values are exactly three enum strings, no others
- Every `rejected` or `deferred` comment has a response
- Every `addressed` comment has a commit sha pointing at a real
  commit in the PR's history

---

## Entity: `Cross Pass Entry`

**Description**: One cross-pass inside a `review-spec.md` or
`review-code.md` artifact. Distinct from `Phase Review Entry`
(which pairs self+cross for one phase in review-code).

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `agent` | string | yes | `## Cross Pass (agent: ...)` heading |
| `date` | date | yes | inline in Cross Pass heading |
| `artifact_kind` | enum (`review-spec`, `review-code`) | yes | which artifact the entry came from |
| `phase_name` | string | required for `review-code` | matches Phase Review Entry |
| `body_subsections` | list[subsection name] | see contract | parsed from body |
| `timed_out` | bool | no | `TIMEOUT:` marker in body |

---

## Entity: `Cross-Pass Agent Routing Decision`

**Description**: The output of matriarch's
`select_cross_pass_agent` function. Not a durable artifact but a
runtime value that gets recorded into review artifacts.

**Contract**: [cross-pass-agent-routing.md](./contracts/cross-pass-agent-routing.md)

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `selected_agent` | string | yes | return value |
| `tier` | int (1-3) | yes | derived from agent's tier in 003 model |
| `excluded` | list[string] | yes | author agent + all previously-tried agents in this review cycle |
| `reason` | enum (`normal`, `downgrade`) | yes | `normal` on first attempt, `downgrade` on retry |

### Invariants

- `selected_agent` is never in the `excluded` list
- `selected_agent` is always tier-preferred (highest tier possible
  given exclusions)
- `reason == "downgrade"` implies at least one agent was tried and
  timed out before this selection

---

## Entity: `Review Milestone` (flow-state view)

**Description**: Flow-state's summary view of all three review
artifacts for a single feature. Not a durable artifact; computed
on demand from the three artifact files plus `spec.md`'s
`## Clarifications` section.

### Fields

| Field | Type | Required | Source |
|---|---|---|---|
| `review_spec_status` | enum (`missing`, `present`, `invalid`, `stale`) | yes | parsed from review-spec.md |
| `review_code_status` | enum (`not_started`, `phases_partial`, `overall_complete`, `invalid`) | yes | parsed from review-code.md |
| `review_pr_status` | enum (`not_started`, `in_progress`, `complete`, `invalid`) | yes | parsed from review-pr.md |
| `overall_ready_for_merge` | bool | yes | computed: all three statuses are their terminal values |

### Relationships

- Derived from `Review Spec Artifact`, `Review Code Artifact`,
  `Review PR Artifact`, and `spec.md`'s `## Clarifications`
- Consumed by matriarch's lane readiness aggregation
- Consumed by the yolo runtime (014) for decision logic

### Invariants

- `overall_ready_for_merge` is `True` only when:
  - `review_spec_status == "present"` AND not stale
  - `review_code_status == "overall_complete"` with verdict `ready-for-pr`
  - `review_pr_status == "complete"` with verdict `merged`
- Stale `review-spec` blocks `overall_ready_for_merge` even if
  verdict was `ready` at review time

---

## Cross-entity relationships diagram

```text
spec.md
  ├── ## Clarifications (owned by speckit.clarify)
  │     └── ### Session YYYY-MM-DD
  │           └── Q: ... → A: ...
  │
  └── review-spec.md (cross-only)
        ├── ## Prerequisites
        │     └── Clarify session: YYYY-MM-DD  ← references session in spec.md
        ├── ## Cross Pass (agent: ...)
        │     └── five body subsections
        └── ## Verdict

tasks.md
  └── review-code.md (append-only across phases)
        ├── ## US1 Self Pass (agent: A)
        │     └── four body subsections
        ├── ## US1 Cross Pass (agent: B)  ← B != A, routed by matriarch
        │     └── four body subsections
        ├── ## US2 Self Pass (agent: C)
        ├── ## US2 Cross Pass (agent: D)  ← D != C
        └── ## Overall Verdict

<GitHub PR>
  └── review-pr.md
        ├── ## PR Identifier
        ├── ## External Comments
        │     └── Comment #N (reviewer, disposition, optional commit)
        ├── ## Retro Note (process retrospective, allowed empty)
        └── ## Verdict (merged | pending-merge | reverted)
```

---

## Vocabulary migration

Old vocabulary (from 006 and current runtime) → new vocabulary
(012):

| Old | New | Notes |
|---|---|---|
| `code-review.md` | `review-code.md` Self Pass subsections | Self Pass replaces the old code-review file |
| `review-cross.md` | `review-code.md` or `review-spec.md` Cross Pass subsections | Cross-mode folded into artifact subsections |
| `review-pr.md` | `review-pr.md` (same filename, different scope) | Narrowed to comment disposition + retro |
| `self-review.md` | Split between `review-code.md` Self Pass subsections and `review-pr.md` Retro Note | Code-self-check content moves to review-code Self Pass; process retrospective moves to review-pr Retro Note |
| `review.md` | `review.md` (unchanged as umbrella summary) | Points at the three artifact files |

Runtime code that used to grep for `review-code.md`, `review-cross.md`,
`review-pr.md`, `self-review.md` now greps for `review-spec.md`,
`review-code.md`, `review-pr.md`. Three files, not four-plus-umbrella.

## Open questions (tactical, for implementation task)

1. Should the parsers be hand-written (simple regex + section
   splitter) or use a real Markdown AST library? My lean:
   hand-written with regex for now. No new dependency, simple,
   good enough for append-only structured docs. Revisit if the
   contract grows.
2. Should the `Review Milestone` flow-state view be cached in
   `.specify/orca/flow-state/` or computed fresh every time?
   Current flow-state is mostly compute-fresh. Lean: stay
   compute-fresh, no caching.
3. Should `review-code.md` support a "fast-forward" mode where a
   self-pass is allowed to skip a cross-pass for trivial
   user-stories? My lean: no — 012 explicitly rejects operator
   override of cross-pass routing. Triviality is subjective and
   this is the kind of escape hatch that erodes the
   adversarial-by-default rule.
