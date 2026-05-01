# Worktree Manager Implementation Review

**Date:** 2026-05-01
**Reviewer:** Cross-pass code reviewer subagent
**Branch:** orca-worktree-manager
**Commits in scope:** 34 (3e8fc60..468a62c)
**Test counts:** unit 141 passed / 2 skipped, integration 4 passed (-m integration)

### Round 1 — Implementation review

**Verdict:** needs-revision

The bulk of the prescriptive recipe landed faithfully. The state-cube precedence is correct (Row 8 mismatch checked before Row 5 attach), the lock spans full read-modify-write windows in `manager.create`, `manager.remove`, and `_run_wt_start`, the symlink helper uses atomic-rename without check-then-unlink, the agent launcher uses the prompt-file pattern with `shlex.quote` on extras and no `tmux set-environment`, schema-v2 dual-emit is in place with the TODO comment, the sdd_adapter normalize tolerates v1/v2/mixed/unknown entries, and the schema-v3 deferral is documented. However, the trust model has a gap that is not specific to one row of the cube but applies on every operator interaction: Stages 3 and 4 hooks bypass the TOFU ledger entirely. There is also a real concurrency hole on `wt doctor --reap` and a config-honoring bug where `manager.worktree_root` ignores `cfg.base`. None of these are arcane — each will fire on plausible operator workflows.

#### Findings

##### [BLOCKER] Stage 3 (`before_run`) and Stage 4 (`before_remove`) hooks bypass the trust ledger
**Area:** 3 (trust ledger soundness)
**Issue:** Spec §"Hook trust model" line 257 explicitly says "First run of **any** hook script for a given (repo_key, script_path, sha256) triple..." and line 295 lists Stage 4 (before_remove) as subject to the trust model. The implementation only gates `after_create` (manager.py:161-180 inside `_run_setup_stages`, plus the `--rerun-setup` path in python_cli.py:1610-1635). `before_run` (manager.py:198-210, also in `_run_wt_start` python_cli.py:1659-1671) and `before_remove` (manager.py:443-462) call `run_hook` directly with no `check_or_prompt` gate. Cloning a hostile repo and running `wt rm` (or any `wt new` that finds an existing lane and triggers `before_run`) is RCE-equivalent — the entire reason the trust model exists.
**Evidence:**
- `manager.py:199-209` — `before_run` runs unconditionally with no trust call.
- `manager.py:443-462` — `before_remove` runs unconditionally with no trust call.
- `python_cli.py:1659-1671` — `_run_wt_start` runs `before_run` unconditionally.
- Spec lines 257, 295 (`docs/superpowers/specs/2026-04-30-orca-worktree-manager-design.md`).
**Recommendation:** Wrap each Stage 2/3/4 invocation in a helper that first calls `check_or_prompt` for that script's SHA. The CLI handlers must pass `trust_hooks` through into `wt rm` and `wt start` (currently `wt rm` has no `--trust-hooks` flag at all). Suggested helper: `_trust_or_skip(*, env, script_path, decision, interactive, stage_name)` returning a bool; manager calls it before every `run_hook`.

##### [BLOCKER] `WorktreeManager.worktree_root` ignores `cfg.base`
**Area:** 1 (state-cube correctness — but root cause is layout)
**Issue:** `manager.py:121` hardcodes `self.worktree_root = repo_root / ".orca" / "worktrees"`. The layout module respects `cfg.base` for the worktree path itself (where the checkout lives), but the *registry, sidecar, events, lock, and hook scripts* are read/written from the hardcoded `.orca/worktrees/` regardless of `cfg.base`. If an operator sets `[worktrees] base = "/tmp/wt"` (or any value other than the default), the worktree directories land at `/tmp/wt/<lane_id>` while the registry index lives at `<repo>/.orca/worktrees/registry.json` — and the hooks are looked up at `<repo>/.orca/worktrees/after_create`, not the configured base. CLI handlers do the same (`_run_wt_start` python_cli.py:1571, `_run_wt_doctor` python_cli.py:2012). Either the spec needs to clarify the split (registry-always-at-`.orca`, worktrees-at-base) or the manager needs to use `resolve_base_dir(repo_root, cfg)` for the registry path too.
**Evidence:**
- `manager.py:121`: `self.worktree_root = repo_root / ".orca" / "worktrees"`
- `layout.py:9-18` resolves `cfg.base` correctly for the lane checkout.
- `python_cli.py:1571`, `1705`, `1753`, `1862`, `2012` all hardcode `repo_root / ".orca" / "worktrees"`.
**Recommendation:** Either remove `cfg.base` from the schema (locking the layout) or thread `resolve_base_dir(repo_root, cfg)` through everywhere `worktree_root` is computed. Add an integration test with a non-default `base`. If the registry-vs-checkout split is deliberate, document it as a hard rule and rename the field to make the split obvious (`checkout_base` for the checkout path; registry stays at `.orca/worktrees/`).

##### [HIGH] Trust ledger writes are not lock-protected
**Area:** 3 (trust ledger soundness)
**Issue:** Spec line 271 mandates fcntl/msvcrt locking on a sibling `worktree-trust.lock` for ledger writes. `TrustLedger.save()` in `trust.py:92-105` does an atomic-rename but no advisory lock. Two concurrent `wt new --trust-hooks --record` calls (likely scenario: two repos opened in parallel) load the same in-memory snapshot, both append, both save — last writer wins, the earlier `record()` is lost. The repo will then re-prompt next time, which is a usability regression but more importantly contradicts the documented contract.
**Evidence:**
- `trust.py:92-105` — `save()` writes via atomic rename, no lock.
- `trust.py:8` docstring claims locking is implemented.
- Spec line 271: "Ledger writes are protected by the same `fcntl.flock` strategy as the registry, on a sibling `worktree-trust.lock` file."
**Recommendation:** Reuse `acquire_registry_lock`-style helper parameterized by lock-path. Wrap the `load → mutate → save` triple in `check_or_prompt` (trust.py:154-178) inside that lock; otherwise `is_trusted` and `record` race even within a single CLI run.

##### [HIGH] `ORCA_TRUST_HOOKS=1` env var is documented but never read
**Area:** 3 (trust ledger soundness)
**Issue:** Spec line 259 promises `--trust-hooks` flag OR `ORCA_TRUST_HOOKS=1` env. The code only consults the CLI flag (`python_cli.py:1468`, `1559`). `TrustDecision.trust_hooks` field comment in `trust.py:132` even names the env var, but no code path reads `os.environ`. Operators who set the env in their shell profile or CI config will hit the non-interactive guard and a confusing error.
**Evidence:**
- `trust.py:132` comment names the env var.
- No `os.environ.get("ORCA_TRUST_HOOKS"...)` anywhere in `src/orca/core/worktrees/` or `python_cli.py`.
- Spec line 259.
**Recommendation:** In `_run_wt_new` and `_run_wt_start`, compute `trust_hooks = ns.trust_hooks or os.environ.get("ORCA_TRUST_HOOKS") in {"1","true","yes"}` before constructing `TrustDecision`. Same for `--record` if you want a parallel `ORCA_TRUST_HOOKS_RECORD` (optional).

##### [HIGH] Operator-supplied `agents.<name>` config is interpolated into a shell launcher with no shell-quoting
**Area:** 7 (agent launch quoting)
**Issue:** `agent_launch.py:60` and `:65` interpolate `agent_cmd` (string from `cfg.agents.<name>` in worktrees.toml) directly into a bash heredoc as `exec {agent_cmd}{...}`. `extra_args` are properly `shlex.quote`-d but `agent_cmd` itself is not. Even though the operator owns worktrees.toml in normal usage, a freshly-cloned hostile repo carries that file too. The trust ledger does NOT gate config interpolation. So `wt new` against a hostile clone with a default agent silently runs whatever the repo's `agents.claude` says, regardless of `--no-setup` (which only skips Stages 2-4, not the agent launch).
**Evidence:**
- `agent_launch.py:51-65` — `f"...exec {agent_cmd}..."` is the smoking gun.
- `manager.py:395-408` always launches the agent if `req.agent != "none"`, gated only on `self.run_tmux`.
- Spec §"Hook trust model" guards hook scripts but is silent on the `agents` table; real-world threat is identical.
**Recommendation:** Two options. (1) Treat the agents table as trust-ledger-protected: hash the resolved `agent_cmd` string and route through `check_or_prompt` before writing the launcher. (2) Restrict `agent_cmd` to a single executable name + arg list (parse with `shlex.split`, reject any shell metacharacters), then build the launcher with `shlex.quote` on each token. Option 2 is simpler and aligns with the prompt-file pattern's spirit.

##### [HIGH] `wt doctor --reap` has a TOCTOU between read-snapshot and per-lane delete
**Area:** 10 (doctor reaping)
**Issue:** `_run_wt_doctor` at python_cli.py:2013 reads `view = read_registry(wt_root)` outside any lock. The `--reap` loop at lines 2083-2103 then iterates that stale snapshot, calling `scp.unlink()` (line 2094) BEFORE acquiring the lock at line 2098. Between the snapshot and the unlink, a concurrent `wt new` can register a new lane (different lane-id) safely, but a concurrent `wt new` that adopts/recreates *this* lane-id will have written a fresh sidecar that `--reap` then deletes. The lock at line 2098 only protects the registry-list rewrite, not the sidecar file. Also: `view` is taken outside the lock so the rewrite at 2100-2102 may clobber a newer registry that has lanes the snapshot doesn't.
**Evidence:**
- `python_cli.py:2013` reads view outside the lock.
- `python_cli.py:2092-2102` — `scp.unlink()` is outside the lock; `read_registry` at 2099 is fresh, but `lane.lane_id` came from the stale outer `view`.
**Recommendation:** Move the entire reap loop inside `acquire_registry_lock(wt_root)`. Within the lock, re-read the registry, re-check on-disk worktree presence, then unlink sidecar and rewrite registry as a single transaction. If the operator's interactive `[y/N]` prompt is unacceptable to hold under lock, collect the orphan list under lock, drop the lock for prompts, re-acquire and re-validate before each delete.

##### [MEDIUM] Row 7 destructive-clean-then-refuse leaks the `--recreate-branch` requirement
**Area:** 1 (state-cube correctness)
**Issue:** `manager.py:279-290`: when branch is absent and a sidecar/registry orphan exists, without `--recreate-branch` the code unlinks the sidecar, rewrites the registry to remove the lane, THEN raises `IdempotencyError`. After the raise, the orphan is gone. A retry without `--recreate-branch` falls through to the create-from-scratch path and succeeds — which means `--recreate-branch` is enforced exactly once. That's a UX-spec mismatch: the flag advertises explicit intent for recreation, but the implementation leaks the requirement on retry.
**Evidence:** `manager.py:279-290`.
**Recommendation:** Either keep the orphan in place when refusing (don't unlink/rewrite until `--recreate-branch` is passed), or accept the auto-clean and remove the user-facing requirement (drop `--recreate-branch` and document that orphans auto-clean on next run). The first is closer to the spec's intent; the second is simpler.

##### [MEDIUM] `wt rm` has no `--trust-hooks` flag, so even an interactive operator cannot bypass the prompt
**Area:** 3 + 12 (trust + error handling)
**Issue:** Once finding #1 is addressed and `before_remove` is gated by the trust ledger, the `wt rm` CLI surface (python_cli.py:1815-1876) has no `--trust-hooks` or `--no-setup` flag wired to anything — `--no-setup` is parsed (line 1829) but only consumed by the manager's `run_setup` to skip Stage 2/3, not Stage 4. Operators who run `wt rm` non-interactively (CI, scripts) will be blocked with no escape hatch.
**Evidence:** `python_cli.py:1815-1876` argparse has no trust flags; `manager.remove` has no trust knob.
**Recommendation:** Add `--trust-hooks`, `--record`, and `--no-setup` to `wt rm`'s parser; thread into `RemoveRequest`; have `manager.remove` honor `req.no_setup` to skip the `before_remove` hook entirely (parallels `req.no_setup` in create).

##### [MEDIUM] `config.py` swallows operator's explicit `symlink_files = []`
**Area:** 5/2 (config — adjacent to symlink TOCTOU)
**Issue:** `config.py:102`: `_require_list(section, "symlink_files") or list(WorktreesConfig().symlink_files)`. If the operator explicitly sets `symlink_files = []` to opt out of the default `.env*` symlinks, the empty list is falsy and the defaults are restored. This is the classic Python truthy-default-fallback bug.
**Evidence:** `config.py:102`.
**Recommendation:** Distinguish "key absent" from "explicit empty". `_require_list` already returns `[]` for missing keys; either change the call to `_require_list(section, "symlink_files") if "symlink_files" in section else list(WorktreesConfig().symlink_files)` or have `_require_list` return a sentinel for missing.

##### [MEDIUM] `wt rm --all` reads registry without the lock
**Area:** 2 (concurrency)
**Issue:** `python_cli.py:1862` reads the registry outside any lock to drive the per-lane removal loop. Each `mgr.remove` call acquires/releases the lock, so concurrent `wt new` between iterations can create a new lane that `--all` doesn't see (acceptable: best-effort), or remove an entry that `--all`'s snapshot believes still exists (also fine, second remove is no-op). The race is benign but the snapshot still shapes the loop, so a concurrently-created lane survives `--all`. Document or fix.
**Evidence:** `python_cli.py:1860-1866`.
**Recommendation:** Either acknowledge the best-effort semantics in help text, or lift the snapshot inside a single lock + serial remove. The latter requires `manager.remove` accept an option to skip the lock when caller already holds it.

##### [MEDIUM] sdd_adapter `_load_worktree_lanes` filter mixes feature_id and lane_id
**Area:** 9 (sdd_adapter normalize)
**Issue:** `sdd_adapter.py:843-847`: `if lane.get("feature") != feature_id and lane.get("id") != feature_id: continue`. The dual-emit writes `id = lane.lane_id` (lane-id, not feature-id) and `feature = feature_id`. The first half of the filter is correct; the second half compares lane-id against feature-id, which spuriously matches only when the operator names a lane after a feature. Probably preserved for v1 back-compat where `id` *was* feature-id, but worth confirming and commenting.
**Evidence:** `sdd_adapter.py:843-847`; dual-emit at `registry.py:78-80`.
**Recommendation:** Drop the `lane.get("id") != feature_id` clause unless the v1 schema actually used `id` for feature-id. If it did, add a comment explaining the back-compat preservation. Add a regression test where a lane has lane_id == some-feature-id-string but `feature_id` is None — current code includes it incorrectly.

##### [LOW] `_default_branch` "empty repo" path returns the unborn branch name but the code below assumes a real ref
**Area:** 1 (manager state)
**Issue:** `manager.py:60-65`: on an empty repo, `git symbolic-ref --short HEAD` returns the unborn branch (e.g. "main") but no commits exist. The subsequent `git worktree add -b req.branch <wt> from_branch` (line 319-323) will fail because `from_branch` has no commit. The doc comment says "Works on empty repos … we must not crash on that path" but `git worktree add` will crash a step later. Either reject empty repos with a clear error or initialize a first commit.
**Evidence:** `manager.py:36-75` plus `manager.py:319-323`.
**Recommendation:** Detect empty-repo (`git rev-parse HEAD` fails) up front and emit a friendly error: "no commits yet; run `git commit` first."

##### [LOW] Event vocabulary lacks `agent.exited` emitter
**Area:** 11 (event log)
**Issue:** `events.py:22` lists `"agent.exited"` in the closed vocabulary, but no code emits it. Either drop from the vocabulary or wire a tmux pane-dead detector (probably out of scope for v1; just close the gap).
**Evidence:** Vocabulary at `events.py:22`; no `emit_event(..., event="agent.exited", ...)` callsite.
**Recommendation:** Drop `agent.exited` from `EVENT_VOCAB` until v2 wires it, or add a comment noting it's reserved for future use.

##### [LOW] `tmux.send_keys` arg `keys` could be split if it contains spaces in unexpected ways
**Area:** 7 (agent launch quoting)
**Issue:** `tmux.py:96-99` passes `keys` as a single argv to `tmux send-keys`. tmux still parses the literal string. The current callsite passes `f"bash .orca/.run-{lane_id}.sh"` where `lane_id` is path-safety-validated, so this is safe today. If a future callsite passes user input it will not be safe. Consider splitting on whitespace and passing each token as a separate argv to `tmux send-keys` — that is the documented safe pattern.
**Evidence:** `tmux.py:92-103`; `manager.py:403-406` is the only caller today.
**Recommendation:** Either tighten the docstring to "`keys` MUST contain only path-safe content; arbitrary text is unsafe" or split on whitespace and pass tokens individually.

#### Summary

| Severity | Count |
|---|---|
| Blocker | 2 |
| High | 4 |
| Medium | 5 |
| Low | 3 |

The 8-row state cube and lock geometry are well-implemented. The two BLOCKERS are not row-of-the-cube issues — they are systemic gaps (trust ledger only gates Stage 2; manager hardcodes registry root regardless of `cfg.base`). Both are reachable on day-1 operator scenarios. The HIGH findings cluster around the trust model (locking, env-var, agent-cmd interpolation) and `wt doctor --reap`'s race. With the BLOCKERS and HIGHs addressed, this is mergeable; the MEDIUMs are tractable in a follow-up but worth fixing before the first external user. Prefer not to ship as-is — the trust gaps invalidate the spec's headline security claim, and the `cfg.base` bug will trip the first operator who customizes layout.
