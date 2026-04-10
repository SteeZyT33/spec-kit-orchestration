# Research: Orca Matriarch

## Key Insight

The highest-value version of Matriarch is not an "agent swarm manager." It is a
durable multi-lane supervisor that makes active Orca work legible and
coordinated.

## Decisions

### Decision: Model managed lanes explicitly

Reasoning:

- branches alone are too weak
- worktrees alone are too low-level
- specs alone do not capture ownership or operational state

Conclusion:

- use a lane record as the canonical orchestration unit

### Decision: Prefer metadata-first coordination over inference-first coordination

Reasoning:

- git state and artifact discovery are useful, but incomplete
- multi-lane supervision needs declared dependencies and ownership
- explicit metadata is easier to test and less magical

Conclusion:

- lane registry is required

### Decision: Keep worktree execution delegated

Reasoning:

- Orca already has worktree runtime helpers
- duplicating creation/cleanup logic in Matriarch would cause drift
- Matriarch’s job is lane coordination, not low-level git runtime ownership

Conclusion:

- consume `001` worktree runtime instead of rebuilding it

### Decision: Make `009-orca-yolo` optional in v1

Reasoning:

- Matriarch must be useful even before full single-lane automation is mature
- otherwise `010` becomes blocked on `009`
- coordination value is already real without automatic lane execution

Conclusion:

- integrate with `009` later as an optional worker/runtime

### Decision: Keep hooks narrow and visible

Reasoning:

- hooks can add real operator value for context refresh and lane summaries
- too many hooks quickly create opaque behavior and accidental coupling

Conclusion:

- define a small hook set and log each execution explicitly
