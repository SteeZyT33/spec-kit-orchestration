# README Style Guide

## Purpose

The README is for humans evaluating, adopting, or operating Orca.

It is not:

- a spec inventory
- a task ledger
- a branch-status dashboard
- a dumping ground for internal planning language

## Core Rules

1. Write for people first.
2. Prefer plain language over internal process jargon.
3. Explain value, workflow, and operator impact before implementation detail.
4. Keep the roadmap directional, not checklist-shaped.
5. Simplify aggressively. If a section reads like internal planning residue, cut or rewrite it.

## Hard Rules

- Do not frame the product through spec numbers.
- Do not mirror internal task states, wave checkpoints, or TODO lists.
- Do not explain the roadmap as a numbered implementation program.
- Do not use the README as the canonical place for internal planning detail.
- Do not use the `speckit` brand in prose or positioning language.

Literal command examples such as `speckit-orca` or existing slash command
syntax are allowed when operationally necessary, but they should appear as
command syntax, not product branding.

## Required Shape

Every README update should aim to answer:

1. What is Orca?
2. Why would someone use it?
3. What does it do today?
4. How do I install and operate it?
5. What is the direction of the product?

## Roadmap Rules

The roadmap section should:

- describe upcoming capabilities in words
- group related direction clearly
- help a reader understand where the product is headed

The roadmap section should not:

- list spec IDs
- list internal waves or checkpoints
- read like sprint planning
- imply every internal idea is committed product scope

## README Update Process

When a feature changes user-visible behavior, install flow, configuration,
runtime helpers, workflow shape, or roadmap-visible status:

1. Draft the README change from the user's point of view.
2. Run a simplification pass.
3. Run a humanization pass.
4. Run a positioning/marketing oversight pass.
5. Only then treat the feature as documentation-complete.

## Recommended Agent Roles

README updates should be treated as a real deliverable, not incidental polish.

Preferred reviewer/owner pattern:

- `README Steward` owns the main draft
- `Human Lead` checks clarity, truthfulness, and whether the page still reads like it was written for people
- `Product Marketer` checks positioning, differentiation, and narrative coherence

If only one pass is feasible, `README Steward` is the default owner.

## Good Outcomes

A strong README should feel:

- clearer than the underlying implementation
- shorter than the internal planning docs
- more opinionated than generated documentation
- trustworthy to a new reader

## Source Of Truth Boundaries

Use the README for:

- product framing
- operator workflow
- install and configuration basics
- human-readable roadmap direction

Use other docs for:

- detailed protocols
- implementation contracts
- internal planning
- spec-by-spec scope tracking
