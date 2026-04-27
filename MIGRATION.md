# Migration Guide

## Migrating from v2.0 (spec-kit-orca) to v2.1 (orca)

### Required changes for downstream callers

- Package name: `pip install spec-kit-orca` → `pip install orca`
- Python imports: `from speckit_orca import X` → `from orca import X`
- CLI: `speckit-orca <args>` → `orca <args>` (or `python -m orca.cli <args>`)
- State directory: `.specify/orca/` → `.orca/`
- Slash commands in scripts: `/speckit.orca.review-code` → `/orca:review-code`

### Removed surfaces (no replacement)

- `speckit.orca.yolo`, `.matriarch`, `.spec-lite`, `.adopt`, `.assign` — these commands no longer exist. See CHANGELOG v2.1.0 for removal rationale.
