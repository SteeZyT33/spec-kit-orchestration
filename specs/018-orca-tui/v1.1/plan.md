# Implementation Plan: 018 TUI v1.1

**Branch**: `018-tui-v1.1`
**Spec**: `specs/018-orca-tui/v1.1/spec.md`
**Parent Plan**: `specs/018-orca-tui/plan.md`

## Summary

Add a generic, read-only Textual `ModalScreen`-backed drawer to the v1 TUI
plus a `t` keybinding that cycles through a filtered list of built-in
Textual themes. No new runtime dependencies. All logic sits inside
`speckit_orca.tui` alongside the existing v1 modules.

## Technical Context

- **UI framework**: Textual (already a runtime dep). We use
  `textual.screen.ModalScreen` for the drawer overlay. No new pins.
- **Data sources**: drawers reuse v1 read APIs —
  `matriarch.summarize_lane`, `yolo.run_status`, `yolo.read_events`
  (existing private helper already exercised by `run_status`), and
  direct-read of `review-spec.md` / `review-code.md` / `review-pr.md`
  artifacts. No new files are invented.
- **Themes**: Textual's built-in `App.available_themes` dict exposes a
  name-keyed catalog. `App.theme = "<name>"` applies a theme at
  runtime. Our cycle is a subset: `["textual-dark", "textual-light",
  "monokai", "dracula"]` filtered through `available_themes` at mount.

## Constitution Check

- **Projection not source**: drawers read, never write. PASS.
- **Read-only**: no keybinding inside the drawer triggers a subprocess or
  filesystem mutation. PASS.
- **SDD-agnostic**: drawers do not parse `spec.md` / `plan.md` /
  `tasks.md`. Review-artifact previews are a bounded exception — they
  read `review-*.md` content, but that file IS the review artifact, not
  an SDD artifact mediated by flow_state. Same trade-off flow_state
  itself makes when surfacing review milestones. PASS.
- **Graceful degradation**: every drawer builder catches source-data
  exceptions and returns a placeholder payload. PASS.
- **Zero new runtime deps**: Textual already ships ModalScreen and
  themes. PASS.
- **All 25 existing tests pass**: verified before starting v1.1 work;
  re-verified after each sub-phase.

## Project Structure

```
src/speckit_orca/tui/
  __init__.py          # unchanged
  __main__.py          # unchanged
  app.py               # +theme cycle, +Enter/Escape bindings, +drawer push
  collectors.py        # unchanged (collectors stay pure, v1)
  drawer.py            # NEW — DrawerContent dataclass + builders + ModalScreen
  panes.py             # +LAST_FOCUSED_ROW cache for drawer origin
  watcher.py           # unchanged
tests/
  test_tui.py          # unchanged (v1 tests)
  test_tui_v11.py      # NEW — drawer + theme tests
specs/018-orca-tui/v1.1/
  spec.md              # spec (this PR)
  plan.md              # this file
  tasks.md             # TDD breakdown
```

## Design Decisions

### Drawer as a ModalScreen

A `ModalScreen[None]` subclass named `DetailDrawer` is pushed onto the
app stack when Enter fires on a pane row. The modal screen:

- Accepts a `DrawerContent` payload at construction.
- Renders a bordered panel with the `title`, a two-column `body`
  (label | value), and an optional `tail` section.
- Binds `Escape` and `Enter` to delegate back to the app's `_close_drawer`
  path, which pops the screen and explicitly refocuses the origin pane
  so focus restoration is deterministic rather than relying on Textual's
  implicit focus-restore behavior.

### DrawerContent is pure data

```python
@dataclass(frozen=True)
class DrawerContent:
    title: str
    body: list[tuple[str, str]]   # (label, value)
    tail: list[str] = []          # optional trailing block (e.g. events)
```

Builders are pure functions: `(repo_root, row) -> DrawerContent`. Each
builder wraps its data fetch in `try/except Exception` and degrades to a
placeholder body rather than raising. This mirrors the collector
discipline from v1.

### Enter dispatch

On `Enter`, the app inspects the currently focused pane:

- `#lane-pane` / `#yolo-pane` / `#review-pane`: resolve the cursor row
  index into the pane's last-rendered rows list (panes cache this on
  `update_rows`), build a DrawerContent, push the DetailDrawer screen.
- `#event-pane`: no-op (documented; event feed is a RichLog with no
  selectable rows).
- If no pane is focused or cursor index is out of range: no-op.

This keeps the drawer dispatch a single `action_open_drawer` handler on
the App, not split across pane classes.

### Theme cycle

- `app.theme` is a Textual reactive; assignment triggers a re-style.
- On mount, compute `self._theme_cycle = [t for t in
  CONFIGURED_THEMES if t in self.available_themes]`; if empty, fall
  back to `[self.theme]`.
- `action_cycle_theme` advances an index mod len(cycle) and assigns
  `self.theme = cycle[idx]`. Wrapped in `try/except` so a runtime
  theme-setter failure reverts gracefully.
- Theme is a property of the app instance — it survives pane
  refreshes naturally because refreshes only touch pane contents, not
  App-level theme state.

### Keybinding additions

```python
Binding("enter", "open_drawer", "drill", show=True, priority=True)
Binding("t", "cycle_theme", "theme", show=True)
```

Existing bindings (`q`, `r`, `1`-`4`) stay at the head of the list.
Escape is NOT an app-level binding; the DetailDrawer ModalScreen owns
it directly and its handler delegates to `app._close_drawer()` so the
origin pane gets explicitly refocused. Enter is declared `priority`
so it beats `DataTable.select_cursor` at the pane level.

## Verification Strategy

- Unit tests for each drawer builder (pure functions, no Textual).
- Pilot-based tests:
  - Enter on lane row pushes DetailDrawer with expected title.
  - Escape on open drawer pops the screen.
  - Enter with drawer open also pops (toggle).
  - `t` changes `app.theme` across a full cycle, wraps, and is
    unaffected by a subsequent `_do_refresh()` call.
- Graceful-degradation tests:
  - Lane builder handed a malformed row returns a placeholder.
  - Yolo builder with missing events.jsonl returns a placeholder tail.
  - Review builder with missing artifact returns `(artifact not yet
    written)` body line.
- All 25 v1 tests re-run and pass.

## Implementation Sub-Phases

- **Phase A**: Spec + plan + tasks (this PR).
- **Phase B**: `drawer.py` module — DrawerContent dataclass, three
  builders (lane/yolo/review), DetailDrawer ModalScreen. Each with a
  failing test first.
- **Phase C**: Wire Enter dispatch into `app.py`. Pane classes cache
  the last-rendered row list so the app can look up a row by index.
- **Phase D**: Theme cycle keybinding + mount-time filter.
- **Phase E**: Documentation refresh (`commands/tui.md` new or
  `commands/matriarch.md` update).

## Non-Goals (v1.1)

- Command palette (v2).
- Mutation keybindings from the drawer (v2).
- Custom user-supplied theme files (v2+).
- Multi-drawer stacking (only one drawer at a time).
- Keyboard navigation inside the drawer beyond Escape/Enter (no
  scrolling shortcut yet; Textual's default pageup/pagedown still work
  on the body widget).
