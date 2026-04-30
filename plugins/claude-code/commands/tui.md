---
description: Launch the Orca TUI, a read-only 2-pane terminal surface (review queue + event feed) that watches flow-state artifacts and refreshes via watchdog or polling.
---

# /orca:tui

> **Status**: v1.1 (drawers + theming on top of the post-strip 2-pane TUI).
> Strictly read-only. All mutations still go through the CLI.

The Orca TUI is an always-on terminal surface that watches files
flow-state already produces and renders them as two live panes (review
queue + event feed). It is a companion to the CLI, not a replacement.
See `specs/018-orca-tui/spec.md` for the original v1 spec and
`specs/018-orca-tui/v1.1/spec.md` for v1.1 drawer + theming additions.
Lane and yolo panes were removed in Phase 1 of the orca v1 rebuild.

## Launch

```bash
python -m orca.tui
# optional flags
python -m orca.tui --repo-root /path/to/repo
python -m orca.tui --poll-interval 2.0
python -m orca.tui --force-polling   # skip watchdog even if available
```

The TUI runs against the current working directory by default and
refreshes via `watchdog` if importable, falling back to a polling loop
(header shows `polling mode (watchdog unavailable)`).

## Panes

1. **Review queue** (left) — cross-feature scan of
   `flow_state.compute_flow_state` for non-complete review milestones.
2. **Event feed** (right) — empty in Phase 1 (matriarch mailbox and
   yolo events were the prior sources). Phase 2 capabilities will
   re-source this pane.

## Keybindings

| key | action |
| --- | --- |
| `q` | quit |
| `r` | force refresh (bypass debounce) |
| `1` | focus review pane |
| `2` | focus event-feed pane |
| `Enter` | open drawer for focused row (v1.1) |
| `Escape` | close drawer (v1.1) |
| `t` | cycle Textual theme (v1.1) |

## Drawers (v1.1)

Pressing `Enter` while the review pane is focused and a row is under
the cursor opens a read-only drawer showing the full detail for that
row. Press `Escape` or `Enter` again to close.

- **Review drawer**: feature_id, review_type, status, artifact path,
  and a preview of the first 40 lines of the review artifact (when
  present).

Enter on the event-feed pane is a documented no-op (the feed is a
scrolling log without selectable rows).

### Graceful degradation

The drawer reads `review-*.md` review artifacts. The event feed is
intentionally empty after the v1 strip (no JSONL sources remain). If a
read fails (artifact not yet written, unreadable file), the drawer
renders a placeholder message rather than crashing the TUI. This
preserves the v1 invariant that one corrupt file never zeroes out the UI.

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
- **Graceful degradation.** Unavailable watchdog or unreadable review
  artifact — each has a documented empty-state / placeholder path.

## Related

- `specs/018-orca-tui/` — v1 spec, plan, brainstorm, data model.
- `specs/018-orca-tui/v1.1/` — drawer + theming additions.
