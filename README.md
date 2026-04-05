# spec-kit-orchestration

Spec-compliant code review, agent-to-task assignment, and cross-harness adversarial review for [Spec Kit](https://github.com/github/spec-kit).

## What this does

Three commands that bridge the gap between writing specs and shipping reviewed code:

**`/speckit.review`** validates implementation against spec artifacts (compliance, code quality, security), applies tiered fixes (auto-fix trivial, suggest medium, flag complex), creates phase PRs, and manages the full GitHub comment response cycle including thread resolution.

**`/speckit.assign`** matches agents to tasks based on capability detection, expertise lenses, and confidence scoring. Reads tasks.md and available agent profiles to produce assignment recommendations.

**`/speckit.crossreview`** invokes a different AI harness (Codex, Claude, Gemini) to adversarially review design artifacts or code changes. Uses structured JSON contracts so the reviewing harness operates independently.

## Install

```bash
specify extension add orchestration --from https://github.com/SteeZyT33/spec-kit-orchestration/archive/refs/tags/v1.0.0.zip
```

Or for local development:

```bash
specify extension add --dev /path/to/spec-kit-orchestration
```

## Usage

After implementation:

```
/speckit.review                    # Full review with tiered fixes + PR
/speckit.review --security         # Force security pass
/speckit.review --comments-only    # Process new PR comments only
/speckit.review --post-merge       # Check for silent reversions
```

Before implementation:

```
/speckit.assign                    # Assign agents to tasks
/speckit.assign focus on security  # Bias assignment toward security expertise
```

After review:

```
/speckit.crossreview               # Adversarial review with alternate harness
/speckit.crossreview --scope code  # Review code only (not design artifacts)
```

## How review works

1. Loads spec.md, plan.md, tasks.md, and any contracts/data-model from the feature directory
2. Runs three passes: spec compliance, code quality, security (conditional)
3. Applies tiered fixes: auto-fix trivial issues, suggest medium fixes (with approval), flag complex issues
4. Checks for merge conflicts with a 4-tier resolution protocol
5. Creates a phase PR with review summary
6. Processes all PR comments with ADDRESSED/REJECTED/ISSUED/CLARIFY responses
7. Resolves conversation threads via GraphQL for branch protection compliance

## How crossreview works

1. Reads review scope (design artifacts or code changes)
2. Launches an alternate AI harness as a subprocess
3. Passes structured context via a JSON contract
4. Parses structured findings from the harness output
5. Merges findings into the review report

## Configuration

After install, optionally create `orchestration-config.yml` in your project root:

```yaml
crossreview:
  harness: "codex"      # codex, claude, or gemini
  model: null            # model override (null = harness default)
  effort: "high"         # reasoning effort level
```

## Works with

- **Spec Kit** (required) -- the base spec-driven workflow
- **cc-spex** (recommended) -- workflow traits, hooks, and gates
- **GitHub MCP Server** (optional) -- enables PR creation and comment management

## License

MIT
