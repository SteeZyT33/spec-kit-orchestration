# Quickstart: Orca Capability Packs

## Goal

Validate that Orca can describe optional workflow behavior through explicit
pack boundaries without recreating trait complexity.

## Scenario 1: Define a pack

1. Run `uv run python -m speckit_orca.capability_packs list --root .`.
2. Verify at least one realistic pack includes explicit purpose, affected
   commands, prerequisites, and activation mode.

## Scenario 2: Core remains understandable

1. Run `uv run python -m speckit_orca.capability_packs show review --root .`.
2. Verify the review lifecycle remains core and always-on rather than hidden
   behind optional pack activation.

## Scenario 3: Downstream behavior is not treated as foundation

1. Run `uv run python -m speckit_orca.capability_packs show yolo --root .`.
2. Verify it is classified as downstream and experimental-only rather than foundational.

## Scenario 4: Override activation remains inspectable

1. Run `tmpdir=$(mktemp -d /tmp/orca-capability-packs-smoke-XXXXXX)`.
2. Run `uv run python -m speckit_orca.capability_packs scaffold --root "$tmpdir"`.
3. Review `"$tmpdir"/.specify/orca/capability-packs.json`.
4. Run `uv run python -m speckit_orca.capability_packs validate --root "$tmpdir"`.
5. Verify the helper accepts the manifest and still reports `yolo` as disabled unless explicitly enabled.
