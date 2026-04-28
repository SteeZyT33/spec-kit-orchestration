# Orca for Codex

Orca is a repo-backed capability library for agentic engineering governance. It does NOT execute host runtimes; it provides JSON-in JSON-out capabilities you can shell out to from within a Codex session.

## What Orca Is NOT

- Not a scheduler, worker runtime, supervisor, or control plane
- Not a daemon, presence system, or live state watcher
- Not a primary store for review or flow state (the host or repo owns that)

LLM-backed capabilities (`cross-agent-review`, `contradiction-detector`) produce **findings and hypotheses, not formal proof**. Hosts decide how findings affect actions.

## CLI Surface

The canonical entry point is `orca-cli`. Six capabilities are available:

| Capability | What it does | README |
|------------|--------------|--------|
| `cross-agent-review` | Bundle a review subject (spec, diff, pr, claim-output), dispatch to claude/codex/cross, return structured findings with stable dedupe IDs | `docs/capabilities/cross-agent-review/README.md` |
| `worktree-overlap-check` | Pure-Python detection of path conflicts between active worktrees and proposed writes | `docs/capabilities/worktree-overlap-check/README.md` |
| `flow-state-projection` | Project an SDD feature directory into a JSON snapshot of stage / milestones / next step | `docs/capabilities/flow-state-projection/README.md` |
| `completion-gate` | Decide whether a feature has cleared gates for a target stage (`plan-ready`, `implement-ready`, `pr-ready`, `merge-ready`) | `docs/capabilities/completion-gate/README.md` |
| `citation-validator` | Rule-based detection of uncited claims and broken refs in synthesis text | `docs/capabilities/citation-validator/README.md` |
| `contradiction-detector` | Cross-agent-review with a fixed contradiction prompt; surfaces conflicts between new content and prior evidence | `docs/capabilities/contradiction-detector/README.md` |

Each capability has an input schema (`docs/capabilities/<name>/schema/input.json`) and output schema (`docs/capabilities/<name>/schema/output.json`).

## Universal Result Envelope

Every `orca-cli` invocation returns this JSON shape on stdout:

```json
{
  "ok": true,
  "result": { /* capability-specific shape, see output.json schemas */ },
  "metadata": {
    "capability": "...",
    "version": "0.1.0",
    "duration_ms": 123
  }
}
```

On failure:

```json
{
  "ok": false,
  "error": {
    "kind": "input_invalid" | "backend_failure" | "timeout" | "internal",
    "message": "...",
    "detail": { /* optional structured context */ }
  },
  "metadata": { ... }
}
```

## Exit Codes

- `0` - success
- `1` - capability returned `Err(...)` (input/backend/internal error)
- `2` - argv parse error (missing required flag, bad value)
- `3` - unknown capability subcommand

## Reviewer Backend Selection

LLM-backed capabilities (`cross-agent-review`, `contradiction-detector`) need reviewer backends configured via env vars:

- `ORCA_FIXTURE_REVIEWER_CLAUDE=<path>` - replay a JSON fixture as if it were a Claude response (test mode)
- `ORCA_FIXTURE_REVIEWER_CODEX=<path>` - replay a JSON fixture as if it were a Codex response (test mode)
- `ORCA_LIVE=1` - enable real backends (Anthropic SDK for claude, `codex` CLI shellout for codex)

If neither is set, the capability returns `Err(INPUT_INVALID)` with `message="reviewer not configured"`.

### Live Backend Prerequisites

When `ORCA_LIVE=1` is set:

- **claude reviewer** uses the Anthropic SDK directly (`anthropic.Anthropic()`).
  Requires `ANTHROPIC_API_KEY` (or `ANTHROPIC_AUTH_TOKEN`) in the host
  environment. The SDK calls `api.anthropic.com` over HTTP - this is a
  separate Claude session from any in-session Claude that may have
  invoked the slash command.
- **codex reviewer** shells out to the `codex` CLI. Requires `codex login`
  to have been completed in the host environment (`codex auth status` to
  verify).
- **timeout** for the codex reviewer is 120 seconds by default. Set
  `ORCA_REVIEWER_TIMEOUT_S=<seconds>` to override (e.g., `300` for large
  diffs). Codex reviewer rejects non-positive or non-integer values and
  warns to stderr.

If a required prerequisite is missing, the capability returns an
`Err(BACKEND_FAILURE)` envelope with a specific message about which
reviewer failed and why (e.g., "Could not resolve authentication method"
for missing API key, "codex timeout after 120s" for timeout exhaustion).

## Invocation Patterns

### Single capability call

```bash
orca-cli cross-agent-review \
  --kind diff \
  --target src/foo.py \
  --feature-id 001-foo \
  --reviewer cross
```

### Pretty mode (human-readable)

Append `--pretty` to any subcommand for a human-friendly summary instead of JSON. Useful for interactive sessions; do not parse the pretty output.

### Reading from stdin

`worktree-overlap-check` reads JSON from stdin (or `--input <file>`):

```bash
echo '{"worktrees":[]}' | orca-cli worktree-overlap-check
```

### Listing capabilities

```bash
orca-cli --list
```

## Don't

- Don't parse the `--pretty` output. JSON is the contract.
- Don't assume any capability "blocks" by itself; orca returns Result envelopes, the caller decides.
- Don't extend orca by adding new state stores. Add new capabilities (small functions returning Result) instead.
- Don't import from `orca.capabilities.*` modules across capability boundaries; each capability is independent.

## Where Things Live

- Capability sources: `src/orca/capabilities/`
- Reviewer adapters: `src/orca/core/reviewers/`
- JSON schemas: `docs/capabilities/<name>/schema/`
- Capability READMEs: `docs/capabilities/<name>/README.md`
- This doc: `plugins/codex/AGENTS.md`
