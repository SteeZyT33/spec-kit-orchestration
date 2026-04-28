# Orca Phase 4a: In-Session Claude Reviewer (Subagent-Driven)

**Date:** 2026-04-28 (revised after parallel adversarial review by Code Reviewer + Reality Checker subagents)
**Status:** Design (post-review, pre-implementation-plan)
**Predecessors:**
- `docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md` (v1 north star)
- `docs/superpowers/specs/2026-04-27-orca-phase-3-plugin-formats-design.md` (Phase 3)
- Phase 3.2 backlog item 9 at `docs/superpowers/notes/2026-04-27-phase-3-2-backlog.md` (claude-reviewer-via-SDK identity collapse)

**Stack:** Built on top of PR #70 branch (`orca-phase-3-plugin-formats`). Touches `plugins/claude-code/commands/review-{spec,code,pr}.md` which exist on the Phase 3 branch. If Phase 3 doesn't merge, Phase 4a needs rebasing; if Phase 3 changes during review, the slash-command edits collide. Safer alternative: fold Phase 4a into Phase 3 (same files). Decision: ship as Phase 4a stacked on PR #70 because PR #70 is review-stable; rebase as needed.

## Context

Phase 3 shipped the slash-command opinion layer. Round 1 of Phase 3's own review-code revealed an architectural mismatch: when a Claude session invokes `orca-cli cross-agent-review --reviewer cross`, the "claude" reviewer adapter calls `anthropic.Anthropic()` (an HTTP roundtrip to api.anthropic.com using the operator's API key). This means:

- The reviewer is API-Claude, not the in-session host Claude. Different conversation, no shared context, different billing surface.
- Round 1 of Phase 3 review-code FAILED entirely because `ANTHROPIC_API_KEY` was unset; the cross-pass couldn't run despite Claude (the host) being present.
- Aspirationally "cross-agent" but really "host-Claude vs API-Claude" - same model family, two sessions.

Phase 4a fixes this by adopting subagent-driven review when the host is Claude Code: the slash command dispatches a fresh subagent (Claude Code's `Agent` tool primitive, see anthropic.com/claude-code/sub-agents docs); the subagent runs in its own context window inheriting Claude Code authentication; its findings flow into orca-cli through a new file-backed reviewer adapter.

## Reality-Check Acknowledgments

The spec was reviewed before commit. Surfaced concerns and how this revision addresses them:

| Concern | Status |
|---------|--------|
| Subagent context-isolation is asserted not proved | Cited as "Claude Code Agent primitive" with platform reference; spec scope is Claude Code as host; portability to other hosts is explicitly out-of-scope |
| Findings file schema mismatch (3 competing shapes) | Reconciled: spec now mandates a top-level JSON array (matches existing `parse_findings_array`); rename of `raw_findings` to `findings` in `fixtures.py` is out of scope |
| `build-review-prompt` extracts code that doesn't exist | Acknowledged: today's prompt is `DEFAULT_REVIEW_PROMPT` (one-line constant). Phase 4a defines `build-review-prompt` as a thin assembly of constant + criteria bullets, NOT extraction of nonexistent per-kind logic. Per-kind opinionation deferred. |
| Subagent output JSON extraction handwaved | Resolved: new `orca-cli parse-subagent-response` subcommand takes raw subagent text on stdin, returns validated findings JSON. Slash command pipes; orca-cli validates. No "host LLM extracts JSON" step. |
| Mixed-mode dedupe behavior unclear | Documented: subagent-authored findings get distinct IDs from API-authored findings for the same logical issue; mixed mode bypasses dedupe by design. Test asserts the behavior. |
| `--codex-findings-file` symmetric is unfounded | Reframed as "operator-supplied codex findings, source-agnostic." Codex-host subagent dispatch is not claimed. |
| Path traversal / large-file / symlink risks | Addressed: orca-cli resolves `--*-findings-file` paths, rejects symlinks, caps file size at 10 MB. |
| Error table missed integration failure modes | Expanded: subagent timeout, host-LLM-skipped-the-step, concurrent runs, subject-binding mismatch, subagent-reviews-wrong-thing all listed. |
| Scope estimate too optimistic | Revised: 5-7 days realistic, with explicit best/typical/pessimistic. |
| "All existing tests pass" rhetoric | Removed. Replaced with verification commitment during impl. |
| "Capability-clean" framing | Replaced with concrete surface-area accounting. |

## Design Constraints

1. **orca-cli's reviewer dispatch primitive is unchanged.** New flags (`--claude-findings-file`, `--codex-findings-file`) and new subcommands (`build-review-prompt`, `parse-subagent-response`) are additions to the configuration surface, not changes to the capability shape. Cross-agent-review still consumes `RawFindings` from reviewer adapters and combines/dedupes them.
2. **Backward compatible.** Operators with `ANTHROPIC_API_KEY` + `ORCA_LIVE=1` continue working unchanged. SDK adapter remains the default when no file flag is present.
3. **Claude Code only for v1.** Subagent dispatch relies on Claude Code's `Agent` primitive (`Task` tool). Other hosts (Codex CLI, Cursor, Aider, plain shell) do not get the in-session reviewer benefit. They keep using SDK or fixtures. Documented explicitly; no silent fallback to wrong behavior.
4. **No auto-detection.** Operators explicitly pass `--claude-findings-file`. No `CLAUDECODE=1` magic.
5. **Findings schema = bare top-level JSON array.** Single shape, matching what `parse_findings_array` already consumes. Validator reuses `parse_findings_array` directly (no new parser, no shape mismatch).

## Architecture

Two new orca-cli subcommands and two new flags on `cross-agent-review`:

**`orca-cli parse-subagent-response`** - reads raw subagent text on stdin, extracts the JSON findings array, validates it via existing `parse_findings_array`, emits validated JSON on stdout (or `Err(INPUT_INVALID)` with a specific message). Failure surface lives in orca-cli; slash commands just pipe.

**`orca-cli build-review-prompt`** - emits the canonical review prompt on stdout. v1 implementation is `DEFAULT_REVIEW_PROMPT + "\n\nCriteria:\n" + bullet-list-of-criteria`. No per-kind opinionation (deferred). Used to feed the subagent the same prompt the SDK adapter passes.

**`--claude-findings-file <path>`** on `cross-agent-review` - when set, the claude reviewer slot uses `FileBackedReviewer` instead of `ClaudeReviewer`. File contents must be a top-level JSON array of findings.

**`--codex-findings-file <path>`** - symmetric. Operator-supplied; not tied to any specific producer.

The slash command (review-spec, review-code, review-pr) handles subagent dispatch BEFORE calling orca-cli:

1. Build prompt: `ORCA_PROMPT=$(orca-cli build-review-prompt --kind diff [--criteria ...])`.
2. Slash command instructs the host LLM (Claude Code) to dispatch a subagent via the `Agent` tool, passing `$ORCA_PROMPT` + the review subject.
3. Slash command captures the subagent's raw response text into a temp variable.
4. Slash command pipes the raw text through `orca-cli parse-subagent-response` to validate and extract the findings JSON. The result writes to `$FEATURE_DIR/.claude-findings.json`.
5. Calls `orca-cli cross-agent-review --reviewer cross --claude-findings-file <path>` for the rest. Codex side runs via SDK as before.

orca-cli stays focused on capability dispatch + findings validation. It does not call the `Agent` tool; the host LLM does that.

## Components

### New: `src/orca/core/reviewers/file_backed.py` (~50 lines)

```python
class FileBackedReviewer:
    """Loads pre-validated findings array from a JSON file. Used when the host
    harness has already authored the review (typically via subagent dispatch).

    The file MUST be a top-level JSON array of findings, matching the schema
    parse_findings_array already validates. orca-cli's parse-subagent-response
    subcommand is the recommended way to produce these files.
    """
    name: str
    findings_path: Path

    def review(self, bundle: ReviewBundle, prompt: str) -> RawFindings:
        # bundle and prompt are part of the adapter interface; ignored here
        # because findings are pre-authored. The host that wrote the file is
        # responsible for using a matching prompt + subject (Phase 4a does
        # not validate prompt-bundle parity at the file level).
        ...
```

`name` is `"claude"` or `"codex"`. Reviewer adapter interface unchanged.

Validation on read:
- Resolve path; reject if it's a symlink (defense in depth)
- Reject files larger than 10 MB (findings JSON should never approach this)
- Parse via `json.loads` after read
- Validate via existing `parse_findings_array` (top-level array shape, per-finding fields)
- All failures raise `ReviewerError(retryable=False, underlying="<specific>")` so the cross combiner reports it correctly

### New: `src/orca/python_cli.py` `_parse_subagent_response` (~30 lines)

```bash
orca-cli parse-subagent-response < raw-text
```

- Reads stdin (raw subagent response, may include markdown wrapping, prose, code fences, etc.)
- Tries to extract first top-level JSON array via existing regex in `_parse.py`
- Validates each finding's required fields
- On success: writes the validated array as JSON to stdout, exit 0
- On failure: emits `Err(INPUT_INVALID, message="parse-subagent-response: ...")` envelope on stdout, exit 1

This makes orca-cli the single source of validation. Slash commands pipe and trust the result.

### New: `src/orca/python_cli.py` `_build_review_prompt` (~15 lines)

```bash
orca-cli build-review-prompt --kind diff [--criteria correctness ...] [--context ...]
```

- v1 implementation: emits `DEFAULT_REVIEW_PROMPT` + criteria bullets + context if any. Plain text on stdout.
- No envelope, no metadata, no validation - just text assembly.
- `--kind` parameter is accepted for forward-compatibility but does not branch in v1 (per-kind prompts are explicitly deferred to Phase 4a-followup).

### Modified: `src/orca/python_cli.py` `_run_cross_agent_review` (~20 lines added)

Two new flags: `--claude-findings-file <path>`, `--codex-findings-file <path>`.

Reviewer-selection precedence (existing logic order, file-flag inserted at top):

```
For each reviewer slot in {claude, codex}:
  if --<reviewer>-findings-file set:
    use FileBackedReviewer(name=<reviewer>, findings_path=...)
  elif ORCA_FIXTURE_REVIEWER_<REVIEWER> set:
    use FixtureReviewer (existing behavior, test-only path)
  elif ORCA_LIVE=1 and backend resolvable:
    use SDK / CLI reviewer (existing behavior)
  else:
    return Err(INPUT_INVALID, "no reviewer source configured for {reviewer}")
```

Mixed mode (file-backed claude + SDK codex) is valid. Documented explicitly.

### Modified: `plugins/claude-code/commands/review-{spec,code,pr}.md`

Outline updated to insert subagent dispatch as a new step. Slash command markdown tells the host LLM:

```markdown
4a. Run the in-session claude reviewer (Claude Code only):

   ```bash
   ORCA_PROMPT=$(uv run orca-cli build-review-prompt \
     --kind diff \
     --criteria correctness --criteria security --criteria maintainability)
   ```

   Then dispatch a subagent via the Agent tool:
   - subagent_type: "Code Reviewer" (or "Senior Developer" for design specs)
   - description: "Cross-pass review of <subject>"
   - prompt: "$ORCA_PROMPT\n\n<paste subject content here>"

   Capture the subagent's response into a variable, then:

   ```bash
   echo "$SUBAGENT_RESPONSE" | uv run orca-cli parse-subagent-response \
     > "$FEATURE_DIR/.claude-findings.json"
   ```

   If parse-subagent-response exits 1, the subagent did not produce
   valid findings. Append a Round N - FAILED block to the artifact and
   stop; do NOT call cross-agent-review with a missing file.
```

This flow makes the failure modes mechanical:
- Subagent produces prose only -> parse-subagent-response fails with specific error -> slash command writes failure block, stops.
- Subagent produces malformed JSON -> same path.
- Subagent produces valid findings -> file written, cross-agent-review proceeds.

The host LLM dispatches the subagent (Claude Code primitive); orca-cli validates the output. Clean responsibility split.

## Data Flow

```
slash command
  -> (1) call: orca-cli build-review-prompt --kind diff [--criteria ...]
orca-cli
  -> stdout: canonical prompt text (DEFAULT_REVIEW_PROMPT + criteria)
slash command
  -> (2) host LLM dispatches subagent via Agent tool
host Claude Code
  -> subagent runs in fresh context (separate window per Claude Code platform docs)
subagent (Code Reviewer)
  -> returns response text (markdown wrapping JSON or prose)
slash command
  -> (3) capture raw response into $SUBAGENT_RESPONSE
slash command
  -> (4) pipe through: echo $SUBAGENT_RESPONSE | orca-cli parse-subagent-response
orca-cli
  -> extracts + validates + emits findings JSON OR Err(INPUT_INVALID)
slash command
  -> (5) if validated: write to $FEATURE_DIR/.claude-findings.json; else fail-block
slash command
  -> (6) call: orca-cli cross-agent-review --reviewer cross
                  --claude-findings-file $FEATURE_DIR/.claude-findings.json
                  --target <subject> --kind diff [--criteria ...]
orca-cli
  -> FileBackedReviewer reads file -> claude RawFindings
  -> CodexReviewer shells codex CLI -> codex RawFindings (or file-backed)
  -> combine + dedupe -> cross-agent envelope
slash command
  -> (7) call: orca-cli ... | python -m orca.cli_output render-review-X
```

## Findings File Schema

**Single shape:** top-level JSON array of finding objects. Matches what `parse_findings_array` already accepts.

```json
[
  {
    "id": "abc1234567890def",
    "category": "correctness",
    "severity": "high",
    "confidence": "high",
    "summary": "...",
    "detail": "...",
    "evidence": ["src/foo.py:42"],
    "suggestion": "...",
    "reviewer": "claude"
  }
]
```

NOT `{"findings": [...]}` (avoids the schema mismatch the reviewers caught). NOT `raw_findings` (that's `fixtures.py`'s legacy key for a different mechanism; out of scope to rename).

`parse-subagent-response` validates by piping to `parse_findings_array(text, source="subagent")`. Same validator the SDK adapter uses today.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `--claude-findings-file` path doesn't exist | `Err(INPUT_INVALID, "claude-findings-file: <path>: file not found")`, exit 1 |
| `--claude-findings-file` is a symlink | `Err(INPUT_INVALID, "claude-findings-file: symlinks rejected")`, exit 1 |
| File larger than 10 MB | `Err(INPUT_INVALID, "claude-findings-file: file exceeds 10 MB cap")`, exit 1 |
| File contains invalid JSON | `Err(INPUT_INVALID, "claude-findings-file: <parse-error>")`, exit 1 |
| File JSON is not a top-level array | `Err(INPUT_INVALID, "claude-findings-file: expected JSON array")`, exit 1 |
| Per-finding validation fails | `Err(INPUT_INVALID, "claude-findings-file: finding[<i>]: <field>: <reason>")`, exit 1 |
| `parse-subagent-response`: stdin has no JSON array | exit 1 with `Err(INPUT_INVALID, "no JSON array found in subagent response")` |
| `parse-subagent-response`: JSON found but invalid | exit 1 with specific error |
| Subagent timeout (5+ min) | Host LLM responsibility; Claude Code's Agent tool has its own timeout. orca-cli not involved. Slash command should write a Round N timeout block. |
| Subagent reviews wrong subject | Not detectable by orca-cli (no subject-binding hash in v1). Operator must read findings and confirm relevance. Tracked as Phase 4a-followup. |
| Concurrent slash-command runs on same feature | `$FEATURE_DIR/.claude-findings.json` race. Mitigation: slash command renames to `.claude-findings.<timestamp>.json` before write. Documented in slash command markdown. |
| Host LLM forgets to dispatch subagent (just calls cross-agent-review) | No `--claude-findings-file` flag means existing behavior: requires `ORCA_LIVE=1` + `ANTHROPIC_API_KEY` OR fixtures. If neither is set, returns `Err(INPUT_INVALID, "no reviewer source configured for claude")` exactly as today. Silent degradation does NOT happen because no flag = error, not silent SDK call. |
| Non-Claude-Code host runs the slash command | The slash command's "dispatch via Agent tool" step is markdown instructions to the host LLM. A non-Claude-Code host either (a) understands the instruction and uses its own subagent primitive, (b) doesn't understand and returns an error to operator, or (c) tries the orca-cli call without `--claude-findings-file` and gets the existing error path. Documented in slash command Prerequisites. |

## Backward Compatibility

- SDK path unchanged. `ORCA_FIXTURE_REVIEWER_*` path unchanged.
- New flags purely additive. Absent -> existing behavior.
- `RawFindings.metadata` gains optional `source: "in-session-subagent" | "sdk" | "fixture" | "file-backed"` and optional `findings_path: str`. Downstream `cli_output` renderers must tolerate either shape; existing renderers do this implicitly via `dict.get`.
- All existing tests EXPECTED to pass without modification. Verification step during impl: run full suite before any commit; if any test fails, fix it (or document the contract change).

## Testing Strategy

- **Unit:** `tests/core/reviewers/test_file_backed.py` (NEW, ~6 tests)
  - Reads valid file -> RawFindings shape correct
  - Symlink rejected
  - 11 MB file rejected
  - Invalid JSON rejected
  - Non-array top-level rejected
  - Per-finding validation failure has clear error message
- **Unit:** `tests/cli/test_python_cli.py` extension (~5 tests)
  - `--claude-findings-file` flag accepted; dispatcher uses FileBackedReviewer
  - `--codex-findings-file` symmetric
  - Mixed mode (file-backed claude + SDK codex when `ORCA_LIVE=1`)
  - Missing file -> exit 1
  - File-flag wins over fixture env var (precedence test)
- **Unit:** `tests/cli/test_python_cli.py` for `parse-subagent-response` (~4 tests)
  - Bare JSON array -> emits same array
  - Markdown-fenced JSON -> extracts and emits
  - Pure prose -> exit 1 with specific error
  - Invalid JSON -> exit 1 with parse error
- **Unit:** `tests/cli/test_python_cli.py` for `build-review-prompt` (~3 tests)
  - Returns prompt with criteria bullets when criteria passed
  - Returns base prompt when no criteria
  - `--kind` is accepted but does not branch (v1)
- **Integration:** end-to-end with both reviewers file-backed (~2 tests)
  - Synthetic claude findings file + synthetic codex findings file
  - Resulting envelope matches existing cross-agent envelope contract
  - Mixed-mode dedupe behavior asserted: subagent + SDK findings of "same logical issue" produce DIFFERENT IDs and are unioned, not deduped
- **Slash command smoke (manual, NOT automated):** in `~/spec-kit-orca`, run `/orca:review-code` against a small diff. Verify subagent dispatched, findings file produced, envelope rendered. This is the highest-risk part; budget half a day for iteration.

## Out of Scope (Phase 4a)

- Per-kind prompt opinionation (`build-review-prompt` v1 emits a constant + criteria; per-kind branching deferred to Phase 4a-followup if demand emerges)
- perf-lab integration shim (Phase 4b)
- Auto-detection via env var
- Subject-binding validation (subagent reviews wrong feature dir not detectable in v1)
- Codex-host subagent dispatch (file flag exists; codex-side host wiring not provided)
- Renaming `fixtures.py`'s `raw_findings` key for schema convergence (orthogonal cleanup)

## Repo Migration

Stack: branched off `orca-phase-3-plugin-formats`. If Phase 3 (PR #70) merges cleanly, rebase Phase 4a onto main. If Phase 3 changes during review of Phase 4a, expect rebase conflicts on slash command markdown.

- New: `src/orca/core/reviewers/file_backed.py`
- New tests: `tests/core/reviewers/test_file_backed.py`, additions to `tests/cli/test_python_cli.py`
- Modified: `src/orca/python_cli.py` (cross-agent-review dispatcher + `parse-subagent-response` + `build-review-prompt`)
- Modified: `plugins/claude-code/commands/review-{spec,code,pr}.md` (subagent dispatch step)
- Modified: `plugins/codex/AGENTS.md` (document new flags + parse-subagent-response)
- No schema breaking changes. CAPABILITIES registry unchanged at the capability level (cross-agent-review still has `name = "cross-agent-review"`); `parse-subagent-response` and `build-review-prompt` are utility subcommands, not capabilities.

## Scope Estimate

Realistic: **5-7 days** of focused work. Best-case 4 days; pessimistic 8 if the slash-command smoke uncovers integration surprises (Phase 3 had 3 review rounds; Phase 4a touches similar surface).

Breakdown:
- `FileBackedReviewer` + tests: 0.5 day (small adapter, schema validation reuses existing helpers)
- `parse-subagent-response` subcommand + tests: 1 day (regex extraction + validation; surprises possible)
- `build-review-prompt` subcommand + tests: 0.5 day (trivial assembly)
- `--claude-findings-file` / `--codex-findings-file` flag wiring + tests: 0.5 day
- 3 slash command updates with subagent dispatch wording: 1 day
- Slash-command smoke testing + iteration on subagent prompt + extraction reliability: 1-2 days (high-risk integration)
- AGENTS.md update + plumbing verification: 0.5 day
- Review cycles (Phase 3 averaged 3 rounds): 0.5-1 day buffer

The 1-2 day smoke-testing item is the long pole. If subagent dispatch + parse-subagent-response works on the first try, this collapses to 0.5; if not, multiple iterations on prompt phrasing and extraction patience.

## Honest Value Statement

What Phase 4a uniquely delivers:

1. **Removes the "Claude reviewing self via API" identity collapse** in the Claude Code host case. Replaces API roundtrip with subagent dispatch.
2. **Operators without `ANTHROPIC_API_KEY` can run cross-pass reviews.** Phase 3 Round 1's failure mode (no key -> entire pass fails) is fixed for Claude Code hosts.
3. **Adds two reusable orca-cli primitives** (`parse-subagent-response`, `build-review-prompt`) usable beyond cross-agent-review. perf-lab Phase 4b can use the same primitives without re-deriving.

What Phase 4a does NOT deliver:

- A general "in-session reviewer" abstraction. v1 is Claude-Code-shaped. Codex CLI / Cursor / Aider don't get the benefit; they keep using SDK or fixtures.
- Per-kind prompt opinionation. v1's `build-review-prompt` is `DEFAULT_REVIEW_PROMPT + criteria bullets` only.
- Auto-detection of host. Operators pass the file flag explicitly.
- Subject-binding (the subagent could review the wrong thing and orca-cli wouldn't know).

## Resolved Design Decisions

- **Subagent dispatch is host-LLM responsibility.** orca-cli has no Agent-tool access; correctly factored.
- **JSON extraction is orca-cli's responsibility.** New `parse-subagent-response` subcommand owns the validation. Slash commands pipe; orca-cli validates. Removes the "host LLM hand-extracts JSON" handwave.
- **File schema is bare top-level array.** Matches existing `parse_findings_array`. Avoids three-shape mismatch.
- **`build-review-prompt` is light v1.** Constant + criteria bullets. Per-kind opinionation deferred (acknowledges no extractable code exists today).
- **No auto-detection.** Explicit `--claude-findings-file` flag.
- **Symmetric `--codex-findings-file` ships at the same time but is not "subagent-symmetric."** Reframed as "operator-supplied codex findings, source-agnostic."
- **Claude Code is the only host with subagent-driven flow.** Other hosts get SDK, fixtures, or a new operator-supplied path. Documented in slash command Prerequisites.
- **Phase 4a stacks on PR #70.** Rebase risk acknowledged; folding into Phase 3 was considered but rejected because Phase 3 is review-stable.
