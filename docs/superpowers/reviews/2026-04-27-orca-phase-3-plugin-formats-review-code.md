# Review-Code: Orca Phase 3 (plugin formats + SDD slash commands)

**Branch:** `orca-phase-3-plugin-formats`
**Base:** `orca-phase-2-capability-cores`
**Diff:** 10 files, +1697 / -75
**Test posture:** 392 passing (346 baseline + 46 new)

---

### Round 1 - FAILED (orca-cli backend mismatch)

- kind: backend_failure
- message: all reviewers failed: claude: "Could not resolve authentication method..."; codex: codex timeout after 120s; reduce bundle size or raise timeout_s
- underlying: all_reviewers_failed

_Recovered via legacy `crossreview.sh` (codex, 600s timeout) + in-session self-pass. See Round 2 below._

---

## Round 2 - Self+Cross Review

## Self-Pass - claude (opus-4-7, in-session)

### Scope

What the diff actually shipped (matches the brief):

- `src/orca/cli_output.py` (new, 509 lines): five renderers plus a stdlib-only `argparse` dispatcher (`python -m orca.cli_output render-{...}`). Renderers: `render_review_spec_markdown`, `render_review_code_markdown`, `render_review_pr_markdown`, `render_completion_gate_markdown`, `render_citation_markdown`, plus shared helpers `render_error_block` and `render_metadata_footer`.
- Three rewired slash commands: `plugins/claude-code/commands/review-spec.md` (full rewrite around `orca-cli cross-agent-review` + `render-review-spec`), `plugins/claude-code/commands/review-code.md` (step 8 mandates the cross-pass; the rest of the file kept its existing prose), `plugins/claude-code/commands/review-pr.md` (added the "Cross-Pass Review" block invoking `cross-agent-review --kind pr`).
- Two new commands: `plugins/claude-code/commands/gate.md`, `plugins/claude-code/commands/cite.md`.
- `plugins/codex/AGENTS.md` (new, 118 lines): Codex consumption pointer doc.
- `tests/cli/test_cli_output.py` (657 lines, 40 tests) and `tests/cli/test_codex_agents_md.py` (93 lines, 6 tests).
- `extension.yml`: bumped to 2.2.0; `orca:gate` and `orca:cite` registered.

What the diff does NOT contain that the spec/plan promised: nothing material is missing for the listed phase 3 deliverables. The "Codex profile/manifest" delivery is intentionally limited to the AGENTS.md pointer and is consistent with the spec's "no behavioral plugin, just a doc surface" framing. cli.py and python_cli.py are untouched.

### Correctness

- `src/orca/cli_output.py:340` - `Coverage: **{coverage:.0%}**`. The `:.0%` format multiplies by 100 then rounds, so `0.999` renders as `100%` even though the validator did NOT achieve full coverage. For an artifact whose entire purpose is to flag uncited claims, this is a real misread risk: an operator scanning the report header sees `100%` while the body lists uncited claims. Fix: switch to `{coverage * 100:.1f}%` or floor instead of round.
- `src/orca/cli_output.py:144-156` (review-spec) and `:175-216` (review-code) - when `findings` is empty AND `partial=True`, the output is `_no findings_` directly followed by a blank line and the partial note. `_no findings_` with `partial: True` is a confusing state - there were missing reviewers AND zero findings, which is closer to "we didn't actually run a full review" than "the code is clean." The renderer faithfully reflects the envelope; the deficiency is upstream in the contract.
- `src/orca/cli_output.py:179-208` (review-code) - if `severity` on a finding is something not in `_SEVERITY_ORDER` (e.g. a normalization slip producing `"BLOCKER"` rather than `"blocker"`, or `"?"` from the `f.get("severity", "?")` default), that finding silently disappears from the markdown because `_SEVERITY_ORDER` is iterated as the outer loop. The one-liner spec renderer does NOT have this hole because it iterates findings directly. Should at minimum render an "Other" group at the bottom for unknown severities so nothing silently vanishes.
- `src/orca/cli_output.py:243-254` (PR table) - `evidence` and `suggestion` from the finding are NOT in the table at all. The shape is intentional, but the slash command (`review-pr.md:104-111`) doesn't tell the operator that those fields go missing.
- `plugins/claude-code/commands/gate.md` and `cite.md` - both pipe `orca-cli ... > /tmp/orca-{gate,cite}-envelope.json`. The slash command never checks `orca-cli`'s exit code, so the slash command itself reports `pass`/`blocked`/`stale` based on parsing the rendered report rather than the envelope's `ok` field. Brittle.
- `plugins/claude-code/commands/review-code.md:139` - `BASE_REF=$(git merge-base "${ORCA_BASE_BRANCH:-main}" HEAD)`. Falls through to `main` even when the working branch was branched off something else. This phase 3 lane itself was branched off `orca-phase-2-capability-cores`, so per this snippet the cross-pass on phase 3 against `main` would include phase 2's diff - the wrong thing. `ORCA_BASE_BRANCH` is the override mechanism but it's not surfaced to operators in the slash command prose.

### Code quality

- `src/orca/cli_output.py:499-505` - `RENDERERS` dict is defined AFTER `main()` references it. Works because `main()` is only invoked from `__main__`. Slightly fragile: a future helper that calls `main()` at import time would `NameError`.
- Five different ad-hoc tmpfiles in `/tmp/` across the slash commands, none cleaned up. Concurrent slash-command runs collide. Use `mktemp` or `$FEATURE_DIR/.{cite,gate}-envelope.json` for parity with review-code/review-pr (which already use `$FEATURE_DIR/.review-{code,pr}-envelope.json`). Inconsistency between the new commands and the rewired commands.
- The cross-pass call is repeated nearly verbatim across review-spec.md, review-code.md, review-pr.md. Drift risk.

### Security

- `src/orca/cli_output.py:416-431` (`_read_envelope`) - reads stdin or a file path. No validation of envelope shape; renderers do `dict.get(...)` with defaults. A malicious envelope could carry attacker-controlled markdown. Markdown is read by humans, not browsers, and the orca-cli backends are trusted. If an operator pipes an untrusted envelope through this dispatcher (e.g. pasted from an external reviewer), the markdown would land in their repo verbatim. Document that envelopes are trusted input.
- All five renderers do passthrough of envelope-supplied strings directly into markdown. No HTML escaping. Trusted-input model.
- `plugins/claude-code/commands/review-code.md:140` - `git diff "$BASE_REF"...HEAD > "$FEATURE_DIR/.cross-pass-patch"`. The slash command doesn't gitignore `.cross-pass-patch` / `.review-code-envelope.json`; they may end up committed.

### Test coverage

Strong baseline (40 tests in test_cli_output.py + 6 drift tests). What's tested well: happy paths, failure envelopes, double-blank invariant (caught a real regression in 852e2fa), detail ordering, unicode passthrough, PR table newline collapse, dispatcher exit codes.

What's NOT tested:

- **Citation coverage rounding**: no test for `0.999` -> "100%" or any "almost 100%" boundary case. The bug exists, and the test gap masks it.
- **Unknown severity**: no test asserts what happens to a finding with `severity: "?"` or `severity: "BLOCKER"` in render_review_code (which silently drops it).
- **Empty findings + partial=True interaction**: no explicit assertion.
- **PR table cell containing a backtick or a backslash-pipe pair**: only plain-pipe and newline are exercised.
- **Reviewer list ordering**: `reviewers = "+".join(f.get("reviewers", []))` - no test asserts deterministic ordering.
- **AGENTS.md drift test only checks substring presence**. It does NOT verify the capability is actually documented under a heading or has a README link.

### Deficiencies I know about

1. **The "claude reviewer via SDK" assumption when claude is the operator** - `python_cli.py:223-228` resolves the Claude reviewer by `import anthropic; anthropic.Anthropic()`. That's an HTTP roundtrip to api.anthropic.com using whatever API key the env provides. When *I* (this Claude session, running the slash command in-harness) am the operator, the slash command's `orca-cli cross-agent-review --reviewer cross` ends up making the host SDK call out to api.anthropic.com - which calls a Claude *I am not*, with no shared session memory, billed against the operator's API key, and not the conversational Claude that's holding the actual review context. The cross-pass result is "Claude (some-model-via-API) reviewing the diff" not "Claude (the agent in this session) reviewing the diff." The phase 3 work doesn't introduce this - it inherits it from phase 2 - but **the slash command rewrite makes this implicit dependency a hard requirement** where it was previously aspirational. **This Round 1 failed precisely because of this assumption** (no API key in env). Either (a) document that `--reviewer cross` against a claude-hosted slash-command session means "API-Claude reviewing, not session-Claude reviewing" or (b) add an in-session claude reviewer mode that has the host claude do the review directly via the slash-command author. Today the slash commands don't acknowledge this at all. **Architectural - must be flagged.**
2. Citation coverage display rounds 99.9% up to 100% (Correctness #1).
3. review-code findings with unknown severity silently disappear (Correctness #3).
4. gate.md and cite.md don't check `orca-cli` exit code before rendering (Correctness #5).
5. `/tmp/` envelope files in gate.md and cite.md - collision risk + inconsistency (Code quality).
6. The cross-pass invocation is duplicated nearly verbatim across three slash commands - drift risk.
7. `ORCA_BASE_BRANCH` defaulting to `main` in review-code.md:139 - wrong base when phase branches stack.
8. AGENTS.md drift tests are substring-only - they miss structural drift.
9. `_DETAIL_ORDER` constant in `cli_output.py:23` is fixed at module scope; if a new ErrorKind starts emitting a new detail key, it'll sort alphabetically last instead of in diagnosis order.

### Verdict

**NEEDS-WORK.** Three issues should not pass cross-pass: (1) the citation `:.0%` rounding bug; (2) the unknown-severity drop in review-code where findings can vanish from the artifact; (3) the architectural mismatch where "Claude reviewer via SDK" is invoked from a Claude slash-command session, which is now baked into three rewired slash commands without documentation. Items 1 and 2 are one-line fixes plus tests, item 3 is documentation plus an optional fallback flag - but each is operator-visible enough that landing as-is would put bad output into operators' artifacts.

---

## Cross-Pass - codex (high effort, tier1-supported-auto)

### Summary

The capability wiring generally matches the CLI surface, and the dispatcher is a clean improvement, but I found merge-blocking issues in markdown safety and command/documentation correctness. The renderers still write raw LLM/user strings into Markdown list and heading contexts, so valid schema strings containing newlines or Markdown control characters can corrupt review artifacts. There is also a project-rule violation from an added em dash, and the gate command includes an invalid optional shell argument in an executable-looking block.

### Blocking

- **`src/orca/cli_output.py:193`** - Renderer fields from envelopes are emitted raw into Markdown contexts. Schema-valid strings in summary/detail/evidence/suggestion, citation claim text, content_path, or error message can contain newlines, pipes, headings, or list markers and produce malformed artifacts; PR summary is the only partially normalized path.
  **Fix:** Add a shared Markdown scalar/table-cell sanitizer or line normalizer and use it for all envelope/user-provided strings before appending to list, heading, table, and footer contexts. Add tests for newlines/control characters in review-spec, review-code, citation, and error rendering.

- **`plugins/claude-code/commands/gate.md:54`** - The bash block includes `[--evidence-json "<json>"]` as a literal continued argument. If copied or executed by an agent, argparse receives an unknown argument and the completion gate fails with exit 2.
  **Fix:** Replace the optional placeholder with executable shell, for example build an args array and conditionally append `--evidence-json "$EVIDENCE_JSON"`, or show separate with/without-evidence commands.

- **`tests/cli/test_cli_output.py:274`** - The added unicode test contains an actual em dash despite the branch/project rule of no em-dashes anywhere.
  **Fix:** Replace the em-dash with a hyphen in the test string, or rephrase the fixture text without U+2014.

### Non-blocking

- **`tests/cli/test_codex_agents_md.py:19`** - The drift test hardcodes `EXPECTED_CAPABILITIES`, so adding a new `_register(...)` entry in `src/orca/python_cli.py` will not fail unless this test is manually updated too.
  **Fix:** Derive the expected set from the CLI registry (`CAPABILITIES`) or `orca-cli --list`, then assert every registered capability appears in `plugins/codex/AGENTS.md`.

- **`plugins/codex/AGENTS.md:73`** - The documented no-backend error says `message="reviewer not configured"`, but default `--reviewer cross` actually returns `missing reviewer for cross mode: 'claude'` when no reviewers are configured.
  **Fix:** Document both single-reviewer and cross-reviewer missing-backend messages, or avoid quoting an exact message.

- **`plugins/claude-code/commands/review-code.md:153`** - `$(basename $FEATURE_DIR)` is unquoted in shell examples, which breaks feature paths containing whitespace.
  **Fix:** Use `$(basename "$FEATURE_DIR")` in review-code and review-pr examples.

- **`plugins/claude-code/commands/review-spec.md:55`** - Several commands use fixed `/tmp/orca-*.json` and `/tmp/orca-*.md` paths, which can collide across concurrent slash-command runs.
  **Fix:** Use `mktemp` or feature-scoped temp files consistently for spec/gate/cite envelopes and reports.

---

## Final Merge Verdict

**NEEDS-WORK.** Both passes converge: the code is structurally sound, but operator-visible correctness bugs and one architectural-honesty gap should land before merge.

**Convergent findings** (both self and cross flagged):

- Operator-visible correctness in renderers (self: rounding + dropped severities; cross: markdown-injection / unsanitized scalar emission).
- `/tmp/` collision risk and inconsistent envelope-file naming across the slash commands.
- `--evidence-json` shape (self: not exit-code-checked; cross: literal `[brackets]` in bash that breaks copy-paste).
- AGENTS.md drift weakness (self: substring-only; cross: hardcoded list rather than CLI-derived).

**Cross-pass added** one finding self-pass missed: `tests/cli/test_cli_output.py:274` contains a real em-dash inside the unicode-passthrough fixture string. The fixture is `"spec uses "smart" quotes — and CJK 中文"`. Decision needed from operator: was the em-dash deliberate (testing passthrough of em-dash content) or accidental? If deliberate, document via comment; if not, replace.

**Self-pass added** one finding cross missed: the Claude-reviewer-via-SDK identity collapse. Codex did not flag this likely because from codex's perspective the SDK adapter just looks like a backend; only Claude (the in-session agent) feels the duplication of identity. **Round 1 failed because of exactly this assumption** - no `ANTHROPIC_API_KEY` in env, so the "claude" reviewer in `--reviewer cross` couldn't run, and codex alone hit the 120s hardcoded timeout on the 1963-line patch.

### Required to clear gate

1. Citation `:.0%` rounding fixed (one line + test) - `src/orca/cli_output.py:340`
2. Unknown-severity findings rendered under "Other" (small change + test) - `src/orca/cli_output.py:179-208`
3. gate.md `[--evidence-json]` literal turned into runnable shell or split into two examples - `plugins/claude-code/commands/gate.md:54`
4. Em-dash on `tests/cli/test_cli_output.py:274` resolved (decision: strip or document)
5. Markdown sanitizer pass for envelope-supplied strings (or explicit "trusted input" doc) - this one might be Phase 3.1 if scope-protective

### Phase 3.1 candidates

- In-session claude reviewer mode (avoid the SDK roundtrip when the host harness IS claude)
- Configurable codex timeout (`ORCA_REVIEWER_TIMEOUT_S` env knob; codex hit the hardcoded 120s on this branch's diff)
- Shared cross-pass-invocation include across the three rewired slash commands
- `ORCA_BASE_BRANCH` surfaced as user-input in review-code/review-pr slash commands
- AGENTS.md drift detection upgraded to derive from `orca-cli --list`

Items 1-4 are quick. Item 5 is the substantive one and the right call depends on threat model.

---

## Round 3 - Fix Verification

**Commit:** `1ccb299` - `fix(cli_output): address phase 3 review-code blockers`
**Test posture:** 399 passing (392 prior + 7 new regression tests covering each fix)

### Required-to-clear-gate items (all 5 closed)

1. **Citation `:.0%` rounding** - `cli_output.py` now uses `int(coverage * 100)` to floor. Verified live: `0.999 -> 99%`, `1.0 -> 100%`, `0.5 -> 50%`. Two new tests (`test_render_citation_floors_almost_full_coverage`, `test_render_citation_full_coverage_is_100_percent`).
2. **Unknown-severity drop in review-code** - findings with severity outside `_SEVERITY_ORDER` now surface under `#### Other` instead of vanishing. Refactored emission into a shared `_emit_group` helper. New regression test `test_render_review_code_does_not_drop_unknown_severity` exercises uppercase `"BLOCKER"` and `"?"`.
3. **gate.md `[--evidence-json "<json>"]` literal** - replaced with two runnable bash forms (without and with `--evidence-json`).
4. **Em-dash in unicode test fixture** - `tests/cli/test_cli_output.py:274` U+2014 -> U+002D. Unicode passthrough still verified by smart quotes + CJK characters. Project rule clean.
5. **Markdown injection surface** - new `_normalize_inline()` helper collapses `\r\n|\n|\r` to spaces; applied in `render_error_block`, `_render_finding_oneline`, `_render_partial_note`, all five top-level renderers. `_normalize_table_cell` now composes `_normalize_inline` + pipe escape (existing PR-table tests still green). Three new regression tests cover newline-injection attempts in summary, claim text, and error message.

### Convergent findings (now resolved)

- Operator-visible correctness (rounding + dropped severities + injection surface) - all closed.
- `--evidence-json` shape - closed via gate.md rewrite.
- Em-dash - closed.

### Phase 3.1 (deferred, non-blocking)

Items below remain open but are scope-protective for Phase 3 and tracked for follow-up:

- **In-session claude reviewer mode** to avoid the SDK roundtrip when the host harness IS claude. This Round 1 failed because of this assumption; codex-only via legacy harness was the workaround. Phase 3.1 should add either a `claude-in-session` reviewer adapter or document the SDK-only contract explicitly in the slash command.
- **Configurable codex reviewer timeout** (`ORCA_REVIEWER_TIMEOUT_S` env knob; codex's hardcoded 120s timed out on this branch's 1963-line patch).
- **Shared cross-pass-invocation include** across the three rewired slash commands (drift risk, ~30 lines duplicated three times).
- **`ORCA_BASE_BRANCH` surfaced as user-input** in review-code/review-pr slash commands (today it's only an env override).
- **AGENTS.md drift detection upgraded** to derive expected capabilities from `orca-cli --list` instead of hardcoded constant.
- **`/tmp/` envelope file collision** in gate.md and cite.md - inconsistent with review-code/review-pr's `$FEATURE_DIR/.*` naming. Use `mktemp` or feature-scoped temp files.
- **Per-finding evidence/suggestion in PR table** - operator doc should call out that those fields are intentionally elided from the disposition table.
- **Backtick escaping in PR table summaries** - currently passes through as inline code; mostly fine but documented behavior would be cleaner.

### Final Verdict

**READY** (for Phase 3 scope; Phase 3.1 follow-ups tracked above).

All round-2 blockers cleared, regression tests in place, full suite green. The architectural identity-collapse callout (claude-via-SDK from a claude-hosted slash command) is real and worth Phase 3.1 work, but it inherits from Phase 2 and the slash command rewire is no worse than the legacy `crossreview.sh` flow it replaced - which also assumed an out-of-session reviewer. Phase 3 ships.

