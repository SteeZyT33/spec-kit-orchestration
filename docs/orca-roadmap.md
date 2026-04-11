# Orca Roadmap

## Purpose

Describe Orca's workflow-system direction now that most of the foundation layer
has already landed.

## Current State

Orca is no longer just a normalized command bundle. It now has:

- durable brainstorm memory
- cross-review agent selection beyond a three-provider special case
- flow-state derived from repo artifacts
- split review artifacts
- explicit context handoffs
- capability packs for optional workflow behavior
- Matriarch for multi-lane supervision
- Evolve for tracking external patterns and wrapper-capability adoption

The main workflow-system subsystem still pending is the full-cycle
single-lane runner, `orca-yolo`.

## Strategic Direction

Orca should keep moving toward a provider-agnostic workflow system with three
clear layers:

1. durable workflow primitives
2. coordination and supervision
3. orchestration over those primitives

The important architectural rule is still the same:

**Do not make orchestration the foundation.**

## What Is Stable

The stable center of Orca is now:

- brainstorming and micro-spec intake
- assignment and review workflow
- durable repo-backed state
- optional capability boundaries
- conservative multi-lane supervision

That means future work should be judged by whether it strengthens those layers
instead of bypassing them.

## What Is Next

### 1. Finish `orca-yolo`

The next major subsystem is still the end-to-end single-lane runner. It should:

- start from durable brainstorm or spec artifacts
- resume from repo-backed state
- use split review artifacts and flow-state rather than inventing progress
- hand off cleanly into PR creation and review

### 2. Deepen review architecture

Orca already has code review, cross-review, PR review, and self-review. The
next refinement is to make those stages sharper and easier for both humans and
automation to consume.

### 3. Refine Matriarch and Evolve

Matriarch and Evolve are merged, but they are still early layers:

- Matriarch should keep improving lane supervision and delegated-work clarity
- Evolve should keep turning external patterns into explicit Orca follow-up work
- both should stay provider-agnostic and avoid becoming wrappers for one host
  runtime

## Adoption Posture

The right lesson from `cc-spex` is still architectural, not platform-specific.
Orca should keep taking:

- memory
- state
- review discipline
- self-evolution discipline

while still adapting heavily or rejecting:

- provider-specific runtime mechanics
- plugin substrate assumptions
- high-indirection layering that makes the system harder to reason about

## Near-Term Priorities

1. Implement `orca-yolo` on top of the already-merged workflow primitives.
2. Tighten how the merged subsystems compose and expose readiness.
3. Use `orca-evolve` to harvest only the highest-value external patterns.

## Decision Summary

Orca's next stage is not another command cleanup cycle. It is controlled
orchestration and system refinement on top of a now-real workflow foundation.
