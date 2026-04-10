# Contract: Brainstorm Memory Files

## Directory Layout

```text
brainstorm/
├── 00-overview.md
├── 01-topic-slug.md
├── 02-another-topic.md
└── ...
```

## Record Filename Contract

- format: `NN-topic-slug.md`
- `NN` is zero-padded to at least two digits and monotonically increasing using
  `max + 1`
- `topic-slug` must be readable and non-empty

## Record Header Contract

Each brainstorm record must expose stable metadata near the top of the file:

```text
# Brainstorm NN: Title

**Status**: active | parked | abandoned | spec-created
**Created**: YYYY-MM-DD
**Updated**: YYYY-MM-DD
**Downstream**: none | spec:<path-or-id> | feature-branch:<name>
```

The remainder of the file stays human-readable Markdown with required sections
defined by the brainstorm command.

## Record Body Contract

Each durable brainstorm record must contain these sections in order:

```text
## Problem
## Desired Outcome
## Constraints
## Existing Context
## Options Considered
## Recommendation
## Open Questions
## Ready For Spec
## Revisions
```

`## Revisions` is required even if it only contains `(none yet)` initially.

## Revision Entry Contract

Additive updates under `## Revisions` use this minimum shape:

```text
### YYYY-MM-DD - Update
[short revision summary or notes]
```

## Overview Contract

`brainstorm/00-overview.md` is generated from current brainstorm records and
must contain:

- title and last updated line
- sessions index table
- open threads section
- parked ideas section

## Regeneration Rules

- If `brainstorm/` exists but `00-overview.md` is missing, Orca must regenerate
  the overview from existing records.
- If numbering gaps exist, Orca must not reuse missing numbers.
- Overview regeneration must not mutate brainstorm record content.
