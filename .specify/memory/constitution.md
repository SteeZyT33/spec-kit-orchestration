# Spec Kit Orca Constitution

## Core Principles

### I. Provider-Agnostic Orchestration
Orca features MUST work across supported agent providers unless a limitation is explicitly documented. Provider-specific behavior belongs behind adapters, integration wrappers, or clearly labeled extension points, not in the core workflow contract.

### II. Spec-Driven Delivery
New workflow capabilities MUST be introduced through a concrete spec, plan, and task sequence before implementation. Micro-spec shortcuts are allowed only when they still preserve an explicit plan, implementation record, verification step, and review artifact.

### III. Safe Parallel Work
Worktree and lane operations MUST favor isolation, metadata integrity, and recoverability. Parallel-agent features MUST not silently overwrite lane state, MUST preserve auditable metadata, and MUST degrade safely when lane state is ambiguous.

### IV. Verification Before Convenience
Every meaningful change MUST include an appropriate verification step: syntax check, test, smoke test, or documented manual verification when automation is not practical. Review tooling, cross-review, and self-review workflows MUST report uncertainty rather than hide it.

### V. Small, Composable Runtime Surfaces
Core runtime helpers, launchers, and templates SHOULD stay simple, inspectable, and scriptable. Prefer plain files, stable CLI contracts, and additive changes over opaque automation or hidden state.

## Operational Constraints

- Bash helpers MUST remain compatible with standard workstation environments where practical; GNU-only behavior requires an explicit fallback or documented constraint.
- Python tooling in this repo MUST fail with clear stderr diagnostics when startup requirements are missing.
- Configuration and memory artifacts under `.specify/` MUST contain project-real values, not unexpanded template placeholders, once the repo is initialized.
- Packaging, installers, and launchers MUST surface non-zero exit status on installation or refresh failures so automation can trust them.

## Delivery Workflow

1. Specify the feature or workflow change before implementation.
2. Produce the implementation plan and task breakdown before substantial code changes.
3. Prefer test-driven or verification-driven development where practical; when tests are not feasible, document the manual verification path.
4. Run self-review and code-review or cross-review before finalizing substantial workflow changes.
5. Capture follow-up work explicitly instead of burying it in comments or leaving silent drift.

## Governance
This constitution overrides conflicting local process notes for this repository. PRs, plans, and reviews MUST flag violations explicitly. Amendments require updating this file, documenting the reason in repo history, and ensuring dependent templates or commands stay aligned with the new rule set.

**Version**: 1.0.0 | **Ratified**: 2026-04-09 | **Last Amended**: 2026-04-09
