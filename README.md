# Orca

Orca is an add-on for Spec Kit.

It keeps more of the workflow in the repo instead of in chat history: idea
capture, review artifacts, worktree state, lane coordination, and adoption
tracking. It does not replace Spec Kit. It adds a stronger operating layer on
top of it while staying provider-agnostic.

## What Orca Adds

Orca is for teams or individual operators who already like the Spec Kit
artifact model but want more structure around how work moves. It adds durable
brainstorming, lighter-weight micro-specs, stronger review modes, metadata-first
worktree handling, and a coordination layer for multiple active specs.

In practice, that means a feature can move from rough thinking to review-ready
work without relying on one agent session to remember everything.

## Install

Orca runs on top of `spec-kit`. Install Spec Kit first if you don't have it:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
```

Then install Orca:

```bash
uv tool install --force git+https://github.com/SteeZyT33/spec-kit-orca.git
```

Then from any Spec Kit repo:

```bash
speckit-orca claude
speckit-orca codex
speckit-orca --status
```

For local development in this repo:

```bash
make tool-install
```

If the command is not found, make sure `~/.local/bin` is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Basic Workflow

The normal path is:

```text
brainstorm -> plan -> tasks -> assign -> implement -> code-review -> cross-review -> pr-review
```

For smaller work, Orca supports `micro-spec` so you can keep the same discipline
without forcing a full heavyweight feature spec.

If you want a lighter install inside the current repo, use `--minimal`. If you
want to refresh Orca in the current repo, use `--force`. If you want to inspect
or diagnose the current repo setup, use `--status` or `--doctor`.

## Built In Commands

| Command | What it does |
|---|---|
| `brainstorm` | Captures early thinking, options, constraints, and recommendations before implementation starts. |
| `micro-spec` | Runs a lighter-weight spec path for bounded changes. |
| `assign` | Recommends or coordinates agent assignment for implementation and review work. |
| `code-review` | Reviews implementation quality, spec compliance, merge readiness, and delivery risk. |
| `cross-review` | Runs an independent review through a different agent or provider. |
| `pr-review` | Handles PR review, comment processing, thread resolution, and merge follow-through. |
| `self-review` | Reviews how the work was executed and where the workflow should improve. |
| `review` | Compatibility entrypoint that routes to the right review mode. |
| `matriarch` | Supervises multiple active specs through lanes, dependencies, assignments, and worker reporting. |

## Built In Systems

| System | What it does |
|---|---|
| Brainstorm memory | Stores numbered brainstorm records and regenerates an overview index. |
| Evolve inventory | Tracks harvested ideas, adoption decisions, wrapper capabilities, and target mappings. |
| Worktree metadata | Tracks lane and worktree state with Orca metadata instead of relying only on raw git output. |
| Flow-state | Infers current stage, review progress, and next-step guidance from repo artifacts. |
| Context handoffs | Preserves the right context between stages, sessions, branches, and lanes. |
| Capability packs | Makes optional workflow behavior explicit and inspectable. |
| Matriarch runtime | Provides a durable lane registry, mailbox and report queues, delegated work, and deployment metadata. |

## Advanced Tools

Brainstorm memory keeps numbered idea records and a generated overview so early
thinking does not disappear. Evolve keeps a durable adoption inventory under
`.specify/orca/evolve/`, including one entry per harvested idea and an overview
of what has been mapped, implemented, deferred, or rejected.

Worktree helpers track lane metadata and prefer durable Orca state over raw git
output. Flow-state reads repo artifacts and infers current stage, review
progress, and next-step guidance. Matriarch is the coordination layer for
multiple active specs. It tracks one primary spec per lane, lane ownership,
dependencies, readiness, deployments, and mailbox or report traffic for workers
attached to that lane.

Capability packs make optional workflow behavior explicit instead of burying it
inside hard-coded branching logic.

Example helper commands:

```bash
uv run python -m speckit_orca.evolve --root . list
bash scripts/bash/orca-worktree.sh list
uv run python -m speckit_orca.flow_state specs/002-brainstorm-memory --format text
bash scripts/bash/orca-matriarch.sh lane list
uv run python -m speckit_orca.capability_packs list --root .
```

Cross-review currently works best with `codex`, `claude`, `gemini`, and
`opencode`. `cursor-agent` is available only when selected explicitly.

## Companion Extensions

The default install attempts to add every extension in the list below from
the Spec Kit community catalog. Any that are not currently published to the
catalog are reported as `unavailable` — they are tracked as future
companions, not install failures.

**Stable companions** (expected to be present):

| Extension | What it adds |
|---|---|
| `superb` | stronger testing, verification, and debugging discipline |
| `verify` | evidence-based completion validation |
| `reconcile` | drift detection between intent and implementation |
| `status` | lightweight workflow visibility |

**Tracked companions** (attempted, may be unavailable):

| Extension | Intended purpose |
|---|---|
| `archive` | long-term record keeping for retired lanes and features |
| `doctor` | extended environment diagnostics |
| `fixit` | structured fix-it loops for failed reviews |
| `repoindex` | durable repo-wide indexing for faster lookup |
| `ship` | optional final-stage promotion helpers |
| `speckit-utils` | shared helpers across Spec Kit extensions |
| `verify-tasks` | focused verification pass over `tasks.md` |

If a tracked companion is not in the catalog yet, `speckit-orca claude` will
count it under `unavailable` in the install summary and continue. That is
expected; it is not an error.

Use `--minimal` if you want Orca without any companions. Use `--force` to
re-install companions that are already registered.

## Current Focus

Orca's workflow primitives are in place. Brainstorm memory, flow-state, split
review artifacts, context handoffs, capability packs, Matriarch multi-lane
supervision, and Evolve adoption tracking all ship in the current release.
`orca-yolo` is contract-complete as a single-lane runner spec and is wired to
Matriarch as its supervisory authority; what remains for YOLO is runtime
implementation on top of the already-durable workflow primitives.

Current focus is therefore two things: building the YOLO runtime against the
merged contracts, and tightening how the composed systems expose lane
readiness, review gates, and handoffs so multi-lane supervision remains safe
and inspectable. Evolve continues to track the next external patterns worth
adopting, with current focus on the wrapper-capability candidates
(`deep-optimize`, `deep-research`, `deep-review`).

## License

MIT
