# Brainstorm: Orca Evolve

## Goal

Design a durable Orca self-evolution system that captures useful external
patterns, records adoption decisions, and turns worthwhile ideas into real Orca
work instead of letting them drift in chat history.

`orca-evolve` should make Orca's future upgrades intentional.

## Product Intent

The point is not to create a vague "research mode." The point is to give Orca
an explicit intake and decision system for external ideas.

That means Evolve should help answer:

- what external patterns do we still care about?
- where did each idea come from?
- did we decide to take it, adapt it, defer it, or reject it?
- where in Orca does it belong?
- has it turned into a spec, roadmap item, or capability pack?

This is how Orca avoids repeatedly rediscovering the same Spex ideas.

## Why This Matters

The repomix review already showed that Orca is harvesting from a system that is
larger and more internally disciplined than it first appeared.

Without Evolve, good ideas will continue to live in:

- chat transcripts
- one-off notes
- partial roadmap docs
- scattered feature specs

That is not enough once Orca itself becomes a workflow system with ongoing
internal evolution.

## Desired Operator Experience

The desired feeling is:

"I can review what Orca still wants to adopt, see which ideas are already
accounted for, and turn new harvest findings into concrete Orca work without
starting from scratch."

This suggests:

- a durable harvest inventory
- explicit adoption decisions
- clear links to destination specs/features
- a way to revisit or refresh older harvest entries

## Scope Shape

Evolve should likely cover three connected jobs:

1. intake
2. decision
3. mapping

Intake:

- capture an external idea/pattern
- record source and summary
- capture why it matters

Decision:

- direct take
- adapt heavily
- defer
- reject

Mapping:

- existing Orca spec
- future Orca spec
- capability pack
- roadmap/parking lot

## Spex-Specific Reality

The immediate source is Spex, and there are still worthwhile ideas left on the
field.

Examples already visible:

- self-evolution discipline itself
- sync/adoption reports
- more explicit upstream comparison workflow
- possibly deeper review layering
- maybe some targeted worktree ergonomics
- future harvest/research helpers
- thin Orca-native wrappers over external specialist skills

The new wrapper direction is important:

- Orca may want a `deep-optimize` entrypoint that routes to `autoresearch`
- later it may want `deep-research` and `deep-review` entrypoints with similar
  boundaries

Those should be tracked as adoption decisions, not silently absorbed as if
Orca owns the full external engine.

So Evolve should not pretend the current Orca upgrade captured everything.
It should preserve the remaining queue intentionally.

## Not Just Documentation

Important caution:

Evolve should not become only a documentation folder.

It needs enough structure that a maintainer can:

- add a new harvest entry
- update its adoption state
- map it to a real Orca destination
- tell which ideas are still unclaimed

That suggests a data model and workflow, not just prose.

## Relationship To Existing Docs

`docs/orca-harvest-matrix.md` is the seed, not the final system.

The harvest matrix is useful because it organizes take/adapt/avoid thinking, but
it is still a static synthesis artifact.

Evolve should probably absorb or operationalize:

- take/adapt/defer/reject
- source references
- target mappings
- status of adoption work
- follow-up spec or roadmap link

## Relationship To Future Deep Research

Evolve is adjacent to the future deep-research skill you mentioned, but they are
not the same.

- deep-research would gather and synthesize source material
- Evolve would record what Orca decided to do with that synthesis

That same pattern should apply to wrapper capabilities:

- external specialist system does the deep work
- Orca owns the wrapper name, routing, scoping, and artifact expectations
- Evolve records that ownership boundary explicitly

So Evolve should be able to consume structured research output later, but it
does not need to become the research engine itself.

## What Not To Overengineer

Strong caution areas:

- building a giant knowledge graph
- heavy sync automation before the adoption model is stable
- trying to fully automate repo comparison in v1
- making source ingestion magical or opaque
- forcing every small idea into a full spec immediately

The first version only needs to preserve adoption discipline and mapping.

## Likely V1 Shape

Best current instinct:

- durable harvest entry records
- explicit adoption statuses
- target mapping into existing/future Orca features
- one index/overview surface
- a light workflow for adding and updating entries
- enough attribution to revisit source reasoning later

## Open Questions

- What is the canonical storage model: one file per harvest entry, a registry,
  or both?
- Should Evolve own the harvest matrix, or sit alongside it?
- Should adoption entries be grouped by source repo, target subsystem, or both?
- What is the minimum useful decision vocabulary?
- When an idea is copied directly, how much source attribution should be
  required in the durable record?
- Should Evolve directly create new specs, or only point to them?

## Tentative Recommendation

Frame `011-orca-evolve` as Orca's adoption-control system:

1. capture external ideas durably
2. record explicit adoption decisions
3. map adopted ideas into Orca's real roadmap/spec structure

Then let future research/sync tooling plug into that system rather than making
Evolve itself do everything.
