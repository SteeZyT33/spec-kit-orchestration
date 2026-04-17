# Feature Specification: 018 TUI v1.1 — Drawers and Theming

**Feature Branch**: `018-tui-v1.1`
**Created**: 2026-04-16
**Status**: Draft
**Input**: Parent spec `specs/018-orca-tui/spec.md` (v1 MVP shipped: 4-pane
read-only Textual TUI). Brainstorm §"Sequencing" called out v1.3 as
"detail drawers + keybindings" and v1.4 as "theme polish". v1.1 bundles
those two increments into one shippable slice while keeping the read-only
invariant intact.

## Context

v1 proved the Textual shape works against real Orca data: four panes, file
watcher with polling fallback, pane isolation on refresh failure, graceful
degradation on corrupt JSONL. The gap v1.1 closes is **drilldown**: today
pressing Enter on a lane row does nothing, so the operator still has to
`cat` a JSON file to see the assignment history, mailbox counts, or
deployment metadata. Similarly the yolo pane shows `run_id/stage/outcome`
but hides the full RunState (retry counts, mailbox path, review sub-states)
and the review pane shows the milestone name but not the artifact content.

v1.1 adds a single generic drawer widget that opens on Enter for the
currently focused pane and closes on Escape or Enter. Drawers are
read-only. They fetch data on open (not proactively) and fail closed with
an informational message if the source data is missing or malformed.

v1.1 also adds richer theming — Textual's built-in theme catalog (dark,
light, monokai, dracula) cycled via `t`. Theme selection persists across
the process lifetime (through file-watcher refreshes and forced `r`
refreshes). The theme list degrades gracefully if a theme is not
registered in the running Textual version (we skip it and log a debug
line rather than crashing).

Command palette stays deferred to v2.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator Drills Into a Lane (Priority: P1)

An operator sees a lane in `blocked` state in the roster pane and wants to
see why without leaving the TUI.

**Why this priority**: This is the drilldown gap the v1 spec explicitly
flagged as the biggest remaining source of CLI/TUI context switching.

**Independent Test**: With the TUI open and a registered lane in the
roster, press `Enter`. A drawer overlay appears showing the full
`summarize_lane` output (lane_id, title, branch, worktree, owner,
dependencies, mailbox counts, delegated tasks, assignment history,
deployment).

**Acceptance Scenarios**:

1. **Given** a lane in the roster with the cursor on it, **When** the
   operator presses `Enter`, **Then** a drawer opens with the lane's
   full detail.
2. **Given** the drawer is open, **When** the operator presses `Escape`,
   **Then** the drawer closes and focus returns to the lane pane.
3. **Given** the drawer is open, **When** the operator presses `Enter`
   again, **Then** the drawer closes (toggle semantics).

---

### User Story 2 - Operator Drills Into a Yolo Run (Priority: P1)

Similar to Story 1 but for the active yolo runs pane.

**Independent Test**: Cursor on a yolo row, press Enter, drawer shows
full RunState fields (mode, lane_id, current_stage, outcome,
block_reason, review_spec_status, review_code_status, review_pr_status,
retry_counts, matriarch_sync_failed, last_event_timestamp) plus the
tail of the run's event log (last 10 entries).

**Acceptance Scenarios**:

1. **Given** a yolo run row with the cursor on it, **When** the operator
   presses `Enter`, **Then** the drawer shows `run_status(run_id)` output
   formatted as key/value pairs plus a tail of the run's events.jsonl.
2. **Given** the run's events.jsonl is corrupt, **When** the drawer
   opens, **Then** the event-tail section shows `(no events)` rather
   than crashing.

---

### User Story 3 - Operator Drills Into a Review Entry (Priority: P2)

**Independent Test**: Cursor on a review row, press Enter, drawer shows
the feature_id, review_type, status, and a preview of the review
artifact content (or an `(artifact missing)` note).

**Acceptance Scenarios**:

1. **Given** a review row with an existing artifact (e.g.
   `review-spec.md`), **When** Enter is pressed, **Then** the drawer
   shows the first 40 lines of the artifact.
2. **Given** the artifact file does not exist, **When** Enter is pressed,
   **Then** the drawer shows `(artifact not yet written)` and does not
   raise.

---

### User Story 4 - Operator Cycles Themes (Priority: P2)

**Independent Test**: Press `t` repeatedly. `app.theme` changes each
press, wrapping back to the start after the final theme.

**Acceptance Scenarios**:

1. **Given** the TUI just mounted with the default theme, **When** `t`
   is pressed, **Then** `app.theme` changes to the next theme in the
   cycle.
2. **Given** a theme cycle has brought the TUI to a non-default theme,
   **When** an auto-refresh fires, **Then** `app.theme` is unchanged.
3. **Given** one of the configured themes is not in
   `app.available_themes`, **When** the TUI mounts, **Then** the missing
   theme is skipped from the cycle list and no error is raised.

---

### Edge Cases

- Event-feed pane has no meaningful "focused row" cursor (it is a
  RichLog tail). Pressing Enter on the event feed pane is a no-op.
- A lane row with `effective_state: error` still opens a drawer showing
  the error placeholder payload; no crash.
- The drawer is keyboard-only in v1.1 — no mouse interactions required.
- If the theme setter raises (e.g. an older Textual build rejects a
  theme name at runtime), the TUI catches the error, logs it, and
  reverts to the previously-applied theme.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-101**: Pressing `Enter` while a pane (lane / yolo / review) is
  focused and has a row under its cursor MUST open a read-only drawer
  showing the full detail for that row.
- **FR-102**: Pressing `Escape` while the drawer is open MUST close the
  drawer and return focus to the originating pane.
- **FR-103**: Pressing `Enter` while the drawer is open MUST close the
  drawer (toggle semantics, same as Escape).
- **FR-104**: The drawer content for a lane row MUST be sourced from
  `matriarch.summarize_lane(lane_id)` and render at minimum: lane_id,
  title, branch, worktree_path, owner_type/owner_id, effective_state,
  status_reason, dependencies, mailbox_counts, delegated_work count,
  assignment_history count, deployment metadata.
- **FR-105**: The drawer content for a yolo row MUST be sourced from
  `yolo.run_status(run_id)` plus a tail of `events.jsonl` (last 10
  entries), and render every RunState field the v1 pane does not
  already show.
- **FR-106**: The drawer content for a review row MUST include
  feature_id, review_type, status, plus a preview (first 40 lines) of
  the review artifact file when present.
- **FR-107**: If the drawer's source data is missing or malformed, the
  drawer MUST render a placeholder message (e.g. `(artifact not yet
  written)`, `(no events)`, `(lane record error: ...)`) rather than
  raise.
- **FR-108**: Pressing `t` MUST cycle the Textual app theme through the
  configured list and persist the selection across auto-refresh and
  manual `r` refresh cycles.
- **FR-109**: The theme cycle list MUST be intersected with
  `app.available_themes` at mount time; unavailable themes are dropped
  from the cycle with a debug log. If no configured themes are
  available, the default theme is kept.
- **FR-110**: The drawer is strictly read-only. No keybinding inside
  the drawer may mutate repo state or trigger a CLI subprocess.
- **FR-111**: Existing v1 keybindings (q, r, 1-4) MUST continue to
  function unchanged. Pressing `Enter` on the event-feed pane is a
  documented no-op.
- **FR-112**: The footer MUST advertise the new bindings: `Enter=drill
  Esc=close t=theme` in addition to the existing hints.

### Key Entities

- **DrawerContent**: a pure-data payload a drawer renders. Shape:
  `title: str`, `body: list[tuple[str, str]]` (label/value pairs),
  `tail: list[str]` (optional trailing lines, e.g. event log tail).
- **DrawerBuilder**: a pure function `(repo_root, row) -> DrawerContent`
  per row type (lane/yolo/review). Builders degrade gracefully: a
  builder that cannot fetch its source data returns a DrawerContent
  whose body includes an `error:` line rather than raising.
- **ThemeCycle**: the list of theme names the `t` keybinding cycles
  through, filtered at mount time against `app.available_themes`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-101**: Pressing Enter on a lane row opens a drawer within one
  event-loop tick (<50ms perceived latency in local testing).
- **SC-102**: Pressing Escape with the drawer open closes it within
  one event-loop tick.
- **SC-103**: The drawer correctly renders all required fields (FR-104
  through FR-106) for representative fixture data in unit tests.
- **SC-104**: Malformed / missing source data never crashes the TUI;
  the drawer always renders a placeholder.
- **SC-105**: `t` cycles `app.theme` across the intersection of the
  configured themes and `app.available_themes`; theme persists across
  refreshes.
- **SC-106**: All 25 existing v1 tests (`tests/test_tui.py`) remain
  green. No functional regression in existing keybindings.
