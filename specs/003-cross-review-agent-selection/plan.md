# Implementation Plan: Orca Cross-Review Agent Selection

**Branch**: `003-cross-review-agent-selection` | **Date**: 2026-04-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-cross-review-agent-selection/spec.md`

## Summary

Expand Orca cross-review from a three-harness implementation into an
agent-selection system with explicit `--agent` input, config migration from
`crossreview.harness` to `crossreview.agent`, support tiers, explainable
selection precedence, first-class `opencode` support, and runtime/artifact
reporting that records requested versus resolved reviewer choice.

The design should preserve Orca's provider-agnostic direction from the repomix
findings: reviewer choice becomes a composable workflow capability implemented
through shared resolution policy plus backend adapters, not a growing list of
hard-coded command exceptions.

## Technical Context

**Language/Version**: Markdown command docs, Bash launchers, Python 3.10+ backend/runtime helpers  
**Primary Dependencies**: existing Orca command docs, `scripts/bash/crossreview.sh`, `scripts/bash/crossreview-backend.py`, current installer-known agent list, Python standard library  
**Storage**: repo config in `config-template.yml`, review artifacts under feature directories, optional reviewer-memory metadata if introduced  
**Testing**: manual CLI smoke checks, `bash -n`, `uv run python -m py_compile`, provider-specific adapter smoke checks, and review-artifact verification  
**Target Platform**: local developer workstations using Orca on Linux/WSL2 first  
**Project Type**: workflow extension / command-doc plus launcher/backend runtime repository  
**Performance Goals**: reviewer selection should resolve immediately; runtime overhead beyond the selected agent invocation should be negligible  
**Constraints**: provider-agnostic behavior, explicit unsupported-agent errors, backward compatibility for `--harness` and `crossreview.harness`, no false claims of support for installer-known agents without verified adapters  
**Scale/Scope**: a small set of first-class review agents with room for gradual expansion through adapter registration rather than full parity across every installer-known agent

## Constitution Check

### Pre-design gates

1. **Provider-agnostic orchestration**: pass. The feature explicitly moves
   cross-review toward agent-based orchestration rather than narrowing it to
   the original three runners.
2. **Spec-driven delivery**: pass. This feature now has its own spec and plan.
3. **Safe parallel work**: pass. The feature changes review-agent selection, not
   lane mutation, but it still must fail clearly rather than misreport review
   completion.
4. **Verification before convenience**: pass with emphasis. Every new adapter or
   compatibility path must have a smoke-check path so Orca does not silently
   claim review support it does not really have.
5. **Small, composable runtime surfaces**: pass. The design centers on shared
   resolution logic and adapter dispatch instead of scattering selection rules
   across multiple command docs and scripts.

### Post-design check

The chosen design stays aligned with the constitution because it:

- isolates provider-specific behavior behind adapters
- uses explicit documented compatibility paths
- prefers structured failure over silent fallback
- keeps selection policy and adapter execution distinct

No constitution violations need justification.

## Project Structure

### Documentation (this feature)

```text
specs/003-cross-review-agent-selection/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── cross-review-command.md
│   ├── cross-review-config.md
│   └── cross-review-output.md
└── tasks.md
```

### Source Code (repository root)

```text
commands/
├── cross-review.md
├── pr-review.md
└── self-review.md

scripts/
└── bash/
    ├── crossreview.sh
    └── crossreview-backend.py

templates/
└── crossreview.schema.json

config-template.yml
README.md
speckit-orca
```

**Structure Decision**: Keep selection policy visible at the command/config
layer, but centralize actual runtime resolution and adapter dispatch inside the
existing cross-review launcher/backend path. This preserves Orca's current
runtime footprint while preventing command-doc policy drift from the executable
backend behavior.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Compatibility window for `--harness` and `crossreview.harness` | Existing Orca users already have working config and command habits | Immediate hard cutover to `agent` would create unnecessary breakage |
| Support tiers instead of uniform support | Installer-known agents do not currently have equivalent review adapters | Pretending parity would create false-positive review success and user distrust |

## Research Decisions

### 1. Normalize on `agent`, not `harness`

Decision: `--agent` and `crossreview.agent` become the canonical interfaces,
while `--harness` and `crossreview.harness` remain compatibility inputs for a
limited window.

Rationale:

- better matches Orca's provider-agnostic direction
- aligns reviewer choice with the broader installer-known agent surface
- avoids a permanently split mental model across docs and artifacts

Alternatives considered:

- keep `harness` naming forever: simpler short-term, but continues the current
  conceptual mismatch
- rename everything immediately without compatibility: cleaner eventually, but
  too disruptive

### 2. Separate selection policy from adapter execution

Decision: implement a shared agent-resolution model plus adapter dispatch
instead of embedding selection logic separately in the command doc, launcher,
and backend.

Rationale:

- keeps runtime behavior inspectable and consistent
- makes new adapters easier to add
- prevents documentation drift from executable behavior

Alternatives considered:

- hard-code each new agent directly into the backend choices: fast once, but
  does not scale and repeats the current problem

### 3. Support tiers are required, not optional

Decision: Orca must formally distinguish Tier 1 supported review agents, known
but best-effort/selectable agents, and known but unsupported agents.

Rationale:

- the installer already recognizes far more agent names than cross-review can
  honestly support
- users need explicit trust boundaries

Alternatives considered:

- treat all known agents as equivalent: misleading
- hide unsupported agents completely: loses visibility into future expansion

### 4. `opencode` is first-class now; `cursor-agent` waits for contract verification

Decision: `opencode` is in the initial implementation scope because it is
already installed and manually usable; `cursor-agent` is designed into the
model but should not become auto-selectable until its adapter contract is
verified.

Rationale:

- keeps delivery grounded in actual runtime capability
- still proves the extensibility model

Alternatives considered:

- hold `opencode` until all agents are ready: unnecessary delay
- auto-enable `cursor-agent` immediately: too speculative

### 5. Reviewer memory should be advisory only

Decision: if reviewer-memory is added now, it should only influence selection as
soft context, never as a forced override.

Rationale:

- stale reviewer memory should not produce confusing or sticky behavior
- explicit config or CLI input must always win

Alternatives considered:

- no memory at all: simpler, but loses a useful low-friction selection signal
- mandatory reuse of previous reviewer: too opaque

## Design Decisions

### 1. Requested, resolved, and active provider must all be distinct concepts

Cross-review needs to represent at least:

- requested agent
- resolved agent
- active provider

This is the only way to report same-agent fallback honestly and explain why a
selection happened.

### 2. Structured unsupported-agent failures are part of the contract

Selecting a known-but-unsupported agent must still return a structured result
that clearly says no substantive review occurred. Silent fallback is not
acceptable here.

### 3. Adjacent command docs must be updated in the same feature

`pr-review`, `self-review`, config docs, and README references must switch to
the same canonical terminology as `cross-review`. Otherwise Orca will still
ship two parallel mental models.

### 4. Adapter registration should be additive

The backend should make new agent support a registration problem, not a command
rewrite problem. The design must leave room for new adapters without requiring
new selection semantics each time.

## Implementation Phases

### Phase 0: Policy and contract alignment

Define the canonical terminology and compatibility window:

- `agent` versus legacy `harness`
- support tiers
- requested/resolved/active reviewer semantics
- artifact reporting requirements

### Phase 1: Command and config normalization

Update:

- `commands/cross-review.md`
- `config-template.yml`
- adjacent docs referencing cross-review

so the UX surface matches the new model.

### Phase 2: Runtime resolution and adapter expansion

Update the launcher/backend to:

- normalize `--agent` and legacy `--harness`
- resolve agents via documented precedence
- support `opencode`
- return structured unsupported-agent results

### Phase 3: Artifact reporting and compatibility polish

Update review output and docs so cross-review records:

- requested agent
- resolved agent
- selection reason
- support tier
- cross-agent vs same-agent fallback

## Verification Strategy

### Primary verification

Manual runtime checks:

1. run cross-review with `--agent codex`
2. run cross-review with `--agent opencode`
3. run cross-review with legacy `--harness claude`
4. run cross-review with no explicit reviewer and verify documented
   auto-selection behavior
5. attempt a known-but-unsupported agent and verify structured failure

### Secondary verification

- `bash -n scripts/bash/crossreview.sh`
- `uv run python -m py_compile scripts/bash/crossreview-backend.py`
- direct backend smoke checks for each Tier 1 adapter
- review artifact inspection to confirm requested/resolved agent reporting

## Risks

### 1. Support inflation

The repo already knows more agent names than the cross-review runtime can
honestly support.

Mitigation:

- support tiers
- explicit unsupported-agent output
- conservative auto-selection

### 2. Terminology drift

If `agent` becomes canonical in one place and `harness` stays canonical in
another, users will still be confused.

Mitigation:

- update adjacent docs in the same feature
- keep legacy naming only as compatibility behavior

### 3. Adapter sprawl

Every new agent can come with different CLI assumptions.

Mitigation:

- adapter-based backend structure
- only promote verified adapters to Tier 1

## Non-goals

- full parity for every installer-known Orca agent in one feature
- redesigning `code-review`
- changing the broader review pipeline ordering
- adding subjective scoring or benchmarking across agents in this feature
