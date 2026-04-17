# Brainstorm: Orca TUI — An Always-On Status Pane for Spec Development

**Feature Branch**: `018-orca-tui`
**Created**: 2026-04-16
**Status**: Brainstorm
**Informed by**:

- `README.md`'s four-concept workflow (intake / state / review / lanes)
  and the explicit "experimental" framing of matriarch multi-lane
  supervision.
- `src/speckit_orca/flow_state.py` — the durable aggregator of feature
  state, spec-lite state, and adoption state. The TUI's central data
  consumer.
- `src/speckit_orca/matriarch.py` — lane registry, mailbox, report
  queue, delegated work, deployment metadata. The lane-pane data
  source.
- `src/speckit_orca/yolo.py` — event-sourced single-lane runner with
  dual-write to matriarch, sync-failed flag, stage prerequisites, and
  retry bounds.
- `commands/matriarch.md` — current lane command surface (all CLI,
  all file-backed, no live view).
- Personal observation: during multi-lane work, I keep three terminals
  open (`speckit-orca --status`, `bash scripts/bash/orca-matriarch.sh
  lane list`, and `tail -f` on the latest yolo events.jsonl). Each
  tells me a slice of the truth; none of them tell me the whole truth
  without cross-referencing.

---

## Problem

Orca's durable primitives are excellent at *storing* state — event
logs, registry files, review artifacts, handoff records. They are
deliberately file-backed, inspectable, replay-safe. But they are
mediocre at *surfacing* that state to the operator while work is
happening. Today the only way to see what's going on across features
is to run a CLI command that prints a snapshot, then run another CLI
command that prints another snapshot, and mentally join them.

This costs more than it looks like it costs. Concrete visibility gaps:

- **Lane state is ambient but invisible.** `bash
  scripts/bash/orca-matriarch.sh lane list` gives you a JSON dump of
  all lanes with effective state, readiness, blockers, and mailbox
  counts. It's a great one-shot. But if you're actively driving one
  lane and another lane's dependency just flipped to satisfied, you
  have no way of knowing until you re-run the command. Matriarch's
  data is durable; the operator's awareness of it is not.

- **yolo runs happen in a tail you have to `tail` manually.** The
  yolo runtime writes every event to
  `.specify/orca/yolo/runs/<run_id>/events.jsonl` and a derived
  `status.json`. If you want to know what stage a run is at right
  now, you `cat status.json`. If you want to know the sequence of
  events that got it there, you `tail events.jsonl`. If you want to
  know whether the matriarch dual-write is failing, you check for
  the `.matriarch_sync_failed` marker. Three separate checks for one
  piece of live information.

- **Review queue state is distributed across files.** A cross-pass
  review is requested via a `CROSS_PASS_REQUESTED` event in a yolo
  run, fulfilled by writing evidence into `review-spec.md` /
  `review-code.md` / `review-pr.md`, and surfaces in flow-state as
  a review milestone. To know "what reviews are pending across all
  active features right now," you run flow-state on each feature
  directory individually and join the results by hand.

- **Mailbox traffic is invisible until you ask.** Matriarch's mailbox
  is the durable substrate for lane↔worker messages — instruction,
  ack, status, blocker, question, approval_needed, handoff, shutdown.
  They're written to `.specify/orca/matriarch/mailbox/<lane>/*.jsonl`
  and consumed on demand. A new blocker written to a lane's mailbox
  is invisible to the operator until they run `lane mailbox list`.

- **"Is this run healthy?" is a three-way join.** A yolo run in
  supervised mode is healthy only when (a) the yolo reducer reports
  `outcome=running`, (b) `sync_failed` is False, and (c) matriarch's
  lane summary shows a matching owner and unarchived lifecycle.
  Joining these three is mechanical, but doing it in my head while
  driving other work is error-prone.

- **Multi-lane context switching has no visible "home page."**
  Matriarch is experimental in v1 precisely because no one yet has
  a good answer for "show me everything going on across lanes in
  one place." The CLI surfaces are all one-shot JSON; `--status` is
  a snapshot; flow-state is per-target. There is no always-on view
  that says "here are your three lanes, here are the two active
  yolo runs, here is the one pending cross-pass." The operator
  assembles it by polling.

None of this is a failure of the durable primitives. The event log,
registry, and review artifacts are all doing their jobs correctly —
they're *correctness* surfaces, not *awareness* surfaces. The gap is
that Orca has no awareness surface at all. A TUI closes that gap
without changing any of the durable primitives.

Crucially, this is **not** a "the CLI is bad, let's replace it"
brainstorm. The CLI is correct and should stay authoritative. The
TUI is a *companion* — a visible pane that watches the same files the
CLI reads, so the operator can glance instead of poll.

---

## Proposed approach

**Ship a Textual-based TUI as a new `speckit_orca.tui` module**,
invoked via `speckit-orca tui` (or `python -m speckit_orca.tui`).
The TUI is a read-heavy, file-watching viewer that composes
flow-state, matriarch, and yolo runtime reads into a single
always-on pane. It does not mutate state; mutations go through the
existing CLI.

### Why Textual (and not the alternatives)

Four real options were considered. Textual wins on fit, and the
reasoning matters because the wrong TUI library turns into a drag
on every subsequent refinement.

- **Textual** (recommended). Python-native, built on Rich, has a
  reactive widget model, supports async event loops, renders in
  any modern terminal (including tmux + WSL2, which is my
  environment), and — critically — has first-class support for
  live-updating panes driven by background watchers. Its widget
  library (`DataTable`, `Tree`, `RichLog`, `Static`,
  `TabbedContent`) maps cleanly to the panes this TUI needs. The
  theming story is good (CSS-like syntax), and the project is
  actively maintained. Textual apps are also testable without a
  real terminal via its `App.run_test()` harness, which matters
  for Orca's contract-heavy test discipline.

- **Rich alone**. Rich is Textual's rendering engine. Using Rich
  without Textual means building the event loop, keybinding router,
  and layout manager by hand. That's a surprising amount of
  scaffolding for a subsystem whose whole point is "show state."
  Rejected for v1 — we'd be reinventing Textual badly. Rich's
  `Live` display could work for a single-pane MVP but starts to
  fight back as soon as you want two panes that update on different
  schedules.

- **prompt_toolkit**. Excellent library for full-screen interactive
  apps (it's what powers ptpython and Jupyter's console). Strong
  keybinding support. But prompt_toolkit's strength is *input-heavy*
  TUIs — REPLs, editors, wizards. Orca's TUI is overwhelmingly
  *read-heavy* with occasional keybindings, which is Textual's
  sweet spot. prompt_toolkit also doesn't have Textual's async
  file-watcher integration baked in. Rejected: right tool for the
  wrong shape of problem.

- **urwid**. The original Python TUI framework, still maintained,
  used by projects like Mitmproxy. Solid but showing its age; its
  widget model is lower-level than Textual's and its theming is
  clunky. Rejected primarily because Textual's async model and
  Rich integration are concretely better for Orca's "watch these
  JSON files and re-render" shape.

- **bash + tput + watch**. Tempting because it requires no new
  dependencies. Viable for a 3-line "show me flow-state every 2
  seconds" display. Not viable for anything with multiple panes,
  keybindings, or reactive refresh. Rejected outright: the cost
  of implementing a multi-pane TUI in shell is higher than the
  cost of taking a Textual dependency, and the result is worse.

Decision: **Textual**. Taking a dependency on `textual>=0.50` (and
transitively `rich>=13`) is worth it. Both are pure-Python, BSD-ish
licensed, and widely adopted.

### Install / invocation shape

- Add `textual` and `rich` to the main `pyproject.toml` dependency
  list (not an extras group — the TUI is part of the product
  surface, not a plugin).
- New entry point: `speckit-orca tui` dispatches to
  `speckit_orca.tui.cli:main`. Optionally: `python -m
  speckit_orca.tui` as a direct invocation.
- Module layout: `src/speckit_orca/tui/` (package, not single
  file). Components live as siblings: `app.py`, `panes/`,
  `watchers/`, `theme.css`, `cli.py`.

---

## Layout proposal

The TUI is a single full-screen app with four panes in a fixed
layout, plus a header and a footer with keybindings. All four panes
are visible simultaneously — no tab switching for the core view.
(Tab switching may appear later for drilldowns; see MVP vs. richer.)

```text
┌─ orca tui ─ repo: spec-kit-orca ─ branch: 018-orca-tui ──────────┐
│                                                                  │
│ ┌─ lanes (3 active, 1 blocked) ──┐ ┌─ active yolo runs (2) ────┐ │
│ │ ID          STATE    BLOCKER    │ │ RUN  FEAT STAGE    SYNC  │ │
│ │ 014-yolo    review   —          │ │ run… 014  impl     ok    │ │
│ │ 015-brown…  active   —          │ │ run… 017  revi…    FAIL  │ │
│ │ 017-brown…  blocked  dep 014    │ │                          │ │
│ │ 010-matr…   archived —          │ │                          │ │
│ └─────────────────────────────────┘ └──────────────────────────┘ │
│                                                                  │
│ ┌─ review queue (1 pending) ──────┐ ┌─ event feed (live) ───────┐ │
│ │ FEATURE     KIND         AGENT   │ │ 14:32:01 yolo  run-…     │ │
│ │ 017-brown…  review-spec  codex   │ │ 14:31:58 matr  lane 015… │ │
│ │                                  │ │ 14:31:45 yolo  stage_ent │ │
│ │                                  │ │ 14:31:02 matr  mailbox…  │ │
│ └──────────────────────────────────┘ └──────────────────────────┘ │
│                                                                   │
├─ [q] quit  [r] refresh  [/] filter  [?] help  [l] lane  [y] run ─┤
└───────────────────────────────────────────────────────────────────┘
```

### Pane details

**1. Lane roster (top-left).** Rows are lanes from matriarch's
registry. Columns: lane_id, effective_state, owner_id, stage,
blocker_reason (truncated). Archived lanes shown dimmed. Hard-blocked
lanes shown red. Review-ready and pr-ready shown in accent color.
Clicking / pressing Enter on a row opens a detail drawer for the
lane (mailbox counts, dependencies, deployment status). Data source:
`speckit_orca.matriarch.list_lanes(repo_root=…)` + the registry
index.

**2. Active yolo run (top-right).** Rows are non-terminal yolo runs
across the whole repo (not just the current feature). Columns:
run_id (shortened to 8 chars), feature_id, current_stage, outcome,
sync_failed flag (loud red "SYNC FAIL" if set). Clicking opens a
per-run drawer showing the last N events. Data source:
`speckit_orca.yolo.list_runs(repo_root)` + `run_status(repo_root,
run_id)` for each. Terminal runs filtered out by default, toggleable
via a keybinding.

**3. Review queue (bottom-left).** Pending cross-passes and
unresolved review threads across all features. Columns: feature_id,
review_kind (review-spec / review-code / review-pr), assigned_agent,
status (pending / in_progress / stale). Data source: for each feature
directory, the flow-state review milestones where status is not
`complete`, plus yolo's `CROSS_PASS_REQUESTED` events that haven't
been followed by a `CROSS_PASS_COMPLETED`. Also surfaces stale
review-spec (where clarify re-ran after review).

**4. Event feed (bottom-right).** Live tail of the union of: (a)
yolo event logs for all active runs, (b) matriarch mailbox and
report queues for all active lanes. Each row: timestamp, source
("yolo" / "matr"), one-line summary (event_type + feature/lane +
key payload field). Auto-scrolls to newest. Pressing `Space`
pauses the scroll for reading.

### Header and footer

- **Header**: repo name (from git config or CWD), current branch,
  optional feature indicator ("viewing specs/018-orca-tui/" if
  invoked from a feature dir). Shows count badges for lanes,
  active runs, pending reviews.
- **Footer**: active keybinding hints, grouped by pane. Press `?`
  to toggle a full keybinding help overlay.

### Keybindings

- `q` quit
- `r` force refresh (bypass watcher debounce)
- `/` open filter (applies to the focused pane)
- `?` toggle help overlay
- `l` focus lane pane
- `y` focus yolo pane
- `v` focus review pane (v for "verify" — r is taken)
- `e` focus event feed
- `Tab` cycle focus
- `Enter` open drawer for focused row
- `Esc` close drawer
- `p` pause / resume event feed scroll
- `a` toggle archived / terminal items visibility
- `:` open command palette (v2; see sequencing)

Keybindings are intentionally modal-ish — pressing `l` does not
enter a mode, it just focuses the pane. No vim-like motion layer
in v1.

### Command palette (deferred to v2)

A `:` palette lets the operator trigger a CLI action without
leaving the TUI. First palette commands: `:archive <lane>`,
`:resume <run>`, `:cancel <run>`, `:yolo start <feature>`. Each
dispatches to the equivalent CLI subcommand via `subprocess.run`
and emits the result into the event feed. Not MVP; the v1 TUI is
strictly read-only and users drop to a separate terminal for
mutations.

---

## Data sources (which files the TUI watches)

Everything the TUI renders comes from existing durable artifacts. No
new file types, no new state stores, no new schemas. Specifically:

- **Lane registry**: `.specify/orca/matriarch/registry.json` +
  `.specify/orca/matriarch/lanes/<lane_id>.json`
- **Lane mailbox**: `.specify/orca/matriarch/mailbox/<lane_id>/inbound.jsonl`
  and `outbound.jsonl`
- **Lane reports**: `.specify/orca/matriarch/reports/<lane_id>/events.jsonl`
- **Lane delegated work**: `.specify/orca/matriarch/delegated/<lane_id>.json`
- **yolo runs**: `.specify/orca/yolo/runs/<run_id>/events.jsonl`,
  `status.json`, and the `.matriarch_sync_failed` marker file
- **Flow-state resume metadata (optional)**:
  `.specify/orca/flow-state/<feature_id>.json`
- **Feature artifacts**: `specs/<feature_id>/spec.md`, `plan.md`,
  `tasks.md`, `review-spec.md`, `review-code.md`, `review-pr.md`
- **Spec-lite registry**: `.specify/orca/spec-lite/SL-NNN-*.md`
  (for a future "lite + adoption" pane, post-MVP)
- **Adoption registry**: `.specify/orca/adopted/AR-NNN-*.md`
  (same — post-MVP pane)

The TUI does not invent derived state. Every value on screen is
traceable to one of the above files. That's the core invariant:
**the TUI is a projection, not a source.**

---

## Refresh model

Three tiers, chosen per data source:

1. **Event-driven via yolo's dual-write.** The yolo runtime already
   emits durable events on every stage transition and writes them
   to the event log plus the matriarch mailbox. The TUI watches
   the yolo events.jsonl files (one per active run) and the
   matriarch mailbox/report jsonl files. When a new line is
   appended, the TUI re-reduces that run or re-renders that lane.
   Implementation: Python's `watchdog` library (cross-platform
   inotify abstraction) is the obvious choice. Already in wide use;
   low cost to adopt.

2. **Poll on a fixed interval for derived state.** Flow-state is
   relatively expensive to compute (it parses markdown, reads task
   lists, checks git). Re-computing on every event would be wasteful.
   Instead: recompute flow-state for all visible features every 5
   seconds on a timer, or immediately when the feature's spec.md /
   tasks.md / review-*.md is modified. Debounced so rapid edits
   don't cause thrash.

3. **On-demand for detail drawers.** When the user presses Enter on
   a lane row, the drawer fetches `summarize_lane(lane_id)` once
   and refreshes on the same event-driven channel as the main pane.
   No proactive fetching for panels the user isn't looking at.

### Why not pure polling?

Polling is simpler to implement, and for v1 it's tempting to just
poll everything every 2 seconds. But the yolo event stream can emit
multiple events per second during an active run, and a 2-second
poll means up to 2 seconds of lag on "stage transitioned" — which
is exactly the event the operator most wants to see immediately.
Event-driven for the fast-moving data, polled for the slow-moving
data, is the right shape.

### Why not pure event-driven?

Inotify on WSL2 has known gotchas (some filesystem events drop
under heavy load), and relying solely on it means a dropped event
becomes a permanently stale UI. Combining event-driven with a
60-second "reconcile all" sweep gives us correctness as a fallback
without sacrificing responsiveness.

### Fallback: `watchdog` is optional

If `watchdog` can't be imported (it's a C-extension-ish package;
should Just Work on Linux / macOS / Windows but occasionally has
wheel issues), the TUI falls back to 2-second polling across the
board with a visible "polling mode (watchdog unavailable)" banner.
No silent degradation.

---

## Integration with existing CLI

**The TUI invokes CLI subcommands via `subprocess.run`, not Python
APIs directly.** Reasoning:

- The CLI is the contract surface — the commands in
  `scripts/bash/orca-matriarch.sh`, `python -m
  speckit_orca.flow_state`, and `python -m speckit_orca.yolo` are
  where stability guarantees live. Calling Python APIs directly
  would couple the TUI to internal signatures that could change
  across Orca versions.
- Subprocess invocation gives us a natural audit trail: the exact
  CLI command the TUI ran is the exact command a user could run
  themselves from a terminal. This matches Orca's durable-
  inspectable philosophy.
- Mutations via subprocess are atomic in the same way the CLI is
  atomic. The TUI doesn't hold partial state across calls.

**Exception**: for the *read* path, the TUI imports Python APIs
directly (`speckit_orca.flow_state.compute_flow_state`,
`speckit_orca.matriarch.list_lanes`,
`speckit_orca.yolo.run_status`). Subprocess overhead on every
refresh is pointlessly expensive, and reads don't have the same
atomicity concerns as writes. The import target is the same Python
process that runs the CLI, so there's no versioning mismatch risk.

In practice: v1 is read-only, so the subprocess question is deferred.
When the v2 command palette lands, it will shell out.

---

## Relationship to matriarch's "experimental" status

Matriarch is marked experimental in v1 (per README's Experimental
section) precisely because the runtime shipped with deliberate
conservatism: lane lifecycle, dependencies, mailbox, event envelope
are all implemented, but drift-flag surfacing, live tmux session
inspection, and the hook model are tracked as post-v1 refinements.

The TUI **accelerates de-experimentalization** of matriarch by
closing the single biggest visibility gap that keeps it experimental:
"operators can't see what's going on without running three CLI
commands." But the TUI does not *require* matriarch to leave
experimental status — they can evolve independently. A v1 TUI can
ship against v1 matriarch, and if matriarch adds drift-flag surfacing
later, the TUI grows a column.

Non-goal: the TUI is **not** a matriarch graduation ceremony. It
doesn't promise "now matriarch is stable." It surfaces what's there.

---

## Relationship to 016 multi-SDD (should the TUI render across SDD formats?)

016-multi-sdd-layer is the in-flight spec for Orca being usable
across multiple spec-development frameworks (spec-kit, OpenSpec,
spec-kitty, etc.). Its shape is still being defined — the directory
exists but there's no brainstorm.md yet.

The TUI's posture toward 016: **render against the Orca abstraction
layer, not the raw SDD files.** Concretely:

- Lane roster, yolo runs, review queue, event feed all come from
  Orca-owned files (`.specify/orca/matriarch/…`,
  `.specify/orca/yolo/…`). These are SDD-agnostic by construction —
  they live under `.specify/orca/` regardless of whether the
  underlying SDD is spec-kit or OpenSpec.
- Flow-state's output is already SDD-aware (it parses feature
  directories + spec-lite + adoption records). If 016 teaches
  flow-state to recognize OpenSpec delta-specs or spec-kitty
  artifacts, the TUI inherits that support for free — it consumes
  flow-state's output, not the raw files.
- The TUI does not parse spec.md, plan.md, tasks.md directly. It
  asks flow-state. If 016 changes the artifact shape, 016 updates
  flow-state, and the TUI keeps working.

This is a hard invariant: **the TUI never parses SDD artifacts
directly.** Everything goes through flow-state or matriarch.

---

## Downstream impact (file-by-file)

### New package: `src/speckit_orca/tui/`

- `__init__.py` — empty or re-exports the app class
- `cli.py` — `main()` entry point for `speckit-orca tui`, flag
  parsing (`--repo-root`, `--no-watch`, `--refresh-interval`),
  dispatch into `app.OrcaTUI().run()`
- `app.py` — Textual `App` subclass; sets up layout, mounts panes,
  registers keybindings, owns the shared data-refresh dispatcher
- `panes/` subdir
  - `lane_roster.py` — `DataTable`-based lane pane
  - `yolo_runs.py` — `DataTable`-based yolo pane
  - `review_queue.py` — `DataTable`-based review pane
  - `event_feed.py` — `RichLog`-based scrolling tail
  - `detail_drawer.py` — generic drawer widget for per-row drilldown
- `watchers/` subdir
  - `file_watcher.py` — watchdog wrapper with polling fallback
  - `event_stream.py` — async merge of yolo + matriarch jsonl tails
  - `flow_state_poller.py` — debounced flow-state recompute
- `theme.css` — Textual CSS for pane colors, borders, hover states
- `README.md` — brief operator guide (how to run, how to interpret
  panes). **Note**: per CLAUDE.md, documentation files require
  explicit user request; skip this for v1 unless requested.

### `src/speckit_orca/cli.py`

- New subcommand: `tui` — dispatches to `speckit_orca.tui.cli:main`.
- Help text in `--status`: "for a live view, try `speckit-orca tui`."

### `pyproject.toml`

- Add `textual>=0.50` and `watchdog>=3.0` to main dependencies.
- (Rich comes transitively via Textual; don't pin separately.)

### `uv.lock`

- Regenerated to include the new deps. Lockfile churn is expected.

### `README.md`

- Add a short subsection under the four-concept workflow:
  "Live view (optional): `speckit-orca tui` opens a single-pane
  TUI that watches lanes, yolo runs, and reviews simultaneously.
  The TUI is a companion to the CLI — all mutations still go
  through CLI commands."
- Mention in the Experimental section that the TUI helps close
  matriarch's visibility gap.

### `Makefile`

- Optional new target: `make tui` runs the TUI against the current
  repo. Mostly for convenience during development.

### Tests

- `tests/test_tui/` directory
- `test_tui_app.py` — uses Textual's `App.run_test()` harness to
  mount the app against a fixture repo and assert the panes
  render the expected rows.
- `test_tui_watchers.py` — unit tests for the file watchers,
  including the watchdog-unavailable fallback path.
- `test_tui_data_sources.py` — contract tests that the pane
  rendering matches what the underlying Python APIs return.
  Explicitly: no snapshot-of-markdown tests; the TUI is tested at
  the same abstraction level as flow-state.

### Integration manifests

- `.specify/integrations/claude.manifest.json` — no change; the
  TUI is a binary invocation, not a slash command.
- `.specify/integrations/codex.manifest.json` — same; no change.

### No changes to

- `src/speckit_orca/flow_state.py` — the TUI is a consumer; the
  aggregator stays as-is.
- `src/speckit_orca/matriarch.py` — same.
- `src/speckit_orca/yolo.py` — same. This is a hard rule: the
  TUI is not allowed to modify runtime internals to make its own
  life easier. If the TUI needs a new read shape, it goes through
  an existing API or adds a new read function with tests.

---

## Sequencing — MVP then richer

### MVP (v1): single-file bring-up

The goal of MVP is to prove the Textual shape works against Orca's
real data. Scope:

- Lane roster pane (read-only, rendering matriarch's `list_lanes`
  output)
- Active yolo run pane (read-only, rendering `list_runs` +
  `run_status`)
- Event feed pane (live tail of one active yolo run's event log,
  selected from a CLI flag or the first active run)
- Polling refresh only (5 seconds)
- No keybindings beyond `q` quit
- No drawer / detail views
- No review queue pane
- No watchdog / inotify (pure poll)

MVP is deliberately small. If we can render three panes against
real data and nothing crashes, the shape is proven. Estimate:
1-2 days of focused work.

### v1.1: event-driven refresh

- Add `watchdog` file watchers for yolo event logs and matriarch
  mailbox/reports
- Polling fallback preserved for environments where watchdog fails
- Debounce on rapid event bursts (coalesce within 100ms)

### v1.2: review queue pane

- Add the bottom-left pane
- Join flow-state review milestones + yolo cross-pass events
- Surface stale review-spec (clarify-after-review) with a visible
  flag

### v1.3: detail drawers + keybindings

- Enter on a row opens a drawer
- Full keybinding set per the earlier table
- Help overlay via `?`

### v1.4: theme polish, terminal compat

- Theme CSS pass (accent colors, dim for archived, red for blocked)
- Test in tmux on WSL2 (my primary env), plus macOS Terminal,
  iTerm2, Windows Terminal
- 80-col fallback layout (degrade gracefully)

### v2 (future): command palette

- `:` palette with `archive`, `resume`, `cancel`, `yolo start`
- Each palette command shells out to the CLI
- Command output appended to event feed
- Not v1 because the mental model shift (read-only → read-write)
  is large enough to deserve its own iteration

### v2+: drawers for spec-lite / adoption / brainstorm memory

- Lite + adoption panes (once 013 + 015 ship in full)
- Brainstorm memory drawer (most recent brainstorms for the active
  feature)
- Handoff record viewer (most recent handoff for the active
  feature)

### v2+ further out: multi-repo / multi-worktree view

- The TUI currently assumes one repo root. A future version could
  aggregate across multiple orca-instrumented repos, useful if
  you're driving work in two adjacent projects.

---

## Explicit non-goals

- **Not a full IDE.** No file editing, no diff view, no syntax
  highlighting for spec.md. The TUI surfaces state; editing
  artifacts still happens in your real editor.
- **Not a CLI replacement.** Every mutation path stays in the CLI.
  The TUI is a companion pane, not a control panel. (v2 command
  palette is a bounded exception — it shells out to the CLI, not
  reimplements it.)
- **Not for artifact authoring.** You won't write brainstorm.md or
  spec.md in the TUI. Authoring is an editor's job.
- **Not required for any workflow.** Users who prefer the CLI
  keep using the CLI. The TUI is strictly additive.
- **Not a real-time collaboration tool.** No multi-user awareness,
  no "X is editing spec.md" indicators. This is a single-operator
  visibility pane.
- **Not a matriarch graduation gate.** Matriarch can stay
  experimental with or without the TUI; the TUI's purpose is
  awareness, not stability certification.
- **Not a replacement for flow-state.** flow-state stays the
  durable aggregator. The TUI displays its output.
- **Not a replacement for the yolo CLI.** `python -m
  speckit_orca.yolo` remains the driver. The TUI shows its
  results.
- **Not a metrics / analytics dashboard.** No charts, no trends,
  no time-series. The TUI shows *now*, not *over time*.
- **Not a log aggregator.** The event feed is a tail, not a
  searchable log store. If you need to search events, `grep` the
  jsonl file.
- **Not a web UI.** Terminal-first. If a web UI ever happens,
  it's a separate spec that reuses the same data sources.
- **Not cross-cutting into SDD artifacts.** The TUI never parses
  spec.md / plan.md / tasks.md directly; everything routes through
  flow-state. This keeps it SDD-agnostic per the 016 relationship
  above.

---

## Open questions

1. **Library version pin strategy.** Textual is actively developed
   and occasionally ships breaking API changes across minor
   versions. Pin to a range (`textual>=0.50,<1.0`) or pin exactly
   (`textual==0.50.1`)? My lean: range pin for v1, re-evaluate
   after the first upstream minor-version bump reveals real
   breakage. Pure-Python deps get range pins by default in Orca.

2. **watchdog vs. asyncinotify vs. pure-async polling.** watchdog
   is the most portable; asyncinotify is Linux-only but integrates
   more cleanly with asyncio; pure polling is zero-deps. My lean:
   watchdog for v1.1, keep polling as a forever-fallback, skip
   asyncinotify unless a real need emerges.

3. **Should the TUI work without a repo root?** If invoked outside
   a git repo, the TUI could either (a) error immediately with a
   helpful message, (b) enter a "pick a repo" launcher mode, or (c)
   render an empty state with instructions. My lean: (a) for v1
   — erroring cleanly is the most honest behavior. (b) is a v2 nice-
   to-have if multiple users ask for it.

4. **Event feed retention.** The feed auto-scrolls to newest. How
   many lines do we keep in memory before pruning the top? Textual's
   `RichLog` has a `max_lines` param. My lean: 1000 lines by default,
   configurable via a flag. Past that, users should grep the jsonl
   files directly.

5. **Spec-lite and adoption records in the TUI.** For v1, neither
   appears in any pane. For v1.3+, should they get dedicated panes
   or share a pane with full specs? My lean: a tabbed "intake"
   pane in v2 that shows all three registries (full specs,
   spec-lite, adoption) in tabs. v1 stays full-spec-only.

6. **Multi-feature scope.** The TUI renders all lanes and all
   active yolo runs in the repo by default. Should there be a
   "focus on current feature" mode driven by the CWD? My lean:
   no default scoping — show everything. Add `--feature <id>` as
   an opt-in filter flag.

7. **Theming / color-blind accessibility.** Textual supports CSS-
   like themes. My lean: ship one default theme (dark-accented
   with clear state colors), document a `--theme` flag for
   future custom themes, commit to a color-blind-safe default
   palette (avoid red/green as the sole state distinguisher; use
   shape / text prefixes too).

8. **TUI in CI / tests.** Textual's `App.run_test()` harness runs
   headless, which is good. Should the full TUI be part of the
   smoke-test suite, or is unit-testing panes in isolation enough?
   My lean: unit tests per pane + one end-to-end run_test() smoke
   that mounts the app against a fixture repo and asserts the
   header renders. Not a full interactive test matrix.

9. **Interaction with `speckit-orca --doctor`.** The doctor
   command reports environment diagnostics. Should it include
   TUI-specific checks (textual importable, watchdog importable,
   terminal supports 256 colors)? My lean: yes, as a small
   additive block in doctor's output. Post-v1.

10. **tmux and WSL2 caveats.** I work primarily in tmux on WSL2.
    Textual generally works, but there are known rendering issues
    with certain tmux versions and some WSL terminal emulators.
    My lean: document the "known good" terminal list in the
    README; ship an `--ascii-only` flag as an escape hatch for
    terminals with poor unicode / color support.

11. **Does the TUI become an Orca extension or stay core?**
    Orca's extension model (capability packs, integrations) could
    technically host the TUI as an extension. My lean: core.
    The TUI is not a cross-cutting workflow concern; it's a direct
    consumer of core modules. Making it an extension adds
    packaging complexity without benefit.

12. **yolo.py event-log file-handle pressure.** Watching one jsonl
    file per active run means O(N) file handles. With a dozen
    concurrent runs that's fine; with a hundred it's a problem.
    My lean: not a v1 concern (we don't have 100 concurrent runs).
    If it becomes a concern, add a shared "yolo multiplexer" that
    tails one combined stream.

13. **What happens when matriarch is absent?** If the repo hasn't
    adopted matriarch (no `.specify/orca/matriarch/` directory),
    the lane pane renders empty. Clean degradation. Same for the
    yolo pane if no runs exist. The review pane degrades the same
    way — it reads per-feature, works fine without matriarch.
    Decision: the TUI handles "feature absent" per-pane; no global
    bail-out.

14. **Refresh interval tunability.** Default 5s for flow-state
    polling, event-driven for jsonl tails. Should the 5s default
    be configurable via a flag (`--flow-refresh 2`)? My lean:
    yes, as a low-risk flag. Document it but don't surface it
    prominently.

15. **Does the TUI respect `--minimal` install mode?** Users who
    install Orca with `--minimal` (no companion extensions) still
    get the TUI, because it's core. They don't get companion
    integrations (which wouldn't affect the TUI's panes anyway).
    Decision: TUI is always present, regardless of install mode.

---

## Suggested next steps

1. Accept or revise this brainstorm. Answer open questions 1-10 as
   part of the plan. (11-15 are lower-risk and can be decided
   during implementation.)
2. Write `specs/018-orca-tui/plan.md` covering the Textual
   architecture, watcher design, pane-to-data-source contract, and
   the MVP-to-v1.4 sequencing as acceptance-gated phases. Include
   a dependency table: which existing modules the TUI imports,
   which it invokes via subprocess, which it never touches.
3. Write `specs/018-orca-tui/data-model.md` specifying the in-
   memory shape each pane holds (LaneRow, YoloRunRow, ReviewRow,
   EventFeedLine) and the adaptation from the source Python types
   (`summarize_lane` output, `RunState`, `FlowMilestone`). Make the
   adaptation pure functions so they're unit-testable without a
   terminal.
4. Write `specs/018-orca-tui/contracts/`:
   - `pane-data-sources.md` — which files each pane watches, what
     triggers a re-render, what the fallback is if the source is
     missing.
   - `refresh-model.md` — event-driven vs. polled boundaries,
     debounce rules, reconcile sweep interval.
   - `subprocess-invocation.md` — (for v2) the exact CLI
     commands the command palette shells out to, and how their
     results surface.
5. Pick the initial theme color palette and commit it as
   `theme.css` in the same PR as the Textual app skeleton. Small
   decision, but blocks reviewability otherwise.
6. Implement the MVP (three panes, polling only, `q` to quit) as
   a single focused PR. Land it. Get feedback.
7. Iterate through v1.1–v1.4 as separate PRs, each with a narrow
   scope (one pane's worth of functionality or one refresh-model
   change per PR).
8. Revisit the 016 multi-SDD relationship after 016 lands. The
   TUI shouldn't need changes if 016 does its job, but a sanity
   pass is worthwhile.
9. When matriarch's drift-flag / live-tmux refinements ship,
   add them as columns / indicators in the lane pane.
10. Defer the command palette (v2) until after at least two weeks
    of v1.x usage — the palette's shape depends on which CLI
    commands end up being the ones operators actually want to run
    from the pane.
