# Worktree Contract Spec Review

**Date:** 2026-05-01
**Spec:** docs/superpowers/specs/2026-05-01-orca-worktree-contract-design.md
**Reviewer:** Cross-pass (Code Reviewer subagent)

### Round 1 - Cross-pass

**Verdict:** needs-revision

#### Findings

##### [BLOCKER] Phase 1 promised `after_create_script` field; contract ships `init_script`
**Criterion:** cross-spec-consistency
**Issue:** The Phase 1 spec at lines 604-614 explicitly proposed the Phase 2 contract schema with the field name `after_create_script`. The Phase 2 contract spec ships the same shape but renames the field to `init_script`. There is no migration note, no compat alias, and no reconciliation in §"Schema". A repo author who read Phase 1 (already shipped, PR #75) and pre-authored a `.worktree-contract.json` against the documented field name will fail validation under Phase 2's reader (which requires `init_script`).
**Evidence:**
- Phase 1 spec line 612: `"after_create_script": ".worktree-contract/after_create.sh"`
- Phase 2 spec line 88: `"init_script": ".worktree-contract/after_create.sh"`
- Phase 2 spec line 99: field is named `init_script` in the validation table; no alias mentioned
**Recommendation:** Pick one and cross-reference. Either (a) keep `init_script`, document it as a deliberate rename of Phase 1's promised name, and amend the Phase 1 spec section to note the corrected field name; or (b) accept both keys at the reader (`init_script` preferred, `after_create_script` accepted with deprecation warning) for one schema generation. Option (a) is cleaner since Phase 1 only design-promised the schema and didn't ship a reader for it.

##### [HIGH] Stage 1 currently overrides host defaults; contract claims union semantics
**Criterion:** cross-spec-consistency
**Issue:** The contract spec at line 153 promises "Symlink lists are the union" and at line 148 says "additionally apply the contract's symlinks." But the already-shipped `auto_symlink.run_stage1()` at `src/orca/core/worktrees/auto_symlink.py:44` does `paths = explicit if explicit else derive_host_paths(host_system)` — a non-empty `cfg.symlink_paths` OVERRIDES host defaults rather than unioning. If `wt init` writes a contract-derived list into `worktrees.toml`, host defaults stop applying. The contract's Discovery heuristic (rule 4, line 118) tries to avoid this collision by excluding host-layout-covered dirs, but that only helps when the operator runs `emit`. A hand-authored contract that lists `specs` (already a host default) will still trigger the override. The spec asserts behavior that the underlying Stage 1 code does not currently implement.
**Evidence:**
- Phase 1 spec line 196: "Empty list = derive from host.system. Explicit list = override."
- Stage 1 code at `src/orca/core/worktrees/auto_symlink.py:44`: `paths = explicit if explicit else derive_host_paths(host_system)`
- Phase 2 spec line 153: "Symlink lists are the union."
- Phase 2 spec line 148: "additionally apply the contract's symlinks."
**Recommendation:** Either change `run_stage1` so explicit + host_layout always union (and update the Phase 1 spec's "explicit list = override" line accordingly — that change was a deliberate choice and reversing it has its own consequences), or weaken the contract's union claim to "the contract's lists are merged into `worktrees.toml.symlink_paths`; host_layout dedup happens at write-time during `wt init`." The latter doesn't fix the runtime path (line 148, "operator skipped `wt init`"). Pick one; spec the runtime reader's exact merge/override rule unambiguously.

##### [HIGH] Trust asymmetry between orca reader and cmux shim is a real foot-gun, not just documented
**Criterion:** security
**Issue:** The orca side runs `init_script` through the TOFU ledger (line 76, line 137, line 153). The cmux shim runs `init_script` directly without trust at line 230-232: `if [[ -x "$INIT_SCRIPT" ]]; then "$INIT_SCRIPT"; fi`. For a cloned hostile repo, `cmux new` via the shim is RCE-equivalent on first checkout while `orca-cli wt new` would prompt. The spec doesn't acknowledge this asymmetry at all in §"cmux compatibility" — it only says "cmux: runs the shim's `.cmux/setup` directly (no trust)" at line 78 as a general note about cmux's model, not as a security warning about the shim writer. A user who runs `orca-cli wt contract install-cmux-shim` is being handed a script that *bypasses orca's signature security feature*, with no warning.
**Evidence:**
- Phase 2 spec line 76: "TOFU trust ledger gates `init_script`"
- Phase 2 spec line 230-232: shim invokes `$INIT_SCRIPT` directly with no trust check
- Phase 2 spec §"Out of scope": "Trust signing / SHA verification of `init_script`" deferred — this is about contract-level signing, separate from the shim's trust hole
- §"cmux compatibility" has no security note about this
**Recommendation:** Add a §"Security model" subsection under cmux compatibility explicitly stating: (1) the shim does NOT participate in orca's TOFU ledger by design; (2) operators using cmux as their primary tool get cmux's trust model (i.e., none), not orca's; (3) `wt contract install-cmux-shim` prints a one-time warning ("This shim runs `init_script` without orca's TOFU prompt; consider running `orca-cli wt new` instead for first-time clones"). Optionally: have the shim invoke `orca-cli wt contract trust-check $INIT_SCRIPT` if `orca-cli` is on PATH, to bridge the two. The latter is more work; the warning + doc fix is the minimum.

##### [HIGH] `from-cmux` regex parser is fragile against the documented target pattern
**Criterion:** feasibility
**Issue:** §"Migration helpers" line 263 says: "Regex extracts the items between `for f in ... ; do` (env files) and `for d in ... ; do` (paths)." The reference perf-lab setup at `~/perf-lab/.worktrees/010-cmux-test/.cmux/setup` (which I read for this review) matches the loop pattern verbatim, so the heuristic works for that file. But cmux's `cmux init` Claude-generated setups (cmux.sh line 783-820) are arbitrary bash — not the documented pattern. Operators who ran `cmux init` get LLM-generated bash with conditionals, multi-line `find`s, sourced helpers, etc. The spec acknowledges this at line 268 ("Complex bash ... won't parse cleanly") but underestimates how common it is: most `.cmux/setup` files in the wild are LLM-authored, not hand-authored to match the documented pattern. The "warns on unparsed lines" fallback is fine, but the spec's claim that `from-cmux` is a real migration helper for cmux users is overstated. Also, the parser must distinguish `for f in .env ...` from `for f in $(find ...)` or `for f in "${env_files[@]}"`; a naive regex will match the latter and produce garbage entries.
**Evidence:**
- Phase 2 spec line 252-261: only two patterns documented
- Phase 2 spec line 263: "Regex extracts the items between..."
- cmux.sh line 783+: `cmux init` generates setup via LLM; output is NOT pattern-constrained
- `~/perf-lab/.worktrees/010-cmux-test/.cmux/setup` happens to match because perf-lab's was hand-authored; not representative
**Recommendation:** Tighten the parser scope: require the loop's iterable to be a literal list of bareword tokens (no `$(...)`, no `${...}`, no `"..."`). On any other shape, refuse to extract from that loop and surface the line range to stderr. Add to `--help`: "Best for hand-authored setups that match `~/perf-lab/.cmux/setup`. LLM-generated setups (from `cmux init`) usually need hand migration." Add a fixture for an LLM-style cmux setup in `tests/core/worktrees/test_from_cmux.py` and assert the parser gracefully refuses + warns rather than producing wrong output.

##### [MEDIUM] `host_layout.derive_host_paths()` citation is wrong; correct module is `worktrees.auto_symlink`
**Criterion:** dependencies
**Issue:** Discovery rule 4 at line 118 says "Skip: anything covered by `host_layout.derive_host_paths()`." But the function lives at `src/orca/core/worktrees/auto_symlink.py:19`, exported as `derive_host_paths(host_system)`. The `orca.core.host_layout` package exports `HostLayout`, `detect`, `from_manifest`, `BareLayout`, etc. — not `derive_host_paths`. An implementer following the spec literally would import-fail.
**Evidence:**
- Phase 2 spec line 118: "host_layout.derive_host_paths()"
- Actual location: `src/orca/core/worktrees/auto_symlink.py:19` (`def derive_host_paths(host_system: str) -> list[str]`)
- `src/orca/core/host_layout/__init__.py:34-35`: `__all__` does not include `derive_host_paths`
**Recommendation:** Change line 118 to reference `orca.core.worktrees.auto_symlink.derive_host_paths` (the actual import path). One-word fix, but spec-as-pseudocode bugs propagate into implementation if not caught.

##### [MEDIUM] Discovery scan budget under-specified for monorepos
**Criterion:** feasibility / industry-patterns
**Issue:** §"Discovery" at lines 114-116 says non-dot dirs <50 MB and dot-dirs <5 MB are included. For a monorepo with `apps/` containing 200 packages totaling 4 GB, computing total size requires walking every file (Python `os.walk` + `stat`). On a cold filesystem with cold cache, that can be tens of seconds. The spec doesn't specify (a) whether scan respects `.gitignore`, (b) whether it bails early once the size limit is exceeded, (c) what happens on permission-denied subdirs, (d) the timeout. Operators running `emit` for the first time will see a 30-second hang with no progress feedback.
**Evidence:**
- Phase 2 spec line 115: "<5 MB total"
- Phase 2 spec line 117: "<50 MB"
- No mention of early termination, gitignore awareness, progress feedback, or timeouts
**Recommendation:** Spec these explicitly:
- Use `git ls-files` for tracked-file enumeration (bounded by `.gitignore`, fast even on monorepos) instead of raw `os.walk`. Untracked files don't count toward the cap.
- Bail early: stop summing once the cap is exceeded; mark the dir "skipped: too large" and move on.
- Permission-denied dirs: log to stderr, skip dir, don't fail the whole emit.
- Print `Scanning <dir>...` progress to stderr when scan exceeds 2 seconds.
- Document that `emit` is a one-shot authoring command and a 5-10s wall-clock is acceptable; it's not on the hot path.

##### [MEDIUM] Union dedup order is non-deterministic; matters for symlink-loop semantics
**Criterion:** feasibility
**Issue:** §"Conflict resolution" line 152 says "Symlink lists are the union. ... Duplicates are deduped on path equality." Set-based dedup loses ordering. For symlink creation order, the order rarely matters (each symlink is independent), but the spec's stated semantics depend on iteration order in two places: (a) tests asserting that `wt new` produces symlinks "in the order declared in the contract" can flake; (b) operators relying on shell glob ordering (`for d in $(ls .)`) — none in this spec, but worth pinning. More importantly, when contract has `["a", "b"]` and `worktrees.toml` has `["b", "a"]`, the union produces what? `["a", "b"]`? `["b", "a"]`? `set()` would lose order; `dict.fromkeys()` preserves first-insertion. Spec doesn't say.
**Evidence:**
- Phase 2 spec line 152: "Duplicates are deduped on path equality." (no order rule)
**Recommendation:** Pin the order explicitly: "Union preserves first-occurrence order, with contract entries listed before `worktrees.toml` entries (since contract is the team-shared spec of record). Implementation: `list(dict.fromkeys(contract + cfg))`." Add a test asserting this. Low-stakes but eliminates a class of test flakes.

##### [MEDIUM] cmux shim's embedded Python assumes `python3` on PATH; not documented
**Criterion:** feasibility
**Issue:** The shim at line 204 uses `python3 - "$CONTRACT" "$REPO_ROOT" <<'PY'` and at line 227 uses `python3 -c "..."`. On macOS without Xcode CLT, on stripped-down container images, on systems where Python is `python` not `python3`, on systems where `python3` is 2.7-aliased — the shim breaks. The spec's "no extra deps" claim at line 236 is misleading; it depends on `python3` being on PATH and being Python ≥ 3.6 (for f-strings at line 211). cmux itself (per cmux.sh) is pure bash + git + standard coreutils; the shim raises the floor.
**Evidence:**
- Phase 2 spec line 204: `python3 - "$CONTRACT" "$REPO_ROOT" <<'PY'`
- Phase 2 spec line 227: `python3 -c "..."`
- Phase 2 spec line 236: "~30 LOC of bash + embedded Python (no extra deps)" — false: depends on `python3`
- cmux.sh uses no Python; pure bash
**Recommendation:** Either (a) document the dependency: "Shim requires `python3` ≥ 3.6 on PATH. Operators on minimal images or systems with only `python`-aliased Python 3 should set up a `python3` shim or hand-author `.cmux/setup`." Add a `command -v python3 || { echo "python3 required" >&2; exit 1; }` guard at shim top so failure is loud not silent. Or (b) rewrite the shim parser in pure bash + `jq` (jq is more commonly preinstalled than python3 in container images and gives proper JSON parsing, no quoting nightmare). Option (b) is more work but matches cmux's pure-shell aesthetic.

##### [MEDIUM] schema_version migration strategy unspecified
**Criterion:** industry-patterns
**Issue:** Line 96 says `schema_version` "Must be `1`. Future versions trigger migration prompt." That's the entire migration spec. What's a v2? Additive-only (new optional fields)? Breaking renames? What does "migration prompt" do — auto-rewrite the operator's committed file? Refuse to load and demand `wt contract migrate`? Both behaviors are reasonable; the spec picks neither. Phase 1's worktree-manager spec was much more rigorous about its v1→v2 registry migration (lines 396-408 of that spec). The contract spec under-invests here.
**Evidence:**
- Phase 2 spec line 96: "Future versions trigger migration prompt." (no detail)
- No `wt contract migrate` verb
- No statement on whether v2 is additive-only or breaking
**Recommendation:** Add a paragraph: "Future versions are additive-only by default (new optional fields). A v2 reader silently accepts v1 contracts. Breaking changes (renamed/removed fields) require a major-version bump and a separate `wt contract migrate` verb (out of scope here; tracked for v3)." This costs no implementation effort in v1 and prevents future churn.

##### [LOW] Test fixture provenance unspecified
**Criterion:** industry-patterns
**Issue:** §"Testing" at lines 302-307 mentions "perf-lab-shaped", "openspec-shaped", "bare repo" fixtures but doesn't say where they live. Phase 1's spec also under-documented this and the test surface ended up larger than estimated. Are these `tmp_path` programmatic constructions in `conftest.py`? Committed under `tests/fixtures/`? Each approach has tradeoffs (programmatic = fast to author, fragile to host_layout changes; committed = realistic, expensive to maintain).
**Evidence:**
- Phase 2 spec line 302-307: fixture types named, not located
**Recommendation:** Add to §"Testing": "Fixtures are programmatically constructed via `pytest.fixture` in `tests/core/worktrees/conftest.py` using `tmp_path`. Layout: a builder function `make_repo(host_system, top_level=[...])` returns a tmp git repo populated with the requested signal files. No on-disk fixture trees committed." Estimated impact: +0.1 days; better than discovering this gap mid-implementation.

##### [LOW] Spec assumes orca + cmux only; no extension hooks for other worktree managers
**Criterion:** industry-patterns
**Issue:** The contract design accommodates orca and cmux. Other worktree tools (`mise`, `worktree-manager`, plain `git-worktree-go`, etc.) exist. The §"Out of scope" line at 31 dismisses "Plain `git worktree` shim" as the operator's problem. But the contract is *named* `.worktree-contract.json` — implying tool-neutrality. If a third tool emerges, the four-field schema is rigid. No reserved namespace for tool-specific extensions (e.g., `extensions.cmux.foo`, `extensions.mise.bar`).
**Evidence:**
- Phase 2 spec line 28: "Per-tool extension blocks in the contract" listed as out of scope
- Filename `.worktree-contract.json` claims tool-neutrality
**Recommendation:** Reserve a top-level `extensions` object key in the schema, ignored by orca's reader, available for future per-tool fields. Cost: zero (just don't error on unknown top-level keys today; spec it for v1). This is a 1-line addition: "Unknown top-level fields (other than the four declared) are ignored by orca's reader. Reserved for future extension namespaces."

#### Per-criterion summary

- **cross-spec-consistency:** Two findings — `init_script` rename (BLOCKER), Stage 1 override-vs-union (HIGH).
- **feasibility:** Three findings — from-cmux parser (HIGH), discovery scan budget (MEDIUM), union order (MEDIUM), python3 dep (MEDIUM).
- **security:** One finding — trust asymmetry shim (HIGH).
- **dependencies:** One finding — `host_layout.derive_host_paths` mis-citation (MEDIUM). The other items in this criterion (Phase 1 shipped, path_safety shipped, cmux upstream PR optional) — no issues identified.
- **industry-patterns:** Three findings — schema migration strategy (MEDIUM), test fixture provenance (LOW), tool-neutrality / extension namespace (LOW). TOML vs JSON: no finding — the spec deliberately picks JSON for cmux compat (cmux.sh is pure bash, can't easily parse TOML; jq is the common JSON parser); the choice is defensible and doesn't warrant a finding.

#### Verdict rationale

The spec is well-scoped and small (~339 lines for ~2.25 days of work), but two issues block clean implementation: (1) the `after_create_script` → `init_script` rename contradicts the Phase 1 spec's own promise of the schema, which will surprise the first repo author who pre-authored a contract against the documented field name; (2) Stage 1's already-shipped override semantics conflict with the contract's stated union semantics, and the spec does not call out that `auto_symlink.run_stage1` would need to change. Beyond those, the trust asymmetry between orca's reader and the cmux shim is a real security gap worth a docs/UX fix, and the `from-cmux` parser scope is overstated for the population of cmux setups in the wild. Mostly mechanical fixes; the spec's architecture is sound and the v2.0 ship path stands independently of cmux upstream cooperation. Recommend one revision round addressing the two cross-spec-consistency items + the trust-asymmetry warning, then ready to ship.

| Severity | Count |
|---|---|
| Blocker | 1 |
| High | 3 |
| Medium | 5 |
| Low | 2 |

### Round 2 - Author response

**Verdict:** all 11 findings addressed in spec v2 (commit follows).

| Finding | Severity | Resolution |
|---|---|---|
| `init_script` rename | BLOCKER | Kept `init_script`; added explicit "Naming note (Phase 1 reconciliation)" callout in §"Schema". Phase 1 only design-promised the schema (no shipped reader); Phase 1's perf-lab compat section will be amended in this PR's docs commit |
| Stage 1 override-vs-union | HIGH | Acknowledged: `auto_symlink.run_stage1()` MUST change to always union. Added explicit "Phase 1 implementation change required" line + concrete one-line replacement spec'd: `paths = list(dict.fromkeys(derive_host_paths(host_system) + cfg.symlink_paths + contract.symlink_paths))`. Effort estimate +0.25 days |
| Trust asymmetry | HIGH | New §"Security model (read first)" subsection at top of §"cmux compatibility". Documents the asymmetry, mandates `install-cmux-shim` warning, references future strict-shim option as out-of-scope |
| `from-cmux` parser scope | HIGH | Tightened: parser REQUIRES bareword-list iterable + verbatim body match. 3 explicit fixtures (A: matches, B: LLM-generated refuses, C: non-bareword refuses). Realistic scope statement added to `--help` text |
| Wrong import path | MEDIUM | Fixed: `host_layout.derive_host_paths` → `orca.core.worktrees.auto_symlink.derive_host_paths` |
| Discovery scan budget | MEDIUM | New "Scan budget (monorepo handling)" subsection: `git ls-files` enumeration, early-bail on size, permission-denied = skip + log, progress feedback every 2s |
| Union dedup order | MEDIUM | Pinned: `list(dict.fromkeys(...))` first-occurrence order; sequence is host_layout → worktrees.toml → contract |
| python3 dependency | MEDIUM | New "Shim runtime requirements" subsection. Shim now starts with `command -v python3` guard. Documented Python ≥ 3.6 requirement |
| schema migration strategy | MEDIUM | New paragraph: additive-only by default; v2 reader accepts v1 silently; breaking changes require version bump + future `wt contract migrate` verb |
| Test fixture provenance | LOW | New "Test fixture provenance" subsection: programmatic `tmp_path` via `make_repo()` builder in `conftest.py`; no committed fixture trees |
| Extension namespace | LOW | New `extensions` reserved field; v1 reader ignores; documented in §"Schema" + new "Unknown top-level keys" rule for forward-compat |

**Outstanding from review:** none. v2 ready for plan-writing.
