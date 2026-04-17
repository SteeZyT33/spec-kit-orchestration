---
description: Brownfield intake for existing features. Creates a single-file adoption record with summary, location, and key behaviors. Reference-only — never reviewed, not drivable by yolo, cannot anchor a matriarch lane.
handoffs:
  - label: Full Spec For This Area
    agent: speckit.specify
    prompt: The area covered by this adoption record needs a full spec for new work
  - label: Supersede With Full Spec
    agent: speckit.orca.adopt
    prompt: A full spec has been authored that replaces this adoption record — run supersede
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

`adopt` is Orca's brownfield intake — it registers existing features that
predate Orca so flow-state can report on them and matriarch can reason
about work adjacent to them. Adoption records are reference-only: they
describe what already exists, not work being done.

Use `adopt` when: the codebase has features built before Orca that need
a durable record. Use `spec-lite` for small NEW work. Use the full spec
path for substantial new features.

## Workflow Contract

- Create, inspect, supersede, or retire adoption records under
  `.specify/orca/adopted/`.
- Do not start implementation against an adoption record — ARs describe
  existing code, not planned work.
- Do not register matriarch lanes against adoption records (the guard
  rejects them).
- Do not run reviews against ARs. `review_state` is hard-coded to
  `"not-applicable"` — there is nothing to review.
- If the operator needs coordination on an area an AR covers,
  recommend hand-authoring a full spec under `specs/` and citing the AR
  as context.

## Outline

1. **Determine the action** from the user input:
   - "adopt this feature" / "register <name>" → create a new AR
   - "list" / "show adopted" → list records
   - "supersede AR-NNN with <spec-id>" → supersede flow
   - "retire AR-NNN" → retirement flow
   - Naming a specific AR ID → inspect that record

2. **For new records**, gather:
   - **Title**: short name for the feature (e.g., "CLI entrypoint")
   - **Summary**: 1-3 sentences describing what the feature does
   - **Location**: file paths or module names where the feature lives
     (at least one)
   - **Key Behaviors**: observed behaviors as bullet points (at least one)
   - **Known Gaps** (optional): what's missing, unreviewed, or not yet
     Orca-managed

   Then create the record:

   ```bash
   uv run python -m speckit_orca.adoption --root <repo> create \
       --title "..." \
       --summary "..." \
       --location "src/foo/bar.py" \
       --location "src/foo/baz.py" \
       --key-behavior "Does X when invoked with Y" \
       --key-behavior "Loads config from Z on startup"
   ```

   The runtime auto-populates `Adopted-on` (today) and `Baseline Commit`
   (HEAD SHA). Pass `--no-baseline` to omit the commit field, or
   `--baseline-commit <sha>` to pin a specific value.

3. **For supersession**, the operator has already authored a full spec
   under `specs/<spec-id>/`. Run:

   ```bash
   uv run python -m speckit_orca.adoption --root <repo> supersede <ar-id> <spec-id>
   ```

   This validates that `specs/<spec-id>/spec.md` exists (rejects if
   not), writes `## Superseded By` into the AR, updates
   `Status: superseded`, and regenerates the overview.

4. **For retirement** (feature removed from the codebase):

   ```bash
   uv run python -m speckit_orca.adoption --root <repo> retire <ar-id> --reason "Removed in v3.0"
   ```

   Without `--reason`, no `## Retirement Reason` section is written —
   `Status: retired` is the signal. The AR file stays on disk as
   historical record.

5. **For inspection**, use flow-state on the record file:

   ```bash
   uv run python -m speckit_orca.flow_state .specify/orca/adopted/<id>.md
   ```

   Or list all records:

   ```bash
   uv run python -m speckit_orca.adoption --root <repo> list
   uv run python -m speckit_orca.adoption --root <repo> list --status superseded
   ```

6. **Output a concise summary** to the user:
   - Record path and ID
   - Current status and Baseline Commit (if present)
   - For new records: recommended next step (usually: "done — the
     feature is now known to Orca; proceed with other work")
   - For superseded/retired: confirm the transition and remind that
     the AR file is preserved

## Guardrails

- If the operator asks to review an AR or run yolo against one,
  explain that ARs are reference-only. `review_state: "not-applicable"`
  is a hard invariant. If they need quality gates, recommend authoring a
  full spec for the new work and running reviews against that.
- If the operator tries to register a matriarch lane against an AR,
  explain the guard rejection and direct them to author a full spec
  citing the AR.
- Do not confuse `adopt` with `spec-lite`. Spec-lite is for NEW bounded
  work. Adopt is for EXISTING features. Different shapes, different
  registries, different lifecycles.
- The `supersede` command requires the target spec to exist on disk.
  If the operator hasn't authored it yet, guide them to do so first
  (possibly via `/speckit.specify`), then come back and supersede.
- When the operator describes an existing feature to adopt, help them
  focus on **observable behaviors** and **file locations**, not on what
  should change or improve. The AR captures what IS, not what should be.
  Improvement ideas belong in a spec-lite or full spec.
- The overview file `00-overview.md` is auto-regenerated on every
  create / supersede / retire call — do not hand-edit it.
- If the operator wants to bulk-adopt many features at once, route
  them to the onboarding pipeline described in the next section.

## Bulk Onboarding (017 MVP)

For brownfield repos with many features that predate Orca, use the
onboarding pipeline instead of creating ARs one at a time. The
pipeline never mutates existing ARs; every new AR it produces goes
through the same `adoption.create_record` call documented above.

### Phases

`scan` (phase 1+2) → edit `triage.md` (phase 3) → `commit` (phase 4).

Durable artifacts land under
`.specify/orca/adoption-runs/<YYYY-MM-DD>-<slug>/`:

- `manifest.yaml` — run state, candidate list, audit trail
- `triage.md` — operator review surface (one section per candidate)
- `drafts/DRAFT-NNN-<slug>.md` — one proposed AR per candidate

### `scan` — discover feature candidates

```bash
uv run python -m speckit_orca.onboard --root <repo> scan \
    --run 2026-04-16-initial \
    --heuristics H1,H2,H3,H6 \
    --score-threshold 0.3
```

Heuristics applied (MVP): H1 directory grouping, H2 entry points
(pyproject / package.json), H3 README H2 headings, H6 git co-change
clustering. Each heuristic assigns a confidence score in [0, 1];
scores combine probabilistically when multiple heuristics fire on
the same path. Candidates below the threshold are dropped before
triage.md is written.

If a run directory with the given `--run` name already exists, the
command exits non-zero. Pick a new name or delete the directory.

### `review` — edit the triage surface

After `scan`, open `.specify/orca/adoption-runs/<run>/triage.md` in
any editor. For each `## C-NNN:` section, set the status line:

```text
- status: accept
- status: reject
- status: edit          # same as accept, signals the draft was modified
- status: duplicate-of:C-NNN
```

Edit the draft file under `drafts/DRAFT-NNN-<slug>.md` directly to
revise Summary, Location, or Key Behaviors before accepting. The
draft must pass 015's validation at commit time: non-empty Summary,
at least one Location path, at least one Key Behavior bullet.

### `commit` — write accepted drafts as real ARs

```bash
uv run python -m speckit_orca.onboard --root <repo> commit \
    --run 2026-04-16-initial
```

Reads triage.md, calls `adoption.create_record` for every accepted
draft, records the outcome in the manifest. Candidates still at
`pending` status block commit until the operator resolves them.
Per-candidate validation failures land in the manifest's `failed`
section but do not abort the run — other accepted drafts still
commit.

Pass `--dry-run` to print the planned `create_record` calls without
writing any ARs.

### `status` — run summary

```bash
uv run python -m speckit_orca.onboard --root <repo> status \
    --run 2026-04-16-initial
```

Prints phase, candidate counts, and committed/rejected/failed
totals.

### `rescan` — deferred to v1.1

Incremental rescan (discover only new candidates since the last run,
skip candidates whose paths are already covered by existing ARs) is
not shipped in the MVP. Running `rescan` prints a deferred-message
pointer. Workaround: invoke `scan --run <new-name>` for a fresh run.

### Invariants

- 017 NEVER writes under `.specify/orca/adopted/` directly. Every
  new AR goes through 015's `create_record`.
- Existing ARs are never mutated. `commit` is strictly additive.
- Every AR that lands has `Status: adopted` — there is no draft
  status in the committed registry.
- Drafts live outside the committed registry; the 015 parser does
  not walk `adoption-runs/`.
