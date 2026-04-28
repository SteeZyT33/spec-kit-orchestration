# Phase 3.2 Backlog

**Source:** Three parallel claude verification sessions ran orca Phase 3 against fresh installs in `/home/taylor/spec-kit-orca`, `/home/taylor/MemWell`, `/home/taylor/perf-lab` on 2026-04-27. Logs at `/tmp/orca-verify-logs/{spec-kit-orca,memwell,perflab}.log`.

**Status:** Convergent findings already addressed in Phase 3 (commit `ac0c45f` Prerequisites + tui frontmatter). The items below are deferred capability-level or design-level work that surfaced during verification.

## Capability-level work

### 1. Citation validator over-flags non-prose content

All three sessions flagged the same issue: `citation-validator` reports `Coverage: **6%**` against typical spec.md / README.md content because the heuristic treats:

- Lines inside fenced code blocks (` ```bash`, ` ```python`, etc.) as prose claims
- Markdown table rows (pipe-delimited cells) as separate claims
- Spec-kit scaffolding patterns: `**FR-001**: ...`, `### Session 2026-04-25`, `**Field**:`, `Run N/3:`
- Brackets without `[ref:...]` or `[#...]` prefix as broken refs (e.g., `[all: 1440 1438 1445]`)

**Fix surface:** `src/orca/capabilities/citation_validator/`. Add a markdown-aware preprocessing pass that:
- Strips fenced code blocks before sentence splitting
- Skips lines that match the markdown table-row pattern `^\|.*\|$`
- Maintains a skip-list of spec-kit scaffolding patterns (configurable via `--skip-pattern` repeatable flag)
- Tightens the broken-ref detector to require `[ref:NAME]`, `[NAME.md]`, or `[#NAME]` form (not bare `[anything: with colons]`)

**Tests to add:** fixture markdown files representing each false-positive class, asserting they don't appear in `uncited_claims` or `broken_refs`.

### 2. Citation default reference set should auto-discover, not hardcode

`plugins/claude-code/commands/cite.md:44-46` describes a default reference set of `events.jsonl`, `experiments.tsv`, `specs/<feature>/research.md`. Two of those are MemWell-specific artifacts; not generic.

**Fix:** Replace with auto-discovery from the resolved feature dir:
- `plan.md`, `data-model.md`, `research.md`, `quickstart.md`, `tasks.md`, `contracts/**/*.md`

Both the slash command markdown AND the `--reference-set` default (if any) in the capability code should change.

### 3. completion-gate `duration_ms` rounds to 0 for fast runs

The completion_gate capability runs in <1ms for typical `plan-ready` checks (just `spec.md` existence + `[NEEDS CLARIFICATION]` grep). `int((time.monotonic() - started) * 1000)` truncates submillisecond durations to 0, which the renderer prints as `_duration: 0ms_`.

This is technically correct but operator-misleading.

**Fix options:**
- (A) Use microseconds in the envelope: `duration_us` field, renderer formats as `0.3ms` for sub-millisecond
- (B) Use float milliseconds with `.1f` precision
- (C) Document that 0ms means <1ms and accept the loss of granularity

(B) is the smallest diff; (A) is more correct.

### 4. completion-gate at `plan-ready` evaluates only 2 gates

Verification showed only `spec_exists` and `no_unclarified` evaluated at `plan-ready`. Either expand the gate set (e.g., `clarifications_resolved`, `acceptance_criteria_present`) or document why those two are sufficient.

**Fix surface:** `src/orca/capabilities/completion_gate/` gate registry per stage.

### 5. Skill sync mechanism - DONE (2026-04-27)

`.specify/extensions/orca/plugins/claude-code/commands/*.md` source files have no auto-sync to `.claude/skills/orca-*/SKILL.md` after install. If an operator edits a source command file, the SKILL stays stale.

**Fix:** Add `bash .specify/extensions/orca/scripts/bash/sync-skills.sh` that re-runs the skill generator from `orca-main.sh:generate_extension_skills`. Mention it in the install README.

**Resolution:** Added `scripts/bash/sync-skills.sh` (commit `a25e356`). Force-regenerates every SKILL.md from current command files; reads `.specify/integration.json` to pick the target skills dir. Mentioned in the new install README (item 6).

## Documentation / install work

### 6. `.specify/extensions/orca/README.md` install doc - DONE (2026-04-27)

No README in the installed extension directory. Operators don't know:
- Where `orca-cli` comes from
- How to install spec-kit-orca so the script is on PATH
- What `ORCA_PROJECT` does
- How to re-sync skills after editing command files

**Fix:** Write a 30-line README at `plugins/claude-code/README.md` (or `docs/install.md`) covering the three install paths (`uv tool install`, `ORCA_PROJECT` env, `~/spec-kit-orca` fallback) and the SKILL.md regeneration command.

**Resolution:** Added `plugins/claude-code/README.md` (commit `268cfe6`). 81 lines covering installed artifacts, all 8 slash commands, the three orca-cli resolution paths, live-reviewer prerequisites (ANTHROPIC_API_KEY / codex / ORCA_REVIEWER_TIMEOUT_S), sync-skills entry, and the doctor health check. The install script copies plugins/ wholesale, so it lands at `.specify/extensions/orca/plugins/claude-code/README.md` automatically.

### 7. `orca:doctor` health-check command - DONE (2026-04-27)

A `/orca:doctor` slash command (and/or `orca-cli check` capability) that verifies:
- `orca-cli` is on PATH (or one of the fallback paths resolves)
- `.specify/` directory exists and has `init-options.json`
- The 7 SKILL.md files exist and have valid frontmatter
- Bundled extension source is loadable
- Any required env vars (`ORCA_PROJECT`) resolve

Would shave 10 minutes off every "why doesn't it work" cycle.

**Resolution:** Added `plugins/claude-code/commands/doctor.md` slash command and `scripts/bash/orca-doctor.sh` (commit `a925a9b`). Implements the five checks above plus reviewer-backend availability (advisory). Registered as `speckit.orca.doctor` in extension.yml so the install auto-generates `orca-doctor` SKILL.md. Smoke-tested on `/home/taylor/spec-kit-orca`: 4/4 critical checks pass, exit 0.

## Design-level / Phase 4 work

### 8. spec-kit validator rejects `orca:*` naming

`specify extension add --dev /path/to/orca` fails with:

```
Validation Error: Invalid command name 'orca:brainstorm': must follow pattern 'speckit.{extension}.{command}'
```

Phase 1 of the v1 rebuild renamed slash commands from `speckit.orca.{cmd}` to `orca:{cmd}`, but spec-kit's extension-catalog validator still requires the legacy prefix. The direct-copy install at `/tmp/install-phase3-orca.sh` bypasses this, but `specify extension add` is broken for orca.

**Fix options:**
- (A) Restore `speckit.orca.{cmd}` naming in `extension.yml provides.commands` while keeping file basenames `gate.md` etc. for `orca:gate` skill invocation. The validator and the slash invocation are decoupled.
- (B) Patch spec-kit's validator to allow `{namespace}:{command}` form. Lives in a different repo (github-spec-kit).

(A) is the right call. Pure renaming in `extension.yml`. No effect on slash command names.

### 9. The "claude reviewer via SDK" identity collapse

Documented in the Phase 3 review-code Round 3. When a Claude session invokes a slash command that runs `orca-cli cross-agent-review --reviewer cross`, the "claude" reviewer adapter calls `anthropic.Anthropic()` — an HTTP roundtrip to api.anthropic.com using the operator's API key. That's:
- A different Claude than the in-session agent (no shared context/memory)
- Billed against the operator's API key (not the host harness)
- Aspirationally "cross-agent" but really "host-Claude vs API-Claude"

**Fix options:**
- (A) Add an `in-session` reviewer mode that returns a sentinel "must be filled by host harness" envelope; the slash command then prompts the host claude to write findings inline
- (B) Detect the host harness via env var (e.g., `CLAUDECODE=1`) and auto-skip the claude reviewer; only run codex
- (C) Document the limitation in `plugins/codex/AGENTS.md` and SKILL bodies

(C) is the cheapest. (A) is the architecturally honest one. (B) is a pragmatic middle.

### 10. Configurable codex reviewer timeout

Phase 3.1 already added `ORCA_REVIEWER_TIMEOUT_S` env knob (default 120s). Phase 3 Round 1 failed because the 1963-line phase-3 patch exceeded the hardcoded 120s. The env knob is in place, but operators don't know about it.

**Fix:** Document the env knob in:
- `plugins/codex/AGENTS.md`
- The slash commands' Prerequisites section (already added) — add a line about `ORCA_REVIEWER_TIMEOUT_S`
- A CHANGELOG entry

## Tracker

Items 1, 2, 3, 4 — capability changes; small-to-medium scope each.
Items 5, 6, 7 — install/UX work; small-to-medium scope each.
Items 8, 9, 10 — design / docs; small to large scope.

Recommended order for Phase 3.2:
1. Item 8 (spec-kit validator naming) — pure rename, unblocks `specify extension add`.
2. Item 6 (install README) + item 10 documentation — quick docs work, big UX win.
3. Item 1 (citation validator markdown awareness) — biggest false-positive reducer.
4. Item 5 (skill sync command) — closes a verification gap.
5. Item 7 (orca:doctor) — sets up future verification automation.
6. Items 2, 3, 4, 9 — order by demand.
