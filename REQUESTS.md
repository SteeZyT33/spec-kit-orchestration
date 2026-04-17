# REQUESTS — Orca feature backlog

Track pending and in-flight work here. Mark items as you complete them.
Format: status / priority / owner / short description / pointer.

Status legend: `[ ]` queued · `[~]` in flight · `[x]` done · `[!]` blocked.

---

## Next up (unblocked, pre-scoped)

- [ ] P1 — **016 Phase 2: OpenSpec adapter.** T034 Phase 1.5 normalized types are merged, so the adapter seam is ready. Needs its own spec (suggested branch `019-openspec-adapter`). Background in `specs/016-multi-sdd-layer/brainstorm.md` §OpenSpec, `specs/016-multi-sdd-layer/spec.md` §Phase 2 deferred items, `specs/016-multi-sdd-layer/plan.md` §Deferred-to-Phase-2.
- [ ] P2 — **018 v2: TUI command palette + write paths.** v1.1 shipped read-only drawers and theme cycling. v2 turns the TUI into a command surface (approve matriarch gates, advance stages, kick off runs) instead of a viewer.
- [ ] P2 — **017 v1.2: LLM-aided discovery for brownfield adoption.** v1.1 added heuristics H4 (ownership) and H5 (test coverage) plus `rescan`. v1.2 is the LLM-aided discovery layer on top — suggested adoption candidates from semantic clustering, not just heuristics.

## Research / low-urgency

- [ ] P3 — **009 Yolo PR F leftovers.** Branch `009-yolo-pr-f` exists remotely but carries no commits ahead of main. Confirm it can be pruned.
- [ ] P3 — **Prune merged branches.** Several merged feature branches remain on origin (009-orca-yolo, 009-yolo-integrations, 016-multi-sdd-layer, 017-*, 018-orca-tui). Batch-delete after confirming nothing depends on them.

## Recently shipped

- [x] CodeQL rename-cache workaround (PR #65) — unblocks every future CI run. Diagnosis in memory `project_codeql_rename_diagnosis.md`.
- [x] 016 Phase 1.5 (PR #62) — normalized review + worktree adapter types.
- [x] 017 v1.1 (PR #63) — H4 ownership, H5 test coverage, `rescan`.
- [x] 018 v1.1 (PR #64) — drawer views + theme cycling.

---

**House rules** (from `claude.md`):
- Backend + frontend + deploy + QA in one pass. No half-delivered features.
- Subagents do the grunt work; the orchestrator divides, reviews, and fixes.
- Concrete numbers, no buzzwords.
- No data deletion without asking.
