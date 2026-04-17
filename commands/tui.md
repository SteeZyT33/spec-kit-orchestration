# /speckit.orca.tui

> **Status**: v1.1 (drawers + theming on top of the v1 4-pane MVP).
> Strictly read-only. All mutations still go through the CLI.

The Orca TUI is an always-on terminal surface that watches the files
flow-state, matriarch, and yolo already produce, and renders them as
four live panes. It is a companion to the CLI, not a replacement. See
`specs/018-orca-tui/spec.md` for the v1 spec and
`specs/018-orca-tui/v1.1/spec.md` for the v1.1 drawer + theming
additions.

## Launch

```bash
python -m speckit_orca.tui
# optional flags
python -m speckit_orca.tui --repo-root /path/to/repo
python -m speckit_orca.tui --poll-interval 2.0
python -m speckit_orca.tui --force-polling   # skip watchdog even if available
```

The TUI runs against the current working directory by default and
refreshes via `watchdog` if importable, falling back to a polling loop
(header shows `polling mode (watchdog unavailable)`).

## Panes

1. **Lane roster** (top-left) — `matriarch.list_lanes`. Columns:
   `lane`, `state`, `owner`, `reason`.
2. **Active yolo runs** (top-right) — `yolo.list_runs` +
   `yolo.run_status`. Terminal runs filtered out. Columns: `run`,
   `feat`, `stage`, `outcome`, `sync` (`FAIL` if dual-write broke).
3. **Review queue** (bottom-left) — cross-feature scan of
   `flow_state.compute_flow_state` for non-complete review milestones.
4. **Event feed** (bottom-right) — merged tail of all active yolo
   `events.jsonl` files and matriarch mailbox `inbound.jsonl` files.

## Keybindings

| key | action |
| --- | --- |
| `q` | quit |
| `r` | force refresh (bypass debounce) |
| `1` | focus lane pane |
| `2` | focus yolo pane |
| `3` | focus review pane |
| `4` | focus event-feed pane |
| `Enter` | open drawer for focused row (v1.1) |
| `Escape` | close drawer (v1.1) |
| `t` | cycle Textual theme (v1.1) |

## Drawers (v1.1)

Pressing `Enter` while a pane is focused and a row is under the cursor
opens a read-only drawer showing the full detail for that row. Press
`Escape` or `Enter` again to close.

- **Lane drawer**: full `summarize_lane` output — lane_id, spec_id,
  title, branch, worktree_path, owner, status_reason, dependencies,
  mailbox counts (inbound / outbound / reports), delegated work,
  assignment history, deployment metadata, registry revision.
- **Yolo run drawer**: full `RunState` — mode, lane_id, current_stage,
  outcome, block_reason, branch, head commit, review sub-statuses,
  retry_counts, matriarch_sync_failed flag, last event id/timestamp.
  Plus a tail of the last 10 events from `events.jsonl`.
- **Review drawer**: feature_id, review_type, status, artifact path,
  and a preview of the first 40 lines of the review artifact (when
  present).

Enter on the event-feed pane is a documented no-op (the feed is a
scrolling log without selectable rows).

### Graceful degradation

If the underlying read fails (missing lane record, unreadable
events.jsonl, artifact not yet written), the drawer renders a
placeholder message rather than crashing the TUI. This preserves the
v1 invariant that one corrupt file never zeroes out the UI.

## Theming (v1.1)

Pressing `t` cycles through Textual's built-in themes: `textual-dark`
(default), `textual-light`, `monokai`, `dracula`. The cycle list is
filtered against the running Textual version's
`app.available_themes`, so a theme missing from an older Textual
build is silently dropped from the cycle instead of crashing.

Theme selection persists for the lifetime of the process — it survives
auto-refresh and manual `r` refresh cycles.

## Invariants

- **Read-only.** No keybinding, pane, or drawer mutates repo state.
  Mutations still go through the CLI.
- **Projection not source.** Every row traces to a file the CLI
  already writes. The TUI never invents state.
- **SDD-agnostic.** The TUI does not parse `spec.md` / `plan.md` /
  `tasks.md` directly. Feature reads route through `flow_state`.
  Review-artifact previews are a bounded exception — they read
  `review-*.md`, which is the review artifact itself.
- **Graceful degradation.** Missing matriarch dir, missing yolo runs,
  unavailable watchdog, malformed JSONL, unreadable review artifact —
  each has a documented empty-state / placeholder path.

## Related

- `commands/matriarch.md` — lane CLI surface.
- `commands/yolo.md` — single-lane runtime.
- `specs/018-orca-tui/` — v1 spec, plan, brainstorm, data model.
- `specs/018-orca-tui/v1.1/` — drawer + theming additions.
