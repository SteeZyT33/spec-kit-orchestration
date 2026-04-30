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

Orca is an opinion layer + capability library for agentic engineering governance.

It keeps more of the workflow in the repo instead of in chat history: idea
capture, current stage, and review evidence. It works on top of Spec Kit,
OpenSpec, the Superpowers convention, or a bare repo — orca detects the
host's spec system and adapts.

## What Orca Adds

Orca is for teams or individual operators who want structure around how work
moves. It ships:

- **A capability library** — `cross-agent-review`, `citation-validator`,
  `contradiction-detector`, `completion-gate`, `worktree-overlap-check`,
  `flow-state-projection`. JSON-in/JSON-out via `orca-cli`, importable as a
  Python library.
- **An opinion layer** — slash commands (`/orca:review-spec`,
  `/orca:review-code`, `/orca:review-pr`, `/orca:cite`, `/orca:gate`) that
  wire the capability library into a personal SDD workflow.
- **Plugin formats** for Claude Code (skills + commands) and Codex
  (AGENTS.md fragments).
- **Brownfield adoption** — a single command (`orca-cli adopt`) installs
  orca into any existing repo, respecting your existing CLAUDE.md /
  AGENTS.md / constitution / spec system, with reviewable manifest and
  one-command revert.

## Install

```bash
uv tool install --force git+https://github.com/SteeZyT33/orca.git
```

If the command is not found, make sure `~/.local/bin` is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Adopt orca into your repo

For any existing repo (spec-kit, openspec, superpowers, or bare):

```bash
cd your-existing-repo
orca-cli adopt          # detects host system, writes .orca/adoption.toml,
                        # appends an orca block to AGENTS.md / CLAUDE.md
orca-cli apply --revert # clean uninstall; byte-identical original restored
```

Adoption is opt-in and reversible. The manifest is the source of truth for
your install choices and is version-controlled with the repo.

### Spec-kit-specific install (legacy)

If you're using Spec Kit explicitly and want the companion extension flow:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
orca claude   # or: orca codex
orca --status
```

For local development in this repo:

```bash
make tool-install
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

## CLI Surface (`orca-cli`)

`orca-cli` is the canonical capability surface. Run `orca-cli --list` to
see all subcommands, or `orca-cli --version` for the installed version.

**Capabilities** (JSON-in/JSON-out, library-callable):

| Subcommand | Purpose |
| ---------- | ------- |
| `cross-agent-review` | Adversarial review by a different agent than the author |
| `citation-validator` | Citation hygiene check against a reference set |
| `contradiction-detector` | Detect contradictions between new content and prior evidence |
| `completion-gate` | Stage-gate evaluator for `plan-ready`, `tasks-ready`, etc. |
| `worktree-overlap-check` | Conflict detection across active worktrees |
| `flow-state-projection` | Aggregated stage/review state for a feature dir |

**Adoption + path resolution** (host-aware):

| Subcommand | Purpose |
| ---------- | ------- |
| `adopt` | Interactive wizard; writes `.orca/adoption.toml` + applies surfaces |
| `apply` | Apply manifest idempotently; `--revert` undoes; `--dry-run` previews |
| `resolve-path` | Resolve `feature-dir`, `constitution`, `agents-md`, `reviews-dir`, or `reference-set` per the host's manifest (or detection if no manifest) |

**Utility**:

| Subcommand | Purpose |
| ---------- | ------- |
| `parse-subagent-response` | Convert host LLM subagent output to findings file |
| `build-review-prompt` | Emit canonical review prompt for in-session subagent dispatch |

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
- **Adoption manifest** — host-aware install state at `.orca/adoption.toml`
plus apply state at `.orca/adoption-state.json`. Pre-modification
backups under `.orca/adoption-backup/<timestamp>/` enable hash-checked
revert. Runtime at `src/orca/core/adoption/`.
- **Host-layout adapter** — single abstraction over `{spec-kit, openspec,
superpowers, bare}` spec conventions. Slash commands consult it via
`orca-cli resolve-path`, so feature-dir resolution honors the adopted
host's convention. Runtime at `src/orca/core/host_layout/`.

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

## What Orca Is

Orca is a repo-backed capability library for agentic engineering governance. It does not execute host runtimes. Hosts pull Orca capabilities and translate outputs into their own state.

Concretely, Orca ships:

- a small set of pure-function capabilities (review, gate, lint, project) with documented JSON contracts
- reviewer adapters (Claude SDK, Codex CLI shellout) that swap behind a single `Reviewer` protocol
- a canonical `orca-cli` surface and an importable Python library
- per-host integration shims (perf-lab) that translate orca outputs into native host events

Orca does NOT ship:

- a scheduler, worker runtime, supervisor, or live presence system
- a control plane that watches host state and decides actions
- a primary store for review state or flow state (the host or the repo owns that)

LLM-backed capabilities (`cross-agent-review`, `contradiction-detector`) produce findings and hypotheses, not formal proof. Hosts decide how findings affect downstream actions.

If a capability is absent or fails, the host stays in control: the host decides whether to block, fall back, or skip. Orca is pull-not-push.

## Current Focus (v2.1)

**Phase 1** stripped the prior runner / supervisor surfaces (yolo, matriarch, spec-lite, adopt, assign) so the project can focus on the review-and-state wedge. See `CHANGELOG.md` and `MIGRATION.md` for the v2.0 → v2.1 transition.

**Phase 2** ships six v1 capabilities with JSON Schemas, a Python CLI, and a structurally typed reviewer protocol: `cross-agent-review`, `worktree-overlap-check`, `flow-state-projection`, `completion-gate`, `citation-validator`, `contradiction-detector`.

**Phase 3** adds plugin formats (Claude Code skills + slash commands; Codex AGENTS.md fragments) and 5 wired slash commands (`/orca:review-spec`, `/orca:review-code`, `/orca:review-pr`, `/orca:gate`, `/orca:cite`).

**Phase 4a** ships in-session subagent-based reviewers: review pattern works inside Claude Code without `ANTHROPIC_API_KEY`. The host LLM dispatches a subagent reviewer and orca consumes its findings via `--claude-findings-file` / `--codex-findings-file`.

**Phase 4b prereqs** (in orca repo): `--claude-findings-file` flag added to `contradiction-detector`, `orca-cli --version`, dispatch algorithm contract, regression test for `build-review-prompt --kind`. Perf-lab integration spec PR is the downstream consumer.

**Spec 015 brownfield adoption** ships `orca-cli adopt` / `orca-cli apply` plus the `host_layout` adapter so a third party can install orca into any existing repo (spec-kit, openspec, superpowers, bare) with reviewable manifest and one-command revert. The companion `resolve-path` refactor wires slash commands through the adapter so feature-dir resolution honors the adopted host's convention.

See `docs/superpowers/specs/` for the design specs and `docs/superpowers/contracts/` for the path-safety and dispatch-algorithm contracts.

## License

MIT
