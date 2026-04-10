# Implementation Plan: Orca Brainstorm Memory

**Branch**: `002-brainstorm-memory` | **Date**: 2026-04-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-brainstorm-memory/spec.md`

## Summary

Add a durable brainstorm memory layer beneath Orca's existing
`/speckit.orca.brainstorm` command. The feature will keep the current ideation
flow and handoff model, but replace ad hoc artifact handling with a stable
project-local `brainstorm/` memory system built from numbered brainstorm
records, a generated `00-overview.md`, overlap detection, and forward links
into later spec artifacts.

The implementation should be split between deterministic file/runtime helpers
and command-level workflow guidance. The agent still performs the thinking, but
Orca becomes responsible for consistent numbering, non-destructive updates,
overview regeneration, and file conventions that later systems can consume.

## Technical Context

**Language/Version**: Markdown command docs, Bash entrypoints, Python 3.10+ for deterministic file/runtime helpers  
**Primary Dependencies**: existing Spec Kit repo layout, `git`, Python standard library, current Orca command/launcher packaging  
**Storage**: project-local Markdown files under `brainstorm/` plus existing spec artifacts under `specs/`  
**Testing**: manual workflow verification, `bash -n`, `uv run python -m py_compile`, and deterministic helper smoke checks where practical  
**Target Platform**: local developer workstations using Spec Kit Orca on Linux/WSL2 first  
**Project Type**: workflow extension / command-doc plus helper-runtime repository  
**Performance Goals**: brainstorm save/update and overview regeneration should feel instant for normal repos with tens of brainstorm files  
**Constraints**: provider-agnostic, no Claude-specific session substrate, preserve manual edits in brainstorm docs, idempotent overview regeneration, keep current brainstorm handoff semantics intact  
**Scale/Scope**: single-repo brainstorm memory for Orca-managed projects, typically dozens rather than hundreds of brainstorm records

## Constitution Check

### Pre-design gates

1. **Provider-agnostic orchestration**: pass. The design stores memory in repo
   files and avoids provider-specific session formats.
2. **Spec-driven delivery**: pass. This feature is being specified and planned
   before implementation.
3. **Safe parallel work**: pass with constraint. Brainstorm memory files must be
   additive and non-destructive so concurrent feature work does not silently
   overwrite idea history.
4. **Verification before convenience**: pass. The plan includes deterministic
   helper verification and manual workflow checks.
5. **Small, composable runtime surfaces**: pass. The plan favors a narrow
   helper surface for numbering, matching, and overview regeneration rather than
   embedding brittle logic only in prompts.

### Post-design check

The chosen design continues to satisfy the constitution because it:

- keeps the runtime surface small and file-based
- avoids hidden provider state
- treats brainstorm history as additive records
- makes regeneration and matching deterministic enough to verify

No constitution violations require explicit justification.

## Project Structure

### Documentation (this feature)

```text
specs/002-brainstorm-memory/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── brainstorm-command.md
│   └── brainstorm-memory-files.md
└── tasks.md
```

### Source Code (repository root)

```text
commands/
└── brainstorm.md                 # update workflow contract and memory behavior

scripts/
└── bash/
    └── ...                      # existing shell utilities; wrapper hooks only if needed

src/
└── speckit_orca/
    ├── cli.py
    ├── assets/
    └── brainstorm_memory.py     # NEW deterministic helper for file operations

templates/
├── quicktask-template.md
├── review-template.md
└── brainstorm-record-template.md # NEW optional record seed/template

docs/
├── orca-harvest-matrix.md
└── ...                          # README/protocol docs may need updates
```

**Structure Decision**: Put deterministic brainstorm-memory logic in a small
Python helper module under `src/speckit_orca/` because overview regeneration,
record parsing, slug handling, and overlap detection are easier to keep
deterministic there than in prompt prose or shell pipelines. Keep user-facing
workflow behavior in `commands/brainstorm.md`, and use templates/docs only for
stable artifact shape and examples.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Python helper for a docs-driven command | Deterministic parsing and regeneration are easier to verify in stdlib Python | Pure prompt-only behavior would make numbering, matching, and overview regeneration inconsistent across providers |
| Generated overview file | Users need a stable memory index without reading each brainstorm file | Relying on file names alone would not surface open threads, statuses, or downstream links |

## Research Decisions

### 1. Memory belongs at project root in `brainstorm/`

Decision: store brainstorm memory in a project-local `brainstorm/` directory
with numbered records and a generated `00-overview.md`.

Rationale:

- matches the strongest Spex pattern without copying its full trait system
- makes ideation artifacts durable and provider-neutral
- gives later workflow stages a stable path convention

Alternatives considered:

- `.specify/orca/inbox/` only: too transient and awkward once the idea becomes
  a durable project artifact
- `specs/<feature>/brainstorm.md` only: works for feature refinement, but does
  not provide pre-spec memory or a cross-feature overview

### 2. Preserve the current brainstorming UX, add a deterministic memory layer

Decision: keep `/speckit.orca.brainstorm` as the primary UX surface and add
small deterministic helpers for numbering, update-vs-new matching, and overview
regeneration.

Rationale:

- protects current Orca workflow and handoff semantics
- makes file behavior consistent across providers
- gives future Orca systems reusable primitives

Alternatives considered:

- prompt-only implementation: lower initial code, but inconsistent and hard to
  validate
- full CLI command first: premature; the command doc already exists as the user
  entrypoint

### 3. First version uses lightweight overlap detection

Decision: use simple normalized title/slug keyword overlap and existing record
metadata to identify likely matches.

Rationale:

- sufficient for first-version revisit handling
- easy to explain, verify, and keep provider-agnostic

Alternatives considered:

- semantic/embedding matching: too heavy and unnecessary here
- no overlap detection: would make brainstorm memory noisy quickly

### 4. Updates must be additive, not destructive

Decision: existing brainstorm records are updated by appending a dated revision
entry or merging into explicit update sections while preserving prior authored
content.

Rationale:

- manual edits must survive
- brainstorm memory is an audit trail, not a cache

Alternatives considered:

- rewrite whole files on each revisit: simplest implementation, but violates the
  preservation requirement and creates user distrust

### 5. Overview is rebuilt from records rather than incrementally patched

Decision: `00-overview.md` should be regenerated from the current set of
brainstorm records each time Orca writes or updates memory.

Rationale:

- idempotent and easier to reason about
- avoids state drift between individual records and the overview

Alternatives considered:

- incremental edits to overview only: smaller writes, but much easier to drift

## Design Decisions

### 1. Separate record authoring from index generation

The brainstorm command or agent creates/updates the content-rich brainstorm
record. The deterministic helper then:

- validates the target directory
- computes next number and slug
- parses existing record metadata
- rebuilds the overview

This keeps the boundary clean between reasoning work and filesystem mechanics.

### 2. Standardize a record header with machine-friendly fields

Each brainstorm record should expose stable fields near the top of the file so
later Orca systems can parse them without needing fragile prompt inference.
Minimum fields:

- brainstorm number
- title/topic
- created/updated dates
- status
- downstream link

### 3. Treat `00-overview.md` as generated-but-readable

The overview is not the place for manual commentary. It should be fully
regenerable from underlying brainstorm records and optimized for quick scanning:

- sessions table
- open threads rollup
- parked ideas summary

### 4. Forward links stop at brainstorm-to-spec for this feature

This feature only needs to support forward references from brainstorm records to
later spec or feature identities. Reverse links, richer run-state coupling, and
review-stage integration are follow-on work.

## Implementation Phases

### Phase 0: Helper and artifact design

Define the stable file contract for:

- brainstorm record filenames: `NN-topic-slug.md`
- overview file: `brainstorm/00-overview.md`
- record metadata/header fields
- update section shape for revisits

Add the deterministic helper module and a template/example if it reduces prompt
ambiguity.

### Phase 1: Brainstorm command integration

Update `commands/brainstorm.md` so it:

- prefers `brainstorm/` as the durable memory target
- distinguishes pre-spec brainstorming from active feature refinement cleanly
- instructs the agent to detect related brainstorms using the helper/runtime
  contract
- writes/updates records with the required sections and status values
- refreshes the overview after writes and updates

### Phase 2: Deterministic regeneration and matching

Implement helper behavior for:

- directory bootstrap
- next-number allocation using `max + 1`
- slug normalization with fallback titles
- record metadata parsing
- overview regeneration
- simple overlap candidate detection

### Phase 3: Downstream linking and documentation

Add support and documentation for:

- marking a brainstorm `spec-created`
- storing a spec path or feature identifier
- README updates that explain brainstorm memory behavior and future consumers

## Verification Strategy

### Primary verification

Manual workflow checks in this repo:

1. save a new brainstorm into an empty repo memory area
2. verify `brainstorm/NN-*.md` and `brainstorm/00-overview.md` are created
3. save a parked brainstorm and confirm non-spec status handling
4. revisit a related topic and confirm update-vs-new behavior
5. mark a brainstorm as linked to a spec and verify the overview reflects it
6. delete `00-overview.md` and regenerate it from records

### Secondary verification

- `uv run python -m py_compile` for the helper module
- direct helper smoke commands for numbering, parsing, and overview generation
- `git diff --check`
- `bash -n` for any touched shell wrappers

## Risks

### 1. Mixed artifact model with existing feature brainstorm files

Orca currently uses `specs/<feature>/brainstorm.md` for active feature
brainstorming. Introducing `brainstorm/` memory could create duplication.

Mitigation:

- define clear precedence in the command contract
- use forward links rather than duplicating whole artifacts
- keep active-feature refinement semantics explicit

### 2. Fragile record parsing

If the helper depends on free-form markdown too much, overview regeneration will
break on manual edits.

Mitigation:

- parse a small stable header only
- keep the rest of the file human-authored and flexible

### 3. Overlap detection false positives or misses

Simple matching will not be perfect.

Mitigation:

- surface likely matches as suggestions, not automatic merges
- always preserve a new-record option

## Non-goals

- full `orca-yolo` orchestration
- reverse links from specs back into brainstorm records
- semantic search or embeddings for brainstorm recall
- review-artifact or flow-state integration beyond establishing the forward
  contract they will consume later
