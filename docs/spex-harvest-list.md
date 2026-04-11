# Spex Harvest List

## Purpose

This document turns the `spex` adoption notes into an actionable harvesting
plan.

The rule for this list is pragmatic:

- if a `cc-spex` file is already close to what Orca needs, copy it
- if it is useful but Claude-coupled, copy it and adapt it
- if it drags in plugin/runtime assumptions Orca does not want, ignore it

Source repo referenced throughout:

- local `cc-spex` clone

## Bucket 1: Copy Directly

These files or file families are strong copy/paste candidates with low rewrite
cost. They still need final naming cleanup, but the structure and content are
already aligned enough to be worth lifting directly.

### 1. Worktree lifecycle logic

Primary source:

- `spex/skills/worktree/SKILL.md` in `cc-spex`

Why:

- strong create/list/cleanup lifecycle
- practical handling of branch restoration
- practical handling of target path computation
- concrete failure cases already thought through

How to use in Orca:

- copy the lifecycle logic
- translate it into Orca worktree runtime helpers and later a possible
  `speckit.orca.worktree`
- remove Claude-specific references from the user guidance

### 2. Reviewer brief structure

Primary source:

- `spex/skills/review-code/SKILL.md` in `cc-spex`

Why:

- the `REVIEW-CODE.md` structure is strong
- it gives human reviewers an efficient entry point
- it avoids flooding reviewers with raw compliance dump output

How to use in Orca:

- copy the structure for a reviewer-facing artifact
- adapt naming and artifact locations to Orca
- keep `review.md` as the authoritative record

### 3. Stage-discipline language

Primary source:

- `spex/skills/ship/SKILL.md` in `cc-spex`

Why:

- excellent language around not silently skipping stages
- explicit resume/start semantics
- strong “pipeline is continuous” discipline

How to use in Orca:

- copy the discipline language into future Orca orchestration docs
- reuse the state/progression ideas later when Orca grows a ship-like lane

## Bucket 2: Copy Then Adapt

These are the highest-value files overall, but they require adaptation before
they belong in Orca.

### 1. Brainstorm workflow

Primary source:

- `spex/skills/brainstorm/SKILL.md` in `cc-spex`

Why it matters:

- stronger conversational ideation loop
- stronger anti-implementation discipline
- better persistence habits around brainstorm artifacts

What to adapt:

- remove Claude-specific hard gates
- remove `/spex:*` assumptions
- adapt command references to Orca and Spec Kit
- keep Orca’s decision that brainstorm can route to `micro-spec`

### 2. Code review workflow

Primary source:

- `spex/skills/review-code/SKILL.md` in `cc-spex`

Why it matters:

- stronger “spec compliance first” framing
- compliance matrix logic
- better distinction between deviations and improvements

What to adapt:

- remove `deep-review` trait assumptions for the first pass
- split anything PR-specific back into Orca `pr-review`
- map outputs into Orca `code-review` and reviewer brief artifacts

### 3. Trait architecture

Primary sources:

- `README.md` in `cc-spex`
- `spex/scripts/spex-traits.sh` in `cc-spex`

Why it matters:

- this is the single biggest architecture win in spex
- it keeps cross-cutting concerns out of the core command set

What to adapt:

- do not copy the full trait system blindly
- copy the trait boundaries and management ideas
- reimplement them in Orca’s provider-agnostic style

Likely Orca targets:

- `worktrees`
- `delivery`
- `deep-review`
- `ship`

### 4. Ship pipeline concepts

Primary source:

- `spex/skills/ship/SKILL.md` in `cc-spex`

Why it matters:

- strong stage orchestration
- explicit state tracking
- useful restart/resume ideas

What to adapt:

- do not port now
- extract only the orchestration/state ideas
- defer implementation until Orca runtime metadata is stronger

### 5. Initialization and trait selection flow

Primary sources:

- `spex/commands/init.md` in `cc-spex`
- `spex/scripts/spex-traits.sh` in `cc-spex`

Why it matters:

- useful model for setup/update and trait enablement

What to adapt:

- remove `AskUserQuestion`
- remove Claude permission model assumptions
- remove plugin-specific init mechanics
- keep the idea of a single orchestrated init/update path

## Bucket 3: Ignore

These should not be copied into Orca except maybe as background reference.

### 1. Claude plugin packaging

Ignore:

- `spex/.claude-plugin` in `cc-spex`
- `docs/plugin-schema.md` in `cc-spex`

Why:

- purely Claude plugin substrate
- not useful for provider-agnostic Orca

### 2. Claude hook/session plumbing

Ignore:

- `spex/scripts/hooks/pretool-gate.py` in `cc-spex`

Why:

- strongly tied to Claude runtime behavior
- imports complexity Orca does not want

### 3. Claude Teams implementation

Ignore for now:

- `spex/skills/teams-orchestrate/SKILL.md` in `cc-spex`
- related `teams*` overlays

Why:

- highly Claude-specific
- too much complexity too early

### 4. Marketplace/install docs

Ignore:

- Claude marketplace install flow in `README.md` in `cc-spex`

Why:

- not relevant to Orca’s install/runtime model

## Suggested First Harvest Pass

Keep the first pass bounded. Do not try to “bring spex into Orca” in one move.

### Pass 1

Steal these first:

1. reviewer brief structure from `review-code`
2. worktree lifecycle logic from `worktree`
3. stronger brainstorm discipline from `brainstorm`

Why:

- highest leverage
- lowest risk
- directly addresses current Orca weaknesses

### Pass 2

Then adapt:

1. spec-compliance scoring in `code-review`
2. trait/module framing from `spex-traits.sh`

### Pass 3

Much later:

1. deep-review concepts
2. ship/state orchestration
3. drift reconciliation concepts

## Copy Policy

Literal copy/paste is acceptable.

Preferred policy:

- if a source file is 80% right, copy it
- then delete or replace the Claude-specific 20%
- do not rewrite from scratch just to make it feel original

This is the point of harvesting: save legwork, not preserve novelty.

## Immediate Next Step

If implementation starts from this harvest list, the first concrete move should
be:

**Port the reviewer brief structure from `spex/skills/review-code/SKILL.md` into
Orca `code-review`, and port the worktree lifecycle logic from
`spex/skills/worktree/SKILL.md` into Orca runtime helpers.**
