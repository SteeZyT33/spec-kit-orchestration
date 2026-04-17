# Implementation Plan: 018-orca-tui

**Branch**: `018-orca-tui`
**Spec**: `specs/018-orca-tui/spec.md`
**Brainstorm**: `specs/018-orca-tui/brainstorm.md`

## Summary

Ship a Textual-based read-only TUI under `src/speckit_orca/tui/` that watches
the files flow-state, matriarch, and yolo already produce, and renders a
four-pane live view: lane roster, active yolo runs, review queue, event
feed. Phase 1 is the MVP: no command palette, no detail drawers, no
mutations. Launch via `python -m speckit_orca.tui`.

## Technical Context

- **Runtime**: Python 3.10+, matching existing Orca.
- **UI framework**: `textual>=0.50`. Reactive widget model, async event loop,
  first-class test harness (`App.run_test()` / `Pilot`), renders across
  tmux / WSL2 / macOS terminals. Chosen over Rich-alone (no event loop),
  prompt_toolkit (input-centric, not read-centric), urwid (older widget
  model, weaker theming), and bash+tput (does not scale past one pane).
- **File watching**: `watchdog>=3.0`. Cross-platform inotify abstraction.
  Optional import - if `watchdog` cannot be imported, the TUI falls back to
  a 5-second polling loop across all panes and surfaces a "polling mode"
  indicator in the header.
- **Existing deps**: none of the TUI depends on matriarch, yolo, or
  flow-state being writable - it only imports their read APIs
  (`list_lanes`, `list_runs`, `run_status`, `compute_flow_state`, etc.).

### New runtime dependencies (called out explicitly)

Two new runtime dependencies are added to `pyproject.toml`:

1. **`textual>=0.50`** - powers the entire pane layout, reactive refresh,
   and pilot-based widget tests.
2. **`watchdog>=3.0`** - optional in practice (import is guarded) but listed
   as a direct dependency so default installs pick up the fast path.

Rich comes transitively via Textual and is not pinned separately. These are
both pure-Python (Textual) or pure-Python-with-optional-C-extensions
(watchdog), BSD/MIT/Apache licensed, widely adopted. The TUI sits behind
its own subpackage (`speckit_orca.tui`) so importing Orca's other
modules does not incur a Textual / watchdog cost unless the TUI is used.

## Constitution Check

- **Projection not source**: the TUI never mutates repo state. Every row
  traces to a file the existing CLI already writes. PASS.
- **SDD-agnostic**: the TUI does not parse `spec.md` / `plan.md` /
  `tasks.md` directly. It routes feature reads through `flow_state`. If
  016-multi-sdd teaches `flow_state` new artifact shapes, the TUI
  inherits them for free. PASS.
- **Read-only in v1**: zero mutation paths exposed. The command palette is
  explicitly v2. PASS.
- **Degrades cleanly**: missing matriarch directory, missing yolo runs,
  unavailable watchdog - each has a documented graceful path. PASS.
- **Testable without a terminal**: collectors are pure functions of
  repo-root input and can be unit-tested without mounting Textual. PASS.

## Project Structure

```
src/speckit_orca/tui/
  __init__.py        # subpackage marker, re-exports main()
  __main__.py        # python -m speckit_orca.tui entry point
  app.py             # OrcaTUI App subclass, layout, keybindings
  collectors.py      # pure-function data collectors
  watcher.py         # watchdog wrapper with polling fallback
  panes.py           # LanePane, YoloPane, ReviewPane, EventFeedPane widgets
tests/
  test_tui.py        # collector + pane unit tests using Textual Pilot
```

## Research Decisions

- **Textual over the alternatives**: see brainstorm §"Why Textual". Decision
  stands. Short form: Textual's reactive model + Pilot test harness is the
  best fit for a read-heavy, file-watching TUI with four panes that must
  stay testable.
- **watchdog over pure polling**: the yolo event stream can emit multiple
  events per second during an active run. A 5s poll means up to 5s of lag
  on the stage-transition event - exactly the one the operator wants to
  see fastest. Event-driven for fast data, polled as a reconcile / fallback.
- **Read APIs over subprocess for reads**: the TUI imports
  `matriarch.list_lanes`, `yolo.list_runs`, `yolo.run_status`,
  `flow_state.compute_flow_state` directly. Subprocess overhead on every
  refresh is pointlessly expensive and these are all pure read functions.
  Writes (v2 command palette) will shell out.
- **Layout: Textual grid**: four equally sized quadrants, header + footer.
  80-col fallback is Textual's default vertical stack; MVP does not attempt
  a hand-tuned compact mode.
- **Event feed retention**: last 30 entries in memory per pane spec FR-007.
  Past that, grep the JSONL files.

## Design Decisions

### Layout

Textual CSS grid with two rows of two panes, plus `Header` and `Footer`
widgets. Pane borders carry the title and a live row count.

### Refresh model

Three-tier, matching brainstorm:

1. **Event-driven for JSONL tails**: yolo event logs + matriarch mailbox
   inbound files watched via `watchdog.observers.Observer`. File change
   triggers pane recomputation on the main Textual event loop via
   `app.call_from_thread`.
2. **5s timer poll for derived state**: `flow_state.compute_flow_state`
   across all feature directories runs on a Textual `set_interval(5.0, …)`
   timer. Debounced so rapid file edits coalesce into one recompute.
3. **Full reconcile on `r` keybinding**: ignores debounce, runs every
   collector synchronously.

If `watchdog` is unavailable, tier 1 collapses into tier 2: every collector
runs on the 5s timer.

### Data sources (files the TUI reads)

| Pane | Source(s) |
| --- | --- |
| Lane roster | `matriarch.list_lanes` (reads `.specify/orca/matriarch/registry.json` + per-lane records) |
| Active yolo | `yolo.list_runs` + `yolo.run_status` per run |
| Review queue | `flow_state.compute_flow_state` per feature dir under `specs/` |
| Event feed | yolo `events.jsonl` per active run + matriarch mailbox `inbound.jsonl` per lane |

The TUI never writes to any of these.

## Implementation Sub-Phases

- **Phase A**: Skeleton - app, 4 placeholder panes, keybindings, CSS grid.
- **Phase B**: Collectors - `collect_lanes`, `collect_yolo_runs`,
  `collect_reviews`, `collect_event_feed`. Each a pure function. Each with
  a failing test first.
- **Phase C**: Watcher - watchdog wrapper with polling fallback, debounce.
- **Phase D**: Event feed wiring - tail JSONL files via the watcher, merge
  into one chronological view.
- **Phase E**: CLI - `python -m speckit_orca.tui` entry point with
  `--repo-root` and `--poll-interval` flags.

## Verification Strategy

- Unit tests for every collector. These do not import `textual`.
- Pane tests using Textual's `Pilot` harness to confirm widgets mount, read
  from collectors, and render non-empty tables when fed fixture data.
- Graceful-degradation tests: matriarch directory absent → lane pane
  renders empty informational row. watchdog import mocked to raise →
  TUI enters polling mode and sets the indicator.
- A single end-to-end smoke test that launches the app via
  `App.run_test()` against a minimal fixture repo and asserts the header
  and footer render.

## Non-Goals (Phase 1)

- Command palette (`:archive`, `:cancel`, `:yolo start`). Deferred to v2.
- Detail drawers on Enter. Deferred.
- Multi-repo aggregation. Deferred.
- Spec-lite / adoption panes. Deferred.
- Custom theming / color-blind mode flag. Deferred.
- ASCII-only fallback. Deferred.
- `speckit-orca tui` as a bash-dispatched subcommand. Phase 1 uses
  `python -m speckit_orca.tui` only; a bash wrapper can land later.
