# Worktree Manager Spec Review

**Spec:** docs/superpowers/specs/2026-04-30-orca-worktree-manager-design.md
**Reviewer:** Cross-pass (Code Reviewer subagent)
**Date:** 2026-04-30

### Round 1 - Cross-pass

**Verdict:** needs-revision

#### Findings

##### [BLOCKER] Registry/sidecar schema is NOT backward-compatible with the legacy reader
**Criterion:** cross-spec-consistency
**Issue:** The spec at lines 270-284 claims the new `registry.json` is "Backward-compatible with the legacy schema read by `sdd_adapter._load_worktree_lanes`," but the proposed shape contradicts the existing reader. Today the reader (lines 815-845 of `src/orca/sdd_adapter.py`) treats `registry["lanes"]` as a flat list of lane-id **strings**, then opens `<lane_id>.json` per entry and reads sidecar fields `feature` (or `id`), `branch`, `status`, `path`, `task_scope`. The new spec proposes (a) `lanes` as a list of **objects** with key `lane_id`, and (b) sidecars keyed `feature_id` / `lane_id` / `worktree_path` (no `feature`, `id`, `path`, `status`, or `task_scope`). After this lands, `_load_worktree_lanes` will fail at line 821 (`worktree_root / f"{lane_id}.json"` — `lane_id` is a dict) and return `[]` for every lane, silently breaking `flow-state-projection` and `worktree-overlap-check`.
**Evidence:** Spec lines 270-284 vs. `src/orca/sdd_adapter.py:815-845`. Spec line 284 explicitly asserts "continue reading without changes; the new manager becomes the single writer," which is false under the proposed shape.
**Recommendation:** Either (a) make the new writer emit the legacy schema verbatim and add the richer fields as additive sidecar keys (`feature_id` alongside `feature`/`id`, `worktree_path` alongside `path`, keep `lanes` as `["015-wizard", ...]`), or (b) bump `schema_version` to 2, ship a one-shot migrator, and update `_load_worktree_lanes` in the same PR. Decide explicitly; do not ship a writer/reader mismatch.

##### [BLOCKER] Path-safety identifier max-length contradicts the contract
**Criterion:** cross-spec-consistency
**Issue:** Spec line 242 states lane-ids "max 64 chars" and reuses `validate_identifier` from path-safety consolidation. The path-safety contract (`docs/superpowers/contracts/path-safety.md` Class D, line 74) and consolidation design both specify **128 characters**. If `wt` calls `validate_identifier` directly, 65-128-char lane-ids pass the validator but then violate the spec's own rule (silent drift). If `wt` adds its own 64-char check on top, the spec must say so and document why lane-ids need a tighter cap than other identifiers (presumably tmux 32-char window-name limit, but that's already truncated separately at line 290).
**Evidence:** Spec line 242 ("max 64 chars") vs. path-safety contract line 74 ("Maximum length 128 characters") vs. spec line 290 (tmux window-name truncation at 32).
**Recommendation:** Pick one. Best path: align lane-ids to the contract's 128-char limit, document tmux window-name truncation as a separate (post-validation) concern, and remove the 64-char number from §"Lane-id rules". If a tighter cap is genuinely needed, define it via a `validate_identifier(..., max_len=64)` parameter rather than inline duplication.

##### [BLOCKER] Inline path-safety fallback is not actually specified
**Criterion:** dependencies
**Issue:** Spec line 380 says "If the worktree manager ships first, the manager carries inline equivalents that are migrated to the shared helpers when path-safety consolidation lands." No inline implementation is sketched, no validator surface area is enumerated, no migration plan is given. This is a load-bearing dependency for every CLI flag (line 384 matrix). The 5-day estimate appears to assume the shared module exists. Today `src/orca/core/path_safety.py` does NOT exist — `grep` of the tree shows no module and no callers. So either (a) `wt` waits on path-safety consolidation (slipping the timeline), (b) `wt` ships duplicate validation that has to be deleted later (which the spec hand-waves), or (c) path-safety consolidation is bundled into this PR (which doubles the scope and isn't in the effort estimate).
**Evidence:** Spec lines 378-389 ("ships inline if needed") + absence of `src/orca/core/path_safety.py` in the tree + path-safety consolidation design's own status ("Design (pre-implementation)").
**Recommendation:** Pick the dependency order before plan-writing. Either: (1) declare path-safety consolidation a hard prerequisite (block this PR on it; remove "ships inline if needed" hedge), (2) inline the four-validator surface here with explicit code sketches and an estimate adjustment (+0.5-1 day), or (3) ship path-safety consolidation as the first commit of this PR. Document the choice in §"Path-safety".

##### [HIGH] Registry concurrent-write semantics are unspecified
**Criterion:** industry-patterns
**Issue:** The spec mentions "atomic writes" (line 419) and "concurrent-writer safety" as a unit-test goal, but specifies no locking, no sequence-token, and no conflict-resolution behavior. Two `wt new` invocations racing for the same `registry.json` (e.g., the operator runs `wt new` in two terminals, or a `wt doctor --reap` overlaps a `wt rm`) will both read the file, both append their entry, both atomically rename — and one wins. Atomic rename is necessary but not sufficient for correctness; you also need read-modify-write protection.
**Evidence:** Spec lines 246 ("Atomic write") and 420 ("concurrent-writer safety") with no implementation strategy. Symphony's reference (`~/symphony/SPEC.md`) handles this with file locks; the spec borrows Symphony's hook pattern but not its concurrency model.
**Recommendation:** Specify the strategy: `fcntl.flock(LOCK_EX)` on `registry.json` for the duration of read-modify-write, plus retry-on-EWOULDBLOCK with a small backoff. Document the lock holder, the timeout, and the failure mode (exit 75 / EX_TEMPFAIL). Add a contended-write integration test that spawns two writers and asserts both lanes land.

##### [HIGH] Idempotency rules underspecified for the worktree-exists-but-mismatched cases
**Criterion:** feasibility
**Issue:** Spec lines 121-123 say "`wt new <branch>` where the branch already has a worktree attaches instead of erroring." Real-world states this hides:
1. Branch exists locally but no worktree (operator did `git checkout -b foo` previously). `git worktree add` will refuse without `-B` or a different branch flag — does `wt new` detect this and error, attempt `-B`, or co-opt the branch?
2. Worktree exists at a path different from the lane-id-derived path (operator ran `git worktree add ../scratch foo` outside orca). Does `wt new` use the existing path and write a sidecar pointing at it, or refuse?
3. Sidecar exists for `<lane-id>` but the underlying `git worktree` was force-removed. Does `wt new` clean up the stale sidecar and create fresh, or refuse?
4. Branch matches but `lane_id_mode = "auto"` resolves a different lane-id than the existing sidecar. Does it attach by branch or refuse on lane-id mismatch?
**Evidence:** Spec lines 120-123 + line 374 ("Sidecar where `worktree_path` is missing on disk → mark `orphaned`"). The doctor section knows about (3) but `wt new`'s behavior in that state is undefined.
**Recommendation:** Add a §"Idempotency state machine" subsection enumerating the (branch-exists, worktree-exists, sidecar-exists, registry-entry-exists) cube and the action taken for each cell. At minimum specify cases 1-4 above with concrete behavior.

##### [HIGH] Hook scripts execute with full operator privilege; no authenticity verification before first run
**Criterion:** security
**Issue:** Spec lines 194-211 describe `after_create` as a bash script committed to the repo. The `setup_version` SHA in the sidecar (line 262) is computed *after* the script runs the first time — so a malicious commit that modifies `after_create` is executed unconditionally on the next `wt new`. Cloning a hostile repo and running `orca-cli wt new feat` is RCE-equivalent. The spec has no opt-in confirmation, no per-script-hash trust ledger, no "review before run" prompt.
**Evidence:** Spec lines 194-211 (Stage 2) + line 262 (`setup_version` "sha256 of after_create when last run"). No mention of trust-on-first-use, signing, or a confirmation flow.
**Recommendation:** Add at minimum: (a) on first run for a given repo OR when the script's hash differs from a `~/.config/orca/worktree-trust.json` ledger, print the script + diff and prompt for confirmation (skippable via `--trust-hooks` or `ORCA_TRUST_HOOKS=1`); (b) document that `--no-setup` is the safe default for untrusted repos; (c) note this in adoption documentation. Symphony's reference handles the equivalent risk by requiring explicit operator opt-in for hook execution.

##### [HIGH] tmux session-name templating doesn't sanitize `{repo}` substitution
**Criterion:** security
**Issue:** Spec lines 168 and 290 show `tmux_session = "work-{repo}"` and "templated with `{repo}`". `{repo}` likely resolves to the repo directory name. tmux session names allow most characters, but the spec passes the resolved name to `subprocess.run(['tmux', 'new-session', '-s', session_name, ...])`. A repo named `'; rm -rf $HOME #` is fine for `subprocess.run` (args list, not shell), but the same name flows into the sidecar JSON, into events.jsonl, into `wt ls` table output, and possibly into the agent-launch `send-keys 'agent-cmd'` string. There's no documented sanitization or character whitelist for `{repo}`. Worse, repo names with `:` or `.` collide with tmux's window-target syntax (`session:window`).
**Evidence:** Spec lines 168, 290, 296-297. No sanitization rule for `{repo}`.
**Recommendation:** Define a `{repo}` sanitization rule (e.g., `[^A-Za-z0-9._-]` → `_`, max 64 chars) before substitution. Apply the same rule any other template tokens added. Add unit tests for repos named with `:`, spaces, shell metacharacters, and unicode. Document the rule in §"tmux integration".

##### [HIGH] Setup-hook env injection via `shlex.quote` doesn't cover agent-launch arg interactions
**Criterion:** feasibility
**Issue:** Spec line 389 says "Hook env values are quoted via `shlex.quote` before injection." That's correct for the env contract (lines 199-205). But the *agent-launch* path is `tmux send-keys -t <target> '<agent-cmd>' Enter` (line 297), and `<agent-cmd>` comes from `[worktrees.agents] claude = "claude --dangerously-skip-permissions"` plus operator-supplied `-p <prompt>` and `-- <agent-args...>`. The spec doesn't say how those are joined, quoted, or passed to `send-keys`. `tmux send-keys` literally types characters into the pane — quoting at the subprocess layer doesn't matter; what matters is what the shell in the pane sees. A prompt containing `'; rm -rf ~/ #` types exactly that into the shell.
**Evidence:** Spec lines 297, 102 (`-p <prompt>`), 156 (agent command strings). Line 389 only addresses hook env, not the send-keys path.
**Recommendation:** Specify the send-keys quoting strategy explicitly. Options: (a) write the agent invocation to a tempfile inside the worktree (`.orca/worktrees/.run-<lane>.sh`) and `send-keys 'bash <path>' Enter`, (b) build the command as a single shlex-quoted string and `send-keys -l` (literal mode) before `Enter`. Add a unit test for prompts containing single-quotes, backticks, `$()`, and newlines.

##### [HIGH] Stale tmux state recovery after server restart not addressed
**Criterion:** industry-patterns
**Issue:** After `tmux kill-server` or a reboot, every sidecar's `tmux_session` / `tmux_window` claim is stale but the sidecar persists. `wt start <branch>` at line 300-305 says "Recreate tmux session/window if missing" — fine. But `wt ls` (presumably enriched with last-activity from events.jsonl per line 354) will show all lanes with seemingly-active tmux state until `wt doctor` runs. There's no specified TTL, no liveness check at list-time, no event emitted on tmux-server death.
**Evidence:** Spec lines 300-305, 354, 369 ("tmux windows correspond to live lanes" — only checked by doctor). No `wt ls` liveness probe specified.
**Recommendation:** Either (a) `wt ls` runs a `tmux list-windows -t <session>` probe and reports stale entries inline, or (b) `wt ls` documents that its tmux state column is point-in-last-event (not live), and operators must run `wt doctor` to reconcile. Pick one and document. Also: emit a `tmux.session.killed` event when `wt rm` finds the session already dead, so events.jsonl reflects reality.

##### [HIGH] Symlink TOCTOU + Stage-1 idempotency race
**Criterion:** security
**Issue:** Stage 1 (line 191) says "existing real files block with an error (refuse to clobber)." The check-then-symlink sequence is `os.path.lexists` → `os.symlink` (or stat → unlink → symlink for the "wrong symlink" case). Between those calls, the path can be replaced. On a multi-tenant or hostile filesystem (e.g., `/tmp` worktrees, CI bind mounts where multiple jobs share scratch), an attacker could swap a real file in between the check and the unlink, causing orca to delete a file it didn't intend to. Even on a single-user box, two concurrent `wt new` invocations can race the symlink layer.
**Evidence:** Spec line 191 ("existing real files block with an error; existing-but-wrong symlinks are replaced"). No O_NOFOLLOW / openat / link-then-rename strategy described.
**Recommendation:** Specify the safe sequence: `os.symlink(target, tmp_link_in_same_dir)` then `os.replace(tmp_link, final)` (atomic rename, no TOCTOU). For the "real file blocks" case, use `os.lstat` on the final path with `O_NOFOLLOW` semantics and refuse if it's a regular file; do NOT unlink in the same path. Document and test.

##### [MEDIUM] `[worktrees]` config block lives inside `adoption.toml` — confused ownership
**Criterion:** cross-spec-consistency
**Issue:** Spec line 130 puts `[worktrees]` inside `.orca/adoption.toml`. The 015 brownfield spec (lines 113-148 of `2026-04-29-orca-spec-015-brownfield-adoption-design.md`) defines `adoption.toml` with `[host]`, `[orca]`, `[slash_commands]`, `[claude_md]`, `[constitution]`, `[reversal]` sections — every section there is **adoption-time policy** (set once, read by `orca-cli apply`). `[worktrees]` is **runtime configuration** (set once, read by every `wt new`). Co-locating them means: (a) every worktree config edit is a manifest revision (which 015 dedupes via content hash for its backup logic — line 196), (b) the `wt config` writer (line 116) becomes a manifest mutator and must coordinate with `orca-cli apply --revert`, (c) two PRs touching adoption-time vs. runtime concerns will conflict on the same file.
**Evidence:** Spec line 130 vs. spec 015 lines 113-148.
**Recommendation:** Move `[worktrees]` to a sibling file `.orca/worktrees.toml` (committed) with the same `worktrees.local.toml` override semantics. Keep `adoption.toml` for adoption policy only. Cross-link in both specs.

##### [MEDIUM] `wt init` ecosystem detection is naive for monorepos
**Criterion:** feasibility
**Issue:** The detection table (lines 220-232) checks for top-level signal files. A monorepo with `apps/web/package.json` (npm), `apps/api/pyproject.toml` (uv), and a top-level `package.json` for tooling will get a single `npm install` line and miss the per-package installs. A monorepo with both `bun.lockb` and `pnpm-lock.yaml` (in process of migrating) gets whichever case the table matches first. The spec's "plain bash. editable" claim (line 233) is the escape hatch, but `wt init` users are likely the least-experienced operators (it's the onboarding command) and least-able to fix the generated script.
**Evidence:** Spec lines 218-233. No mention of monorepo, glob walking, or detection failure modes.
**Recommendation:** Either (a) explicitly document the table as "top-level only; monorepos: edit by hand," and emit a warning if the spec finds matching signal files in subdirectories, or (b) walk one level down (`apps/*`, `packages/*`) and emit one install line per detected package. Pick one; the current handwave will produce confused bug reports.

##### [MEDIUM] Capability vs. utility classification is implicit, not declared
**Criterion:** cross-spec-consistency
**Issue:** The toolchest north-star (`2026-04-26-orca-toolchest-v1-design.md` lines 79-114) lists six capabilities, each with a JSON contract, each invocable as `orca <capability>`. The spec adds `orca-cli wt <verb>` — a top-level subcommand with its own verb tree, no capability JSON contract, no entry in `contracts/capabilities/`. The spec is silent on whether `wt` is a seventh capability, a "utility subcommand" (different category), or a sui generis CLI surface. This matters for: (a) does `wt` get a `contracts/capabilities/wt.json` schema? (b) does it surface in `orca-cli list-capabilities`? (c) does it appear in adoption.toml's `installed_capabilities` list (currently 6 names per 015 line 124-131)?
**Evidence:** Toolchest design lines 79-114, 218-219 ("Every capability returns one of two JSON shapes"); this spec has no JSON-shape commitment for `wt` outputs (e.g., `wt ls --json`).
**Recommendation:** Add a §"Classification" paragraph stating explicitly: "`wt` is a utility subcommand, not a v1 capability — it does not appear in `installed_capabilities`, does not have a JSON contract, and is exempt from the data-shape commitments in `2026-04-26`." OR commit to a contract and write it. Also specify the `wt ls --json` shape — operators *will* script against it.

##### [MEDIUM] `.worktree-contract.json` perf-lab compatibility code path is out of scope but in scope
**Criterion:** dependencies
**Issue:** Lines 396-411 describe `.worktree-contract.json` as a future cross-repo migration tracked separately, but line 410 says "orca (`wt init` honors natively)." If `wt init` reads `.worktree-contract.json` and converts it to orca's hook + symlink config, that's a non-trivial code path (parse contract, validate schema, translate to `[worktrees]` block, generate `after_create` from the contract's script reference). The 5-day effort estimate (lines 443-456) does not budget this. If `wt init` does NOT honor it natively in v1, line 410 is wrong and perf-lab compatibility is undelivered.
**Evidence:** Spec line 410 vs. line 449 ("`wt init` (script generation): 0.25 days").
**Recommendation:** Decide: either (a) drop "honors natively" from line 410 and document this as Phase 2, or (b) add 0.5 days to the estimate, write the schema for `.worktree-contract.json` in this spec (not separately), and add unit tests. Prefer (a).

##### [LOW] Shell completion for `wt cd <branch>` not in scope but referenced
**Criterion:** industry-patterns
**Issue:** Line 106-110 designs `wt cd` for `$(...)` wrapping, which implies operators will tab-complete branch names. Completion script generation (`bash`/`zsh`/`fish` completion) is not listed in scope or out-of-scope. Without it, `wt cd <branch>` UX is "type the full branch name from memory" — the cmux UX parity claim weakens.
**Evidence:** Spec lines 106-110, scope list lines 20-28 (no completion mention), out-of-scope list lines 29-38 (no exclusion either).
**Recommendation:** Add to out-of-scope explicitly OR add a 0.25-day line item for `orca-cli wt completion bash|zsh|fish` script emission. Either is fine; ambiguity is not.

##### [LOW] Worktree base-path collision on repos that use `worktrees/` for app code
**Criterion:** industry-patterns
**Issue:** Default `base = ".orca/worktrees"` (line 134) is namespaced and safe. But the `wt init` flow doesn't probe whether the repo already has a `worktrees/` directory (some monorepos use it for git submodules or generated code). Not a real conflict given the `.orca/` prefix, but `wt doctor` and `wt ls` output may be confusing if the operator's PWD is inside `<repo>/worktrees/` (their own `worktrees/`, not orca's).
**Evidence:** Spec line 134 + no probe in `wt init` flow.
**Recommendation:** Low priority; just document in `wt init` output ("orca worktrees live at `.orca/worktrees/`; this is unrelated to any existing `worktrees/` directory in your repo"). One-line fix.

#### Summary

| Severity | Count |
|---|---|
| Blocker | 3 |
| High | 7 |
| Medium | 4 |
| Low | 2 |

Three blockers prevent shipping as-is: a registry/sidecar schema break disguised as backward-compat (will silently break existing `flow-state-projection` and `worktree-overlap-check` reads), an identifier-length contradiction with the path-safety contract (silent drift), and an unspecified inline path-safety fallback that the 5-day estimate appears to assume away. Seven highs cover real runtime sharp edges (concurrent-writer races, idempotency state-cube gaps, hook RCE-on-clone, tmux template injection, agent-launch send-keys quoting, tmux server-restart staleness, and symlink TOCTOU). Recommend: resolve the 3 blockers and at least the top 4 highs (registry concurrency, idempotency state machine, hook trust, send-keys quoting) before plan-writing. The medium/low items can be tracked as plan-time notes.

### Round 2 - Author response

**Verdict:** all 16 findings addressed in spec v2 (commit follows).

| Finding | Resolution |
|---|---|
| BLOCKER #1 registry schema break | Bumped to schema_version 2; v2 sidecars emit BOTH new and legacy field names for read-side compat; reader at `src/orca/sdd_adapter.py:799-845` updated in same PR; one-shot migrator on first wt invocation |
| BLOCKER #2 identifier max-length | Aligned to 128 chars (path-safety contract Class D); tmux 32-char window-name truncation documented as separate post-validation concern |
| BLOCKER #3 inline path-safety hand-waved | Hedge removed; declared hard prerequisite (must land first or as lead commit of this PR); 5-day estimate revised to 7 days |
| HIGH #4 concurrent writes | `fcntl.flock(LOCK_EX)` on `registry.lock` (separate file) with 30s timeout, `EX_TEMPFAIL` on contention; Windows: `msvcrt.locking` |
| HIGH #5 idempotency state cube | New §"Idempotency state machine" with 8-row table; `--reuse-branch` flag for branch-without-worktree case |
| HIGH #6 hook RCE on clone | Trust-on-first-use ledger at `~/.config/orca/worktree-trust.json`; prompt on first run / SHA change; `--trust-hooks` and `--no-setup` escape hatches; CI-non-interactive guard |
| HIGH #7 tmux `{repo}` injection | Sanitization rule defined: `[^A-Za-z0-9._-]` → `_`, `:` and `.` also replaced; truncated to 64 chars; tested |
| HIGH #8 send-keys agent quoting | Tempfile-script approach: write `.orca/.run-<lane>.sh`, set `ORCA_INITIAL_PROMPT` via `tmux set-environment` (subprocess args, not shell), `send-keys 'bash <path>' Enter` |
| HIGH #9 stale tmux state | `wt ls` runs `tmux list-windows` probe; emits `tmux.session.killed` event on first observed missing |
| HIGH #10 symlink TOCTOU | Atomic-rename pattern: symlink to `.tmp-<pid>-<rand>`, `os.replace` to final; `O_NOFOLLOW` semantics on lstat check |
| MEDIUM #11 [worktrees] in adoption.toml | Moved to sibling `.orca/worktrees.toml`; adoption.toml stays adoption-time policy only |
| MEDIUM #12 wt init monorepo | Documented as top-level only; warning emitted when subdirectory signals detected; auto-walk tracked as Phase 2 |
| MEDIUM #13 capability classification | New §"Classification" stating wt is a utility subcommand, not a v1 capability; JSON shapes for `wt ls --json` and `wt config --json` committed |
| MEDIUM #14 perf-lab .worktree-contract.json | Moved entirely to Phase 2; v1 ships orca-only; documented |
| LOW #15 shell completion | Explicit out-of-scope for v1; tracked as Phase 2 |
| LOW #16 worktrees/ collision | One-line note in `wt init` output |

**Outstanding from review:** none. Re-review encouraged before plan-writing if any change is suspect.

### Round 2 - Re-review of v2

**Verdict:** needs-revision

#### Verification of round-1 findings

1. **BLOCKER #1 registry schema break** — ⚠️ partially resolved. v2 spec lines 331-376 introduce `schema_version: 2`, dual-emit legacy fields, an in-PR reader update, and a one-shot migrator. The sidecar dual-emit (line 347-363) genuinely keeps `_load_worktree_lanes` working at the sidecar layer. **But** the registry shape change is not actually compatible with the unmodified reader: today's `sdd_adapter.py:815-820` reads `lanes` as strings and iterates `lane_id` as a string into `worktree_root / f"{lane_id}.json"`. With v2 emitting lane objects (line 340-344), an unupdated reader builds `Path / dict`, which raises `TypeError`. The spec promises the reader is "updated in the same PR" (line 333, 367-370) but does not include a defensive code path for "v2 registry encountered by old reader" (e.g., a downstream consumer pinned to an older orca version). Either commit to writing v1 registry shape until a hard cutover OR document that schema_version 2 is a hard incompatibility for older readers and bump orca's own version pin.
2. **BLOCKER #2 identifier max-length** — ✅ resolved. Line 301 aligns to 128; tmux 32-char truncation documented as separate (line 303).
3. **BLOCKER #3 inline path-safety hand-wave** — ✅ resolved. Lines 156-158 declare hard prerequisite; hedge removed.
4. **HIGH #4 concurrent writes** — ⚠️ partially resolved. `fcntl.flock` strategy specified (lines 378-384), but Windows fallback (`msvcrt.locking(LK_NBLCK)`) is one line and underspecified — see new finding NEW-1.
5. **HIGH #5 idempotency state cube** — ✅ resolved. 8-row table at lines 128-138 with `--reuse-branch` semantics. One subtle internal asymmetry flagged in NEW-2.
6. **HIGH #6 hook RCE on clone** — ⚠️ partially resolved. TOFU ledger described (lines 237-247) but the trust-ledger location and the `--trust-hooks` interaction with the ledger are underspecified — see NEW-3 and NEW-4.
7. **HIGH #7 tmux `{repo}` injection** — ✅ resolved. Sanitization rule at lines 392-394 with explicit `:` and `.` replacement.
8. **HIGH #8 send-keys agent quoting** — ❌ not actually fixed. Tempfile-script approach is correct in principle, but the cleanup story is broken (`exec claude` makes "self-deletes after exec" impossible) and `tmux set-environment` leaks the prompt into other windows in the same session — see NEW-5 and NEW-6.
9. **HIGH #9 stale tmux state** — ✅ resolved. `wt ls` runs `tmux list-windows`; `tmux.session.killed` event emitted on first observed missing.
10. **HIGH #10 symlink TOCTOU** — ⚠️ partially resolved. Atomic-rename pattern is correct on POSIX (lines 226-235) but the Windows `mklink /J` fallback path through `os.replace` is asserted without verification — see NEW-7.
11. **MEDIUM #11 [worktrees] in adoption.toml** — ⚠️ partially resolved. File moved to `.orca/worktrees.toml` (lines 162-164), but the adoption-flow integration is dropped — see NEW-8.
12. **MEDIUM #12 wt init monorepo** — ✅ resolved. Lines 291-293 document top-level-only with subdirectory warning.
13. **MEDIUM #13 capability classification** — ✅ resolved. Lines 152-154 declare wt as utility subcommand; JSON shapes committed in §"JSON output shapes" (lines 458-478).
14. **MEDIUM #14 perf-lab `.worktree-contract.json`** — ✅ resolved. Moved entirely to Phase 2 (lines 41, 538-556).
15. **LOW #15 shell completion** — ✅ resolved. Explicit out-of-scope at line 40.
16. **LOW #16 worktrees/ collision** — ✅ resolved. One-line note at line 293.

#### New findings (introduced by v2 revisions)

##### [HIGH] NEW-1: Windows registry locking semantics differ from POSIX without spec coverage
**Criterion:** industry-patterns
**Issue:** Line 382 says "Windows: `msvcrt.locking(LK_NBLCK)` with the same retry loop. Documented as best-effort on Windows." `msvcrt.locking` is mandatory byte-range locking — fundamentally different from `fcntl.flock`'s advisory whole-file lock. The spec doesn't specify which byte range to lock (typical idiom: byte 0 with length 1), what happens when the lock file is empty (a common case before any write — `msvcrt.locking` on byte 0 of a 0-byte file fails with EINVAL), or how the retry loop interacts with `LK_NBLCK`'s immediate-fail behavior. "Best-effort" on the most contended primitive in the system is hand-waving. A second `wt new` on Windows during a slow `after_create` could either deadlock the retry loop or silently corrupt the registry.
**Evidence:** Line 382 (single sentence) vs. lines 378-381 (POSIX path is fully specified).
**Recommendation:** Specify the Windows path concretely: ensure the lock file has at least 1 byte (write a sentinel on first creation), lock byte 0 with length 1, retry on `OSError` with `errno.EACCES`/`EDEADLK`, document that the retry loop on Windows is `LK_NBLCK + sleep + retry` (not `LK_LOCK` blocking, which can deadlock). Add a Windows contended-write integration test (or explicitly document that Windows is unsupported for concurrent `wt new` and have `wt new` refuse if it detects another running instance via PID file).

##### [HIGH] NEW-5: Tempfile-script cleanup is broken — `exec` precludes self-delete
**Criterion:** feasibility
**Issue:** Line 402-404 specifies the agent-launch script as `exec claude --dangerously-skip-permissions --prompt "$ORCA_INITIAL_PROMPT"`. Line 407 then says "Cleanup: the script self-deletes after exec OR is removed by `wt rm`." This is incoherent: `exec` replaces the shell process with claude, so no script lines after `exec` ever execute. There is no "after exec" — the script process is gone. So `<worktree>/.orca/.run-<lane>.sh` accumulates indefinitely until `wt rm`. If the agent crashes mid-run and the operator runs `wt start` (which presumably re-launches), the old script is overwritten — fine — but in the gap window, the stale script is still on disk. More importantly, if the operator's prompt (encoded in `$ORCA_INITIAL_PROMPT` at the time of launch) is sensitive (API keys pasted into the prompt, secret feature names), it lingers on disk in the script's argv path until `wt rm`.
**Evidence:** Lines 401-407. The `exec` keyword on line 403 contradicts the "self-deletes after exec" claim on line 407.
**Recommendation:** Pick one: (a) drop `exec` and add `rm -f "$0"` after the agent exits (script stays alive as parent of agent — wastes one shell PID per lane), (b) keep `exec` and accept that cleanup is `wt rm`-only; explicitly document that the script persists for the lane's lifetime, (c) write the script to `$(mktemp)` outside the worktree and let OS tmpdir cleanup handle it (loses gitignored-in-worktree property). Whichever path, fix the contradiction. Also: `$ORCA_INITIAL_PROMPT` flows through `tmux set-environment` (no shell interpolation) but the script then references it as `"$ORCA_INITIAL_PROMPT"` — which IS shell-interpolated by bash inside the script. That's safe for double-quoted values but the spec should note that.

##### [HIGH] NEW-6: `tmux set-environment` is session-scoped — prompt leaks into all windows
**Criterion:** security
**Issue:** Line 405 says "Set the prompt as an env var on the spawned shell via `tmux set-environment -t <session> ORCA_INITIAL_PROMPT '<value>'`." `tmux set-environment` without `-g` is session-scoped (not window-scoped) and is inherited by ALL future panes/windows opened in that session via tmux's update-environment list. Two consequences: (1) lane B opened after lane A in the same session sees `ORCA_INITIAL_PROMPT` from lane A in its env — confusing at best, exfiltrating-sensitive-prompt-content at worst (operators paste secrets into prompts); (2) if the operator opens any non-orca pane in the same session (e.g., `tmux split-window` to run `htop`), that pane's environment also has the prompt. There is no per-window scoping for `set-environment`.
**Evidence:** Line 405 and tmux docs (`tmux set-environment` without `-g` is session-level; window-level scoping does not exist for `set-environment`).
**Recommendation:** Don't use `set-environment`. Pass the prompt to the script via a different mechanism: write it to a per-lane file (`.orca/.run-<lane>.prompt` in the worktree, mode 0600) and have the script read it (`--prompt "$(cat .orca/.run-<lane>.prompt)"`), then delete the file. OR pass it as an argv arg in the `send-keys` call but quoted via shlex — which contradicts the entire reason we went to tempfile-script. The cleanest path: tempfile next to the script, mode 0600, deleted by the script after first read. Update tests for the session-scoping leak case.

##### [MEDIUM] NEW-2: Idempotency state cube has an asymmetry between rows 6 and 7
**Criterion:** cross-spec-consistency
**Issue:** Row 6 (`yes | no | yes | yes`, line 135) says "Sidecar/registry stale: worktree was force-removed externally. Clean stale entries; if `--reuse-branch`: recreate worktree from existing branch. Else: refuse with hint." Row 7 (`no | no | yes | yes`, line 136) says "Sidecar without branch... Auto-clean sidecar + registry, then proceed as happy path. Log a warning." Both rows have stale sidecar+registry. The difference is whether the branch still exists. But the disposition is opposite: row 6 refuses without `--reuse-branch`, row 7 silently auto-cleans. The user-facing reasoning ("branch still exists" → "user might care more") is plausible but undocumented in the table; the rationale should be in the spec text, not implicit in the row asymmetry. Worse: the happy path requires creating a branch from `--from`, but row 7's "proceed as happy path" implies creating a NEW branch with the same name as the deleted one, which surprises operators ("I deleted that branch yesterday, why is orca recreating it?").
**Evidence:** Lines 135-136 (rows 6 and 7 of the state-cube table).
**Recommendation:** Add a one-paragraph rationale beneath the table explaining the row-6 vs row-7 split. Consider tightening row 7 to also require an opt-in flag (`--recreate-branch`) so silent auto-clean doesn't surprise.

##### [MEDIUM] NEW-3: Trust ledger location breaks on shared/container hosts and lacks key-collision discussion
**Criterion:** industry-patterns
**Issue:** Line 241 keys the trust ledger by `(repo_root_realpath, script_path, sha256)` and stores it at `~/.config/orca/worktree-trust.json`. Three issues: (1) **Containerized dev environments** (devcontainers, codespaces) reset `$HOME` per container — operator gets re-prompted on every container rebuild even though the script content is unchanged. (2) **`repo_root_realpath` differs across mount points** — same repo cloned at `/home/me/foo` (host) vs `/workspace/foo` (devcontainer) is two distinct ledger entries, so trusting in one doesn't carry over. (3) **Concurrent writes to the JSON ledger** are not specified — two `wt new` invocations from different repos could race the ledger, just like the registry races flagged in HIGH #4, but the ledger has no locking strategy described.
**Evidence:** Lines 237-247.
**Recommendation:** (a) Document the devcontainer/$HOME limitation explicitly and recommend mounting `~/.config/orca/` from host into container as a workaround; (b) add `fcntl.flock` (or equivalent Windows path) to ledger writes, mirroring the registry strategy; (c) consider keying by `(git remote URL, script_path, sha256)` instead of repo_root_realpath, so ledger entries survive cross-mount mounting.

##### [MEDIUM] NEW-4: `--trust-hooks` interaction with the trust ledger is unspecified
**Criterion:** feasibility
**Issue:** Line 243 says "`--trust-hooks` flag (or `ORCA_TRUST_HOOKS=1` env) skips the prompt — meant for automation/CI where the operator pre-validates." But it doesn't say whether passing `--trust-hooks` on a one-off invocation also UPDATES the ledger (so subsequent runs without the flag don't re-prompt) or merely BYPASSES the check this once. Both are defensible; pick one. If "bypass without record" is the choice, then operators using `--trust-hooks` once for convenience get re-prompted forever; if "bypass and record" is the choice, then `--trust-hooks` is a one-shot way to silently trust a hostile script with no audit trail.
**Evidence:** Line 243.
**Recommendation:** Specify the behavior. Recommended: `--trust-hooks` records the SHA only if `--trust-hooks-record` is also passed; otherwise it bypasses-without-record. This forces operators to be explicit about persisting trust.

##### [MEDIUM] NEW-7: Windows `os.replace` over a junction is not verified to be atomic
**Criterion:** industry-patterns
**Issue:** Line 235 says "The atomic-rename pattern still applies via `os.replace` which is cross-platform on Python ≥ 3.3." Combined with line 456 ("Symlinks on Windows: `pathlib` symlink fallback to directory junction (`mklink /J`)"), the pattern becomes: `mklink /J <tmp_junction> <target>`, then `os.replace(<tmp_junction>, <final>)`. `os.replace` over a directory junction on Windows: CPython's implementation calls `MoveFileExW` with `MOVEFILE_REPLACE_EXISTING`, which DOES handle junctions, but ONLY when the destination is also a junction or doesn't exist. If the destination is a regular directory (e.g., the auto-symlink target was previously a real directory and the spec says "blocks with an error" on Stage 1), the replace fails. The spec's lstat refuses-on-real check on line 230 should prevent this — but the order of operations matters. Also: `os.replace` is not atomic across volumes on Windows; two paths inside the worktree are same-volume so this is fine in practice, but spec doesn't note the constraint.
**Evidence:** Lines 230-235, 456.
**Recommendation:** Add a one-line note: "On Windows, the atomic-rename relies on same-volume source/dest (always the case inside a worktree) and on the lstat refuse-on-real-dir check (line 230) eliminating the junction-over-directory case." Add a Windows-specific test case in the test suite list (currently only POSIX is covered).

##### [MEDIUM] NEW-8: `.orca/worktrees.toml` is not part of the adoption flow
**Criterion:** cross-spec-consistency
**Issue:** Round-1 #11 was correctly resolved by moving `[worktrees]` out of `adoption.toml`. But the new `.orca/worktrees.toml` file has no adoption-flow integration: it is generated by `wt init` (line 118), not by `orca-cli adopt`. The 015 brownfield spec's adoption flow (`orca-cli adopt` → write `adoption.toml` → `orca-cli apply`) does NOT touch `worktrees.toml`. So a fresh `orca-cli adopt`'d repo CANNOT use `wt new` until the operator separately runs `wt init`. There's no `installed_capabilities`-style record of whether worktrees are configured. Worse: `orca-cli doctor` (run as final step of `apply` per spec 015 line 198) doesn't know about `worktrees.toml`, so a missing-but-needed file is not surfaced.
**Evidence:** Lines 162-164 + spec 015 lines 191-198 + spec line 118 (`wt init` is a separate manual command).
**Recommendation:** Pick one: (a) make `orca-cli adopt --enable-worktrees` (or equivalent) call `wt init` as part of the adoption flow, recording in `adoption.toml` `[orca] enabled_features = ["worktrees"]`; (b) document explicitly in §"Configuration schema" that `wt init` is a separate post-adoption step and update spec 015 to mention it; (c) make `wt new` auto-bootstrap `worktrees.toml` with defaults if missing (lazy adoption). Cross-link the choice in spec 015.

##### [LOW] NEW-9: Schema-v2 dual-emit creates accumulating tech debt with no deprecation horizon
**Criterion:** industry-patterns
**Issue:** Lines 347-363 emit both new and legacy field names indefinitely. Line 365 says "NOT documented as orca's preferred surface — operators should read the v2 fields. They're emitted only for read-side compatibility." But there's no deprecation horizon, no schema_version 3 plan, no "remove legacy fields when downstream readers all updated" milestone. Six months from now, a v3 reader has to keep parsing five legacy field names because some third-party tool somewhere reads them. The spec doesn't define when this dual-write ends.
**Evidence:** Lines 347-365.
**Recommendation:** Add a one-line "Deprecation horizon" note: "Legacy field emission is removed in schema_version 3, no earlier than 2026-Q4 and contingent on `_load_worktree_lanes` updating to v2 in all supported orca versions." Track removal as a Phase 3+ task.

##### [LOW] NEW-10: Effort estimate undercounts by ~10% per the line-item arithmetic
**Criterion:** feasibility
**Issue:** Summing the line-items in §"Effort estimate (revised post-review)" (lines 588-606): 0.5 + 0.5 + 0.25 + 0.5 + 0.5 + 0.5 + 0.25 + 0.25 + 0.25 + 0.75 + 0.25 + 0.25 + 0.25 + 0.5 + 0.25 + 0.5 + 1.25 + 0.25 = **8.0 days**, not the ~7 days claimed at line 607. Round-1 added 2.25 days of net new work (TOFU 0.5 + idempotency 0.5 + locking 0.25 + atomic-rename 0.25 + tempfile 0.25 + migrator 0.5) on top of the original 5, which puts the math at 7.25 minimum, and the existing line-items now add to 8. The "~7 days" framing soft-sandbags ~12-15%. Plus: the integration-test bullet (line 604) lists "50 unit + 15 integration + 3 contended-write" — but the v2 revision now requires 8 idempotency state-cube tests, Windows lock tests, send-keys quoting tests, TOFU prompt-flow tests, schema-v2 migrator tests, and the dogfood test. That's well above 15 integration tests for 1.25 days.
**Evidence:** Lines 588-607 (arithmetic) + line 604 (test count vs. the new test surface).
**Recommendation:** Either increase the test-suite line item to 1.75 days (covering the v2-introduced test surface) and update the total to 8.5 days, or trim a feature (e.g., defer `wt merge` per line 599 — it's barely justified at 0.25 days for what's a non-trivial verb).

##### [LOW] NEW-11: `wt cd` doesn't accept lane-id without shell completion
**Criterion:** industry-patterns
**Issue:** `wt cd <branch>` (line 110-114) takes a branch name. Shell completion is out-of-scope for v1 (line 40). Operators must therefore type the full branch name from memory. But the registry knows lane-ids and there's no way to `wt cd <lane-id>`. A `wt ls` → eyeball lane-id → `wt cd <branch-from-the-row>` flow is awkward.
**Evidence:** Lines 110-114, 40.
**Recommendation:** Tiny v1 fix: `wt cd` accepts EITHER a branch name OR a lane-id. Documented in CLI help. Cost: ~5 lines of resolver code.

#### Summary

| Source | Resolved | Partial | Not Fixed | New |
|---|---|---|---|---|
| Round 1 (16) | 11 | 4 | 1 | — |
| Round 2 introduced | — | — | — | 11 |

The v2 revision genuinely closes 11 of the 16 round-1 findings cleanly. Four are partial — the registry-schema reader path (#1) is correct in principle but lacks a defensive code path for unupdated readers; concurrent-write Windows fallback (#4) is one underspecified line; hook trust (#6) lacks ledger-locking and `--trust-hooks` semantics; symlink TOCTOU (#10) hand-waves the Windows path. One — send-keys quoting (#8) — is not actually fixed: the tempfile-script's `exec` defeats self-delete cleanup, and `tmux set-environment` leaks the prompt across the entire tmux session (windows AND splits), which is an active security regression versus round-1's already-broken state. Eleven new findings emerged; two are HIGH (Windows locking, tempfile/env-var cleanup), four MEDIUM (state-cube asymmetry, trust-ledger portability, --trust-hooks semantics, adoption-flow gap, Windows os.replace), three LOW (deprecation horizon, estimate arithmetic, wt cd ergonomics). The HIGH-severity tempfile/env-var issue alone justifies needs-revision: shipping a system that leaks operator-supplied prompts across tmux session-wide env is worse than shipping with `send-keys` quoting because it pretends to be safe. Recommend: fix NEW-5 and NEW-6 (rewrite the agent-launch path to use a mode-0600 prompt file, drop `tmux set-environment` entirely), tighten NEW-1 (Windows locking) and NEW-3/NEW-4 (TOFU ledger portability + --trust-hooks semantics), then re-review. Other findings can be plan-time notes.

### Round 3 - Author response

**Verdict:** all 11 round-2 new findings + 4 round-2-flagged partial round-1 items + 1 round-2 not-fixed item addressed in spec v3 (commit follows).

| Finding | Resolution |
|---|---|
| NEW-1 Windows registry locking | Specified concretely: 1-byte sentinel on lock-file creation, byte 0 length 1, `LK_NBLCK` non-blocking with backoff retry up to 30s, `EX_TEMPFAIL` on timeout, no `LK_LOCK` (deadlock-prone). Windows test gated by `pytest -m windows` |
| NEW-5 tempfile-script `exec` cleanup contradiction | Redesigned: prompt lives in separate mode-0600 file (`.orca/.run-<lane>.prompt`), launcher script reads-and-deletes prompt file then execs agent. Launcher persists for lane lifetime (documented; removed by `wt rm`); prompt file is one-shot |
| NEW-6 `tmux set-environment` session-scoped leak | Dropped `tmux set-environment` entirely; replaced with the prompt-file pattern above. No env-var crosses panes |
| NEW-2 row-6 vs row-7 asymmetry | Added rationale paragraph; tightened row 7 to require `--recreate-branch` flag (no silent branch recreation) |
| NEW-3 TOFU ledger portability | Repo key defaults to `git config remote.origin.url` (mount-independent, survives reclone); fallback to realpath if no remote. Ledger location is `${ORCA_TRUST_LEDGER:-${XDG_CONFIG_HOME:-$HOME/.config}/orca/worktree-trust.json}`. Devcontainer recommendation documented. Ledger writes use the same flock strategy as registry |
| NEW-4 `--trust-hooks` ledger semantics | Specified: `--trust-hooks` bypasses-without-record (one-off); `--trust-hooks --record` bypasses-and-records (CI bootstrap) |
| NEW-7 Windows os.replace + junction | Documented: `MoveFileExW(MOVEFILE_REPLACE_EXISTING)` handles junction-replace-junction; lstat refuse-on-real-dir eliminates the dir case before replace. Same-volume requirement noted (always satisfied inside worktree). Windows test added |
| NEW-8 worktrees.toml not in adoption flow | Added: `orca-cli apply` runs `wt init` non-interactively when `[orca] enabled_features` includes `worktrees` (default-on). Doctor surfaces missing worktrees.toml as warning. `wt new` lazily generates worktrees.toml with defaults if missing |
| NEW-9 deprecation horizon | Added: legacy field emission removed in schema_version 3, no earlier than 2026-Q4, contingent on all readers updated. Tracked as Phase 3+ |
| NEW-10 effort estimate arithmetic | Revised total to 8.5 days; test bullet bumped to 1.75 days covering 60 unit + 25 integration + 3 contended-write |
| NEW-11 wt cd lane-id support | `wt cd` now accepts EITHER branch or lane-id; CLI help documents the resolver order |
| Round-1 #1 partial: defensive reader path | Added: reader normalizes mixed string+dict `lanes` entries (logs and skips unknowns); prevents `Path / dict` TypeError if a downstream consumer pinned to old orca encounters v2 registry |
| Round-1 #4 partial: Windows lock | Subsumed by NEW-1 fix |
| Round-1 #6 partial: hook trust ledger | Subsumed by NEW-3 + NEW-4 fixes |
| Round-1 #10 partial: Windows symlink TOCTOU | Subsumed by NEW-7 fix |

**Outstanding from review:** none. Spec v3 is ready for round 3 verification or plan-writing.
