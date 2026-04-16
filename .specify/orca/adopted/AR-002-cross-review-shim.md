# Adoption Record: AR-002: Cross-review shim

**Status**: adopted
**Adopted-on**: 2026-04-15
**Baseline Commit**: cad775f

## Summary
Pre-012 implementation of cross-review coordination via bash + Python bridge. Superseded in design by 012's three-artifact review model but the shim remains in scripts/bash/ as the actual review invocation pathway until 012's runtime subsumes it.

## Location
- scripts/bash/crossreview.sh
- scripts/bash/crossreview-backend.py

## Key Behaviors
- bash launcher detects tmux and can split a pane for the reviewer agent; otherwise runs in foreground
- backend dispatches to the selected agent (codex, claude, gemini, opencode, cursor-agent) via adapter modules
- agent selection falls through a tier system (tier-1 supported-auto, tier-2 supported-manual, tier-3 known-unsupported)
- writes reviewer output to a specified --output path using a --schema-file for structured response shape

## Known Gaps
Cross-pass routing policy lives here today; 012's runtime may formalize it and migrate selection logic elsewhere
