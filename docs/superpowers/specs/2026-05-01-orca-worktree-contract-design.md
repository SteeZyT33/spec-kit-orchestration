# Orca Worktree Contract — Design

**Date:** 2026-05-01
**Status:** Design (Phase 2 follow-up to worktree manager)
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
| `schema_version` | int | yes | Must be `1`. Future versions trigger migration prompt. |
| `symlink_paths` | list[str] | yes (may be empty) | Repo-root-relative dir paths. Each is symlinked from primary checkout into each new worktree. |
| `symlink_files` | list[str] | yes (may be empty) | Repo-root-relative file paths. Same semantics, file granularity. |
| `init_script` | str or null | no | Repo-root-relative path to an executable script. Runs once after worktree creation. |

**Validation rules** (enforced by orca's reader; cmux shim is best-effort):
- All paths must be repo-root-relative; absolute paths or `..` traversal rejected (uses `orca.core.path_safety` Class A rules)
- `init_script`, when set, is checked for existence + executable bit at `wt new` time (Stage 2 invocation), NOT at contract-load time. This lets repos ship the contract before the script lands (CI bootstraps it during build).
- Bad schema (missing required field, wrong type, version mismatch) raises `ContractError` (a `ValueError` subclass). The orca CLI handler catches it and emits an `INPUT_INVALID` envelope with `exit_code=1`.

## Discovery (`orca-cli wt contract emit`)

Scans the repo and writes a proposed `.worktree-contract.json`. Operator reviews + commits.

**Heuristic:**
1. **Always include in `symlink_files`:** repo-root files matching `.env*` if present
2. **Always include in `symlink_paths`:** top-level dot-dirs that are
   - exists on disk (regardless of git status)
   - <5 MB total
   - contain only text-shaped content (extensions: `.md`, `.json`, `.yml`, `.yaml`, `.toml`, `.txt`, `.sh`, `.py`, `.js`, `.ts`)
   - NOT in the excluded-name list (`node_modules`, `__pycache__`, `.venv`, `target`, `dist`, `build`, `out`, `coverage`, `.pytest_cache`, `.next`, `.cache`)
3. **Always include in `symlink_paths`:** top-level non-dot-dirs that are tracked in git AND <50 MB AND not in the excluded-name list
4. **Skip:** anything covered by `host_layout.derive_host_paths()` — those auto-symlink in orca regardless. Specifically: `.specify/`, `specs/` (spec-kit), `docs/superpowers/` (superpowers), `openspec/` (openspec), `docs/orca-specs/` (bare). Contract should not duplicate them.
5. **Skip:** worktree dirs themselves — `.worktrees/`, `.orca/worktrees/`, anything matching `worktrees/*/`

**Output:** the JSON file plus stderr summary listing what was included AND what was skipped (with reason). Operator runs `git diff` to review, then commits.

**Flags:**
- `--dry-run` prints JSON to stdout without writing
- `--force` overwrites existing `.worktree-contract.json` (default: refuse)
- `--init-script PATH` points to an existing setup script
- `--max-dir-size <MB>` overrides 50 MB ceiling for non-dot dirs

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

- **Symlink lists are the union.** orca symlinks everything either source declares. Duplicates are deduped on path equality.
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

### Shim (Phase 2.0, ships with orca)

`orca-cli wt contract install-cmux-shim` writes `.cmux/setup`:

```bash
#!/usr/bin/env bash
# Generated by orca-cli wt contract install-cmux-shim
# Translates .worktree-contract.json into cmux's setup convention.
# Do not edit — re-run install-cmux-shim to refresh.
set -euo pipefail

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

**Parser strategy:** static parse, no execution. Match documented cmux patterns:

```bash
# Pattern 1 (env files)
for f in .env .env.local .env.secrets perf-lab.config.json; do
  [ -e "$REPO_ROOT/$f" ] && ln -sf "$REPO_ROOT/$f" "$f"
done

# Pattern 2 (shared dirs)
for d in specs .specify docs shared; do
  [ -e "$d" ] && [ ! -L "$d" ] && rm -rf "$d"
  [ -e "$REPO_ROOT/$d" ] && ln -sfn "$REPO_ROOT/$d" "$d"
done
```

Regex extracts the items between `for f in ... ; do` (env files) and `for d in ... ; do` (paths).

Build steps in the script (e.g., `go mod download`, `pip install -r requirements-dev.txt`) are preserved as the contract's `init_script`: parser writes a new `.worktree-contract/after_create.sh` containing the build steps with the symlink loops stripped, then sets `init_script` to point at it.

**Limitations** (documented in `--help`):
- Complex bash (functions, conditionals, non-standard symlink patterns) won't parse cleanly
- Operator gets a stderr warning naming the unparsed lines
- Refuses to overwrite an existing contract unless `--force`
- Not in scope: parsing arbitrary bash. Heuristic targets the documented cmux setup pattern; weird scripts get hand-migrated.

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

### Unit (~12 tests)

- `tests/core/worktrees/test_contract.py`:
  - schema validation (4-field shape)
  - schema_version mismatch raises
  - path traversal rejection (`..`, absolute paths)
  - missing required fields
  - optional `init_script` (null vs absent vs set)
  - merge_with_config: union semantics + dedup

- `tests/core/worktrees/test_emit.py`:
  - discovery against fixture repo (perf-lab-shaped: dot-dirs + non-dot-dirs)
  - openspec-shaped (skips `openspec/` per host_layout overlap)
  - bare repo (skips `docs/orca-specs/`)
  - excluded-name filter (`.venv`, `node_modules`, etc. excluded)
  - `--max-dir-size` honored
  - refuses to overwrite without `--force`

- `tests/core/worktrees/test_from_cmux.py`:
  - parses standard env-files loop
  - parses standard shared-dirs loop
  - extracts non-loop content into `init_script` body
  - warns on unparsed lines
  - refuses overwrite without `--force`

### Integration (~3 tests, gated `-m integration`)

- Round-trip: `wt contract emit` → `wt new` → assert all listed symlinks present in worktree
- Coexistence: `.worktree-contract.json` + `worktrees.toml` both present → union semantics verified end-to-end
- Shim: `wt contract install-cmux-shim` then run shim against a temp repo → assert symlinks created (without orca involved)

## Effort estimate

- Schema + reader (`contract.py` + tests): 0.25 days
- `wt contract emit` discovery: 0.5 days
- `wt contract from-cmux` parser: 0.5 days
- `wt contract install-cmux-shim` writer: 0.25 days
- orca `wt init` + Stage 1 reader integration: 0.25 days
- Tests + docs: 0.5 days
- Upstream cmux PR (optional, Phase 2.1, separate): ~0.5 days

**Total v2.0: ~2.25 days.** Phase 2.1 is an optional separate PR if cmux upstream cooperates.

## Cross-references

- Phase 1 worktree manager spec: `docs/superpowers/specs/2026-04-30-orca-worktree-manager-design.md`
- cmux source: `~/.cmux/cmux.sh`
- Reference perf-lab setup: `~/perf-lab/.cmux/setup`
- Path-safety contract (governs path validation): `docs/superpowers/contracts/path-safety.md`
