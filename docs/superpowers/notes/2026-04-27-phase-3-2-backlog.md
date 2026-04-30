# Phase 3.2 Backlog

**Source:** Three parallel claude verification sessions ran orca Phase 3 against fresh installs in `/home/taylor/spec-kit-orca`, `/home/taylor/MemWell`, `/home/taylor/perf-lab` on 2026-04-27. Logs at `/tmp/orca-verify-logs/{spec-kit-orca,memwell,perflab}.log`.

**Status:** Convergent findings already addressed in Phase 3 (commit `ac0c45f` Prerequisites + tui frontmatter). The items below are deferred capability-level or design-level work that surfaced during verification.

## Capability-level work

### 1. Citation validator over-flags non-prose content - DONE (2026-04-27)

All three sessions flagged the same issue: `citation-validator` reports `Coverage: **6%**` against typical spec.md / README.md content because the heuristic treats:

- Lines inside fenced code blocks (e.g., `bash`/`python` fences) as prose claims
- Markdown table rows (pipe-delimited cells) as separate claims
- Spec-kit scaffolding patterns: `**FR-001**: ...`, `### Session 2026-04-25`, `**Field**:`, `Run N/3:`
- Brackets without `[ref:...]` or `[#...]` prefix as broken refs (e.g., `[all: 1440 1438 1445]`)

**Fix surface:** `src/orca/capabilities/citation_validator/`. Add a markdown-aware preprocessing pass that:
- Strips fenced code blocks before sentence splitting
- Skips lines that match the markdown table-row pattern `^\|.*\|$`
- Maintains a skip-list of spec-kit scaffolding patterns (configurable via `--skip-pattern` repeatable flag)
- Tightens the broken-ref detector to require `[ref:NAME]`, `[NAME.md]`, or `[#NAME]` form (not bare `[anything: with colons]`)

**Tests to add:** fixture markdown files representing each false-positive class, asserting they don't appear in `uncited_claims` or `broken_refs`.

**Resolution:** Added `_strip_code_fences` (handles backtick + tilde + indented + unclosed-at-EOF), `_is_table_row`, `_SCAFFOLDING_PATTERNS` (FR-NNN bullets with leading `- ` tolerated, session headers, `**Field**:` lines, Run N/M tags), `_is_reflike` ref-shape filter, and `skip_patterns` input field with re.compile error -> INPUT_INVALID. `_ref_resolves` strips `ref:` prefix. CLI gains `--skip-pattern`. 14 new tests; 32 total in `test_citation_validator.py`; 417 passing overall (commit `a7ea715`). Smoke against representative spec.md files showed uncited-claim counts dropping ~10x (e.g., `specs/006-orca-review-artifacts/spec.md`: 34 -> 9; `specs/003-cross-review-agent-selection/spec.md`: 26 -> 2).

### 2. Citation default reference set should auto-discover, not hardcode - DONE (2026-04-27)

`plugins/claude-code/commands/cite.md:44-46` describes a default reference set of `events.jsonl`, `experiments.tsv`, `specs/<feature>/research.md`. Two of those are MemWell-specific artifacts; not generic.

**Fix:** Replace with auto-discovery from the resolved feature dir:
- `plan.md`, `data-model.md`, `research.md`, `quickstart.md`, `tasks.md`, `contracts/**/*.md`

Both the slash command markdown AND the `--reference-set` default (if any) in the capability code should change.

**Resolution:** Updated `plugins/claude-code/commands/cite.md` Outline step 2 with a generic SDD-aware auto-discovery snippet that globs `plan.md`, `data-model.md`, `research.md`, `quickstart.md`, `tasks.md`, and `contracts/**/*.md` under the resolved `$FEATURE_DIR`, passing each existing path as a repeated `--reference-set` arg. Operator-supplied flags still win; empty result falls through to capability-level empty-ref handling. Markdown-only change; capability `reference_set` already defaults to `[]` (commit `0a32dcc`).

### 3. completion-gate `duration_ms` rounds to 0 for fast runs - DONE (2026-04-27)

The completion_gate capability runs in <1ms for typical `plan-ready` checks (just `spec.md` existence + `[NEEDS CLARIFICATION]` grep). `int((time.monotonic() - started) * 1000)` truncates submillisecond durations to 0, which the renderer prints as `_duration: 0ms_`.

This is technically correct but operator-misleading.

**Fix options:**
- (A) Use microseconds in the envelope: `duration_us` field, renderer formats as `0.3ms` for sub-millisecond
- (B) Use float milliseconds with `.1f` precision
- (C) Document that 0ms means <1ms and accept the loss of granularity

(B) is the smallest diff; (A) is more correct.

**Resolution:** Picked option (B). All six dispatchers in `src/orca/python_cli.py` now use `round((time.monotonic() - started) * 1000, 1)` (float, 0.1ms precision). `Result.to_json` type hint flipped `duration_ms: int` -> `float` in `src/orca/core/result.py`. `render_metadata_footer` in `src/orca/cli_output.py` renders sub-millisecond floats as `"0.3ms"` and >=1ms or int values as integer for clean display. Three regression tests added to `tests/cli/test_cli_output.py` (sub-ms decimal, >=1ms int, legacy int=0 backward compat). 420 tests passing. Smoke against `completion-gate` now reports `"duration_ms": 0.1` instead of `0` (commit `0a32dcc`).

### 4. completion-gate at `plan-ready` evaluates only 2 gates - RESOLVED-AS-DOCUMENTED (2026-04-28)

Verification showed only `spec_exists` and `no_unclarified` evaluated at `plan-ready`. Either expand the gate set (e.g., `clarifications_resolved`, `acceptance_criteria_present`) or document why those two are sufficient.

**Resolution:** Picked the documented-rationale path. Added a "Design Notes" section to `docs/capabilities/completion-gate/README.md` explaining why each candidate gate was rejected:
- `acceptance_criteria_present`: spec-kit specs use varied conventions; rigid heading check is brittle. LLM-aware detection is out of v1 rule-based scope. Operators wanting stricter pre-`/plan` review run `/orca:review-spec` instead.
- `clarifications_resolved`: identical semantics to `no_unclarified`. Already covered.
- `user_story_present`: stories often live in plan.md not spec.md; would mis-block legitimately deferred breakdown.

The minimal precondition for `/plan` is a spec.md the planner can read without ambiguity blockers; the existing 2-gate set captures exactly that. No code change.

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

### 8. spec-kit validator rejects `orca:*` naming - DONE (2026-04-28)

`specify extension add --dev /path/to/orca` fails with:

```
Validation Error: Invalid command name 'orca:brainstorm': must follow pattern 'speckit.{extension}.{command}'
```

Phase 1 of the v1 rebuild renamed slash commands from `speckit.orca.{cmd}` to `orca:{cmd}`, but spec-kit's extension-catalog validator still requires the legacy prefix. The direct-copy install at `/tmp/install-phase3-orca.sh` bypasses this, but `specify extension add` is broken for orca.

**Fix options:**
- (A) Restore `speckit.orca.{cmd}` naming in `extension.yml provides.commands` while keeping file basenames `gate.md` etc. for `orca:gate` skill invocation. The validator and the slash invocation are decoupled.
- (B) Patch spec-kit's validator to allow `{namespace}:{command}` form. Lives in a different repo (github-spec-kit).

(A) is the right call. Pure renaming in `extension.yml`. No effect on slash command names.

**Resolution:** Picked option (A). All 7 `provides.commands` entries renamed `orca:*` -> `speckit.orca.*` in `extension.yml`. Hooks references updated to match. Verified via `specify extension add --dev /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats` - validator accepts cleanly. Slash invocation unchanged because `src/orca/assets/orca-main.sh:705` derives skill names from file basenames (`orca-{base}`), not from `extension.yml`. (Commit `4bd6a7d` as part of review-pr Round 1 disposition sweep.)

### 9. The "claude reviewer via SDK" identity collapse - DONE via Phase 4a (2026-04-28)

Documented in the Phase 3 review-code Round 3. When a Claude session invokes a slash command that runs `orca-cli cross-agent-review --reviewer cross`, the "claude" reviewer adapter calls `anthropic.Anthropic()` - an HTTP roundtrip to api.anthropic.com using the operator's API key. That's:
- A different Claude than the in-session agent (no shared context/memory)
- Billed against the operator's API key (not the host harness)
- Aspirationally "cross-agent" but really "host-Claude vs API-Claude"

**Fix options:**
- (A) Add an `in-session` reviewer mode that returns a sentinel "must be filled by host harness" envelope; the slash command then prompts the host claude to write findings inline
- (B) Detect the host harness via env var (e.g., `CLAUDECODE=1`) and auto-skip the claude reviewer; only run codex
- (C) Document the limitation in `plugins/codex/AGENTS.md` and SKILL bodies

(C) is the cheapest. (A) is the architecturally honest one. (B) is a pragmatic middle.

**Status:** Shipped in Phase 4a. Option (A) (in-session reviewer mode) plus orca-cli-side validation. Specifically:
- New `FileBackedReviewer` (commits `0b9282d` + `f603988`) loads pre-authored findings from a JSON file, bypassing the SDK roundtrip.
- New `--claude-findings-file` / `--codex-findings-file` flags on `cross-agent-review` (commits `6fd948c0` + `f17b65a`); pre-flight validation surfaces all six failure modes as `INPUT_INVALID` per spec.
- New utility subcommands `parse-subagent-response` (commit `8856a61`) and `build-review-prompt` (commit `9b62da9`) - host pipes subagent output through these.
- Slash commands `review-spec`, `review-code`, `review-pr` (commits `7c479e0`, `16b6cd8`, `b4a007a`) updated to dispatch a `Code Reviewer` subagent BEFORE calling `cross-agent-review --claude-findings-file`. Subagent runs in a fresh Claude Code context (no shared memory with host, no API key needed).
- AGENTS.md (commits `a21199b3` + `2f12c9c`) documents the in-session flow as a coherent feature.
- 24 new tests added (FileBackedReviewer + flag tests + parse-subagent-response + build-review-prompt + context bullets); 445 tests pass total.
- End-to-end smoke verified: file-backed cross-agent-review produces well-formed envelope with `reviewer_metadata.<name>.source = "in-session-subagent"`.

Option (B) auto-detection via `CLAUDECODE=1` was rejected per Phase 4a spec; operators explicitly pass `--claude-findings-file`.

### 10. Configurable codex reviewer timeout - DONE (2026-04-28)

Phase 3.1 already added `ORCA_REVIEWER_TIMEOUT_S` env knob (default 120s). Phase 3 Round 1 failed because the 1963-line phase-3 patch exceeded the hardcoded 120s. The env knob is in place, but operators don't know about it.

**Fix:** Document the env knob in:
- `plugins/codex/AGENTS.md`
- The slash commands' Prerequisites section (already added) - add a line about `ORCA_REVIEWER_TIMEOUT_S`
- A CHANGELOG entry

**Resolution:** Env knob shipped in Phase 3.1 (commit `f82ce45`); AGENTS.md "Live Backend Prerequisites" block (commit `4bd6a7d` review-pr disposition Fix #3) documents it; slash-command Prerequisites blocks (commit `ac0c45f`) cover `ORCA_RUN`/`ORCA_PY` resolution though they don't call out the timeout knob explicitly. Codex reviewer rejects non-positive or non-integer values and warns to stderr (Phase 3.1 design).

## Tracker

| Item | Status | Resolution |
|------|--------|------------|
| 1. Citation validator markdown awareness | DONE | commit `a7ea715` |
| 2. Cite default reference set auto-discovery | DONE | commit `0a32dcc` (markdown-only) |
| 3. completion-gate `duration_ms` granularity | DONE | commit `0a32dcc` |
| 4. plan-ready gate set | RESOLVED-AS-DOCUMENTED | README "Design Notes" |
| 5. Skill sync mechanism | DONE | commit `a25e356` |
| 6. Install README | DONE | commit `268cfe6` |
| 7. orca:doctor health check | DONE | commit `a925a9b` |
| 8. spec-kit validator naming compat | DONE | commit `4bd6a7d` |
| 9. Claude reviewer SDK identity collapse | DONE (Phase 4a) | in-session reviewer + file-backed pattern shipped 2026-04-28 |
| 10. Codex timeout env knob + docs | DONE | commits `f82ce45` + `4bd6a7d` |

All 10 backlog items closed; Item 9 was completed in Phase 4a (in-session reviewer + file-backed reviewer pattern).
