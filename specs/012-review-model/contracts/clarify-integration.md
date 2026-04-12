# Contract: `speckit.clarify` Integration for `review-spec`

**Status**: Draft
**Parent**: [012-review-model plan.md](../plan.md)
**Research input**: [`docs/research/speckit-clarify-integration.md`](../../../docs/research/speckit-clarify-integration.md)

---

Defines how `review-spec` delegates the author-facing sharpening
loop to upstream `github/spec-kit`'s `/speckit.clarify` command
and enforces that delegation at runtime.

## Scope split

Two different systems own two different halves of the spec-quality
problem. This contract defines the exact split.

| Owned by `speckit.clarify` (upstream) | Owned by `review-spec` (this spec) |
|---|---|
| Functional Scope & Behavior | Cross-spec consistency |
| Domain & Data Model | Feasibility / tradeoff analysis |
| Interaction & UX Flow | Security / compliance audit |
| Non-Functional Quality Attributes | Dependency graph analysis |
| Integration & External Dependencies | Industry-pattern comparison |
| Edge Cases & Failure Handling | |
| Constraints & Tradeoffs | |
| Terminology & Consistency | |
| Completion Signals | |
| Misc / Placeholders | |

Ten categories vs five. `speckit.clarify` explicitly narrows to
its 10 categories and does not touch the five `review-spec`
owns — verified in the clarify research doc on main.

## Precondition check

`review-spec` MUST refuse to run if `speckit.clarify` has not
already run on the target spec. The check is enforced at command
start, before any adversarial agent work begins.

### Enforcement

```python
spec_text = Path(spec_path).read_text(encoding="utf-8")
if "## Clarifications" not in spec_text:
    raise ReviewSpecError(
        f"review-spec requires /speckit.clarify to have run first. "
        f"No '## Clarifications' section in {spec_path}. "
        f"Run `/speckit.clarify` and answer the questions, then retry."
    )
```

More robust check (recommended):

```python
import re

spec_text = Path(spec_path).read_text(encoding="utf-8")

# Must have the ## Clarifications heading
if "## Clarifications" not in spec_text:
    raise ReviewSpecError(
        f"review-spec requires /speckit.clarify to have run first. "
        f"No '## Clarifications' section in {spec_path}. "
        f"Run `/speckit.clarify` and answer the questions, then retry."
    )

# Must have at least one ### Session YYYY-MM-DD subheader *inside* the
# Clarifications section specifically — a rogue Session heading under some
# other section (changelog, history, etc.) must NOT satisfy the check.
clarifications_match = re.search(
    r"^## Clarifications\b(.*?)(?=^## |\Z)",
    spec_text,
    re.MULTILINE | re.DOTALL,
)
clarifications_body = clarifications_match.group(1) if clarifications_match else ""

session_pattern = re.compile(r"^### Session \d{4}-\d{2}-\d{2}\b", re.MULTILINE)
if not session_pattern.search(clarifications_body):
    raise ReviewSpecError(
        f"review-spec requires at least one completed /speckit.clarify session. "
        f"Found '## Clarifications' heading in {spec_path} but no '### Session' "
        f"subheaders inside that section. Run `/speckit.clarify` and answer the "
        f"questions, then retry."
    )
```

The robust check guards against a stub `## Clarifications` heading
that was manually added without actually running clarify.

## Scope enforcement

`review-spec`'s command prompt (written later, in the deferred
prompt-rewrite task) MUST explicitly instruct the cross-pass
agent to **not** re-ask questions already covered by clarify's 10
categories.

The prompt MUST include a section like:

```text
## Scope boundaries

speckit.clarify has already run on this spec. You can see the
Q&A history in the `## Clarifications` section. **Do not re-ask
any of those questions.** Clarify owns the following 10 categories
and you should trust its coverage:

1. Functional Scope & Behavior
2. Domain & Data Model
3. Interaction & UX Flow
4. Non-Functional Quality Attributes
5. Integration & External Dependencies
6. Edge Cases & Failure Handling
7. Constraints & Tradeoffs
8. Terminology & Consistency
9. Completion Signals
10. Misc / Placeholders

Your scope is the five categories clarify does NOT cover:

1. Cross-spec consistency — compare this spec against sibling
   specs in `specs/` for contradictions
2. Feasibility / tradeoff analysis — audit whether the spec is
   implementable within its declared constraints
3. Security / compliance audit — threat models, attack surfaces,
   regulatory gaps, data-handling compliance
4. Dependency graph analysis — external APIs, version conflicts,
   breaking-change exposure, upstream reliability
5. Industry-pattern comparison — is this approach unusual, and
   have alternative patterns been considered?
```

Strict adherence to the scope boundary is what makes the
delegation clean. If `review-spec` starts re-asking clarify-owned
questions, the two systems begin duplicating work and the
division of labor collapses.

## Staleness detection

If `speckit.clarify` runs **again** after a `review-spec` pass
has completed, the review-spec artifact is **stale** — the verdict
no longer reflects the current clarified spec state.

### Mechanism

`review-spec.md`'s `## Prerequisites` section records the latest
`### Session` date from `spec.md`'s `## Clarifications` at review
time:

```markdown
## Prerequisites
- Clarify session: 2026-04-11
```

Staleness is detected by comparing this date against the current
latest session date in `spec.md`. If the current latest is newer,
the review is stale.

### Enforcement location

Staleness is a **flow-state concern**, not a matriarch concern.
`src/speckit_orca/flow_state.py`'s review-milestone interpretation
MUST include a `stale_against_clarify` field in its output for
`review-spec`:

```python
{
    "review_spec_status": "present" | "missing" | "invalid" | "stale",
    "verdict": "ready" | "needs-revision" | "blocked" | None,
    "clarify_session_referenced": "2026-04-11",
    "clarify_session_current": "2026-04-12",
    "stale_against_clarify": True,
}
```

When `stale_against_clarify` is `True`, flow-state reports the
review as stale even if its own verdict is `ready`. Matriarch's
lane readiness consumer MUST NOT count a stale review as
satisfying the review-spec gate.

## Interaction with `/speckit.clarify` output

### What clarify writes

Per the research doc, `speckit.clarify` modifies `spec.md` in
place with:

- `## Clarifications` top-level heading (created if absent, not
  duplicated on subsequent runs)
- `### Session YYYY-MM-DD` subheader (one per clarify run, new
  session for each re-run)
- `- Q: <question> → A: <answer>` bullets inside each session

It also writes inline updates into the relevant spec sections
(Functional Requirements, Data Model, etc.) as clarifications
resolve specific questions.

### What review-spec expects

`review-spec` reads the **entire** `spec.md` including the
inline updates. The `## Clarifications` section is primarily a
staleness marker and an audit trail, not the source of truth.

The source of truth for *what has been clarified* is the spec
itself — the inline updates are authoritative. `review-spec`
should read the whole spec when performing its five categories of
analysis, not just the `## Clarifications` section.

## Invariants

- No `review-spec.md` artifact is valid without a
  `## Prerequisites` block that references a clarify session date
  present in the target `spec.md`
- `review-spec` command start MUST fail fast if clarify has not
  run (before any agent cost is incurred)
- Flow-state MUST flag a review-spec as stale whenever its
  clarify session date is older than the current latest clarify
  session in the spec
- Matriarch lane readiness MUST NOT treat a stale review-spec as
  satisfying the review gate

## Anti-scope

Things `review-spec` MUST NOT do, even when they seem in-scope:

1. **Do not ask new clarifying questions.** If the reviewer
   thinks clarify missed something, the correct response is to
   request a clarify re-run, not to ask the author directly in
   the review artifact.
2. **Do not edit the spec.** `review-spec` is read-only against
   the spec. Any content changes come from the author responding
   to the verdict and optionally re-running clarify.
3. **Do not second-guess clarify's coverage.** If clarify's scan
   marks a category as Complete, `review-spec` trusts it. The
   review's job is the 5 items clarify cannot reach, not to
   retread its 10 categories.
4. **Do not propose implementation details.** That is the plan
   stage's job. `review-spec` operates on the spec, not the plan.

## Open questions (tactical, for command-prompt task)

1. Should the precondition check also verify that the spec has
   been updated *since* the last clarify session? (Edge case: a
   stub `## Clarifications` heading manually inserted.) My lean:
   the robust check already covers this via the `### Session`
   subheader requirement.
2. Should `review-spec` surface the clarify Q&A content in the
   adversarial agent's prompt as explicit context, or trust the
   agent to find it? My lean: include the `## Clarifications`
   section verbatim as context so the agent can check whether a
   finding was already answered.

## Supersedes

This contract is new in 012. It does not supersede an existing
contract, but it constrains the behavior of the future
`commands/review-spec.md` prompt and the future
`src/speckit_orca/review_spec.py` runtime (if one is built).
