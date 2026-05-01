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

### Round 2 - Re-review of v2

**Verdict:** needs-revision

#### Verification of round-1 findings

1. **`init_script` rename (BLOCKER)** — Partially resolved. The v2 spec adds the "Naming note (Phase 1 reconciliation)" callout at lines 103-104. However, the disposition table promises "Phase 1's perf-lab compatibility section will be amended in this PR's docs commit," and that amendment has NOT happened in `2026-04-30-orca-worktree-manager-design.md` — line 612 still reads `"after_create_script": ".worktree-contract/after_create.sh"`. The fix is committed-to but not delivered in the file under review.
2. **Stage 1 override-vs-union (HIGH)** — Resolved on paper. Lines 167 specify the exact one-liner replacement and call out the Phase 1 docs amendment. (Caveat: see new finding R2-NEW-2 below — the implementation change has ripples not yet acknowledged.)
3. **Trust asymmetry (HIGH)** — Partially resolved. Lines 201-214 add a §"Security model (read first)" block that documents the foot-gun. (Caveat: see new finding R2-NEW-3 below — the warning is install-time only and a fresh clone bypasses it entirely.)
4. **`from-cmux` parser scope (HIGH)** — Partially resolved. Lines 301-323 strict-pattern the parser and add fixtures A/B/C. (Caveat: see new finding R2-NEW-4 — strict pattern excludes plausible hand-authored variants the spec still claims to cover.)
5. **Wrong import path (MEDIUM)** — Resolved. Line 126 now reads `orca.core.worktrees.auto_symlink.derive_host_paths`.
6. **Discovery scan budget (MEDIUM)** — Partially resolved. Lines 137-142 add the §"Scan budget" subsection with `git ls-files`, early-bail, permission handling, progress feedback. (Caveat: see new finding R2-NEW-5 — `git ls-files` excludes untracked content, but the perf-lab discovery target includes untracked dot-dirs.)
7. **Union dedup order (MEDIUM)** — Resolved on paper. Line 167 pins `dict.fromkeys` order: host_layout → worktrees.toml → contract. (Caveat: see new finding R2-NEW-6 — chosen order contradicts §"Goals" framing of contract as authoritative.)
8. **python3 dependency (MEDIUM)** — Resolved. Lines 216-230 add §"Shim runtime requirements" with the `command -v python3` guard.
9. **Schema migration strategy (MEDIUM)** — Partially resolved. Lines 105-107 add a paragraph. (Caveat: see new finding R2-NEW-7 — the additive-only-without-bump rule is internally contradictory with the v1-reader-must-error-on-version-mismatch rule.)
10. **Test fixture provenance (LOW)** — Resolved. Lines 354-367 specify `tmp_path` + `make_repo()` builder.
11. **Extension namespace (LOW)** — Partially resolved. Line 101 reserves `extensions`, line 107 documents "ignore unknown top-level keys." (Caveat: see new finding R2-NEW-1 — malformed-but-present `extensions` value has no spec'd behavior.)

#### New findings (introduced by v2 revisions, or items round 1 missed)

##### [HIGH] R2-NEW-2: `run_stage1` signature change ripples not enumerated
**Criterion:** cross-spec-consistency
**Issue:** The v2 spec at line 167 calls out the one-line change to `auto_symlink.run_stage1` but treats it as a pure internal swap. Two real callsites need attention that the spec does not name: (a) `src/orca/core/worktrees/manager.py:179` calls `run_stage1` with `cfg=self.cfg` only — no contract is plumbed in. The v2 spec promises `contract.symlink_paths` is added to the union, but there's no spec'd path for `manager.py` to obtain `ContractData` and pass it. The runtime path described at line 163 ("if `.worktree-contract.json` exists ... additionally apply the contract's symlinks") has nowhere to land in the current call graph. (b) The shipped test `tests/core/worktrees/test_auto_symlink.py:50-58` (`test_explicit_symlink_paths_override_host_defaults`) asserts the OLD override semantics. Changing `run_stage1` flips this test red; the v2 spec doesn't mention test deletion or rewrite. The "0.25 days" estimate for the run_stage1 change covers the one-liner but not (a) wiring contract loading into `Manager._run_stages`, (b) plumbing `ContractData` through the function signature, or (c) the test rewrite.
**Evidence:**
- `src/orca/core/worktrees/manager.py:179-184` — `run_stage1` called with `cfg=self.cfg`, no contract param
- `tests/core/worktrees/test_auto_symlink.py:50-58` — asserts `cfg.symlink_paths=["custom"]` causes `.specify` to NOT be symlinked (the OLD override behavior)
- v2 spec line 167 — gives the one-line replacement but no signature change, no caller-update list
**Recommendation:** Expand line 167 to spell out the full delta: (1) `run_stage1` gains a `contract: ContractData | None = None` kwarg; (2) `manager.py` loads the contract via `load_contract(self.repo_root)` and passes it; (3) the existing `test_explicit_symlink_paths_override_host_defaults` is renamed and rewritten to assert union semantics; (4) the effort estimate's +0.25 day line item explicitly includes "+ caller updates + test rewrite" or bumps to +0.5 days.

##### [HIGH] R2-NEW-3: Install-time warning misses the cloned-hostile-repo scenario it's meant to defend
**Criterion:** security
**Issue:** The §"Security model" mitigation at lines 208-212 says `wt contract install-cmux-shim` prints a one-time warning at install time. That defends against an operator who is currently running `install-cmux-shim` on a known-good repo. But the threat model in line 205 is "for a cloned hostile repo, `cmux new` via the shim is RCE-equivalent on first checkout" — and that operator does NOT run `install-cmux-shim`; they `git clone <hostile>`, the hostile repo's `.cmux/setup` is already committed (the shim or any arbitrary bash), and `cmux new` runs it. The install-time warning is fired only on the operator's OWN repos, not on third-party repos. So the warning lands where the danger isn't. This is "warning + docs" theater for a real RCE.
**Evidence:**
- v2 spec line 205: threat model = "cloned hostile repo, `cmux new` via the shim is RCE-equivalent on first checkout"
- v2 spec lines 208-212: mitigation = warning at `install-cmux-shim` time (operator's own repo)
- The cmux shim itself (lines 238-287) has no warning print at runtime; it just runs `init_script`
**Recommendation:** Move the warning into the shim body itself: at the top of `.cmux/setup` (before `python3 -c json.load`), print to stderr "WARNING: this shim runs init_script with no trust check; press Ctrl-C in 3s to abort" with a `sleep 3` or a prompt-on-tty if `[ -t 1 ]`. Annoying-every-time IS the right call when the threat is per-clone, not per-install. Alternatively: spec a strict-shim variant (currently "out of scope" line 214) and recommend it as the default rather than the lenient one. The spec's claim that "warning + docs" is sufficient mitigation should be downgraded to "documented foot-gun, no real mitigation in v2.0" so reviewers don't mistake disclosure for defense.

##### [MEDIUM] R2-NEW-4: Strict parser pattern excludes common hand-authored variants the spec still claims to cover
**Criterion:** feasibility
**Issue:** Lines 304-318 require the iterable to be "literal bareword tokens" and the body to "match verbatim modulo whitespace." Hand-authored cmux setups (which the spec calls the 80% case at line 334) routinely use idiomatic variants the strict matcher will refuse: `[[ -e "$f" ]]` instead of `[ -e "$f" ]` (bash idiom), `test -e "$f"` (POSIX idiom), inline comments inside the loop body (`# symlink shared dirs`), `ln -s` instead of `ln -sf`, blank lines, line-continuation `\`. The spec's "verbatim body match" wording forbids all of these. Result: the operator hand-authors a setup that LOOKS like the documented template, runs `from-cmux`, gets "cannot extract symlinks" warnings, and does manual migration anyway. The "80% case" claim is overstated; with verbatim matching the realistic hit rate is closer to "exact-template-followers only."
**Evidence:**
- v2 spec line 318: "matches the literal symlink-or-replace pattern verbatim (modulo whitespace)"
- v2 spec line 334: "The 80% case (hand-authored setups matching the documented template) works"
- `~/perf-lab/.cmux/setup` happens to match exactly because perf-lab is the reference; non-reference repos likely vary in trivial ways
**Recommendation:** Either (a) loosen the body matcher to a parsed AST-shape rather than verbatim text — accept any of `[`, `[[`, `test`, with `-e`/`-f`/`-d` predicates, ignore comments + blank lines + line continuations; OR (b) be honest about scope: change line 334 to "Hand-authored setups exactly matching the perf-lab template work; trivial variations (different test syntax, comments) usually need hand migration." Pick one. The current text promises (a) and delivers (b).

##### [MEDIUM] R2-NEW-5: `git ls-files` discovery misses untracked dot-dirs that are the primary discovery target
**Criterion:** feasibility
**Issue:** Line 138 says "Use `git ls-files <dir>` for tracked-file enumeration ... Untracked content does NOT count toward size caps." But the heuristic at line 122 says "Always include in `symlink_paths`: top-level dot-dirs that are exists on disk (regardless of git status)." Dot-dirs like `.tools/`, `.omx/`, `.env-local/` are commonly gitignored — that's WHY they're symlink candidates (they hold worktree-shared local state, not tracked content). `git ls-files .tools/` returns empty for an untracked dir. With the v2 budget rule, an untracked dot-dir registers as 0 bytes (under the 5 MB cap, fine) but it ALSO registers as "no tracked content" — does the heuristic still include it? The spec is ambiguous: line 122 says include based on disk existence, line 138 says size from `git ls-files`. An untracked dir with 4 GB of content is 0-byte to `git ls-files` and infinite to `os.walk`. Which wins?
**Evidence:**
- v2 spec line 122 (rule 2): "exists on disk (regardless of git status)"
- v2 spec line 125 (rule 3): "tracked in git AND <50 MB"
- v2 spec line 138: "Use `git ls-files`... Untracked content does NOT count toward size caps"
- Reality: `.tools/`, `.omx/` are typically untracked AND large
**Recommendation:** Spell out the union: dot-dirs (rule 2) use `os.walk` with size cap and early-bail (operators get progress feedback at 2s); non-dot-dirs (rule 3) use `git ls-files`. Different rules for different signal classes is fine, but the spec must say so. Add to line 138: "Dot-dirs are size-checked via `os.walk` with early-bail on cap (`git ls-files` is empty for untracked content). Non-dot-dirs use `git ls-files` (gitignored content excluded by definition)."

##### [MEDIUM] R2-NEW-6: Pinned union order makes contract LAST, contradicting "team-shared spec of record" framing
**Criterion:** industry-patterns
**Issue:** Line 167 pins the order: `derive_host_paths(host_system) + cfg.symlink_paths + contract.symlink_paths` — host first, worktrees.toml second, contract last. With `dict.fromkeys` first-insertion semantics, this means when contract and worktrees.toml both list the same path, worktrees.toml's position wins. But §"Goals" line 41-43 frames contract as the team-shared baseline that operators should be able to TRUST as authoritative; line 167's parenthetical even labels contract "team-shared baseline" as last. For human-readable `wt config` output and conflict-resolution UX, contract entries appearing after operator-local overrides reads backward from the spec's own framing. Compare the disposition table's claim ("contract is the team-shared spec of record") with the chosen iteration order; they're misaligned.
**Evidence:**
- v2 spec §"Goals" line 41-43: contract is the team-shared bridge
- v2 spec line 167 parenthetical: "contract (team-shared baseline)" listed LAST
- Round-1 review line 80 recommended: "contract entries listed before `worktrees.toml` entries (since contract is the team-shared spec of record)" — the spec adopted the OPPOSITE order
**Recommendation:** Either swap to `derive_host_paths + contract.symlink_paths + cfg.symlink_paths` (host → contract → worktrees.toml) so the team-shared baseline appears before operator-local overrides, OR keep current order and add a one-line rationale at line 167: "worktrees.toml precedes contract because operators may locally narrow the team baseline; reordering to contract-first would surface team baselines first in `wt config` output but defeats local override expressivity." Pick one and document the WHY.

##### [MEDIUM] R2-NEW-7: Schema migration strategy is internally contradictory
**Criterion:** industry-patterns
**Issue:** Lines 105-107 say (a) "Future versions are **additive-only** by default: new optional fields can be added without bumping `schema_version`"; (b) "v1 readers presented with a v2 contract that has a higher `schema_version` raise `ContractError` rather than guessing." These two rules collide: if additive changes don't bump the version, then a contract with new optional fields stays at `schema_version: 1`, which means a v1 reader and a v2 reader both see version 1 and the v1 reader silently ignores the new fields (per line 107's "ignore unknown top-level keys"). Fine. But then when DOES `schema_version` increment? Only on breaking changes. So `schema_version` in this scheme is effectively a "breaking-changes-only counter" — but rule (b) says v1 readers MUST error on `schema_version=2`, which means a v2-aware repo cannot ship a contract that v1 readers gracefully degrade on. The "additive-only" path forecloses on `schema_version` ever incrementing for a non-breaking reason, which is fine; what's NOT fine is the spec saying "additive-only by default" without making explicit that additive changes are version-stable. A reader looking at this spec can't tell what version to set when adding a new optional field.
**Evidence:**
- v2 spec line 105: "additive-only by default ... A v2 reader silently accepts v1 contracts"
- v2 spec line 105: "Breaking changes ... require a `schema_version` bump"
- v2 spec line 107: "ignores top-level keys other than the five declared"
- Implication missed: additive changes don't bump version; only breaking changes do
**Recommendation:** Rewrite lines 105-107 to make the decision tree explicit: "(1) Adding a new optional top-level key does NOT bump `schema_version`; v1 readers ignore the unknown key per line 107. (2) Adding a new required field, removing a field, or changing a field's type bumps `schema_version` to 2; v1 readers raise `ContractError` on `schema_version >= 2`. (3) Renaming a field counts as breaking and requires `wt contract migrate` (future spec)." Three sentences eliminate the ambiguity.

##### [LOW] R2-NEW-1: Malformed `extensions` value has no spec'd behavior
**Criterion:** industry-patterns
**Issue:** Line 101 says `extensions` is "object" type, "Orca's reader IGNORES this key in v1; do not error on its presence." But what if `extensions: 42` (int) or `extensions: "foo"` (str) is committed? "IGNORES" suggests no validation, which means a malformed `extensions` value silently passes today and silently passes when v2 binds subkeys (because v1 already accepted it). A repo could commit `{"extensions": null}` or `{"extensions": [1,2,3]}` as a typo-bug and v1 readers green-light it. Forward-compat ergonomics: when v2 BINDS an extension namespace and the operator already has malformed `extensions` from v1's permissive era, what happens?
**Evidence:**
- v2 spec line 101: "Orca's reader IGNORES this key in v1; do not error on its presence."
- No type-check on `extensions` in v1
**Recommendation:** Add a sentence to line 101: "If `extensions` is present, it MUST be a JSON object (`dict`); other types raise `ContractError`. Subkey contents are ignored in v1 but the top-level shape is enforced now to keep the namespace usable in future schema versions." Cost: one type check at load time, no behavior change for well-formed contracts.

#### Summary

| Source | Resolved | Partial | Not Fixed | New |
|---|---|---|---|---|
| Round 1 (11) | 4 | 7 | 0 | — |
| Round 2 introduced | — | — | — | 7 |

The v2 revisions land most of the round-1 substance on paper but introduce or fail to close 7 followups: 2 HIGH (run_stage1 ripples, security warning lands in the wrong place), 4 MEDIUM (parser strictness vs claimed scope, untracked dot-dir scan ambiguity, union order vs framing, migration-strategy self-contradiction), 1 LOW (malformed `extensions` value). The Phase 1 docs amendment promised in the disposition table also hasn't been delivered to `2026-04-30-orca-worktree-manager-design.md` yet. None are blockers, but the run_stage1 caller-graph and the security-warning misplacement should be addressed before plan-writing — both will resurface during implementation otherwise. Recommend one more revision round addressing R2-NEW-2 (run_stage1 ripples), R2-NEW-3 (move warning into shim body), and a quick pass on R2-NEW-4 through R2-NEW-7 + the unfulfilled Phase 1 amendment, then ready.

### Round 3 - Author response

**Verdict:** all 7 round-2 new findings + 1 unfulfilled commitment addressed in spec v3 (commit follows).

| Finding | Severity | Resolution |
|---|---|---|
| R2-NEW-2 run_stage1 ripples | HIGH | Spec now enumerates the full delta: signature change (+ contract kwarg), manager.py:179 caller update via load_contract, test rewrite (test_explicit_symlink_paths_union_with_host_defaults + new test_contract_symlink_paths_join_union), Phase 1 line 196 amendment. Effort 0.25 → 0.5 days |
| R2-NEW-3 install-time warning lands wrong | HIGH | Warning moved into shim BODY (every-run); ORCA_SHIM_NO_PROMPT=1 bypass for CI; install-time warning kept as one-shot reminder but not the primary defense. Effort +0.1 days |
| R2-NEW-4 parser strict-pattern too narrow | MEDIUM | Tolerance list expanded: `[ ... ]` / `[[ ... ]]` / `test`, all `-e/-f/-d/-L` predicates, `ln -s/-sf/-snf/-sfn`, inline comments, blank lines, line continuations. Tokenization on normalized form. --help statement updated to reflect realistic scope |
| R2-NEW-5 untracked dot-dirs scan | MEDIUM | Spelled out: dot-dirs use `os.walk` with early-bail (catches untracked `.tools/` etc.); non-dot-dirs use `git ls-files`. Different rules for different signal classes |
| R2-NEW-6 union order contradicts framing | MEDIUM | Order swapped to host_layout → contract → worktrees.toml. Contract (team-shared baseline) now appears before local override entries; matches §"Goals" framing. Test description at line 438 updated |
| R2-NEW-7 schema migration self-contradictory | MEDIUM | Three explicit rules (additive = no bump; new required / removed / type change = bump v2; rename = bump + migrate verb). Decision tree now unambiguous |
| R2-NEW-1 malformed extensions value | LOW | extensions field doc tightened: top-level value MUST be JSON object if present; non-object types raise ContractError. Subkeys still ignored in v1 |
| Unfulfilled commitment: Phase 1 docs amendment | — | `2026-04-30-orca-worktree-manager-design.md:612` updated `after_create_script` → `init_script` with note explaining the rename. Phase 1 line 196 also updated for run_stage1 union semantics |

**Outstanding from review:** none. Spec v3 ready for plan-writing.
