# Implementation Plan: Brownfield v2 — Per-Project Onboarding Pipeline

**Branch**: `017-brownfield-v2` | **Date**: 2026-04-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/017-brownfield-v2/spec.md`

## Summary

Ship the MVP per-project onboarding pipeline that sits on top of
015's single-record `create_record`. Four durable phases backed by
a single on-disk manifest: discovery (walk the repo, apply
heuristics H1/H2/H3/H6, score candidates), proposal (generate one
draft AR per surviving candidate), review (operator edits
`triage.md`), and commit (read triage decisions, call 015's
`create_record` per accept). Deterministic, no LLM, no network.

017 is strictly additive. It never writes under
`.specify/orca/adopted/` directly. It never mutates an existing AR.
It never introduces a new AR `Status`. Drafts live under
`.specify/orca/adoption-runs/<run-id>/drafts/` — a directory 015's
parser does not walk.

## Technical Context

**Language/Version**: Python 3.10+ (matches the rest of
`src/speckit_orca/`)
**Primary Dependencies**: `speckit_orca.adoption` (015 runtime)
via import. No new third-party runtime dependencies; `pyproject.toml`
stays at `dependencies = []`.
**Storage**: `.specify/orca/adoption-runs/<YYYY-MM-DD>-<slug>/` per
run, with `manifest.yaml`, `triage.md`, and `drafts/`.
**Testing**: pytest; TDD red-green per sub-phase; fixture-based
end-to-end with a synthetic brownfield repo under `tmp_path`.
**Target Platform**: same repo shell as all other orca runtimes.
**Project Type**: runtime module + command-doc extension.
**Performance Goals**: SC-002 — scan+commit under 10s for a 1k-file
repo on a standard laptop.
**Constraints**: zero new dependencies, deterministic output, no
mutation of existing ARs, calls `create_record` per accept.

## Constitution Check

### Pre-design gates

1. **Provider-agnostic orchestration**: pass. 017 is a local-only
   Python runtime; no provider dependency, no network.
2. **Spec-driven delivery**: pass. spec.md + this plan land before
   implementation; contracts are deferred to a follow-up PR once
   the MVP surface stabilizes (see Project Structure below).
3. **Safe parallel work**: pass. 017 uses 015's existing advisory
   lock for each `create_record` call; no new concurrency primitive.
4. **Verification before convenience**: pass. Triage blocks commit
   until every candidate has an explicit status. No silent
   accepts.
5. **Small, composable runtime surfaces**: pass. 017 is one new
   module (`onboard.py`) that imports from 015; it does not
   re-implement record creation.

### Post-design check

The design stays constitution-aligned if:

- 017 never opens an existing AR file for write
- Every AR that lands goes through `create_record`
- The manifest is the durable single source of run state
- No network, no LLM in MVP

No constitution violations.

## Project Structure

### Documentation (this feature)

```text
specs/017-brownfield-v2/
├── brainstorm.md
├── spec.md
├── plan.md
└── tasks.md
```

Contracts are deferred to a follow-up PR. The brainstorm is dense
enough to drive the MVP; contract files grow when the surface
stabilizes past MVP.

### Source Code (repository root)

```text
src/speckit_orca/
├── adoption.py          (unchanged, 015's runtime)
└── onboard.py           (NEW — 017's runtime, imports from adoption)

tests/
└── test_onboard.py      (NEW)

commands/
└── adopt.md             (EXTENDED — scan/review/commit/rescan guidance)
```

**Structure Decision**: One new module. No new package. No new
top-level command. 017 layers on top of 015 by import.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Hand-written YAML subset parser | `dependencies = []` constraint; PyYAML would be the first runtime dep | JSON would work but breaks brainstorm's "hand-editable, spec-kit-aligned" posture; the manifest is flat enough that a ~100 LOC subset parser is tractable |
| New `.specify/orca/adoption-runs/` directory | Per-run durability across interruptions; preserves history | A shared drafts folder couples runs and loses history; a non-durable in-memory pipeline fails User Story 2 |

## Research Decisions

### 1. Manifest format — YAML subset, not JSON

Decision: write `manifest.yaml` in a small, well-defined YAML
subset that the 017 runtime both emits and parses.

Rationale:

- Hand-editable by operators in the normal course of triage.
- Matches spec-kit's surface (extension.yml).
- Avoids adding PyYAML to `dependencies`.
- Schema is shallow: scalars, lists of strings, lists of dicts of
  scalars. No anchors, aliases, multi-doc, or flow style.

Alternatives considered:

- JSON: machine-strict but ugly for hand edits.
- TOML: not widely used for this shape.
- PyYAML: first runtime dep would violate `dependencies = []`.

### 2. Triage surface — markdown, one section per candidate

Decision: `triage.md` is the canonical operator review surface.
Each candidate is a markdown section with a single `- status:`
line the parser reads back.

Rationale:

- Survives closed laptops, editor switches.
- Familiar to operators (same shape as `spec-lite`, AR).
- Parser is strict on the `- status:` line; forgiving on
  surrounding prose.

Alternatives considered:

- Interactive CLI loop: fine, but not durable. Deferred to v1.1.
- YAML field inside `manifest.yaml`: operator would edit two
  files in sync. Error-prone.

### 3. Heuristic set — H1 + H2 + H3 + H6

Decision: MVP heuristics are directory grouping (H1), entry points
(H2), README headings (H3), and git-history co-change clustering
(H6). Note on naming: the brainstorm reserved H6 for package /
import boundaries; MVP relabels "git history density" from the
brainstorm's H4 to H6 here, since H1 already captures package
boundaries structurally and the brainstorm's H4 is the more
valuable signal. Brainstorm's H5 (test co-location), H4 original
(as ordering hint), and H7 (LLM reviewer) are v1.1/v1.2.

Rationale:

- H1 covers the 80% shape. Most features live in a named
  subdirectory.
- H2 catches things H1 misses (CLI entry points that are one-file).
- H3 honors operator-authored signals when present.
- H6 catches cross-cutting features (files touched together even
  though they live in different directories).
- Determinism: all four are pure functions of repo state at a
  commit SHA.

Alternatives considered:

- Start with H1 only: under-covers CLI and cross-cutting features.
- Include all of H1–H7 at MVP: gold-plates; H4/H5 add noise on
  small repos; H7 requires an API key.

### 4. Confidence scoring — probabilistic OR, threshold 0.3

Decision: each heuristic emits a score in [0, 1]; when multiple
heuristics fire on the same candidate, scores combine via
`1 - prod(1 - s_i)` (probabilistic OR). Candidates below 0.3 are
dropped before triage.

Rationale:

- Combines signals monotonically — more heuristics firing cannot
  reduce score.
- Threshold is tunable via `--score-threshold`.
- No dependency on a weighting table per heuristic; defaults are
  H3=0.7, H2=0.6, H1=0.5, H6=0.4 — tuned in the module.

### 5. Draft shape — exactly 015's on-disk format

Decision: drafts are real-looking AR markdown files (title,
metadata, Summary, Location, Key Behaviors). The placeholder
`Status: adopted` is written so the draft is parseable by 015's
parser during commit-time validation. A banner comment at the top
of the draft marks it as uncommitted.

Rationale:

- Operators edit drafts in-place. Familiar shape.
- Commit re-reads the draft, parses it, and passes the fields to
  `create_record`.
- If the operator leaves TODO placeholders in summary or
  key-behaviors, 015's validation rejects the commit for that
  candidate with a clear error.

## Design Decisions

### 1. Onboarding manifest shape

```yaml
run_id: "2026-04-16-initial"
created: "2026-04-16T14:03:00Z"
phase: "review"  # discovery | review | commit | done
repo_root: "/abs/path/to/repo"
baseline_commit: "abc1234"
heuristics_enabled: ["H1", "H2", "H3", "H6"]
score_threshold: 0.3
candidates:
  - id: "C-001"
    draft_path: "drafts/DRAFT-001-auth.md"
    triage: "pending"  # pending | accept | reject | edit | duplicate
    duplicate_of: null  # or "C-003"
    proposed_title: "Auth"
    proposed_slug: "auth"
    paths: ["src/auth/__init__.py", "src/auth/middleware.py"]
    signals: ["H1:src/auth", "H2:entry-point:auth-cli"]
    score: 0.78
committed: []
rejected: []
failed: []
```

### 2. Triage markdown shape

```markdown
# Adoption Run — 2026-04-16-initial

Phase: review. 12 candidates. Mark each with `- status: accept |
reject | edit | duplicate-of:C-NNN`. Then run
`orca adopt commit --run 2026-04-16-initial`.

## C-001: Auth

- draft: [DRAFT-001-auth.md](drafts/DRAFT-001-auth.md)
- score: 0.78
- signals: H1:src/auth, H2:entry-point:auth-cli
- status: pending
```

Parser rules (strict):

- Exactly one section per candidate, starting with `## C-NNN:`.
- Each section MUST contain a `- status: <verb>` line. Verbs:
  `pending`, `accept`, `reject`, `edit`, `duplicate-of:C-NNN`.
- Unknown verbs or missing status line: parse error with line
  number.
- Candidates in the manifest that are absent from triage.md:
  treated as `pending`; commit blocks.
- Candidates in triage.md that are absent from the manifest:
  parse error.

### 3. Heuristic scoring

| Heuristic | Base score | Bump |
|-----------|-----------|------|
| H1 directory grouping | 0.5 | +0.1 per additional source file beyond 2, capped at +0.2 |
| H2 entry point | 0.6 | +0.1 if H1 also fires on the path |
| H3 README heading | 0.7 | +0.1 if matches a directory name |
| H6 git co-change cluster | 0.4 | +0.1 per additional distinct author in the cluster, capped at +0.3 |

Grab-bag name denylist (applied post-scoring): `utils`, `helpers`,
`common`, `lib`, `shared`, `misc`, `internal`. Candidates whose
proposed slug matches the denylist have their score multiplied by
0.3 (drops most of them below 0.3 threshold).

### 4. Commit flow

```text
read manifest.yaml
read triage.md → map candidate_id → triage verb
if any candidate is pending → exit 1 with list of pending ids
for each candidate:
  if verb == accept or verb == edit:
    parse draft at drafts/DRAFT-NNN-<slug>.md
    call adoption.create_record(
        repo_root=manifest.repo_root,
        title=draft.title,
        summary=draft.summary,
        location=draft.location,
        key_behaviors=draft.key_behaviors,
        known_gaps=draft.known_gaps,
        baseline_commit=manifest.baseline_commit,
    )
    on success: append to manifest.committed
    on AdoptionError: append to manifest.failed (continue)
  if verb == reject or verb == duplicate:
    append to manifest.rejected
write manifest.yaml with phase = done
```

## Implementation Sub-Phases

### Sub-phase A — Manifest dataclasses + file I/O

`OnboardingManifest`, `CandidateRecord`, `TriageEntry` dataclasses.
YAML subset emit + parse round-tripping. Atomic write. Tests: round
trip, unknown fields tolerated, required fields validated.

### Sub-phase B — Heuristics H1 + H2 + H3 + H6

Pure functions `repo_root → list[CandidateRecord]`. Deterministic.
Tests: fixture directory tree under `tmp_path` exercises each
heuristic in isolation plus their union.

### Sub-phase C — Proposal generator

`build_drafts(manifest, repo_root)` writes one `drafts/DRAFT-NNN-
<slug>.md` per candidate using 015's on-disk AR shape with a
`Status: adopted` placeholder and TODO markers in Summary and
Key Behaviors that force operator edits. Tests: drafts parse via
015's `parse_record`; empty summaries fail.

### Sub-phase D — Triage.md parser + commit flow

`render_triage(manifest) → str`, `parse_triage(text, manifest)`
returns `dict[candidate_id, TriageVerb]`. `commit_run(manifest,
repo_root)` reads triage, calls `create_record`, writes manifest
with audit trail. Tests: pending-blocks-commit, accept-calls-
create-record, reject-is-audited, failure-is-isolated.

### Sub-phase E — CLI integration

Add scan/review/commit/rescan subcommand guidance to
`commands/adopt.md`. No new CLI module; the `onboard.py` module
exposes a `cli_main` callable and the command prompt explains how
to invoke it via `python -m speckit_orca.onboard`.

## Verification Strategy

### Primary verification

1. Run `uv run pytest tests/test_onboard.py -v`. All tests green.
2. Run the full suite `uv run pytest --tb=short`. All tests
   green (no regression in 015, 012, 013, etc.).
3. Manually run `python -m speckit_orca.onboard scan --root <fixture>`
   against a synthetic brownfield repo and inspect the output
   manifest + drafts + triage.

### Secondary verification

1. Confirm existing AR files are untouched after a scan+commit
   cycle (mtime + content hash check in an integration test).
2. Confirm 015's advisory lock is respected — no bypass.
3. Confirm determinism by running `scan` twice on the same repo
   state and diffing the manifests.

### Cross-harness verification

After the test suite passes, run a read-only cross-harness review
via codex to surface BLOCKERs this agent missed. Address BLOCKERs
before landing. No push until green.

## Out Of Scope (Explicit)

- LLM-aided drafting and summary generation (v1.2).
- `rescan` subcommand (v1.1).
- Interactive CLI review loop (v1.1).
- H4 / H5 / H7 heuristics (later).
- Contracts as separate files (follow-up).
- Cross-repo onboarding, multi-SDD-format import, extend/audit
  commands.

## Open Questions (Deferred)

- How does `rescan` detect "extend AR-NNN" candidates? Brainstorm
  lean is path-based — defer the mechanism to v1.1.
- Should the manifest record operator identity
  (`git config user.email`)? Brainstorm lean is yes; MVP can skip
  it without regret.
- What happens if two heuristics produce identical paths and
  titles? MVP: keep both as separate candidates; operator uses
  `duplicate-of` to merge. Auto-merge is v1.1.
