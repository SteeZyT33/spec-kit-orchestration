# spec-kit-orchestration

Spec-compliant code review, agent-to-task assignment, cross-harness adversarial review, and process self-improvement for [Spec Kit](https://github.com/github/spec-kit).

## Quick Start

From inside any project directory:

```bash
speckit-orchestrate              # default: claude
speckit-orchestrate codex        # different agent
speckit-orchestrate --minimal    # no companion extensions
```

This installs:
- **Spec Kit** (core) — specify, plan, tasks, implement, analyze, clarify, constitution, checklist
- **Orchestration** (this extension) — review, assign, crossreview, self-review
- **Superb** (companion) — TDD enforcement, verification gates, debug protocol, superpowers bridge
- **Verify** (companion) — evidence-based completion validation
- **Reconcile** (companion) — spec-implementation drift detection
- **Status** (companion) — workflow progress dashboard

## Commands

### `/speckit.review`

Validates implementation against spec artifacts (compliance, code quality, security), applies tiered fixes (auto-fix trivial, suggest medium, flag complex), creates phase PRs, and manages the full GitHub comment response cycle including thread resolution.

```
/speckit.review                    # Full review with tiered fixes + PR
/speckit.review --security         # Force security pass
/speckit.review --comments-only    # Process new PR comments only
/speckit.review --post-merge       # Check for silent reversions
```

### `/speckit.assign`

Matches agents to tasks based on capability detection, expertise lenses, and confidence scoring.

```
/speckit.assign                    # Assign agents to tasks
/speckit.assign focus on security  # Bias toward security expertise
```

### `/speckit.crossreview`

Invokes a different AI harness (Codex, Claude, Gemini) to adversarially review design artifacts or code changes.

```
/speckit.crossreview               # Adversarial review with alternate harness
/speckit.crossreview --scope code  # Review code only
```

### `/speckit.self-review`

Process retrospective — NOT a code review. Evaluates what worked and what didn't across the full spec-driven workflow, then dispatches agents to automatically improve extension commands based on findings.

```
/speckit.self-review               # Full process retrospective
```

Evaluates five dimensions: spec fidelity, plan accuracy, task decomposition, review effectiveness, and workflow friction. Low/medium risk improvements are auto-applied to extension commands. High risk improvements are deferred for human review.

## Recommended Workflow

```
specify → plan → tasks → assign → implement → review → crossreview → self-review
                                      ↑                                    |
                                      └────── improvements flow back ──────┘
```

The self-review loop is what makes this self-improving: each feature you ship makes the orchestration commands better for the next feature.

## Companion Extensions

These are installed automatically by `speckit-orchestrate`. They work independently but complement the orchestration workflow:

| Extension | What it adds | Why |
|---|---|---|
| **superb** | TDD gates, verification, debug protocol, superpowers bridge | Enforces test-first development and evidence-based completion |
| **verify** | Post-implementation completion gate | Prevents false task completions — complements review |
| **reconcile** | Drift detection and spec repair | Catches when code diverges from spec — feeds crossreview |
| **status** | Workflow progress dashboard | Shows where you are in the SDD lifecycle |

Install without companions: add `--minimal` flag to the init script.

## Configuration

After install, optionally edit `orchestration-config.yml`:

```yaml
crossreview:
  harness: "codex"      # codex, claude, or gemini
  model: null            # model override
  effort: "high"         # reasoning effort

exclusions:
  - ".specify/scripts/*"    # vendor code
  - ".specify/templates/*"  # upstream templates
```

## Architecture

This extension is designed to work alongside — not replace — other tools:

- **Spec Kit** (upstream, unmodified) — the base process layer
- **This extension** — review, assignment, cross-review, self-improvement
- **cc-spex** (optional) — workflow traits, hooks, and gates
- **Mneme** (optional) — durable memory across sessions and projects

## License

MIT
