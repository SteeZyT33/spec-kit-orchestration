# Orca

Orca is an add-on for Spec Kit. It extends Spec Kit with stronger agent
workflow, review, coordination, and multi-lane supervision.

It gives you a clearer path from rough idea to reviewed pull request by keeping
brainstorms, specs, plans, review artifacts, and coordination state on disk
instead of scattering them across chat sessions.

Orca depends on the Spec Kit workflow and artifact model. It is not meant to
replace Spec Kit. It adds a stronger operating layer on top of it while staying
provider-agnostic.

## What You Can Do With It

Orca adds durable brainstorming, lighter-weight micro-specs, clearer assignment
across agents, explicit review stages, metadata-first worktree management, and
Matriarch supervision for multiple active specs. All of that assumes you are
already working inside a Spec Kit-style project.

## Install

Orca is installed into a repo that already uses Spec Kit.

```bash
cd ~/spec-kit-orca
make tool-install
```

Or install it directly with `uv`:

```bash
cd ~/spec-kit-orca
uv tool install --force .
```

Then from any repo:

```bash
speckit-orca
speckit-orca codex
speckit-orca --minimal
```

If the command is not found, make sure `~/.local/bin` is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Basic Workflow

The normal path is:

```text
brainstorm -> plan -> tasks -> assign -> implement -> code review -> cross-review -> PR review
```

For smaller work, Orca supports micro-specs so you can keep the structure
without forcing a full heavyweight spec.

## Built In

Orca ships with a built-in workflow command set:

| Command | What it does |
|---|---|
| `brainstorm` | Captures pre-spec thinking, options, constraints, and recommendations before implementation starts. |
| `micro-spec` | Runs a lighter-weight spec flow for bounded changes that do not need a full feature spec. |
| `assign` | Recommends or coordinates agent assignment for implementation and review work. |
| `code-review` | Reviews implementation quality, spec compliance, merge readiness, and delivery risk. |
| `cross-review` | Runs an independent review through a different agent or provider for adversarial validation. |
| `pr-review` | Handles PR lifecycle review, comment processing, thread resolution, and post-merge checks. |
| `self-review` | Runs a process retrospective on how the work was executed and where the workflow should improve. |
| `review` | Compatibility entrypoint that routes to the appropriate review mode. |
| `matriarch` | Supervises multiple active specs through lanes, dependencies, assignments, and worker reporting. |

Orca also includes helper systems that support those commands:

| Helper | What it does |
|---|---|
| Brainstorm memory | Stores numbered brainstorm records and regenerates an overview index. |
| Evolve inventory | Tracks external ideas, adoption decisions, wrapper capabilities, and target mappings Orca wants to preserve. |
| Worktree metadata | Tracks lane/worktree state with Orca metadata instead of relying only on raw git output. |
| Flow-state | Infers stage, review progress, and next-step guidance from repo artifacts. |
| Context handoffs | Preserves the right upstream context between stages, sessions, branches, and lanes. |
| Capability packs | Makes optional workflow behavior explicit and inspectable. |
| Matriarch runtime | Provides durable lane registry, mailbox/report queues, delegated work, and deployment metadata. |

## Core Ideas

Important workflow state should live in the repo, not only in chat. Orca keeps
brainstorms, specs, plans, tasks, reviews, and coordination artifacts on disk.
It also treats review as more than one generic step by separating code review,
cross-agent review, PR review, and self-review. When several agents are active
at once, Orca favors clear ownership, durable state, and visible handoffs over
improvisation.

## Advanced

Orca also includes several deeper workflow tools.

Brainstorm memory keeps numbered idea records and regenerates an overview so
early thinking does not disappear. Evolve keeps a durable adoption inventory
under `.specify/orca/evolve/`, including one record per harvested idea and a
generated overview of mapped, implemented, deferred, and rejected entries.
Worktree helpers track lane metadata and prefer durable Orca state over raw git
output. The flow-state helper reads repo artifacts and infers current stage,
review progress, and next-step guidance.

Matriarch is the coordination layer for multiple active specs. It tracks one
primary spec per lane, lane ownership, dependencies, readiness, deployments,
and mailbox or report traffic for workers attached to that lane. It is meant
to supervise work, not replace the underlying Spec Kit artifacts.

Capability packs make optional workflow behaviors explicit instead of burying
them in hard-coded branching logic.

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

The default install also brings in companion extensions that strengthen the
workflow:

| Extension | What it adds |
|---|---|
| `superb` | stronger testing, verification, and debugging discipline |
| `verify` | evidence-based completion validation |
| `reconcile` | drift detection between intent and implementation |
| `status` | lightweight workflow visibility |

Use `--minimal` if you want Orca without the companion set.

## Roadmap

Orca is growing toward a more complete workflow system. The next steps are
smoother handoffs between stages, sessions, and worktrees, stronger multi-spec
supervision, deeper autonomous execution on top of stable workflow contracts,
and better ways to adopt worthwhile patterns from external systems without
losing Orca's identity.

## License

MIT
