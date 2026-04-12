# Contract: `review-pr.md` Artifact

**Status**: Draft
**Parent**: [012-review-model plan.md](../plan.md)

Defines the durable shape of a `review-pr.md` file — the record
of external PR comment processing plus a short process
retrospective. `review-pr` is intentionally narrow: it is NOT a
full review gate. It records how PR review comments were
dispositioned and captures a one-paragraph retro note on how the
feature cycle went.

## Location

One `review-pr.md` per feature, living in the feature directory:

```text
specs/NNN-<slug>/
├── spec.md
├── review-spec.md
├── plan.md
├── tasks.md
├── review-code.md
├── review-pr.md   ← this artifact
```

Written after the PR is opened on GitHub. Can be appended to as
new comment rounds arrive.

## Required sections

### `# Review: PR Comments`

Top-level heading. Fixed.

### `## PR Identifier`

Records which PR this artifact tracks. Required fields:

- `- repository: <owner/repo>`
- `- number: <pr-number>`
- `- opened: YYYY-MM-DD`

Example:

```markdown
## PR Identifier
- repository: SteeZyT33/spec-kit-orca
- number: 42
- opened: 2026-04-11
```

### `## External Comments`

The core of the artifact. Lists each comment from external
reviewers on the PR along with how it was dispositioned. Each
comment becomes a single bullet with fixed subfields.

Required bullet shape:

```markdown
- **Comment #<id>** (reviewer: <name>, date: YYYY-MM-DD)
  - thread: <short quote or summary of the comment>
  - disposition: addressed | rejected | deferred
  - response: <one-sentence explanation, required if disposition != addressed>
  - commit: <commit-sha if addressed, omit otherwise>
```

### Disposition enum

Exactly three values:

- **`addressed`** — the comment pointed at a real issue, a fix
  was committed, and the thread was resolved
- **`rejected`** — the comment was acknowledged but intentionally
  not addressed (out of scope, disagreement with reviewer, etc.).
  REQUIRES a `response:` explaining why.
- **`deferred`** — the comment points at a real issue that will
  be handled in a follow-up PR, not this one. REQUIRES a
  `response:` naming the follow-up.

If `disposition` is `addressed`, the `response` field is optional
(the fix itself is the response) but the `commit` field is
required so the trail is auditable.

### `## Retro Note`

**Required section, allowed to contain "no notes".** This is the
forcing function that replaces the old `self-review` command's
process-retrospective function. Body is one paragraph maximum.

The content MUST answer the question *"how did this feature cycle
go, and what (if anything) should change about the workflow for
the next cycle?"*. If the operator has nothing to say, the section
body is literally the sentence `No workflow changes needed this
cycle.` — this is explicitly allowed and NOT flagged by flow-state.

Example of a non-empty retro note:

```markdown
## Retro Note

This cycle hit a snag on US2 where the cross-pass agent (codex)
timed out and the Tier-2 downgrade (claude) picked it up cleanly.
Worth tightening the cross-pass timeout budget in the orchestration
config so we trigger the downgrade earlier — roughly 3 minutes
wasted before the retry fired.
```

Example of an empty retro note:

```markdown
## Retro Note

No workflow changes needed this cycle.
```

Both are valid.

### `## Verdict`

Final PR state. Required fields:

- `- status: merged | pending-merge | reverted`
- `- merged-at: YYYY-MM-DD` (required if status is `merged`)
- `- notes: <optional one-line summary>`

The three verdict values:

- **`merged`**: PR merged successfully, comment round closed
- **`pending-merge`**: comments processed but PR not yet merged
  (waiting on CI, waiting on approval, etc.)
- **`reverted`**: PR was merged but then reverted; the artifact
  captures the revert reason in `notes:`

## Append-only across comment rounds

If the PR picks up additional comments after a first review-pr
pass, the artifact is appended:

```markdown
## External Comments

### Round 1 (2026-04-11)
- **Comment #3** (reviewer: alice, date: 2026-04-11)
  - thread: "this should use foo() not bar()"
  - disposition: addressed
  - commit: abc123

### Round 2 (2026-04-12)
- **Comment #7** (reviewer: bob, date: 2026-04-12)
  - thread: "nit: rename X"
  - disposition: deferred
  - response: will be handled in PR #45 (followup)
```

The `## Verdict` section is always updated to reflect the latest
state, not appended. Only `## External Comments` is append-only
across rounds.

## Forbidden patterns

- No field may reference code that does not exist in the PR's commit history
- `disposition: rejected` without a `response:` field is invalid
- `disposition: deferred` without a follow-up reference in the
  `response:` field is invalid
- `disposition: addressed` without a `commit:` field is invalid
- `## Retro Note` MUST exist even if the body is "no workflow changes needed this cycle"
- `## Verdict` MUST exist and MUST have a valid status enum

## Invariants

- Exactly five top-level sections: PR Identifier, External
  Comments, Retro Note, Verdict, plus the `# Review: PR Comments`
  heading
- PR number is a positive integer matching a real GitHub PR
- Every External Comments bullet has a valid disposition value
- `merged-at` is present iff `status: merged`

## Flow-state interpretation

`flow_state.py` reads `review-pr.md` and produces:

```python
{
    "review_pr_status": "not_started" | "in_progress" | "complete" | "invalid",
    "pr_number": int | None,
    "verdict": "merged" | "pending-merge" | "reverted" | None,
    "merged_at": str | None,
    "comments_by_disposition": {"addressed": 3, "rejected": 1, "deferred": 2},
    "has_retro_note": bool,  # True even if body is "no workflow changes needed"
}
```

`review_pr_status` is `complete` only when `## Verdict` exists
with a terminal status (`merged` or `reverted`). `pending-merge`
is still `in_progress`.

## Supersedes

This contract supersedes the portions of
`specs/006-orca-review-artifacts/` that defined the old
`review-pr.md` shape, AND absorbs the process-retrospective
function of the old `self-review.md`. `self-review.md` as a
standalone artifact is retired in the 012 wave.
