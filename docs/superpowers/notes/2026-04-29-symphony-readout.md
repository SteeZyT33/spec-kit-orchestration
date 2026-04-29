# Symphony Readout — What We Can Learn From It

**Date:** 2026-04-29
**Source:** `~/symphony` (OpenAI, released 2026-04-28)
**Audience:** orca v1 design

## What Symphony is

OpenAI's **outer-loop** agent orchestrator. Polls Linear, claims tickets, dispatches Codex app-server sessions into per-issue workspaces, keeps them alive across continuation turns, retries on failure. ~2,200-line spec, Elixir reference implementation. Codex-only at this stage but the SPEC is harness-neutral in places (§10 explicitly defers protocol shape to "the targeted coding-agent app-server").

Repo layout that matters for our purposes:
- `SPEC.md` — 18-section language-agnostic specification (the contract)
- `elixir/` — reference implementation (deliberately framed as "prototype")
- `elixir/WORKFLOW.md` — concrete repo-owned policy file (YAML frontmatter + Markdown prompt body)
- `.codex/skills/<name>/SKILL.md` — skill definitions in Codex skill format (commit, push, pull, land, linear, debug)

## Symphony does NOT compete with orca

Symphony is the **ticket-loop runtime**; orca is the **inner-loop opinion layer + capability library**. They compose: a Symphony agent inside an issue workspace could invoke orca slash commands during execution. Symphony's WORKFLOW.md skills (`linear`, `commit`, `push`, `land`) map onto orca's `.codex/skills/<name>/SKILL.md` shape exactly — same convention Phase 3 ships.

## What we should learn from it

### 1. WORKFLOW.md as a single repo-owned policy contract

Symphony's WORKFLOW.md combines typed config (YAML frontmatter) with a prompt template (Markdown body) in one version-controlled file. Cleaner than scattering policy across `constitution.md`, `.specify/extensions.yml`, and per-feature plans. Worth considering an `ORCA.md` or constitution extension that adopts this shape for opinion-layer config (review thresholds, criteria defaults, model-tier floor, citation reference-set defaults).

### 2. Safety invariants codified, not implied

SPEC.md §9.5 lists three invariants explicitly:
- Run the coding agent only in the per-issue workspace path (`cwd == workspace_path`)
- Workspace path MUST stay inside workspace root (normalized absolute prefix check)
- Workspace key is sanitized (`[A-Za-z0-9._-]` only)

Phase 4a's path validation does some of this; it should be codified as a single `path-safety` contract that all orca capabilities cite. See `docs/superpowers/contracts/path-safety.md` (drafted alongside this note).

### 3. Stall-timeout pattern

Symphony's `stall_timeout_ms` (300s default) kills sessions when no events arrive for N seconds. Phase 4b should add stall detection to the host-side dispatch wrappers; per-capability timeouts cover the orca-cli call but not a hung subagent dispatch.

### 4. Harness-neutral pass-through for sandbox/approval policy

§10.5 explicitly does NOT mandate a posture; operators document theirs. Lesson: never bake security/sandbox policy into the capability library. Host concern. Phase 4b v2 already follows this; Symphony's spec validates the shape.

### 5. Continuation turns vs fresh sessions

Symphony keeps Codex alive, reuses the same `thread_id`, and sends only continuation guidance (not the original prompt) on follow-up turns. Orca's review loops re-dispatch fresh subagents each round. Probably right for orca's one-shot review semantics, but worth noting if review loops grow longer or if a future capability ("rework loop") needs to maintain context.

### 6. Tool injection through the harness, not the skill

Symphony injects `linear_graphql` as an in-session tool the agent calls directly. This validates Phase 4b v2's three-layer split — the host is where tool dispatch happens, NOT a bash skill running under flock. Symphony chose the same boundary for the same reason.

### 7. Reference-implementation framing

Symphony's README explicitly says: "Implement your own from the spec; the Elixir implementation is a prototype." Long-term orca should consider whether `cross-agent-review` etc. should be reimplementable from the JSON envelope contract (so other teams could ship orca-equivalent capabilities in their preferred language), or whether spec-kit-orca remains the canonical implementation. Not urgent for v1.

### 8. PR feedback sweep as a documented protocol

Symphony's WORKFLOW.md codifies: "gather all PR comments → treat each as blocking until addressed-or-pushed-back → re-validate." Orca has no equivalent today. Could be a future capability (`pr-feedback-sweep`) or slash command — but out of scope for v1.

## What Symphony does that orca should NOT do

- **Tracker integration** (Linear/Jira/etc). Stay tracker-agnostic.
- **Outer-loop orchestration** (polling, retries, workspace lifecycle, agent process supervision). Symphony or perf-lab v6 owns that layer.
- **Streaming app-server protocol handling.** Host concern.
- **Per-issue persistent workspaces.** Orca lives in an existing repo; "workspace" is the user's repo or feature dir.

## Strategic reframe for orca v1

Add a "Composition with Outer-Loop Runtimes" section to the v1 north-star spec stating: **orca is the inner-loop opinion layer + capability library; outer-loop runtimes like Symphony or perf-lab v6 invoke orca skills inside agent sessions.** This positioning makes Phase 4b's "perf-lab integration" pattern generalize: it's the same shape any Symphony-style runtime would use. The pattern is:

1. Outer loop dispatches an agent into a workspace (Symphony does this for Linear tickets; perf-lab v6 does this for research claims).
2. The agent inside the workspace invokes orca slash commands (`/orca:review-spec`, `/orca:review-code`, etc.) or shells out to `orca-cli` directly.
3. The host (Claude Code, Codex) handles subagent dispatch via Phase 4a's file-backed reviewer pattern.
4. Orca capabilities return JSON envelopes; host translates to the runtime's event/state ledger.

## Concrete actions taken alongside this note

- New `docs/superpowers/contracts/path-safety.md` codifying invariants from Symphony §9.5 generalized for orca path-accepting flags.
- v1 north-star gains a "Composition with Outer-Loop Runtimes" section.
- Phase 4b v2 spec references the path-safety contract instead of inlining rules.

## Deferred / not-yet

- WORKFLOW.md-style ORCA.md unification — track as a Phase 5+ consideration; v1 keeps existing constitution.md / extensions.yml structure.
- Stall-timeout policy on subagent dispatch — add to Phase 4b v2 spec as a Phase 4b-pre-4 task in orca repo (host-side dispatch wrapper concern).
- PR-feedback-sweep capability — out of v1 scope.
- Cross-language reimplementation framing — long-term doc concern; not blocking.
