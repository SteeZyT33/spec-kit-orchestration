# Contract: Pack Activation

## Purpose

Define how Orca represents whether a capability pack is active.

## Activation Modes

- `always-on`
- `config-enabled`
- `experimental-only`

## Rules

- experimental packs must never activate silently
- core behavior should not require pack activation to remain understandable
- pack activation should be inspectable from repo artifacts or config

## Runtime Representation

- Activation overrides are read from `.specify/orca/capability-packs.json`
- Manifest entries may be either:
  - `true` / `false`
  - `{ "enabled": true|false, "reason": "..." }`
- `always-on` packs ignore disable attempts during resolution and emit a warning; validation also reports those disable attempts as invalid
- `experimental-only` packs stay disabled until explicitly opted in by manifest
