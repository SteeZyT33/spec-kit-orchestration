<div align="center">

<img src="https://img.shields.io/badge/v2.1.0-orca-blue?style=flat-square" alt="version" />

<pre>
   .
   ":"
    ___:____      |"\/"|
  ,'        `.    \  /
  |  O        \___/  |
~^~^~^~^~^~^~^~^~^~^~^~
 ██████  ██████   ██████  █████
██    ██ ██   ██ ██      ██   ██
██    ██ ██████  ██      ███████
██    ██ ██   ██ ██      ██   ██
 ██████  ██   ██  ██████ ██   ██
orca · spec-kit orchestration · orcas don't sleep
</pre>

</div>

Orca is an add-on for Spec Kit.

It keeps more of the workflow in the repo instead of in chat history: idea
capture, current stage, and review evidence. It does not replace Spec Kit.
It adds a stronger operating layer on top of it while staying
provider-agnostic.

## What Orca Adds

Orca is for teams or individual operators who already like the Spec Kit
artifact model but want more structure around how work moves. It adds
durable brainstorming, an aggregated flow-state view, and stronger review
modes anchored to durable per-stage artifacts.

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
uv tool install --force git+https://github.com/SteeZyT33/orca.git
```

Then from any Spec Kit repo:

```bash
orca claude
orca codex
orca --status
```

For local development in this repo:

```bash
make tool-install
```

If the command is not found, make sure `~/.local/bin` is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## The Three-Concept Workflow

Orca's public surface is three things: **intake**, **state**, and
**review**. If you learn these three, you have learned Orca. Everything
else is implementation detail.

### 1. Intake — where work starts


| Entry point    | Use it for                                                                                                                                                |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `brainstorm`   | Early thinking, options, constraints, and recommendations before implementation starts. Captured as durable numbered brainstorm records, not chat memory. |
| Full spec path | Normal `specify → plan → tasks → implement` flow for new features.                                                                                        |


### 2. State — where a feature is right now

Orca's answer to *"what is going on with this feature?"* is **flow-state**.
It reads the repo artifacts (brainstorm, spec, plan, tasks, review files,
worktree metadata) and reports the current stage, review progress,
next-step guidance, and any blockers. Ask flow-state first when you pick
up a feature that was worked on in another session.

```bash
# Full-spec feature directory
uv run python -m orca.flow_state specs/NNN-feature-name --format text
```

Flow-state reads feature directories (full spec) and returns a view of
the current stage, review progress, and any blockers. Flow-state is the
visible aggregator of truth — you do not need to know which internal
subsystem owns an artifact.

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
from the author. See `specs/012-review-model/` for contracts.

## Basic Workflow

The normal path for one feature is:

```text
brainstorm → specify → plan → tasks → implement → review-spec → review-code → review-pr
```

Use `--minimal` to install Orca without companion extensions, `--force`
to refresh Orca in the current repo, and `--status` or `--doctor` to
inspect or diagnose repo setup.

## Internals

Orca's workflow primitives are implementation detail. You do not need to
learn any of these to ship a feature, and they are **not** a public
product surface. They are listed here so operators can find the runtime
when debugging, not so day-one users are expected to understand them.

- **Brainstorm memory** — numbered brainstorm records with a generated
overview index under `.orca/brainstorms/`. Called indirectly
by the `brainstorm` command.
- **Flow-state** — the aggregator surfaced under "State" above. Runtime
at `src/orca/flow_state.py`, CLI at `python -m orca.flow_state`.
- **Review artifacts** — durable per-stage review files owned by the
review commands (`commands/review-spec.md`, `commands/review-code.md`,
`commands/review-pr.md`) and rendered from
templates under `templates/review-*-template.md`.
- **Context handoffs** — stage-to-stage continuity records under
`.orca/handoffs/`, consumed automatically when a feature
crosses a stage boundary. Runtime at `src/orca/context_handoffs.py`.
- **Worktree runtime** — shell-level worktree create/list/cleanup
lifecycle plus lane metadata under `.orca/worktrees/`. See
`scripts/bash/orca-worktree.sh` and `scripts/bash/orca-worktree-lib.sh`.

### Maintainer Subsystems

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


If a tracked companion is not in the catalog yet, `orca claude`
will count it under `unavailable` in the install summary and continue.
That is expected; it is not an error.

Use `--minimal` if you want Orca without any companions. Use `--force` to
re-install companions that are already registered.

Cross-review currently works best with `codex`, `claude`, `gemini`, and
`opencode`. `cursor-agent` is available only when selected explicitly.

## Current Focus

v2.1 reframes Orca as a repo-backed control plane: brainstorm memory,
flow-state aggregation, durable per-stage review artifacts, and context
handoffs ship as the core surface. Phase 1 stripped the runner /
supervisor / brownfield surfaces (yolo, matriarch, spec-lite, adopt,
assign) to focus the project on the review-and-state wedge.

Phase 2-5 work targets six v1 capabilities with documented JSON
contracts (cross-agent-review, completion-gate, worktree-overlap-check,
flow-state-projection, citation-validator, contradiction-detector), plus
a Codex plugin and reviewer backend. See `CHANGELOG.md` and
`MIGRATION.md` for the v2.0 → v2.1 transition.

## License

MIT
