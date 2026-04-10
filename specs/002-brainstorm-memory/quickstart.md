# Quickstart: Orca Brainstorm Memory

## Goal

Validate that Orca can persist, update, and index brainstorm memory in a
provider-agnostic way.

## Setup

1. Work on branch `002-brainstorm-memory`.
2. Use a disposable repo area or temporary branch state for manual checks.
3. Ensure Python helper changes run with `uv run` and shell wrappers pass
   `bash -n` if touched.

## Scenario 1: First saved brainstorm

1. Start a brainstorm for a new idea.
2. Save the session as a meaningful brainstorm.
3. Verify:
   - `brainstorm/` is created if it did not exist
   - `brainstorm/01-*.md` exists
   - `brainstorm/00-overview.md` exists
   - overview index contains the new brainstorm

## Scenario 2: Parked idea

1. Run a brainstorm that does not move to spec.
2. Save it intentionally as parked.
3. Verify:
   - record status is `parked`
   - overview lists it correctly
   - open questions appear in the overview rollup

## Scenario 3: Revisit/update

1. Start a brainstorm on a topic related to an existing brainstorm.
2. Verify Orca surfaces likely related brainstorms.
3. Choose `update existing`.
4. Verify:
   - prior brainstorm content is preserved
   - a dated update section is appended or equivalent additive update is made
   - overview reflects the updated record

## Scenario 4: Downstream link to spec

1. Take a saved brainstorm into `speckit.specify`.
2. Mark the brainstorm as `spec-created` with the resulting spec reference
   during or immediately after the brainstorm-side workflow update.
3. Verify:
   - record shows the downstream link
   - overview index shows the linked spec

## Scenario 5: Overview recovery

1. Remove `brainstorm/00-overview.md`.
2. Run overview regeneration.
3. Verify the rebuilt overview matches the existing records and does not alter
   them.
