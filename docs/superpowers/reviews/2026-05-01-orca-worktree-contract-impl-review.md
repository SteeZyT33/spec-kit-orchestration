# Worktree Contract Implementation Review

**Date:** 2026-05-01
**Branch:** orca-worktree-contract
**Commits in scope:** 16 (7156d88..HEAD)
**Test counts:** unit 39 (13 + 9 + 7 + 4 + 6) / integration 3 — matches plan claim of "~38 unit + 3 integration"

All 50 tests in scope green under `uv run pytest`.

### Round 1 — Implementation review

**Verdict:** needs-revision

The schema loader, merge_symlinks, run_stage1 ripple, parser, CLI dispatcher,
and shim install path all work as specified and pass tests. Two findings are
load-bearing for the spec and, separately, the cmux shim has an asymmetric
trust model relative to the orca CLI path that should be documented or
hardened before this lands. The remaining items are sharp edges and small
correctness gaps that are easy to fix in a follow-up commit.

#### Findings

##### [HIGH] `init_script` is loaded but never executed by `orca-cli wt new`
**Area:** 6 (and indirectly 3)
**Issue:** Spec §"Validation rules" mandates that `init_script`, when set, "is
checked for existence + executable bit at `wt new` time (Stage 2 invocation)"
and §"Field semantics" says it "Runs once after worktree creation."
Implementation only stores `init_script` in `ContractData` and returns it from
`load_contract`. Nothing in `run_stage1`, `_run_setup_stages`, or
`WorktreeManager.create` reads `contract.init_script` or invokes it. Only the
cmux shim ever runs it (`contract_shim.py:64-70`). An operator who emits a
contract with `init_script: ".worktree-contract/after_create.sh"` will get
their symlinks but their script is silently ignored when they run
`orca-cli wt new`.
**Evidence:**
- `src/orca/core/worktrees/manager.py:180-195` — loads contract, threads it to `run_stage1`, never reads `contract.init_script`.
- `src/orca/core/worktrees/auto_symlink.py:48-90` — uses `contract.symlink_paths`/`symlink_files` only.
- `grep -rn "contract.init_script\|contract\\.init_script" src/` returns no matches outside `contract.py`/`contract_emit.py`.
- No test asserts that `init_script` actually runs from `orca-cli wt new`. `test_emit_then_new_applies_contract_symlinks` only asserts symlink creation.
**Recommendation:** In `_run_setup_stages`, after Stage 1 and after the
existing `after_create_hook` runs, gate `contract.init_script` through the
same trust ledger (`_trust_or_skip` with the `after_create` decision), then
invoke it via `run_hook`. Alternative: add a fast-fail at contract-load that
documents `init_script` as cmux-only-for-now and amend the spec. Either
direction is fine, but the current state is "spec-promised, silently
unimplemented."

##### [HIGH] `propose_candidates` does not skip nested host_layout paths (`docs/superpowers`, `docs/orca-specs`)
**Area:** 4
**Issue:** Spec §"Discovery" line 132 says: "Skip: anything covered by
`derive_host_paths(host_system)` ... Specifically: `.specify/`, `specs/`
(spec-kit), `docs/superpowers/` (superpowers), `openspec/` (openspec),
`docs/orca-specs/` (bare). Contract should not duplicate them." The
implementation builds `host_skip = set(derive_host_paths(host_system))` and
filters with `if name in host_skip` — but `name` is a top-level entry name
like `"docs"`, while `host_skip` for superpowers/bare contains
`"docs/superpowers"` / `"docs/orca-specs"`. The set membership check never
matches the parent. Result: for `host_system="superpowers"` or `"bare"`,
`docs/` is always proposed as a top-level symlink_path even though the host
already auto-symlinks the relevant subdir.

Verified empirically: in a fresh repo with `docs/superpowers/foo.md` and
`docs/other.md`, `propose_candidates(repo, host_system="superpowers")`
returns `symlink_paths=['docs']`. After Stage 1 dedup, the worktree ends up
with `<wt>/docs` as a single symlink to primary, which prevents the
operator from ever having per-worktree `docs/non-superpowers/...` content
— exactly the failure mode the host_skip rule was designed to prevent.

The `spec-kit` host has only top-level entries (`.specify`, `specs`), which
is why the unit test `test_skips_host_layout_overlap` passed.
**Evidence:**
- `src/orca/core/worktrees/contract_emit.py:98-104`
- `tests/core/worktrees/test_contract_emit.py:36-43` — only exercises spec-kit, masks the bug.
**Recommendation:** Expand `host_skip` to include the first path segment of
every entry, OR refuse to propose any top-level dir that contains a
host_skip path: `host_skip_top = {Path(p).parts[0] for p in derive_host_paths(host_system)}`.
Add a regression test for `host_system="superpowers"` that asserts `docs`
is not in `proposal.symlink_paths` when only `docs/superpowers/...` exists.

##### [HIGH] Cmux shim creates symlinks from raw JSON without traversal validation
**Area:** 6 (cmux compatibility)
**Issue:** `load_contract` rejects absolute paths and `..` segments per spec.
The cmux shim (`contract_shim.py:40-62`) inlines its own python that does
`for rel in c.get("symlink_paths") + c.get("symlink_files"): os.symlink(src, rel)`
with **no traversal guard**. A hostile or merely malformed contract with
`symlink_paths: ["../../tmp/evil"]` causes the shim to create a symlink at
that absolute location relative to the worktree CWD. The shim does refuse
to clobber existing non-symlinks (`if os.path.lexists(rel) and not
os.path.islink(rel): continue`), so `/etc/passwd` is safe — but any
non-existent path outside the worktree is fair game.

This is consistent with the spec's "cmux shim is best-effort" note, but
the shim already fronts the trust warning, and adding ~6 lines of
validation here closes a real footgun for operators who land malformed
contracts in shared repos.
**Evidence:** `src/orca/core/worktrees/contract_shim.py:40-62` — no check
on `rel` before `os.symlink`.
**Recommendation:** In the embedded python, add at the top of the loop:
```python
if rel.startswith("/") or ".." in rel.split("/"):
    print(f"contract: rejecting unsafe path {rel!r}", file=sys.stderr)
    continue
```
The `init_script` extraction (line 64) has the same gap and should also
reject `..` and absolute paths before exec-ing.

##### [MEDIUM] CLI `--cmux-script` and `--init-script` flags bypass `path_safety`
**Area:** 8
**Issue:** Spec §"Validation rules" cites `orca.core.path_safety` Class A
rules. CLI handlers accept operator-supplied paths without invoking it:
- `_run_wt_contract_from_cmux` (`python_cli.py:2296`) takes
  `--cmux-script` and reads it directly with no `validate_repo_file`.
  An operator passing `--cmux-script ../../etc/something` would be honored.
- `_run_wt_contract_emit` (`python_cli.py:2241`) takes `--init-script`
  and writes it verbatim into the contract JSON. The string is later
  validated by `load_contract` on the next `wt new`, so the eventual
  symlink attempt is guarded — but the contract on disk is invalid until
  someone reads it.
**Evidence:**
- `src/orca/python_cli.py:2296-2299` — `--cmux-script` not validated.
- `src/orca/python_cli.py:2241,2270` — `--init-script` written without validation.
**Recommendation:** Run `validate_repo_file(repo_root, ns.cmux_script)` for
from-cmux. For `--init-script`, run the same `_validate_path_relative`
helper used by `load_contract` so the emit-time check matches the
load-time check (no asymmetric "you can write a contract you can't load").

##### [MEDIUM] `--max-dir-size` flag is parsed and silently ignored
**Area:** 7
**Issue:** `_run_wt_contract_emit` defines `--max-dir-size` (int, default
50) but never passes it to `propose_candidates` or `emit_contract`. The
underlying `propose_candidates` accepts `dot_dir_cap_mb` and
`non_dot_dir_cap_mb` kwargs but they remain at module defaults. Operator
sets the flag, sees no effect.
**Evidence:** `src/orca/python_cli.py:2242-2243` (defined),
`src/orca/python_cli.py:2263-2278` (never used). `grep` confirms
`max_dir_size_mb` appears only at the parser definition.
**Recommendation:** Either wire it through (`non_dot_dir_cap_mb=ns.max_dir_size_mb`)
or remove the flag. Wiring through is the lighter touch and matches the
likely intent.

##### [MEDIUM] `from-cmux` writes a non-empty `after_create.sh` even when only bash boilerplate remains
**Area:** 5/7
**Issue:** `_run_wt_contract_from_cmux` (`python_cli.py:2340-2349`) writes
`.worktree-contract/after_create.sh` whenever `parsed.init_script_body.strip()`
is non-empty. After the parser strips handled loop spans, what often
remains is `#!/bin/bash` + `set -euo pipefail` + the `REPO_ROOT="..."`
computation — i.e., bash boilerplate with no real work. The handler then
prepends a SECOND shebang and SECOND `set -euo pipefail` (line 2345),
producing a script that is technically valid (the second `#!` becomes a
comment) but useless and confusing on inspection. The user sees
`init_script` in their contract for no semantic reason.
**Evidence:** `src/orca/python_cli.py:2338-2349`,
`src/orca/core/worktrees/contract_from_cmux.py:109-120`.
**Recommendation:** In the parser, when computing `init_script_body`,
strip the leading shebang/`set` block and a `REPO_ROOT=` assignment if
those are the only non-loop content. Alternatively: in the handler,
detect "boilerplate-only" (regex: shebang+set+REPO_ROOT and nothing else)
and skip writing `after_create.sh`.

##### [MEDIUM] Bad/malformed contract is silently swallowed by `WorktreeManager`
**Area:** 1/3
**Issue:** `manager._run_setup_stages` wraps `load_contract` in
`try: ... except ContractError: contract = None` (`manager.py:181-187`)
with a comment "Doctor will surface the parse error separately." There is
no `wt doctor` for contracts in this PR, no event emit
(`contract.parse_failed` or similar), and no stderr warning. An operator
who fat-fingers their contract gets a worktree without any of the
contract's symlinks and no signal that anything went wrong. The CI envelope
logging (`emit_event(state_root, event="contract.load_failed", ...)`) would
take ~3 lines and gives a forensic trail.
**Evidence:** `src/orca/core/worktrees/manager.py:180-187`.
**Recommendation:** Emit a structured event on `ContractError` and print a
short stderr warning. Or fail loudly — a malformed contract in a shared
repo is operationally serious enough that "silent skip" is the wrong
default.

##### [LOW] `init_script` extraction in shim is fragile to single-quote in repo path
**Area:** 6
**Issue:** `contract_shim.py:64`:
```bash
INIT_SCRIPT_REL="$(python3 -c "import json; print(json.load(open('$CONTRACT')).get('init_script') or '')")"
```
`$CONTRACT` is interpolated into a single-quoted Python string literal. If
the repo lives at a path containing a single quote (e.g., `/home/user's
repo`), this produces a Python `SyntaxError`. `set -e` aborts the shim,
the user sees a confusing python traceback. Rare but real: macOS users
sometimes have apostrophes in account names.
**Evidence:** `src/orca/core/worktrees/contract_shim.py:64`.
**Recommendation:** Pass the path as `sys.argv` rather than interpolating:
```bash
INIT_SCRIPT_REL="$(python3 - "$CONTRACT" <<'PY'
import json, sys
print(json.load(open(sys.argv[1])).get('init_script') or '')
PY
)"
```
Mirrors the pattern already used in lines 40-62.

##### [LOW] Contract bypass in `path_safety` cite
**Area:** 1
**Issue:** Spec says contract validation "uses `orca.core.path_safety`
Class A rules"; implementation hand-rolls the checks
(`contract.py:32-42`). Functionally equivalent for absolute and `..`
detection, but it bypasses `path_safety`'s symlink-resolution and
root-containment checks. Since contract entries are name-patterns (not
yet-materialized files), full Class A validation isn't applicable, so
this is more of a cite-mismatch than a real defect.
**Evidence:** `src/orca/core/worktrees/contract.py:32-42` vs
`src/orca/core/path_safety.py:46-200`.
**Recommendation:** Either update the spec cite to "validates per Class A
absolute/traversal rules; defers materialization checks to Stage 1" OR
move the helper into `path_safety` as a `validate_contract_path` so the
module owns the rule.

##### [LOW] Dead-code path in `contract_emit` excluded-name check
**Area:** 4
**Issue:** `contract_emit.py:108`:
```python
if name == ".git" or name.startswith(".git/"):
```
`name` comes from `repo_root.iterdir()` and is a single path segment — it
will never contain `/`. The `startswith(".git/")` branch is unreachable.
Harmless but misleading; suggests the author intended to filter
`.gitmodules`/`.gitattributes`/`.gitignore` and got the syntax wrong, or
copied from a deeper-walking iteration.
**Evidence:** `src/orca/core/worktrees/contract_emit.py:108`.
**Recommendation:** Drop the `or name.startswith(".git/")` clause, or
state explicitly which `.git*` names should also be excluded
(`.github/` should NOT be — operators want CI workflows symlinked).

#### Summary

| Severity | Count |
|---|---|
| Blocker | 0 |
| High | 3 |
| Medium | 4 |
| Low | 3 |

**Notes for the operator:**
- Test coverage matches plan claim. Coverage gap is the host_skip nested-path case (Finding #2) — a one-line regression test catches it.
- All 16 commits are clean: lowercase, ≤72 chars, single logical units, no merges, no fixups.
- The schema validator, merge_symlinks ordering, run_stage1 ripple, and CLI dispatcher are all correct against the spec.
- Two of the High findings (#1 init_script not invoked, #2 host_skip nested) are spec-conformance issues with concrete operator-visible failure modes — recommend fixing before merge. The third High (#3 shim traversal) is a defense-in-depth item that could be a fast-follow if the team is comfortable shipping with a stderr warning instead.
