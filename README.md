# Orca

Orca is a workflow layer for agent-driven software delivery. It helps turn a
rough idea into reviewed, merge-ready work with stronger structure around
brainstorming, implementation, review, and parallel execution.

The emphasis is simple:

- make good work easier to repeat
- keep durable artifacts instead of relying on chat memory
- support multiple agent providers without locking the workflow to one of them

## What Orca Does Today

Orca already supports:

- durable brainstorming with project-local memory and overview regeneration
- micro-spec work for bounded changes
- assignment guidance for multi-agent or parallel execution
- Matriarch supervision for multi-spec lane coordination, dependency tracking, and durable lane-local messaging
- implementation review, PR review, cross-agent review, and self-review
- split durable review artifacts instead of one overloaded generic review file
- metadata-first worktree helpers for lane-based execution
- a computed flow-state helper that can infer stage and next-step guidance from durable artifacts
- capability packs so optional workflow behavior stays explicit instead of being hard-coded everywhere

It also installs companion extensions for verification, reconciliation, status,
and stricter delivery habits.

## Install

Install the tool once with `uv`:

```bash
cd ~/spec-kit-orca
make tool-install
```

Or directly:

```bash
cd ~/spec-kit-orca
uv tool install --force .
```

From inside any project directory:

```bash
speckit-orca
speckit-orca codex
speckit-orca --minimal
```

To refresh the installed tool from this repo:

```bash
cd ~/spec-kit-orca
make tool-reinstall
```

If `speckit-orca` is not found after install, make sure `~/.local/bin` is on
your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Workflow Surface

The operator-facing workflow is built around:

- brainstorm
- micro-spec
- assign
- implement
- code review
- cross-review
- PR review
- self-review

In practice, the common path is:

```text
brainstorm -> plan -> tasks -> assign -> implement -> code review -> cross-review -> PR review
```

For smaller work, micro-spec stays lighter while still keeping planning,
verification, and review explicit.

## Runtime Helpers

### Brainstorm memory

Brainstorming is backed by durable project-local memory under `brainstorm/`.
That gives you numbered idea records plus a generated `00-overview.md` instead
of a one-off chat artifact.

Direct helper usage:

```bash
uv run python -m speckit_orca.brainstorm_memory create ...
uv run python -m speckit_orca.brainstorm_memory matches ...
uv run python -m speckit_orca.brainstorm_memory update ...
uv run python -m speckit_orca.brainstorm_memory regenerate-overview ...
```

### Worktree helpers

Orca includes a metadata-first worktree runtime:

```bash
bash scripts/bash/orca-worktree.sh create --lane ui --task-scope T012,T013
bash scripts/bash/orca-worktree.sh list
bash scripts/bash/orca-worktree.sh status
bash scripts/bash/orca-worktree.sh cleanup
```

It writes lane metadata only after git worktree creation succeeds, prefers Orca
metadata over raw git output when reporting state, and refuses to clean up
ambiguous or active lanes.

### Flow-state helper

Orca also includes a computed-first flow-state helper:

```bash
uv run python -m speckit_orca.flow_state specs/002-brainstorm-memory --format text
uv run python -m speckit_orca.flow_state specs/002-brainstorm-memory --format json
```

It derives current stage, review progress, ambiguity, and next-step hints from
durable artifacts rather than chat history.

### Matriarch supervision

Matriarch gives Orca a conservative control plane for multiple active specs. It
tracks one primary spec per lane, assignment history, dependencies, readiness
signals, and state-first mailbox/report traffic for lane-local workers.

Direct helper usage:

```bash
bash scripts/bash/orca-matriarch.sh status
bash scripts/bash/orca-matriarch.sh lane register 010-orca-matriarch --owner-type human --owner-id taylor
bash scripts/bash/orca-matriarch.sh lane list
bash scripts/bash/orca-matriarch.sh lane show 010-orca-matriarch
bash scripts/bash/orca-matriarch.sh lane startup-ack 010-orca-matriarch --sender claude-code --deployment-id 010-orca-matriarch-direct-session
```

Matriarch keeps tmux optional. For long-lived interactive workers such as
Claude Code, `direct-session` is a first-class deployment type instead of an
implicit “no deployment” fallback.

### Capability packs

Capability packs let Orca expose optional workflow behaviors without turning
the core into a giant pile of conditional logic.

The initial packs include:

- `brainstorm-memory`
- `flow-state`
- `worktrees`
- `review`
- `yolo`

Inspect the effective pack state for a repo:

```bash
uv run python -m speckit_orca.capability_packs list --root .
uv run python -m speckit_orca.capability_packs show flow-state --root . --json
uv run python -m speckit_orca.capability_packs validate --root .
uv run python -m speckit_orca.capability_packs scaffold --root .
```

## Review

Cross-review currently supports a tiered agent model. The strongest current
cross-agent path is through `codex`, `claude`, `gemini`, or `opencode`.
`cursor-agent` is available only when explicitly selected.

Orca now keeps review stages more explicit:

- `review.md` as the summary/index
- `review-code.md` for implementation review
- `review-cross.md` for alternate-agent review
- `review-pr.md` for pull request lifecycle review
- `self-review.md` for process retrospective

## Configuration

After install, you can optionally edit `orca-config.yml`:

```yaml
crossreview:
  agent: null
  harness: null
  model: null
  effort: "high"
  ask_on_ambiguous: true
  remember_last_success: true

exclusions:
  - ".specify/scripts/*"
  - ".specify/templates/*"
```

If no reviewer agent is configured, Orca prefers a different installed Tier 1
reviewer than the current provider when possible.

## Roadmap

Orca is moving from a useful workflow toolkit toward a more coherent workflow
system.

Planned work includes:

- cleaner handoffs between stages, sessions, and worktrees
- a full-run orchestration mode that can take work from idea to PR on stable foundations
- deeper multi-spec supervision layers above today’s single-spec lane model
- a self-evolution layer for harvesting and adopting worthwhile patterns from external repos

The roadmap should explain direction, not mirror internal planning.

## Companion Extensions

The default install also brings in companion extensions that strengthen the
workflow:

| Extension | What it adds |
|---|---|
| `superb` | test-first discipline, verification gates, and debug workflow support |
| `verify` | evidence-based completion validation |
| `reconcile` | drift detection between intent and implementation |
| `status` | lightweight workflow visibility |

Use `--minimal` if you want Orca without the companion set.

## Documentation

The README is intentionally product-facing. It should explain what Orca is,
what it can do now, and where it is going next without turning into an internal
spec ledger.

The rules for future README work live in
[readme-style-guide.md](/home/taylor/spec-kit-orca/docs/readme-style-guide.md).

## License

MIT
