---
description: Single-lane execution runner. Starts, resumes, and manages full-cycle workflow runs from brainstorm through PR-ready completion using event-sourced state.
scripts:
  sh: scripts/bash/check-prerequisites.sh --json
  ps: scripts/powershell/check-prerequisites.ps1 -Json
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

Use `/speckit.orca.yolo` to run a feature through the full Orca workflow
with durable state tracking. The runtime is event-sourced: every stage
transition is recorded in an append-only JSONL log, and state is derived
by replaying the log through a deterministic reducer.

**Subcommands**: `start`, `next`, `resume`, `status`, `recover`, `cancel`, `list`

## Runtime

```bash
uv run python -m speckit_orca.yolo start <feature-id> [--stage brainstorm] [--actor claude]
uv run python -m speckit_orca.yolo next <run-id> [--result success|failure|blocked] [--reason "..."]
uv run python -m speckit_orca.yolo resume <run-id>
uv run python -m speckit_orca.yolo recover <run-id>
uv run python -m speckit_orca.yolo status <run-id>
uv run python -m speckit_orca.yolo cancel <run-id>
uv run python -m speckit_orca.yolo list
```

## Prompt body

> Stub — full prompt deferred per runtime-plan section 4.
> The runtime module at `src/speckit_orca/yolo.py` is the authoritative
> implementation. This command file will be expanded with a full
> operator-facing prompt once the runtime stabilizes across PRs C-F.
