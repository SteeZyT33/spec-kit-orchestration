# spec-kit-orca

Spec-compliant workflow orchestration, code review, PR review, agent-to-task assignment, cross-agent adversarial review, and process self-improvement for [Spec Kit](https://github.com/github/spec-kit).

## Quick Start

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
speckit-orca              # default: claude
speckit-orca codex        # different agent
speckit-orca --minimal    # no companion extensions
```

To update the installed tool from this repo:

```bash
cd ~/spec-kit-orca
make tool-reinstall
```

If you want a simple local symlink instead of `uv tool`, the fallback is:

```bash
cd ~/spec-kit-orca
make install
```

If `speckit-orca` is not found after install, make sure `~/.local/bin` is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

This installs:
- **Spec Kit** (core) — specify, plan, tasks, implement, analyze, clarify, constitution, checklist
- **Orchestration** (this extension) — brainstorm, micro-spec, assign, code-review, pr-review, cross-review, self-review
- **Superb** (companion) — TDD enforcement, verification gates, debug protocol, superpowers bridge
- **Verify** (companion) — evidence-based completion validation
- **Reconcile** (companion) — spec-implementation drift detection
- **Status** (companion) — workflow progress dashboard

## Commands

### `/speckit.orca.brainstorm`

Structured pre-spec ideation that captures the problem, options, constraints, and recommendation without dropping into implementation.

```text
/speckit.orca.brainstorm                 # create or refine brainstorm artifact
/speckit.orca.brainstorm --feature 004   # target an existing feature explicitly
```

Durable brainstorm sessions are stored in project-local memory under `brainstorm/`
as numbered records such as `brainstorm/01-agent-selection.md`. Orca regenerates
`brainstorm/00-overview.md` after each durable brainstorm write or update so the
current idea landscape stays navigable. Existing feature refinement continues to
use `specs/<feature>/brainstorm.md`, and `.specify/orca/inbox/` remains a
temporary scratch fallback rather than the default save target.

The deterministic helper behind this flow is available for direct verification:

```text
uv run python -m speckit_orca.brainstorm_memory create ...
uv run python -m speckit_orca.brainstorm_memory matches ...
uv run python -m speckit_orca.brainstorm_memory update ...
uv run python -m speckit_orca.brainstorm_memory regenerate-overview ...
```

## Capability Packs

Orca now has a lightweight capability-pack registry so cross-cutting behavior is
explicit instead of being hard-coded into every command. The initial packs are:

- `brainstorm-memory`
- `flow-state`
- `worktrees`
- `review`
- `yolo`

Inspect the effective pack state for a repo:

```text
uv run python -m speckit_orca.capability_packs list --root .
uv run python -m speckit_orca.capability_packs show flow-state --root . --json
uv run python -m speckit_orca.capability_packs validate --root .
uv run python -m speckit_orca.capability_packs scaffold --root .
```

Repo-local overrides live at `.specify/orca/capability-packs.json`. This keeps
activation inspectable without recreating Spex's heavier trait layering.

### `/speckit.orca.micro-spec`

Micro-spec workflow for bounded work. Requires a mini-plan, declared verification mode, code review, and promotion to full spec flow when the scope grows.

```
/speckit.orca.micro-spec "Fix broken path detection"
/speckit.orca.micro-spec --feature 004 "Polish graph filter labels"
```

### `/speckit.orca.code-review`

Validates implementation against spec artifacts, checks merge and delivery readiness, and records findings before the PR feedback loop begins.

```
/speckit.orca.code-review               # Full implementation review
/speckit.orca.code-review --security    # Force security pass
/speckit.orca.code-review --critique    # Add product + engineering critique
```

### `/speckit.orca.pr-review`

Handles PR creation or update, external reviewer comments, review thread resolution, and post-merge verification.

```
/speckit.orca.pr-review                 # PR lifecycle + external feedback handling
/speckit.orca.pr-review --comments-only # Process new PR comments only
/speckit.orca.pr-review --post-merge    # Check for silent reversions after merge
```

### `/speckit.orca.review`

Compatibility alias only. Routes to `code-review` or `pr-review` based on flags and intent.

```
/speckit.orca.review --security
/speckit.orca.review --comments-only
```

### `/speckit.orca.assign`

Matches agents to tasks based on capability detection, expertise lenses, and confidence scoring.

```
/speckit.orca.assign                    # Assign agents to tasks
/speckit.orca.assign focus on security  # Bias toward security expertise
```

### `/speckit.orca.cross-review`

Invokes an alternate reviewer agent to adversarially review design artifacts or code changes.

```text
/speckit.orca.cross-review                  # Auto-select a reviewer agent
/speckit.orca.cross-review --agent opencode # Explicit reviewer agent
/speckit.orca.cross-review --scope code  # Review code only
```

### `/speckit.orca.self-review`

Process retrospective — NOT a code review. Evaluates what worked and what didn't across the full spec-driven workflow, then dispatches agents to automatically improve extension commands based on findings.

```
/speckit.orca.self-review               # Full process retrospective
```

Evaluates five dimensions: spec fidelity, plan accuracy, task decomposition, review effectiveness, and workflow friction. Low/medium risk improvements are auto-applied to extension commands. High risk improvements are deferred for human review.

## Recommended Workflow

```text
brainstorm (optional) → specify → plan → tasks → assign → implement → code-review → cross-review → pr-review → self-review
                                      micro-spec (bounded work) ───────────────┘
```

The self-review loop is what makes this self-improving: each feature you ship makes the orchestration commands better for the next feature.

## Protocols

Orca now treats execution topology and delivery hygiene as first-class workflow concerns:

- **Worktree protocol** — provider-agnostic lane metadata under `.specify/orca/worktrees/` is the workflow source of truth, not agent-specific folders.
- **Delivery protocol** — branch, commit, and PR shape should reflect feature and lane boundaries so review and integration stay coherent.

The practical implication is that `assign` is no longer just a convenience command for big task lists. It is the place where Orca decides whether work is sequential or lane-based, using Orca metadata rather than Claude-specific assumptions.

## Worktree Runtime

The first runtime helper surface is shell-based:

```bash
bash scripts/bash/orca-worktree.sh create --lane ui --task-scope T012,T013
bash scripts/bash/orca-worktree.sh list
bash scripts/bash/orca-worktree.sh status
bash scripts/bash/orca-worktree.sh cleanup
```

Behavior:

- `create` writes lane metadata only after the git worktree succeeds
- `list` and `status` are metadata-first and warn when metadata drifts from `git worktree list`
- `cleanup` only processes lanes already marked `merged` or `retired`; active or ambiguous lanes are warned and skipped
- `.specify/orca/worktrees/` is local runtime state and is ignored by git by default

## Companion Extensions

These are installed automatically by `speckit-orca`. They work independently but complement the orchestration workflow:

| Extension | What it adds | Why |
|---|---|---|
| **superb** | TDD gates, verification, debug protocol, superpowers bridge | Enforces test-first development and evidence-based completion |
| **verify** | Post-implementation completion gate | Prevents false task completions — complements review |
| **reconcile** | Drift detection and spec repair | Catches when code diverges from spec - feeds cross-review |
| **status** | Workflow progress dashboard | Shows where you are in the SDD lifecycle |

Install without companions: add `--minimal` flag to the init script.

## Configuration

After install, optionally edit `orca-config.yml`:

```yaml
crossreview:
  agent: null                # canonical reviewer selection
  harness: null              # legacy alias during migration
  model: null                # model override
  effort: "high"             # reasoning effort
  ask_on_ambiguous: true      # deferred: backend stays deterministic for now
  remember_last_success: true # advisory memory gate when reviewer memory is supplied

exclusions:
  - ".specify/scripts/*"    # vendor code
  - ".specify/templates/*"  # upstream templates
```

Tier 1 supported and auto-selectable reviewer agents are `codex`, `claude`,
`gemini`, and `opencode`. `cursor-agent` is supported only when explicitly
selected; it is not auto-selected. If `crossreview.agent` is left `null`, Orca
prefers a different installed Tier 1 reviewer than the current provider so the
result is actually cross-agent when possible. `ask_on_ambiguous` is documented
for future workflow-level prompting, but the backend currently uses a
deterministic highest-priority fallback instead of interactive escalation.

## Architecture

This extension is designed to work alongside — not replace — other tools:

- **Spec Kit** (upstream, unmodified) — the base process layer
- **This extension** — brainstorming, quicktasks, code review, PR review, assignment, cross-review, self-improvement
- **cc-spex** (optional) — workflow traits, hooks, and gates
- **Mneme** (optional) — durable memory across sessions and projects

## License

MIT
