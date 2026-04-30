# Orca Roadmap

> **Note**: The pre-Phase-1 roadmap (Matriarch, yolo, capability packs, Evolve, multi-lane supervision) has been archived to `docs/archive/orca-roadmap-pre-toolchest.md`. Those subsystems were removed during the Phase 1 strip because they did not earn their keep.

The current direction is documented in:

- **`docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md`** — toolchest-with-native-perf-lab-integration design (the v1 north star)
- **`docs/superpowers/plans/2026-04-26-orca-phase-1-rename-and-strip.md`** — Phase 1: package rename + kill-list strip
- **`docs/superpowers/plans/2026-04-27-orca-phase-2-capability-cores-and-cli.md`** — Phase 2: capability cores + CLI

## Phase Plan (Summary)

- **Phase 1** (shipped): rename `spec-kit-orca` → `orca`, strip the kill-list (yolo, matriarch, spec-lite, adopt, assign, capability-packs, evolve, onboard).
- **Phase 2** (shipped): six v1 capabilities with JSON Schemas, Python CLI, structurally typed reviewer protocol.
- **Phase 3** (next): plugin formats (Claude Code skills + Codex AGENTS.md fragments) + personal SDD opinion-layer slash commands.
- **Phase 4** (deferred): perf-lab integration shim — translates orca capability outputs into perf-lab events. Orca remains pull-not-push.
- **Phase 5** (hardening): test coverage, schema CI gates, live-LLM nightly runs.

## Identity

Orca is a repo-backed capability library for agentic engineering governance. It does not execute host runtimes. Hosts pull Orca capabilities and translate outputs into their own state.

Orca is NOT a scheduler, worker runtime, supervisor, presence system, or control plane. Each capability returns a JSON envelope; hosts decide what to do with it.
