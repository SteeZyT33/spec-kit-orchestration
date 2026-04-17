# Contract: Flow State Evidence

## Primary Evidence Sources

Flow state may derive from:

- `spec.md`
- `plan.md`
- `tasks.md`
- `brainstorm.md` and linked files under `brainstorm/`
- `review.md` and `self-review.md`
- implementation evidence when available
- worktree metadata as contextual evidence
- thin cached resume metadata under `.specify/orca/flow-state/`

## Evidence Rules

- durable artifacts outrank branch/session inference
- missing evidence produces incomplete state, not fake completion
- conflicting evidence produces ambiguity notes
- worktree or lane metadata may enrich state but may not replace feature truth
- cached resume metadata may enrich summaries, but it does not determine stage completion

## Resume Metadata Rule

Any persisted flow-state metadata is secondary to primary evidence sources and
must be safely recomputable or ignorable.

The current helper writes one JSON file per feature at:

- `.specify/orca/flow-state/<feature>.json` when a repo root is available
- `<feature>/.flow-state.json` only as a fallback for detached feature paths
