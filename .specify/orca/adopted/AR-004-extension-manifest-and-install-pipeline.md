# Adoption Record: AR-004: Extension manifest and install pipeline

**Status**: adopted
**Adopted-on**: 2026-04-15
**Baseline Commit**: cad775f

## Summary
How speckit.orca registers with Claude Code / Codex / Gemini / Cursor via the extension manifest system. The install path discovers extension.yml, writes per-integration manifests under .specify/integrations/, and installs companion extensions (superb, verify, reconcile, status).

## Location
- extension.yml
- .specify/integrations/claude.manifest.json
- .specify/integrations/speckit.manifest.json
- src/speckit_orca/assets/speckit-orca-main.sh
- Makefile

## Key Behaviors
- extension.yml declares the speckit.orca extension with commands, hooks, companions, and tags — consumed by 'specify extension add orca'
- Install script (speckit-orca-main.sh) is the user-facing bootstrap: installs the extension via specify CLI then refreshes companion catalogs
- Per-integration .manifest.json files record file hashes for install-time verification — NOT command registration
- Makefile target 'tool-install' is the dev-machine equivalent of running the bootstrap directly

## Known Gaps
No manifest version check — extension.yml schema_version is static '1.0' even though the command surface has shifted multiple times
