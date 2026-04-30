# Orca: `resolve-path` CLI + Slash Command Host-Aware Refactor

**Date:** 2026-04-29
**Status:** Design (post-brainstorm, pre-implementation-plan)
**Predecessors:**
- `docs/superpowers/specs/2026-04-29-orca-spec-015-brownfield-adoption-design.md` (manifest + host_layout adapter; this spec is the load-bearing follow-up that makes Spec 015 functional)
- `docs/superpowers/contracts/path-safety.md` § Class A (already promises "reads from `host_layout.resolve_feature_dir(feature_id)`" — this spec delivers on that promise)

## Why this spec

Spec 015 batch review (Important #1) flagged that the `host_layout` adapter is built and tested but unused at runtime: `orca-cli adopt` writes a manifest declaring (e.g.) `feature_dir_pattern = "openspec/changes/{feature_id}"`, but `/orca:review-spec --feature-id foo` still looks in `specs/foo/`. Adoption is structurally complete but functionally inert until slash commands consult `host_layout`.

This spec closes that gap with a single new CLI subcommand (`orca-cli resolve-path`) plus targeted edits to 5 slash commands. Estimated half-day of focused work.

## Goal

A third party who has run `orca-cli adopt` against their existing repo (any of `{spec-kit, openspec, superpowers, bare}`) can run `/orca:review-spec`, `/orca:review-code`, `/orca:review-pr`, `/orca:gate`, `/orca:cite` and have orca correctly resolve paths per their declared convention. Hosts that have NOT adopted (no manifest) continue to work via detection.

## Scope

In scope:
- New `orca-cli resolve-path` subcommand consuming `host_layout` (manifest-driven OR detection-driven)
- Targeted refactor of 5 slash commands to use `resolve-path` instead of hardcoded `specs/<id>/` patterns
- A small detection-aware contract for the legacy `{SCRIPT}` template-var (clarify what it returns vs. what `resolve-path` produces)

Out of scope:
- Brainstorm, doctor, tui slash commands (don't resolve feature dirs in a way that needs the adapter)
- Changes to capabilities themselves (cross-agent-review, citation-validator, etc.) — they accept resolved paths and don't need the adapter
- Migration from one host system to another (would happen at adoption time, not at resolve time)
- Performance optimization (resolve-path is a cheap operation; one process spawn per slash command is fine)

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Slash command (bash workflow in *.md file)                    │
│                                                                │
│  FEATURE_ID=$({SCRIPT} ... | jq -r .feature_id)               │
│  FEATURE_DIR=$(orca-cli resolve-path \                         │
│                  --kind feature-dir \                          │
│                  --feature-id "$FEATURE_ID")                  │
│  # ... existing capability invocations use $FEATURE_DIR ...   │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ orca-cli resolve-path  (new subcommand)                       │
│                                                                │
│  1. Try from_manifest(repo_root)  →  HostLayout adapter       │
│  2. If no manifest: detect(repo_root)  →  HostLayout adapter  │
│  3. Call adapter method per --kind:                            │
│     • feature-dir  →  resolve_feature_dir(feature_id)         │
│     • constitution →  constitution_path()                      │
│     • agents-md    →  agents_md_path()                         │
│     • reviews-dir  →  review_artifact_dir()                    │
│     • reference-set →  list of feature-relative SDD artifacts │
│  4. Print resolved absolute path(s) to stdout, exit 0          │
└──────────────────────────────────────────────────────────────┘
```

## CLI contract

### Synopsis

```
orca-cli resolve-path --kind <kind> [--feature-id <id>] [--repo-root <path>] [--pretty]
```

### Flags

- `--kind` (required): one of `feature-dir`, `constitution`, `agents-md`, `reviews-dir`, `reference-set`
- `--feature-id` (required for `feature-dir` and `reference-set`; ignored otherwise)
- `--repo-root` (default: cwd resolved): repo root for layout resolution
- `--pretty` (default: false): human-readable output instead of plain path

### Output

By default, prints resolved absolute path(s) to stdout, one per line, exit 0. Multiple paths only for `--kind reference-set`.

`--pretty` adds a leading "kind: <kind>" line and an "adapter: <name>" line for human reading.

### Behavior matrix

| `--kind` | Returns | Detection fallback |
|----------|---------|-------------------|
| `feature-dir` | `host_layout.resolve_feature_dir(feature_id)` (computed; existence not checked) | yes |
| `constitution` | `host_layout.constitution_path()` or empty string + exit 0 if `None` | yes |
| `agents-md` | `host_layout.agents_md_path()` (always returns a path; existence not checked) | yes |
| `reviews-dir` | `host_layout.review_artifact_dir()` | yes |
| `reference-set` | List of feature-dir-relative SDD artifacts that exist (`plan.md`, `data-model.md`, `research.md`, `quickstart.md`, `tasks.md`, `contracts/**/*.md`); one path per line | yes |

### Error envelope

Follows orca's standard `Result.Err` shape on stderr; exit 1:

```json
{
  "ok": false,
  "error": {
    "kind": "INPUT_INVALID",
    "message": "specific reason",
    "field": "--kind",
    "rule_violated": "..."
  }
}
```

Validation rules:
- `--kind` must be one of the 5 allowed values
- `--feature-id` required when `--kind ∈ {feature-dir, reference-set}`; rejected when `--kind ∈ {constitution, agents-md, reviews-dir}`
- `--feature-id` follows path-safety contract Class D (`[A-Za-z0-9._-]+`, max 128, no `.`/`..`)
- `--repo-root` must resolve to an existing directory

Exit codes: 0 (success), 1 (capability error: INPUT_INVALID etc.), 2 (argv parse error)

## Detection fallback

When `<repo_root>/.orca/adoption.toml` does NOT exist, `resolve-path` runs `host_layout.detect(repo_root)` and uses the auto-detected adapter. This means:

- **Existing in-tree orca usage continues to work** without an adoption.toml. The orca repo has `docs/superpowers/specs/`; detection picks `SuperpowersLayout`; slash commands resolve correctly.
- **Third parties who haven't run `orca-cli adopt` yet** get sensible defaults instead of errors.
- **Adopted hosts** get their declared convention honored.

The detection priority order from Spec 015 (`superpowers > openspec > spec-kit > bare`) applies unchanged.

## Slash command changes

Five slash commands need updates. Each is a small bash-block edit:

### `review-spec.md`

Currently (paraphrased): "Resolve `<feature-dir>` from user input or current branch (e.g., `specs/001-foo/`)."

New: extract `FEATURE_ID` from user input or branch (existing logic), then resolve via:
```bash
FEATURE_DIR=$(orca-cli resolve-path --kind feature-dir --feature-id "$FEATURE_ID")
```

### `review-code.md`, `review-pr.md`

Currently: rely on `{SCRIPT}` to set `$FEATURE_DIR`. After: `{SCRIPT}` returns `feature_id`; bash block resolves to `$FEATURE_DIR` via `orca-cli resolve-path`.

### `gate.md`

Same pattern as review-spec — resolve via `orca-cli resolve-path --kind feature-dir`.

### `cite.md`

Two changes: (a) resolve `$FEATURE_DIR` for default reference-set discovery, (b) optionally use `--kind reference-set` to get the auto-discovered list directly:
```bash
mapfile -t REFS < <(orca-cli resolve-path --kind reference-set --feature-id "$FEATURE_ID")
```

The `cite.md` workflow currently has a custom `find` loop for reference-set discovery; that loop becomes the `resolve-path --kind reference-set` implementation, executed once in the orca-cli capability rather than per-slash-command.

### Unchanged

- `brainstorm.md` — references `specs/<feature>/...` as documentation but doesn't enforce the path; can stay loose
- `tui.md` — self-documentation only
- `doctor.md` — no feature-dir resolution

## Path-safety contract integration

The path-safety contract (`docs/superpowers/contracts/path-safety.md`) Class A already promises this dispatch path; this spec delivers it. No further contract update needed. `resolve-path` validates `--feature-id` per Class D and returns absolute paths that callers can use as Class A inputs to capabilities.

## Components

### `src/orca/cli/resolve_path.py` (new)

```python
def run(args: list[str]) -> int:
    """argparse + dispatch to host_layout adapter; print result."""
```

### `src/orca/python_cli.py` (modified)

Register `resolve-path` in `CAPABILITIES`:
```python
_register("resolve-path", _run_resolve_path, "1.0.0")
```

Implement `_run_resolve_path` with argparse + adapter dispatch + output formatting. ~80 LOC.

### `src/orca/core/host_layout/reference_set.py` (new)

The reference-set auto-discovery logic (currently embedded in `cite.md` bash). Single function:
```python
def discover(feature_dir: Path) -> list[Path]:
    """Return existing SDD artifacts under feature_dir, in canonical order."""
```

This consolidates Phase 3.2 backlog item 2's logic into a single Python function consumable by `resolve-path` and any future capability.

### Modified slash commands

5 small bash-block edits in `plugins/claude-code/commands/{review-spec,review-code,review-pr,gate,cite}.md`.

## Testing strategy

- **Unit:** `_run_resolve_path` argparse + each `--kind` value, parametrized over all 4 host_layout adapters. ~12 tests.
- **Reference-set discovery:** unit tests for `discover()` against fixture feature dirs (with/without each canonical SDD artifact). ~6 tests.
- **CLI smoke:** `orca-cli resolve-path` end-to-end with `subprocess.run`, both manifest-driven and detection-driven flows. ~4 tests.
- **Slash command bash parsing:** new test `test_slash_commands_call_resolve_path` greps each modified command for the `orca-cli resolve-path` invocation pattern; prevents regression where a command quietly drops back to hardcoded paths.
- **Backwards compat:** existing slash command tests should continue to pass unchanged (the in-tree orca repo runs detection → SuperpowersLayout → same paths as today).

## Self-host case (orca repo dogfooding)

The orca repo has `docs/superpowers/specs/` and no `.orca/adoption.toml` (deliberately). After this spec lands:
- `orca-cli resolve-path --kind feature-dir --feature-id 015-brownfield-adoption` → returns `/path/to/orca/docs/superpowers/specs/015-brownfield-adoption` (via detection → SuperpowersLayout)
- Slash commands continue to work without surprise

If we later want to commit an `.orca/adoption.toml` to the orca repo (declaring superpowers explicitly), it's a no-op behavior change — same paths, same workflow.

## Failure modes

| Scenario | Behavior |
|----------|----------|
| Manifest missing AND detection finds bare repo (no spec system) | `BareLayout` returns `docs/orca-specs/<feature_id>/` — caller still gets a valid path; existence not checked |
| Manifest schema invalid | `INPUT_INVALID` propagated from `from_manifest` (existing Spec 015 behavior) |
| `--feature-id` violates path-safety Class D | `INPUT_INVALID`, exit 1 |
| `--feature-id` provided for `--kind` that doesn't accept it | `INPUT_INVALID`, exit 1 |
| `--repo-root` not a directory | `INPUT_INVALID`, exit 1 |
| Adapter returns `None` for `constitution_path()` | Empty stdout, exit 0 (NOT an error — caller checks for empty) |

## Honest scope estimate

- New CLI subcommand: ~80 LOC + ~12 tests
- Reference-set discovery module: ~30 LOC + ~6 tests
- 5 slash command edits: ~5 LOC each
- Test coverage: ~22 new tests
- Total: ~150 LOC + 22 tests, **~half-day of focused work**.

## Honest value statement

What this spec uniquely delivers:
1. **Adoption becomes functional, not just structural.** A third party adopting orca onto an OpenSpec or bare repo gets working slash commands.
2. **Closes the path-safety contract loop.** Class A promises adapter dispatch; this spec delivers it.
3. **Centralizes reference-set discovery** that's currently bash logic in one slash command.

What it does NOT deliver:
- New host systems (still 4: spec-kit, openspec, superpowers, bare)
- Cross-host migration (out of scope per Spec 015)
- Capability-level changes (capabilities are unchanged)

## References

- Spec 015 design: `docs/superpowers/specs/2026-04-29-orca-spec-015-brownfield-adoption-design.md`
- Spec 015 plan: `docs/superpowers/plans/2026-04-29-orca-spec-015-brownfield-adoption.md`
- Path-safety contract: `docs/superpowers/contracts/path-safety.md` (Class A + Class D)
- Phase 3.2 backlog item 2 (reference-set discovery origin): `docs/superpowers/notes/2026-04-27-phase-3-2-backlog.md`
