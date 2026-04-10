# Contract: `/speckit.orca.brainstorm`

## Purpose

Define the externally visible workflow contract for Orca's brainstorm command
after brainstorm memory is introduced.

## Inputs

- optional free-form problem statement
- optional `--feature <id>` target for existing feature refinement

## Artifact Destination Precedence

Use the first matching destination model:

1. **Existing feature refinement**: if `--feature <id>` is provided, or if the
   active branch clearly resolves to an existing feature and the user is
   refining that feature, write the mutable feature artifact at
   `specs/<feature>/brainstorm.md`.
2. **New durable brainstorm memory**: if the session is new idea capture or a
   revisit of durable brainstorm memory rather than feature refinement, write to
   `brainstorm/NN-topic-slug.md` and regenerate `brainstorm/00-overview.md`.
3. **Legacy inbox fallback**: use `.specify/orca/inbox/brainstorm-<timestamp>.md`
   only for intentionally temporary scratch capture when the user does not want
   durable brainstorm memory yet.

`brainstorm/` is the durable memory system. `specs/<feature>/brainstorm.md`
remains the mutable refinement artifact for an already identified feature.

## Required Behavior

1. Resolve whether the session is:
   - new idea capture
   - existing feature refinement
   - better suited for `micro-spec`
2. Read enough repo/spec context to produce a useful brainstorm artifact.
3. Write or update durable brainstorm memory when the user chooses to save a
   meaningful session.
4. Refresh `brainstorm/00-overview.md` after any brainstorm memory write or
   update.
5. Recommend the next command without entering implementation directly.

## Save / Update Outcomes

### New brainstorm

- create `brainstorm/NN-topic-slug.md`
- populate required sections and metadata
- regenerate `brainstorm/00-overview.md`

### Revisit existing brainstorm

- surface likely related brainstorm candidates
- let the user choose `update existing` or `create new`
- preserve existing brainstorm content if updating
- regenerate `brainstorm/00-overview.md`

### Incomplete session

- default to not saving trivial sessions
- allow meaningful incomplete sessions to be saved with `parked` or `abandoned`
  status

## Meaningful vs Trivial Session Heuristic

Treat a session as meaningful by default when at least one of these is true:

- two or more core sections contain non-trivial content:
  `Problem`, `Desired Outcome`, `Options Considered`, `Recommendation`, or
  `Open Questions`
- the substantive body across those sections is at least roughly 100
  non-whitespace characters
- the user explicitly asks to preserve the session

Treat a session as trivial by default when none of those conditions hold.

## Explicit Non-Behavior

- must not route directly to `/speckit.implement`
- must not silently overwrite an existing brainstorm record
- must not require provider-specific session files

## Outputs To User

- brainstorm artifact path
- overview path when relevant
- recommended next command
- blocking open questions, if any
