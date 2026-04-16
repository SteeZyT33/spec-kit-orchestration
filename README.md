<div align="center">

<img src="https://img.shields.io/badge/v2.0.2-spec--kit--orca-blue?style=flat-square" alt="version" />

<pre>
       .
      ":"
    ___:____     |"\/"|
  ,'        `.    \  /
  |  O        \___/  |
~^~^~^~^~^~^~^~^~^~^~^~
 ██████  ██████   ██████  █████
██    ██ ██   ██ ██      ██   ██
██    ██ ██████  ██      ███████
██    ██ ██   ██ ██      ██   ██
 ██████  ██   ██  ██████ ██   ██
spec-kit orchestration · orcas don't sleep
</pre>

</div>

Orca is an add-on for Spec Kit.

It keeps more of the workflow in the repo instead of in chat history: idea
capture, current stage, review evidence, and optional multi-lane
coordination. It does not replace Spec Kit. It adds a stronger operating
layer on top of it while staying provider-agnostic.

## What Orca Adds

Orca is for teams or individual operators who already like the Spec Kit
artifact model but want more structure around how work moves. It adds
durable brainstorming, lighter-weight spec-lite intake, stronger review modes,
and — when work actually spans multiple features in parallel — a careful
multi-lane supervisor.

In practice, that means a feature can move from rough thinking to
review-ready work without relying on one agent session to remember
everything.

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

## The Four-Concept Workflow

Orca's public surface is four things: **intake**, **state**, **review**,
and (optionally) **lanes**. If you learn these four, you have learned
Orca. Everything else is implementation detail or experimental.

### 1. Intake — where work starts


| Entry point    | Use it for                                                                                                                                                                                                                                                               |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `brainstorm`   | Early thinking, options, constraints, and recommendations before implementation starts. Captured as durable numbered brainstorm records, not chat memory.                                                                                                                |
| `spec-lite`    | Bounded small NEW work that does not justify a full feature spec. Single-file record with problem / solution / acceptance / files-affected — no phase gates, no mandatory reviews, no promotion command. If scope grows, hand-author a full spec and cite the spec-lite. |
| `adopt`        | Brownfield intake for EXISTING features that predate Orca. Single-file adoption record with summary / location / key-behaviors. Reference-only: never reviewed, never drivable by yolo, never anchors a matriarch lane. Supersede when a full spec replaces it.          |
| Full spec path | Normal `specify → plan → tasks → assign → implement` flow for larger new features.                                                                                                                                                                                       |


### 2. State — where a feature is right now

Orca's answer to *"what is going on with this feature?"* is **flow-state**.
It reads the repo artifacts (brainstorm, spec, plan, tasks, review files,
worktree metadata) and reports the current stage, review progress,
next-step guidance, and any blockers. Ask flow-state first when you pick
up a feature that was worked on in another session.

```bash
# Full-spec feature directory
uv run python -m speckit_orca.flow_state specs/NNN-feature-name --format text

# Spec-lite record (per-file)
uv run python -m speckit_orca.flow_state .specify/orca/spec-lite/SL-001-slug.md

# Adoption record (per-file)
uv run python -m speckit_orca.flow_state .specify/orca/adopted/AR-001-slug.md
```

Flow-state accepts three target types: feature directories (full spec),
spec-lite record files, and adoption record files. Each returns a view
shape fitted to the target kind. Flow-state is the visible aggregator of
truth — you do not need to know which internal subsystem owns an artifact.

### 3. Review — durable evidence at every gate


| Command       | Artifact         | Description                                         |
| ------------- | ---------------- | --------------------------------------------------- |
| `review-spec` | `review-spec.md` | Cross-only adversarial review of the clarified spec |
| `review-code` | `review-code.md` | Self+cross review per user-story phase, append-only |
| `review-pr`   | `review-pr.md`   | PR comment disposition + required process retro     |


Three review artifacts with distinct structures: `review-spec` is
cross-only (adversarial), `review-code` has self+cross passes per
user-story phase, and `review-pr` handles PR comment disposition
plus a required process retro. Cross-pass agent is always different
from the author, routed automatically by Matriarch. See
`specs/012-review-model/` for contracts.

### 4. Lanes — optional, only for parallel work

Lanes exist when you're working on **multiple feature specs in parallel**
and need one place to see who owns what, what's blocked, and what's
ready. Single-feature work does not need lanes at all. See the
[Experimental](#experimental) section below for Matriarch, Orca's careful
multi-lane supervisor.

## Basic Workflow

The normal path for one feature is:

```text
brainstorm → specify → plan → tasks → assign → implement → review-spec → review-code → review-pr
```

For smaller work, use `spec-lite` instead of the full spec path. Use
`--minimal` to install Orca without companion extensions, `--force` to
refresh Orca in the current repo, and `--status` or `--doctor` to inspect
or diagnose repo setup.

## Experimental

The following subsystems exist in the repo and are usable, but they are
**not part of the default workflow**. They are optional, and they are
explicitly not required to ship a feature through Orca. Treat them as
opt-in advanced mode.

### Matriarch — multi-lane supervision (optional, experimental in v1)

Use Matriarch only when you need one durable view over **multiple active
feature specs being worked on in parallel**. Single-feature work does not
need it. Matriarch is a supervisor, not a hidden swarm runtime — it
tracks lane registration, dependencies, assignments, readiness
aggregation, durable mailbox/report traffic for lane-local workers, and
optional deployment metadata, but it does not own feature-stage
semantics, review evidence, or uncontrolled autonomous execution. Those
stay with flow-state, review artifacts, and the commands that own them.

Matriarch is marked **experimental in v1** because the runtime has
shipped with deliberate conservatism: lane lifecycle, dependency
evaluation, mailbox/event-envelope, delegated work, and command surface
are implemented and tested, but several refinements (drift-flag
surfacing, live tmux session inspection, the hook model) are tracked as
post-v1 work. Shipping a single feature through Orca does not require
any of this.

```bash
bash scripts/bash/orca-matriarch.sh lane list
bash scripts/bash/orca-matriarch.sh status
```

See [commands/matriarch.md](./commands/matriarch.md) for the full
supervisory surface, and `specs/010-orca-matriarch/` for the contracts
and data model.

## Internals

Orca's workflow primitives are implementation detail. You do not need to
learn any of these to ship a feature, and they are **not** a public
product surface. They are listed here so operators can find the runtime
when debugging, not so day-one users are expected to understand them.

- **Brainstorm memory** — numbered brainstorm records with a generated
overview index under `.specify/orca/brainstorms/`. Called indirectly
by the `brainstorm` command.
- **Flow-state** — the aggregator surfaced under "State" above. Runtime
at `src/speckit_orca/flow_state.py`, CLI at `python -m speckit_orca.flow_state`.
- **Review artifacts** — durable per-stage review files owned by the
review commands (`commands/review-spec.md`, `commands/review-code.md`,
`commands/review-pr.md`) and rendered from
templates under `templates/review-*-template.md`.
- **Context handoffs** — stage-to-stage continuity records under
`.specify/orca/handoffs/`, consumed automatically when a feature
crosses a stage boundary. Runtime at `src/speckit_orca/context_handoffs.py`.
- **Worktree runtime** — shell-level worktree create/list/cleanup
lifecycle plus lane metadata under `.specify/orca/worktrees/`. See
`scripts/bash/orca-worktree.sh` and `scripts/bash/orca-worktree-lib.sh`.
- **Capability packs** — optional composition layer that keeps
cross-cutting concerns out of the core command set. Runtime at
`src/speckit_orca/capability_packs.py`. Most operators never need to
configure packs manually.

### Maintainer Subsystems

These are for maintainers who are harvesting external systems into Orca
or running structural reviews. They are not operator-facing.

- **Evolve inventory** — durable adoption record for external patterns,
wrapper capabilities, and deferred ideas under `.specify/orca/evolve/`.
One entry per harvested pattern with decision, rationale, and target
mapping. Runtime at `src/speckit_orca/evolve.py`; CLI at
`uv run python -m speckit_orca.evolve --root . list`.
- **Refinement reviews** — structured product-surface reviews under
`docs/refinement-reviews/`. Use when the repo's architecture has grown
faster than its external narrative. See the directory README for the
five-section framework and when to run one.

## Companion Extensions

The default install attempts to add every extension in the list below
from the Spec Kit community catalog. Any that are not currently published
to the catalog are reported as `unavailable` — they are tracked as future
companions, not install failures.

**Stable companions** (expected to be present):


| Extension   | What it adds                                             |
| ----------- | -------------------------------------------------------- |
| `superb`    | stronger testing, verification, and debugging discipline |
| `verify`    | evidence-based completion validation                     |
| `reconcile` | drift detection between intent and implementation        |
| `status`    | lightweight workflow visibility                          |


**Tracked companions** (attempted, may be unavailable):


| Extension       | Intended purpose                                        |
| --------------- | ------------------------------------------------------- |
| `archive`       | long-term record keeping for retired lanes and features |
| `doctor`        | extended environment diagnostics                        |
| `fixit`         | structured fix-it loops for failed reviews              |
| `repoindex`     | durable repo-wide indexing for faster lookup            |
| `ship`          | optional final-stage promotion helpers                  |
| `speckit-utils` | shared helpers across Spec Kit extensions               |
| `verify-tasks`  | focused verification pass over `tasks.md`               |


If a tracked companion is not in the catalog yet, `speckit-orca claude`
will count it under `unavailable` in the install summary and continue.
That is expected; it is not an error.

Use `--minimal` if you want Orca without any companions. Use `--force` to
re-install companions that are already registered.

Cross-review currently works best with `codex`, `claude`, `gemini`, and
`opencode`. `cursor-agent` is available only when selected explicitly.

## Current Focus

Orca's workflow primitives are in place. Brainstorm memory, flow-state,
split review artifacts, context handoffs, capability packs, Matriarch
multi-lane supervision (experimental), and Evolve adoption tracking all
ship in the current release. `orca-yolo` is contract-complete as a
single-lane runner spec and is wired to Matriarch as its supervisory
authority; what remains for YOLO is runtime implementation on top of the
already-durable workflow primitives.

Current focus is therefore two things: building the YOLO runtime against
the merged contracts, and tightening how the composed systems expose
lane readiness, review gates, and handoffs so multi-lane supervision
remains safe and inspectable. Evolve continues to track the next
external patterns worth adopting, with current focus on the
wrapper-capability candidates (`deep-optimize`, `deep-research`,
`deep-review`).

## License

MIT