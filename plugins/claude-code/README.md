# Orca - Claude Code Plugin

This plugin registers the orca cross-agent review and SDD-gate slash commands
inside a Claude Code host.

## What gets installed

When the orca extension is added to a spec-kit repo (via `specify extension add`
or the direct-copy installer at `/tmp/install-phase3-orca.sh`), three things
land in the host:

- **7 SKILL.md wrappers** at `.claude/skills/orca-{brainstorm,cite,gate,review-code,review-pr,review-spec,tui}/SKILL.md`. These make the slash commands user-invocable.
- **`extension.yml` registration** at `.specify/extensions/orca/extension.yml`, listing the 7 commands plus hooks.
- **Source command files** at `.specify/extensions/orca/plugins/claude-code/commands/*.md`. These are the prompts the skills wrap.
- **Helper scripts** at `.specify/extensions/orca/scripts/bash/`.

## Slash commands

| Command | Purpose |
| --- | --- |
| `/orca:gate <stage>` | SDD completion-gate lint for `plan-ready`, `implement-ready`, `pr-ready`, `merge-ready`. |
| `/orca:cite <path>` | Validate citations and ref hygiene in synthesis text. |
| `/orca:review-spec` | Cross-agent adversarial review of a clarified spec. |
| `/orca:review-code` | Self+cross review per user-story phase. |
| `/orca:review-pr` | PR comment disposition and merge retro. |
| `/orca:brainstorm` | Pre-spec ideation that captures options and recommendation. |
| `/orca:tui` | Live awareness pane: review queue + event feed. |
| `/orca:doctor` | Health check: orca-cli, .specify wiring, SKILL.md, reviewer backends. |

## Resolving orca-cli

The slash commands shell out to `orca-cli`. There are three install paths; the
Prerequisites block in each command file walks the resolution chain in order:

1. **`uv tool install /path/to/spec-kit-orca`** - puts `orca-cli` on PATH. Recommended for daily-driver setups.
2. **`export ORCA_PROJECT=/path/to/spec-kit-orca`** - commands resolve via `uv run --project "$ORCA_PROJECT" orca-cli`.
3. **`~/spec-kit-orca` fallback** - automatic when the source tree is cloned at that path. No env var needed.

If none of the three resolve, the command file prints a one-line error and exits.

## Live reviewer backends

`/orca:review-spec` and `/orca:review-code` invoke external reviewer adapters.
These are best-effort and skipped gracefully if missing:

- **`ANTHROPIC_API_KEY`** - required for the `claude` reviewer (Anthropic SDK). The reviewer makes an HTTP call to `api.anthropic.com`; not the same as the in-session host Claude.
- **Authenticated `codex` CLI** - run `codex login` once. Used by the `codex` reviewer.
- **`ORCA_REVIEWER_TIMEOUT_S=<seconds>`** - override the codex reviewer's default 120s timeout. Bump it for large patches.

## Re-syncing skills after edits

If you edit a source command file at `.specify/extensions/orca/plugins/claude-code/commands/*.md`, the corresponding SKILL.md does not auto-regenerate. Re-sync with:

```bash
bash .specify/extensions/orca/scripts/bash/sync-skills.sh
```

This force-regenerates all 7 SKILL.md wrappers from the current command files.

## Health check

To confirm the install is wired correctly, run:

```bash
/orca:doctor
```

Or directly:

```bash
bash .specify/extensions/orca/scripts/bash/orca-doctor.sh
```

Exits 0 when orca-cli, `.specify/`, and the 7 SKILL.md files are all healthy.
Reviewer-backend availability is reported as warnings, not failures.

## Known issues

Phase 3.2 backlog tracking documentation gaps, validator over-flagging, and
adapter identity collapse: see `docs/superpowers/notes/2026-04-27-phase-3-2-backlog.md`
in the orca source tree.
