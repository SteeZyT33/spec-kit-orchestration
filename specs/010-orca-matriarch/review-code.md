# Code Review: Orca Matriarch

## Scope

- Feature: `010-orca-matriarch`
- Branch: `010-orca-matriarch-impl`
- Runtime surface reviewed:
  - [matriarch.py](../../src/speckit_orca/matriarch.py)
  - [orca-matriarch.sh](../../scripts/bash/orca-matriarch.sh)
  - [matriarch.md](../../commands/matriarch.md)
  - [README.md](../../README.md)
  - [test_matriarch.py](../../tests/test_matriarch.py)

## Findings

### No remaining local blocking findings

The implementation now matches the conservative `010` contracts closely enough
for a first shipping pass:

- lane state is file-backed and revisioned
- lane-file writes are committed under the same registry lock instead of racing
  outside it
- dependencies are evaluated rather than merely stored
- mailbox and report events share one envelope with explicit ACK state
- delegated work uses a claim token plus locked writes, not just unlocked file
  replacement
- `direct-session` is first-class in the lane deployment model

## Issues Found And Fixed During Review

- corrected the latent `lane_id` / `spec_id` mix-up in `assign_lane`
- fixed the fallback flow-state shape to use `current_stage`
- hardened `stage_reached` dependency evaluation against unknown upstream stage
  values
- moved lane-file persistence under the same lock/revision step as registry
  updates
- recorded initial assignment history on lane registration when an owner is
  supplied
- made ACK events carry acknowledged state in both mailbox and report queues
- added `completed_at` for delegated-work completion visibility

## Verification

- `uv run python -m py_compile src/speckit_orca/matriarch.py`
- `uv run pytest tests/test_matriarch.py tests/test_context_handoffs.py tests/test_capability_packs.py`
- `bash -n scripts/bash/orca-matriarch.sh`
- disposable manual lane scenario covering:
  - lane registration
  - dependency satisfaction after upstream registration
  - startup ACK reporting
  - delegated-work creation
  - status summary output
