# Research: Orca YOLO

## Decision 1: `orca-yolo` should orchestrate upstream workflow primitives

- **Decision**: `009` consumes upstream memory, flow, review, handoff, and pack
  contracts rather than redefining them.
- **Why**: The workflow-system upgrade only makes sense if `yolo` is downstream
  of durable primitives.
- **Alternatives considered**:
  - monolithic orchestration engine: rejected because it would absorb too much
    workflow logic
  - prompt-only alias over existing commands: rejected because it would not
    support durable resume

## Decision 2: The first version should be conservative about autonomy

- **Decision**: prioritize explicit stage progression, bounded retry, and
  explicit stop reasons over maximum automation.
- **Why**: A conservative orchestrator is easier to trust and easier to debug.
- **Alternatives considered**:
  - aggressive autonomous fix loops: rejected because review gates would become
    muddy

## Decision 3: Run state should be a first-class durable artifact

- **Decision**: model each full-cycle run as a durable record with policy,
  stage, outcome, and artifact links.
- **Why**: Resume, auditability, and PR-ready completion all depend on durable
  orchestration state.
- **Alternatives considered**:
  - reconstruct from repo state alone: rejected because branch/worktree/file
    state is not enough to disambiguate orchestration intent

## Decision 4: PR completion should be policy-governed

- **Decision**: `009` should support PR-ready completion and optional PR
  creation, but PR publication remains explicit policy.
- **Why**: Publishing a PR is a meaningful side effect and should not be
  implicit.
- **Alternatives considered**:
  - always create a PR: rejected because it is too forceful
  - never include PR handling: rejected because it leaves the workflow
    incomplete

## Decision 5: Capability-pack alignment should stay explicit

- **Decision**: `orca-yolo` may later be represented as a downstream capability
  pack, but the pack model must not become a hidden prerequisite for
  understanding the orchestration contract.
- **Why**: `008` exists to keep optional behavior explicit, not to obscure it.
- **Alternatives considered**:
  - require pack understanding before `009` makes sense: rejected because it
    raises cognitive load unnecessarily
