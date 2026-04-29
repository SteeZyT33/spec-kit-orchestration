# Orca v1: Tool Chest with Native Perf-Lab Integration

**Date:** 2026-04-26
**Status:** Design (post-brainstorm, pre-implementation-plan)
**Successor to:** `docs/orca-v1.4-design.md`, `docs/orca-roadmap.md` (both superseded by this doc)

## Context

Orca began as `spec-kit-orca`, a fork of spec-kit with extra orchestration commands. Over the past weeks the system grew yolo (1432 lines), matriarch (AI-supervisor agent), spec-lite (lite-spec loophole), mailbox, and event envelopes. None of these earned their keep against actual use. A previous brainstorm landed on "orca's wedge is cross-agent review."

This design is the rebuild around that wedge, adapted to a concrete first integrator: perf-lab's self-organizing research runtime (`~/perf-lab/specs/010-...`).

The system has three audiences:

- **Personal SDD use.** Taylor's opinionated workflow on top of spec-kit/openspec — the daily driver.
- **Perf-lab.** The self-organizing research runtime reaches for orca capabilities at specific lifecycle points to keep cross-agent review structured and to gain SDD awareness for its meta-development loop.
- **Future consumers.** If orca ever ships beyond personal use, the opinion layer must adapt to other workflows without reinvention.

## Design Constraints

Four hard constraints, ordered by precedence:

1. **Standalone.** Orca is its own repo with its own catalog. Perf-lab pulls it in via submodule or vendor-at-release; orca is not absorbed.
2. **Native when included.** When a host pulls orca in, orca speaks the host's data shapes via integration shims. Findings flow into the host's event ledger; no parallel state directories.
3. **Doesn't get in the way.** Pull, never push. Hosts reach for capabilities; orca never intercepts a host's lifecycle. If orca is absent or a capability fails, the host still works.
4. **Real value or no entry.** Each capability must clear the "would a real host actually reach for this" bar. Speculative capabilities don't ship.

The opinion layer (Taylor's slash commands, R→P→I workflow) is part of orca for personal use. It's distinct from the capability catalog and from per-host integration shims.

## Architecture

```
ENGINE: orca Python library + CLI (canonical, JSON I/O, Result-typed)
                       │
       ┌───────────────┼───────────────┬──────────────┐
       ▼               ▼               ▼              ▼
  Claude Code      Codex           Perf-lab        Personal SDD
  plugin           plugin          integration     opinion
  (skills +        (AGENTS.md      shim (event     (slash
   commands)       fragments)      translation)    commands)
```

The Python library is the engine. The CLI is the canonical public surface. Everything else (plugin formats, integration shims, slash commands) is a hand-written wrapper that calls the CLI. Hosts can import the library directly or shell out; both are supported.

The data contract (the JSON shapes of capability outputs) is the obsolescence-resistance bet. Agents change; data shapes don't.

### Repo structure

```
orca/                                # renamed from spec-kit-orca
├── src/orca/                        # renamed from speckit_orca
│   ├── capabilities/                # 6 v1 capabilities
│   │   ├── cross_agent_review/
│   │   │   ├── __init__.py
│   │   │   └── reviewers/
│   │   │       ├── claude.py
│   │   │       └── codex.py
│   │   ├── completion_gate.py
│   │   ├── worktree_overlap_check.py
│   │   ├── flow_state_projection.py
│   │   ├── citation_validator.py
│   │   └── contradiction_detector.py
│   ├── cli.py                       # CLI entry, JSON I/O, Result handling
│   └── core/                        # shared primitives, error types
├── plugins/
│   ├── claude-code/
│   │   ├── skills/                  # skill files (auto-registered)
│   │   └── commands/                # slash commands (opinion layer)
│   └── codex/                        # codex-as-host invocation surface
│       ├── AGENTS.md                # codex-host instructions (capability discovery + invocation patterns)
│       └── prompts/                 # codex-native prompt directory for slash-command equivalents
├── integrations/
│   └── perf_lab/                    # event translation shim
├── docs/
│   └── capabilities/                # JSON contracts per capability
└── pyproject.toml                   # name = "orca"
```

## v1 Capability Catalog

Six capabilities. Each is invocable as `orca <capability>` via CLI or `from orca.capabilities import <capability>` via library.

### `cross-agent-review` — universal

**Purpose:** bundle a review subject, dispatch to a reviewer that's a different agent than the one being reviewed, return structured findings.

**Input contract:**
- `kind` ∈ {`spec`, `diff`, `pr`, `claim-output`}
- `target`: paths/refs to review
- `feature_id?`: ties to spec-kit feature
- `reviewer` ∈ {`claude`, `codex`, `cross`} (`cross` = both, returns dual reports)
- `criteria?`: focus list
- `context?`: related artifacts

**Output:** `findings.json` (findings[] with stable `id`/`severity`/`confidence`/`category`/`summary`/`detail`/`evidence`/`suggestion`, plus reviewer metadata) + `disposition.json` (per-finding `accept`/`reject`/`defer` with reasons).

**Backends:** `reviewers/claude.py`, `reviewers/codex.py`. Adding a backend is a single file with a `review(bundle) -> Findings` interface.

**Tier inheritance:** capability core enforces caller-tier-policy. A `cheap` tier caller cannot escalate to a `strong` reviewer.

### `completion-gate` — meta-dev primary

**Purpose:** decide whether an SDD-managed feature has cleared gates for a target stage. Revision-aware: knows when a prior review went stale because the artifact changed.

**Input:** `feature_id`, `target_stage` ∈ {`plan-ready`, `implement-ready`, `pr-ready`, `merge-ready`}, `evidence?`.

**Output:** `gate-result.json` with `status` ∈ {`pass`, `blocked`, `stale`}, `gates_evaluated[]`, `blockers[]`, `stale_artifacts[]`.

**Note:** runtime quality gates for perf-lab use citation-validator and contradiction-detector instead. completion-gate handles SDD R→P→I stage transitions.

### `worktree-overlap-check` — shared utility

**Purpose:** detect path conflicts between active worktrees, or proposed writes against active worktrees.

**Input:** `worktrees[]`, `proposed_writes?`, `repo_root?`.

**Output:** `overlap-result.json` with `safe`, `conflicts[]`, `proposed_overlaps[]`.

**Use:** perf-lab's `lease.sh` shells out to this instead of reimplementing FR data-model.md:220 overlap detection.

### `flow-state-projection` — meta-dev primary

**Purpose:** given a feature directory, return current SDD stage, artifact statuses, review statuses, staleness.

**Input:** `feature_id` or `feature_dir`, `sdd_kind` ∈ {`spec-kit`, `openspec`, `auto`}.

**Output:** `flow-state.json` with `feature_id`, `current_stage`, `artifacts[]`, `review_status`, `next_recommended_action`.

**Note:** mostly already exists in `src/speckit_orca/flow_state.py`. v1 work is API stabilization + JSON contract documentation.

### `citation-validator` — research-loop primary

**Purpose:** detect uncited claims and broken refs in synthesis/artifact text.

**Input:** `content_path` or `content_text`, `reference_set` (paths to events.jsonl, experiments.tsv, etc.), `mode` ∈ {`strict`, `lenient`}.

**Output:** `citation-result.json` with `uncited_claims[]`, `broken_refs[]`, `well_supported_claims[]?`, `citation_coverage`.

**v1 scope:** rule-based only. Regex for assertion-shaped sentences + ref existence check. No LLM in v1.

### `contradiction-detector` — research-loop primary

**Purpose:** detect when new synthesis or theory contradicts existing raw evidence or prior synthesis.

**Input:** `new_content`, `prior_evidence` (events, experiments, prior synthesis versions), `reviewer` ∈ {`claude`, `codex`, `cross`}.

**Output:** `contradiction-result.json` with `contradictions[]` (each with new claim, conflicting evidence ref, confidence, suggested resolution) + reviewer metadata.

**Implementation note:** effectively `cross-agent-review` with fixed contradiction criteria and a structured output schema. Exposed separately for clarity. v2 may collapse into `cross-agent-review` presets.

## Perf-Lab Integration Shim

Lives at `orca/integrations/perf_lab/`. Translates capability outputs into perf-lab events; emits via perf-lab's existing `perf-event` emitter.

### Shim entry points

Both Python and Bash for each capability:

```
run_cross_agent_review(claim_id, bundle, *, policy)
run_completion_gate(feature_id, target_stage, *, policy)
run_worktree_overlap_check(worktrees, *, policy)
run_flow_state(feature_id_or_dir, *, policy)
run_citation_validator(content_ref, *, policy)
run_contradiction_detector(new_content, evidence_refs, *, policy)
```

Each function: builds capability input from perf-lab state → shells out to `orca <capability> --json` → captures raw output to `/shared/orca/<event_id>/` → translates to perf-lab event payload → emits via `perf-event`.

### New event types (extends perf-lab FR-008)

- `quality_gate` — emitted by `completion-gate` non-pass results
- `synthesis_validated` — emitted after `citation-validator` runs
- `contradiction_detected` — emitted by `contradiction-detector`

The existing `critique` event gets a structured payload when produced by orca: `findings_ref`, `summary`, `blocker_count`, `high_count`, `reviewer_metadata`. The `findings_ref` indirection keeps `events.jsonl` lines short.

These additions documented in `~/perf-lab/specs/010-self-organizing-research-runtime/spec.md` under "Future Integration Notes: Orca Capability Layer."

### Policy config

Per-capability policy in `.perf-lab/orca-policy.yaml`. Defaults are explicit; safe fallbacks per capability:

```yaml
cross_agent_review:    { timeout_s: 120, fallback: emit_feedback_needed, reviewer_default: cross }
completion_gate:       { timeout_s: 30,  fallback: emit_feedback_needed }
worktree_overlap_check:{ timeout_s: 5,   fallback: block }
flow_state_projection: { timeout_s: 10,  fallback: emit_feedback_needed }
citation_validator:    { timeout_s: 30,  fallback: emit_feedback_needed }
contradiction_detector:{ timeout_s: 180, fallback: emit_feedback_needed, reviewer_default: cross }
```

Default fallback is `emit_feedback_needed` (orca failures surface to operator, never hang rounds). `worktree-overlap-check` is the exception: fallback is `block` because granting a lease without a successful overlap check is unsafe.

### Failure semantics

| Failure | Default behavior |
|---|---|
| Orca CLI not installed | Skip silently; integration is optional |
| Orca CLI returns timeout | Emit fallback event, `reason="orca_<capability>_timeout"` |
| Orca CLI returns error JSON | Emit fallback event, `reason="orca_<capability>_error"`, attach error JSON |
| Reviewer auth failure | Emit fallback event, `reason="orca_reviewer_auth_failed"`, no auto-retry |

Shim does not interpret findings. It translates JSON envelope to perf-lab event and emits. Decision-making (does this finding block? trigger follow-up claim?) is perf-lab scheduler logic.

### Constraints

- Optional. Perf-lab v1 ships and operates fully without orca.
- Failed orca calls never block rounds indefinitely.
- Outputs MUST translate to perf-lab event types before entering `events.jsonl`.
- Reviewer backends inherit perf-lab's tier policy when invoked from runtime.
- No long-running daemon. Each call is one shell-out + one event emission.

## Error Handling

### Universal Result contract

Every capability returns one of two JSON shapes:

```json
// Success
{
  "ok": true,
  "result": { /* capability-specific */ },
  "metadata": {"capability": "...", "version": "...", "duration_ms": 123}
}

// Error
{
  "ok": false,
  "error": {
    "kind": "input_invalid" | "backend_failure" | "timeout" | "internal",
    "message": "...",
    "detail": { /* optional structured context */ }
  },
  "metadata": {"capability": "...", "version": "...", "duration_ms": 123}
}
```

Exit codes: `0` success, `1` error JSON, `2` contract violation (invalid CLI input), `3` capability not found.

Python library mirrors the JSON shape with a `Result[T, Error]` discriminated union — exceptions are reserved for *unexpected* failures, mapping to `internal`. Business-logic failures (input invalid, backend failed) are values, not exceptions. Shims and slash commands branch on `result.ok` rather than wrapping every call in try/except.

### Per-capability error surface

Pure-logic capabilities (`completion-gate`, `worktree-overlap-check`, `flow-state-projection`) only emit `input_invalid` and `internal`. They have no backend and no I/O beyond filesystem reads.

LLM-backed capabilities (`cross-agent-review`, `contradiction-detector`, optionally `citation-validator`) emit the full surface including `backend_failure` and `timeout`. Reviewer errors include structured `detail`: `reviewer`, `stage`, `underlying_error`, `retryable`, `fallback_available`.

### Cross-mode partial success

When `reviewer=cross` and one backend fails, the other backend's findings still return with `result.partial = true` and `result.missing_reviewer`. Hosts see `ok: true` but can detect partial reviews. Shim translates this into a `critique` event with `partial_review: true`.

### What capabilities don't do

- No retries by default (host or `--retry N` flag controls)
- No automatic fallback to a different reviewer
- No host-specific event emission (shim's job)
- No prompt engineering at the host site (lives in reviewer adapters, ships with orca releases)

## Testing Strategy

| Layer | Test type | Speed | Dependencies |
|---|---|---|---|
| Capability core (pure logic) | pytest unit | fast | filesystem fixtures |
| Reviewer adapters | pytest with VCR cassettes | fast (replay) / slow (live) | recorded responses or real APIs |
| CLI surface | shell tests + JSON schema validation | fast | jq, schemas |
| Integration shims | pytest with subprocess mocks | fast | mocked orca CLI |
| End-to-end | shell + real fixtures | slow | real LLM optional |

**Reviewer adapter contract test** (the swap-cleanly claim): every reviewer is parameterized through the same test that asserts against `FINDINGS_SCHEMA`. New reviewers must pass before merging.

**JSON schema validation in CI:** every CLI invocation's output validated against `docs/capabilities/<name>/schema/output.json`. Schema drift is a build break.

**E2E tests:**
- Personal SDD: fixture spec + `/orca:review-spec` slash command → verify findings markdown output
- Perf-lab: tiny fixture mission, fire `critique` claim, verify shim emits correct event into `events.jsonl`

Both run with mocked reviewers by default. Both have `--live` flag for real LLM tests.

**Not tested:** reviewer prompt quality (eval problem, not test problem); LLM determinism (assert on schema, not text); cross-host portability with hypothetical hosts.

**CI matrix:**
- Every commit: capability unit, adapter contract (mocked), CLI schema validation, shim mocked
- PR: above + VCR replay + e2e mocked
- Nightly: above + `pytest -m live` (real LLM, cost-capped)
- Pre-release: above + manual smoke via real perf-lab fixture

## Repo Migration

Rename `spec-kit-orca` → `orca` in place. Single PR ships:

1. `pyproject.toml`: `name = "spec-kit-orca"` → `name = "orca"` (also unblocks the CodeQL rename-cache failure on PRs #62/#63/#64)
2. `src/speckit_orca/` → `src/orca/`
3. State path `.specify/orca/` → `.orca/` (already partially in flight)
4. CLI invocations `python -m speckit_orca.X` → `python -m orca.X`
5. Slash commands `speckit.orca.*` → `orca:*` (Claude Code plugin namespace convention, e.g. `/orca:review-spec`)
6. Strip kill-list code:
   - `src/speckit_orca/yolo.py` and `commands/yolo.md`
   - `src/speckit_orca/matriarch.py` and `commands/matriarch.md`
   - `src/speckit_orca/spec_lite.py` and `commands/spec-lite.md`
   - `src/speckit_orca/adoption.py`, `onboard.py`, `evolve.py`, `capability_packs.py`
   - `commands/adopt.md`, `commands/assign.md`
7. Move slash commands to `plugins/claude-code/commands/`
8. Add `plugins/claude-code/skills/` for plugin-format skill files
9. Add `plugins/codex/` with AGENTS.md fragments and codex-native prompts
10. Add `integrations/perf_lab/` shim
11. Document JSON contracts in `docs/capabilities/<name>/`

TUI (`src/speckit_orca/tui/`, `commands/tui.md`) stays. v1 work on TUI is limited to import path updates and slash command rename; no new TUI features. Post-rename it reads from `.orca/` (already partially migrated) and continues to render the same panes.

## v1 Scope

In v1:

- 6 capabilities with documented JSON contracts
- CLI + Python library (Result-typed)
- Claude Code plugin (skills + commands)
- Codex plugin (AGENTS.md fragments + prompts)
- Codex reviewer backend (for cross-agent-review)
- Perf-lab integration shim
- Personal SDD opinion layer (slash commands)
- Test coverage per testing strategy
- Repo rename + kill-list strip
- TUI continues to function post-rename

Deferred from v1:

- Pi-agent-harness surface (host doesn't exist yet)
- MCP server wrapper (no concrete consumer yet; reconsider if a Cursor user appears)
- Caching layer (premature optimization)
- Citation-validator LLM mode (rule-based first; upgrade when rule-based proves insufficient against real text)
- Future research-loop capabilities (`abstention-rationalizer`, etc.)
- Combo reviewer mode beyond `cross` (could grow to N-way comparison)
- New TUI features

Honest scope estimate: ~3 weeks of focused work for v1 as defined. Implementation plan should phase as: (1) repo rename + kill-list strip, (2) capability cores + CLI, (3) plugin formats (Claude Code, Codex), (4) perf-lab integration shim, (5) test coverage hardening. Phases 2 and 3 can partly parallelize once 1 lands.

## Honest Value Statement

What orca uniquely provides perf-lab:

1. **Pre-thought data contracts for cross-agent review** — `findings.json` with stable dedupe IDs, `disposition.json`, revision-aware bundle hashes. Perf-lab's native `critique` mode can emit *something* without orca; it can't reach this contract without rebuilding orca.
2. **Reviewer backend abstraction** — Claude vs. Codex vs. future; swap via config.
3. **SDD awareness for meta-development** — perf-lab's runtime has zero knowledge of `spec.md`/`plan.md`/`tasks.md`. Orca knows SDD; this is the only place perf-lab fundamentally cannot self-serve.

What perf-lab could build itself (and largely will): event audit trail, critique-mode workers, quality-gate-at-lease-close hooks, native worktree overlap detection. Orca's `worktree-overlap-check` is included in v1 specifically as a prevent-reinvention play (perf-lab shells out instead of duplicating).

## Composition with Outer-Loop Runtimes

Orca is an **inner-loop** opinion layer + capability library. Outer-loop runtimes own ticket-fetching, workspace lifecycle, agent process supervision, and retry orchestration. Orca does not.

Concrete examples of outer-loop runtimes orca composes with:

- **Symphony** (OpenAI, 2026-04-28): polls Linear for tickets, dispatches Codex app-server sessions into per-issue workspaces, manages continuation turns. The Codex agent inside the workspace can invoke orca slash commands (`/orca:review-spec`, `/orca:review-code`) or `orca-cli` directly during execution. See `docs/superpowers/notes/2026-04-29-symphony-readout.md` for the full readout.
- **Perf-lab v6**: self-organizing research runtime with its own scheduler, claim/lease model, and event ledger. Perf-lab invokes orca skills (`perf-cite`, `perf-contradict`, `perf-review`) at lifecycle points where structured cross-agent review or citation hygiene matters. Phase 4b spec defines the integration.
- **Future Symphony-style runtimes** for other trackers (GitHub Issues, Jira) or other agents (Cursor, OpenHands, etc.): same composition pattern — orca capabilities are JSON-in/JSON-out CLI calls invokable from any agent session.

The composition pattern, generalized:

1. **Outer loop** dispatches an agent into a per-task workspace (Symphony does this for Linear tickets; perf-lab v6 does this for research claims).
2. **Agent inside workspace** invokes orca slash commands or shells out to `orca-cli` for opinion-layer work (review, validation, gate checks).
3. **Host harness** (Claude Code, Codex, perf-lab devcontainer) handles subagent dispatch via Phase 4a's file-backed reviewer pattern.
4. **Orca capabilities** return JSON envelopes; host translates to the runtime's event/state ledger as needed (e.g., perf-lab's `synthesis_validated` events, Symphony's structured logs).

Why this matters for v1: it sets the boundary cleanly. Orca should never grow tracker integrations, polling loops, persistent workspace management, or agent process supervision. Those are outer-loop concerns. When tempted to add "automatic" enforcement at lifecycle boundaries, push back: that's the outer loop's job, and orca's role is to provide the primitive that the outer loop calls.

The path-safety contract at `docs/superpowers/contracts/path-safety.md` (lifted from Symphony §9.5 and generalized for orca) defines the invariants every orca capability that accepts paths must enforce, so capabilities behave consistently regardless of which outer-loop runtime invokes them.

## Open Questions for Spec Self-Review

- Does the perf-lab integration shim need its own version pinning to perf-lab's spec version? (Currently no; relies on event taxonomy alignment via the 010 spec note.)
- Should `findings_ref` artifacts under `/shared/orca/<event_id>/` be cleaned up after some retention period, or kept indefinitely? (Currently: kept; perf-lab's retention is the operator's call.)
- Is the v1 cut of the personal opinion layer (slash commands) just a rename, or does anything actually change in those commands? (Currently: rename + kill-list-related deletions; behavior unchanged.)
