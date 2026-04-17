# Brainstorm: Brownfield v2 — Per-Project Onboarding Pipeline

**Feature Branch**: `017-brownfield-v2`
**Created**: 2026-04-16
**Status**: Brainstorm (pre-plan)
**Informed by**:

- `specs/015-brownfield-adoption/` — the v1 single-record runtime
  that shipped the Adoption Record (AR) primitive: one file under
  `.specify/orca/adopted/AR-NNN-<slug>.md` per existing feature,
  created by hand, one at a time.
- Memory note `project_brownfield_adoption.md` — the original
  ranking of brownfield ideas; items 2, 3, and 4 (adoption
  manifest, import/bootstrap command, matriarch relaxation) were
  explicitly deferred out of 015's scope and form the seed of 017.
- 015 plan section 2, strawman Q4 — "Adoption manifest location:
  deferred to v2. v1 does not ship a manifest. v2 will likely
  place it at `.specify/orca/adoption.md` at registry root."
- 015 brainstorm "Deferred to v2 (per-project scope)" list:
  `adopt new --from <path>`, `adopt scan`, `adopt init` — these
  are the shape of the onboarding pipeline 017 owns.
- 015's `src/speckit_orca/adoption.py` runtime (PR #41) —
  `create_record`, `supersede_record`, `retire_record`, and the
  advisory-lock + overview regeneration machinery are the
  narrow API 017 must compose against, NOT bypass.
- `commands/adopt.md` — the operator-facing flow 017 extends.
- 016-multi-sdd-layer (brainstorm.md landed in this same PR):
  the in-flight spec for reading non-spec-kit SDD formats. 017
  must not presume 016 ships on any particular timeline; see
  section on 016 relationship.

---

## Problem

015 shipped the single-record runtime. It solves "Orca needs a
durable reference for this one pre-Orca feature" — you hand-author
summary / location / key behaviors and the AR lands cleanly in the
registry. That's the right minimum primitive. Keep it.

Single-record-at-a-time does not solve **onboarding a real
codebase**. The shape of the actual onboarding problem is
different:

- A mid-size Python/TS repo has **30–80 recognizable features**
  that predate Orca. Authoring 30+ AR records by hand, each with
  summary / location / key-behavior bullets, is a multi-day slog.
  Operators bounce off before finishing.
- The operator **doesn't know what's in the repo** well enough to
  enumerate it cold. They need the tool to propose candidates
  before they can triage. A blank `create` form asking "title?
  summary? location?" produces omissions — features get missed
  simply because the operator forgot they existed.
- **Discovery is a judgment call.** What counts as a feature?
  `src/auth/middleware.py` is probably one AR. But is every file
  under `src/utils/` a separate AR, or one AR called "utils
  infrastructure"? Operators need to see the repo's proposed
  partition and **shift boundaries** before committing records.
- **Review matters more than authoring.** The hard part isn't
  writing markdown — it's deciding "yes this is a real feature
  worth a record / no this is incidental / merge these two / rename
  that". Operators need a triage surface, not a blank form.
- **Incremental re-runs are required.** A repo onboarded today will
  grow tomorrow. The onboarding pipeline must handle "scan again,
  propose only the NEW features, leave existing ARs alone" —
  otherwise operators avoid re-running it and adoption staleness
  compounds.
- **015's manual create path is fine once you know what to write.**
  The bottleneck is upstream of that: discovery + proposal +
  triage. v2's job is to feed v1 pre-digested work, not to
  duplicate or bypass it.

The user story in plain terms:

> "I just shipped Orca into an existing Python/TS repo. The repo
> has 40-ish features I should probably record. Walking me through
> `create` for each one by hand is not going to happen. Give me a
> `scan`, let me triage a list of drafts, accept the ones that
> matter, and commit them as real ARs in one pass. Then when I
> merge a new feature next month, let me re-scan and pick up just
> the new stuff."

That's the v2 spec. This brainstorm proposes the shape.

## Proposed approach — the onboarding pipeline

Four phases. Each phase produces a **durable on-disk artifact**
that the next phase consumes. Any phase can be resumed after an
interruption (closed laptop, switched machines, next-week followup)
because the state lives in files, not memory.

### Phase 1 — Discovery

Walk the repo, emit a list of **feature candidates**. Each
candidate is a proposed unit-of-adoption: a name, a set of file
paths, and the signals that produced it (so the operator can
sanity-check). Discovery is **the biggest judgment call in the
spec** — see "Discovery heuristics" below for the detailed
breakdown. The output is a machine-readable file, not yet markdown
records.

### Phase 2 — Proposal

For each candidate, generate a **draft AR record**. The draft has
the same shape as a real AR (title, summary, location, key
behaviors) but lives under a scratch directory (not the real
registry), omits the `Status:` field entirely (015's parser only
accepts `adopted | superseded | retired`, so drafts stay
off-registry rather than introducing a new status value), and is
clearly labeled as "not yet committed". Proposal uses the
discovery signals plus code introspection (maybe LLM-aided) to
populate the fields. The operator sees real markdown they can edit,
not a form.

### Phase 3 — Review

Operator triages the drafts. For each candidate: **accept**
(commit as-is), **edit** (revise title/summary/paths/behaviors
then accept), **reject** (drop — the candidate is noise), or
**merge** (two drafts describe the same feature — fuse them). The
review surface is either (a) a CLI loop that walks drafts one at a
time, (b) a generated triage.md with checkboxes the operator edits
then the runtime reads back, or (c) both. I lean toward (b) — see
"Review surface" below — because it matches how operators already
work with markdown and survives being closed/reopened.

### Phase 4 — Commit

Accepted drafts become real AR records in `.specify/orca/adopted/`.
Commit **goes through 015's runtime** — specifically
`adoption.create_record()`. v2 does NOT write to
`.specify/orca/adopted/` directly. This is load-bearing: 015 owns
the validation, the ID allocation lock, the overview regeneration,
and the canonical render format. v2 is an authoring pipeline that
feeds v1; v1 is the storage layer. (See "Relationship to 015 v1"
below for the contract.)

### The durable artifact: the onboarding manifest

All four phases read and write a single manifest file, proposed
location:

```text
.specify/orca/adoption-runs/
├── 2026-04-16-initial/
│   ├── manifest.yaml          ← state across phases
│   ├── triage.md              ← operator's review surface
│   └── drafts/
│       ├── DRAFT-001-auth-middleware.md
│       ├── DRAFT-002-cli-entrypoint.md
│       └── ...
├── 2026-06-20-q2-rescan/
│   └── ...
└── ...
```

- One directory per onboarding **run**. A run is a discovery +
  proposal + review + commit cycle. Named by ISO date + short slug
  so you can re-run and keep the history.
- `manifest.yaml` — the state machine. Phase, candidates, drafts,
  triage decisions, commit results. Durable across sessions and
  machines (git-tracked).
- `triage.md` — operator-facing markdown with a checkbox per
  candidate. See "Review surface" below.
- `drafts/DRAFT-NNN-<slug>.md` — one draft AR per candidate. Shape
  mirrors a real AR but the leading `Status: draft` marker
  distinguishes it. The 015 parser is adjusted to recognize the
  draft prefix and ignore draft files when walking the registry —
  or simpler, drafts live under `adoption-runs/*/drafts/` which the
  015 parser never walks. The latter is cleaner. Go with the
  latter.

Yes, this means `.specify/orca/adoption-runs/` is a new top-level
directory. It sits beside `spec-lite/` and `adopted/`, both of
which are registries in their own right, and doesn't pollute the
committed-AR namespace. Manifests are valuable history: a future
operator can see "we ran the initial onboarding in April, picked
up 12 new features in June, another 4 in September."

## Discovery heuristics

This is the hard part. "What's a feature?" is genuinely
underdetermined, and heuristic choice shapes everything
downstream. Ranking candidates by strength, with a lean:

### H1 — Directory grouping (primary signal)

Top-level and second-level directories under `src/`, `lib/`,
`packages/`, `app/`, `cmd/`, etc. are the **strongest prior** for
feature boundaries. `src/auth/` is almost certainly one feature.
`src/payments/stripe/` is probably one feature (or two — stripe
subfeature of payments). A monorepo's `packages/api/` and
`packages/web/` are each a feature at minimum.

**Heuristic**: emit one candidate per directory that contains
≥2 source files and has a coherent name (not `utils`, `helpers`,
`lib`, `common` — those are grab-bags). Configurable via
`--max-depth` and `--min-files`.

**Confidence**: high. This matches how most operators think about
their own code.

### H2 — Entry points (primary signal)

Files that expose an external surface are almost always features:

- `main.py`, `cli.py`, `bin/*`, `cmd/*/main.go`
- `*.routes.ts`, `*Router.ts`, FastAPI `@router` / Flask
  `@app.route` decorator presence
- `setup.py`, `pyproject.toml` entry_points, `package.json` `bin`
  fields
- `Makefile` targets, `justfile` recipes

**Heuristic**: extract entry points, propose one candidate per
named entry point. The candidate's location defaults to the entry
file plus its direct imports (static analysis via AST — not deep
dataflow, just "files this file imports").

**Confidence**: high. Entry points are definitionally feature
surfaces.

### H3 — Module docstrings / README sections

Modules with real docstrings (`"""Auth middleware. Handles session
validation..."""`) self-identify. Top-level README sections with
H2 / H3 headings like `## Authentication` or `## Data Pipeline`
self-identify. These are **operator-authored signals** about what
the repo considers a feature.

**Heuristic**: treat long module docstrings (≥3 sentences) and
README H2s as feature-candidate seeds. Use the heading / first
sentence as the proposed title. This is the highest-precision
signal when present — operators have already named their features.

**Confidence**: high. Low recall (most repos don't have this), but
very high precision when they do.

### H4 — Git history density

Files that have been touched many times by many authors over a
long period are load-bearing. Files touched once in an initial
commit and never again are either abandoned or infrastructure
(formatter config, etc.).

**Heuristic**: for each directory candidate, compute a "feature
weight" = log(unique authors) * log(commits over last 6mo). Rank
candidates by weight. Use weight for **ordering** in triage, not
for filtering (low weight doesn't mean "not a feature" — it might
mean "done and stable"). Operator sees the heaviest features
first.

**Confidence**: medium. Useful as a signal, bad as a gate.

### H5 — Test file co-location

`tests/test_auth.py` testing `src/auth/*` is strong evidence that
auth is a feature worth recording. Conversely, a directory with
NO tests is still a feature (adoption is about what IS, not what's
tested) but maybe flag it in `Known Gaps` as "no tests found".

**Heuristic**: match test files to source files by naming
convention (`test_X.py` ↔ `X.py`; `X.test.ts` ↔ `X.ts`;
`X_test.go` ↔ `X.go`) and inject "test coverage: present/absent"
into the draft's generated metadata.

**Confidence**: medium. Good signal enhancer, weak standalone.

### H6 — Package/import boundaries

Python: distinct top-level packages (`auth/__init__.py` exists).
TS: distinct `index.ts` files. Go: distinct `package foo`
declarations. These are the language's own notion of feature
boundaries.

**Heuristic**: one candidate per language-level package boundary,
merged with H1 directory grouping.

**Confidence**: high. This is basically H1 with language-aware
filtering.

### H7 — LLM pass over the candidate list

After H1–H6 produce a candidate list, run a single LLM call with:

```text
"Here's a list of 47 candidate features with their paths and
signals. Review for: duplicates (A and B are the same feature),
misses (we missed a feature at path X), mislabels (A is really
part of B). Return adjusted list."
```

**Heuristic**: LLM is a **reviewer**, not a primary discoverer.
Feeding an LLM the whole repo and asking "find features" burns
tokens and produces hallucinated boundaries. Feeding it a
heuristic-derived list and asking "critique this" is cheap and
high-signal.

**Confidence**: medium-high as a reviewer; low as a primary
discoverer. The spec must NOT depend on LLMs for correctness —
H1–H6 must produce a usable list with no LLM. H7 is the upgrade.

### Combined

MVP: H1 + H2 + H3 (directory + entry points + docstrings). Ship
these and nothing else. They cover 80% of the real signal and are
deterministic, testable, reproducible. H4/H5 are post-MVP
enhancers. H6 is automatic when H1 is language-aware. H7 is opt-in
and requires API keys, so it's last.

The order of precedence when heuristics disagree:

1. H3 (operator-authored) wins — if the README says `## Auth`, that's
   the feature name.
2. H2 (entry points) next — entry point names override directory
   names.
3. H1 + H6 (directory + package) tie-break by being more specific
   (nested wins over top-level).
4. H4, H5 never rename — they only annotate.

## Manifest shape

`manifest.yaml` — proposed concrete shape:

```yaml
# .specify/orca/adoption-runs/2026-04-16-initial/manifest.yaml
run_id: "2026-04-16-initial"
created: "2026-04-16T14:03:00Z"
phase: "review"  # discovery | proposal | review | commit | done
repo_root: "/home/taylor/myrepo"
baseline_commit: "abc1234"  # HEAD when run started
heuristics_enabled: ["H1", "H2", "H3", "H6"]  # H4/H5/H7 opt-in
candidates:
  - id: "C-001"
    draft_path: "drafts/DRAFT-001-auth-middleware.md"
    triage: "accept"  # pending | accept | edit | reject | merge
    merge_into: null  # "C-003" if this is being merged into C-003
    proposed_title: "Auth Middleware"
    proposed_slug: "auth-middleware"
    paths: ["src/auth/middleware.py", "src/auth/sessions.py"]
    signals: ["H1:src/auth", "H2:entry-point", "H5:tests-present"]
    feature_weight: 4.2
  - id: "C-002"
    ...
committed:
  - candidate_id: "C-001"
    ar_id: "AR-005"
    ar_path: ".specify/orca/adopted/AR-005-auth-middleware.md"
    committed_at: "2026-04-16T15:12:00Z"
  - ...
rejected:
  - candidate_id: "C-002"
    reason: "grab-bag utils directory, not a feature"
merged:
  - candidate_id: "C-008"
    into: "C-005"
    at: "2026-04-16T14:45:00Z"
```

Design notes on the manifest:

- **YAML, not JSON.** Hand-editable when something breaks mid-run.
  Matching spec-kit's surface (extension.yml, manifest files).
- **Phase is authoritative** for "where am I?" The runtime reads
  this on every invocation and routes accordingly. `adopt scan`
  in the `review` phase is an error ("review in progress — finish
  or --reset").
- **Triage verb per candidate** — `pending` until the operator
  touches it. Explicit `pending` state prevents "silent accepts"
  where the operator forgets to mark something.
- **`committed` section grows over time**; it's the audit trail
  the run produces. When commit phase finishes, this is the list
  of real ARs that got written.
- **Baseline commit** lets re-scan know what changed since last
  run (see Incremental runs below).
- **Heuristics enabled** recorded so a re-run with different
  heuristics is visibly different (not a silent behavior change).
- **No secrets.** The manifest is git-tracked by default. API
  keys for LLM passes (H7) go through env vars, not the manifest.

## Review surface

Two candidates. I lean hard toward markdown + CLI hybrid.

### Option A — CLI loop

```bash
$ uv run python -m speckit_orca adopt review
[1/47] C-001: Auth Middleware
  paths: src/auth/middleware.py, src/auth/sessions.py
  signals: H1 (directory), H2 (entry point)
  feature weight: 4.2

  Preview draft? [y/N] y
  <renders DRAFT-001-auth-middleware.md>

  [a]ccept / [e]dit / [r]eject / [m]erge / [s]kip / [q]uit: _
```

**Pros**: interactive, linear, every candidate forced through a
decision. **Cons**: the operator has to be present for the whole
loop — 47 candidates is 30+ minutes. Closing laptop mid-loop is
awkward. Edit means "open $EDITOR on the draft, wait for
completion" — works but clunky. No at-a-glance overview.

### Option B — Triage markdown

Runtime emits `triage.md`:

```markdown
# Adoption Run — 2026-04-16-initial

47 candidates discovered. For each: mark `- [x]` to accept, strike
through with `~~` to reject, add a `-> C-NNN` to merge into another.
Edit the draft file under `drafts/` to revise the AR before
accepting.

## Candidates

- [ ] **C-001**: Auth Middleware — [draft](drafts/DRAFT-001-auth-middleware.md) — weight 4.2
- [ ] **C-002**: CLI Entrypoint — [draft](drafts/DRAFT-002-cli-entrypoint.md) — weight 3.8
- [ ] **C-003**: Data Pipeline — [draft](drafts/DRAFT-003-data-pipeline.md) — weight 3.5
- [ ] ~~**C-004**: Utils~~ — rejected (grab-bag)
- [ ] **C-005**: Payments → merge into C-001 — [draft](drafts/DRAFT-005-payments.md)
- ...
```

Operator edits this file + edits individual drafts, then runs
`orca adopt commit`. Runtime re-reads `triage.md`, parses the
checkboxes / strikethroughs / merge arrows into manifest triage
verbs, and commits accordingly.

**Pros**: survives closed laptop / switched machine. Visible at a
glance. Edit via normal file editing (any editor). Matches how
operators already work with markdown in Orca. **Cons**: parser
must be robust — fuzzy checkbox syntax, strikethrough conventions.
It can be mis-edited into an invalid state.

### Recommendation

**Ship B as primary. Add a thin A wrapper later.** The triage
markdown is the durable artifact; the CLI loop is an interactive
alternative that writes the same triage file under the hood. The
markdown is load-bearing either way.

Triage parsing rules (opinionated):

- `- [x] **C-NNN**` → accept
- `- [ ] **C-NNN**` → pending (no decision yet — block commit)
- `- [ ] ~~**C-NNN**~~` or `~~- [ ] **C-NNN**~~` → reject
- `→ merge into C-MMM` or `-> C-MMM` anywhere on the line → merge
- Line order doesn't matter; candidate ID is authoritative
- Unknown candidate IDs in triage file are a parse error (operator
  added a candidate — direct them to the manifest)
- Missing candidate IDs (exists in manifest, absent from triage) are
  implicit `pending` — commit blocks

`orca adopt commit` is a separate phase run that reads triage.md,
updates manifest.yaml, and calls `adoption.create_record()` per
accepted draft. Rejected / merged / pending candidates are skipped.

## Command surface

Extend the existing `orca adopt` CLI surface (registered as the
`speckit.orca.adopt` slash command in `extension.yml`) with new
subcommands. Do NOT rename or reshape the 015 surface; it is
stable. Throughout this spec, `orca adopt <sub>` refers to the CLI
invocation, and the slash-command namespace stays
`speckit.orca.adopt`.

### 017 commands

- **`orca adopt scan [--run <name>] [--heuristics H1,H2,...]`** —
  Phase 1 + Phase 2 combined. Walks the repo, applies heuristics,
  generates drafts, writes manifest.yaml + triage.md + drafts/.
  Defaults run name to `YYYY-MM-DD-initial` or
  `YYYY-MM-DD-<N>` for re-scans.
- **`orca adopt review [--run <name>]`** — optional interactive
  loop (the CLI option A above). Reads the same triage.md / writes
  the same triage.md. Pure wrapper.
- **`orca adopt commit [--run <name>] [--dry-run]`** — Phase 4.
  Reads triage.md, calls `adoption.create_record()` per accepted
  candidate. `--dry-run` emits the planned list without writing.
- **`orca adopt rescan [--run <name>]`** — incremental discovery.
  See "Incremental runs" below.
- **`orca adopt status [--run <name>]`** — summary of the current
  (or named) run's phase and counts.

Deferred to post-MVP (call out but don't design):

- `orca adopt import` — pull drafts from another system (OpenSpec
  archive/, raw JSON). Not MVP.
- `orca adopt diff` — compare two runs. Not MVP.

### 015 surface is unchanged

`orca adopt create|list|get|supersede|retire|regenerate-overview`
all stay identical. 017 layers ABOVE this surface, not around it.

## Relationship to 015 v1

**v2 creates the records; v1 manages them.** The contract:

1. 017 MUST call `adoption.create_record()` for every committed
   AR. It MUST NOT write files directly under
   `.specify/orca/adopted/`.
2. 017's drafts live under `.specify/orca/adoption-runs/*/drafts/`.
   The 015 parser never walks this path. Draft format mirrors AR
   shape but the canonical registry never sees a draft.
3. 017 MUST respect 015's validation. `create_record` rejects
   empty summaries, empty location lists, empty key_behaviors.
   If a draft fails validation at commit time, 017 surfaces the
   error back to the operator with a pointer to the draft file
   and blocks that candidate — but does NOT block the run. Other
   accepted candidates still commit. The manifest records the
   failure in a `failed` section alongside `committed`.
4. 017 MUST NOT bypass the advisory lock. The commit loop calls
   `create_record` one at a time; 015 handles ID allocation and
   lock acquisition per call. This means the NNN ids assigned to
   a batch of 30 accepted drafts are not guaranteed contiguous if
   concurrent `orca adopt create` ran during the commit — that's
   fine, gaps are allowed by 015.
5. 017 MUST NOT introduce a new status. Drafts are NOT a status
   on committed records. A draft is an off-registry artifact; a
   committed record has `Status: adopted` at birth, same as 015.
6. 017's manifest tracks drafts; it does NOT track live AR state.
   If an operator supersedes AR-005 next year via 015's
   `supersede` command, 017's historical manifest does not update.
   That's correct — manifests are run history, not live state.

Concretely: 017's implementation imports
`speckit_orca.adoption.create_record` (and maybe
`parse_record` for draft validation preview). It does NOT
re-implement any of that. New module would be
`src/speckit_orca/adoption_v2.py` or `src/speckit_orca/onboard.py`
— I lean toward `onboard.py` because "adoption_v2" suggests it
replaces v1, and it emphatically does not.

### Required 015 touch-ups

None, hopefully. 017 should be purely additive. The one risk is
that `create_record`'s signature is not quite rich enough for
batch callers — e.g., it always reads current HEAD for
baseline_commit, which for a batched commit might differ from the
run's baseline_commit. Fix: 017 passes explicit
`baseline_commit=<manifest.baseline_commit>` per call, using
015's existing `baseline_commit` parameter. No 015 change needed.

The other risk: 015's advisory lock serializes create calls, which
for 47 accepted drafts means 47 lock acquisitions. That's fine —
flock is cheap on local FS, and 47 ARs is not a stress case.

## Relationship to 016 multi-SDD layer

016 has its own brainstorm as of this PR, but its plan and
contracts are still open. The open question for 017: should it
scan for any spec-driven-development format (OpenSpec, spec-kitty,
raw spec-kit), or only spec-kit?

My lean: **017 scans for code, not for other SDD formats.**
Discovery is about finding features in the codebase — the files,
the entry points, the behaviors. If the repo already has OpenSpec
or spec-kitty artifacts, those describe features that may or may
not be in code yet, and blending them into discovery confuses two
different questions:

- "What features exist in this codebase?" (017's question)
- "What feature descriptions live in this repo's existing SDD
  files, and can Orca consume them?" (016's question)

Reading OpenSpec's `archive/` and pulling the descriptions into
Orca is a valid and useful feature — but it's **import**, not
**discovery**. It belongs in 016 or in a dedicated `adopt import`
command (noted in "Command surface" as deferred).

**Decision**: 017 scans code. 016, when it ships, can optionally
feed 017 by converting external SDD artifacts into Orca candidates
that 017 then triages like anything else. 017 does not block on
016. 016 does not block on 017.

If the user disagrees and wants 017 to also consume existing
spec-kit `specs/` folders (e.g., "if there's a spec, don't emit a
candidate for the same feature"), that's a narrow scope expansion
I'd accept: skip discovery for features already covered by a
`specs/NNN-*/spec.md`. Easy win, avoids duplicate records for the
subset of features that already have full specs. But reading
OpenSpec / spec-kitty / any non-spec-kit format is firmly 016.

## Incremental runs

Re-scanning after new code lands. Shape:

```bash
$ orca adopt rescan
Last run: 2026-04-16-initial (baseline abc1234)
New commits since: 42 commits across 18 files
Candidates from rescan: 5 new (C-048..C-052), 0 changed, 0 stale
Writing to: .specify/orca/adoption-runs/2026-06-20-q2-rescan/
```

Mechanics:

- Rescan is a **new run directory**, not a mutation of the prior
  run. Preserves history.
- Rescan reads the most recent completed run's manifest and
  loads the set of `committed` AR paths from there — or,
  equivalently, reads `.specify/orca/adopted/` directly. I lean
  toward reading the registry directly — it's the source of
  truth, and the manifests might be out of date if an operator
  ran `adopt retire` between runs.
- Discovery runs normally. For each candidate, check if ANY of
  its file paths are already covered by an existing AR's
  Location bullets.
  - If all paths are covered → **skip** (existing candidate, no
    rescan entry).
  - If some paths covered, some new → **flag as "extend AR-NNN"**
    (candidate with a `suggested_action: extend` marker; operator
    decides whether to update the existing AR's Location list or
    create a new sibling AR).
  - If no paths covered → **new candidate**, same as initial run.
- Rescan's `triage.md` shows new candidates grouped by kind (new
  feature, extension, unchanged). Unchanged candidates are listed
  for visibility but don't need triage decisions.
- `adopt commit` on a rescan run only commits the new candidates;
  "extend" candidates surface as a prompt to the operator to
  manually run `adopt update` (does not exist in 015 — see below)
  or hand-edit the target AR.

### The `adopt update` problem

015 explicitly has no `update` command — "edit the markdown
directly." That's fine for one-off tweaks but awkward for rescan's
"extend AR-NNN with these new paths" case. Options:

- **A. Keep 015's no-update rule.** Rescan surfaces "extend"
  candidates as operator prompts; operator hand-edits the target
  AR to add paths. Rescan itself doesn't mutate existing records.
- **B. Add `orca adopt extend <ar-id> --location <path>`** as a
  narrow 015 addition (not 017's surface). Append-only: never
  removes paths, never changes title/summary.
- **C. Let 017 do the extend under a flag.** Riskier; 017 starts
  mutating real ARs.

I lean **A** for MVP. Extend candidates are probably rare
(existing features picking up new files is the 20% case). Hand-
editing two or three ARs per quarter is fine. Revisit if demand
materializes.

### Identifying "changed" candidates

The harder question: what if a file that USED to be part of
AR-005's Location moves / splits / renames? Discovery won't
detect this automatically without a reverse index (AR paths →
candidate paths). For MVP, **don't try**. Stale Locations in
existing ARs are the operator's to clean up via normal
supersede/retire/edit flow. 017 rescan is additive only: new
candidates, flagged extensions, no detection of rot in existing
ARs.

A post-MVP `orca adopt audit` command could spot these ("AR-005
Location lists src/auth/old.py but that file was deleted") — valid
future spec, out of 017 scope.

## Downstream impact

### New files

- `src/speckit_orca/onboard.py` — main runtime. Discovery, proposal,
  triage, commit. Probably 600-1000 lines.
- `src/speckit_orca/heuristics/` — one file per heuristic (H1, H2,
  H3, H4, H5, H6, H7). Clean separation lets tests target each in
  isolation.
- `tests/test_onboard.py` — covers the pipeline end-to-end on a
  fixture repo.
- `tests/test_heuristics.py` — per-heuristic unit tests.
- `commands/adopt-scan.md`, `commands/adopt-review.md`,
  `commands/adopt-commit.md`, `commands/adopt-rescan.md` — new
  command prompts. OR: extend `commands/adopt.md` to dispatch to
  the new subcommands. The latter is cleaner — one operator-facing
  entry point, like 015. Lean toward extending `commands/adopt.md`.

### Modified files

- `commands/adopt.md` — add scan/review/commit/rescan subcommand
  guidance. Existing create/list/supersede/retire text stays.
- `src/speckit_orca/cli.py` (or wherever `adopt` subcommands
  dispatch) — register new subcommands.
- `extension.yml` — register any new slash commands (probably just
  one if we extend the existing `speckit.orca.adopt`).
- `README.md` — add "bulk onboarding" section under the brownfield
  intake topic.

### Unchanged

- `src/speckit_orca/adoption.py` — 015's runtime stays locked.
  017 imports from it.
- `.specify/orca/adopted/` — registry shape unchanged.
- `.specify/orca/spec-lite/` — unrelated, unchanged.
- 010 matriarch — ARs still never anchor lanes, guards unchanged.
- 012 review model — ARs still `review_state: not-applicable`.
- 009/014 yolo — ARs still out of yolo scope.

### New directory

- `.specify/orca/adoption-runs/` — new top-level directory under
  the orca registry root. Sits beside `adopted/` and `spec-lite/`.
  `.gitignore` considerations: tracked by default (history is
  valuable) but per-run directories can be pruned manually if
  clutter accumulates.

## Sequencing

MVP is generous here. There's a real risk of gold-plating
heuristics. Keep the discovery shallow and the pipeline coherent.

### MVP (ship as 017 v1)

1. `onboard.py` scaffolding — manifest schema, phase state
   machine, triage.md parser.
2. Heuristics **H1 + H2 + H3** only. No git history, no LLM, no
   test co-location annotation. Three heuristics, deterministic.
3. Draft generation — template-driven, no LLM. Title from H3/H2/H1
   (in precedence), summary is one stub sentence the operator
   edits, Location from paths, Key Behaviors is one "TODO: fill
   in" bullet the operator MUST edit before accepting.
4. `adopt scan` writes manifest + triage + drafts.
5. `adopt commit` reads triage, calls `create_record`.
6. `adopt status` shows counts.
7. End-to-end test on a fixture repo (dogfood spec-kit-orca).

At MVP, the operator still does real work — every draft needs
summary and key behaviors filled in. The tool removes the
**organizational** burden (what features exist, what paths,
titles, ordering) but not the **descriptive** burden (what does
each feature do). That's the right MVP — automating description
via LLM is the next iteration, not v1.

### v1.1 additions

- **Heuristic H4** (git history weight) for triage ordering.
- **Heuristic H5** (test co-location) as an annotation on drafts
  ("tests present: yes/no" in a drafted Known Gaps line).
- **`adopt review`** interactive CLI loop as an alternative to
  triage.md editing.
- **`adopt rescan`** with skip-covered-paths logic.

### v1.2 additions

- **Heuristic H7** (LLM review pass on the candidate list). Opt-in
  via `--llm-review`. Uses whatever API key is configured;
  documented as optional; MVP must work with no API access.
- **LLM-aided summary / key-behavior drafting**. Given the paths
  and imports for a feature, draft realistic summary and key
  behaviors. Operator still reviews before accepting but starts
  from real text instead of "TODO". Gated behind `--llm-drafts`.

### v2 — out of scope for 017

- `adopt audit` (find stale ARs)
- `adopt import` (consume OpenSpec or other SDD formats — depends
  on 016)
- `adopt update` / `adopt extend` (if rescan's "extend" path
  needs real support)
- LLM-generated test-coverage analysis, LLM-generated "this AR is
  out of date because the code changed" notices

## Explicit non-goals

- **Not replacing 015.** `adopt create` for single records stays
  the first-class surface for targeted adoption. 017 is bulk
  intake; 015 is surgical.
- **Not auto-committing.** Every AR that lands is the result of
  an operator decision (explicit accept in triage). No "best
  effort" silent commits.
- **Not reading non-spec-kit SDD formats.** OpenSpec / spec-kitty
  / etc. import belongs in 016 or a dedicated import command.
- **Not mutating existing ARs in rescan.** Rescan is additive.
  "Extend" candidates surface as prompts, not writes.
- **Not LLM-dependent.** MVP works with no LLM. H7 and
  LLM-drafting are opt-in enhancements, not core.
- **Not cross-repo.** One run scans one repo. Multi-repo onboarding
  is a different spec.
- **Not integrating with 010 matriarch lanes.** ARs are not lane
  anchors; 015's guard is unchanged; no touch-point or coordination
  metadata in drafts or manifests.
- **Not modifying the 015 on-disk AR format.** The drafts look
  like ARs but the committed ARs are produced by
  `create_record` and match 015's shape exactly.
- **Not introducing a `Status: draft` value.** Drafts are
  off-registry; the `Status` enum stays `adopted | superseded |
  retired`.
- **Not doing "import from git history"** as a primary discovery
  mechanism. Git is an annotator (H4), not a discoverer. Features
  live in code, not commits.
- **Not providing a web UI.** CLI + markdown triage. If someone
  wants a web surface later, that's a different spec.

## Open questions

1. **Manifest format — YAML vs JSON?** YAML is human-editable,
   comfortable for operators, matches `extension.yml`. JSON is
   stricter and tool-friendly. Lean YAML. Cost: spec-kit-orca's
   `pyproject.toml` currently declares zero runtime dependencies,
   and today's YAML-ish files (`extension.yml`,
   `scripts/bash/crossreview-backend.py`) are hand-parsed. 017
   should either keep hand-parsing a narrow YAML subset or add
   `pyyaml` as the first explicit runtime dependency. Call this
   out rather than assuming the dep is free.
2. **Where do drafts live — per-run drafts/ or a shared
   `.specify/orca/drafts/`?** Per-run is cleaner and preserves
   history. Shared is more like a Kanban "in progress" folder. Lean
   per-run. Cost: drafts don't roll forward between runs (you can't
   start drafting in run A and finish in run B), but I don't think
   operators want that.
3. **Triage.md parser robustness — strict or forgiving?** Strict
   catches typos (operator wrote `- [X]` instead of `- [x]`).
   Forgiving accepts variants. Lean strict with a clear error
   message pointing at the exact line. Undefined triage is better
   than silently-wrong triage.
4. **Should rescan reuse candidate IDs or always issue new ones?**
   C-001 in run 1 might or might not match C-001 in run 2. Safer
   to always issue fresh IDs per run and let the committed AR IDs
   be the stable reference. Lean fresh IDs per run.
5. **Baseline commit capture — run-level or candidate-level?** v1
   probably just needs run-level (all candidates share the run's
   baseline). If rescan discovers new candidates between commits,
   they still share the run's baseline. Lean run-level; v2 can add
   per-candidate if it matters.
6. **MVP heuristic choice — is H1+H2+H3 really enough?** On a
   polyglot monorepo H1 alone may over-segment. H6 (package
   boundaries) would reduce noise. Possible MVP revision: H1+H2+H3
   plus H6 for Python/TS/Go repos. Lean: add H6 to MVP if it's
   cheap (it should be — it's an AST pass per source file).
7. **Draft rendering — use the 015 renderer or a scratch template?**
   015's `_render_record` writes the canonical AR shape. Reusing
   it for drafts means drafts look EXACTLY like committed ARs,
   which aids review. Cost: drafts need a `Status: adopted`
   placeholder (015's renderer requires a real status), or 017
   needs to post-process to prepend a `DRAFT — NOT COMMITTED`
   banner. Lean: reuse 015's renderer, prepend a banner comment
   in the draft body, keep drafts visibly different.
8. **What happens if the operator deletes a draft file between
   scan and commit?** Commit phase reads the draft per candidate.
   Missing draft = error for that candidate. Lean: skip that
   candidate with a warning, don't block the run.
9. **`triage.md` dual-edit conflict** — operator edits triage.md in
   an editor, 017 rewrites triage.md after a rescan. Could clobber.
   Lean: rescan writes a NEW run directory, never touches the
   in-progress run's triage.md. (This is already the design — call
   out explicitly in contract.)
10. **Should `adopt scan` dry-run by default?** Safer default vs.
    annoying extra flag. Lean: scan writes the artifacts on first
    run (there's nothing to lose — nothing exists yet). On re-scan
    where a run directory exists, require `--force` or
    `--new-run=<name>`.
11. **Interaction with 018 Orca TUI** (brainstorm.md landed in
    this same PR, plan still open): if 018 ships a TUI, does it
    expose the triage step? Probably yes, later. Not an MVP
    question. Flag for cross-spec alignment but don't design
    around it.
12. **Discovery on huge monorepos — perf?** 50k files, H1 is fine;
    H2 parses every Python/TS/Go file for entry points, could be
    slow. MVP: single-threaded, acceptable up to ~5k source files.
    Document the limit. Threading / async is a post-MVP perf pass.
13. **Language support — which languages does MVP support for H2
    (entry points) and H6 (packages)?** Lean: Python + TypeScript
    + Go at MVP. JavaScript (non-TS) gets "treated as TS". Rust,
    Java, Swift, etc. are post-MVP.
14. **Does the manifest record operator identity?** For a solo
    repo, no; for a team repo, maybe. Lean: capture
    `git config user.email` at scan time for attribution. Cheap,
    low-risk.
15. **Interaction with `spec-lite`** — should bulk onboarding also
    propose spec-lite records for "obvious new work" like stale
    TODOs or `// FIXME`s in the code? No. That's a completely
    different scan (code-smell discovery, not feature discovery).
    Out of scope. Note for a future spec.

## Suggested next steps

1. Review this brainstorm. Sharpen or kill any of the 15 open
   questions. Especially decide: is bulk onboarding worth building
   now, or is 015 manual-per-record enough for the real use cases
   we'll hit in the next 6 months?
2. If greenlit, write `specs/017-brownfield-v2/plan.md` with:
   - MVP heuristic set (lean: H1+H2+H3, maybe H6).
   - Manifest schema (lean: YAML; commit the exact shape in a
     contract file).
   - Triage.md parser contract (lean: strict).
   - Command surface confirmed (lean: extend `commands/adopt.md`,
     don't fork it).
3. Write `specs/017-brownfield-v2/contracts/`:
   - `manifest.md` — YAML schema, phase state machine, triage
     parsing rules.
   - `discovery.md` — heuristic contract (inputs, outputs, merge
     precedence).
   - `commit-path.md` — how 017 calls into 015's
     `adoption.create_record`; error handling; batch semantics.
4. Write `specs/017-brownfield-v2/data-model.md` covering the
   Candidate / Draft / TriageDecision / RunState types.
5. Implement `src/speckit_orca/onboard.py` + heuristic modules.
   Keep it boring. Every heuristic is a deterministic function
   repo_root → list[Candidate]. Merge is a pure function.
6. Write `tests/test_onboard.py` using a fixture repo
   (`tests/fixtures/brownfield_repo/` with a realistic structure
   — auth, cli, data pipeline, utils grab-bag, test files) and
   verify scan/commit/rescan cycles.
7. Dogfood on spec-kit-orca itself. Run `adopt scan` against the
   current repo, triage the candidates, commit. If the MVP can
   reproduce (or improve on) the four ARs that 015 hand-created,
   that's the success criterion. If it surfaces a few new
   candidates the hand pass missed, even better.
8. Update `commands/adopt.md` with the scan/review/commit/rescan
   guidance.
9. Update `README.md` brownfield section to distinguish
   single-record adoption (015) from bulk onboarding (017).

## Appendix — what 015 got right that 017 preserves

- **AR primitive shape.** The minimal fields (summary, location,
  key behaviors) are exactly what a bulk pipeline would produce
  for each candidate. No pressure to expand AR shape.
- **Status enum.** `adopted | superseded | retired` covers the
  lifecycle. Drafts are off-registry, not a fourth status. Stays
  clean.
- **Advisory lock + atomic writes.** 017's batch commit calls 015
  per-record; the locking pattern just works under iteration.
- **Tolerant parser.** Lets 017 generate drafts that occasionally
  have odd formatting without blowing up the committed result.
- **No review, no yolo, no matriarch lanes for ARs.** Zero
  complexity to inherit — 017 produces more ARs, and they all stay
  inert the same way.
- **Overview regeneration.** After commit, the overview is
  auto-rewritten. 017 doesn't have to care — 015 handles it.

Everything 015 deferred to v2 — the manifest, the scan, the init
wizard — is what 017 builds. The deferral was correct; v2 is not
a retrofit of v1 primitives, it's a pipeline built on top of them.

## Appendix — what NOT to copy from OpenSpec

OpenSpec inspired 015's brownfield posture and indirectly motivates
017. Some OpenSpec patterns are worth explicitly rejecting:

- **Delta-spec semantics** (ADDED / MODIFIED / REMOVED per spec).
  Clever, but solves a different problem (tracking spec evolution).
  015 rejected this; 017 doesn't need it either.
- **`archive/` folder as a concept.** OpenSpec archives completed
  changes. Orca's ARs are durable references, not archives. Keep
  separate.
- **Auto-generating spec text from code comments.** OpenSpec doesn't
  quite do this but is tempting. 017 draws hard line: heuristics
  propose **structure** (here's a candidate, here's its paths);
  humans write **description** (what does it do). LLM-drafting
  (v1.2) softens this but always with operator review.

That's the brainstorm. Opinionated leans captured; open questions
flagged; sequencing scoped to what ships in MVP vs. follow-ons.
Next step is plan.md once the 15 open questions shrink to a
working set.
