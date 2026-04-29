# Orca Spec 015 — Brownfield Adoption (v2)

**Date:** 2026-04-29
**Status:** Design (post-brainstorm, pre-implementation-plan)
**Predecessors:**
- `docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md` (v1 north star)
- Original `specs/015-brownfield-adoption/` (2026-04-14) — historical; covered Adoption Records for pre-orca features. Implementation killed in Phase 1 strip. This new 015 reuses the slot with different scope.
- Memory note `project_brownfield_adoption.md` (2026-04-12) — gap framing.

## Why this spec

Orca v1 ships a capability library, plugin formats (Claude Code skills/commands, Codex AGENTS.md), and an opinion layer. What it does NOT have today is a clean install story for a third party adopting orca into their existing repo. The current install is "clone the source, point `ORCA_PROJECT` at it, manually merge whatever's needed into your CLAUDE.md, hope nothing collides."

Real friction points known to exist:
- **CLAUDE.md / AGENTS.md collisions** when host repo has its own content
- **Slash command name conflicts** (host's `/review-spec` vs orca's)
- **`.specify/` directory shape** is spec-kit-specific; orca should not impose it
- **constitution.md merge strategy** when host has its own
- **CI/review hooks** in host repo
- **`.orca/` state directory placement** in a repo with its own conventions

Spec 015 closes the gap with a declarative-manifest-driven adoption flow that respects the host's existing system.

## Scope

In scope:
- Install workflow for a third party adopting orca into their existing repo
- Adapter layer making orca spec-system-agnostic (`{spec-kit, openspec, superpowers, bare}`)
- Idempotent apply + reversible revert
- Conflict resolution policies for CLAUDE.md/AGENTS.md, slash commands, constitution

Out of scope (v1):
- CI hook installation (orca does NOT touch `.github/workflows/`)
- Migration helpers between host systems (`spec-kit → superpowers`, etc.)
- AR records / pre-orca feature reference (was the original 015's scope; deferred)
- Plugin formats other than Claude Code + Codex (covered by Phase 3)
- Multi-repo install (one repo at a time)
- Auto-discovery of orca commands the host has hidden via per-user overrides

## Goals

A third party with an existing git repo can run a single command (`orca adopt`) and end up with a working orca install that respects what was already in the repo. The choices made are captured in a version-controlled manifest. Reversal is one command (`orca apply --revert`).

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│  orca adopt          → interactive wizard, populates manifest   │
│  orca apply          → idempotent executor, reads manifest       │
│  orca apply --revert → undoes a prior apply                      │
└──────────┬─────────────────────────────────────────────────────┘
           │  reads/writes
           ▼
┌────────────────────────────────────────────────────────────────┐
│  .orca/adoption.toml  (the manifest — source of truth)          │
│  - host_system: spec-kit | openspec | superpowers | bare        │
│  - feature_dir_pattern: <derived per host>                      │
│  - slash_command_namespace: orca | <custom>                     │
│  - claude_md_policy: append | section | namespace | skip        │
│  - constitution_md: respect-existing | merge | skip             │
│  - state_dir: .orca                                             │
│  - installed_capabilities: [list]                               │
└──────────┬─────────────────────────────────────────────────────┘
           │  consulted by
           ▼
┌────────────────────────────────────────────────────────────────┐
│  orca.core.host_layout  (adapter)                               │
│  - resolve_feature_dir(feature_id) → Path                       │
│  - list_features() → [feature_id]                               │
│  - constitution_path() → Path | None                            │
│  - agents_md_path() → Path | None                               │
│  - review_artifact_dir() → Path                                 │
└──────────┬─────────────────────────────────────────────────────┘
           │  used by
           ▼
┌────────────────────────────────────────────────────────────────┐
│  Capabilities + slash commands (existing)                        │
│  Read paths via host_layout, not hardcoded conventions.         │
└────────────────────────────────────────────────────────────────┘
```

Three components:

1. **CLI surface.** `orca adopt` (wizard) populates the manifest. `orca apply` (executor) reads it. `orca apply --revert` undoes. The wizard is optional convenience; the manifest is the contract.

2. **Manifest (`.orca/adoption.toml`).** Declarative file capturing every adoption choice. Lives in the host's `.orca/` directory, version-controlled, hand-editable. Validated by orca on read.

3. **`orca.core.host_layout` adapter.** The single abstraction that lets every capability and slash command work against any host system. Maps "feature-dir for feature-id X" → actual path per the manifest's `host_system`. Adding a new host system is a new adapter case, not a refactor across capabilities.

### Spec-agnostic implication

The adapter is the only place that knows about specific host systems. Capabilities and slash commands receive resolved `Path` objects.

### Path-safety contract integration

Today path-safety contract Class A hardcodes `<repo>/specs/<feature-id>/` OR `<repo>/openspec/changes/<feature-id>/`. After 015, Class A reads from `host_layout.resolve_feature_dir(feature_id)` — the manifest decides. The contract document at `docs/superpowers/contracts/path-safety.md` gets a corresponding update once 015 implementation lands.

## Detection (`orca adopt` discovery)

Probes in priority order; first match wins:

1. **superpowers** — `docs/superpowers/specs/` exists, OR `.claude/plugins/cache/claude-plugins-official/superpowers/` exists
2. **openspec** — `openspec/changes/` exists
3. **spec-kit** — `.specify/` exists
4. **bare** — none of the above; orca creates `docs/orca-specs/` as fallback

Detection writes a `host_system` value to the manifest. User can override via `orca adopt --host superpowers`. Multiple systems detected (rare; usually a migration in progress) → wizard asks user to pick.

## Manifest schema

```toml
# .orca/adoption.toml
schema_version = 1

[host]
system = "superpowers"  # spec-kit | openspec | superpowers | bare
feature_dir_pattern = "docs/superpowers/specs/{feature_id}"  # interpolation pattern
constitution_path = "docs/superpowers/constitution.md"  # null if none
agents_md_path = "AGENTS.md"  # or CLAUDE.md
review_artifact_dir = "docs/superpowers/reviews"

[orca]
state_dir = ".orca"  # default; alternate path possible
installed_capabilities = [
  "cross-agent-review",
  "citation-validator",
  "contradiction-detector",
  "completion-gate",
  "worktree-overlap-check",
  "flow-state-projection",
]

[slash_commands]
namespace = "orca"  # collision-free if no host commands start with /orca:
enabled = ["review-spec", "review-code", "review-pr", "gate", "cite", "doctor"]
disabled = []  # opt out of specific commands

[claude_md]
policy = "section"  # append | section | namespace | skip
section_marker = "## Orca"  # used when policy = section
namespace_prefix = "orca:"  # used when policy = namespace

[constitution]
policy = "respect-existing"  # respect-existing | merge | skip

[reversal]
backup_dir = ".orca/adoption-backup"
```

### Schema validation rules

- `schema_version` must be 1 (this spec); future versions trigger migration prompt
- `host.system` must be one of the four supported values; unknown rejected
- `host.feature_dir_pattern` must contain `{feature_id}` literal
- All paths in manifest are resolved relative to the repo root; absolute paths rejected (per path-safety Class A)
- `slash_commands.namespace` must match `[a-z][a-z0-9-]*` and not collide with reserved prefixes (`speckit-`, `claude-`)

## Conflict resolution policies

| Surface | Existing host state | Default policy | Alternatives |
|---------|---------------------|----------------|--------------|
| **CLAUDE.md / AGENTS.md** | file exists with content | `section` (orca appends `## Orca` block delimited by HTML comment markers) | `append` (no delimiter), `namespace` (orca content lives in `ORCA.md`, referenced from CLAUDE.md), `skip` (manual integration) |
| **Slash commands** | host has `/review-spec` etc. | `namespace` (`/orca:review-spec`; current default) | `flat` (use `/review-spec` if not taken; refuse if taken) |
| **Constitution** | host has `constitution.md` | `respect-existing` (orca reads, doesn't write) | `merge` (append orca block), `skip` |
| **`.orca/`** | doesn't exist | create with mode 0755 | alternate path via manifest |
| **`.orca/adoption.toml`** | exists from prior install | `orca apply` is idempotent | `orca adopt --reset` regenerates |
| **CI hooks** | host has `.github/workflows/*` | orca does NOT touch CI in v1 | manual; documented in adoption guide |

### Section markers (CLAUDE.md `policy = section`)

orca delimits its inserted block with HTML comment markers so a future revert can find and remove it precisely:

```html
<!-- orca:adoption:start version=1 -->
## Orca

[orca-managed content here]
<!-- orca:adoption:end -->
```

If the markers are tampered with (user edits inside the block), revert refuses for safety; user must manually remove the block.

### Ambiguity rejection

`orca apply` rejects ambiguous states by default. Examples:
- CLAUDE.md exists with no clear merge marker AND manifest says `policy = "section"` AND markers cannot be auto-inserted safely → user told to choose `append` explicitly OR pre-add the marker manually
- Slash command name `/review-spec` taken by host AND manifest says `namespace = ""` (flat) → refuse; user must set `namespace = "orca"` or another non-colliding value

## Data flow

### Apply (idempotent)

1. Read `.orca/adoption.toml`; validate schema
2. Snapshot every file orca will modify into `.orca/adoption-backup/<timestamp>/` (only if not already snapshotted for this manifest revision; dedupe by manifest content hash)
3. Compute desired state per manifest
4. For each surface (CLAUDE.md, slash commands, constitution): diff actual vs desired; apply if different
5. Write `.orca/adoption-state.json` recording what was applied — file paths, content hashes pre/post, manifest hash, timestamp
6. Run `orca-cli doctor` as final verification; if doctor reports failures, surface them but do NOT roll back automatically (user decides)

### Revert

1. Read `.orca/adoption-state.json`
2. For each modified file, restore from `.orca/adoption-backup/<timestamp>/` IF the current content's hash matches the post-apply hash recorded in state.json
3. If hash mismatch (user has hand-edited): refuse for that file specifically; revert proceeds for other files; report the skipped files
4. Remove `.orca/` directory (with `--keep-state` flag to preserve `adoption-backup/` as audit trail)

### Wizard (`orca adopt`)

1. Probe host (detection section)
2. Ask 3-5 questions: confirm `host_system`, slash command namespace policy, CLAUDE.md merge policy, capabilities to enable
3. Write manifest to `.orca/adoption.toml`
4. By default: run `orca apply` immediately; `--plan-only` flag stops after manifest write so user can review/commit before applying

## Components

### `orca.core.host_layout`

```python
class HostLayout(Protocol):
    def resolve_feature_dir(self, feature_id: str) -> Path: ...
    def list_features(self) -> list[str]: ...
    def constitution_path(self) -> Path | None: ...
    def agents_md_path(self) -> Path | None: ...
    def review_artifact_dir(self) -> Path: ...

def from_manifest(manifest_path: Path) -> HostLayout: ...
def detect(repo_root: Path) -> HostLayout: ...  # used by `orca adopt`
```

Implementations: `SpecKitLayout`, `OpenSpecLayout`, `SuperpowersLayout`, `BareLayout`. Each implements the protocol; detection picks one.

### `orca adopt` (CLI)

```
orca adopt [--host <system>] [--plan-only] [--reset] [--force]
```

- `--host`: override detection
- `--plan-only`: stop after writing manifest; don't apply
- `--reset`: regenerate manifest from scratch (existing manifest backed up)
- `--force`: skip prompts (use defaults); requires `--host` if multiple host systems detected

### `orca apply` (CLI)

```
orca apply [--manifest <path>] [--revert] [--keep-state] [--dry-run]
```

- Default: read `.orca/adoption.toml`, apply
- `--revert`: undo per `adoption-state.json`
- `--keep-state`: with `--revert`, preserve `adoption-backup/` after revert
- `--dry-run`: print diff of what would change; no writes

### `orca-cli doctor` (existing)

Already exists from Phase 3.2. After 015 lands, doctor's checks include:
- `.orca/adoption.toml` valid
- `host_system` reachable (e.g., for `superpowers`, the `docs/superpowers/specs/` directory exists and is writable)
- `adoption-state.json` consistent with current file states
- All `installed_capabilities` invokable

## Error handling

| Error | Behavior |
|-------|----------|
| Manifest missing | `INPUT_INVALID`, suggest running `orca adopt` |
| Manifest invalid (schema) | `INPUT_INVALID`, cite the specific field, exit 1 |
| Manifest schema_version > 1 | Prompt for migration; `--force` accepts at user's risk |
| Host detected mismatches manifest | Warning; user can `--force` or edit manifest |
| Backup directory missing during revert | Refuse; preserve current state; explain |
| Hand-edited file detected during revert | Refuse for that file; revert rest; report |
| Section markers tampered with | Refuse the section-policy revert; user removes manually |
| `.orca/` exists with foreign content (not orca-managed) | Refuse; user clears or chooses different `state_dir` |

All errors follow the path-safety contract's `Result.Err` envelope shape (`kind`, `message`, `field`, `value_redacted`, `rule_violated`).

## Testing strategy

- **Unit:** `host_layout` adapter for each of 4 host systems. Fixtures: minimal repo trees with `.specify/` / `openspec/changes/` / `docs/superpowers/specs/` / nothing.
- **Integration: detection.** `orca adopt --plan-only` against each fixture; snapshot the generated manifest; assert `host_system` value matches expected.
- **Integration: apply.** `orca apply` against each fixture; snapshot post-apply file tree; run `orca-cli doctor`; assert exit 0.
- **Integration: revert.** Apply + revert produces byte-identical original tree.
- **Idempotency:** Apply twice = no-op (second apply produces zero file diffs).
- **Conflict matrix:** Parametrize over CLAUDE.md collision policies × constitution policies × slash command namespaces; assert each combination produces correct output.
- **Edge cases:** Hand-edited file during revert; manifest schema migration; multiple host systems detected; bare-repo fallback.
- **Path-safety contract:** every path-accepting flag in the new CLI follows the contract (symlinks rejected, root containment, etc.).

## Naming note

"Spec 015" historically refers to the brownfield-adoption gap (per memory note). The original implementation used spec-kit's numbered directory convention at `specs/015-brownfield-adoption/`. This new design uses the superpowers convention (date-prefixed file in `docs/superpowers/specs/`) since the orca repo's own canonical spec location is now superpowers. The "015" in this spec's filename is a memory reference, not a directory pointer. This slight inconsistency is itself a brownfield artifact; resolved cleanly once the path-safety + host_layout work lands and orca reads its own specs through the adapter.

## Spec-kit-only side effects

If `host.system = "spec-kit"`, `orca apply` ALSO writes/updates `.specify/extensions.yml` (existing Phase 3.2 surface) to register orca's slash commands at `speckit.orca.*` per the spec-kit extension protocol. For other host systems, no `extension.yml` is touched. The manifest's `host.system` value is the gate for this side effect; bare/openspec/superpowers hosts never see `.specify/extensions.yml` created.

## Self-host case (orca repo adopting itself)

Running `orca adopt` against the orca repo itself (dogfooding) MUST succeed. The orca repo's host system is `superpowers` (specs live at `docs/superpowers/specs/`). The adapter's `SuperpowersLayout` resolves feature dirs accordingly. `.orca/` already exists with capability state; adoption.toml is added alongside, not over. This case is a required integration test — it exercises detection, manifest write, and apply against a real (large) host repo.

## Migration of existing 015 artifacts

The 2026-04-14 `specs/015-brownfield-adoption/` (Adoption Records for pre-orca features) is historical. This new 015 design reuses the slot. Migration:

- Move existing `specs/015-brownfield-adoption/*` to `specs/015-brownfield-adoption-historical/` to preserve the work; the directory is renamed to make the slot reuse explicit.
- Reference the historical directory from this spec's "Predecessors" section (above).
- The original 015's AR-record concept can be revived as a future spec (e.g., 016, when needed) building on top of brownfield install.

## Honest scope estimate

This spec describes:
- 1 new CLI surface (`orca adopt`)
- 1 new CLI subcommand (`orca apply`, plus `--revert`, `--dry-run`, `--keep-state`, `--reset`)
- 1 new module (`orca.core.host_layout`) with 4 implementations
- 1 manifest schema (toml)
- Updates to path-safety contract Class A
- Updates to existing slash commands to consult `host_layout` instead of hardcoded paths

Estimated implementation: **~3-5 days of focused work** spread across:
- Adapter module + 4 host-system implementations: 1.5 days
- `orca adopt` wizard: 0.5 days
- `orca apply` + revert: 1 day
- Slash command refactors to use adapter: 0.5 days
- Test coverage matrix: 1 day

The implementation plan should sequence these in a way that keeps existing behavior unchanged until the adapter is fully wired (i.e., the in-tree spec-kit-orca repo continues to work via a `SpecKitLayout` adapter, not via direct `.specify/` access).

## Honest value statement

What 015 uniquely delivers:

1. **Third-party adoption is real for the first time.** Today, "another team using orca" requires hand-holding; after 015, it's a documented command flow with reviewable choices.
2. **Spec-system independence** unblocks orca for the superpowers/openspec/bare-repo audiences without forcing them onto spec-kit conventions.
3. **Idempotent + reversible** install is a credibility marker for production tools. "I tried orca and uninstalled it cleanly" is a much better experience than "I tried orca and now my CLAUDE.md has stuff I can't easily remove."

What 015 does NOT deliver:

- Per-feature backfill of pre-orca work (the original 015's AR-records). Deferred.
- CI integration; manual today.
- Cross-host migration tooling.

## References

- v1 north star: `docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md` (notably § "Composition with Outer-Loop Runtimes")
- Path-safety contract: `docs/superpowers/contracts/path-safety.md`
- Phase 4a in-session reviewer: `docs/superpowers/specs/2026-04-28-orca-phase-4a-in-session-reviewer-design.md`
- Memory note: `~/.claude/projects/-home-taylor-spec-kit-orca/memory/project_brownfield_adoption.md`
- Original 015 (historical): `specs/015-brownfield-adoption/` (to be moved to `specs/015-brownfield-adoption-historical/` per migration plan above)
