# Research: Orca Evolve

## Key Insight

Orca no longer needs only a roadmap. It needs a durable adoption-control system
for external patterns.

## Decisions

### Decision: Make adoption, not research, the core domain

Reasoning:

- research sources will vary over time
- the stable Orca need is preserving what was decided and why
- this keeps Evolve useful even when research happens elsewhere

Conclusion:

- Evolve owns adoption records and mappings

### Decision: Use a file-per-entry model with a secondary index

Reasoning:

- individual ideas need independent history and linking
- files are easy to review and edit
- an index is still useful for operator overview

Conclusion:

- one durable entry per idea, plus an overview file

### Decision: Keep the decision vocabulary intentionally small

Reasoning:

- too many statuses create taxonomy noise
- the main goal is preserving actionable decisions, not perfect classification

Conclusion:

- use direct-take, adapt-heavily, defer, reject in v1

### Decision: Treat Spex as the first source, not the only source

Reasoning:

- current value comes from Spex
- future Orca evolution will likely learn from more than one repo/system

Conclusion:

- source model must be repo-agnostic
