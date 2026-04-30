---
description: Diagnose orca install - check orca-cli on PATH, .specify/ wiring, SKILL.md presence/validity, and reviewer backend availability.
handoffs:
  - label: Reinstall Orca
    agent: bash
    prompt: Re-run /tmp/install-phase3-orca.sh against this repo to fix missing extension files.
  - label: Re-Sync Skills
    agent: bash
    prompt: Run `bash .specify/extensions/orca/scripts/bash/sync-skills.sh` to regenerate SKILL.md from current command files.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

`doctor` is a non-destructive health check for an orca install. It runs the
five-check diagnostic at `.specify/extensions/orca/scripts/bash/orca-doctor.sh`
(or the in-tree equivalent at `scripts/bash/orca-doctor.sh`) and reports each
check on its own line.

The exit code is informative, not advisory:

- **0** - all critical checks passed (orca-cli + .specify + SKILL.md).
- **1** - at least one critical check failed.

Reviewer-backend checks (`ANTHROPIC_API_KEY`, `codex` CLI, `ORCA_REVIEWER_TIMEOUT_S`)
are reported as warnings and do not change the exit code.

If `.orca/adoption.toml` is present (Spec 015 brownfield adoption), doctor also
validates the manifest's schema. A malformed manifest is reported as a warning
but does not change the exit code. Absence of `.orca/adoption.toml` is informational
(orca not adopted in this repo; run `orca-cli adopt` to install).

## Workflow Contract

- Resolve the doctor script: prefer `.specify/extensions/orca/scripts/bash/orca-doctor.sh`; fall back to in-tree `scripts/bash/orca-doctor.sh` when running from the orca source repo.
- Run it. Capture stdout and the exit code.
- Echo the output verbatim to the user.
- Summarize: if exit 0, say healthy. If exit 1, list the failed checks and recommend the relevant handoff.

## Outline

1. Resolve the script:

   ```bash
   if [[ -x .specify/extensions/orca/scripts/bash/orca-doctor.sh ]]; then
     DOCTOR=.specify/extensions/orca/scripts/bash/orca-doctor.sh
   elif [[ -x scripts/bash/orca-doctor.sh ]]; then
     DOCTOR=scripts/bash/orca-doctor.sh
   else
     echo "orca-doctor.sh not found. Reinstall orca or run from the orca source tree." >&2
     exit 1
   fi
   ```

2. Run it and capture exit:

   ```bash
   bash "$DOCTOR"
   doctor_exit=$?
   ```

3. Report findings to the operator.

   - If `doctor_exit` is 0, report "orca install is healthy".
   - If `doctor_exit` is 1, list the failed checks and suggest the appropriate handoff:
     - SKILL.md check failed -> "Re-Sync Skills" handoff (sync-skills.sh).
     - orca-cli or .specify check failed -> "Reinstall Orca" handoff.
     - Bundled extension import warning -> investigate `.specify/extensions/orca/src` integrity.

4. If reviewer-backend warnings are present (ANTHROPIC_API_KEY unset, codex
   missing), surface them as advisory only. They do not block any orca
   functionality unless the operator runs review-spec or review-code.

## Errors

If the doctor script fails to execute (permission denied, missing python3,
etc.), surface the underlying error verbatim and recommend a reinstall.
