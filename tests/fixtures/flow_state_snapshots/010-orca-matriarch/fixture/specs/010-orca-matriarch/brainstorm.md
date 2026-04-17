# Brainstorm: Orca Matriarch

## Goal

Design a practical multi-spec orchestrator for Orca that lets one operator
manage several active feature lanes from one interface without manually
juggling branch state, worktrees, assignments, and review readiness.

`orca-matriarch` should feel like the control plane for multi-spec development,
not like a giant autonomous agent platform.

## Product Intent

The main job is to supervise and coordinate multiple spec implementations end
to end:

- know which specs are active
- know who or what owns each lane
- know which branch and worktree each lane uses
- know which stage each lane is in
- know what is blocked, waiting, ready for review, or ready for PR
- expose the next sensible operator action from one place

This is not the same as `orca-yolo`.

- `orca-yolo` is a single-lane runner
- `orca-matriarch` is a multi-lane supervisor

The first version should prioritize:

- visibility
- safe coordination
- durable lane state
- logical branch/worktree management
- explicit checkout and hook behavior

The first version should avoid:

- pretending to own the whole repo exclusively
- silently moving work between lanes
- spawning uncontrolled autonomous loops
- hiding dependency or review problems behind automation

## Operator Experience

The desired user feeling is:

"I can open one Matriarch view and understand the state of all active specs,
see what each lane is doing, move into the right worktree cleanly, and know
what should happen next."

That implies one primary interface with supporting commands, not a scattered
set of unrelated helpers.

Likely operator capabilities:

- list active lanes
- inspect one lane deeply
- create/register a lane from a spec
- assign or reassign an agent/owner
- assign/create/record a worktree
- switch or print the correct checkout target
- mark dependencies between lanes
- surface blocked/ready states
- aggregate review and PR readiness
- invoke or hand off to lane-local execution tools when appropriate

## Core Model

Matriarch should think in lanes, not just branches.

A lane likely represents:

- one spec or feature
- one branch identity
- zero or one active worktree
- zero or one current assignee
- one current workflow stage
- one readiness state
- zero or more dependencies
- links to artifacts and reviews

That suggests a durable registry or lane ledger rather than pure git
inspection.

Likely durable concepts:

- lane record
- assignment record
- dependency graph
- lane events/history
- readiness snapshot
- checkout target

## Boundaries

Matriarch should not own everything.

Other subsystems still own their domains:

- `001` owns worktree runtime behavior
- `005` owns stage/state semantics
- `006` owns review artifact semantics
- `007` owns context handoff semantics
- `009` may later own automated single-lane execution

Matriarch consumes these and presents a multi-lane supervisory layer.

That means the first version should mostly:

- read durable artifacts
- write lane-management metadata
- orchestrate safe transitions
- expose decisions and next actions

It should not reimplement all lower-level workflow logic.

## Worktree And Branch Management

This is one of the highest-risk areas and needs discipline.

Desired behavior:

- a lane can declare whether it requires a worktree
- Matriarch can create or attach a worktree intentionally
- branch, worktree path, and lane id stay linked durably
- operator can ask "where should I go for this lane?"
- operator can safely resume work from the right checkout

Important design principles:

- never guess destructively
- prefer explicit lane metadata over ad hoc discovery
- tolerate manual git activity but detect drift
- preserve the ability to operate without worktrees when appropriate

Questions to settle later in planning:

- Should Matriarch create branches directly or delegate to existing Orca
  worktree/runtime helpers?
- Should lane creation require a spec id up front?
- Should one lane ever support multiple worktrees, or is that out of scope for
  v1?
- What hooks run on lane creation, checkout, reassignment, review-ready, and
  PR-ready transitions?

## Checkout And Hook Behavior

The user explicitly wants checkout systems and hooks, so this cannot stay vague.

Potential hook surfaces:

- lane created
- branch created
- worktree created/attached
- lane entered / checkout requested
- lane stage changed
- lane blocked
- lane review-ready
- lane PR-ready
- lane archived or closed

Potential hook purposes:

- update status artifacts
- refresh agent context
- print lane-specific instructions
- verify clean/expected git state
- regenerate summary/index outputs

Important constraint:

hooks should be transparent and inspectable, not hidden magic.

## One Interface

The user wants one interface for managing multiple specs end to end.

That likely means Matriarch needs a primary surface such as:

- a command family with one main status/dashboard entry
- lane-specific subcommands
- a summary artifact or dashboard file

The first version probably does not need a fancy TUI.
It does need a coherent operator surface.

Minimal viable interface ideas:

- `matriarch status`
- `matriarch lane list`
- `matriarch lane show <lane>`
- `matriarch lane create <spec>`
- `matriarch lane assign <lane> --agent ...`
- `matriarch lane worktree <lane> ...`
- `matriarch lane checkout <lane>`
- `matriarch lane ready`
- `matriarch lane block`

The key point is not exact command names.
The key point is: one predictable supervisory interface.

Refinement direction:

- keep the v1 surface intentionally small
- prefer `register`, `show`, `list`, `assign`, `depend`, `checkout`, and
  `deploy`
- avoid adding broad command families until lifecycle and registry semantics
  are stable

## Dependency Management

Dependencies are central because the user is actively coordinating multiple
specs in parallel.

Matriarch should let the operator declare things like:

- `007` depends on `006` review artifact contract
- one lane is blocked pending another lane's review or merge
- a lane can proceed in partial mode but not finalize

This should be explicit metadata, not only inferred from numbering.

Likely dependency states:

- none
- soft dependency
- hard blocker
- satisfied
- waived/overridden with rationale

Refinement direction:

- dependency declarations should target concrete conditions, not vague prose
- likely targets are lane existence, stage reached, review-ready, PR-ready, and
  merged
- dependency status should be inspectable without reading chat history

## Readiness And Gates

Matriarch becomes useful when it can answer:

- what is active?
- what is blocked?
- what is ready for implementation?
- what is ready for review?
- what is ready for PR?
- what is waiting on another lane?

This depends on durable inputs from:

- flow state
- review artifacts
- worktree/lane metadata
- maybe PR metadata later

The first version should avoid over-scoring or fake confidence.
If evidence is missing, Matriarch should say "unknown" or "missing evidence."

## Tmux Deployment

The user is right that multi-lane coordination gets much more useful once there
is a real deployment substrate for active agent work.

For Matriarch, tmux should be treated as:

- an optional lane deployment attachment
- one session per lane in v1
- explicit launch/attach/inspect behavior
- visible state, never hidden magic

Tmux should not be treated as:

- proof that work is healthy
- proof that work is complete
- a replacement for lane lifecycle or readiness state
- a general-purpose swarm scheduler

## What Not To Overengineer

Strong caution areas:

- full autonomous multi-agent execution
- complex scheduling algorithms
- dynamic optimization of agent allocation
- too many hook layers
- rich UI before the data model is stable
- trying to replace git, GitHub, or existing review commands

The first version only needs to make multi-spec development manageable and
legible.

## Likely V1 Shape

Best current instinct for v1:

- durable lane registry
- lane/dependency model
- branch and worktree attachment rules
- checkout helper behavior
- hook points for lane lifecycle events
- one supervisory status surface
- readiness aggregation from existing workflow artifacts

That would already solve a lot of the current pain without turning Matriarch
into an overbuilt orchestration platform.

## Open Questions

- Is Matriarch a command suite, a registry plus command suite, or a dashboard
  plus command suite?
- What is the canonical lane id: spec id, branch, or separate identifier?
- Should lane creation be allowed before a full spec exists?
- How much write authority should Matriarch have over git state in v1?
- Should checkout behavior ever auto-switch the shell, or should it only print
  the target and commands?
- Which hook events are truly required for v1 versus nice-to-have?
- Should Matriarch own agent assignment directly or just record/operator-guide
  it?
- When `009-orca-yolo` exists, does Matriarch invoke it directly or simply
  record that a lane is delegated to YOLO?

## Tentative Recommendation

Frame `010-orca-matriarch` as a conservative supervision system with three
layers:

1. lane registry and dependency model
2. branch/worktree/checkout coordination
3. readiness and next-action dashboard

Then treat deeper multi-agent automation as a later extension, not the v1
foundation.
