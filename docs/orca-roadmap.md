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
- `orca-yolo` spec tightened and wired to Matriarch as its supervisory
  authority (contract-complete, runtime still to build)

Every primary workflow-system spec that was open during the upgrade program
has now shipped. What remains is runtime implementation of the `orca-yolo`
single-lane runner on top of the already-durable primitives, plus ongoing
composition tightening as the merged systems meet real multi-lane usage.

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

### 1. Build the `orca-yolo` runtime against the merged contracts

`009-orca-yolo` is contract-complete (spec, data-model, and three contracts
covering run state, stage model, and orchestration policies). The spec also
defines the Lane Agent Binding that links a supervised run to a Matriarch
lane. What remains is the runtime: a resumable single-lane driver that:

- consumes durable brainstorm, spec, flow-state, and review artifacts
  rather than reconstructing progress from chat memory
- supports both standalone and matriarch-supervised modes explicitly
- emits upward reports via the Lane Mailbox when supervised, per the
  Lane Agent contract
- stops on failing review gates, missing prerequisites, or unresolved
  clarification — not on a retry timer

The tightest first step is a contract-conformance harness, not a full
driver: something that can exercise each stage transition and verify it
writes into `005-orca-flow-state`, emits a `006-orca-review-artifacts`
output, and produces a `007-orca-context-handoffs` handoff.

### 2. Deepen review architecture

Orca already has code review, cross-review, PR review, and self-review. The
next refinement is to make those stages sharper and easier for both humans and
automation to consume. `EV-012 Reviewer Brief Artifact` is the specific
Evolve-tracked pattern to adopt here — a human-facing review brief distinct
from the split spec/plan/code/cross/pr artifacts 006 already owns.

### 3. Refine Matriarch and Evolve

Matriarch and Evolve are merged and stable, but they are early layers:

- Matriarch should keep improving lane supervision and delegated-work
  clarity, with the Lane Agent contract now normative and referenced from
  `009` supervised-mode behavior
- Evolve should keep turning external patterns into explicit Orca
  follow-up work; current open candidates are `EV-005 Self-Evolution
  Discipline`, `EV-012 Reviewer Brief Artifact`, and `EV-013
  Spec-Compliance-First Code Review`, plus the deferred `EV-011 Drift
  Reconciliation`
- both must stay provider-agnostic and avoid becoming wrappers for one
  host runtime

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

1. Build the `orca-yolo` runtime on top of the already-merged workflow
   primitives, starting with a contract-conformance harness before a full
   driver.
2. Tighten how the merged subsystems compose and expose readiness, with
   particular attention to Matriarch lane readiness and handoff edges.
3. Use `orca-evolve` to harvest only the highest-value external patterns —
   the current open inventory is the source of truth, not ad-hoc prose.

## Decision Summary

Orca's next stage is not another command cleanup cycle. It is controlled
orchestration and system refinement on top of a now-real workflow foundation.
