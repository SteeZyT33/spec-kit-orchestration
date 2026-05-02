# orca Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-04-09

## Active Technologies
- project-local Markdown files under `brainstorm/` plus existing spec artifacts under `specs/` (002-brainstorm-memory)

- Markdown command docs, Bash entrypoints, Python 3.10+ for deterministic file/runtime helpers + existing Spec Kit repo layout, `git`, Python standard library, current Orca command/launcher packaging (002-brainstorm-memory)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Markdown command docs, Bash entrypoints, Python 3.10+ for deterministic file/runtime helpers: Follow standard conventions

## Recent Changes
- 002-brainstorm-memory: Added Markdown command docs, Bash entrypoints, Python 3.10+ for deterministic file/runtime helpers + existing Spec Kit repo layout, `git`, Python standard library, current Orca command/launcher packaging

- 002-brainstorm-memory: Added Markdown command docs, Bash entrypoints, Python 3.10+ for deterministic file/runtime helpers + existing Spec Kit repo layout, `git`, Python standard library, current Orca command/launcher packaging

<!-- MANUAL ADDITIONS START -->

## Core invariant: orca is spec-system-agnostic

Orca works on top of **spec-kit**, **superpowers**, **openspec**, or
**bare** repos. The auto-generated "Active Technologies" section above
mentions spec-kit only because feature 002 happened to be a spec-kit
project; it does **not** mean orca itself is spec-kit-bound.

**Every feature path lookup MUST route through
`orca.core.host_layout`.** Never hardcode `specs/`,
`docs/superpowers/`, or any other host-specific path. Use:

```python
from orca.core.host_layout import from_manifest
layout = from_manifest(repo_root)
for fid in layout.list_features():
    feat_dir = layout.resolve_feature_dir(fid)
```

Adapters (`SpecKitLayout`, `SuperpowersLayout`, `OpenSpecLayout`,
`BareLayout`) live in `src/orca/core/host_layout/`. If a method you
need is missing from the protocol, add it to the protocol and to
every adapter — don't bypass.

For full conventions and testing guidance, see `CLAUDE.md` in the
repo root.

<!-- MANUAL ADDITIONS END -->
