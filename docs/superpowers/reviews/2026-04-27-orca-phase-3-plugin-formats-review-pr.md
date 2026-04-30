# Review-PR: Orca Phase 3 (PR #70)

**PR:** https://github.com/SteeZyT33/orca/pull/70
**Branch:** `orca-phase-3-plugin-formats` -> `orca-phase-2-capability-cores`
**Diff:** 5031 lines (10 files src + docs/notes/reviews)
**Tests:** 403 passing
**Comments awaiting disposition:** 0 (CodeRabbit auto-skipped; no human reviews yet)

---

## Round 1 - Cross-Pass via codex (high effort, tier1-supported-auto)

### Summary

No human comments need disposition and CodeRabbit skipped, so there is nothing pending on comment handling. The main PR-level blocker is install regression risk: `extension.yml` still registers `orca:*` commands even though the backlog confirms spec-kit's validator rejects that naming, which breaks the canonical `specify extension add` path. The rest looks shippable with follow-up UX/docs work, especially backend prerequisites, timeout docs, and citation defaults.

### External Comment Responses

_No external comments yet (CodeRabbit auto-skipped because target is `orca-phase-2-capability-cores`, not `main`)._

### Findings Table

| # | Severity | File:Line | Reviewer | Summary | Disposition |
|---|----------|-----------|----------|---------|-------------|
| 1 | blocking | extension.yml:18 | codex | `provides.commands` registers `orca:*` names; spec-kit validator rejects them, breaking `specify extension add`. Backlog item 8 confirms this. | _pending_ |
| 2 | non-blocking | plugins/claude-code/commands/cite.md:67 | codex | Default reference set still hardcodes `events.jsonl` and `experiments.tsv` (MemWell-leftover). | _pending_ |
| 3 | non-blocking | plugins/codex/AGENTS.md:65 | codex | Reviewer backend prerequisites underdocumented (Anthropic SDK behavior, codex CLI auth, `ORCA_REVIEWER_TIMEOUT_S`). | _pending_ |
| 4 | non-blocking | plugins/claude-code/commands/review-spec.md:84 | codex | review-spec still writes envelope to fixed `/tmp/orca-review-spec-envelope.json`; gate/cite moved to `$FEATURE_DIR/.*` but review-spec didn't. Concurrent-run collision. | _pending_ |
| 5 | non-blocking | plugins/claude-code/commands/review-code.md:168 | codex | Cross-pass diff defaults to `ORCA_BASE_BRANCH:-main`. For stacked branches reviewers get parent-branch changes too. | _pending_ |
| 6 | non-blocking | plugins/claude-code/commands/review-pr.md:117 | codex | Round counting only matches `### Round N - ` (hyphen). Existing artifacts use em-dash. Migration path: duplicate Round 1 blocks after upgrade. | _pending_ |
| 7 | non-blocking | src/orca/assets/orca-main.sh:846 | codex | Post-install summary still lists only the original five Orca commands; omits `gate` and `cite`. Fresh installs look incomplete. | _pending_ |

### Detail per finding

**#1 (blocking) - extension.yml command naming**

```
extension.yml:18:    - name: "orca:brainstorm"
extension.yml:22:    - name: "orca:review-spec"
... etc.
```

Phase 1 of the v1 rebuild renamed slash commands from `speckit.orca.{cmd}` to `orca:{cmd}`, but spec-kit's extension-catalog validator at `specify extension add` still requires the legacy prefix. This blocks the canonical install command. The Phase 3 install bypassed via `/tmp/install-phase3-orca.sh`.

**Fix:** Rename only `extension.yml provides.commands` entries to `speckit.orca.{command}` while keeping file basenames `gate.md` etc. for `orca:gate` skill invocation. The validator and the slash invocation are decoupled per the SKILL.md generator (see `orca-main.sh:705` where `skill_name = f"orca-{base}"` derives from file basename, not `extension.yml`).

This is the highest-priority backlog item (item 8) and codex independently flagged it as blocking.

**#2 - cite default reference set**

`plugins/claude-code/commands/cite.md` step 2 of the Outline says default refs are `events.jsonl`, `experiments.tsv`, and any `specs/<feature>/research.md`. The first two are MemWell-specific; not generic SDD artifacts.

**Fix:** Replace with auto-discovery from feature dir: `plan.md`, `data-model.md`, `research.md`, `quickstart.md`, `tasks.md`, `contracts/**/*.md`.

**#3 - AGENTS.md reviewer backend docs**

`plugins/codex/AGENTS.md` documents fixture env vars and `ORCA_LIVE=1` but doesn't mention:
- `ANTHROPIC_API_KEY` for the Anthropic SDK (claude reviewer needs this; verified by Round 1's Phase 3 review-code failure)
- That codex CLI must be authenticated
- `ORCA_REVIEWER_TIMEOUT_S` env knob (added in Phase 3.1 commit `f82ce45`)

**Fix:** Add a short "Reviewer Backend Prerequisites" block.

**#4 - review-spec.md /tmp/ envelope path**

The cite.md and gate.md commands moved to `$FEATURE_DIR/.cite-envelope.json` / `$FEATURE_DIR/.gate-envelope.json` in Phase 3.1, but review-spec.md still uses `/tmp/orca-review-spec-envelope.json`. Inconsistent and collision-risky.

**Fix:** Use `$FEATURE_DIR/.review-spec-envelope.json` for parity with review-code/review-pr.

**#5 - ORCA_BASE_BRANCH not surfaced**

`review-code.md:168` (around the BASE_REF line) defaults to `main` for the merge-base. Stacked PRs (like this one branched off `orca-phase-2-capability-cores`) need the env override but it's documented only as an env var, not as a user-input flag.

**Fix:** Surface `ORCA_BASE_BRANCH` as a parsed argument (`--base-branch <ref>`) or auto-detect from `git config branch.<current>.merge`.

**#6 - Round counting hyphen vs em-dash**

review-pr.md (and review-spec.md, review-code.md) tell operators to count `### Round N - ` headers (hyphen). But pre-Phase-1 artifacts use `### Round N — ` (em-dash). Operators upgrading existing repos will get duplicate Round 1 blocks.

**Fix:** Match both forms during round detection. One-line regex change: `### Round (\d+) [-—] ` instead of `### Round (\d+) - `.

**#7 - orca-main.sh post-install summary**

Final summary line in `orca-main.sh:846` lists only `brainstorm`, `review-spec`, `review-code`, `review-pr`, `tui` — not `gate` and `cite`.

**Fix:** Append `.gate` and `.cite` to the summary.

---

## Disposition Plan

Working order (codex-blocking first, then non-blocking by impact):

1. **#1 (blocking) - extension.yml naming** -> `ADDRESSED` once renamed. Backlog item 8.
2. **#7 - orca-main.sh summary** -> `ADDRESSED`, trivial.
3. **#4 - review-spec.md /tmp -> $FEATURE_DIR** -> `ADDRESSED`, mirror Phase 3.1 fix.
4. **#6 - hyphen/em-dash round count** -> `ADDRESSED`, regex compat.
5. **#3 - AGENTS.md reviewer prerequisites** -> `ADDRESSED`, documentation.
6. **#5 - ORCA_BASE_BRANCH as flag** -> deferred; non-trivial slash-command parser change. Backlog.
7. **#2 - cite reference set defaults** -> deferred; capability-level change. Backlog item 2.

After dispositions, append a Round 2 with the remediation commits and final verdict.

---

## Round 2 - Disposition Verification

**Commit:** `4bd6a7d` - `fix: review-pr round 1 disposition sweep`

### Dispositions

| # | Status | Notes |
|---|--------|-------|
| 1 | ADDRESSED | extension.yml renamed to speckit.orca.* form; spec-kit validator accepts. Slash invocation unchanged (decoupled per orca-main.sh:705). |
| 2 | ISSUED Phase 3.2 #2 | cite default reference set; capability-level change |
| 3 | ADDRESSED | AGENTS.md gained Live Backend Prerequisites block |
| 4 | ADDRESSED | review-spec.md envelope path moved from /tmp to $FEATURE_DIR |
| 5 | ISSUED Phase 3.2 #5 | ORCA_BASE_BRANCH as parsed flag; non-trivial slash-command parser change |
| 6 | ADDRESSED | Round counting prose updated to match both hyphen and em-dash forms |
| 7 | ADDRESSED | orca-main.sh post-install summary now lists gate + cite |

### Final Verdict

**READY** to merge after Phase 2 (PR #69) lands. Codex-blocking #1 cleared; remaining deferrals are scope-protective and tracked in `docs/superpowers/notes/2026-04-27-phase-3-2-backlog.md`.

Test posture: 403 passing. CI green.
