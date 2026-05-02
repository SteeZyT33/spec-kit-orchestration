# Orca — Agent Guidelines

> **Read this before touching code.** It's short on purpose.

## Core invariant: orca is spec-system-agnostic

Orca is **not a spec-kit tool**. It works on top of any of these:

- **spec-kit** — `specs/<NNN-name>/{spec.md,plan.md,tasks.md,...}`
- **superpowers** — `docs/superpowers/specs/<feature-id>/...`
- **openspec** — its own convention
- **bare** — repos with no SDD framework at all

The host system is detected at adoption time and recorded in
`.orca/adoption.toml`. **Every feature path lookup MUST route through
`orca.core.host_layout`.** Never hardcode `specs/`, `docs/superpowers/`,
or any other host-specific path in:

- collectors (TUI, flow_state, anything that walks features)
- review pipelines
- slash command resolvers
- new code, period

If you're about to write `repo_root / "specs"`, stop. Use
`host_layout.list_features()` and `host_layout.resolve_feature_dir(fid)`
instead. The adapters (`SpecKitLayout`, `SuperpowersLayout`,
`OpenSpecLayout`, `BareLayout`) live in `src/orca/core/host_layout/`.

`from_manifest(repo_root)` reads `.orca/adoption.toml` and returns the
right adapter; fall back to `detect(repo_root)` for unadopted repos.

This invariant is the entire reason orca exists. Violating it makes
the tool useless to anyone not on spec-kit.

## Other foundations

- **Read-only by default.** Mutating actions live behind `orca-cli`
  subprocesses, not direct file writes. Even the TUI's c/o/e
  keybindings shell out instead of poking files.
- **Path safety.** Validate every path that crosses a public surface
  via `orca.core.path_safety` (six core invariants — see
  `docs/superpowers/contracts/path-safety.md`).
- **Capability versioning.** Every capability carries a
  `version: <semver>` field; bump on contract changes.
- **Reversible adoption.** `orca-cli apply --revert` must restore
  byte-identical originals.

## Workflow conventions in this repo

- Specs live in `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- Plans live in `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
- Brainstorming + writing-plans + subagent-driven-development +
  ralph-loop are the active development primitives (superpowers
  plugin). Use them.
- Feature work lands on a stacked branch off the latest
  unmerged-but-approved branch (e.g., `tui-v2-impl` was stacked on
  `tui-color`).
- Commit messages are conventional commits with subject ≤72 chars.

## Tests

- `uv run python -m pytest -q` — full suite
- TDD discipline: every GREEN had a RED first
- Pilot harness for TUI integration tests; pure-function collectors
  tested without Textual

## Host-aware reminder for agents

Before writing any code that reads features, reviews, or constitutions:

1. `from orca.core.host_layout import from_manifest, detect`
2. `layout = from_manifest(repo_root)` (or `detect(repo_root)` if no
   `.orca/adoption.toml` yet)
3. Use `layout.list_features()`, `layout.resolve_feature_dir(fid)`,
   `layout.review_artifact_dir()`, `layout.constitution_path()`,
   `layout.agents_md_path()`

If a layout adapter is missing a method you need, **add the method to
the protocol and every adapter**, don't bypass.
