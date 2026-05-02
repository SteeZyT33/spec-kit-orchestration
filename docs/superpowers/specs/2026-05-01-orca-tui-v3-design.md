# orca TUI v3 — Fleet View

**Status:** Approved (brainstormed 2026-05-01, supersedes v2)
**Owner:** Taylor
**Predecessor:** `docs/superpowers/specs/2026-05-01-orca-tui-v2-design.md` (judged "absolute trash" — superseded, not iterated)

## Goal

A single-screen fleet view that answers one question: **what is each agent doing right now, where is it in flow, and is it healthy?**

The TUI exists to visualize **agent organization**, **doneness** (lifecycle stage), and **worktree health** (live/stale/abandoned/failed). Nothing else.

## Why v2 was scrapped

v2 shipped three panes (reviews / events / adoption) plus a kanban toggle. It surfaced bookkeeping artifacts (review-artifact filenames, git events, adoption manifest fields) instead of agent activity. The operator could not glance at it and answer "what is my fleet doing." It also looked AI-generated — unfocused color palette, redundant borders, generic logo.

v3 is a clean redesign, not a fix-up. Different mental model, different visual language.

## What it shows

A single full-height table. One row per lane (worktree). Sorted by state (live → stale → merged → failed → idle).

| Column     | Source                                                       | Width (rendered) |
|------------|--------------------------------------------------------------|------------------|
| state      | derived (live/stale/merged/failed/idle)                      | 1 ch             |
| agent      | `Sidecar.agent` ("claude" / "codex" / "none")                | 6 ch             |
| lane       | `Sidecar.feature_id · Sidecar.branch`                        | 22 ch            |
| stage      | flow-state strip (2-char glyphs + dot separators)            | 23 ch            |
| last_seen  | derived from `last_attached_at` + `agent.launched/exited`    | 5 ch             |
| s·c·p      | review verdicts shorthand (spec/code/pr)                     | 7 ch             |
| health     | staleness / doctor warnings (empty when fine)                | 8 ch             |

Implementation note: `FleetTable` uses `cell_padding=0` so declared `add_column(width=N)` renders at exactly N chars (no padding added). Total: state(1) + agent(6) + lane(22) + stage(23) + seen(5) + s·c·p(7) + health(8) = 72 ch + 2 ch border + 2 ch fleet-panel padding = 76 ch. Fits in 80 cols, breathes at 140.

### State glyph (column 1)

| Glyph | Meaning             | Rule                                                                |
|-------|---------------------|---------------------------------------------------------------------|
| `●`   | live                | tmux session+window alive AND `agent.launched` more recent than `agent.exited` |
| `◐`   | stale               | last_attached_at > 24h ago, no `lane.removed`                       |
| `◯`   | merged-not-removed  | branch merged into base, lane sidecar still active                  |
| `✕`   | failed              | most recent setup.* event is `.failed` and no recovery since        |
| `·`   | idle                | none of the above; lane exists but has no recent activity           |

Color: live=green, stale=yellow, merged=cyan, failed=red, idle=dim.

### Stage strip (column 4)

Eight glyphs, one per stage in `flow_state.STAGE_ORDER`:
`br · sp · pl · ta · im · rs · rc · rp`

For each stage:
- lowercase = not started or skipped (e.g. `br`)
- UPPERCASE bold = currently active (the highest stage with `in_progress`)
- color: green=complete, yellow=in_progress, red=blocked, dim=not_started

The strip is a glance-readable progress meter. The user can see "this lane is in implement" or "this lane is stuck on review-spec" without leaving the row.

### Done column

Three slots: `spec code pr`. Each is `✓` (verdict ready/ready-for-pr/merged), `⏵` (in_progress), `✕` (blocked / needs-revision), or `·` (no review yet).

### Health column

Comma-separated short tags, only when something is wrong:
- `stale 14d` — last_attached_at age
- `setup-failed` — last setup event failed
- `merged·cleanup` — branch is merged, worktree should be removed
- `tmux-orphan` — tmux session killed but lane still active
- `doctor: <hint>` — `wt doctor` warnings

Empty when healthy. Red text when present.

## Drill-down (Enter on a row)

Pushes a screen with:
1. **Header:** `<lane_id> · <agent> · <state>` and worktree path
2. **Metadata:** branch, base, ahead/behind, host_system, task_scope
3. **Stage progress:** the 8 stages, full names, with timestamps and evidence-source paths (from `flow_state.FlowMilestone.evidence_sources`)
4. **Recent events:** last 20 entries from `events.jsonl`, newest first

`Esc` returns to the fleet view.

## Keybindings (footer)

| Key   | Action                                                  |
|-------|---------------------------------------------------------|
| `↑↓`  | navigate                                                |
| `↵`   | drill into focused lane                                 |
| `o`   | open shell in worktree                                  |
| `e`   | open `$EDITOR` in worktree                              |
| `r`   | remove (close) lane (confirm modal, then `orca-cli wt rm`) |
| `n`   | new lane (calls `orca-cli wt new` with prompt modal)    |
| `d`   | doctor (calls `orca-cli wt doctor`, shows result modal) |
| `g`   | refresh (manual)                                        |
| `q`   | quit                                                    |

`--read-only` flag suppresses `r`, `n`, `d`. Footer hides them too.

## Architecture

```
src/orca/tui/
  __init__.py
  __main__.py       # `python -m orca.tui` entrypoint
  app.py            # FleetApp(App)
  fleet.py          # FleetTable(DataTable) — the only main-screen widget
  drilldown.py      # LaneScreen(Screen) — Enter pushes this
  models.py         # FleetRow dataclass (pure data)
  collect.py        # collect_fleet(repo_root) -> list[FleetRow]
  flow_strip.py     # render the 8-stage strip from FlowProjection
  state.py          # derive state glyph from sidecar + events
  health.py         # derive health tags
  actions.py        # subprocess wrappers (orca-cli wt rm/new/doctor; shell; editor)
  modals.py         # ConfirmModal, ResultModal, NewLaneModal, DoctorModal
  watcher.py        # watchdog → debounced on_change() callback
  theme.tcss        # the entire visual style, in one file
```

`tui-v3-impl` branches off `main`, wiping the v2 tree on first commit. No legacy stub.

## Visual language

- **One bordered region only:** the fleet table. No nested boxes, no logo header, no banner.
- **Color discipline:** four palette slots — green (good), yellow (in progress / warning), red (failure / blocked), neutral (everything else, default fg). No accent decoration, no rainbow.
- **No emoji except the state glyph and review check.** State uses `● ◐ ◯ ✕ ·`. Review uses `✓ ⏵ ✕ ·`. Nothing else.
- **Monospace alignment.** All columns padded to width with single-space separators. The stage strip is `br·sp·pl·ta·im·rs·rc·rp` — middle-dot separators, lowercase letters, UPPER for current.
- **Bottom status line:** `host: <host_system> · <N> lanes · <stale_count> stale · <merged_count> ready-to-merge · last refresh: 2s ago`. One line. Dim.
- **Footer:** Textual's standard `Footer()` widget with the key bindings above. No customization.

The v2 logo header, banner art, multiple bordered panes, severity-rainbow, and "events feed" are explicitly removed.

## Data sources (no new I/O)

The collector reads:
- `.orca/worktrees/registry.json` and per-lane sidecars
- `.orca/worktrees/events.jsonl` (last N entries)
- `flow_state.project_feature(feature_id, layout)` for each lane that has a `feature_id`
- `git for-each-ref --merged <base>` to detect merged-not-removed
- `tmux has-session -t <session>` to detect tmux-orphan

All of this is host-agnostic via `host_layout.from_manifest(repo_root)`.

## Reactivity

- `Watcher` monitors `.orca/worktrees/`, `.orca/worktrees/events.jsonl`, and `host_layout.list_features()`-derived feature dirs.
- Coalesce window: 0.5s.
- Manual refresh: `g`.
- Polling fallback: 5s when watchdog unavailable.

## Mutations

All mutating actions shell out to existing `orca-cli` verbs. No direct file writes from the TUI process. `--read-only` suppresses bindings entirely.

| Action       | Command                                                        |
|--------------|----------------------------------------------------------------|
| close lane   | `orca-cli wt rm --branch <branch> --force`                     |
| new lane     | `orca-cli wt new --feature <id> --agent <agent> [--from <br>]` |
| doctor       | `orca-cli wt doctor --reap`                                    |
| open shell   | spawn `$SHELL -i` cwd=`worktree_path` (in `app.suspend()`)     |
| open editor  | spawn `shlex.split($EDITOR) <worktree_path>` (in suspend)      |

## Quality gates

- **`tui-reviewer` agent reviews each phase** — after spec, after plan, after each implementation step. v2 had no outside-eyes review.
- **Visual smoke at 80×24, 100×30, 140×44.** Each smoke captures a Pilot SVG and passes it through `tui-reviewer` before phase advance.
- **TDD on collectors and renderers.** State derivation, stage strip rendering, health-tag derivation are pure functions tested without Textual.
- **Functional smoke on actions.** End-to-end against a throwaway worktree: `n` creates, `r` removes, `d` runs doctor, `o`/`e` suspend correctly.

## Out of scope

Same exclusions as v2 plus more:
- No multi-repo. One repo per process.
- No filter/sort UI. Fixed sort by state. If the fleet exceeds one screen, scroll.
- No mouse.
- No drag-to-advance.
- No mark-review-complete from inside the TUI.
- No command palette.
- No dashboards, charts, or graphs.
- No "events" pane. Events live in drill-down.
- No "adoption" pane. Adoption shows as one bottom-status-line field.

## Implementation phasing

1. **Phase 0 — Branch + scaffold.** Create branch `tui-v3-impl` off `main`. Scaffold `src/orca/tui/v3/` skeleton. Wire `python -m orca.tui` to v3. Wire `--read-only` and `--repo-root`.
2. **Phase 1 — Pure-function core.** Models, collect, state derivation, stage-strip rendering, health-tag derivation. Full TDD, no Textual.
3. **Phase 2 — Render the table.** FleetTable + theme.tcss + bottom status line + watcher wiring. `tui-reviewer` gate at end.
4. **Phase 3 — Drill-down.** LaneScreen with metadata, stage progress, recent events. `tui-reviewer` gate.
5. **Phase 4 — Actions.** `o`/`e`/`r`/`n`/`d` wired through subprocess. End-to-end smoke against throwaway worktree. `tui-reviewer` gate.
6. **Phase 5 — Polish + production checklist.** 80×24/100×30/140×44 smoke renders, full pytest, PR.

Each phase ends with a `tui-reviewer` agent run against the rendered SVG snapshot. v2's failure was no outside review — v3 corrects that.

## Production-readiness checklist

- [ ] Renders cleanly at 80×24, 100×30, 140×44 (SVGs reviewed by `tui-reviewer`).
- [ ] Full pytest suite green (existing 900+ tests + new TUI tests).
- [ ] End-to-end action smoke against a throwaway worktree (n / r / d / o / e all succeed).
- [ ] Watcher coalesces; no flicker on idle (verified by 30s render-stability test).
- [ ] `--read-only` mode hides mutating keys and refuses `r`/`n`/`d` if invoked.
- [ ] `tui-reviewer` returns "approved" on the final 140×44 render.
- [ ] PR opened against `main`.

## Non-goal: backwards compatibility with v2

v3 replaces v2. **No preservation.** The v2 branch (`tui-v2-impl`) and its TUI code are abandoned. v3 branches off `main` with a fresh `src/orca/tui/` tree. The previous TUI is reachable via git history if anyone ever wants to look at it.
