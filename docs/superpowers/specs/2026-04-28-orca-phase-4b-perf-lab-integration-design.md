# Orca Phase 4b: Perf-Lab Integration (Spec Contribution) — v2

**Date:** 2026-04-28 (v1) / 2026-04-29 (v2 revision)
**Status:** Design (post-cross-pass-review revision; pre-implementation-plan)
**Predecessors:**
- `docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md` (v1 north star)
- `docs/superpowers/specs/2026-04-28-orca-phase-4a-in-session-reviewer-design.md` (Phase 4a, landed)
- v1 of this spec (`bb78733`) — see `docs/superpowers/reviews/2026-04-28-orca-phase-4b-review-spec.md` for the cross-pass review that drove this v2
- `docs/superpowers/contracts/path-safety.md` (referenced by Path Validation section)
- `docs/superpowers/notes/2026-04-29-symphony-readout.md` (Symphony composition pattern, stall-timeout precedent)

## Why v2

v1 of this spec was reviewed via cross-pass and found NEEDS-REVISION with seven convergent blockers. v2 fixes the architectural issues, aligns with the existing perf-lab spec.md "Future Integration Notes" instead of contradicting it, and pulls the orca repo prerequisites out of the implementation plan and into this spec where they belong.

The biggest structural change: **skills do not dispatch subagents.** Subagent dispatch is the host LLM's responsibility (Phase 4a was explicit on this). v1 incorrectly placed dispatch inside `entry.sh` bash scripts running under `flock` inside a devcontainer. v2 splits the work into three layers: host-side dispatch (LLM + Agent tool), thin skill (orca-cli wrapper, file-flag passthrough), and the opaque orca-cli capability call.

## Deliverable

Phase 4b ships a **spec contribution PR** to the perf-lab repo (no running code). The PR adds:

- New file: `perf-lab/specs/010-self-organizing-research-runtime/orca-integration.md` (the integration spec)
- A unified-diff replacement of the existing "Future Integration Notes" subsection in `perf-lab/specs/010-self-organizing-research-runtime/spec.md` (lines 420-451 of commit `1c0ddae`). v1 silently appended; v2 explicitly replaces, since v1's added content collided with the existing block.
- Implementation tasks block in `perf-lab/specs/010-self-organizing-research-runtime/tasks.md`, blocked on T000i (perf-event skill foundation)
- Reference to a parallel orca-repo prerequisite block (Phase 4b-pre) that must merge before T0Z03/04/05 in perf-lab

Phase 4b deliberately does NOT ship running code in the perf-lab repo. perf-lab v6 is mid-build (T000a-T000j unfinished); the perf-lab side waits on T000i. Phase 4b also adds **five prerequisite tasks to the orca repo** (Phase 4b-pre-1 through pre-5 below), which CAN ship now and unblock perf-lab T0Z when v6 reaches T000i.

## Context

The v1 north star originally proposed Phase 4 as a perf-lab integration shim living in the orca repo at `orca/integrations/perf_lab/`. After Phase 4a's "orca = JSON-in JSON-out library" framing, that location is wrong: perf-lab-specific event translation belongs in the perf-lab repo so orca stays opaque. Phase 4b reflects that revised architecture.

The integration is **opt-in**: perf-lab v1 must continue to operate without orca. orca skills are tools agents may invoke; orca-driven enforcement at perf-synthesis or perf-lease boundaries is gated on per-claim config, with all defaults disabled.

Phase 4a unblocks Phase 4b by removing the `ANTHROPIC_API_KEY` dependency. Inside perf-lab's devcontainer, claude/codex hosts can dispatch their own subagent reviewers, write findings to a file, and call orca-cli with `--claude-findings-file` / `--codex-findings-file`. No API key required.

## Three-Layer Architecture

```
                    ┌─────────────────────────────────────┐
  Host LLM session  │ Slash command / harness wrapper     │
  (Claude Code,     │ - dispatches Agent-tool subagent    │
   Codex, etc.)     │ - parses response → findings.json   │
                    │ - then invokes perf-lab skill       │
                    └────────────────┬────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
  perf-lab          │ Skill (perf-cite / perf-contradict / │
  devcontainer      │       perf-review)                  │
  (under flock)     │ - reads findings.json (already on   │
                    │   disk; skill never dispatches)     │
                    │ - calls orca-cli with file flag     │
                    │ - parses envelope                   │
                    │ - emits perf-event                  │
                    └────────────────┬────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
  orca-cli          │ Opaque capability                   │
                    │ (citation-validator / contradiction-│
                    │  detector / cross-agent-review)     │
                    └─────────────────────────────────────┘
```

The skill never holds a subagent in flight. By the time `entry.sh` runs, the findings file is already written by the host LLM. The skill is bash + flock + orca-cli; no Agent tool, no LLM. This matches Phase 4a's slash-command pattern exactly.

### Three new perf-lab skills

- **`perf-cite`** wraps `orca-cli citation-validator` (no host-side dispatch needed; mechanical capability)
- **`perf-contradict`** wraps `orca-cli contradiction-detector` (host-side dispatch produces findings file; skill consumes it)
- **`perf-review`** wraps `orca-cli cross-agent-review` (host-side dispatch produces findings file; skill consumes it)

### Host-side dispatch wrappers

Two new perf-lab-side wrappers run OUTSIDE the devcontainer (or inside, in an interactive session — wherever the Agent tool is available):

- **`scripts/perf-lab/orca-dispatch-contradict.sh`** — for any host wanting to call `perf-contradict`. Builds prompt via `orca-cli build-review-prompt --kind contradiction`, dispatches subagent, parses response, writes findings file, then invokes the skill via `claim-run perf-contradict ...`.
- **`scripts/perf-lab/orca-dispatch-review.sh`** — same shape for `perf-review`.

In Claude Code these are wrapped by slash commands (`/perf:contradict`, `/perf:review`) that handle the Agent tool dispatch via the same prompt template Phase 4a uses. In Codex, they're shell scripts the harness invokes.

### Two opt-in enforcement points (defaults OFF)

- **`perf-synthesis` commit flow** can call `perf-cite` and `perf-contradict` as gates if claim config sets `orca_policy.synthesis_validators`. **Validators run AFTER synthesis content is written but BEFORE acquiring `synthesis.lock`** — see "Lock and timeout policy" below.
- **`scripts/runtime-v6/lease.sh`** (host-side scheduler, NOT the `perf-lease` worker skill) can call `orca-cli worktree-overlap-check` if claim config sets `orca_policy.lease_overlap_check: "orca"`. This explicitly does NOT live in the `perf-lease` worker skill, which is read-only (check/info ops only per perf-lab's skill contract).

## Skill Contracts

### `perf-cite`

```
perf-cite --content-path <path> [--reference-set <path>]... [--mode strict|lenient]
```

Wraps `orca-cli citation-validator`. Validates citation hygiene in synthesis text. No subagent dispatch (citation-validator is purely mechanical).

- Required: `--content-path` (markdown file inside `/shared/` to validate; symlinks rejected)
- Optional: `--reference-set` (repeatable; defaults to claim feature dir auto-discovery per Phase 3.2 backlog item 2 (`docs/superpowers/notes/2026-04-27-phase-3-2-backlog.md` § "Citation default reference set should auto-discover"))
- Optional: `--mode strict|lenient` (default `strict`)

Behavior:
1. Validate `--content-path` resolves inside `/shared/` and is a regular file (not a symlink, not a directory).
2. Resolve reference set (auto-discover if not provided).
3. Shell to `orca-cli citation-validator --content-path ... --reference-set ... --mode ...`
4. Parse JSON envelope; on `Err(...)`, emit `synthesis_validated` event with `payload.error = {kind, message}` and exit 1.
5. **Read coverage from envelope** (do not recompute; orca-cli already produced it).
6. Compare against operator-configured threshold (`orca_policy.cite_threshold`, default 1.0).
7. Emit `synthesis_validated` event. Payload aligns with existing perf-lab spec.md line 437: `{uncited_spans, broken_refs, citation_coverage}` plus orca-runtime fields `{capability: "citation-validator", capability_version, duration_ms, threshold, exit_status}`. Note: `capability_version`, not `version` — avoids collision with perf-event's `payload_version` envelope field.
8. Exit 0 if coverage >= threshold; exit 1 with stderr listing uncited spans and broken refs otherwise.

Concurrency: `flock /shared/locks/cite.lock` only when writing reports to `/shared/`, NOT around the orca-cli call (which is read-only).

### `perf-contradict`

```
perf-contradict --content-path <path> --evidence-path <path> --findings-file <path>
```

Wraps `orca-cli contradiction-detector --claude-findings-file <path>`. The findings file is **a precondition**, not something the skill produces. Host must run `orca-dispatch-contradict.sh` first (or the equivalent slash command) to populate it.

- Required: `--content-path` (the new synthesis content; symlinks rejected; must be a regular file inside `/shared/`)
- Required: `--evidence-path` (prior evidence file; symlinks rejected; directories rejected to prevent traversal)
- Required: `--findings-file` (path to JSON file produced by `parse-subagent-response`; must exist and parse)

Behavior:
1. Validate all three paths: resolve, reject symlinks, reject directories for `--content-path` and `--evidence-path`, require regular files inside `/shared/`.
2. Verify `--findings-file` exists and is non-empty. If missing, emit failure event with `error.kind = "MISSING_FINDINGS_FILE"` and exit 2 (operator config error, not a runtime failure).
3. Detect host harness from env (`HARNESS=claude-code` or `HARNESS=codex`); pick `--claude-findings-file` or `--codex-findings-file` accordingly.
4. Shell to `orca-cli contradiction-detector --claude-findings-file <path> --new-content <path> --prior-evidence <path>` (note the actual orca CLI uses `--new-content`/`--prior-evidence`, not `--content-path`/`--evidence-path`; skill normalizes the names).
5. Parse JSON envelope; emit `contradiction_detected` event. Payload aligns with existing perf-lab spec.md line 438: `{contradictions: [...]}` (with refs and confidence per orca contract) plus orca-runtime fields `{capability: "contradiction-detector", capability_version, duration_ms, contradiction_count, exit_status}`.
6. Exit 0 if zero contradictions; exit 1 if any found (caller decides whether to escalate to `feedback_needed`).

Concurrency: `flock /shared/locks/contradict.lock` for shared writes only.

### `perf-review`

```
perf-review --kind {spec,diff,pr,artifact} --target <path> --findings-file <path> [--criteria <c>]... [--feature-id <id>]
```

Wraps `orca-cli cross-agent-review --claude-findings-file <path>`. Like `perf-contradict`, the findings file is a precondition.

- Required: `--kind`, `--target`, `--findings-file`
- Optional: `--criteria` (repeatable), `--feature-id` (defaults to claim's feature ID)

Behavior:
1. Validate `--target` resolves inside `/shared/`; reject symlinks; allow regular files OR directories (cross-agent-review accepts both).
2. Verify `--findings-file` exists and parses.
3. Detect host harness; pick correct flag.
4. Shell to `orca-cli cross-agent-review --claude-findings-file <path> --kind ... --target ... --feature-id ... [--criteria ...]`.
5. Parse envelope; emit **`cross_review_summary`** event (not `quality_gate` — see Event Types below). Payload: `{capability: "cross-agent-review", capability_version, duration_ms, kind, finding_count, severity_breakdown: {blocker, high, medium, low, nit}, exit_status, target_sha256, criteria_hash}`. The `criteria_hash` is required for `review_required` gate satisfaction (see Claim Config Additions); skill computes it as `sha256` of the sorted, joined criteria list.
6. Exit 0 always (review is informational; agent reads findings and decides).

Concurrency: `flock /shared/locks/review.lock` for shared writes only.

## Event Types — Reconciliation with Existing spec.md

The existing perf-lab `spec.md` lines 425-451 already define event payloads for orca integration. v1 of this Phase 4b spec proposed conflicting payloads. v2 reconciles by:

1. **Keeping the existing `synthesis_validated` and `contradiction_detected` payload field names** (`uncited_spans`, `broken_refs`, `citation_coverage`, `contradictions[]`).
2. **Reusing `quality_gate` ONLY for `orca:completion-gate`** as the existing spec.md line 436 specifies. Phase 4b does NOT integrate completion-gate (out of scope), so Phase 4b does NOT emit `quality_gate`. Future work that integrates completion-gate emits it then.
3. **Adding a new event type `cross_review_summary`** for `perf-review`. This avoids overloading `quality_gate` for cross-agent-review (different semantics: review is informational, gate is pass/fail).

The proposed FR-008 amendment thus updates the canonical event taxonomy to:

| Type | Payload (orca-side fields) | Emitted by |
|------|---------------------------|------------|
| `synthesis_validated` | `uncited_spans`, `broken_refs`, `citation_coverage` + runtime: `capability`, `capability_version`, `duration_ms`, `threshold`, `exit_status` | `perf-cite` (always); `perf-synthesis` (if `orca_policy.synthesis_validators` includes `cite`) |
| `contradiction_detected` | `contradictions[]` + runtime: `capability`, `capability_version`, `duration_ms`, `contradiction_count`, `exit_status` | `perf-contradict` (always); `perf-synthesis` (if `orca_policy.synthesis_validators` includes `contradict`) |
| `cross_review_summary` | `kind`, `finding_count`, `severity_breakdown`, `target_sha256`, `criteria_hash` + runtime fields | `perf-review` (always) |
| `quality_gate` | `gate_result_ref`, `blockers`, `target_stage` | (RESERVED for future `orca:completion-gate` integration; not emitted in Phase 4b) |

All four types must land in `perf-event`'s FR-008 canonical list **before** any skill emits them — `perf-event` rejects unknown types with exit 3. Implementation tasks enforce this ordering: T0Z02 (FR-008 amendment) is a hard prerequisite for T0Z03/04/05 (skill emissions).

**On `claim_id` in event-binding gates:** `claim_id` is carried on the `perf-event` envelope's standard fields (alongside `event_id`, `timestamp`, `harness`, `image_digest`), NOT inside the per-event payload. Gate verification reads `claim_id` from the envelope. The same applies to `cross_review_summary` events satisfying `review_required`: the gate checks the envelope's `claim_id` matches the active claim, plus the payload's `target_sha256` and `criteria_hash` match the gate's binding fields. Adding `claim_id` to the payload would duplicate envelope state; the spec leaves it on the envelope only.

### Unified-diff replacement of existing spec.md text

The existing perf-lab `spec.md` Future Integration Notes section (lines 420-451) currently says the shim lives in the orca repo. v2 directly contradicts that, so the spec PR replaces the section. The diff is part of the deliverable:

```diff
-### v1 orca catalog consumed by perf-lab
-
-The orca v1 catalog provides six capabilities. The perf-lab integration shim translates outputs from all six. Runtime hot-path use focuses on:
-
-- `cross-agent-review` — invoked when a `critique` claim fires; findings emitted as `critique` events with a structured payload schema.
-- `worktree-overlap-check` — invoked from `lease.sh`'s overlap detection; conflict result drives `lease_rejected` events.
-- `citation-validator` — invoked after `synthesis_updated` and `artifact_updated` events to verify refs.
-- `contradiction-detector` — invoked after `synthesis_updated` and `theory_updated` to detect conflicts with raw evidence.
-
-The remaining two capabilities (`completion-gate`, `flow-state-projection`) are SDD-aware and primarily serve perf-lab's *meta-development* (perf-lab as a project being developed via Research-Plan-Implement), not perf-lab's research-loop runtime. They are not invoked from runtime hot paths.
-
-### New event types introduced when orca integration is enabled
-
-When the orca integration ships (post-v1), the FR-008 canonical event taxonomy MUST extend with:
-
-- `quality_gate`: emitted by the perf-lab integration shim when `orca:completion-gate` returns a non-pass result. Payload includes `gate_result_ref`, `blockers`, `target_stage`. Relevant for meta-development gates; not emitted by runtime hot path in v1.
-- `synthesis_validated`: emitted after `orca:citation-validator` runs. Payload includes `uncited_spans`, `broken_refs`, `citation_coverage`.
-- `contradiction_detected`: emitted by `orca:contradiction-detector` when new synthesis or theory conflicts with raw evidence. Payload includes `contradictions[]` with refs and confidence.
-
-Adding these event types follows FR-008's amendment process: extend the canonical list and add corresponding schema entries before the integration is enabled.
-
-### Shim location and ownership
-
-The integration shim lives in the `orca` repo under `integrations/perf_lab/`. Perf-lab does not vendor orca code. Perf-lab's scheduler shells out to orca's CLI when the integration is enabled. Perf-lab's `events.jsonl` remains canonical; raw orca outputs (`findings.json`, `gate-result.json`, etc.) are captured as referenced artifacts under `/shared/orca/<event_id>/` but only the translated event is canonical.
+### v1 orca catalog consumed by perf-lab
+
+The orca v1 catalog provides six capabilities. Perf-lab integrates four via three skills (`perf-cite`, `perf-contradict`, `perf-review`) defined in `orca-integration.md`:
+
+- `cross-agent-review` — invoked via `perf-review`; findings emitted as `cross_review_summary` events.
+- `worktree-overlap-check` — invoked from host-side `scripts/runtime-v6/lease.sh`'s overlap check (NOT from a worker skill); conflict result drives `lease_rejected` events.
+- `citation-validator` — invoked via `perf-cite` after synthesis content is written; emits `synthesis_validated`.
+- `contradiction-detector` — invoked via `perf-contradict` after synthesis or theory updates; emits `contradiction_detected`.
+
+The remaining two capabilities (`completion-gate`, `flow-state-projection`) are SDD-aware and primarily serve perf-lab's *meta-development*, not the runtime. Not integrated in Phase 4b.
+
+### New event types introduced when orca integration is enabled
+
+The FR-008 canonical event taxonomy extends with the four types defined in `orca-integration.md`:
+`synthesis_validated`, `contradiction_detected`, `cross_review_summary`, and `quality_gate` (reserved for future completion-gate integration; not emitted in Phase 4b).
+
+Adding these event types follows FR-008's amendment process: extend the canonical list and add corresponding schema entries before the integration is enabled.
+
+### Shim location and ownership
+
+The integration lives in the perf-lab repo. Three new perf-lab skills (`perf-cite`, `perf-contradict`, `perf-review`) wrap orca-cli calls; orca itself stays opaque (JSON-in JSON-out CLI). Perf-lab's scheduler invokes the skills inside the devcontainer; subagent dispatch happens host-side BEFORE skill invocation (see `orca-integration.md` § Three-Layer Architecture). Perf-lab's `events.jsonl` remains canonical; raw orca envelopes are captured as referenced artifacts under `/shared/orca/<claim_id>/<round_id>/<kind>-<timestamp>.json` but only the translated event is canonical.
```

(The implementation plan instructs the implementer to land this diff verbatim alongside the new `orca-integration.md`. If perf-lab's spec.md has drifted by then, the implementer reconciles by hand; the contract is that the new text is what survives.)

The `### Constraints` subsection in perf-lab spec.md (currently lines 446-451) is **NOT touched** by this diff — those constraints (timeouts, model-tier inheritance, host-only invocation) remain in force and Phase 4b's policies are additive on top of them.

## Claim Config Additions

Per-claim config gains an optional `orca_policy` block:

```json
{
  "claim_id": "abc123",
  "mode": "implement",
  "orca_policy": {
    "synthesis_validators": ["cite", "contradict"],
    "lease_overlap_check": "orca",
    "review_required": {
      "kind": "diff",
      "target_sha256": "<sha>",
      "criteria_hash": "<sha>",
      "claim_id": "abc123"
    },
    "cite_threshold": 1.0,
    "cite_reference_set": ["plan.md", "research.md"],
    "model_tier_floor": "strong"
  }
}
```

Field semantics (all optional, defaults null/disabled):

- **`synthesis_validators`**: list, subset of `["cite", "contradict"]`. If non-empty, `perf-synthesis` invokes the named validators after writing synthesis content. Validators run **before acquiring `synthesis.lock`** (see lock policy below); the lock is only held for the actual commit, not the validator window. Validator failure -> commit aborts; agent gets a `feedback_needed` event.

- **`lease_overlap_check`**: if set to `"orca"`, host-side `scripts/runtime-v6/lease.sh` calls `orca-cli worktree-overlap-check` before granting any lease whose paths overlap an active lease. NOT routed through the `perf-lease` worker skill (which remains read-only).

- **`review_required`**: object (not just kind). For a `cross_review_summary` event to satisfy a gate, the event must bind to specific content. Required sub-fields:
  - `kind` — one of `spec/diff/pr/artifact`
  - `target_sha256` — hash of the artifact being reviewed (prevents stale events from satisfying gates)
  - `criteria_hash` — hash of the criteria list used (prevents loosened-criteria reuse)
  - `claim_id` — the claim ID (prevents cross-claim event reuse)
  Stale `cross_review_summary` events (mismatched on any of the above) do not satisfy the gate.

- **`cite_threshold`**: float in [0.0, 1.0]; default 1.0.

- **`cite_reference_set`**: list of relative paths from claim's feature dir; if unset, `perf-cite` auto-discovers per Phase 3.2 backlog item 2 (`docs/superpowers/notes/2026-04-27-phase-3-2-backlog.md` § "Citation default reference set should auto-discover").

- **`model_tier_floor`**: one of `cheap/standard/strong`; default `cheap`. The host-side dispatch wrapper MUST honor this when selecting the subagent reviewer model. A `cheap`-tier worker invoking `perf-review` MUST NOT escalate to a `strong` reviewer unless `model_tier_floor` is set to `strong` (per existing spec.md line 450).

Defaults: all unset. orca is invisible to vanilla claims. perf-lab v1 operates without orca exactly as it does without Phase 4b shipped.

### Discoverability of opt-in policy

Mission templates (`perf-lab/templates/mission.json`) gain an optional `default_orca_policy` block. Operators starting a new mission with `--orca-on` get a policy template populated; without `--orca-on`, it stays unset. This avoids the "opt-in by default-off" being a config nobody discovers.

## Lock and Timeout Policy

Per existing spec.md line 449: "Failed orca calls MUST NOT block perf-lab rounds indefinitely... default fallback is to emit `feedback_needed` rather than hang." v1 of this spec was silent on this. v2 specifies:

### Lock window for synthesis_validators

When `orca_policy.synthesis_validators` is set, perf-synthesis acquires `synthesis.lock` ONLY for the final commit window — NOT during the validator window. Sequence:

1. Write candidate synthesis content to a temp file outside the lock.
2. Run validators (`perf-cite`, `perf-contradict`) against the temp file. These are LLM-backed for `perf-contradict`; can take minutes.
3. If all validators exit 0: acquire `synthesis.lock`, atomically move temp -> canonical, release lock.
4. If any validator exits 1: emit `feedback_needed` event with the validator failure reason; do NOT acquire `synthesis.lock`; agent retries with feedback.

This prevents the lock from being held during the LLM round-trip.

### Per-capability timeouts

Each skill enforces a hard timeout on the orca-cli call (configurable via env, defaults below):

| Skill | Default timeout | Override env |
|-------|----------------|---------------|
| `perf-cite` | 60s | `ORCA_TIMEOUT_CITE` |
| `perf-contradict` | 300s | `ORCA_TIMEOUT_CONTRADICT` |
| `perf-review` | 300s | `ORCA_TIMEOUT_REVIEW` |

On timeout: skill emits its event with `payload.error = {kind: "TIMEOUT", message, timeout_seconds}`, and exits 1. Caller (perf-synthesis or scheduler) emits `feedback_needed` if the timeout occurred inside a synthesis-validator window.

The host-side dispatch wrapper has its own timeout for the subagent call (default 600s); on dispatch timeout it writes a sentinel findings file `{ok: false, error: {kind: "DISPATCH_TIMEOUT"}}`, which the skill detects and propagates as `payload.error`.

### Stall detection on subagent dispatch

Borrowed from Symphony SPEC §10.6: the host-side dispatch wrapper enforces a stall timeout (default 300s, override via `ORCA_DISPATCH_STALL_TIMEOUT`) measuring time-since-last-event from the subagent. If no Agent-tool events arrive for the stall window, the wrapper kills the subagent and writes a sentinel findings file `{ok: false, error: {kind: "DISPATCH_STALL", elapsed_seconds: N}}`. This complements the hard timeout above: a hung subagent that emits zero events trips the stall timer well before the 600s hard cap, freeing the dispatch slot faster.

Stall detection is a host-side dispatch wrapper concern, not a skill concern. The implementation lives in the perf-lab repo alongside the dispatch wrappers (`scripts/perf-lab/orca-dispatch-lib.sh`, sourced by both `orca-dispatch-contradict.sh` and `orca-dispatch-review.sh`). Phase 4b-pre-4 ships only the **algorithm specification** (event-monitoring loop, default timeout, sentinel findings-file format) in orca's docs; perf-lab's T0Z06 implements the bash helper and Claude Code's slash commands implement an equivalent in their own runtime. Cross-repo bash sourcing is avoided.

## Path Validation

All path-accepting flags in `perf-cite`, `perf-contradict`, `perf-review` and their underlying orca-cli capabilities follow the **path-safety contract** at `docs/superpowers/contracts/path-safety.md`. That contract is canonical; this spec does not duplicate the rules.

In Phase 4b's context specifically (see contract for full rules per class):
- `--content-path`, `--evidence-path`, `--target` are **Class B** (shared paths). Contract Class B requires CLAIM_ID env-match for reads under `/shared/orca/`; this applies to the dispatch wrappers writing findings files and the skills consuming them.
- `--findings-file` (and `--claude-findings-file` / `--codex-findings-file` once Phase 4b-pre-1 lands) is **Class C** (findings-file paths). Contract Class C requires the full path shape `/shared/orca/<claim_id>/<round_id>/<kind>-findings-<timestamp>.json`; v2 defers to the contract for the depth and naming convention rather than restating.
- `--reference-set` for `perf-cite` is **Class A** within the claim's feature directory.
- `CLAIM_ID`, `--feature-id` are **Class D** identifiers.

Skill failure on any path-safety violation: emit the skill's event with `payload.error = {kind: "INPUT_INVALID", rule_violated: "...", field: "..."}` per the contract's error-reporting shape, and exit 1. No traversal attempts reach orca-cli.

## /shared/orca/ Path Conventions

Phase 4a uses `<feature-dir>/.<command>-<reviewer>-findings.json` for in-repo runs. Perf-lab needs a stable path under `/shared/`. Convention:

```
/shared/orca/
  <claim_id>/
    <round_id>/
      cite-findings-<timestamp>.json         # perf-cite (when LLM-backed mode lands)
      contradict-findings-<timestamp>.json   # perf-contradict
      review-findings-<timestamp>.json       # perf-review (perf-review --kind value lives in event payload, not filename)
      <skill>-envelope-<timestamp>.json      # raw orca-cli output
      <skill>-stderr-<timestamp>.log
```

The `<kind>` segment in the path-safety contract Class C shape (`<kind>-findings-<timestamp>.json`) corresponds to the **skill shortname** (`cite`/`contradict`/`review`), not to perf-review's `--kind` argument. perf-review's `--kind` value (one of `spec`/`diff`/`pr`/`artifact`) is captured in the `cross_review_summary` event payload, not in the filename. Avoids namespace collision between two different `kind` concepts.

- **Owner of `<claim_id>/`**: `perf-claim`'s claim-create flow MUST create `/shared/orca/<claim_id>/` with mode 0775 (group write for the claim's worker UID). `perf-claim` close flow tars `/shared/orca/<claim_id>/` to the claim's archive dir and removes the live directory.
- **Owner of `<round_id>/`**: `perf-claim`'s round-increment flow MUST create `/shared/orca/<claim_id>/<round_id>/` with mode 0775 atomically when the round counter advances. Skills NEVER create round subdirs themselves — they assert existence and fail with `INPUT_INVALID` if absent (which indicates round-counter desync). Round ID comes from perf-claim's round counter (zero-padded integer, e.g., `r0001`).
- **Timestamp suffix**: ISO-8601 millis (`20260429T143000123Z`) avoids overwrite collisions when a single round runs multiple validators.
- **Cleanup**: `perf-claim close` is the canonical cleanup hook. No skill runs `rm` directly.
- **Concurrent writes**: writes within a single round are serialized by the per-skill flock (`/shared/locks/<skill>.lock`).

## Devcontainer Installation

`perf-lab/.devcontainer/Dockerfile` (currently spec'd in T000b) needs `orca-cli` available at runtime. Two paths:

```dockerfile
# Option A: PyPI install once orca publishes there
# (Phase 4b-pre-3 decided 2026-04-29: bind-mount only; this PyPI install line is documented but unused.)
RUN pip install --no-cache-dir uv && \
    uv tool install spec-kit-orca==<version-pin>

# Option B: bind-mount source tree (development; current state)
ENV ORCA_PROJECT=/opt/orca
# (perf-lab compose file mounts host orca tree at /opt/orca read-only)
```

Phase 4b-pre-3 (orca repo) decides the publication strategy; T0Z11 (perf-lab repo) implements whichever path was chosen. See Orca Repo Prerequisites below.

`<version-pin>` is the orca git tag at perf-lab v6 release time. Pinning forces explicit Dockerfile bumps for orca upgrades; combined with the compatibility contract below, this gives operators a predictable upgrade path.

## Orca-CLI Compatibility Contract

perf-lab's Dockerfile pins a specific orca version. Phase 4b defines a contract orca-cli must satisfy at that version, and a probe perf-lab uses to verify it.

### Minimum capability matrix at perf-lab v6 release

| Capability | Required flags | Required envelope version |
|-----------|----------------|---------------------------|
| `cross-agent-review` | `--claude-findings-file`, `--codex-findings-file`, `--kind`, `--target`, `--feature-id`, `--criteria` (repeatable) | `1.x` |
| `contradiction-detector` | `--claude-findings-file`, `--codex-findings-file`, `--new-content`, `--prior-evidence` (repeatable) | `1.x` |
| `citation-validator` | `--content-path`, `--reference-set` (repeatable), `--mode` | `1.x` |
| `worktree-overlap-check` | `--paths` (repeatable) or equivalent | `1.x` |
| `build-review-prompt` | `--kind`, `--criteria`, `--context` | n/a |
| `parse-subagent-response` | (stdin → stdout) | n/a |
| (top-level) | `--version` (prints `<package> <semver>` to stdout, exit 0) | n/a |

### Startup probe

`scripts/perf-lab/orca-probe.sh` runs at devcontainer build (and optionally at claim start when `orca_policy` is set). It:

1. Calls `orca-cli --version`; verifies exit 0 and parses semver. If `--version` missing, fails with a clear message: "orca-cli too old for Phase 4b; needs orca >= X.Y.Z (must implement --version)."
2. Calls each required capability with `--help`; greps for required flags. Missing flag → fail.
3. Writes a probe report to `/shared/orca/_probe-<timestamp>.json`.

If probe fails, perf-lab refuses to honor `orca_policy` and falls back to vanilla v1 behavior (with a warning event). This means orca version drift never wedges perf-lab silently.

### Fixture test matrix

For perf-lab CI: a fixture set under `tests/fixtures/orca/` containing canned envelopes for each capability at envelope version 1.0. Skill tests stub `orca-cli` with `tests/bin/fake-orca-cli.sh` returning the fixtures. This lets perf-lab's downstream tests run without a real orca install.

## Failure Modes

| Scenario | Skill behavior |
|----------|----------------|
| `orca-cli` not in PATH and `ORCA_PROJECT` unset | Exit 2 with stderr `"orca-cli not found; check Dockerfile install or set ORCA_PROJECT"` |
| Probe failed at devcontainer build | Skill exits 2 with `"orca compatibility probe failed; orca_policy disabled"` |
| orca capability returns `Err(INPUT_INVALID)` | Skill emits its event with `payload.error = {kind, message}`; exits 1 |
| orca capability returns `Err(BACKEND_FAILURE)` | Skill emits its event with `payload.error`; exits 1 with stderr surfaced |
| Skill timeout exceeded | Emit event with `payload.error = {kind: "TIMEOUT"}`; exit 1; perf-synthesis converts to `feedback_needed` |
| `--findings-file` missing or unparseable | Skill exits 2 with `error.kind = "MISSING_FINDINGS_FILE"` (config error, not runtime) |
| Host harness has no Agent tool (e.g., bare shell, pi.sh) | Host-side dispatch wrapper exits 2 with `"in-session reviewer unavailable on this host; cannot satisfy orca_policy.synthesis_validators=[contradict] or review_required"`. **Operators on Codex hosts that lack Agent tool support must either (a) restrict `orca_policy` to `cite`-only, or (b) configure their Codex harness to expose Agent-tool equivalents, or (c) set `synthesis_validators=[]` for that claim.** Documented in T0Z11 operator guide. |
| Path outside `/shared/` or symlink in path | Exit 1 with `error.kind = "INPUT_INVALID"`, specific message |
| `CLAIM_ID` unset | Exit 1 with `"missing CLAIM_ID; orca skills run only inside a claim"` |
| `synthesis.lock` deadlock risk | NOT POSSIBLE in v2: validators run before lock acquisition (see Lock and Timeout Policy) |
| orca version below required minimum | Probe rejects at devcontainer build; orca_policy disabled with warning event |

## Test Plan — Split

v1 conflated spec-PR review with downstream implementation tests. v2 splits cleanly:

### Spec-PR review checks (run on the perf-lab spec PR itself)

These run in perf-lab's CI on the spec PR (not against running code):

- Markdown lint: `mdformat --check` on `orca-integration.md` and the modified `spec.md` section.
- Cross-ref check: every internal `<file>#<anchor>` reference resolves.
- Schema-doc validation: the four event types defined here match the JSON schema document syntax used in `data-model.md`.
- Diff-conflict check: confirm the unified diff applies cleanly to `spec.md` HEAD at PR-merge time.
- Front-matter validation: `orca-integration.md` matches the format of sibling spec-010 docs.

### Downstream implementation tests (T0Z03+ tasks; out of scope for the spec PR)

These run after T000i lands and the actual skills are implemented:

- **Skill smoke tests**: `tests/skills/test_perf_cite.bats`, `test_perf_contradict.bats`, `test_perf_review.bats`. Bats. Stub `orca-cli` with `tests/bin/fake-orca-cli.sh`.
- **Event schema validation**: extend `tests/events/test_event_schema.py` to validate the four new event types' payloads.
- **Integration tests**: `tests/integration/test_orca_synthesis_gate.bats`, `test_orca_lease_overlap.bats`, `test_orca_review_required.bats`. Mark as integration; require orca-cli installed.
- **Probe tests**: `tests/scripts/test_orca_probe.bats` exercises happy path + each fail mode.
- **Claim-config validator**: extend perf-lab's claim-config validator to recognize `orca_policy`.
- **Lock-window tests**: `test_orca_synthesis_lock_window.bats` confirms `synthesis.lock` is NOT held during validator runs.

## Implementation Tasks (added to perf-lab tasks.md)

Block T0Z (orca integration), all blocked on T000i (skill foundation):

- T0Z00: **Wait gate** — confirm orca repo prerequisites (Phase 4b-pre-1 through Phase 4b-pre-5 below) have merged before starting T0Z03.
- T0Z01: Author `perf-lab/specs/010-.../orca-integration.md` (the spec contribution itself).
- T0Z02: **(prerequisite for T0Z03+)** Add `synthesis_validated`, `contradiction_detected`, `cross_review_summary` to FR-008 canonical event list in spec.md and corresponding payload schemas in `data-model.md`. Reserve `quality_gate` for future completion-gate integration. Block T0Z03/04/05 on this task.
- T0Z03: Implement `perf-cite` skill (entry.sh + SKILL.md + Bats tests).
- T0Z04: Implement `perf-contradict` skill (entry.sh + SKILL.md + Bats tests).
- T0Z05: Implement `perf-review` skill (entry.sh + SKILL.md + Bats tests).
- T0Z06: Implement host-side dispatch wrappers `scripts/perf-lab/orca-dispatch-{contradict,review}.sh` plus the shared helper `scripts/perf-lab/orca-dispatch-lib.sh` (intra-perf-lab; implements stall detection + hard timeout + sentinel findings-file format per orca's `docs/superpowers/contracts/dispatch-algorithm.md`). Add corresponding slash commands for Claude Code; document Codex equivalent.
- T0Z07: Extend claim config schema for `orca_policy` block (validator + tests, including `review_required` binding fields).
- T0Z08: Wire `synthesis_validators` policy into `perf-synthesis` commit flow with the lock-window discipline (validators outside lock).
- T0Z09: Wire `lease_overlap_check` policy into `scripts/runtime-v6/lease.sh` (NOT into `perf-lease` worker skill).
- T0Z10: Wire `review_required` policy into commit flows; verify event-binding fields.
- T0Z11: Add orca-cli install line to `.devcontainer/Dockerfile` (T000b); verify PyPI publication state of `spec-kit-orca`; document bind-mount fallback.
- T0Z12: Implement `scripts/perf-lab/orca-probe.sh` and wire into devcontainer build + claim-start.
- T0Z13: Document orca-policy operator guide in `docs/runtime/orca-policy.md` including the Codex-host limitation, model-tier policy, and discoverability via mission template.

Each task gets perf-lab's standard task shape (description, files, acceptance criteria).

## Orca Repo Prerequisites (Phase 4b-pre)

These tasks land in the **orca repo** before perf-lab T0Z03 can begin. They are scoped to the orca repo and can ship now (don't wait on perf-lab v6).

- **Phase 4b-pre-1**: Add `--claude-findings-file` and `--codex-findings-file` to `orca-cli contradiction-detector`. Mirror Phase 4a's `cross-agent-review` implementation: file-backed reviewer adapter, INPUT_INVALID preflight, fixture tests. Estimated 1 task in orca's plan.
- **Phase 4b-pre-2**: Add `orca-cli --version` top-level flag. Print `orca <semver>` and exit 0 (package name is `orca` per `pyproject.toml`; `spec-kit-orca` was the legacy fork name pre-rename). Tested by adding `--version` to the existing CLI smoke tests. ~30 min of work.
- **Phase 4b-pre-3**: **DECIDED 2026-04-29: Option C — no PyPI publication; bind-mount only.** See `docs/superpowers/notes/2026-04-29-pypi-publication-decision.md`. T0Z11 implements bind-mount per the decision artifact. The PyPI install line below is documented but DEFERRED until an external consumer requests publication.
- **Phase 4b-pre-4**: Document the host-side subagent-dispatch algorithm with stall detection (per Symphony SPEC §10.6) in orca's docs as `docs/superpowers/contracts/dispatch-algorithm.md`. Specifies: event-monitoring loop semantics, default timeouts (300s stall, 600s hard), sentinel findings-file format on timeout/stall, error envelope shape. Each consumer (perf-lab bash wrappers, Claude Code slash commands, future Codex hosts) implements the algorithm in its own runtime — no shared bash helper crosses repos. Estimated half-day of doc work.
- **Phase 4b-pre-5**: Add a regression test asserting `orca-cli build-review-prompt --kind <arbitrary-string>` succeeds for any non-empty string (current behavior is documented as "accepts any kind without branching"; this fixes the contract by codifying it). Trivial: one test file, one assertion. Required so Phase 4b's `orca-dispatch-contradict.sh` can rely on `--kind contradiction` not failing in some future orca version that adds kind-validation.

These five are merge prerequisites for the perf-lab spec PR. The spec PR explicitly cites the orca SHAs that satisfy them in its description.

## Cross-Repo Considerations

Phase 4b lands in perf-lab repo. orca repo gets the three prerequisite tasks above. Two ongoing cross-repo concerns:

1. **Version contract enforcement**: perf-lab's startup probe (T0Z12) is the primary enforcement mechanism. orca-cli's `--version` output and capability help-text become a compatibility contract. Any orca change that removes a flag or breaks an envelope shape requires a major-version bump and a corresponding perf-lab Dockerfile bump.
2. **Cross-repo CI**: out of scope for Phase 4b. A future task could add an orca-side smoke test that verifies all flags listed in the compatibility matrix are still present, breaking orca CI when they regress. Tracked as orca repo follow-up.

## Out of Scope (Phase 4b)

- Implementing the perf-lab skills (waits on T000i — perf-event foundation)
- New orca capabilities (use existing 6)
- `flow-state-projection` integration (perf-lab has its own scheduler; orca's projection is for SDD)
- `completion-gate` integration (SDD-specific stage gates don't apply to perf-lab's claim/round model in v1; `quality_gate` event type is reserved but not emitted)
- Automatic enforcement (per user decision: opt-in via claim config only; no global default-on)
- Cross-repo CI ensuring perf-lab and orca versions stay compatible (manual via probe today)
- Operator UX for migrating existing perf-lab v5 runs to use orca skills (no migration; v6 is a fresh runtime)
- A perf-lab equivalent of Phase 4a's `parse-subagent-response` — perf-lab reuses orca's. If perf-lab needs a different parser shape later, that's a perf-lab task, not an orca task.

## Resolved Design Decisions (v2)

- **Integration lives in perf-lab repo**, not orca repo (deviation from v1 north-star). Phase 4a's "orca = opaque library" framing made this the right call. v2 carries this through and explicitly replaces the v1 north-star's "shim in orca/integrations/" text.
- **Three thin skills** (`perf-cite`, `perf-contradict`, `perf-review`) plus host-side dispatch wrappers running OUTSIDE the skill boundary. Default behavior: orca invisible.
- **Subagent dispatch is host-side**, never inside `entry.sh`. v1 violated Phase 4a's framing on this; v2 fixes by splitting into three layers.
- **`lease_overlap_check` is scheduler-side**, not worker-skill-side. `perf-lease` skill remains read-only.
- **Event payloads align with existing perf-lab spec.md** (`uncited_spans`, `broken_refs`, `citation_coverage`, `contradictions[]`); `cross_review_summary` is a new type for `perf-review`; `quality_gate` reserved for future completion-gate work.
- **Lock window is tight**: `synthesis.lock` held only for the commit, not for validator runs.
- **Per-capability timeouts** with `feedback_needed` fallback per existing spec.md line 449.
- **Model-tier inheritance via `orca_policy.model_tier_floor`** per existing spec.md line 450.
- **`review_required` binds to content** via `target_sha256`, `criteria_hash`, `claim_id` (prevents stale-event gate satisfaction).
- **Orca repo prerequisites called out explicitly** as merge gates: Phase 4b-pre-1 through Phase 4b-pre-5.
- **Test plan split**: spec-PR review checks (markdown lint etc.) vs downstream implementation tests (Bats, schema validation, etc.).
- **Codex-host dispatch limitation documented**, not silenced. Operators get a clear error message and three explicit paths.

## Honest Scope Estimate

Phase 4b spec contribution PR (this design): **~1 day** of focused work on the perf-lab side (one ~600-line `orca-integration.md` plus the unified-diff replacement and tasks-list additions). v2 is meaningfully larger than v1 because the gaps surfaced by review need addressing in spec rather than in plan.

The orca-repo prerequisites (Phase 4b-pre-1 through Phase 4b-pre-5) are **~half a day** combined: the `--claude-findings-file` flag for contradiction-detector mirrors Phase 4a's cross-agent-review work; `--version` is trivial; PyPI publication is a non-coding decision; the dispatch-algorithm doc and the `build-review-prompt --kind` regression test are both small.

The downstream perf-lab v6 implementation of orca skills (T0Z03-T0Z13) is a separate project, blocks on perf-lab's T000i, and is out of scope for Phase 4b.

## Honest Value Statement

What Phase 4b uniquely delivers:

1. **Locks the integration contract** before perf-lab v6 builds its skill foundation. When T000i lands, T0Z work has a clear target that's been cross-reviewed and reconciled with existing spec.md text.
2. **Forces clarity on opt-in semantics**: "perf-lab v1 must work without orca" is a documented, probe-enforced constraint, not just a hope.
3. **Reuses Phase 4a's subagent dispatch correctly**, with the three-layer split that v1 missed.
4. **Surfaces the orca-repo work that has to ship anyway** (Phase 4b-pre-1 through Phase 4b-pre-5) — these prerequisites land independent of perf-lab v6 timing.

What Phase 4b does NOT deliver:

- Running orca-aware perf-lab. That's perf-lab v6 + T0Z block.
- New orca capabilities. The spec uses the existing 6.
- A hard guarantee that the integration contract is right. perf-lab v6 implementation may surface gaps; spec is a living document that may need a 4b-followup.
