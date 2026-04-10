# Review: Orca Capability Packs

## Scope

- Feature: `008-orca-capability-packs`
- Branch: `008-orca-capability-packs-impl`
- Commit under review: `23965b4` plus local review-fix follow-ups
- Cross-review agent: `opencode` (`claude-opus-4.6`)

## Findings

### No remaining feature-specific blocking findings

The first external pass found real issues in the initial implementation:

- `flow-state` was heuristically enabled even when `specs/` was absent
- runtime validation did not enforce non-empty `owned_behaviors`
- `scaffold` could raise an unhandled `FileNotFoundError`
- disabling an `always-on` pack was warned but not treated as invalid

Those issues were fixed on this branch before finalizing this review.

## Cross-Review Summary

`opencode` produced a substantive first-pass review and the resulting fixes were
applied locally. A second pass on the updated diff did not surface any new
feature-specific correctness, packaging, or contract issues.

## Verification

- `uv run pytest tests/test_capability_packs.py tests/test_brainstorm_memory.py`
- `uv run python -m py_compile src/speckit_orca/capability_packs.py`
- `uv run python -m speckit_orca.capability_packs list --root .`
- `uv run python -m speckit_orca.capability_packs show yolo --root . --json`
- `uv run python -m speckit_orca.capability_packs validate --root .`
- `uv run python -m speckit_orca.capability_packs scaffold --root /tmp/orca-capability-packs-UB4gEQ`
- `uv run --with build python -m build`
- `git diff --check`
