# Tasks: 018-orca-tui

**Input**: spec.md, plan.md, brainstorm.md

## Phase A - Skeleton + layout

- [ ] **T001** [Test] RED: `tests/test_tui.py::test_app_imports` - importing
  `speckit_orca.tui.app` raises no exception and exposes `OrcaTUI`.
- [ ] **T002** Create `src/speckit_orca/tui/__init__.py` exporting `main`
  and `OrcaTUI`.
- [ ] **T003** Create `src/speckit_orca/tui/app.py` with a `OrcaTUI(App)`
  subclass containing placeholder panes, 2×2 CSS grid, Header, Footer.
  Keybindings registered: `q` (quit), `r` (refresh), `1`/`2`/`3`/`4`
  (focus).
- [ ] **T004** [Test] GREEN: T001 passes.
- [ ] **T005** [Test] RED: Pilot test mounts the app, asserts header widget
  is present and four pane containers are mounted with IDs `lane-pane`,
  `yolo-pane`, `review-pane`, `event-pane`.
- [ ] **T006** Wire panes into app layout so T005 passes.

## Phase B - Collectors

- [ ] **T010** [Test] RED: `test_collect_lanes_empty` - against a tmp repo
  with no matriarch directory, `collect_lanes` returns empty list, no
  raise.
- [ ] **T011** [Test] RED: `test_collect_lanes_returns_rows` - against a
  tmp repo with one lane registered, returns one `LaneRow` with
  `lane_id`, `effective_state`, `owner_id`, `status_reason`.
- [ ] **T012** Implement `collectors.collect_lanes(repo_root) ->
  list[LaneRow]` in `src/speckit_orca/tui/collectors.py`.
- [ ] **T013** [Test] RED: `test_collect_yolo_runs_filters_terminal` -
  against a repo with one running run and one completed run, returns only
  the running one.
- [ ] **T014** Implement `collectors.collect_yolo_runs(repo_root) ->
  list[YoloRow]`.
- [ ] **T015** [Test] RED: `test_collect_reviews_skips_complete` - a
  feature with complete review-spec does not appear; a feature with
  stale review-spec does.
- [ ] **T016** Implement `collectors.collect_reviews(repo_root) ->
  list[ReviewRow]`.
- [ ] **T017** [Test] RED: `test_collect_event_feed_merges_sources` -
  yolo events + matriarch inbound messages merged, sorted descending by
  timestamp, truncated to 30.
- [ ] **T018** Implement `collectors.collect_event_feed(repo_root) ->
  list[EventFeedEntry]`.
- [ ] **T019** [Test] RED: `test_collect_all_returns_collector_result` -
  top-level `collect_all(repo_root, polling_mode)` returns a
  `CollectorResult` with four pane states plus `collected_at` and
  `polling_mode`.
- [ ] **T020** Implement `collectors.collect_all`.

## Phase C - Watcher with polling fallback

- [ ] **T030** [Test] RED: `test_watcher_falls_back_when_watchdog_missing`
  - with `watchdog` import patched to raise, constructing a `Watcher`
  sets `polling_mode=True` and registers a timer-based fallback.
- [ ] **T031** Implement `src/speckit_orca/tui/watcher.py` with
  `Watcher(paths, on_change, poll_interval)` that prefers watchdog and
  falls back to polling.
- [ ] **T032** [Test] RED: `test_watcher_debounces_rapid_changes` - fast
  successive writes within 100ms coalesce into one `on_change` callback.
- [ ] **T033** Implement debounce logic in `Watcher`.
- [ ] **T034** [Test] RED: `test_watcher_stops_cleanly` - `watcher.stop()`
  releases observers and joins polling threads.
- [ ] **T035** Implement clean-stop semantics.

## Phase D - Event feed live tail

- [ ] **T040** [Test] RED: Pilot test - appending a new line to a yolo
  `events.jsonl` updates the event feed pane within the test pilot's
  timeout.
- [ ] **T041** Wire `Watcher` into `OrcaTUI`, reading `collect_event_feed`
  on change.
- [ ] **T042** [Test] RED: Pilot test - header renders "polling mode" when
  watchdog is unavailable.
- [ ] **T043** Implement header polling-mode indicator.

## Phase E - CLI / entry point

- [ ] **T050** [Test] RED: `test_main_parses_repo_root_flag` - calling
  `tui.main(['--repo-root', str(tmp)])` constructs an app with that root.
- [ ] **T051** Implement `src/speckit_orca/tui/__main__.py` and `main()`
  in `app.py` so `python -m speckit_orca.tui` works.
- [ ] **T052** [Test] RED: `test_main_defaults_to_cwd` - without
  `--repo-root`, `main` uses `Path.cwd()`.
- [ ] **T053** Add `textual>=0.50` and `watchdog>=3.0` to
  `pyproject.toml` dependencies. Regenerate `uv.lock`.

## Verification

- [ ] **T060** `uv run pytest --tb=short` - all tests pass including
  prior suite.
- [ ] **T061** Manual smoke: `python -m speckit_orca.tui` in this repo
  renders four panes and exits cleanly on `q`.
- [ ] **T062** Cross-harness review via codex.

## Parallelization notes

- T001–T009 serial (skeleton order matters).
- T010–T020 collectors are independent per-source. `collect_lanes`,
  `collect_yolo_runs`, `collect_reviews`, `collect_event_feed` can be
  implemented in parallel by separate agents if splitting.
- T030–T035 must follow collectors (watcher triggers collector calls).
- T040–T043 must follow watcher.
- T050–T053 last.
