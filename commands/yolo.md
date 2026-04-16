---
description: Single-lane execution runner. Event-sourced full-cycle workflow driver. Start, advance, resume, or recover a run through brainstorm → implement → review → pr-ready with durable state, review gates, and bounded retry.
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

Use `/speckit.orca.yolo` to drive a feature through the full Orca workflow
with durable state tracking. Unlike `/speckit.implement` (which executes a
single stage), `yolo` is a **resumable orchestrator** that:

- reads durable artifacts (spec, plan, tasks, review files)
- computes the next decision via a pure-function reducer over an event log
- advances the stage only when the caller reports success on the current one
- enforces review gates (review-spec → plan, review-code → pr-ready)
- stops safely on failures, blockers, missing prerequisites
- supports both **standalone** mode (direct operator) and
  **matriarch-supervised** mode (lane agent with dual-write to matriarch mailbox)

The runtime source of truth is an append-only JSONL event log at
`.specify/orca/yolo/runs/<run-id>/events.jsonl`. State is derived by
replaying events through `speckit_orca.yolo.reduce()` — always
deterministic.

## Stage model (happy path)

```text
brainstorm → specify → clarify → review-spec
           → plan → tasks → assign (optional) → implement
           → review-code → pr-ready [→ pr-create → review-pr]
```

Review gates:

- **plan** cannot execute until `review_spec_status == "complete"`
- **pr-ready** cannot execute until `review_code_status == "complete"`

Terminal: `pr-ready` by default. `pr-create` is explicit opt-in per
`specs/009-orca-yolo/contracts/orchestration-policies.md`.

## Subcommands

```bash
uv run python -m speckit_orca.yolo --root <repo> <subcommand> [args]
```

| Subcommand | Purpose |
|---|---|
| `start <feature-id>` | Begin a new run. `--stage` picks a start stage (default `brainstorm`). `--mode standalone\|matriarch-supervised`. `--lane-id` required in supervised mode. |
| `next <run-id>` | Query the current decision (read-only). Pass `--result success\|failure\|blocked` to advance. `--reason` and `--evidence` as appropriate. |
| `resume <run-id>` | Replay the event log and return the current decision. In supervised mode, consults matriarch's lane registry (FR-018). |
| `recover <run-id>` | Reconcile supervised-mode lane reassignment or unregistration. Requires `--confirm-reassignment` + `--reason` when supervised lane state has changed. (Stale-run and head-commit drift overrides are planned but not yet implemented; see runtime-plan §10.) |
| `status <run-id>` | Print the current `RunState` (stage, outcome, review statuses, `matriarch_sync_failed`). |
| `cancel <run-id>` | Emit a terminal event with `reason="canceled by operator"`. Run outcome becomes `canceled`. |
| `list` | Enumerate all runs under `.specify/orca/yolo/runs/`. |

## Pre-Execution Checks

**Check for extension hooks (before yolo runs)**:

- If `.specify/extensions.yml` does not exist, skip silently.
- If it exists, read it and inspect `hooks.before_yolo`.
- If the YAML is invalid, ignore extension hooks for this run and continue.
- If `hooks.before_yolo` is missing, not a list, or empty, skip silently.
- Filter out hooks where `enabled` is explicitly `false`. Hooks without an `enabled` field are enabled by default.
- Do not interpret `condition` expressions yourself — if a hook has a non-empty `condition`, skip it and leave evaluation to the HookExecutor implementation. If the field is absent or null, treat the hook as executable.
- For each remaining hook, surface it using the same heading convention as `commands/review-code.md`:
  - Use **Optional Pre-Hook** when `optional: true` (operator confirmation/input required before running)
  - Use **Automatic Pre-Hook** when `optional: false` (runs automatically without operator confirmation)
- Do NOT use a combined `**Optional/Automatic Pre-Hook**` label.

## Outline

1. Run `{SCRIPT}` from repo root and parse `FEATURE_DIR` or `--root`.

2. Parse arguments:
   - subcommand (`start | next | resume | recover | status | cancel | list`)
   - per-subcommand flags per the table above
   - any remaining text: additional intent the model should consider

3. **For `start`**:

   a. Resolve `<feature-id>` to a spec directory under `specs/<feature-id>/`
      (full-spec only — spec-lite `SL-*` and adoption `AR-*` are rejected
      per `specs/009-orca-yolo/contracts/orchestration-policies.md`
      Start Artifact Restrictions).

   b. Verify the chosen `--stage` has its upstream artifacts on disk:
      - `brainstorm` requires nothing
      - `specify` onward requires spec.md
      - `plan` onward requires spec.md + `## Clarifications` section
        (produced by `/speckit.clarify`; see
        `specs/012-review-model/contracts/clarify-integration.md`)
      - `implement` onward requires plan.md + tasks.md
      - `review-code` requires implementation evidence

      If prerequisites missing, STOP and explain which files are needed
      before `--stage` is valid.

   c. Choose mode:
      - **standalone**: single operator, no matriarch involvement
      - **matriarch-supervised**: requires `--lane-id`. The lane MUST be
        registered via `/speckit.orca.matriarch` before calling `yolo start`.
        Standalone is the default.

   d. Invoke:

      ```bash
      uv run python -m speckit_orca.yolo --root "$REPO_ROOT" start "$FEATURE_ID" \
        --actor "${ORCA_ACTIVE_AGENT:-claude}" \
        --branch "$(git rev-parse --abbrev-ref HEAD)" \
        --sha "$(git rev-parse HEAD)" \
        [--stage <stage>] [--mode <mode>] [--lane-id <lane>]
      ```

   e. Print the returned `run_id` and the first decision (what to do now).

4. **For `next`**:

   a. If called without `--result`, this is a read-only query. Print the
      current decision: `kind`, `next_stage`, `prompt_text`, and whether
      `requires_confirmation` is set.

   b. If called with `--result`, the caller has executed the stage and
      reports the outcome. Collect `--reason` (required for `failure`/
      `blocked`) and `--evidence` (optional, list of artifact paths that
      prove the result).

   c. After `next --result`, print the NEW decision. Loop or stop based
      on its `kind`:
      - `step`: execute `next_stage`, report back via `next --result`
      - `decision_required`: operator input needed (typically a review
        gate or clarify pending). Resolve the block, then call again.
      - `blocked`: run is stopped. Either call `recover` after operator
        inspection, or `cancel`.
      - `terminal`: run is complete. Inspect `status` for outcome.

5. **For `resume`**:

   a. Replays the event log and returns the current decision.

   b. In supervised mode, consults matriarch's lane registry. If the lane
      owner changed or the lane was unregistered since the run started,
      `resume` raises. Operator must use `recover` with confirmation.

6. **For `recover`**:

   a. Used when the operator has inspected a supervised-mode lane
      reconciliation issue (lane reassignment or lane unregistration
      detected via the matriarch lane registry) and explicitly decides
      to continue.

   b. In supervised mode with a changed lane, MUST pass
      `--confirm-reassignment` AND `--reason`. Without them, `recover`
      raises ValueError. This makes the override an auditable action.

   c. Do NOT treat `recover` as enforcing stale-run thresholds or
      `head_commit_sha` drift checks. Those are planned extensions
      per runtime-plan §10 but are not implemented today. Operators
      may still inspect for those conditions manually, but `recover_run`
      does not gate on them.

7. **For `status`**:

   a. Print `RunState` fields: `current_stage`, `outcome`, `block_reason`,
      `review_spec_status`, `review_code_status`, `review_pr_status`,
      `retry_counts`, `matriarch_sync_failed`, `last_event_timestamp`.

   b. If `matriarch_sync_failed` is True in a supervised run, SURFACE
      the warning prominently — matriarch visibility is lost and the
      supervised health signal is no longer reliable.

8. **For `cancel`**:

   a. Confirm with the operator unless `$ARGUMENTS` indicates the user
      already explicitly requested cancellation.

   b. Invoke `cancel` subcommand. Run outcome becomes `canceled`.

9. **For `list`**:

   a. Enumerate all run directories and their outcomes. Group by feature
      when multiple runs share a feature_id.

## Supervised-mode specifics

When `--mode matriarch-supervised`:

- Events dual-write to both yolo's event log AND matriarch's channels:
  - `RUN_STARTED` → matriarch reports queue as startup ACK (per 010
    `lane-mailbox.md` §V1 Rules)
  - Status events (stage entered, cross-pass requested/completed,
    unblock, terminal) → matriarch reports queue
  - Blockers (block, stage_failed) → matriarch mailbox as `blocker`
  - Decision required at review gate → mailbox as `approval_needed`
  - Decision required elsewhere → mailbox as `question`
- Sender identity on all mirrored events: `lane_agent:<lane_id>` per
  `event-envelope.md`
- If the mirror write fails, a `.matriarch_sync_failed` marker is set
  and future `status` / `list` calls show the lost visibility

## Guardrails

- NEVER start a run with a spec-lite or adoption record as the anchor.
  Both are rejected by the runtime; surface the error.
- NEVER silently advance past a review gate. If the gate blocks,
  operator must resolve (run the cross-pass, update the review artifact)
  before `next --result success` will advance.
- NEVER call `recover` without confirming you understand what you're
  overriding (supervised lane reassignment or unregistration).
- NEVER treat an `outcome == "canceled"` run as resumable. Canceled is
  terminal.

## Output

After each invocation, print:

- subcommand invoked and arguments
- run_id (for start, or the input for others)
- resulting decision `kind` + `next_stage` + `prompt_text`
- path to `.specify/orca/yolo/runs/<run-id>/` for evidence inspection
- any blockers or ambiguities encountered

## Completion

Check `.specify/extensions.yml` for `hooks.after_yolo` and surface any
optional or mandatory hooks. If `review-code` hasn't run yet for the
implementation phase, suggest `/speckit.orca.review-code` per the
standard flow.
