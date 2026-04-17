# Feature Specification: Orca TUI - Live Awareness Pane

**Feature Branch**: `018-orca-tui`
**Created**: 2026-04-16
**Status**: Draft
**Input**: Brainstorm `specs/018-orca-tui/brainstorm.md` - operator needs a
single always-on terminal surface that joins lane state, yolo runs, pending
reviews, and the live event stream, so multi-lane work stops costing three
separate CLI invocations per glance.

## Context

Orca's durable primitives (flow-state, matriarch, yolo) correctly *store*
state as event logs, JSON registries, and review artifacts. What they do not
do is *surface* it. Today the operator polls three CLI surfaces (flow-state,
`orca-matriarch.sh lane list`, `tail -f` on yolo events.jsonl) to assemble a
mental join of "what is live right now." 018 closes that awareness gap with
a read-only Textual TUI that watches the same files the CLI reads.

Phase 1 scope (this spec) is strictly the MVP: four panes, read-only, file
watching via watchdog with polling fallback, launched via
`python -m speckit_orca.tui`. Command palette, detail drawers, multi-repo
aggregation, and spec-lite / adoption panes are explicitly deferred to v2 and
out of scope here.

The TUI is a projection. It never mutates state. Every row on every pane is
traceable to a file the existing CLI already writes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator Opens TUI While Driving a Lane (Priority: P1)

An operator is actively driving feature 018 in one terminal and wants to see,
without context-switching, what the other lanes and runs are doing.

**Why this priority**: This is the single gap that justifies the feature.
Without it the TUI is a toy.

**Independent Test**: Run `python -m speckit_orca.tui` against a repo with
at least one registered lane, one active yolo run, and one pending review.
All three appear on the correct panes within 5 seconds of launch.

**Acceptance Scenarios**:

1. **Given** a repo with matriarch lanes registered, **When** the TUI
   launches, **Then** the lane roster pane renders every registered lane with
   its `effective_state`, owner, and blocker reason (if any).
2. **Given** a repo with non-terminal yolo runs, **When** the TUI launches,
   **Then** the active yolo pane renders every run whose `outcome=running`,
   showing `current_stage` and the `matriarch_sync_failed` flag.
3. **Given** a feature whose `review-spec.md` is stale against clarify,
   **When** the TUI launches, **Then** the review queue pane surfaces that
   feature with a `stale` indicator.

---

### User Story 2 - Operator Sees State Change Without Re-Running a CLI Command (Priority: P1)

An operator has the TUI open while a lane agent appends a new event to a yolo
run. The operator expects the TUI to reflect the change without user action.

**Why this priority**: The whole reason to pay a Textual dependency is live
refresh. Snapshot rendering is already done by flow-state.

**Independent Test**: With the TUI open, append a new yolo event to an active
run's `events.jsonl`. The event feed pane shows the new entry within 5
seconds. With watchdog available the latency should be sub-second.

**Acceptance Scenarios**:

1. **Given** watchdog imports successfully, **When** a watched file mutates,
   **Then** the corresponding pane re-renders within one event-loop tick.
2. **Given** watchdog is unavailable, **When** a watched file mutates,
   **Then** the corresponding pane re-renders within the polling interval
   (default 5 seconds) and a "polling mode" indicator is visible in the
   header.

---

### User Story 3 - Operator Quits TUI Cleanly (Priority: P1)

The TUI is a companion, not a replacement. Operators must be able to drop
out quickly.

**Why this priority**: Without a clean quit path the TUI is worse than no
TUI.

**Independent Test**: Press `q`. The process exits with code 0, no leftover
threads, no stuck watchers.

**Acceptance Scenarios**:

1. **Given** the TUI is running, **When** the operator presses `q`, **Then**
   the TUI stops all watchers, releases all file handles, and exits 0.
2. **Given** the TUI is running and a refresh is in flight, **When** `q`
   fires, **Then** the in-flight refresh is canceled (not awaited) before
   exit.

---

### Edge Cases

- Repo has no matriarch directory. Lane pane renders empty with an
  informational row. No crash.
- Repo has no yolo runs. Yolo pane and event feed render empty. No crash.
- `watchdog` cannot be imported. TUI falls back to 5-second polling across
  all panes and displays "polling mode (watchdog unavailable)" in the header.
- Terminal is too narrow (<80 cols). Textual degrades the grid to vertical
  stacking. MVP does not attempt a custom compact layout.
- `flow-state` raises during recomputation for one feature. The TUI logs the
  error into the event feed and leaves the prior row in place rather than
  dropping the pane.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The TUI MUST be invocable via `python -m speckit_orca.tui` from
  a repo root.
- **FR-002**: The TUI MUST accept an optional `--repo-root <path>` flag; if
  omitted it uses the current working directory.
- **FR-003**: The TUI MUST render four panes simultaneously on launch: lane
  roster, active yolo runs, review queue, event feed.
- **FR-004**: The lane roster pane MUST read via `matriarch.list_lanes` and
  render at minimum `lane_id`, `effective_state`, `owner_id`, and
  `status_reason` for every registered lane.
- **FR-005**: The active yolo pane MUST read via `yolo.list_runs` + per-run
  `yolo.run_status` and display only runs whose `outcome` is not in
  {"completed", "canceled", "failed"}. Each row MUST render `run_id`
  (shortened), `feature_id`, `current_stage`, `outcome`, and the
  `matriarch_sync_failed` flag.
- **FR-006**: The review queue pane MUST aggregate, across every feature
  directory under `specs/`, the review milestones from
  `flow_state.compute_flow_state` whose `status` is not `complete` /
  `overall_complete` / `present`. Each row MUST render `feature_id`,
  `review_type`, `status`.
- **FR-007**: The event feed pane MUST tail yolo `events.jsonl` files for
  all runs and matriarch mailbox inbound JSONL files for all lanes, and
  render a unified chronological view of the last 30 entries.
- **FR-008**: Every pane MUST refresh on file mutation when `watchdog` is
  available, and fall back to 5-second polling otherwise.
- **FR-009**: Polling-mode fallback MUST display a visible indicator in the
  header: `polling mode (watchdog unavailable)`.
- **FR-010**: The TUI MUST be read-only in v1. No keybinding, pane, or menu
  MAY mutate repo state.
- **FR-011**: The TUI MUST respond to `q` by stopping watchers, canceling
  in-flight refresh tasks, and exiting with code 0.
- **FR-012**: The TUI MUST respond to `r` by forcing a full recomputation of
  all panes, bypassing any debounce.
- **FR-013**: The TUI MUST respond to `1`, `2`, `3`, `4` by focusing the
  respective pane (lane / yolo / review / event feed).
- **FR-014**: Data collectors MUST be pure functions of repo-root input and
  file contents. No module-level caching of mutable state. This is required
  so they can be unit tested without a terminal.
- **FR-015**: The TUI MUST NOT parse `spec.md`, `plan.md`, `tasks.md`
  directly; it routes all feature reads through `flow_state`.
- **FR-016**: The TUI MUST gracefully handle absent matriarch / yolo
  directories by rendering an empty pane with an informational row, never by
  crashing or aborting startup.
- **FR-017**: Footer MUST display the active keybindings: `q=quit r=refresh
  1-4=focus`.
- **FR-018**: Header MUST display the repo root and git branch (if
  resolvable), plus the polling-mode indicator when applicable.

### Key Entities

- **LanePaneState**: in-memory representation of the lane roster pane. A
  list of `LaneRow(lane_id, effective_state, owner_id, status_reason)`
  tuples, derived pure-functionally from `matriarch.list_lanes` output.
- **YoloPaneState**: in-memory representation of the active yolo pane. A
  list of `YoloRow(run_id, feature_id, current_stage, outcome,
  matriarch_sync_failed)` tuples, derived from `yolo.list_runs` +
  `yolo.run_status`. Terminal runs filtered out.
- **ReviewPaneState**: in-memory representation of the review queue pane. A
  list of `ReviewRow(feature_id, review_type, status)` tuples, derived by
  running `flow_state.compute_flow_state` against each feature directory and
  selecting non-complete review milestones.
- **EventFeedEntry**: a single row in the event feed. Shape:
  `(timestamp, source, summary)` where `source ∈ {"yolo", "matr"}` and
  `summary` is a one-line render of the originating event/message.
- **CollectorResult**: bundled output of one full pane refresh: the four
  pane states plus a `collected_at` timestamp and a `polling_mode` boolean.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Launching the TUI in a repo with representative state (≥1
  lane, ≥1 run, ≥1 pending review) renders all four panes within 2 seconds
  of process start.
- **SC-002**: When watchdog is available, a file mutation on a watched JSONL
  propagates to the event feed within 500ms of the write completing.
- **SC-003**: When watchdog is unavailable, a file mutation propagates within
  the configured polling interval (default 5s).
- **SC-004**: Quitting via `q` releases all watchers and exits with code 0;
  no zombie processes or leftover inotify handles.
- **SC-005**: The TUI starts successfully against a fresh repo with no
  matriarch directory and no yolo runs, rendering each empty pane with an
  informational row.
- **SC-006**: 100% of data collector functions are unit-testable without
  launching Textual. Collectors do not import `textual` or `rich`.
