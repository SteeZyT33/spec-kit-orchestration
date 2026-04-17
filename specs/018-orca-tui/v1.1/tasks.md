# Tasks: 018 TUI v1.1 — Drawers and Theming

**Branch**: `018-tui-v1.1`
**Spec**: `specs/018-orca-tui/v1.1/spec.md`
**Plan**: `specs/018-orca-tui/v1.1/plan.md`

## Phase A — Sub-spec scaffolding

- [x] A1. Create `specs/018-orca-tui/v1.1/spec.md`.
- [x] A2. Create `specs/018-orca-tui/v1.1/plan.md`.
- [x] A3. Create `specs/018-orca-tui/v1.1/tasks.md` (this file).

## Phase B — Drawer module (TDD)

- [x] B1. RED: write `test_drawer_content_lane_builds_from_row` against
      a not-yet-existent `speckit_orca.tui.drawer` module.
- [x] B2. RED: `test_drawer_content_lane_degrades_on_missing_lane`.
- [x] B3. RED: `test_drawer_content_yolo_includes_runstate_fields`.
- [x] B4. RED: `test_drawer_content_yolo_degrades_on_read_failure`.
- [x] B5. RED: `test_drawer_content_review_previews_artifact`.
- [x] B6. RED: `test_drawer_content_review_missing_artifact`.
- [x] B7. GREEN: implement `drawer.py` with `DrawerContent` dataclass,
      `build_lane_drawer`, `build_yolo_drawer`,
      `build_review_drawer`, and the `DetailDrawer` ModalScreen.
- [x] B8. All six drawer tests pass plus original 25 still pass.

## Phase C — Enter dispatch wiring

- [x] C1. RED: Pilot test `test_enter_on_lane_pushes_drawer`.
- [x] C2. RED: Pilot test `test_escape_closes_drawer`.
- [x] C3. RED: Pilot test `test_enter_toggles_drawer_closed`.
- [x] C4. RED: Pilot test `test_enter_on_event_pane_is_noop`.
- [x] C5. GREEN: extend panes to cache `_last_rows`; add
      `action_open_drawer` + `action_close_drawer` on the App; add
      `Enter` and `Escape` bindings. Event-pane Enter is a no-op.
- [x] C6. All Pilot tests pass; no regressions.

## Phase D — Theme cycle

- [x] D1. RED: `test_theme_cycle_advances_on_t`.
- [x] D2. RED: `test_theme_cycle_wraps_around`.
- [x] D3. RED: `test_theme_cycle_filters_unavailable`.
- [x] D4. RED: `test_theme_persists_across_refresh`.
- [x] D5. GREEN: implement `action_cycle_theme`, mount-time
      `_theme_cycle` computation, and add the `t` Binding.
- [x] D6. All theme tests pass.

## Phase E — Documentation

- [x] E1. Create `commands/tui.md` (new) documenting v1.1 keybindings
      and drawer semantics.
- [x] E2. Verify no changes needed in `commands/matriarch.md` besides
      a cross-reference if helpful (optional).

## Phase F — Cross-harness review

- [ ] F1. Run codex with the review prompt; address BLOCKERs.
- [ ] F2. Push + open PR with `SKIP_CODERABBIT=1`.
