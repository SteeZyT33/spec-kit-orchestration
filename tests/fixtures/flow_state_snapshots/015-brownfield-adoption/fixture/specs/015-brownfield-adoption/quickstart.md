# Quickstart: 015 Brownfield Adoption

**Status**: Draft
**Parent**: [plan.md](./plan.md)

Walked-through example of an adoption record's lifecycle: create
the record, optionally augment it, eventually supersede it (when
a full spec replaces it) or retire it (when the feature is
removed). Written from the operator's point of view. Shows what
the record looks like at each stage and where the matriarch guard
fires.

---

## The scenario

You're adopting Orca on the spec-kit-orca repo itself. Several
subsystems predate the named specs (`brainstorm-memory`, `evolve`,
`matriarch`, `flow-state`) — most notably the CLI entrypoint at
`src/speckit_orca/cli.py` and the `speckit-orca` binary. Flow-state
has no record of them, matriarch has no concept they exist, and
you don't want to retroactively write a full spec + plan + tasks
for code that already works.

You decide to register them as adoption records. This walkthrough
covers AR-001 (the CLI entrypoint) end-to-end.

**Command naming convention used throughout**: `/speckit.orca.adopt
*` is the operator-facing slash command surface (registered via the
extension manifest and invoked through Claude Code / Codex / Gemini).
`python -m speckit_orca.adoption *` is the underlying Python CLI
that the slash command dispatches to. The walkthrough shows the
Python CLI form because it is explicit and reproducible; in practice
most operators invoke the slash command form.

## Step 0 — Create the adoption record

You run `/speckit.orca.adopt new` (which dispatches to the Python
CLI's `create` subcommand):

```bash
uv run python -m speckit_orca.adoption --root . create \
    --title "CLI entrypoint" \
    --summary "Argument routing, subcommand dispatch, and config loading for the speckit-orca CLI. Predates every named spec." \
    --location "src/speckit_orca/cli.py" \
    --location "speckit-orca" \
    --key-behavior "Dispatches to subcommand modules (brainstorm, evolve, matriarch, etc.) based on argv[1]" \
    --key-behavior "Loads config from .specify/integration.json and .specify/init-options.json" \
    --key-behavior "Provides --help, --version, and per-subcommand help via argparse"
```

The runtime assigns the next available ID, captures the current
HEAD SHA as `Baseline Commit`, and writes:

```text
.specify/orca/adopted/AR-001-cli-entrypoint.md
```

The file looks like this:

```markdown
# Adoption Record: AR-001: CLI entrypoint

**Status**: adopted
**Adopted-on**: 2026-04-14
**Baseline Commit**: 69e48a0

## Summary
Argument routing, subcommand dispatch, and config loading for the
speckit-orca CLI. Predates every named spec.

## Location
- src/speckit_orca/cli.py
- speckit-orca

## Key Behaviors
- Dispatches to subcommand modules (brainstorm, evolve, matriarch,
  etc.) based on argv[1]
- Loads config from .specify/integration.json and
  .specify/init-options.json
- Provides --help, --version, and per-subcommand help via argparse
```

The overview file `00-overview.md` is automatically regenerated to
include AR-001 under the "Adopted" group.

## Step 1 — Inspect via flow-state

You can ask flow-state to interpret the AR file:

```bash
uv run python -m speckit_orca.flow_state .specify/orca/adopted/AR-001-cli-entrypoint.md
```

Returns:

```python
{
    "kind": "adoption",
    "id": "AR-001-cli-entrypoint",
    "slug": "cli-entrypoint",
    "title": "CLI entrypoint",
    "status": "adopted",
    "adopted_on": "2026-04-14",
    "baseline_commit": "69e48a0",
    "location": ["src/speckit_orca/cli.py", "speckit-orca"],
    "key_behaviors": ["Dispatches to subcommand modules...", ...],
    "known_gaps": None,
    "superseded_by": None,
    "retirement_reason": None,
    "review_state": "not-applicable",
}
```

Notice:

- `kind` is `"adoption"` (distinct from `"feature"` and
  `"spec-lite"`).
- `review_state` is `"not-applicable"` — adoption records are not
  reviewed and never will be in v1.
- No incomplete-milestone entries are derived from
  directory-style expectations. Flow-state does not warn about
  absent `plan.md` / `tasks.md` because AR files are single-file
  registry records, not feature directories.

## Step 2 — List records

To see all adoption records grouped by status:

```bash
uv run python -m speckit_orca.adoption --root . list
```

Output (after the first record):

```text
Adoption records (1 total)

Adopted (1):
  AR-001-cli-entrypoint  CLI entrypoint  (adopted 2026-04-14)
```

Filter by status:

```bash
uv run python -m speckit_orca.adoption --root . list --status superseded
```

## Step 3 — (Negative path) Try to register a matriarch lane

Suppose you forget that adoption records can't anchor lanes and
try:

```bash
# This will fail
uv run python -m speckit_orca.matriarch --root . register-lane --spec-id AR-001-cli-entrypoint
```

The matriarch guard fires **before any filesystem side effects**:

```text
MatriarchError: Cannot register lane for adoption record
'AR-001-cli-entrypoint'. Adoption records describe pre-existing
features, not active work. To coordinate work that touches
'AR-001-cli-entrypoint', hand-author a full spec under specs/
and register that instead. The adoption record can be used as
reference content when drafting the full spec.
```

After this rejection, you can verify the workspace is untouched:

```bash
ls .specify/orca/matriarch/mailbox/AR-001-cli-entrypoint/  # → does not exist
ls .specify/orca/matriarch/reports/AR-001-cli-entrypoint/  # → does not exist
```

The error tells you exactly what to do: if lane coordination
matters, hand-author a full spec. The AR stays as reference
content.

## Step 4 — (Growth path) Adoption record → hand-authored full spec

Later, you decide the CLI needs a substantial rewrite — moving
from argparse to click, restructuring subcommand dispatch, adding
plugin discovery. This warrants a full spec with plan, tasks, and
matriarch lane coordination.

You hand-author `specs/020-cli-rewrite/spec.md` and cite AR-001
as background:

```markdown
# Feature Specification: CLI Rewrite

## Background
The current CLI is documented as adoption record
[AR-001](/.specify/orca/adopted/AR-001-cli-entrypoint.md). It uses
argparse with manual subcommand dispatch. This spec covers the
migration to click with plugin discovery.

## References
- [AR-001](/.specify/orca/adopted/AR-001-cli-entrypoint.md) —
  the existing CLI being rewritten

...
```

The full spec links **back** to the adoption record. The AR does
not link forward (no equivalent of a `Promoted To` field on the
AR itself yet — that comes in Step 5 via the explicit supersede
command).

Now `specs/020-cli-rewrite/` can register a matriarch lane, go
through clarify, plan, tasks, review-spec, review-code — the full
ceremony. Until you supersede the AR, both the AR and the new
spec coexist.

## Step 5 — Supersede the adoption record

Once the rewrite ships and merges, you supersede the AR:

```bash
uv run python -m speckit_orca.adoption --root . supersede AR-001 020-cli-rewrite
```

The runtime:

1. Validates that `specs/020-cli-rewrite/spec.md` exists. If not,
   the command rejects with a clear pointer.
2. Updates the AR's `**Status**: adopted` line to
   `**Status**: superseded`.
3. Writes a `## Superseded By` section pointing at the full spec.
4. Regenerates the overview so AR-001 moves from "Adopted" to
   "Superseded".

The AR file now looks like:

```markdown
# Adoption Record: AR-001: CLI entrypoint

**Status**: superseded
**Adopted-on**: 2026-04-14
**Baseline Commit**: 69e48a0

## Summary
Argument routing, subcommand dispatch, and config loading for the
speckit-orca CLI. Predates every named spec.

## Location
- src/speckit_orca/cli.py
- speckit-orca

## Key Behaviors
- Dispatches to subcommand modules (brainstorm, evolve, matriarch,
  etc.) based on argv[1]
- Loads config from .specify/integration.json and
  .specify/init-options.json
- Provides --help, --version, and per-subcommand help via argparse

## Superseded By
020-cli-rewrite
```

The AR is preserved as historical context. Flow-state now reports
`status: superseded` and `superseded_by: 020-cli-rewrite`.

## Step 6 — (Alternative path) Retire instead of supersede

Suppose instead of replacing the CLI you remove it entirely (e.g.,
the CLI binary is deprecated in favor of a different
distribution). You retire the AR:

```bash
uv run python -m speckit_orca.adoption --root . retire AR-001 \
    --reason "CLI binary retired in v3.0; use the Python module entrypoints directly"
```

The runtime updates `**Status**: retired` and writes:

```markdown
## Retirement Reason
CLI binary retired in v3.0; use the Python module entrypoints
directly.
```

If you retire without `--reason`, the section is omitted entirely
(presence of `Status: retired` is sufficient signal).

The AR moves to the "Retired" group in the overview. Same as
supersession: the file is preserved as historical record, never
deleted by the runtime.

## What the operator learned

- **Adoption is fast.** Create → done is one command. The AR
  immediately appears in flow-state and the overview.
- **The matriarch guard catches misuse early.** Trying to anchor
  a lane on an AR fails with a clear message before any
  filesystem side effects happen — no junk artifacts left behind.
- **Supersession is explicit.** Writing a new full spec doesn't
  automatically supersede related ARs; you run
  `adopt supersede <ar-id> <spec-id>` when you decide the AR is
  replaced. The validation requires the target spec to exist.
- **Retirement preserves history.** Retired ARs aren't deleted.
  The retirement reason and the adopted-on date together document
  the feature's full lifespan.
- **No reviews ever.** Adoption records are reference-only by
  design; `review_state: "not-applicable"` is a hard invariant,
  not a default.

## What this walkthrough does NOT cover

- **Bulk adoption.** v1 is one record at a time. The
  `speckit.orca.adopt scan` command (repo-wide discovery) is
  deferred to v2. For now, audit the codebase manually and create
  ARs one at a time.
- **Code-introspection scaffolding.** v1's `new` command takes
  explicit `--summary` / `--location` / `--key-behavior` flags.
  The `--from <path>` mode that pre-fills these from source-code
  introspection is deferred to v2.
- **Adoption manifest.** A project-level
  `.specify/orca/adoption.md` describing baseline state (adopted
  on date X, baseline commit Y) is deferred to v2. v1 ships
  per-record `Baseline Commit` only.
- **Touch-point coordination.** Full specs do NOT declare which
  ARs they touch in v1. The lane-conflict-detection mechanism was
  cut from the design after cross-review. If two lanes both
  modify code covered by an AR, matriarch will not flag the
  overlap. Operators coordinate manually.
- **AR participation in 012 reviews.** ARs do not contribute to
  012's Review Milestone fields. There are no
  `AR-NNN-<slug>.review-spec.md` siblings, no review aggregation
  changes, no review_state mutation.
- **AR participation in yolo runs.** ARs are not a valid yolo
  start artifact in v1. The 009 yolo runtime does not consume
  them.

## Expected conformance against the contracts

As of 2026-04-16, the 013 spec-lite runtime has shipped (PR #40),
establishing `review_state` as a flow-state view field and the
`register_lane` guard-before-side-effects reorder. The 015
adoption runtime (PR #41) adds the adoption-specific
implementations. Once the 015 runtime PR lands, each step should
conform to the contracts under `./contracts/` as follows:

- Step 0's record will match `adoption-record.md`: 2 required + 1
  optional metadata fields, 3 required body sections, filename
  matches ID, lives under `.specify/orca/adopted/`.
- Step 1's flow-state view will match the
  `Adoption Flow-State View` entity in `data-model.md`:
  `kind: "adoption"`, `review_state: "not-applicable"`, all parsed
  fields present. The `review_state` view field was introduced by
  013's runtime (PR #40) for the spec-lite kind; 015's runtime
  extends it with the `"not-applicable"` value for adoption.
- Step 3's matriarch guard will match `matriarch-guard.md`: fires
  before any filesystem side effects, raises `MatriarchError`
  with the expected message shape, leaves no mailbox / reports /
  delegated-task artifacts on disk. Note: current `register_lane`
  creates those artifacts before any guard; the 015 runtime PR
  reorders the flow.
- Step 4's hand-authored full spec correctly links back to the
  AR without modifying the AR record. The AR's `Superseded By`
  section is empty until step 5 runs the supersede command.
- Step 5's supersession will match the `supersede` flow in
  `adoption-record.md`: validates target spec exists, updates
  status, writes `Superseded By` section, regenerates overview.
- Step 6's retirement will match the `retire` flow: updates status,
  writes `Retirement Reason` section if `--reason` was provided
  (omits the section entirely otherwise per plan open question 5),
  regenerates overview.
