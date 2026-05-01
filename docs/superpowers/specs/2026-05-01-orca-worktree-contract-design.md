# Orca Worktree Contract — Design

**Date:** 2026-05-01
**Status:** Design v2 (post-cross-pass-review-r1; 11 findings addressed)
**Review:** `2026-05-01-orca-worktree-contract-review.md` round 1 surfaced 1 BLOCKER, 3 HIGH, 5 MEDIUM, 2 LOW; v2 below addresses all.
**Predecessors:**
- `docs/superpowers/specs/2026-04-30-orca-worktree-manager-design.md` §"Perf-lab compatibility" (lines 538-556) sketched the idea and deferred
- `~/.cmux/cmux.sh` — cmux's existing `.cmux/setup` convention (single hook, run unconditionally)
- `~/perf-lab/.cmux/setup` — reference operator-authored setup script

## Why this spec

Orca v1's worktree manager (`orca-cli wt`) is a standalone alternative to cmux: both manage git worktrees + tmux sessions, neither reads the other's state. Operators today choose one tool per repo. Repos like `perf-lab` ship a `.cmux/setup` script with hardcoded symlink loops + build steps; an orca user has to either re-author the same logic in `worktrees.toml` + `after_create` or accept missing symlinks.

The Phase 1 spec called out `.worktree-contract.json` as the bridge: a tool-neutral, four-field JSON declaring symlinks + bootstrap script. Both tools read it; both honor what they understand. v1 deferred it. v2 ships it.

## Scope

**In scope:**
- Schema definition (`.worktree-contract.json` at repo root, 4 fields)
- orca CLI: `wt contract emit / from-cmux / install-cmux-shim` subverbs
- Discovery heuristic for `wt contract emit`
- orca `wt init` + Stage 1 reader integration so the contract drives symlinks automatically
- cmux compatibility shim (Python-embedded bash that runs as `.cmux/setup`)
- Optional upstream PR to cmux/cmux for native contract support (Phase 2.1)

**Out of scope (v1 of this work):**
- Trust signing / SHA verification of `init_script`
- Per-tool extension blocks in the contract
- Multiple init-script stages
- Auto-discovery at runtime (only at `emit` authoring time)
- Plain `git worktree` shim (operators using bare git can call `init_script` manually post-`git worktree add`)

## Goals

A perf-lab operator can:
1. Run `orca-cli wt contract emit` once, get a populated `.worktree-contract.json` with sensible symlink defaults from a repo scan
2. Commit it
3. Use either `orca-cli wt new` OR `cmux new` against the same repo and get equivalent worktree state — same symlinks, same init script execution

A repo author can:
1. Ship a `.worktree-contract.json` in their repo
2. Tell users "use orca or cmux, both work"
3. Not maintain `.cmux/setup` separately if they want orca-only safety (TOFU + Stage 2/3/4)

## Non-goals

- Replace cmux. cmux's UX (interactive shell function, `cmux cd`, `cmux init` Claude-generation) is its differentiator. The contract just standardizes the shared subset.
- Orca's value-adds (TOFU trust ledger, 3-stage hooks, lifecycle event log) stay tool-specific. The contract is intentionally minimal.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Repo root: .worktree-contract.json (committed, team-shared)     │
│   {                                                              │
│     "schema_version": 1,                                         │
│     "symlink_paths":  [...],                                     │
│     "symlink_files":  [...],                                     │
│     "init_script":    "..."                                      │
│   }                                                              │
└──────────┬─────────────────────┬─────────────────────────────────┘
           │                     │
           ▼                     ▼
┌──────────────────────┐  ┌──────────────────────────────────────┐
│  orca-cli wt new     │  │  cmux new                            │
│   reads contract     │  │   runs .cmux/setup (shim translates  │
│   merges with        │  │   contract → symlinks + init script) │
│   worktrees.toml     │  │                                      │
│   applies symlinks   │  │                                      │
│   runs Stage 2       │  │                                      │
│   under TOFU         │  │                                      │
└──────────────────────┘  └──────────────────────────────────────┘
```

The contract is the source of truth for cross-tool symlink/init agreement. orca and cmux each layer their own opinions on top:
- orca: TOFU trust ledger gates `init_script`; Stage 1 auto-symlink also covers host_layout-derived dirs (.specify/, docs/superpowers/, etc.); Stages 3 + 4 hooks aren't part of the contract
- cmux: runs the shim's `.cmux/setup` directly (no trust); no per-stage lifecycle

## Schema

```json
{
  "schema_version": 1,
  "symlink_paths": ["specs", ".specify", "docs", "shared",
                    ".tools", ".omx", "agents", "skills", "templates"],
  "symlink_files": [".env", ".env.local", ".env.secrets",
                    "perf-lab.config.json"],
  "init_script": ".worktree-contract/after_create.sh"
}
```

**Field semantics:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | int | yes | Must be `1`. Future versions are additive-only by default (see §"Schema migration strategy"). |
| `symlink_paths` | list[str] | yes (may be empty) | Repo-root-relative dir paths. Each is symlinked from primary checkout into each new worktree. |
| `symlink_files` | list[str] | yes (may be empty) | Repo-root-relative file paths. Same semantics, file granularity. |
| `init_script` | str or null | no | Repo-root-relative path to an executable script. Runs once after worktree creation. |
| `extensions` | object | no | Reserved namespace for future per-tool extensions (e.g., `extensions.cmux.foo`, `extensions.mise.bar`). Orca's reader IGNORES the SUBKEYS of this dict in v1; the TOP-LEVEL value MUST be a JSON object if present (`extensions: {...}`). Other types (`extensions: 42`, `extensions: "foo"`, `extensions: null`, `extensions: [...]`) raise `ContractError`. Subkey contents are ignored in v1, but enforcing the top-level shape now keeps the namespace usable in future schema versions. |

**Naming note (Phase 1 reconciliation).** Phase 1's worktree-manager spec (line 612) promised the Phase 2 contract field as `after_create_script`. Phase 2 ships it as `init_script` — a deliberate rename for clarity (the contract's script is conceptually the "init" of a new worktree, not specifically tied to orca's Stage 2 hook nomenclature). Phase 1 only design-promised the schema; it did not ship a reader. Repos pre-authoring against the Phase 1 name need a one-line rename before this v2 lands. Phase 1's Perf-lab compatibility section will be amended in this PR's docs commit to reference the corrected field name.

**Schema migration strategy.** Three explicit rules:

1. **Adding a new optional top-level key does NOT bump `schema_version`.** v1 readers ignore unknown keys (per the "Unknown top-level keys" rule below); newer readers see and use them. Forward-compatible additive changes flow through without coordination.
2. **Adding a new required field, removing a field, or changing a field's type bumps `schema_version`** to 2 (or higher). v1 readers raise `ContractError` on `schema_version >= 2` rather than guessing.
3. **Renaming a field counts as breaking** and requires both a `schema_version` bump AND a `wt contract migrate` verb (out of scope for v2.0; tracked for a future spec).

In short: `schema_version` is a "breaking-changes-only counter." Additive fields are version-stable; v1 contracts and v2 readers coexist without operator action so long as no required field semantics change.

**Unknown top-level keys:** orca's v1 reader IGNORES top-level keys other than the five declared above (`schema_version`, `symlink_paths`, `symlink_files`, `init_script`, `extensions`). This guarantees forward-compat for repos that publish contracts targeting future schema generations.

**Validation rules** (enforced by orca's reader; cmux shim is best-effort):
- All paths must be repo-root-relative; absolute paths or `..` traversal rejected (uses `orca.core.path_safety` Class A rules)
- `init_script`, when set, is checked for existence + executable bit at `wt new` time (Stage 2 invocation), NOT at contract-load time. This lets repos ship the contract before the script lands (CI bootstraps it during build).
- Bad schema (missing required field, wrong type, version mismatch) raises `ContractError` (a `ValueError` subclass). The orca CLI handler catches it and emits an `INPUT_INVALID` envelope with `exit_code=1`.

## Discovery (`orca-cli wt contract emit`)

Scans the repo and writes a proposed `.worktree-contract.json`. Operator reviews + commits.

**Heuristic:**
1. **Always include in `symlink_files`:** repo-root files matching `.env*` that are *untracked* in git
2. **Always include in `symlink_paths`:** top-level dot-dirs that are
   - exists on disk
   - *untracked* in git (no `git ls-files` matches under the dir)
   - <5 MB total (via `os.walk` early-bail)
   - NOT in the excluded-name list (`node_modules`, `__pycache__`, `.venv`, `target`, `dist`, `build`, `out`, `coverage`, `.pytest_cache`, `.next`, `.cache`)
3. **Always include in `symlink_paths`:** top-level non-dot-dirs that are *untracked* in git AND <50 MB AND not in the excluded-name list
4. **Skip:** anything covered by `orca.core.worktrees.auto_symlink.derive_host_paths(host_system)` — those auto-symlink in orca regardless. Specifically: `.specify/`, `specs/` (spec-kit), `docs/superpowers/` (superpowers), `openspec/` (openspec), `docs/orca-specs/` (bare). Contract should not duplicate them.
5. **Skip:** worktree dirs themselves — `.worktrees/`, `.orca/worktrees/`, anything matching `worktrees/*/`

**Tracked-content rule (uniform across rules 1, 2, 3):** any path with tracked content is git's job. Symlinking it would shadow the per-branch checkout and defeat the purpose of git worktrees. This is enforced by a single `git ls-files -z -- <path>` check per candidate; a single tracked file under a candidate is sufficient to skip it. (Inverted from the original spec in the 2026-05-01 dogfood-blockers fix — the prior "tracked + <50MB" rule for non-dot-dirs proposed `src/`, `tests/`, `specs/` as symlink candidates on this very repo.)

**Output:** the JSON file plus stderr summary listing what was included AND what was skipped (with reason). Operator runs `git diff` to review, then commits.

**Flags:**
- `--dry-run` prints JSON to stdout without writing
- `--force` overwrites existing `.worktree-contract.json` (default: refuse)
- `--init-script PATH` points to an existing setup script
- `--max-dir-size <MB>` overrides 50 MB ceiling for non-dot dirs

**Scan budget (monorepo handling):**

After the tracked-content gate filters out git-owned dirs (which is fast: `git ls-files` is O(matched-files), bounded by `.gitignore`), only untracked candidates remain. Size-cap measurement uses `os.walk` with early-bail since untracked content is by definition not in git's index:

- **Dot-dirs (rule 2):** `os.walk` with **early-bail at 5 MB**.
- **Non-dot-dirs (rule 3):** `os.walk` with **early-bail at 50 MB** (configurable via `--max-dir-size`).
- **Bail early on size:** stop summing once a directory exceeds its cap; mark it `skipped: too large` and continue. Do not walk the full subtree just to confirm.
- **Permission-denied subdirs:** log to stderr, skip the dir, continue. Never fail the whole `emit` invocation on a single permission error.
- **Progress feedback:** when total scan exceeds 2 seconds wall-clock, print `Scanning <dir>... (N candidates examined)` to stderr every 2 seconds.
- **Operator expectation:** `emit` is a one-shot authoring command, not on the hot path. 5-10s wall-clock on a large monorepo is acceptable; >30s indicates a pathological case (hand-edit the contract instead).

The discovery errs toward "include this candidate, let the operator delete it" rather than "skip silently." Better UX than guessing wrong.

## Orca integration (reader)

### `wt init` (boot a new repo)

1. If `.worktree-contract.json` exists, parse it and seed `worktrees.toml` with its `symlink_paths` + `symlink_files`. Add a comment: `# generated from .worktree-contract.json`.
2. If `init_script` is set, write a default `.orca/worktrees/after_create` that exec's the contract's script:
   ```bash
   #!/usr/bin/env bash
   exec "$ORCA_REPO_ROOT/.worktree-contract/after_create.sh"
   ```
   This puts orca's TOFU trust gate around the contract script.
3. If contract absent, fall back to existing `wt init` behavior (host_layout-derived defaults only).

### `wt new` Stage 1 (every worktree creation)

Existing Stage 1 already runs symlinks from `worktrees.toml` + host_layout auto-derive.

**Plus:** if `.worktree-contract.json` exists AND its symlink lists are NOT already represented in `worktrees.toml` (operator skipped `wt init`), additionally apply the contract's symlinks. This makes the contract effective even in repos where `wt init` was never run.

### Conflict resolution: contract + worktrees.toml both present

- **Symlink lists are the union, with deterministic order.** orca symlinks everything either source declares.

  **Phase 1 implementation change required (full ripple list):**
  1. `auto_symlink.run_stage1()` at `src/orca/core/worktrees/auto_symlink.py:44` currently does `paths = explicit if explicit else derive_host_paths(host_system)` (explicit OVERRIDES host defaults). This Phase 2 work changes the function signature to accept a new `contract: ContractData | None = None` kwarg and the body to ALWAYS union:
     ```python
     paths = list(dict.fromkeys(
         derive_host_paths(host_system)
         + (contract.symlink_paths if contract else [])
         + cfg.symlink_paths
     ))
     ```
     Order: host defaults first, then **contract** (team-shared baseline appears before local overrides for `wt config` readability and to honor §"Goals" framing of contract as authoritative), then `worktrees.toml` (operator's local additions). `dict.fromkeys` preserves first-insertion order so duplicates land at their first appearance.
  2. `manager.py:179` is the only `run_stage1` caller. Update it to load contract via `load_contract(self.repo_root)` (returning None if absent) and pass it through to `run_stage1`. The Manager itself does not need a contract attribute; the load happens at hook-execution time so the file's mtime is fresh.
  3. The shipped test `tests/core/worktrees/test_auto_symlink.py:50-58` (`test_explicit_symlink_paths_override_host_defaults`) asserts the OLD override semantics. Rename to `test_explicit_symlink_paths_union_with_host_defaults` and rewrite to assert union: `cfg.symlink_paths=["custom"]` + `host_system="spec-kit"` produces a worktree with BOTH `custom/` AND `.specify/` symlinked. Plus a new test `test_contract_symlink_paths_join_union` exercising the contract third-arg path.
  4. Phase 1's "explicit list = override" line in `2026-04-30-orca-worktree-manager-design.md` (around line 196) gets amended to "explicit list = additive union with host defaults."
- **`init_script` becomes orca's Stage 2 hook content** — `wt init` exec's it from `.orca/worktrees/after_create`. If the operator has hand-authored a different `.orca/worktrees/after_create` (orca-native, not contract-derived), that file wins as-is. The runtime always invokes `.orca/worktrees/after_create`; the contract is only the SOURCE during `wt init`. This keeps Stage 2 invocation path uniform regardless of contract presence.
- **Other `worktrees.toml` fields** (`tmux_session`, `default_agent`, `lane_id_mode`, etc.) have no contract analog and pass through unmodified.

### New module

`src/orca/core/worktrees/contract.py`:

```python
@dataclass(frozen=True)
class ContractData:
    schema_version: int
    symlink_paths: list[str]
    symlink_files: list[str]
    init_script: str | None


class ContractError(ValueError):
    """Raised on contract schema violation."""


def load_contract(repo_root: Path) -> ContractData | None:
    """Read .worktree-contract.json; return None if absent, raise on error."""

def merge_with_config(
    contract: ContractData | None, cfg: WorktreesConfig
) -> WorktreesConfig:
    """Return cfg with contract's symlinks unioned in."""
```

Tested against fixtures.

## cmux compatibility

### Security model (read first)

The orca reader runs `init_script` through orca's TOFU trust ledger. The cmux shim runs `init_script` directly with no trust check — by design, because cmux's own trust model is "none." Operators using cmux as their primary tool inherit cmux's behavior, not orca's.

**Consequence:** for a cloned hostile repo, `cmux new` via the shim is RCE-equivalent on first checkout. `orca-cli wt new` would prompt under TOFU. This asymmetry is intentional (the shim cannot run orca's interactive prompt without becoming a Python program in disguise) but it IS a real foot-gun for operators who switch tools.

**Mitigation (revised — install-time warning was insufficient).** The threat fires on `cmux new` against a freshly-cloned hostile repo, NOT during `install-cmux-shim` on the operator's own repo. So the warning must live in the shim BODY — every-run — not at install time. The shim prints to stderr on every invocation and pauses for confirmation when stdin is a tty:

```bash
echo "WARNING: cmux shim runs init_script with no trust check." >&2
echo "  Hostile init_scripts in cloned repos run as your user." >&2
if [ -t 0 ] && [ "${ORCA_SHIM_NO_PROMPT:-0}" != "1" ]; then
    echo -n "  Press ENTER to continue, Ctrl-C to abort: " >&2
    read -r _
fi
```

Operators in CI / unattended scripts set `ORCA_SHIM_NO_PROMPT=1` to bypass. README + `wt contract install-cmux-shim --help` document the asymmetry prominently. The install-time warning is ALSO printed (one-shot reminder when the shim is laid down) but is not the primary defense.

**Stricter shim variant** (out of scope for v2.0; tracked as future work): a strict shim that invokes `orca-cli wt contract trust-check $INIT_SCRIPT` before exec, bridging the TOFU ledger. Operators can opt in via `install-cmux-shim --strict`. This is left out of v2.0 to ship the bridge fast; v2.0's lenient-with-runtime-warning is the documented baseline.

### Shim runtime requirements

The shim is bash-with-embedded-Python. Requirements:
- `python3` ≥ 3.6 on PATH (the embedded heredoc uses f-strings)
- standard `git` (for `git rev-parse --git-common-dir`)

cmux itself is pure bash + git; the shim raises that floor. On systems without `python3` (minimal container images, some macOS configs where only `python` is aliased to Python 3) the shim fails fast at top with a clear error.

The shim guards this:
```bash
command -v python3 >/dev/null 2>&1 || {
    echo "orca-cli wt contract shim requires python3 on PATH" >&2
    exit 1
}
```

Tracked alternative: rewrite the shim's parser in pure bash + `jq`. Not adopted in v2.0 because (a) `jq` is not universally pre-installed either, (b) bash JSON parsing without `jq` or `python` is its own nightmare. Operators on minimal images can hand-author `.cmux/setup` instead of using the shim.

### Shim (Phase 2.0, ships with orca)

`orca-cli wt contract install-cmux-shim` writes `.cmux/setup`:

```bash
#!/usr/bin/env bash
# Generated by orca-cli wt contract install-cmux-shim
# Translates .worktree-contract.json into cmux's setup convention.
# Do not edit — re-run install-cmux-shim to refresh.
set -euo pipefail

command -v python3 >/dev/null 2>&1 || {
    echo "orca-cli wt contract shim requires python3 on PATH" >&2
    exit 1
}

# Trust warning (every invocation; CI bypasses via ORCA_SHIM_NO_PROMPT=1).
echo "WARNING: cmux shim runs init_script with no trust check." >&2
echo "  Hostile init_scripts in cloned repos run as your user." >&2
if [ -t 0 ] && [ "${ORCA_SHIM_NO_PROMPT:-0}" != "1" ]; then
    echo -n "  Press ENTER to continue, Ctrl-C to abort: " >&2
    read -r _
fi

REPO_ROOT="$(git rev-parse --git-common-dir | xargs dirname)"
CONTRACT="$REPO_ROOT/.worktree-contract.json"
if [[ ! -f "$CONTRACT" ]]; then
    echo ".worktree-contract.json not found; cmux shim is a no-op" >&2
    exit 0
fi

python3 - "$CONTRACT" "$REPO_ROOT" <<'PY'
import json, os, sys
contract_path, repo_root = sys.argv[1], sys.argv[2]
try:
    with open(contract_path) as f:
        c = json.load(f)
except Exception as e:
    print(f"contract parse failed: {e}", file=sys.stderr)
    sys.exit(0)

for rel in c.get("symlink_paths", []) + c.get("symlink_files", []):
    src = os.path.join(repo_root, rel)
    if not os.path.exists(src):
        continue
    if os.path.lexists(rel) and not os.path.islink(rel):
        # Refuse to clobber real content
        continue
    if os.path.lexists(rel):
        os.unlink(rel)
    os.makedirs(os.path.dirname(rel) or ".", exist_ok=True)
    os.symlink(src, rel)
PY

INIT_SCRIPT_REL="$(python3 -c "import json; print(json.load(open('$CONTRACT')).get('init_script') or '')")"
if [[ -n "$INIT_SCRIPT_REL" ]]; then
    INIT_SCRIPT="$REPO_ROOT/$INIT_SCRIPT_REL"
    if [[ -x "$INIT_SCRIPT" ]]; then
        "$INIT_SCRIPT"
    fi
fi
```

cmux runs `.cmux/setup` automatically on `cmux new`; the shim translates the contract at runtime. ~30 LOC of bash + embedded Python (no extra deps).

### Upstream PR (Phase 2.1, optional)

Send PR to `craigsc/cmux` adding native `.worktree-contract.json` support. cmux's `_cmux_run_setup` falls back to reading the contract when no `.cmux/setup` exists. Removes the shim. cmux maintainers may not accept; the shim is the permanent fallback if they don't.

## Migration helpers

### `orca-cli wt contract from-cmux`

Reads existing `.cmux/setup`, parses common patterns, writes equivalent `.worktree-contract.json`.

**Parser strategy:** static parse, no execution. **Strict pattern-match against the documented cmux setup template only:**

```bash
# Pattern 1 (env files) — REQUIRED EXACT SHAPE
for f in <bareword> <bareword> ... ; do
  [ -e "$REPO_ROOT/$f" ] && ln -sf "$REPO_ROOT/$f" "$f"
done

# Pattern 2 (shared dirs) — REQUIRED EXACT SHAPE
for d in <bareword> <bareword> ... ; do
  [ -e "$d" ] && [ ! -L "$d" ] && rm -rf "$d"
  [ -e "$REPO_ROOT/$d" ] && ln -sfn "$REPO_ROOT/$d" "$d"
done
```

The parser REQUIRES:
- The loop iterable is a literal list of bareword tokens (no `$(...)`, no `${...}`, no quoted strings, no glob expansions, no array references)
- The loop body's gist matches the documented symlink-or-replace shape, with these tolerated variations:
  - `[ ... ]` OR `[[ ... ]]` OR `test ...` (any of the three test forms)
  - `-e`, `-f`, `-d`, or `-L` predicates
  - `ln -s`, `ln -sf`, `ln -snf`, `ln -sfn` (any sensible flag combination)
  - Inline `# comments` and blank lines inside the loop body
  - Backslash line continuations (`\\\n`)
- Whitespace and indentation are ignored; tokenization happens on a normalized form

Loops that don't match (functions, conditionals around the symlink call, sourced helpers, `find`-fed iterables, LLM-generated freeform bash with arbitrary control flow, etc.) are NOT extracted. Their line ranges go to stderr: `cmux setup line N-M: cannot extract symlinks; hand-migrate this block.`

**Realistic scope statement (in `--help`):**
> Handles hand-authored cmux setups matching the documented template, including idiomatic variations (`[[ ... ]]`, `test`, comments, line continuations). LLM-generated setups produced by `cmux init` use freeform bash (per `cmux.sh:783-820`) and usually require hand migration. The parser refuses to extract symlinks from non-matching shapes rather than producing wrong output.

**Build steps preservation:** non-loop content (e.g., `go mod download`, `pip install -r requirements-dev.txt`) is preserved as the contract's `init_script`. The parser writes a new `.worktree-contract/after_create.sh` containing the build steps with the matched symlink loops stripped, then sets `init_script` to point at it. If no build steps remain after stripping, `init_script` is omitted from the generated contract.

**Test coverage** (per §"Testing"):
- Fixture A: hand-authored perf-lab-style setup matching the strict shape → parser extracts cleanly, no warnings
- Fixture B: LLM-generated cmux setup with conditionals and `find` → parser refuses both loops, emits warnings, build steps preserved
- Fixture C: setup with `for d in $(find ...); do ...` → parser refuses (non-bareword iterable), build steps preserved

**Other limitations** (in `--help`):
- Refuses to overwrite an existing contract unless `--force`
- Not in scope: parsing arbitrary bash. The 80% case (hand-authored setups matching the documented template) works; the 20% case (LLM-generated) is hand-migrated.

### `orca-cli wt contract install-cmux-shim`

See cmux compatibility section above. Refuses to overwrite existing `.cmux/setup` unless `--force`.

## CLI surface

```text
orca-cli wt contract emit             [--dry-run] [--force]
                                      [--init-script PATH]
                                      [--max-dir-size MB]
orca-cli wt contract from-cmux        [--cmux-script PATH] [--force]
orca-cli wt contract install-cmux-shim [--force]
```

Three new subverbs on the existing `wt contract` parent verb. Each parses argv via argparse with `exit_on_error=False` per the existing CLI pattern; emits Result envelopes on stdout.

## Testing

### Test fixture provenance

All fixtures are programmatically constructed via `pytest.fixture` in `tests/core/worktrees/conftest.py` using `tmp_path`. A builder helper:

```python
def make_repo(tmp_path: Path, *, host_system: str = "bare",
              top_level_paths: list[str] | None = None,
              top_level_files: list[str] | None = None) -> Path:
    """Create a tmp git repo populated with the requested signal files
    and host-system markers (.specify/, docs/superpowers/, openspec/, etc.).
    Returns the repo root."""
```

No on-disk fixture trees committed under `tests/fixtures/`; all test repos are ephemeral. This keeps the test surface small and avoids drift with `host_layout` definitions.

### Unit (~14 tests)

- `tests/core/worktrees/test_contract.py`:
  - schema validation (5-field shape including `extensions`)
  - schema_version mismatch raises `ContractError`
  - path traversal rejection (`..`, absolute paths)
  - missing required fields
  - optional `init_script` (null vs absent vs set)
  - unknown top-level keys ignored (forward-compat)
  - `extensions` key ignored by reader

- `tests/core/worktrees/test_emit.py`:
  - discovery against perf-lab-shaped fixture (dot-dirs + non-dot-dirs)
  - openspec-shaped (skips `openspec/` per host_layout overlap)
  - bare repo (skips `docs/orca-specs/`)
  - excluded-name filter (`.venv`, `node_modules`, etc.)
  - `--max-dir-size` honored
  - early-bail on size cap (don't walk full subtree)
  - permission-denied subdir → log + skip + continue
  - refuses to overwrite without `--force`

- `tests/core/worktrees/test_from_cmux.py`:
  - **Fixture A** (hand-authored perf-lab-style): parses standard env-files loop + shared-dirs loop, no warnings
  - **Fixture B** (LLM-generated freeform bash): parser refuses both loops, emits stderr warnings naming line ranges, build steps preserved in `init_script`
  - **Fixture C** (`for d in $(find ...); do ...`): parser refuses non-bareword iterable
  - extracts non-loop content into `init_script` body
  - refuses overwrite without `--force`

### Integration (~3 tests, gated `-m integration`)

- Round-trip: `wt contract emit` → `wt new` → assert all listed symlinks present in worktree (host defaults + contract entries unioned)
- Coexistence: `.worktree-contract.json` + `worktrees.toml` both present → union semantics verified end-to-end (order: host_layout → contract → worktrees.toml via `dict.fromkeys`)
- Shim: `wt contract install-cmux-shim` then run shim against a temp repo → assert symlinks created (without orca involved); `python3` guard fires when `python3` is unset (skipped on hosts where `python3` is unavailable)

## Effort estimate (revised post-review-r1)

- Schema + reader (`contract.py` + tests): 0.25 days
- `wt contract emit` discovery + scan-budget guards (early-bail, permission handling, progress feedback): 0.5 days *(unchanged)*
- `wt contract from-cmux` strict-pattern parser + 3 fixture variants: 0.5 days *(scope tightened, test count up)*
- `wt contract install-cmux-shim` writer + python3 guard + warning print: 0.25 days *(unchanged)*
- orca `wt init` + Stage 1 reader integration: 0.25 days *(unchanged)*
- **`run_stage1` change to union semantics + signature change + caller wiring + test rewrite + Phase 1 docs amendment**: 0.5 days *(revised from 0.25 per round-2 R2-NEW-2; full ripple list now spec'd)*
- **Cmux shim runtime trust warning + ORCA_SHIM_NO_PROMPT + tests**: 0.1 days *(new from round-2 R2-NEW-3)*
- Tests + docs (14 unit + 3 integration; conftest builder helper): 0.5 days
- Upstream cmux PR (optional, Phase 2.1, separate): ~0.5 days

**Total v2.0: ~2.85 days** (revised from 2.5; +0.25 for run_stage1 ripples + 0.1 for shim warning). Phase 2.1 is an optional separate PR if cmux upstream cooperates.

## Cross-references

- Phase 1 worktree manager spec: `docs/superpowers/specs/2026-04-30-orca-worktree-manager-design.md`
- cmux source: `~/.cmux/cmux.sh`
- Reference perf-lab setup: `~/perf-lab/.cmux/setup`
- Path-safety contract (governs path validation): `docs/superpowers/contracts/path-safety.md`
