# Orca Phase 3: Plugin Formats + SDD Opinion-Layer Slash Commands

**Date:** 2026-04-27
**Status:** Design (post-brainstorm, pre-implementation-plan)
**Predecessors:**
- `docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md` (v1 north star)
- `docs/superpowers/plans/2026-04-26-orca-phase-1-rename-and-strip.md` (Phase 1)
- `docs/superpowers/plans/2026-04-27-orca-phase-2-capability-cores-and-cli.md` (Phase 2)

## Context

Phase 2 shipped six v1 capabilities (`cross-agent-review`, `worktree-overlap-check`, `flow-state-projection`, `completion-gate`, `citation-validator`, `contradiction-detector`) as a Python library and `orca-cli` subcommand surface. Phase 3 wires those capabilities into the personal SDD opinion layer (Claude Code slash commands) and exposes a Codex surface so a second agent can invoke them.

Phase 1 already shipped 5 markdown slash commands (`brainstorm`, `review-spec`, `review-code`, `review-pr`, `tui`) and a SKILL.md generator (`orca-main.sh:generate_extension_skills`). These commands are currently markdown prompts that *describe* the workflow but do not invoke `orca-cli`. Phase 3 closes that loop.

Per jcode review (`docs/ecosystem-integration-review-2026-04-27-jcode.md`): Orca remains pull-not-push. Slash commands and Codex fragments are two ways for a host to *pull* the capability layer. Neither becomes a control plane or runtime.

## Design Constraints

1. **Existing slash commands keep their opinionated artifact shape.** `review-spec.md`, `review-code.md`, `review-pr.md` artifacts already have a documented append-only format with handoff routing, retro notes, and tier mapping. Phase 3 wires the capability layer behind those slash commands; it does NOT redesign the artifact shape.
2. **Translation, not replacement.** The slash command produces `review-X.md` markdown; the orca-cli call provides the FINDINGS that go into that markdown. A small `cli_output` helper translates between the two.
3. **Codex surface is a pointer, not a port.** `plugins/codex/AGENTS.md` documents `orca-cli` invocation; per-capability prompt files would duplicate `docs/capabilities/*/README.md`. Codex reads docs.
4. **Generated SKILL.md stays generated.** The Phase 1 `generate_extension_skills` bash function already wraps slash command markdown into SKILL.md; new commands are picked up automatically.
5. **No bash convenience launchers.** Two CLI surfaces (Python + bash wrappers) is duplication for hypothetical hosts. Defer.

## v1 Slash Command Catalog (Phase 3)

Five slash commands, three rewired and two new:

### Rewired: `/orca:review-spec`, `/orca:review-code`, `/orca:review-pr`

Each shells to `orca-cli cross-agent-review --kind {spec,diff,pr}` and pipes the JSON envelope through `cli_output` to produce the existing markdown artifact (`review-spec.md`, `review-code.md`, `review-pr.md`). Existing markdown structure (sections, append-only round headers, handoff blocks, tier maps) is preserved.

The slash command markdown documents:
- Which `orca-cli` subcommand to invoke
- Required env: `ORCA_LIVE=1` (or fixture overrides for dry-run)
- How to translate the JSON envelope into the artifact's section shape
- What to do on `Err(...)` — the artifact still gets a `Round N` header noting the failure with `result.error.kind` and `detail.underlying`

The slash command does NOT:
- Re-implement the JSON contract (that's `cli_output`'s job)
- Bypass the capability layer (no direct claude/codex SDK calls in the slash command)
- Make decisions about gate behavior (the operator reads findings and decides)

### New: `/orca:gate <stage>`

Shells to `orca-cli completion-gate --feature-dir <auto-detected> --target-stage <stage>` and emits a human-readable summary. Optionally evidence-aware via `--evidence-json` (CI green status, stale artifacts).

Output goes to stdout (operator-facing) and optionally appended to a `gate-history.md` artifact under the feature dir if `--persist` is passed.

`<stage>` enum mirrors the capability: `plan-ready`, `implement-ready`, `pr-ready`, `merge-ready`.

### New: `/orca:cite <synthesis-path>`

Shells to `orca-cli citation-validator --content-path <path> --reference-set <auto-detected refs>` and emits a markdown summary of uncited claims, broken refs, and well-supported claims. Reference set defaults to `events.jsonl`, `experiments.tsv`, and `specs/<feature>/research.md` if present.

Output to stdout; optionally `--write` appends to a `cite-report.md` artifact.

### Skipped capabilities (no slash command)

- **`contradiction-detector`**: research-loop primary. perf-lab integration shim invokes this; personal SDD doesn't. If demand emerges, easy to add later.
- **`worktree-overlap-check`**: host machinery. perf-lab's `lease.sh` calls this; not a slash command shape.
- **`flow-state-projection`**: feeds the existing `/orca:tui`; no separate slash command.

## Output Adapter (`src/orca/cli_output.py`)

A small Python module with one public function per artifact type:

```python
def render_review_spec_markdown(envelope: dict, *, round_num: int, feature_id: str) -> str: ...
def render_review_code_markdown(envelope: dict, *, round_num: int, feature_id: str) -> str: ...
def render_review_pr_markdown(envelope: dict, *, round_num: int, feature_id: str) -> str: ...
def render_completion_gate_markdown(envelope: dict, *, target_stage: str) -> str: ...
def render_citation_markdown(envelope: dict, *, content_path: str) -> str: ...
```

Each function takes the full Result envelope (success or failure) and returns the markdown the slash command appends to the artifact. Failure envelopes produce a `### Round N — FAILED (kind=BACKEND_FAILURE, underlying=timeout)` block; success envelopes produce the established section shape per artifact convention.

The slash command uses `orca-cli ... --json` to get the envelope, pipes it through `python -m orca.cli_output render-{type} --feature-id ... --round N`, and the resulting markdown is what gets appended to the on-disk artifact.

This keeps the slash command markdown FREE of JSON parsing logic. Slash commands describe the high-level flow; `cli_output` does the rendering.

## Codex Surface (`plugins/codex/AGENTS.md`)

A single instruction fragment that codex's session loader picks up. Contents:

- One-paragraph framing: "Orca exposes a JSON-in JSON-out capability library at `orca-cli`."
- Subcommand list with one-liner descriptions and a pointer to `docs/capabilities/<name>/README.md` for each.
- The standard envelope shape (`{ok, result|error, metadata}`) with exit code mapping (0/1/2/3).
- The fixture override convention (`ORCA_FIXTURE_REVIEWER_*` env vars for dry-run testing).
- The `ORCA_LIVE=1` requirement for live LLM-backed capability calls.
- A short "what Orca is NOT" block (mirrors the README positioning per jcode).

No per-capability prompt files. Codex reads `docs/capabilities/*/README.md` directly when invoked against a capability.

## File Structure

```
plugins/
├── claude-code/
│   └── commands/
│       ├── brainstorm.md           # unchanged (no capability behind it)
│       ├── review-spec.md          # REWIRED to orca-cli
│       ├── review-code.md          # REWIRED to orca-cli
│       ├── review-pr.md            # REWIRED to orca-cli
│       ├── tui.md                  # unchanged
│       ├── gate.md                 # NEW
│       └── cite.md                 # NEW
└── codex/
    └── AGENTS.md                   # NEW

src/orca/
└── cli_output.py                   # NEW — markdown rendering helpers

extension.yml                       # MODIFIED — register gate + cite commands
```

## Testing Strategy

- **`cli_output` rendering** is unit-testable: feed canonical envelope shapes per capability, snapshot the markdown output. ~12-15 tests covering success / partial / error envelopes per renderer.
- **Slash command rewiring** is integration-tested via shell scripts that:
  1. Set up a tiny fixture feature dir
  2. Set `ORCA_FIXTURE_REVIEWER_*` env vars to deterministic JSON
  3. Run the slash command equivalent (the bash invocation pattern the markdown documents)
  4. Assert the resulting markdown artifact matches expected shape
- **Codex `AGENTS.md`** is verified by parsing it as markdown + checking the subcommand list matches `orca-cli --list` output. No live codex invocation required for tests.

## Error Handling

- Slash commands handle `orca-cli` non-zero exits by appending a failure block to the artifact (still produces an artifact, doesn't silently fail).
- `cli_output` renderers accept any envelope shape; failure envelopes produce labeled failure blocks.
- Slash command markdown documents what to do on each ErrorKind:
  - `INPUT_INVALID`: operator typo; report and stop without artifact append
  - `BACKEND_FAILURE`: write a "Round N — backend failed" block; operator decides whether to retry
  - `INTERNAL`: write the same as BACKEND_FAILURE plus the `detail.underlying` for filing a bug

## Repo Migration

- Existing `review-spec.md`, `review-code.md`, `review-pr.md` slash command files keep their position and most of their content. The "what to invoke" section gets rewritten to use `orca-cli`. The artifact-shape section is preserved.
- `extension.yml` `provides.commands` array gets two new entries.
- `generate_extension_skills` is unchanged — picks up new files automatically.

## v1 Scope (Phase 3)

In v1:

- 3 rewired slash commands invoking `orca-cli cross-agent-review`
- 2 new slash commands (`gate`, `cite`)
- `cli_output` helpers for the 5 artifact shapes
- Codex `AGENTS.md` pointer doc
- `extension.yml` updated with the new commands
- Test coverage per testing strategy above

Out of scope for Phase 3:

- Per-host integration shims (perf-lab — Phase 4)
- Bash convenience launchers (defer)
- MCP server wrapper (deferred from v1)
- `contradiction-detector` slash command (no demand yet)
- `worktree-overlap-check` slash command (host machinery, not personal SDD)
- TUI changes
- Live LLM nightly runs (Phase 5)

## Honest Scope Estimate

~1 week of focused work. Smaller than Phase 2 because most plumbing exists:

- Slash command rewiring is ~30 lines of markdown change per file
- `cli_output` is ~150 lines of Python (5 small render functions)
- Codex `AGENTS.md` is one document
- Tests are mostly snapshot-style on `cli_output`

Implementation plan should phase as:
1. `cli_output` module + tests
2. Rewire `review-spec`, `review-code`, `review-pr` slash commands
3. Add `gate.md`, `cite.md` slash commands
4. Codex `AGENTS.md`
5. `extension.yml` update + smoke verification

Phases 1-3 can partly parallelize once `cli_output` is in.

## Honest Value Statement

What Phase 3 uniquely delivers:

1. **The slash commands actually invoke the capability layer.** Today they describe a workflow without running it. Phase 3 closes the loop so `/orca:review-code` produces a finding-shaped artifact derived from a real cross-agent-review pass.
2. **Codex can use orca.** Today `orca-cli` works for any shell user, but there's no doc Codex reads to know the capability layer exists. Phase 3 gives codex a one-stop pointer.
3. **`cli_output` is the boundary.** Slash commands stay declarative; capability output stays machine-readable; the markdown shape stays operator-friendly. Three surfaces, one translator.

What Phase 3 explicitly doesn't deliver:

- Magic — slash commands still need `ORCA_LIVE=1` and configured backends to actually run
- A new artifact format — existing review-X.md shapes are preserved
- Universal host adoption — that's perf-lab's job in Phase 4

## Resolved Design Decisions

- **`cli_output` entrypoint**: separate `python -m orca.cli_output render-{type} --feature-id ... [--round N]`. Keeps `orca-cli` focused on capability dispatch; renderers are a separate utility surface.
- **`/orca:gate` persistence**: operator-controlled `--persist` flag, default stdout-only. Writes append to `<feature_dir>/gate-history.md` only when `--persist` is passed.
- **`/orca:cite` persistence**: operator-controlled `--write` flag for symmetry, default stdout-only. Writes to `<feature_dir>/cite-report.md` only when `--write` is passed.
- **Codex `AGENTS.md` distribution**: in-place under `plugins/codex/AGENTS.md`. Codex reads project files directly; no install step needed (unlike Claude Code SKILL.md which is auto-generated and installed under `.claude/skills/`).
