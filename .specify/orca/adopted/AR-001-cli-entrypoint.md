# Adoption Record: AR-001: CLI entrypoint

**Status**: adopted
**Adopted-on**: 2026-04-15
**Baseline Commit**: cad775f

## Summary
Argument routing and subcommand dispatch for the speckit-orca CLI. Predates every named spec; provides the single operator-facing entry point into the package.

## Location
- src/speckit_orca/cli.py
- speckit-orca

## Key Behaviors
- Dispatches to subcommand modules (brainstorm-memory, evolve, matriarch, flow-state, spec-lite, adoption) via argparse subparsers
- Loads integration metadata from .specify/integration.json and .specify/init-options.json on startup
- Provides --help, --version, and per-subcommand help text for operator self-service

## Known Gaps
No machine-readable error exit codes beyond 0/1/2 — some callers expect structured failure taxonomy
