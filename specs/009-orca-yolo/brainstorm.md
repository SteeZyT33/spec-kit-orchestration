# Brainstorm: Orca YOLO

## Problem

Orca needs a full-cycle runner, but only after the rest of the workflow system
is real. The challenge is not "how do we automate more." The challenge is "how
do we orchestrate durable workflow primitives without collapsing them back into
one opaque mega-command."

## Desired Outcome

`orca-yolo` should let a user start from a durable idea/spec artifact and run
through planning, implementation, review, and PR-ready completion with:

- resumable state
- explicit stop conditions
- configurable ask levels
- explicit stage transitions
- durable run artifacts

## What This Feature Is Not

- not a replacement for brainstorm memory
- not a replacement for flow state
- not a replacement for review artifacts
- not a replacement for context handoffs
- not a hidden provider-specific automation engine

## Favored Direction

Treat `orca-yolo` as a downstream orchestration layer over stable upstream
workflow primitives. The first version should define:

- run stages
- durable run records
- stop and resume behavior
- ask policy
- PR-ready completion policy

It should not overbuild agent choreography or speculative autonomous loops in
the first pass.

## Likely Start Modes

- start from brainstorm memory
- start from a spec (spec-lite records excluded in v1; adoption records always excluded)
- resume a prior run
- start from a later stage only when upstream artifacts already exist

## Likely Stage Model

- brainstorm
- specify
- plan
- tasks
- implement
- self-review
- code-review
- cross-review
- pr-ready or pr-create

## Likely Durable Outputs

- run record
- current stage and outcome
- links to upstream/downstream artifacts
- stop reason when blocked or paused
- final summary

## Hard Questions

- how much autonomy should the first version have versus later phases?
- should PR creation be in scope now or only PR-ready completion?
- how should retry/fix loops be bounded so `orca-yolo` stays safe?
- what is the minimum useful run-state shape that can actually support resume?

## Favored Answer

Bias conservative. The first version should support:

- stage progression
- durable state
- resume
- explicit stops
- optional PR-ready finish

Full autonomous fix loops should remain bounded and secondary to explicit review
gates.
