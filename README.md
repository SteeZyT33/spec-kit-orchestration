# spec-kit-orchestration

Spec-compliant workflow orchestration, code review, PR review, agent-to-task assignment, cross-harness adversarial review, and process self-improvement for [Spec Kit](https://github.com/github/spec-kit).

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

```
/speckit.orca.brainstorm                 # create or refine brainstorm artifact
/speckit.orca.brainstorm --feature 004   # target an existing feature explicitly
```

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

Invokes a different AI harness (Codex, Claude, Gemini) to adversarially review design artifacts or code changes.

```
/speckit.orca.cross-review               # Adversarial review with alternate harness
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
| **reconcile** | Drift detection and spec repair | Catches when code diverges from spec — feeds cross-review |
| **status** | Workflow progress dashboard | Shows where you are in the SDD lifecycle |

Install without companions: add `--minimal` flag to the init script.

## Configuration

After install, optionally edit `orchestration-config.yml`:

```yaml
crossreview:
  harness: null         # auto-pick a different installed provider when possible
  model: null            # model override
  effort: "high"         # reasoning effort

exclusions:
  - ".specify/scripts/*"    # vendor code
  - ".specify/templates/*"  # upstream templates
```

If `crossreview.harness` is left `null`, Orca should prefer a provider that is
different from the current integration so the review is actually cross-harness.

## Architecture

This extension is designed to work alongside — not replace — other tools:

- **Spec Kit** (upstream, unmodified) — the base process layer
- **This extension** — brainstorming, quicktasks, code review, PR review, assignment, cross-review, self-improvement
- **cc-spex** (optional) — workflow traits, hooks, and gates
- **Mneme** (optional) — durable memory across sessions and projects

## License

MIT
