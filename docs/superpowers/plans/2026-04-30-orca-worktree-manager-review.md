# Worktree Manager Plan Review

**Plan:** docs/superpowers/plans/2026-04-30-orca-worktree-manager.md
**Reviewer:** Cross-pass (Code Reviewer subagent)
**Date:** 2026-04-30

### Round 1 — Plan review

**Verdict:** needs-revision

The plan is largely well-structured and the prerequisite API surface (`validate_identifier(value, *, field, max_length=128)` and `PathSafetyError`) matches `src/orca/core/path_safety.py` exactly, so most subagent tasks will execute. However, several specific tasks contain runtime bugs, missing spec coverage, or implementation gaps that will produce incorrect behavior or hard errors in real-world use. Most are easy fixes; one is a load-bearing implementation gap (`--rerun-setup`).

#### Findings

##### [HIGH] `--rerun-setup` flag never compares SHA — Stage 2 re-run is dead code
**Category:** gaps
**Issue:** Spec line 158 mandates: `Re-run Stage 2 hook only if --rerun-setup AND sidecar's setup_version differs from current after_create SHA`. Task 28's `_run_wt_start` parses `--rerun-setup` (`ns.rerun_setup`) but the flag is never read after parsing. The function unconditionally runs Stage 3 (`before_run`) and never executes the SHA comparison or Stage 2 (`after_create`) re-run. The contract advertised by the spec is silently a no-op.
**Evidence:** Plan lines 4959 (flag declared), 4988-5023 (start body — `ns.rerun_setup` not referenced); spec line 158, plan self-review line 5701 claims state cube covers "wt start re-attach" but lists no rerun-setup verification.
**Recommendation:** In `_run_wt_start`, after Stage 3, add: if `ns.rerun_setup` and `sc.setup_version != hook_sha(ac_path)` then re-run Stage 2 with TOFU prompt and update sidecar's `setup_version`. Add a CLI test that mutates `after_create` between `wt new` and `wt start --rerun-setup` and asserts the new content executes.

##### [HIGH] Task 18 `_default_branch` crashes on a brand-new repo with no commits
**Category:** edge-cases
**Issue:** The fallback `git rev-parse --abbrev-ref HEAD` is invoked with `check=True`. On an empty repo (no commits, no `main`/`master`, no origin) this exits 128 ("ambiguous argument 'HEAD'") and `subprocess.run` raises `CalledProcessError`. Real operators run `git init && orca-cli wt new feat` and hit this. Test fixtures sidestep the bug because they always commit first.
**Evidence:** Plan lines 3166-3187; reproduced locally on `git init` + immediate `git rev-parse --abbrev-ref HEAD` returns rc=128. Test fixture `_init_repo` (plan line 3050) always runs `git commit --allow-empty` before invoking `create()`.
**Recommendation:** Replace `check=True` with `check=False`, then if rc != 0 fall back to `git symbolic-ref --short HEAD` (which works pre-commit because it returns the current symbolic ref like `refs/heads/main` even with no commits) or to a configurable default (`init.defaultBranch`). Add a test fixture variant that does NOT pre-commit and asserts a sensible default branch is selected.

##### [HIGH] State-cube rows 3, 4, and 8 have no tests; row 8 has no implementation
**Category:** coverage
**Issue:** Plan self-review (line 5703) claims "all 8 rows" are covered, but Task 19 tests cover only rows 2 (twice), 5, 6, 7 (twice). Row 3 (worktree at canonical path, no sidecar — adopt) is implicitly handled via `adopting_existing` but not asserted. Row 4 (worktree at non-canonical path) raises `IdempotencyError` but no test exercises it. Row 8 (sidecar branch mismatch) is described in the spec (line 141, "INPUT_INVALID; recommend `wt rm <existing-lane-id>` first") but has neither a test nor any code path that compares `sidecar.branch != req.branch`.
**Evidence:** Plan tests at lines 3309-3394 cover rows 2/5/6/7. Spec table line 130-148 enumerates all 8 rows. Manager code at lines 3441-3576 has no `sidecar.branch != req.branch` check.
**Recommendation:** Add three explicit tests: (a) row 3 — pre-create a worktree at `<base>/<lane-id>/` via `git worktree add` directly, then assert `mgr.create()` adopts it (sidecar+registry written, `lane.attached` event emitted, no second `git worktree add` invocation); (b) row 4 — pre-create a worktree at `/tmp/elsewhere`, assert `IdempotencyError` with the unexpected-path message; (c) row 8 — register a lane with branch=`feat-A`, then call `create(branch="feat-A-different")` with the same derived lane-id, assert refusal. Add the `sidecar.branch != req.branch` guard to `create()`.

##### [HIGH] Task 30 `wt doctor` operator-precedence bug skips the orphan-git check
**Category:** order-of-ops
**Issue:** The expression at plan lines 5296-5297 is:
```
if gp != str(repo_root) and gp not in registered_paths and \
   Path(gp).is_relative_to(wt_root) if Path(gp).is_absolute() else False:
```
Python parses this as `(A and B and C) if D else False`. `git worktree list --porcelain` always emits absolute paths so `D` is always True and the `else False` branch is dead code. More importantly, the `is_relative_to(wt_root)` clause means orphan worktrees that the operator parked OUTSIDE `.orca/worktrees/` (e.g. `git worktree add ../scratch`) are silently NOT reported, even though they are unregistered and probably an issue. Either the predicate is wrong or the structure communicates the wrong thing.
**Evidence:** Plan lines 5295-5298. Verified parse via `ast.parse`: outer node is `IfExp(test=is_absolute(...), body=BoolOp(...))`.
**Recommendation:** Drop the `is_relative_to` clause (orphan-git is by definition any unregistered worktree under git's view, regardless of where the operator parked it), or split into nested `if` statements: `if not Path(gp).is_absolute(): continue` then a separate `if gp != str(repo_root) and gp not in registered_paths: issues.append(...)`. Add a test that creates an external worktree and asserts doctor reports it.

##### [MEDIUM] `wt ls` does not emit `tmux.session.killed` event when first observing a missing session
**Category:** gaps
**Issue:** Spec line 473 commits to: "An emitted `tmux.session.killed` event is appended to `events.jsonl` when `wt ls` first observes session-missing for a previously-attached lane." Task 27's implementation reads tmux state and computes the column but never calls `emit_event`. Consumers of `events.jsonl` (spec line 559, "flow-state-projection gains a per-lane setup+agent dimension") will never see the kill notification.
**Evidence:** Plan lines 4830-4855 (no `emit_event` call); spec line 473.
**Recommendation:** Track previous tmux state by reading prior `tmux.session.killed` events or by checking sidecar's `last_attached_at`. When transitioning attached→session-missing, emit the event once. Alternatively, demote this to a Phase 2 item and flag it explicitly in the plan.

##### [MEDIUM] Task 27 test only exercises `session-missing` row; `attached` and `stale` paths are untested
**Category:** tdd
**Issue:** The CLI test helper `_run` passes `--no-tmux --no-setup` to every invocation, so no tmux window is ever created. `live_windows` in Task 27 is always empty → `tmux_state == "session-missing"`. The test assertion at line 4803 just checks the key exists, not its value. The other two states (`attached`, `stale`) and the JSON value contract are unverified.
**Evidence:** Plan lines 4371-4377 (helper), 4791-4803 (test).
**Recommendation:** Add a unit test directly against the manager.list-style function (or a refactored `_compute_tmux_state(window, live_windows)` helper) that asserts each of the three states produces the documented enum value. Don't try to spin up real tmux in unit tests.

##### [MEDIUM] Task 28 `_run_wt_start` writes sidecar without holding the lock during read-modify-write
**Category:** order-of-ops
**Issue:** Plan lines 4985-5023: read sidecar, then later `with acquire_registry_lock(wt_root): write_sidecar(...)`. Two concurrent `wt start` invocations will both read the same `sc`, both compute `last_attached_at`, both write — last writer wins, intermediate state lost. The lock serializes the write but doesn't make read-modify-write atomic.
**Evidence:** Plan lines 4985, 5018-5022.
**Recommendation:** Move the sidecar read INSIDE the lock context: acquire lock, read sidecar, mutate, write, release. Same pattern as `manager.create()` already uses correctly. Low impact in practice (rare concurrent `wt start`) but fixes a known footgun pattern.

##### [MEDIUM] Task 18 happy-path test reads `result.lane_id` after `result` is rebound to a `subprocess.run` return
**Category:** tdd
**Issue:** Plan lines 3072-3088: `result = mgr.create(req)` then later `result = subprocess.run(...)` then `assert result.returncode == 0`. The CompletedProcess has no `.lane_id`; the test only verifies subprocess succeeded. Earlier assertions on `result.lane_id` (line 3074) reference the manager's `CreateResult` correctly because that's still bound at that point. The test passes, but the rebinding makes the test brittle and the post-rebind assertion adds nothing because `subprocess.run(check=True)` would raise before the assertion.
**Evidence:** Plan lines 3072-3088.
**Recommendation:** Rename the second variable: `git_check = subprocess.run(...)` and `assert git_check.returncode == 0`. Cosmetic but prevents future copy-paste accidents.

##### [MEDIUM] Devcontainer trust-ledger guidance from spec is not implemented
**Category:** gaps
**Issue:** Spec line 269 commits: "Devcontainer / codespace operators mount `~/.config/orca/` from host into container OR set `ORCA_TRUST_LEDGER` to a persistent volume path." Task 13 implements `ledger_path()` to honor `ORCA_TRUST_LEDGER` and `XDG_CONFIG_HOME`, which satisfies the env override. But no documentation, no warning surfaced when the ledger is on a tmpfs, and the README section in Task 32 doesn't mention it. Operators in codespaces will have prompts re-fire every container boot until they discover this themselves.
**Evidence:** Spec line 269, Task 32 README addition lines 5485-5507 (no devcontainer guidance), trust ledger code at lines 2120-2126 (correct env handling but no surfacing).
**Recommendation:** Add a sentence to the README's worktree section: "Devcontainer / Codespaces users should set `ORCA_TRUST_LEDGER` to a persistent volume path (e.g. a Docker named volume) or mount `~/.config/orca/` from host." Optionally have `wt doctor` warn when the ledger lives under `/tmp` or `/run`.

##### [MEDIUM] Schema-v2 deprecation horizon not represented in any task
**Category:** gaps
**Issue:** Spec line 393: "Legacy field emission is removed in `schema_version` 3, no earlier than 2026-Q4 ... Tracked as a Phase 3+ task. v3 is OUT OF SCOPE here." This is correctly out of scope, but the plan doesn't add a tracking artifact (TODO comment in `registry.py` `write_sidecar`, or a docs entry) so the dual-emit will rot in place. By the time someone wants to clean it up, the Phase-3 commitment will be lost.
**Evidence:** Spec line 393; plan tasks 4 (sidecar) and 8 (migrator) have no v3 sunset comment.
**Recommendation:** Add a `# TODO(schema-v3, 2026-Q4): drop dual-emit of {id, feature, path, status, task_scope} once all consumers read v2.` comment above the dual-emit block in Task 4's `write_sidecar`.

##### [LOW] Constitution / agents-md auto-derive symlinks from spec aren't in Stage 1 implementation
**Category:** gaps
**Issue:** Spec line 234: "Plus `host.constitution_path` and `host.agents_md_path` if set in the manifest" should auto-symlink. Task 12's `run_stage1` only consults `_HOST_DEFAULTS` (host_system → fixed list) and `cfg.symlink_files`. It does not read the manifest's `host.constitution_path` or `host.agents_md_path`.
**Evidence:** Spec line 234, plan lines 1947-1994.
**Recommendation:** Either thread the manifest into `run_stage1` and append `host.constitution_path` / `host.agents_md_path` to the path list when set, or document this as deferred to Phase 2 and remove it from the spec's auto-derive table.

##### [LOW] Task 31 test references `OrcaConfig.enabled_features` and `build_default_manifest` without verifying they exist
**Category:** api-drift
**Issue:** Plan lines 5386-5395 import `build_default_manifest` from `orca.core.adoption.wizard` and reference `m.orca.enabled_features`. The plan itself acknowledges: "`OrcaConfig.enabled_features` doesn't exist yet — this is a forward-compatible read" (line 5418), then simplifies away. But the TEST (lines 5380-5398) was written assuming the feature is present and was not updated when the simplification happened. The test will execute `apply()` and assert worktrees.toml exists, which works under the simplified always-on path, but the assertion no longer ties to "when worktrees enabled" — the test name is now misleading.
**Evidence:** Plan lines 5380-5398 (test), 5418-5427 (simplification note).
**Recommendation:** Rename the test from `test_apply_runs_wt_init_when_worktrees_enabled` to `test_apply_seeds_worktrees_config` and remove the misleading comment about default features. Or, defer this whole task until the manifest schema bump lands.

##### [LOW] Effort estimate sanity check
**Category:** effort
**Issue:** Spec claims 8.5 days, plan has 35 tasks. That's ~14 minutes per task at an 8-hour day. Tasks 19 (state cube), 23 (hook integration with revert), 25 (CLI dispatch with full new-handler), and 30 (doctor + reap) are clearly multi-hour each. The estimate is not absurd in aggregate (8.5 days × 8 hours = 68 hours, roughly 2 hours per task average) but the per-task cadence will be uneven; subagents should expect to spend a half-day on Task 19 and a half-day on Task 25 alone.
**Evidence:** Spec line 664; plan task count.
**Recommendation:** No fix required, but flag in the plan preamble that tasks 18-19, 23-24, 25, 30 are "thick" tasks expected to take 1-3 hours each, while tasks like 1-3 are 15-30 min. Helps subagents pace and ask for help sooner on the thick ones.

#### Summary

| Category | Count |
|---|---|
| Coverage | 1 |
| Types | 0 |
| API drift | 1 |
| Order-of-ops | 2 |
| TDD | 2 |
| Edge cases | 1 |
| Effort | 1 |
| Gaps | 4 |
| **Total** | **12** |

The plan's prerequisite API matches the implementation (`validate_identifier(value, *, field, max_length=128)` confirmed in `src/orca/core/path_safety.py`), the dataclass signatures (`Sidecar`, `LaneRow`, `WorktreesConfig`, `CreateRequest`, `RemoveRequest`, `HookEnv`, `HookOutcome`, `TrustOutcome`, `TrustDecision`, `IdempotencyError`) are stable across the tasks that introduce and consume them, and the `_register`/`_emit_envelope`/`ErrorKind` symbols Task 25 calls actually exist in `python_cli.py`. So most tasks will execute without import errors.

The blocking concerns are: (1) `--rerun-setup` is wired in argv but never executes a re-run, breaking a documented spec contract; (2) `_default_branch` crashes on empty repos; (3) state-cube row 8 has no implementation despite the plan's self-review claiming full coverage; (4) `wt doctor`'s orphan-git check has a precedence bug that hides external worktrees. Fix those four before dispatching subagents and the rest can be addressed in-flight or as polish.

Recommended order: HIGH issues first (rerun-setup, default-branch, state-cube rows 3/4/8, doctor predicate), then MEDIUM (events emission, lock-during-RMW, devcontainer guidance, deprecation TODO), then LOW. Estimated cleanup before execution: 2-3 hours for the four HIGH items including added tests.

### Round 2 — Author response

**Verdict:** all 12 findings addressed in plan v2 (commit follows).

| Finding | Severity | Resolution |
|---|---|---|
| `--rerun-setup` dead code | HIGH | Task 28 rewritten: `_run_wt_start` now reads `ns.rerun_setup`, computes `hook_sha(ac)`, compares vs `sc.setup_version`, runs Stage 2 with TOFU prompt + non-interactive guard, updates `setup_version` in sidecar. Two new CLI tests cover (a) re-run executes when SHA changes, (b) re-run is no-op when SHA unchanged |
| `_default_branch` empty-repo crash | HIGH | Replaced `check=True` rev-parse with: 5-step fallback chain (origin HEAD → main/master refs → symbolic-ref --short HEAD → init.defaultBranch → "main" final). Works on `git init` with zero commits |
| State-cube rows 3, 4, 8 | HIGH | Row 8 implementation added (sidecar branch-mismatch refusal); three new tests cover rows 3 (adopt existing canonical worktree), 4 (refuse non-canonical path), 8 (refuse same lane-id for different branch) |
| `wt doctor` precedence bug | HIGH | Replaced `A and B and C if D else False` one-liner with explicit nested-if structure. External worktrees parked outside `.orca/worktrees/` now correctly surface as orphan-git issues |
| `tmux.session.killed` not emitted | MEDIUM | `wt ls` now reads prior events; on first observed attached→session-missing transition, emits the event. Idempotent (subsequent runs check ledger of past killed events) |
| Task 27 only tests session-missing | MEDIUM | Extracted `_compute_tmux_state(window, live_windows)` pure helper. Three new unit tests verify each documented value: attached / stale / session-missing |
| `wt start` RMW not under lock | MEDIUM | Sidecar read moved INSIDE the `acquire_registry_lock` context; whole stage-2/stage-3/setup_version update is now atomic vs concurrent `wt start` |
| Task 18 test variable rebinding | MEDIUM | Renamed second `result` to `git_check` for clarity |
| Devcontainer trust-ledger guidance | MEDIUM | Added README paragraph explaining `~/.config/orca/` mount or `ORCA_TRUST_LEDGER` env override for devcontainer/codespace persistence |
| Schema-v2 deprecation tracking | MEDIUM | Added `# TODO(schema-v3, 2026-Q4): drop dual-emit ...` comment above the dual-emit block in `write_sidecar` |
| Constitution / agents-md auto-symlinks | LOW | `run_stage1` extended with `constitution_path` and `agents_md_path` kwargs; manager call site loads manifest and threads them through |
| Test name `_when_worktrees_enabled` lies | LOW | Renamed to `test_apply_seeds_worktrees_config` and updated comment to clarify v1 always-on, post-Phase-2 schema bump for the gate |
| Effort estimate uneven distribution | LOW | Added "Task pacing" section to preamble listing thick tasks (19, 23, 25, 28, 30) and thin tasks (1-3, 6-9, 31-32) |

**Outstanding from review:** none.
