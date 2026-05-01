# Orca Worktree Manager — Design

**Date:** 2026-04-30
**Status:** Design (post-brainstorm, pre-implementation-plan)
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

orca-cli wt cd [<branch>]                # prints absolute path; no
                                          # arg = repo root (primary
                                          # checkout); arg = worktree
                                          # path. Operator wraps in
                                          # $(...) to actually cd.
orca-cli wt ls [--json] [--all]
orca-cli wt merge [<branch>] [--into <target>] [--strategy ...]
orca-cli wt rm [<branch>] [--all] [-f] [--keep-branch]
orca-cli wt init [--replace]             # generates after_create from repo
orca-cli wt config [<key>] [<value>]     # read/write effective config
orca-cli wt version
orca-cli wt doctor [--reap [-y]]
```

Idempotency:
- `wt new <branch>` where the branch already has a worktree attaches instead of erroring
- `wt start <branch>` recreates missing tmux window without touching the worktree
- `wt rm` is no-op if the lane isn't registered

## Configuration schema

### Committed: `.orca/adoption.toml` `[worktrees]`

```toml
[worktrees]
schema_version = 1

# Where worktrees live. Configurable; ".orca/worktrees" is the opinionated default.
base = ".orca/worktrees"

# Lane-id derivation:
#   "branch" — sanitized branch name (cmux-style)
#   "lane"   — <feature>-<short-name> (Orca-style)
#   "auto"   — lane mode if both --feature and --lane are passed; else branch mode
lane_id_mode = "auto"

# Auto-symlinks. Empty list = derive from host.system. Explicit list = override.
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

For each entry in effective `symlink_paths` and `symlink_files`, create a symlink in the worktree pointing at the primary checkout's copy. Idempotent: existing-and-correct symlinks are no-op; existing-but-wrong symlinks are replaced; existing real files block with an error (refuse to clobber).

### Stage 2: `after_create` (once per worktree)

Bash script at `.orca/worktrees/after_create`. Cwd: the new worktree. Env:

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

## Lane-id and sidecar

### Lane-id rules

- Source: `--branch` (always required) plus optional `--feature` + `--lane` for Orca lane mode
- Sanitization: slashes → hyphens, `[^A-Za-z0-9._-]` → `_`
- Validation: matches `[A-Za-z0-9._-]+`, max 64 chars, not `.` / `..`, not leading `-`
- Reuses `validate_identifier` from path-safety consolidation (Class D)

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

### Registry `.orca/worktrees/registry.json`

Backward-compatible with the legacy schema read by `sdd_adapter._load_worktree_lanes` (`src/orca/sdd_adapter.py:799-821`):

```json
{
  "schema_version": 1,
  "lanes": [
    {"lane_id": "015-wizard", "branch": "feature/015-wizard",
     "worktree_path": "...", "feature_id": "015"}
  ]
}
```

`flow_state_projection` and `worktree-overlap-check` continue reading without changes; the new manager becomes the single writer.

## tmux integration

### Session model

One tmux session per repo, named per `[worktrees] tmux_session` (literal or templated with `{repo}`). Each worktree gets one tmux **window** within the session. Windows are named by lane-id (truncated to tmux's 32-char window-name limit if needed). Panes within the window are the operator's domain.

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

## Path-safety

This spec depends on `orca.core.path_safety` from the path-safety consolidation refactor (`docs/superpowers/specs/2026-04-30-orca-path-safety-consolidation-design.md`). If the worktree manager ships first, the manager carries inline equivalents that are migrated to the shared helpers when path-safety consolidation lands.

Every CLI flag goes through `orca.core.path_safety` helpers (Class A repo paths, Class D identifiers). Specifically:

| Flag | Class | Validator |
|---|---|---|
| `--branch`, `--feature`, `--lane` | D | `validate_identifier` |
| `--worktree-path`, hook paths | A | `validate_repo_dir` / `validate_repo_file` |

Subprocess invocations (tmux, git, hook scripts) use `subprocess.run(args=[...], check=False)` with `args` as a list, never shell strings. Hook env values are quoted via `shlex.quote` before injection.

## Perf-lab compatibility

Per operator note, perf-lab needs to be loosened so orca, cmux, and plain `git worktree` all work as worktree managers above it.

Migration (orca contributes patches back to perf-lab; tracked separately):

1. Loosen perf-lab's CLAUDE.md to "use any worktree manager that supports `.worktree-contract.json`"
2. Add `.worktree-contract.json` at perf-lab root:
   ```json
   {
     "schema_version": 1,
     "symlink_paths": ["specs", ".specify", "docs", "shared"],
     "symlink_files": [".env", ".env.local", ".env.secrets",
                       "perf-lab.config.json"],
     "after_create_script": ".worktree-contract/after_create.sh"
   }
   ```
3. Move `.cmux/setup` → `.worktree-contract/after_create.sh` (rename only)
4. Both cmux (small adapter shim) and orca (`wt init` honors natively) read this contract

Orca PR ships first. Perf-lab patch is a separate cross-repo follow-up.

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

## Effort estimate

- Module scaffolding + config + identifiers: 0.5 days
- `wt new` (worktree + Stage 1 auto-symlink + sidecar + registry): 0.5 days
- `wt rm` + `wt ls` + `wt cd`: 0.25 days
- Hooks (Stage 2/3/4) + env contract + revert-on-failure: 0.5 days
- tmux integration: 0.5 days
- `wt init` (script generation): 0.25 days
- `wt start` (reattach + setup_version): 0.25 days
- `wt doctor` + `--reap`: 0.5 days
- Lifecycle event log: 0.25 days
- `wt config` + `wt version` + `wt merge`: 0.25 days
- Tests (50 unit + 15 integration): 1 day
- Docs (capability README, slash command stub deferred, AGENTS.md row): 0.25 days

Total: ~5 days focused work.

## Cross-references

- Phase 4a (file-backed reviewer pattern) — `docs/superpowers/specs/2026-04-28-orca-phase-4a-in-session-reviewer-design.md`
- Spec 015 (brownfield adoption) — `docs/superpowers/specs/2026-04-29-orca-spec-015-brownfield-adoption-design.md`
- Path-safety consolidation — `docs/superpowers/specs/2026-04-30-orca-path-safety-consolidation-design.md`
- v1 north-star — `docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md`
- Symphony reference — `~/symphony/SPEC.md`
- cmux reference — `~/.cmux/cmux.sh`
