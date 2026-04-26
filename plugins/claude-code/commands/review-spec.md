---
description: Cross-only adversarial review of a clarified spec. Validates cross-spec consistency, feasibility, security implications, dependency risks, and industry patterns against the feature's spec.md.
handoffs:
  - label: Revise The Spec
    agent: speckit.specify
    prompt: Spec review found issues — revise the spec before planning
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Purpose

`review-spec` is 012's cross-only spec review. A different agent from the
spec author examines the clarified `spec.md` for consistency, feasibility,
security, dependencies, and industry-pattern alignment. There is no
self-pass — spec review is adversarial by design.

## Workflow Contract

- Read the feature's `spec.md` (and `brainstorm.md` / `plan.md` if present
  for context).
- Produce a structured review artifact at
  `<feature-dir>/review-spec.md` with cross-pass findings.
- Do not implement anything. Do not modify the spec.
- If the spec has critical issues, record them and recommend revision
  before planning proceeds.

## Outline

1. Resolve the feature directory from the user input or current context.
2. Read `spec.md` plus any supporting artifacts.
3. Evaluate against:
   - Cross-spec consistency (does this conflict with other specs?)
   - Feasibility (can this actually be built with the stated approach?)
   - Security implications (OWASP top 10, auth boundaries, data exposure)
   - Dependency risks (upstream contracts consumed, downstream impact)
   - Industry patterns (are there better-known approaches?)
4. Write findings to `<feature-dir>/review-spec.md`.
5. Report verdict: `ready`, `needs-revision`, or `blocked`.

## Guardrails

- This is a CROSS-only review. The reviewing agent must be different from
  the agent that authored the spec. If you are the author, say so and
  recommend routing to a different agent via the cross-pass mechanism.
- Do not conflate spec review with code review. Spec review examines the
  DESIGN artifact, not implementation code.
- If no `spec.md` exists for the target feature, stop and explain —
  do not fabricate a review against missing input.
