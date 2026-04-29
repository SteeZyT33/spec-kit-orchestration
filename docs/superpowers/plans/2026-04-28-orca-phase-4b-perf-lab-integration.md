# Orca Phase 4b: Perf-Lab Integration (Spec Contribution) Implementation Plan — SUPERSEDED

> **STATUS: SUPERSEDED (2026-04-29).** This plan was written against v1 of the Phase 4b spec (`bb78733`), which was found NEEDS-REVISION by cross-pass review and rewritten as v2/v2.1. This plan's architecture (skills dispatching subagents from bash entry.sh, lease check in perf-lease worker, single combined plan) is no longer correct.
>
> Superseded by:
> - `docs/superpowers/plans/2026-04-29-orca-phase-4b-pre-prereqs.md` — orca-side prerequisites (Phase 4b-pre-1 through pre-5)
> - `docs/superpowers/plans/2026-04-29-orca-phase-4b-perf-lab-spec-pr.md` — perf-lab spec PR (gated on prereqs above)
>
> Kept in repo for historical reference and to preserve the cross-pass review trail. Do NOT execute this plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open a spec contribution PR against the perf-lab repo that adds orca-integration.md, revises spec.md's Future Integration Notes section to match Phase 4b's architecture, and adds a T0Z task block (blocked on T000i) to tasks.md. No running code; pure spec authoring.

**Architecture:** Phase 4b lives in perf-lab repo, not orca repo. Phase 4a's "orca = JSON-in JSON-out library" framing means perf-lab-specific event translation lives in perf-lab. The PR adds 3 new agent-visible skill contracts (perf-cite, perf-contradict, perf-review), 2 opt-in enforcement points (synthesis_validators, lease_overlap_check), and 3 new event types. Defaults are OFF; perf-lab v1 keeps working without orca.

**Tech Stack:** Markdown only. No code. perf-lab's existing spec/contract conventions (see `perf-lab/specs/010-self-organizing-research-runtime/contracts/skills.md`).

**Source spec:** `/home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats/docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md` (commit `bb78733`).

**Target repo:** `/home/taylor/perf-lab` (separate repo from orca).

---

## File Structure

### New files (in perf-lab repo)

- `specs/010-self-organizing-research-runtime/orca-integration.md` (~250 lines): the integration contract sibling to data-model.md/runtime-mechanics.md/etc.

### Modified files (in perf-lab repo)

- `specs/010-self-organizing-research-runtime/spec.md`: REVISE the existing "Future Integration Notes: Orca Capability Layer" section (around line 425-445) to match Phase 4b architecture. Today's prose says shim lives in orca repo and lists 4 capabilities; Phase 4b says shim lives in perf-lab repo and lists 3 new agent-visible skills + 2 opt-in enforcement points.
- `specs/010-self-organizing-research-runtime/tasks.md`: APPEND a T0Z task block (T0Z01-T0Z11) blocked on T000i.

### Why this layout

- `orca-integration.md` is a sibling spec doc, not embedded in spec.md, so the existing spec.md stays focused on the runtime architecture without growing a long integration appendix.
- spec.md gets a one-paragraph revision pointing to `orca-integration.md`. Existing Future Integration Notes content is replaced (not appended) because the architecture changed (shim in orca repo -> shim in perf-lab repo).
- tasks.md gets a clean T0Z block with all tasks blocked on T000i so the perf-lab team sees the dependency explicitly.

---

## Pre-flight Verification (before Task 1)

Two cross-repo questions must be answered before authoring the spec:

1. **Does `orca-cli contradiction-detector` accept `--claude-findings-file`?**

Run from orca worktree:
```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
uv run orca-cli contradiction-detector --help 2>&1 | grep -E "claude-findings-file|codex-findings-file" | head
```

If matches found: Phase 4a's flag was applied to contradiction-detector; spec can assume the flag works. Note this in the plan-execution log.

If NO matches: Phase 4a only wired `cross-agent-review`. The Phase 4b spec must call out that perf-contradict requires API-Claude (no in-session subagent) until orca adds the flag, OR the spec must defer perf-contradict to a follow-up task that depends on an orca PR. Document the path chosen in Task 2's spec text.

2. **Identify perf-lab's target branch for the PR.**

Run from perf-lab repo:
```bash
cd /home/taylor/perf-lab
git status -sb
git branch -a 2>&1 | grep -E "010|main"
```

The spec 010 dir lives on multiple branches in perf-lab. Identify which branch carries the AUTHORITATIVE spec 010 (the one being actively edited). At time of plan writing: `009-dotfolder-consolidation` has spec 010 as untracked files; `010-self-organizing-research-runtime` is a separate branch with older committed content. Confirm with the perf-lab maintainer (the operator) which branch is canonical before opening the PR.

If unclear, default to creating a feature branch `feature/orca-integration-spec` off whichever branch the operator confirms holds the latest spec 010.

---

## Task 1: Pre-flight verification + branch setup

**Files:** none (read-only verification)

- [ ] **Step 1: Verify contradiction-detector flag status**

Run:
```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
uv run orca-cli contradiction-detector --help 2>&1 | grep -E "claude-findings-file|codex-findings-file"
```

Record the output. If `--claude-findings-file` appears: spec assumes Phase 4b can use the flag for perf-contradict.
If `--claude-findings-file` does NOT appear: spec must include a note that perf-contradict requires an orca-side PR before it can use subagent dispatch; perf-contradict v1 falls back to API-Claude OR is deferred entirely.

- [ ] **Step 2: Identify perf-lab target branch**

Run:
```bash
cd /home/taylor/perf-lab
git status -sb
ls specs/010-self-organizing-research-runtime/ 2>&1 | head
git log --oneline -3
```

Identify which branch carries the latest spec 010. Common cases:
- Branch `009-dotfolder-consolidation` has spec 010 as untracked files -> need to commit those first OR create a feature branch off 010-self-organizing-research-runtime
- Branch `010-self-organizing-research-runtime` is up-to-date with active spec 010 -> use that as base
- Other -> stop and ask the operator

Pick the right base branch. Document it in your task report.

- [ ] **Step 3: Create feature branch**

```bash
cd /home/taylor/perf-lab
git checkout <base-branch-from-step-2>
git pull origin <base-branch-from-step-2> 2>/dev/null || true
git checkout -b feature/orca-integration-spec
```

If git pull fails because there's no remote tracking branch, that's fine for local work but flag for the operator before pushing.

- [ ] **Step 4: Confirm spec 010 dir is reachable**

Run:
```bash
ls /home/taylor/perf-lab/specs/010-self-organizing-research-runtime/
```

Expected: shows `spec.md`, `tasks.md`, `data-model.md`, `runtime-mechanics.md`, `contracts/skills.md`, etc. If missing or different than expected, stop and report.

- [ ] **Step 5: Commit nothing, just report**

Task 1 is verification-only; no commits. Report:
- Whether `--claude-findings-file` is on contradiction-detector
- Which perf-lab branch is base
- That feature branch `feature/orca-integration-spec` is created and clean

---

## Task 2: Author orca-integration.md

**Files:**
- Create: `/home/taylor/perf-lab/specs/010-self-organizing-research-runtime/orca-integration.md`

This is the primary deliverable. ~250 lines of markdown. Structure mirrors the Phase 4b design spec at `/home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats/docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md` but rewritten in perf-lab's spec voice (consistent with `data-model.md` / `runtime-mechanics.md` style).

- [ ] **Step 1: Read the perf-lab spec voice reference**

Run:
```bash
head -60 /home/taylor/perf-lab/specs/010-self-organizing-research-runtime/data-model.md
head -60 /home/taylor/perf-lab/specs/010-self-organizing-research-runtime/contracts/skills.md
```

Note the conventions: terse declarative, `**Args**:` blocks for skill contracts, `**Required**:` / `**Optional**:` / `**Side effects**:` / `**Exit codes**:` / `**Concurrency**:` keys. Match this format in Task 2's content.

- [ ] **Step 2: Write the file**

Create `/home/taylor/perf-lab/specs/010-self-organizing-research-runtime/orca-integration.md` with this content. Adjust the contradiction-detector section based on Task 1 Step 1's finding (if `--claude-findings-file` not on contradiction-detector, add the caveat block as marked).

```markdown
# Orca Integration

**Companion to**: [spec.md](./spec.md), [data-model.md](./data-model.md), [contracts/skills.md](./contracts/skills.md)
**Status**: Spec contribution. Implementation tasks (T0Z block in [tasks.md](./tasks.md)) blocked on T000i (skill foundation).
**Source**: Phase 4b of orca v1 (see orca repo `docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md`).

## Purpose

Orca is a JSON-in JSON-out capability library at `orca-cli` (see orca repo `plugins/codex/AGENTS.md`). When operators opt in via `claim_config.orca_policy`, perf-lab skills can wrap orca capabilities to validate synthesis content (`perf-cite`, `perf-contradict`) and review artifacts (`perf-review`). Three opt-in enforcement points let operators bake validation into the synthesis or lease commit path on a per-claim basis.

The integration is opt-in. perf-lab v1 must continue to operate without orca: the three skills are agent-visible tools the agent invokes when their claim says to; the enforcement points are gated on `claim_config.orca_policy` and default off.

## Skill Contracts

All skills follow the conventions in [contracts/skills.md](./contracts/skills.md): live at `/opt/perf-lab/skills/<name>/entry.sh`, called by absolute path, read `CLAIM_ID` and `SHARED_ROOT` from env, emit events via `perf-event`, use `flock` for shared writes, exit 0 on success.

### perf-cite

Wraps `orca-cli citation-validator`. Validates citation hygiene in synthesis text.

**Args**:
```
perf-cite --content-path <path> [--reference-set <path>]... [--mode strict|lenient]
```

**Required**: `--content-path` (markdown file inside `/shared/`).

**Optional**: `--reference-set` (repeatable; defaults auto-discover from claim's feature dir: `plan.md`, `data-model.md`, `research.md`, `quickstart.md`, `tasks.md`, `contracts/**/*.md`). `--mode strict|lenient` (default `strict`).

**Side effects**: appends one `synthesis_validated` event to `/shared/events.jsonl` via `perf-event`. Payload: `{capability: "citation-validator", version, duration_ms, coverage, uncited_count, broken_refs_count, threshold}`. Optionally writes a finding report to `/shared/orca/<claim_id>/cite-report.md` if `--write` (matches orca's `cite.md` slash command convention).

**Exit codes**:
- `0`: validation succeeded; coverage >= threshold
- `1`: validation failed (uncited claims, broken refs, or coverage below threshold); stderr lists offenders
- `2`: orca-cli not available; check Dockerfile install or `ORCA_PROJECT`
- `3`: invalid args

**Concurrency**: `flock /shared/locks/cite.lock` only when writing reports.

### perf-contradict

Wraps `orca-cli contradiction-detector`. Validates new synthesis content against prior evidence to flag contradictions. Uses subagent dispatch for the LLM portion (Phase 4a pattern).

**Args**:
```
perf-contradict --content-path <path> --evidence-path <path>
```

**Required**: `--content-path` (the new synthesis content). `--evidence-path` (prior evidence file or directory).

**Side effects**: emits `contradiction_detected` event with payload `{capability: "contradiction-detector", version, duration_ms, contradiction_count, contradictions[]}`.

**Behavior**:
1. Build review prompt: `ORCA_PROMPT=$(orca-cli build-review-prompt --kind contradiction --criteria contradicts-evidence --criteria contradicts-prior-synthesis)`. The `--kind contradiction` arg is forward-compat; v1's build-review-prompt accepts any `--kind` without branching.
2. Dispatch a `Code Reviewer` subagent via the host's Agent tool (Claude Code or Codex). The host inside the devcontainer is whichever harness is running (env `HARNESS`).
3. Subagent input: `$ORCA_PROMPT` + content of `--content-path` + content of `--evidence-path`.
4. Capture subagent response; pipe through `orca-cli parse-subagent-response` to write findings to `/shared/orca/<claim_id>/contradict-findings.json`.
5. Call `orca-cli contradiction-detector --claude-findings-file <path> --content-path <path> --evidence-path <path>`. (See "Open question" below if `--claude-findings-file` is not yet supported on contradiction-detector.)
6. Parse JSON envelope; emit `contradiction_detected` event.

**Exit codes**:
- `0`: zero contradictions found
- `1`: contradictions found OR validation error (caller decides whether to escalate to `feedback_needed`)
- `2`: orca-cli not available
- `3`: invalid args

**Concurrency**: `flock /shared/locks/contradict.lock` for shared writes.

**Open question** (delete this block if Task 1 Step 1 confirmed the flag exists): if orca-cli's `contradiction-detector` does not yet accept `--claude-findings-file`, perf-contradict v1 either falls back to SDK-only (requires `ANTHROPIC_API_KEY` in container) OR is deferred behind an orca PR adding the flag. Tracking task: T0Z02b (file orca PR) blocks T0Z04 (perf-contradict skill). See orca's Phase 4a spec for the established pattern.

### perf-review

Wraps `orca-cli cross-agent-review` with subagent dispatch. Runs cross-agent review against an artifact (research paper draft, theory doc, implementation diff).

**Args**:
```
perf-review --kind {spec,diff,pr,artifact} --target <path> [--criteria <c>]... [--feature-id <id>]
```

**Required**: `--kind` (one of: spec, diff, pr, artifact). `--target` (path to subject inside `/shared/`).

**Optional**: `--criteria` (repeatable). `--feature-id` (defaults to claim's feature ID).

**Side effects**: emits `quality_gate` event with payload `{capability: "cross-agent-review", version, duration_ms, kind, finding_count, severity_breakdown: {blocker, high, medium, low, nit}}`.

**Behavior**:
1. Build review prompt via `orca-cli build-review-prompt`.
2. Dispatch subagent reviewer (Phase 4a pattern).
3. Pipe response through `parse-subagent-response`; write to `/shared/orca/<claim_id>/review-findings.json`.
4. Call `orca-cli cross-agent-review --claude-findings-file <path> --kind ... --target ... [--criteria ...]`.
5. Parse envelope; emit `quality_gate` event.

**Exit codes**:
- `0` always (review is informational; agent reads findings and decides next action)
- `2` if orca-cli not available
- `3` if invalid args

**Concurrency**: `flock /shared/locks/review.lock` for shared writes.

## New Event Types (extends FR-008)

Three new event types added to `perf-event`'s canonical FR-008 list:

| Type | Required payload fields | Notes |
|------|-------------------------|-------|
| `synthesis_validated` | `capability`, `version`, `duration_ms`, `coverage`, `uncited_count`, `broken_refs_count`, `threshold` | Emitted by `perf-cite`. Optional emit by `perf-synthesis` when `orca_policy.synthesis_validators` includes `"cite"`. |
| `contradiction_detected` | `capability`, `version`, `duration_ms`, `contradiction_count`, `contradictions[]` | Emitted by `perf-contradict`. Optional emit by `perf-synthesis` when `orca_policy.synthesis_validators` includes `"contradict"`. |
| `quality_gate` | `capability`, `version`, `duration_ms`, `kind`, `finding_count`, `severity_breakdown` | Emitted by `perf-review`. Always informational (perf-review exits 0). |

Each event also carries the standard perf-event fields (`event_id`, `timestamp`, `harness`, `image_digest`, `claim_id`).

## Claim Config Additions

Per-claim config (`/shared/claims/<id>/config.json`) gains an optional `orca_policy` block. All fields optional; defaults disable orca entirely.

```json
{
  "claim_id": "abc123",
  "mode": "implement",
  "orca_policy": {
    "synthesis_validators": ["cite", "contradict"],
    "lease_overlap_check": "orca",
    "review_required_kind": "diff",
    "cite_threshold": 1.0,
    "cite_reference_set": ["plan.md", "research.md"]
  }
}
```

**Field semantics**:

- `synthesis_validators` (list of `"cite" | "contradict"`): if non-empty, `perf-synthesis` invokes the named validators after building synthesis content but before committing the lease. Validator failure aborts the synthesis commit; agent gets a `feedback_needed` event.
- `lease_overlap_check` (string `"orca"` or absent): if `"orca"`, `perf-lease` calls `orca-cli worktree-overlap-check` before granting any lease whose paths overlap an active lease. orca's pure-Python check is more thorough than perf-lease's built-in overlap detection.
- `review_required_kind` (string `"spec" | "diff" | "pr" | "artifact"` or absent): if set, perf-synthesis or perf-artifact commit flows require a successful `perf-review` event for this claim before allowing commit.
- `cite_threshold` (float in `[0.0, 1.0]`, default 1.0): `perf-cite` exits non-zero if coverage falls below.
- `cite_reference_set` (list of paths relative to claim's feature dir): if unset, `perf-cite` auto-discovers per orca's Phase 3.2 conventions.

Defaults: all unset. perf-lab v1 operates without orca exactly as it does without Phase 4b shipped.

## Devcontainer Installation

`.devcontainer/Dockerfile` (T000b) needs orca-cli at runtime:

```dockerfile
# orca capability library (Phase 4b integration; opt-in via claim_config.orca_policy)
RUN pip install --no-cache-dir uv && \
    uv tool install spec-kit-orca==<version-pin>
```

Where `<version-pin>` is the orca git tag at perf-lab v6 release time. Pinning forces explicit Dockerfile bumps for orca upgrades.

Alternative for development: `ENV ORCA_PROJECT=/opt/orca` plus a bind mount of the orca source tree. Lets perf-lab developers iterate on orca without rebuilding the image. Document both paths in T000b.

## Failure Modes

| Scenario | Skill behavior |
|----------|----------------|
| orca-cli not in PATH and `ORCA_PROJECT` unset | Skill exits 2 with stderr `"orca-cli not found; check Dockerfile install or set ORCA_PROJECT"` |
| orca capability returns `Err(INPUT_INVALID)` | Skill emits its event with `payload.error = {kind, message}`; exits 1 |
| orca capability returns `Err(BACKEND_FAILURE)` | Skill emits its event with `payload.error`; exits 1 with stderr surfaced from orca |
| Subagent dispatch unavailable (host lacks Agent tool, e.g., pi.sh) | `parse-subagent-response` returns INPUT_INVALID; skill exits 1 with `"in-session reviewer unavailable on this host"` |
| `--content-path` outside `/shared/` | Skill exits 1 (security: prevent reading outside the runtime sandbox) |
| Skill invoked outside an active claim (`CLAIM_ID` unset) | Skill exits 1 with `"missing CLAIM_ID; orca skills run only inside a claim"` |
| orca version below perf-lab's required minimum | Skill exits 2 with `"orca-cli version X.Y.Z below required A.B.C; bump devcontainer image"` |

## Out of Scope

- Implementing the perf-lab skills (waits on T000i, perf-event foundation)
- New orca capabilities (uses existing 6)
- flow-state-projection integration (perf-lab has its own scheduler; orca's projection is for SDD)
- completion-gate integration (SDD-specific stage gates don't apply to perf-lab's claim/round model)
- Automatic enforcement (per design: opt-in via claim config only; no global default-on)

## Test Plan

Following perf-lab spec 010's test conventions:

- **Skill smoke tests**: `tests/skills/test_perf_cite.bats`, `test_perf_contradict.bats`, `test_perf_review.bats`. Use Bats. Stub `orca-cli` with a fake script returning canned envelopes.
- **Event schema validation**: extend `tests/events/test_event_schema.py` (or equivalent) to validate the three new event types' payloads.
- **Integration tests**: `tests/integration/test_orca_synthesis_gate.bats` (synthesis_validators policy), `test_orca_lease_overlap.bats` (lease_overlap_check policy). Mark as integration; require orca-cli in test environment.
- **Claim config validator**: existing perf-lab claim-config validator extended to recognize the `orca_policy` block.

## References

- orca v1 north star: `<orca-repo>/docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md`
- orca Phase 4a (in-session reviewer, dependency unlock): `<orca-repo>/docs/superpowers/specs/2026-04-28-orca-phase-4a-in-session-reviewer-design.md`
- orca Phase 4b design: `<orca-repo>/docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md`
- orca AGENTS.md (codex-facing capability docs): `<orca-repo>/plugins/codex/AGENTS.md`
- perf-lab skill conventions: [contracts/skills.md](./contracts/skills.md)
- perf-lab event taxonomy (FR-008): [spec.md](./spec.md)
```

(Replace `<orca-repo>` references with the resolved orca repo URL or path before opening the PR; match perf-lab's existing cross-repo reference style.)

- [ ] **Step 3: Em-dash check**

Run:
```bash
grep -nE "—" /home/taylor/perf-lab/specs/010-self-organizing-research-runtime/orca-integration.md
```
Expected: 0 matches. If any, replace with ` - `.

- [ ] **Step 4: Verify file is well-formed markdown**

Run:
```bash
wc -l /home/taylor/perf-lab/specs/010-self-organizing-research-runtime/orca-integration.md
head -40 /home/taylor/perf-lab/specs/010-self-organizing-research-runtime/orca-integration.md
```
Expected: ~200-280 lines, frontmatter visible, sections present.

- [ ] **Step 5: Commit**

```bash
cd /home/taylor/perf-lab
git add specs/010-self-organizing-research-runtime/orca-integration.md
git commit -m "docs(orca): add orca-integration.md spec contribution"
```

If commitlint fails, shorten while preserving intent.

---

## Task 3: Revise spec.md Future Integration Notes

**Files:**
- Modify: `/home/taylor/perf-lab/specs/010-self-organizing-research-runtime/spec.md` (around lines 425-445)

The existing section reflects the OLD v1 north-star design (shim in orca repo, 4 capabilities mapped to runtime). Phase 4b changes:
- Shim moves to perf-lab repo
- 3 new agent-visible skills (perf-cite, perf-contradict, perf-review)
- 2 opt-in enforcement points (synthesis_validators, lease_overlap_check)
- claim_config.orca_policy block
- completion-gate dropped (SDD-specific)
- flow-state-projection dropped (SDD-specific)
- Reference to new sibling file `orca-integration.md`

- [ ] **Step 1: Read the current section to find exact boundaries**

```bash
sed -n '420,450p' /home/taylor/perf-lab/specs/010-self-organizing-research-runtime/spec.md
```

Identify where the section starts (likely a heading like `### Future Integration Notes: Orca Capability Layer` or similar) and where it ends (next major heading or end of file).

- [ ] **Step 2: Replace the section**

Find the exact text starting from the section heading through the last paragraph of the section. REPLACE with this new content (preserve the same heading style; if the existing is `###`, use `###`; if `##`, use `##`):

```markdown
### Future Integration Notes: Orca Capability Layer

The orca capability library (`orca-cli`) is a JSON-in JSON-out toolchest of pure-Python and LLM-backed capabilities. When operators opt in per-claim via `claim_config.orca_policy`, perf-lab skills can wrap orca capabilities to validate synthesis content and review artifacts. The integration is opt-in: perf-lab v1 operates without orca, and `orca_policy` defaults to disabling all orca-driven behavior.

Three new agent-visible skills wrap orca capabilities:
- `perf-cite` wraps `orca-cli citation-validator` (citation hygiene in synthesis text)
- `perf-contradict` wraps `orca-cli contradiction-detector` (subagent dispatch via Phase 4a pattern; flags contradictions between new synthesis and prior evidence)
- `perf-review` wraps `orca-cli cross-agent-review` (subagent-driven cross-pass review of artifacts)

Two opt-in enforcement points (defaults OFF):
- `perf-synthesis` commit flow can call `perf-cite` and `perf-contradict` as gates if claim config sets `orca_policy.synthesis_validators`
- `perf-lease` grant flow can call `orca-cli worktree-overlap-check` if claim config sets `orca_policy.lease_overlap_check: "orca"`

orca capabilities not used by perf-lab's runtime: `completion-gate` (SDD R-P-I stage gates) and `flow-state-projection` (SDD feature projection). These remain available for perf-lab's meta-development (perf-lab as an SDD-managed project) but are not invoked from runtime hot paths.

#### New event types introduced when orca integration is enabled

When the orca integration ships (post-v1), the FR-008 canonical event taxonomy MUST extend with:

- `synthesis_validated`: emitted after `perf-cite` runs. Payload includes `capability`, `version`, `duration_ms`, `coverage`, `uncited_count`, `broken_refs_count`, `threshold`.
- `contradiction_detected`: emitted by `perf-contradict` when new synthesis or theory conflicts with raw evidence. Payload includes `capability`, `version`, `duration_ms`, `contradiction_count`, `contradictions[]`.
- `quality_gate`: emitted by `perf-review` on completion. Payload includes `capability`, `version`, `duration_ms`, `kind`, `finding_count`, `severity_breakdown`.

Adding these event types follows FR-008's amendment process: extend the canonical list and add corresponding schema entries before the integration is enabled.

#### Shim location and ownership

Phase 4b's revised architecture (replacing the v1 north star's `orca/integrations/perf_lab/` location) places the integration shim in this repo, not in the orca repo. The orca repo stays a generic JSON-in JSON-out capability library; perf-lab owns its own runtime wire format. Each perf-lab skill shells to `orca-cli`, parses the JSON envelope, and emits events via `perf-event`. Orca outputs are captured under `/shared/orca/<claim_id>/` as referenced artifacts; only the translated perf-event is canonical.

See [orca-integration.md](./orca-integration.md) for the full skill contracts, claim config schema, devcontainer installation, failure modes, and test plan.
```

- [ ] **Step 3: Verify the section was replaced cleanly**

```bash
grep -n "Future Integration Notes" /home/taylor/perf-lab/specs/010-self-organizing-research-runtime/spec.md
sed -n '420,470p' /home/taylor/perf-lab/specs/010-self-organizing-research-runtime/spec.md
```
Expected: section starts at the same line range, contains the new content, ends with a link to `orca-integration.md`.

- [ ] **Step 4: Em-dash check**

```bash
grep -nE "—" /home/taylor/perf-lab/specs/010-self-organizing-research-runtime/spec.md | head -5
```

If any em-dashes appear in the new content I just wrote (NOT pre-existing ones in untouched sections), replace with ` - `. Pre-existing em-dashes in untouched sections are out of scope.

- [ ] **Step 5: Commit**

```bash
cd /home/taylor/perf-lab
git add specs/010-self-organizing-research-runtime/spec.md
git commit -m "docs(orca): revise Future Integration Notes for Phase 4b"
```

---

## Task 4: Append T0Z task block to tasks.md

**Files:**
- Modify: `/home/taylor/perf-lab/specs/010-self-organizing-research-runtime/tasks.md` (append at end)

- [ ] **Step 1: Find current tasks.md tail**

```bash
tail -20 /home/taylor/perf-lab/specs/010-self-organizing-research-runtime/tasks.md
```

Identify what's at the end. The new T0Z block appends after existing tasks without disturbing them.

- [ ] **Step 2: Append the T0Z block**

Append this content to `/home/taylor/perf-lab/specs/010-self-organizing-research-runtime/tasks.md`:

```markdown

## T0Z: Orca Integration (blocked on T000i)

All T0Z tasks are blocked on T000i (skill foundation: `perf-event`, `perf-claim`, `perf-lease`, etc.). Once T000i lands, T0Z can proceed. See [orca-integration.md](./orca-integration.md) for full contracts.

- [ ] T0Z01 Cross-repo verification: confirm orca-cli at the pinned version supports `--claude-findings-file` on `cross-agent-review` (Phase 4a) AND on `contradiction-detector`. If contradiction-detector lacks the flag, file an orca PR adding it before T0Z04 proceeds. Document the orca version pin used.

- [ ] T0Z02 Add `synthesis_validated`, `contradiction_detected`, `quality_gate` event types to `perf-event`'s FR-008 canonical event-type validation list. Update schema entries per [orca-integration.md](./orca-integration.md) "New Event Types" table.

- [ ] T0Z03 Implement `perf-cite` skill: `entry.sh` + `SKILL.md` + Bats tests under `tests/skills/test_perf_cite.bats`. Wraps `orca-cli citation-validator`. See contract in [orca-integration.md](./orca-integration.md).

- [ ] T0Z04 Implement `perf-contradict` skill: `entry.sh` + `SKILL.md` + Bats tests under `tests/skills/test_perf_contradict.bats`. Wraps `orca-cli contradiction-detector` with subagent dispatch via the host harness (Claude Code or Codex). Blocks on T0Z01 confirmation.

- [ ] T0Z05 Implement `perf-review` skill: `entry.sh` + `SKILL.md` + Bats tests under `tests/skills/test_perf_review.bats`. Wraps `orca-cli cross-agent-review` with subagent dispatch.

- [ ] T0Z06 Extend claim-config schema (`/shared/claims/<id>/config.json`) for the `orca_policy` block. Add validator + tests. See "Claim Config Additions" in [orca-integration.md](./orca-integration.md).

- [ ] T0Z07 Wire `synthesis_validators` policy into `perf-synthesis` commit flow. When `orca_policy.synthesis_validators` is non-empty, invoke the named validators (`perf-cite`, `perf-contradict`) before committing the lease. Validator failure aborts commit and emits `feedback_needed`.

- [ ] T0Z08 Wire `lease_overlap_check` policy into `perf-lease` grant flow. When `orca_policy.lease_overlap_check == "orca"`, call `orca-cli worktree-overlap-check` before granting any lease whose paths overlap an active lease.

- [ ] T0Z09 Wire `review_required_kind` policy into commit flows (perf-synthesis, perf-artifact). When set, require a successful `perf-review` event for the claim before allowing commit.

- [ ] T0Z10 Add orca-cli install to `.devcontainer/Dockerfile` (T000b). Pin the orca version. Document the alternative `ORCA_PROJECT` bind-mount path for development. See "Devcontainer Installation" in [orca-integration.md](./orca-integration.md).

- [ ] T0Z11 Author `docs/runtime/orca-policy.md` operator guide. Cover: when to enable each policy, expected event volume impact, how to debug a policy that's blocking commits, how to disable per-claim or per-mission. Cross-link from [orca-integration.md](./orca-integration.md).

- [ ] T0Z12 Integration smoke tests: `tests/integration/test_orca_synthesis_gate.bats` (synthesis_validators end-to-end), `test_orca_lease_overlap.bats` (lease overlap check end-to-end), `test_orca_review_required.bats` (review-required gate). Mark as integration; require `orca-cli` in test environment.
```

- [ ] **Step 3: Em-dash check**

```bash
grep -nE "—" /home/taylor/perf-lab/specs/010-self-organizing-research-runtime/tasks.md | head
```

Replace any new em-dashes I just authored with ` - `.

- [ ] **Step 4: Commit**

```bash
cd /home/taylor/perf-lab
git add specs/010-self-organizing-research-runtime/tasks.md
git commit -m "docs(orca): add T0Z task block (blocked on T000i)"
```

---

## Task 5: Spec self-review + push + open PR

**Files:** none (verification + push)

- [ ] **Step 1: Self-review the three commits**

Run:
```bash
cd /home/taylor/perf-lab
git log --oneline feature/orca-integration-spec ^<base-branch> | head
git diff <base-branch>..feature/orca-integration-spec --stat
```

Verify:
- 3 commits (Tasks 2, 3, 4)
- 3 files modified: orca-integration.md (new), spec.md (modified), tasks.md (modified)
- No accidental edits to other files

- [ ] **Step 2: Cross-reference check**

Verify all internal links work:
```bash
cd /home/taylor/perf-lab
grep -nE "\[.*\]\(\./" specs/010-self-organizing-research-runtime/orca-integration.md
grep -n "orca-integration.md" specs/010-self-organizing-research-runtime/spec.md
grep -n "orca-integration.md" specs/010-self-organizing-research-runtime/tasks.md
```

Expected: orca-integration.md links to spec.md, contracts/skills.md, data-model.md, tasks.md (all relative). spec.md and tasks.md both link to ./orca-integration.md.

- [ ] **Step 3: Final em-dash sweep**

```bash
cd /home/taylor/perf-lab
git diff <base-branch>..feature/orca-integration-spec | grep -E "^\+.*—" | head
```

Expected: 0 matches in diff additions. Pre-existing em-dashes in untouched lines are OK.

- [ ] **Step 4: Push the branch**

```bash
cd /home/taylor/perf-lab
git push -u origin feature/orca-integration-spec
```

If push fails because the remote doesn't exist or auth issues, stop and report.

- [ ] **Step 5: Open PR**

```bash
cd /home/taylor/perf-lab
gh pr create \
  --base <base-branch-from-task-1> \
  --head feature/orca-integration-spec \
  --title "docs(orca): phase 4b integration spec contribution" \
  --body "$(cat <<'EOF'
## Summary

Phase 4b spec contribution from orca v1. Adds the contract for opt-in orca capability integration into perf-lab v6's skill model.

### Changes

- **NEW** `specs/010-self-organizing-research-runtime/orca-integration.md` (~250 lines): full skill contracts, event types, claim config schema, devcontainer notes, failure modes, test plan
- **REVISED** `specs/010-self-organizing-research-runtime/spec.md` "Future Integration Notes" section: replaces v1 north-star's shim-in-orca-repo design with Phase 4b's perf-lab-side integration
- **APPENDED** `specs/010-self-organizing-research-runtime/tasks.md`: T0Z block (T0Z01-T0Z12), all blocked on T000i (skill foundation)

### Why this PR is spec-only

perf-lab v6 is mid-build (T000a-T000j unfinished). Skills foundation (T000i) hasn't shipped yet. The orca skill code can't run until `perf-event` exists. This PR locks the integration contract NOW so that when T000i lands, T0Z work has a clear target.

### Architecture

- 3 new agent-visible skills: `perf-cite`, `perf-contradict`, `perf-review`
- 2 opt-in enforcement points: `synthesis_validators`, `lease_overlap_check`
- 3 new event types: `synthesis_validated`, `contradiction_detected`, `quality_gate`
- Defaults OFF: perf-lab v1 keeps working without orca
- Phase 4a's subagent dispatch pattern (file-backed reviewer, no API key) is what makes this integration possible inside the devcontainer

### Cross-repo dependency

Verified at PR creation: orca-cli's `cross-agent-review` supports `--claude-findings-file` (Phase 4a). Whether `contradiction-detector` supports it is tracked as T0Z01; if not, T0Z04 (perf-contradict) is gated on a separate orca PR.

### Source

Phase 4b design spec in orca repo: `docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md`

### Test plan

- [x] Markdown well-formed (manual review)
- [x] Internal links resolve (spec.md, contracts/skills.md, data-model.md, tasks.md, orca-integration.md cross-references)
- [x] No em-dashes in new content (project rule)
- [x] Existing tasks.md content untouched (only T0Z block appended)
- [x] Existing spec.md sections untouched outside the Future Integration Notes block
EOF
)"
```

- [ ] **Step 6: Report PR URL**

Capture the PR URL from the gh output. Report it to the controller.

---

## Self-Review Checklist

Run before declaring DONE:

1. **Spec coverage**:
   - [x] Three skill contracts (perf-cite, perf-contradict, perf-review) - Task 2
   - [x] Three new event types - Task 2 + Task 3
   - [x] orca_policy claim config block - Task 2 + Task 3
   - [x] Devcontainer installation note - Task 2
   - [x] Failure modes table - Task 2
   - [x] Test plan - Task 2
   - [x] Out-of-scope items - Task 2
   - [x] References cross-linked - Task 2 + Task 3 + Task 4
   - [x] T0Z task block - Task 4
   - [x] Future Integration Notes revised in spec.md - Task 3

2. **No placeholders**: every step contains the actual content. No `<feature-id>`-style placeholders that the engineer has to invent. (The plan contains literal `<base-branch-from-task-1>` placeholders intentionally - those are inputs the engineer fills in based on Task 1's output.)

3. **Type consistency**: `perf-cite`/`perf-contradict`/`perf-review` skill names consistent across all four tasks. Event types `synthesis_validated`/`contradiction_detected`/`quality_gate` consistent. `orca_policy.synthesis_validators` field name consistent across spec.md and orca-integration.md. T0Z task IDs (T0Z01-T0Z12) consistent.

4. **Cross-repo gotchas**: explicit Pre-flight verification (Task 1) catches the contradiction-detector flag question before authoring the spec content. T0Z01 is the runtime's cross-repo guard.

---

## Honest Risk Notes

- **Branch identification (Task 1 Step 2)** is the highest-uncertainty step. perf-lab has multiple branches with spec 010 in different states. The plan mitigates by requiring explicit branch confirmation; if the branch is wrong, opening a PR against the wrong base is recoverable but wastes a cycle.
- **Em-dash discipline** in markdown: easy to introduce accidentally via copy-paste from the design spec. Each task has an em-dash check step, but reviewer should verify on PR.
- **Internal link resolution** is the next-highest risk: if any link path is wrong, the rendered docs are broken. Task 5 Step 2 verifies this manually.
- **PR base branch in gh pr create**: if the operator picks the wrong base, the PR shows a huge unrelated diff. Task 5 Step 5 uses the value identified in Task 1; mistakes there compound here.
- **No code, no tests**: Phase 4b ships docs only. There's no runtime validation that the spec's contracts actually work. perf-lab v6 implementation (T0Z block) is where contracts get exercised; gaps surface at that point. This is acknowledged scope.
