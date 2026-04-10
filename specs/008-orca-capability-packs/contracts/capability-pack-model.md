# Contract: Capability Pack Model

## Purpose

Define the minimum Orca capability-pack shape.

## Required Fields

- pack id
- purpose
- affected commands
- prerequisites
- activation mode
- maturity/status
- owned behaviors

## Initial Runtime Surface

- Built-in pack registry lives in `src/speckit_orca/capability_packs.py`
- Optional repo-local activation overrides live in
  `.specify/orca/capability-packs.json`
- Effective pack state is inspectable with
  `uv run python -m speckit_orca.capability_packs list --root .`

## Rule

Capability packs must describe real optional cross-cutting behavior, not simply
rename existing commands.
