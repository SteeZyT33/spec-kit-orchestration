# Orca Worktree Manager — Design

**Date:** 2026-04-30
**Status:** Design v2 (post-brainstorm, post-cross-pass-review-r1)
**Review:** `2026-04-30-orca-worktree-manager-review-spec.md` round 1 surfaced 16 findings; v2 below addresses all 3 blockers + 7 highs + 4 mediums + 2 lows.
**Predecessors:**
- `docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md` (v1 north-star)
- `docs/superpowers/specs/2026-04-29-orca-spec-015-brownfield-adoption-design.md` (host_layout adapter, manifest)
- `docs/superpowers/contracts/path-safety.md` (path validation contract)
- cmux (`~/.cmux/cmux.sh`) — reference UX for opinionated worktree management
- Symphony (`~/symphony/`) — reference design for lifecycle hooks + observability

## Why this spec

Orca currently READS legacy worktree metadata (`.orca/worktrees/registry.json`) via `sdd_adapter._load_worktree_lanes` but does not CREATE worktrees. Operators today either run plain `git worktree add` (lossy: no symlinks, no agent launch, no lane sidecar) or use cmux (good UX but redundant with orca's adoption manifest, hooks duplicate orca's host_layout knowledge, no integration with `flow-state-projection` / `worktree-overlap-check`).

This spec adds an opinionated, tmux-mediated worktree manager to orca: `orca-cli wt <verb>`. It absorbs cmux's UX, layers Symphony's 3-stage hook + lifecycle-event pattern, and integrates with the existing adoption manifest + flow-state machinery so "create a lane" becomes one command that produces a fully wired workspace.

## Scope

In scope:
- CLI verbs: `wt new`, `wt start`, `wt cd`, `wt ls`, `wt merge`, `wt rm`, `wt init`, `wt config`, `wt version`, `wt doctor`
- Three-stage hook lifecycle (auto-symlink → `after_create` → `before_run`; `before_remove` on teardown)
- tmux session/window management with optional agent launch (claude / codex / none)
- Configuration via committed `[worktrees]` block in `.orca/adoption.toml` + gitignored `.orca/worktrees.local.toml` overrides
- Sidecar metadata per lane + registry index (backward-compatible with legacy schema)
- Lifecycle event log (`events.jsonl`) for observability
- Cross-platform: Linux, macOS, WSL native; Windows native with `--no-tmux` implicit

Out of scope (v1):
- Background cleanup daemon (operator runs `wt doctor --reap`)
- Multi-repo orchestration
- Remote / SSH workspaces
- Container or chroot isolation beyond git worktrees
- Slash command wrappers (CLI only)
- New TUI views (existing `flow-state-projection` consumers gain lane events but no new screens)
- Hook templating DSL (bash only)
- Auto-rebase on reattach
- Windows native tmux integration
- Shell completion script generation (`wt completion bash|zsh|fish`) — tracked as Phase 2; v1 documents that operators type branch names to `wt cd` manually
- `.worktree-contract.json` cross-tool schema reader in `wt init` — tracked as Phase 2 (see Perf-lab compatibility)
- Auto-walking monorepo `apps/*` / `packages/*` for `wt init` — v1 only walks top-level signal files

## Goals

A third party with a manifest-adopted orca install can run `orca-cli wt new <branch>` and end up in a tmux window cd'd into a fully wired worktree with the agent of their choice running. Removal is one command. State is observable. The same primitives compose with cmux or plain `git worktree` for operators who don't want orca's full opinions.

## Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│ orca-cli wt <verb>                                              │
│    new | start | cd | ls | merge | rm | init | config | doctor  │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ src/orca/core/worktrees/                                        │
│   manager.py        — orchestrates create/remove/list           │
│   layout.py         — base path + lane-id resolution            │
│   config.py         — adoption.toml + worktrees.local.toml merge │
│   setup_hook.py     — auto-symlink + custom-script execution    │
│   tmux.py           — tmux subprocess wrapper                   │
│   registry.py       — sidecar + registry.json + events.jsonl    │
│   identifiers.py    — lane-id sanitization (path-safety Class D) │
│   protocol.py       — WorktreeManager Protocol                  │
└────────────┬────────────────────────────────────────────────────┘
             │  reads/writes
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ .orca/                                                          │
│   adoption.toml          [worktrees] section (committed)        │
│   worktrees.local.toml   personal overrides (gitignored)        │
│   worktrees/                                                    │
│     <lane-id>.json       sidecar per lane                       │
│     registry.json        active-lane index (legacy-compatible)  │
│     events.jsonl         lifecycle event log                    │
│     after_create         hook (created by `wt init`)            │
│     before_run           hook (optional)                        │
│     before_remove        hook (optional)                        │
└────────────┬────────────────────────────────────────────────────┘
             │  drives
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ git worktree + tmux                                             │
│ <repo>/.orca/worktrees/<lane-id>/   ← actual worktree           │
│ tmux session "orca", window <lane-id>                           │
└─────────────────────────────────────────────────────────────────┘
```

The manager, tmux helper, and setup-hook runner are **decoupled**:

- `manager.create()` produces a worktree with no tmux requirement
- `tmux.spawn_window()` attaches to an existing worktree without manager
- `registry.write()` is the convergence point both code paths emit to
- `setup_hook.run()` is opt-out via `--no-setup`

This lets operators compose: pure worktree (`--no-tmux`), pure tmux on existing worktree, or full opinionated flow.

## CLI verb surface

```text
orca-cli wt new <branch> [--from <base>] [--feature <id>] [--lane <name>]
                         [--agent claude|codex|none] [--no-tmux] [--no-setup]
                         [-p <prompt>] [-- <agent-args...>]

orca-cli wt start <branch> [--agent claude|codex|none] [-p <prompt>]
                           [--rerun-setup]

orca-cli wt cd [<branch-or-lane-id>]     # prints absolute path; no
                                          # arg = repo root (primary
                                          # checkout); arg accepts
                                          # EITHER a branch name OR
                                          # a lane-id (registry-aware
                                          # resolver tries lane-id
                                          # first, falls back to
                                          # branch). Operator wraps
                                          # in $(...) to actually cd.
orca-cli wt ls [--json] [--all]
orca-cli wt merge [<branch>] [--into <target>] [--strategy ...]
orca-cli wt rm [<branch>] [--all] [-f] [--keep-branch]
orca-cli wt init [--replace]             # generates after_create from repo
orca-cli wt config [<key>] [<value>]     # read/write effective config
orca-cli wt version
orca-cli wt doctor [--reap [-y]]
```

### Idempotency state machine

`wt new <branch>` decisions across the (branch-exists, worktree-exists, sidecar-exists, registry-entry-exists) state cube. "exists" for branch means `git show-ref refs/heads/<branch>`; for worktree means it appears in `git worktree list`; for sidecar means `<lane-id>.json` is present; for registry means the lane is in `lanes`.

| branch | worktree | sidecar | registry | Action |
|---|---|---|---|---|
| no | no | no | no | Happy path: create worktree + branch from `--from`, write sidecar + registry, run hooks. |
| yes | no | no | no | Branch exists locally but no worktree (operator did `git checkout -b foo` previously). Refuse with `INPUT_INVALID`; recommend `wt new <branch> --from <branch>` (which is a no-op tautology) or `--reuse-branch` to attach. |
| yes | yes | no | no | Worktree exists at the lane-id-derived path but orca has no record (e.g., operator ran `git worktree add` directly). Adopt: write sidecar + registry, run hooks. Print "adopted existing worktree." |
| yes | yes (different path) | no | no | Worktree exists but at a different path than `<base>/<lane-id>/`. Refuse with `INPUT_INVALID`; print the existing path and recommend `wt rm` first or `wt adopt --path <existing>` (out of scope v1). |
| yes | yes | yes | yes | Fully registered. Idempotent attach: re-run Stage 3 (`before_run`) hook, ensure tmux window, switch focus. |
| yes | no | yes | yes | Sidecar/registry stale: worktree was force-removed externally. Clean stale entries; if `--reuse-branch`: recreate worktree from existing branch. Else: refuse with hint. |
| no | no | yes | yes | Sidecar without branch (operator deleted branch + worktree externally, sidecar orphaned). Auto-clean sidecar + registry. Recreate branch only if `--recreate-branch` is passed; otherwise exit with hint. |
| any | any | mismatch | any | Sidecar's `branch` field disagrees with `--branch` arg (e.g., operator created a different branch with the same lane-id). Refuse with `INPUT_INVALID`; recommend `wt rm <existing-lane-id>` first. |

**Row 6 vs row 7 rationale.** Both rows have stale sidecar+registry. The difference: row 6 still has a branch (operator's work-in-progress, branch is the canonical thing to preserve); row 7 has neither branch nor worktree (operator already discarded the work, sidecar is pure leftover). Row 6 refuses without `--reuse-branch` because we don't want to silently re-attach to a branch the operator may have force-removed for a reason. Row 7 silently auto-cleans the sidecar/registry but **also requires `--recreate-branch`** to actually recreate the branch — recreating a branch the operator deleted yesterday surprises them. Without `--recreate-branch`, row 7 cleans the stale sidecar+registry and exits with a hint to pass the flag (or use `wt new` with a fresh branch name).

`--reuse-branch` flag opts into adopting an existing branch into a new worktree (`git worktree add <path> <branch>` without `-b`). Without it, branch-exists-without-worktree is a refusal.

`--recreate-branch` flag opts into recreating a previously-deleted branch (used in row 7).

`wt rm` short-circuits:
- No-op if `<lane-id>` isn't in registry AND no sidecar exists
- If sidecar exists but worktree doesn't: clean sidecar + registry; skip hook
- If worktree exists but sidecar doesn't: refuse unless `--force` (we don't want to clobber operator's external worktree)

`wt start <branch>`:
- Refuse if no sidecar/registry entry — operator must `wt new` first
- Recreate tmux session/window if missing
- Re-run Stage 3 hook
- Re-run Stage 2 hook only if `--rerun-setup` AND sidecar's `setup_version` differs from current `after_create` SHA

## Classification

`wt` is a **utility subcommand**, not a v1 capability. It does NOT appear in `installed_capabilities` (per `2026-04-29-orca-spec-015-brownfield-adoption-design.md` line 124-131), does NOT have a `contracts/capabilities/wt.json` schema, and is NOT bound by the data-shape commitments in `2026-04-26-orca-toolchest-v1-design.md`. It does emit JSON via `wt ls --json` and `wt config --json`; those shapes are committed below in §"JSON output shapes".

## Hard prerequisite: path-safety consolidation

This spec **depends on** `orca.core.path_safety` from `2026-04-30-orca-path-safety-consolidation-design.md`. Path-safety consolidation MUST land first (or as the lead commit of this PR). The earlier "ships inline if needed" hedge is removed. The 5-day estimate below assumes the shared module exists.

## Configuration schema

### Committed: `.orca/worktrees.toml` (sibling of adoption.toml)

`[worktrees]` lives in its own file rather than `adoption.toml`. Adoption.toml is set-once policy read by `orca-cli apply`; worktrees.toml is runtime config read by every `wt new`. Co-locating them would force every worktree edit to mutate the manifest and entangle `wt config` with `orca-cli apply --revert`. Both files are committed; only `.orca/worktrees.local.toml` is gitignored.

**Adoption-flow integration.** `orca-cli adopt` defers worktree configuration. `orca-cli apply` runs `wt init` automatically when `[orca] enabled_features` includes `"worktrees"` (default-on for new adoptions; opt-in via `orca-cli adopt --enable-worktrees=false` to skip). `wt init` in this mode is non-interactive (uses defaults + repo-detection); operators can re-run `wt init --replace` interactively after adoption.

**Doctor coverage.** `orca-cli doctor` (run as final step of `orca-cli apply` per spec 015 §"Doctor handoff") gains a worktree-config check: if `[orca] enabled_features` includes `"worktrees"` but `.orca/worktrees.toml` is missing, surface as a warning with hint to run `wt init`.

**Lazy fallback.** `wt new` against a repo with no `worktrees.toml` auto-generates one with defaults (silent, on-the-fly) so first-time use doesn't require an explicit `wt init`. `wt config` shows that the file is auto-generated until first explicit edit.

```toml
[worktrees]
schema_version = 1

# Where worktrees live. Configurable; ".orca/worktrees" is the opinionated default.
# `base` controls only the checkout location; orca's worktree state (registry,
# sidecars, events, locks, hook scripts) always lives at `<repo>/.orca/worktrees/`
# regardless of this setting.
base = ".orca/worktrees"

# Lane-id derivation:
#   "branch" — sanitized branch name (cmux-style)
#   "lane"   — <feature>-<short-name> (Orca-style)
#   "auto"   — lane mode if both --feature and --lane are passed; else branch mode
lane_id_mode = "auto"

# Auto-symlinks. Empty list = derive from host.system. Explicit list = additive union with host defaults (changed in Phase 2 contract spec).
symlink_paths = []
symlink_files = [".env", ".env.local", ".env.secrets"]

# Hook script paths (relative to base directory).
after_create_hook  = "after_create"
before_run_hook    = "before_run"
before_remove_hook = "before_remove"

# tmux integration.
tmux_session  = "orca"     # plain string, or template "orca-{repo}"
default_agent = "claude"   # claude | codex | none

[worktrees.agents]
claude = "claude --dangerously-skip-permissions"
codex  = "codex --yolo"
```

### Local override: `.orca/worktrees.local.toml`

Gitignored on adoption. Same schema; deep-merges over committed values, last-writer wins.

```toml
[worktrees]
base = "/home/me/scratch-worktrees"
default_agent = "codex"
tmux_session = "work-{repo}"

[worktrees.env]
EXTRA_PATH = "/opt/local/bin"
```

### Auto-derived symlinks per `host.system`

| `host.system` | Auto-added symlinks |
|---|---|
| `spec-kit` | `.specify/`, `specs/` |
| `superpowers` | `docs/superpowers/` |
| `openspec` | `openspec/` |
| `bare` | `docs/orca-specs/` |

Plus `host.constitution_path` and `host.agents_md_path` if set in the manifest.

## Hook lifecycle

Three optional hooks, executed in sequence after the auto-symlink layer.

### Stage 1: Auto-symlink (always runs)

For each entry in effective `symlink_paths` and `symlink_files`, create a symlink in the worktree pointing at the primary checkout's copy. Idempotent and TOCTOU-safe via atomic-rename pattern:

1. `os.lstat(final_path)` — if it's a regular file or directory (not a symlink), refuse with `INPUT_INVALID` ("won't clobber unmanaged content at <path>")
2. If it's a symlink already pointing at the correct target: no-op
3. Otherwise: `os.symlink(target, <final_path>.tmp-<pid>-<rand>)` in the same dir, then `os.replace(<final_path>.tmp...>, final_path)`. This is atomic and immune to concurrent-replace races between check-and-set.
4. The `os.lstat` step uses `O_NOFOLLOW` semantics to prevent symlink-to-victim attacks; a path that resolves through a symlink to outside the worktree is rejected.

Cross-platform: on Windows, fallback to `mklink /J` (directory junction) for path symlinks where developer-mode is not enabled. File-symlink fallback: print warning, skip. The atomic-rename pattern still applies via `os.replace` which is cross-platform on Python ≥ 3.3.

**Windows-specific note for `os.replace`.** CPython's `os.replace` calls `MoveFileExW` with `MOVEFILE_REPLACE_EXISTING`. This handles directory junctions correctly when the destination is a junction or absent, but fails when the destination is a regular directory. The lstat refuse-on-real-dir check (step 1 above) eliminates that case before we get here. Same-volume source/destination is required for atomicity — always satisfied because both paths are inside the same worktree. A Windows-specific test case (`pytest -m windows`) covers junction-replacing-junction and the refused-real-dir path.

### Hook trust model (trust-on-first-use)

Hook scripts run with the operator's full privileges. Cloning a hostile repo and running `wt new` is RCE-equivalent without trust. Orca enforces:

1. **Default-safe.** First run of any hook script for a given `(repo_key, script_path, sha256)` triple prints the script content + path and prompts the operator to confirm (`Run this script? [y/N]`). Confirmation is recorded in the trust ledger.
2. **Subsequent runs** re-validate the SHA against the trust ledger. If the SHA changed, prompt again with a diff.
3. **`--trust-hooks` flag** (or `ORCA_TRUST_HOOKS=1` env) bypasses the prompt for THIS invocation only and does NOT update the ledger. Subsequent runs without the flag re-prompt. Meant for one-off automation.
4. **`--trust-hooks --record`** bypasses the prompt AND records the SHA in the ledger. Subsequent runs without the flag accept silently. Meant for CI bootstrap after operator pre-validation.
5. **`--no-setup`** skips Stages 2-4 entirely; safe default for untrusted clones.
6. **Non-interactive guard.** `wt new` against a fresh clone with `default_agent != none` AND no entry in the ledger AND stdin is non-interactive: exit `INPUT_INVALID` with hint to pass `--trust-hooks` or `--no-setup`. Interactive sessions get the prompt.

**Repo key.** The ledger is keyed by `(repo_key, script_path, sha256)` where:
- `repo_key` defaults to `git config --get remote.origin.url` (canonical, mount-independent, survives reclone)
- If no remote: fall back to `repo_root_realpath`
- The choice is recorded in the ledger entry so debugging shows which path was used

**Ledger location.** `${ORCA_TRUST_LEDGER:-${XDG_CONFIG_HOME:-$HOME/.config}/orca/worktree-trust.json}`. Devcontainer / codespace operators mount `~/.config/orca/` from host into container OR set `ORCA_TRUST_LEDGER` to a persistent volume path.

**Ledger writes** are protected by the same `fcntl.flock` strategy as the registry, on a sibling `worktree-trust.lock` file. Concurrent `wt new` invocations across different repos do not race the ledger.

The ledger is per-machine, never committed to any repo, and shared across all repos for that operator.

### Stage 2: `after_create` (once per worktree)

Bash script at `.orca/worktrees/after_create`. Cwd: the new worktree. Subject to the trust model above. Env:

```text
ORCA_REPO_ROOT=<absolute path to primary checkout>
ORCA_WORKTREE_DIR=<absolute path to new worktree>
ORCA_BRANCH=<branch name>
ORCA_LANE_ID=<sanitized lane id>
ORCA_LANE_MODE=<branch|lane>
ORCA_FEATURE_ID=<set only if lane mode>
ORCA_HOST_SYSTEM=<spec-kit|openspec|superpowers|bare>
```

Failure (non-zero exit): `wt new` aborts and reverts (removes worktree, deletes branch). Skip with `--no-setup`.

### Stage 3: `before_run` (every reattach)

Same env as Stage 2. Runs after Stage 2 on `wt new`, then on every `wt start`. Use case: refresh secrets, warm caches, ensure auth tokens. Failure logs but does not abort.

### Stage 4: `before_remove` (every removal)

Same env. Runs before any deletion happens. Use case: archive logs, close detached PRs, push cleanup. Failure logs but does not block.

### `wt init` generator

Generates `after_create` by inspecting the primary checkout for ecosystem signals:

| Signal file | Generated line |
|---|---|
| `package.json` (no lockfile) | `npm install` |
| `package.json` + `bun.lockb` | `bun install` |
| `package.json` + `pnpm-lock.yaml` | `pnpm install` |
| `pyproject.toml` + `uv.lock` | `uv sync` |
| `pyproject.toml` (no `uv.lock`) | `pip install -e .` |
| `requirements*.txt` | `pip install -r <each>` |
| `Cargo.toml` | `cargo fetch` |
| `go.mod` | `go mod download` |
| `Gemfile` | `bundle install` |

Plain bash. Editable. Refuses to overwrite existing file unless `--replace`.

**Monorepo behavior.** The detection table walks the **top-level only**. Repos with `apps/<x>/package.json` or `packages/<y>/pyproject.toml` get a single top-level install line, missing per-package installs. `wt init` prints a warning when it detects signal files in `apps/`, `packages/`, or `crates/` subdirectories, recommending the operator hand-edit. The generated script ships with a comment `# monorepo: edit per-package install lines if needed`. v1 does NOT auto-walk subdirectories; this is tracked as future work.

**Existing `worktrees/` directory.** If the repo already has a top-level `worktrees/` (some monorepos use it for git submodules or generated code), `wt init` prints a one-line note: `orca worktrees live at .orca/worktrees/; this is unrelated to the existing worktrees/ directory in your repo`. No collision on the default base because `.orca/` namespace prefix is in effect.

## Lane-id and sidecar

### Lane-id rules

- Source: `--branch` (always required) plus optional `--feature` + `--lane` for Orca lane mode
- Sanitization: slashes → hyphens, `[^A-Za-z0-9._-]` → `_`
- Validation: matches `[A-Za-z0-9._-]+`, **max 128 chars** (aligned with path-safety contract Class D), not `.` / `..`, not leading `-`
- Reuses `validate_identifier(value, field="...", max_length=128)` from path-safety consolidation (Class D)
- tmux window-name truncation (`tmux` enforces ≤ 32 visible chars) is a separate post-validation concern; sidecar's `tmux_window` field stores the truncated form, `lane_id` stores the full form

### Sidecar `.orca/worktrees/<lane-id>.json`

Atomic write, one file per active worktree:

```json
{
  "schema_version": 1,
  "lane_id": "015-wizard",
  "lane_mode": "lane",
  "feature_id": "015",
  "lane_name": "wizard",
  "branch": "feature/015-wizard",
  "base_branch": "main",
  "worktree_path": "/abs/path/to/worktree",
  "created_at": "2026-04-30T22:55:00Z",
  "tmux_session": "orca",         // resolved (template substituted)
  "tmux_window": "015-wizard",
  "agent": "claude",
  "setup_version": "<sha256 of after_create when last run>",
  "last_attached_at": "2026-04-30T23:10:00Z",
  "host_system": "superpowers"
}
```

The `setup_version` field drives `wt start --rerun-setup`: if the script's hash changed since this lane was created, `wt start` warns and re-runs Stage 2 on demand.

### Registry `.orca/worktrees/registry.json` (schema_version 2)

The legacy reader at `src/orca/sdd_adapter.py:799-845` expects `lanes` as a flat list of lane-id **strings**, then opens `<lane_id>.json` per entry to read sidecar fields `feature` (or `id`), `branch`, `status`, `path`, `task_scope`. The new manager bumps to schema_version 2 with a richer shape. The reader is updated in the same PR to handle both shapes; a one-shot migrator runs at first `wt` invocation against an existing v1 registry.

**v2 registry shape:**

```json
{
  "schema_version": 2,
  "lanes": [
    {"lane_id": "015-wizard", "branch": "feature/015-wizard",
     "worktree_path": "/abs/path", "feature_id": "015"}
  ]
}
```

**v2 sidecar emits BOTH new and legacy field names** so older readers (Phase 1.5 sdd_adapter, third-party tools) continue working:

```json
{
  "schema_version": 2,
  "lane_id": "015-wizard", "id": "015-wizard",
  "feature_id": "015", "feature": "015",
  "lane_mode": "lane",
  "lane_name": "wizard",
  "branch": "feature/015-wizard",
  "base_branch": "main",
  "worktree_path": "/abs/path", "path": "/abs/path",
  "status": "active",
  "task_scope": [],
  "...": "..."
}
```

The legacy fields (`id`, `feature`, `path`, `status`, `task_scope`) are NOT documented as orca's preferred surface — operators should read the v2 fields. They're emitted only for read-side compatibility.

**Deprecation horizon.** Legacy field emission is removed in `schema_version` 3, no earlier than 2026-Q4 and contingent on `_load_worktree_lanes` being updated to read v2 in all supported orca versions. Tracked as a Phase 3+ task. v3 is OUT OF SCOPE here.

**Reader update** (`src/orca/sdd_adapter.py:799-845`):
- If `registry["schema_version"] == 2` and lanes are objects: read `lane["lane_id"]`
- Else (v1 or missing version): preserve existing string-list path
- Defensive guard: if `lanes` contains a mix of strings and dicts (e.g., partial migration mid-write), normalize each entry — strings pass through, dicts read `["lane_id"]`, anything else is logged and skipped. Prevents `Path / dict` TypeError if a downstream consumer pinned to old orca encounters a v2 registry
- Sidecar reader unchanged (legacy fields still present)

**Migrator** (`orca.core.worktrees.registry.migrate_v1_to_v2`):
- Triggered automatically on first `wt new`/`wt ls`/`wt doctor` if registry has no `schema_version` or `schema_version == 1`
- Reads legacy registry + per-lane sidecars, writes v2 registry, preserves sidecars (they're additively compatible — new fields written, legacy fields kept)
- Idempotent; subsequent invocations are no-op
- Backed up as `registry.v1.bak.json` next to the registry

### Concurrent-write semantics

`registry.json` reads and writes are protected by `fcntl.flock(LOCK_EX)` for the duration of read-modify-write. Acquisition has a 30-second timeout (configurable via `ORCA_WT_LOCK_TIMEOUT`); on timeout, exit code 75 (`EX_TEMPFAIL`) with `INPUT_INVALID` envelope. The lock is held on `<repo>/.orca/worktrees/registry.lock` (separate file, not the registry itself, to avoid cross-platform "lock-on-renamed-file" issues). The actual write is still atomic (write-to-tmp + `os.replace`) inside the lock.

**Windows path** (`msvcrt.locking` — mandatory byte-range, semantically different from POSIX advisory whole-file):

1. On first creation, write a 1-byte sentinel `b"\0"` to `registry.lock` so byte 0 exists (`msvcrt.locking` on a 0-byte file returns `EINVAL`)
2. Open with `os.open(..., os.O_RDWR)`, `os.lseek(fd, 0, 0)`, `msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)` — non-blocking lock on byte 0, length 1
3. On `OSError` with `errno.EACCES` or `errno.EDEADLK`: sleep `min(0.1 * 2**attempt, 1.0)` seconds with small jitter, retry up to 30s total wall-clock; on timeout return exit code 75 (`EX_TEMPFAIL`)
4. Release via `msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)` then `os.close`
5. Do NOT use `LK_LOCK` (blocking). Windows blocking locks can deadlock when the lock holder is itself blocked; non-blocking + retry is safer

Contended-write integration test (POSIX): spawns two writers, asserts both lanes land and one waits.
Contended-write integration test (Windows, gated by `pytest -m windows`): same expectation; if Windows CI is unavailable, document explicitly that Windows concurrent `wt new` is best-effort and SHOULD NOT be driven from automation.

## tmux integration

### Session model

One tmux session per repo, named per `[worktrees] tmux_session` (literal or templated with `{repo}`). Each worktree gets one tmux **window** within the session. Windows are named by lane-id (truncated to tmux's 32-char window-name limit if needed). Panes within the window are the operator's domain.

### `{repo}` template sanitization

`{repo}` resolves to `Path(repo_root).name` (basename of the primary checkout). Before substitution, the value is sanitized via `re.sub(r"[^A-Za-z0-9._-]", "_", name)` and truncated to 64 chars. Reserved tmux-target characters (`:`, `.`) are replaced with `_` even though they're inside `[A-Za-z0-9._-]` exception (the `.` exception is removed for `{repo}` substitution specifically). Test cases: repos named with `:`, spaces, shell metacharacters, unicode, leading `-`. The sanitized form is what writes to sidecar `tmux_session` and `events.jsonl`.

### Agent-launch quoting via prompt-file + launcher-script

The agent-launch path does NOT use `tmux send-keys '<long-shell-string>' Enter` (typed literally into the pane, operator-supplied prompts can contain shell metacharacters) AND does NOT use `tmux set-environment` (session-scoped — leaks env var into every other window AND every split-pane in the session).

Instead, two files per lane:

1. **Prompt file** at `<worktree>/.orca/.run-<lane-id>.prompt`, mode 0600, owner-read only. Contains the raw operator prompt (one or more lines). Written by `wt new` before `send-keys`. Deleted by the launcher script after first read.

2. **Launcher script** at `<worktree>/.orca/.run-<lane-id>.sh`, mode 0700:
   ```bash
   #!/usr/bin/env bash
   set -e
   PROMPT_FILE=".orca/.run-<lane-id>.prompt"
   if [[ -f "$PROMPT_FILE" ]]; then
     PROMPT="$(cat "$PROMPT_FILE")"
     rm -f "$PROMPT_FILE"
   else
     PROMPT=""
   fi
   exec claude --dangerously-skip-permissions --prompt "$PROMPT"
   ```

3. `tmux send-keys -t <session>:<window> 'bash .orca/.run-<lane-id>.sh' Enter` sends only the script path; no operator content flows through `send-keys` and no env var gets set at session scope.

**Cleanup contract:**
- Prompt file: deleted by launcher script on read (one-shot), so a crashing agent does not leak the prompt past first launch
- Launcher script: persists for the lane's lifetime, removed by `wt rm`. Operators rerunning `wt start` overwrite the prompt file but reuse the same launcher
- Both files added to `.git/info/exclude` of the worktree at creation time so they never accidentally enter git

**Operator-supplied `-- <agent-args...>`** are appended to the launcher script as a quoted array via `shlex.quote`, NOT embedded in the prompt:
```bash
exec claude --dangerously-skip-permissions <quoted-args...> --prompt "$PROMPT"
```

**Unit tests** cover: prompts with single-quotes, double-quotes, backticks, `$()`, newlines, unicode, multi-line prompts, empty prompt (no `--prompt` flag emitted), no `-p` argument supplied (no prompt file written, launcher reads empty), and the cleanup-after-crash case (prompt file already deleted on second start).

### Stale tmux state on `wt ls`

`wt ls` runs `tmux list-windows -t <session>` (best-effort; missing session is fine) and reconciles per-row:

- Sidecar claims tmux window X exists in session Y. If `list-windows` shows X: column reads `attached`. If not: column reads `stale`. If session Y doesn't exist: column reads `session-missing`.
- An emitted `tmux.session.killed` event is appended to `events.jsonl` when `wt ls` first observes session-missing for a previously-attached lane.
- The reconciliation is read-only; `wt doctor --reap` is what actually cleans up.

### `wt new`

1. Create worktree via `git worktree add`
2. Run hooks (Stage 1 → Stage 2 → Stage 3)
3. tmux: ensure session exists (`tmux new-session -d -s <session> -c <path>` if missing), create window (`tmux new-window -t <session> -n <lane-id> -c <path>`)
4. If `--agent <name>` (default from config): `tmux send-keys -t <session>:<lane-id> '<agent-cmd>' Enter`
5. Print absolute worktree path to stdout (so non-tmux operators can `cd "$(orca-cli wt new ...)"`); print attach hint to stderr

### `wt start`

1. Verify worktree exists (registry + `git worktree list`)
2. Run Stage 3 hook
3. Recreate tmux session/window if missing
4. Launch agent only if pane has no live agent and `--agent` is set

### `wt rm`

1. Run Stage 4 hook
2. Kill tmux window (`tmux kill-window`, silent if missing)
3. `git worktree remove` then `git branch -D` (unless `--keep-branch`)
4. Remove sidecar and registry entry
5. Kill session if empty

### `--no-tmux`

Skip all tmux subprocess calls. Worktree, hooks, sidecar, registry all run normally. Agent does NOT auto-launch (no pane to launch into). Operator can later `wt start <branch>` (without `--no-tmux`) to add the tmux window to an existing worktree.

### Cross-platform

| Platform | Status |
|---|---|
| Linux | full |
| macOS | full |
| WSL | full |
| Cygwin / Git Bash | full |
| Windows native | `--no-tmux` implicit; warning printed once; agent auto-launch unavailable |

Symlinks on Windows: `pathlib` symlink fallback to directory junction (`mklink /J`) where applicable. If neither works, log warning and skip — operator handles manually.

## JSON output shapes

Operators script against `wt ls --json` and `wt config --json`. These shapes are committed:

```json
// wt ls --json
{"schema_version": 1, "lanes": [
  {"lane_id": "015-wizard", "branch": "feature/015-wizard",
   "worktree_path": "/abs/path", "feature_id": "015",
   "tmux_state": "attached|stale|session-missing|none",
   "agent": "claude|codex|none",
   "last_attached_at": "2026-04-30T23:10:00Z|null",
   "setup_version": "<sha>|null"}
]}

// wt config --json
{"schema_version": 1, "effective": { /* merged worktrees.toml + worktrees.local.toml */ },
 "sources": {"committed": ".orca/worktrees.toml", "local": ".orca/worktrees.local.toml"}}
```

Bumping these shapes requires `schema_version` increment.

## Lifecycle events

Every state transition appends a JSON line to `.orca/worktrees/events.jsonl`:

```json
{"ts": "2026-04-30T22:55:00Z", "event": "lane.created",
 "lane_id": "015-wizard", "branch": "feature/015-wizard"}
{"ts": "2026-04-30T22:55:03Z", "event": "setup.after_create.completed",
 "lane_id": "015-wizard", "duration_ms": 2340, "exit_code": 0}
{"ts": "2026-04-30T22:55:04Z", "event": "tmux.window.created",
 "lane_id": "015-wizard", "session": "orca", "window": "015-wizard"}
```

Closed event vocabulary (new events require contract bump):

- `lane.created`, `lane.attached`, `lane.removed`
- `setup.{after_create|before_run|before_remove}.{started|completed|failed}` with `duration_ms` + `exit_code`
- `tmux.window.{created|killed}`, `tmux.session.{created|killed}`
- `agent.launched`, `agent.exited`

Consumers:

- `wt ls` enriches the table with last-activity column
- `wt doctor` cross-references events vs. registry vs. `git worktree list`
- `flow-state-projection` (existing) gains a per-lane setup+agent dimension

## Doctor + reap

`orca-cli wt doctor [--reap [-y]]` validates:

- Config files parse and validate
- tmux is installed (or `--no-tmux` implicit on Windows)
- Hook scripts (if present) are executable
- Registry consistency vs. `git worktree list` (orphaned in either direction)
- Sidecar consistency vs. registry
- tmux windows correspond to live lanes
- Sidecar `worktree_path` exists on disk

`--reap` offers fixes interactively (`-y` for unattended). Examples of orphans:

- Worktree in `git worktree list` but no registry entry → register it
- Sidecar without a `git worktree` → remove sidecar + branch
- tmux window for a lane that no longer exists → kill window
- Sidecar where `worktree_path` is missing on disk → mark `orphaned`

No background daemon. No automatic cleanup. Operator runs explicitly.

## Path-safety usage

Per the hard-prerequisite section above. Every CLI flag goes through `orca.core.path_safety` helpers:

| Flag | Class | Validator |
|---|---|---|
| `--branch`, `--feature`, `--lane` | D | `validate_identifier(..., max_length=128)` |
| `--worktree-path`, hook paths | A | `validate_repo_dir` / `validate_repo_file` |

Subprocess invocations (tmux, git, hook scripts) use `subprocess.run(args=[...], check=False)` with `args` as a list, never shell strings. Hook env values are quoted via `shlex.quote` before injection. Agent-launch quoting uses the tempfile-script approach (see §"Agent-launch quoting via tempfile script") rather than `send-keys` literal strings.

## Perf-lab compatibility (Phase 2; out of v1 scope)

Per operator note, perf-lab needs to be loosened so orca, cmux, and plain `git worktree` all work as worktree managers above it.

Migration is **not** in v1. v1 ships orca's worktree manager only. Phase 2 will add `.worktree-contract.json` support — a cross-tool standard read by `wt init` to seed `worktrees.toml` + generate `after_create`. Until then, operators of perf-lab use orca by running `wt init` manually after editing `worktrees.toml` to match perf-lab's existing `.cmux/setup` symlink list. This is documented in the v1 README.

The `.worktree-contract.json` schema (Phase 2 design — see `2026-05-01-orca-worktree-contract-design.md` for the canonical spec):

```json
{
  "schema_version": 1,
  "symlink_paths": ["specs", ".specify", "docs", "shared"],
  "symlink_files": [".env", ".env.local", ".env.secrets",
                    "perf-lab.config.json"],
  "init_script": ".worktree-contract/after_create.sh"
}
```

NOTE: the field name was originally proposed as `after_create_script` here. The Phase 2 spec ships the corrected name `init_script` (more accurate semantically — it's the contract's worktree-init hook, not specifically tied to orca's Stage 2 nomenclature). This snippet is updated for consistency with the Phase 2 spec.

Orca PR ships first; perf-lab cross-repo PR follows; both ship the schema and adapter together in Phase 2.

## Testing

### Unit (~50 tests)

- `layout.py`: lane-id derivation × 3 modes, sanitization edge cases, base-path resolution
- `config.py`: TOML parse + merge, schema validation, missing-section defaults, scalar-where-list rejection (lessons from PR #70)
- `setup_hook.py`: auto-symlink per `host.system`, conflict-when-real-file-blocks, idempotency, hook env contract
- `registry.py`: atomic writes, missing/malformed input, concurrent-writer safety, legacy-schema compatibility
- `tmux.py`: subprocess invocation contract (mocked tmux), per-verb argv shape
- `identifiers.py`: shared with path-safety once landed

### Integration (~15 tests, gated by `pytest -m integration`)

- Full `wt new` happy path against fresh tmp git repo (real `git worktree add`, real fs, mocked tmux)
- `wt new` → `wt rm` round trip leaves repo clean
- `wt new` with hook failure aborts and reverts cleanly
- `wt start` re-attach when sidecar exists but tmux window doesn't
- `wt doctor --reap` on deliberately-corrupted state
- Cross-host: spec-kit / openspec / superpowers / bare each get correct symlinks

### Dogfood

The orca repo itself uses `wt new` for a subsequent feature branch and validates the workflow end-to-end. Counts as one integration test.

### Path-safety regression

Symlink-rejection, root-containment, and identifier-format tests on every flag.

## Effort estimate (revised post-review)

- Module scaffolding + config (committed + local merge) + identifiers: 0.5 days
- `wt new` (worktree + Stage 1 auto-symlink + sidecar + registry): 0.5 days
- `wt rm` + `wt ls` + `wt cd`: 0.25 days
- Hooks (Stage 2/3/4) + env contract + revert-on-failure: 0.5 days
- **Hook trust model** (TOFU ledger + prompt + `--trust-hooks` + CI-non-interactive guard): 0.5 days *(new)*
- tmux integration: 0.5 days
- **Agent-launch tempfile-script approach** (write `.orca/.run-<lane>.sh`, env-var prompt, cleanup): 0.25 days *(new; in addition to base tmux)*
- `wt init` (script generation + monorepo warnings): 0.25 days
- `wt start` (reattach + setup_version + `--rerun-setup`): 0.25 days
- `wt doctor` + `--reap` + tmux liveness probe in `wt ls`: 0.75 days
- Lifecycle event log: 0.25 days
- `wt config` + `wt version` + `wt merge`: 0.25 days
- **Concurrent-write locking** (fcntl + Windows fallback + retry/timeout): 0.25 days *(new)*
- **Idempotency state machine** (8-row state cube + `--reuse-branch`): 0.5 days *(new)*
- **Atomic-rename symlink layer** (TOCTOU-safe): 0.25 days *(new; absorbed Stage 1)*
- **Schema v2 migrator** + reader update at `sdd_adapter._load_worktree_lanes`: 0.5 days *(new)*
- Tests (60 unit + 25 integration + 3 contended-write): 1.75 days
- Docs (capability README, AGENTS.md row, README troubleshooting): 0.25 days

Total: **~8.5 days focused work** (revised up from initial 5; round 1 added load-bearing items, round 2 added test surface for state-cube + Windows + TOFU + send-keys quoting).

Hard prerequisite: path-safety consolidation lands first or as the lead commit (its own 2-3 day budget per `2026-04-30-orca-path-safety-consolidation-design.md`).

## Cross-references

- Phase 4a (file-backed reviewer pattern) — `docs/superpowers/specs/2026-04-28-orca-phase-4a-in-session-reviewer-design.md`
- Spec 015 (brownfield adoption) — `docs/superpowers/specs/2026-04-29-orca-spec-015-brownfield-adoption-design.md`
- Path-safety consolidation — `docs/superpowers/specs/2026-04-30-orca-path-safety-consolidation-design.md`
- v1 north-star — `docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md`
- Symphony reference — `~/symphony/SPEC.md`
- cmux reference — `~/.cmux/cmux.sh`
