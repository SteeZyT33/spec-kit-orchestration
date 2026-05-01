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
