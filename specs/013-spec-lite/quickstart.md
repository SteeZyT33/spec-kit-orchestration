# Quickstart: 013 Spec-Lite

**Status**: Draft
**Parent**: [plan.md](./plan.md)

Walked-through example of spec-lite's lifecycle: create a record,
implement the change, optionally verify, and optionally review.
Written from the operator's point of view. Shows what the record
looks like at each stage and where the matriarch guard fires.

---

## The scenario

You're fixing a small bug in CS2 Stats Magic: the team-stats sync
job silently drops rows when the API returns a partial page. It's
a 20-line fix, not worth a full spec, but you want a durable
record of what you're doing and why.

## Step 0 — Create the spec-lite record

You run `/speckit.orca.spec-lite` (or the runtime CLI):

```bash
uv run python -m speckit_orca.spec_lite --root . create \
    --title "Fix team-stats sync partial-page drop" \
    --problem "Sync job silently drops rows when API returns a partial page" \
    --solution "Check hasMore flag and paginate until complete" \
    --acceptance "Given a 3-page API response, when sync runs, then all rows are persisted" \
    --files-affected "src/sync/team_stats.py,tests/test_team_stats.py"
```

The runtime assigns the next available ID and writes:

```text
.specify/orca/spec-lite/SL-007-fix-team-stats-sync-partial-page-drop.md
```

The file looks like this:

```markdown
# Spec-Lite SL-007: Fix team-stats sync partial-page drop

**Source Name**: operator
**Created**: 2026-04-11
**Status**: open

## Problem
Sync job silently drops rows when API returns a partial page.

## Solution
Check hasMore flag and paginate until complete.

## Acceptance Scenario
Given a 3-page API response, when sync runs, then all rows are
persisted.

## Files Affected
- src/sync/team_stats.py
- tests/test_team_stats.py
```

The overview file `00-overview.md` is automatically regenerated to
include the new record under its "Active records" section.

## Step 1 — Implement the fix

You open `src/sync/team_stats.py`, add the pagination loop, write
a test in `tests/test_team_stats.py`, verify locally, and commit.

At this point the spec-lite record is still `Status: open`.
Flow-state reports:

```python
{
    "kind": "spec-lite",
    "id": "SL-007",
    "slug": "fix-team-stats-sync-partial-page-drop",
    "title": "Fix team-stats sync partial-page drop",
    "status": "open",
    "files_affected": ["src/sync/team_stats.py", "tests/test_team_stats.py"],
    "has_verification_evidence": False,
    "review_state": "unreviewed",
}
```

## Step 2 — Mark as implemented

You update the record's status:

```bash
uv run python -m speckit_orca.spec_lite --root . update-status SL-007 implemented
```

The runtime edits the `**Status**:` line in place from `open` to
`implemented` and regenerates the overview. The record now lives
under "Implemented records" in `00-overview.md`.

## Step 3 — (Optional) Add verification evidence

If you want a durable record of your test run, you append the
optional section:

```markdown
## Verification Evidence
pytest tests/test_team_stats.py -v → 3 passed, 0 failed
Manually verified against staging API with 3-page response.
```

Flow-state now reports `has_verification_evidence: True`. This is
entirely optional — many spec-lite records skip this section and
that's fine.

## Step 4 — (Optional) Request a review

Reviews are opt-out for spec-lite. If you want one anyway, you
can run a self-review or cross-review against the record. The
review artifact lives as a sibling file:

```text
.specify/orca/spec-lite/
├── SL-007-fix-team-stats-sync-partial-page-drop.md
├── SL-007-fix-team-stats-sync-partial-page-drop.self-review.md  ← optional
└── ...
```

Flow-state updates `review_state` from `unreviewed` to
`self-reviewed` (or `cross-reviewed` if a cross-review was run).
The review format is lightweight — no five-category structure like
`review-spec`, just a free-form assessment.

Most spec-lite records will never have a review. That's by design.

## Step 5 — (Negative path) Try to register a matriarch lane

Suppose you forget that spec-lite can't anchor lanes and try:

```bash
# This will fail
uv run python -m speckit_orca.matriarch --root . register-lane --spec-id SL-007
```

The matriarch guard fires **before** `_feature_dir` resolves:

```text
MatriarchError: Cannot register lane for spec-lite record 'SL-007'.
Spec-lite does not participate in matriarch lanes in v1. Spec-lite
is a reference-only shape; if you need lane coordination,
hand-author a full spec under specs/ and register that instead.
The spec-lite record can be used as reference content when drafting
the full spec.
```

The error tells you exactly what to do: if lane coordination
matters, hand-author a full spec. The spec-lite stays as
reference content.

## Step 6 — (Growth path) Spec-lite → hand-authored full spec

Later, you realize the partial-page fix needs broader changes —
pagination affects three other sync jobs. You decide this warrants
a full spec with plan, tasks, and matriarch lane coordination.

You hand-author `specs/025-sync-pagination/spec.md` and cite the
spec-lite as context:

```markdown
# Feature Specification: Sync Pagination Overhaul

## Background
Originally tracked as spec-lite SL-007 (fix for team-stats sync
partial-page drop). That fix landed but the same pagination issue
exists in three other sync jobs. This full spec covers all four.

## References
- [SL-007](/.specify/orca/spec-lite/SL-007-fix-team-stats-sync-partial-page-drop.md) — original partial-page fix

...
```

The full spec links **back** to the spec-lite. The spec-lite does
NOT link forward (no `Promoted To` field). The relationship is
documented in the new spec, not in the old record.

Now `specs/025-sync-pagination/` can register a matriarch lane,
go through clarify, review-spec, plan, tasks, review-code — the
full ceremony. The spec-lite stays on disk as historical context
with `Status: implemented`.

## What the operator learned

- **Spec-lite is fast.** Create → implement → mark done is three
  commands (or one command + two manual edits). No ceremony.
- **Verification evidence is optional.** You can add it or not.
  Flow-state reports either way.
- **Reviews are opt-out.** Most spec-lite records never get
  reviewed. That's the point — reduced ceremony.
- **The matriarch guard catches misuse early.** If you try to
  anchor a lane on a spec-lite, you get a clear error before
  anything breaks.
- **Growth is manual.** If scope grows, you hand-author a full
  spec and cite the spec-lite. No automated promotion. This is
  intentional — spec-lite stays lite.

## What this walkthrough does NOT cover

- **Abandonment.** If the fix turns out to be unnecessary, you
  `update-status SL-007 abandoned`. The record stays on disk
  as historical context. No deletion.
- **Listing and filtering.** `spec-lite list --status open` shows
  all active records. `spec-lite list` shows everything.
  Filtering is by status only in v1.
- **Cross-review routing.** If you opt into a cross-review for a
  spec-lite, the cross-pass agent routing policy from 012 applies
  (different agent from author, tier preference, etc.). Same
  rules, lighter context.

## Validation against the contracts

Each step above conforms to the contracts under `./contracts/`:

- Step 0's record matches `spec-lite-record.md`: 3 required
  metadata fields, 4 required body sections, filename matches ID,
  lives under `.specify/orca/spec-lite/`
- Step 2's status update is a valid transition (`open` →
  `implemented`) per the status enum
- Step 3's verification evidence section matches the optional
  5th body section specification
- Step 4's review sibling file naming matches the convention
  defined in `spec-lite-record.md` (sibling file sharing the
  record ID stem)
- Step 5's matriarch guard matches `matriarch-guard.md`: fires
  before `_feature_dir`, raises `MatriarchError` with the
  expected message shape
- Step 6's hand-authored full spec correctly links back to the
  spec-lite without modifying the spec-lite record itself (no
  forward link, no `Promoted To` field)
