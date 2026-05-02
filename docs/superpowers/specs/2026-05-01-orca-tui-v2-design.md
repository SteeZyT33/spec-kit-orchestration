# orca TUI v2 — Bug-free Interactive Kanban

**Status:** Approved (brainstormed 2026-05-01)
**Owner:** Taylor
**Predecessors:** PR #84, #86, #87, #88, #90, #89, #91 (TUI v1.2 stack)

## Goal

Take the TUI from "read-only awareness surface" to "an actually usable
operator console for orca." Three concrete deliverables, ordered:

1. **Phase 0 — Bug sweep.** Find and fix every interaction bug in the
   existing v1.2 TUI. Confirmed: navigation keys (down / pagedown) do
   nothing in the review pane. There are likely more.
2. **Phase 1 — Toggleable kanban view.** A second screen showing every
   feature laid out across five lifecycle columns. `b` toggles between
   list view (existing 3-pane) and board view (new). The list view
   stays exactly as it is.
3. **Phase 2 — Worktree actions on cards.** Each kanban card shows its
   associated worktree (if any). Three keybindings act on the focused
   card: `c` close worktree, `o` open shell in worktree dir, `e` open
   `$EDITOR` in worktree dir. All actions confirm before destructive
   execution and shell out to existing CLI commands.

The TUI itself never writes files or rewrites repo state directly.
"Actions" mean the TUI spawns existing CLI subprocesses (e.g.
`orca-cli wt close`) which own all mutation. v1.2's read-only
invariant becomes "TUI process is read-only; CLI subprocesses
spawned from the TUI may mutate."

## Non-Goals

- Replace the v1 list view (it stays).
- Drag-and-drop card movement. Cards are read-only projections of
  filesystem state; advancing a feature means doing the work, not
  moving a card.
- Mark-review-complete or kick-off-review from the TUI. The review
  artifacts are written by `orca-cli review-*`; that stays a CLI-only
  workflow for v2.
- Filter / search / sort. Defer until the kanban proves it isn't
  enough on its own.
- Multi-repo aggregation, command palette, mouse support, persistent
  cursor state. Out of scope.

## Architecture

### Phase 0: Bug sweep

A systematic Pilot-driven test pass that exercises every documented
keybinding, every focus transition, every refresh path. Each bug
observed becomes a fix + a regression test. The deliverable is a
clean run of the existing 69-test suite plus N new tests for each
bug found.

Already known:
- Navigation keys (`down`, `up`, `pageup`, `pagedown`, `home`, `end`)
  do not move cursor or scroll the review-pane DataTable. Confirmed
  via Pilot — after 20 down presses, `cursor_row=0, scroll_y=0.0`.
  Likely cause: the app's `priority=True` Enter binding intercepts
  the DataTable's default key chain, or focus lands on the pane
  Container instead of the inner DataTable.

Likely-but-unconfirmed bugs (to verify in Phase 0):
- Cursor row resets to 0 every refresh (DataTable.clear() drops it).
- Drawer focus restoration races with table refresh.
- Border-title rebuild every refresh causes flicker.
- Watcher-thread refresh during Pilot interaction can produce
  inconsistent reads.

Phase 0 is done when:
- Every keybinding documented in the footer actually works.
- Cursor position survives a refresh.
- No flicker, no race condition under sustained interaction (10s of
  arrow-key presses with watcher firing).

### Phase 1: Toggleable kanban view

#### Screen toggle

Two `Screen` subclasses: `ListScreen` (the current 3-pane layout) and
`BoardScreen` (new). The app starts on `ListScreen`. Pressing `b` toggles: if the active
screen is `BoardScreen`, pop it back to `ListScreen`; otherwise
push `BoardScreen`. The toggle never produces a nested stack — at
most one of each screen exists.

The logo header and footer are shared chrome, mounted at the app
level; both screens compose against them.

#### Board layout

Five horizontal columns (left to right), separated by 1-cell gutter:

```
┌─ Spec ──────┬─ Plan ──────┬─ Tasks ─────┬─ Review ────┬─ Merged ────┐
│ feature-024 │ feature-018 │ feature-023 │ feature-016 │ feature-014 │
│ feature-025 │             │ feature-026 │ feature-017 │ feature-015 │
│             │             │             │             │             │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
```

Each column is independently scrollable. Tab cycles focus between
columns; arrow keys move within a column. Card count appears in the
column border title (`Plan · 3`). Long feature IDs ellipsize.

#### Card content

Each card is a 4-line block:

```
024-foo-bar
  branch: feature-024-foo-bar
  worktree: clean
  reviews: spec missing
```

Lines:
1. Feature ID (truncated if needed, full ID on Enter).
2. Branch name (or `(no worktree)` if none registered).
3. Worktree status (`clean`, `dirty (3 files)`, `behind main by 2`,
   `(no worktree)`). Color-coded same scheme as v1.2.
4. Review summary (most-blocking review for the feature, or `done`
   if all complete).

Cards never grow taller than 4 rows. Anything longer goes into the
drawer that opens on Enter.

#### Lifecycle binning

A new `kanban.py` collector bins each feature directory under
`specs/` into one of the five columns:

- **Spec** — `spec.md` exists, `plan.md` does not.
- **Plan** — `plan.md` exists, `tasks.md` does not.
- **Tasks** — `tasks.md` exists, no review milestones complete.
- **Review** — at least one review milestone non-terminal, at least
  one complete.
- **Merged** — all review milestones complete OR a branch whose name
  starts with `<feature_id>-` (i.e. follows the `001-foo-bar` →
  branch `001-foo-bar` convention) is reachable from `main`.

Implementation reuses `flow_state.compute_flow_state` for review
milestones; Phase 0 / Phase 1 share that abstraction unchanged. The
Merged check needs new logic: if `feature_id` matches a branch name
that's been merged into `main` (per `git branch --merged main`), the
feature lands in Merged regardless of review state.

### Phase 2: Worktree actions on cards

Three keybindings on the focused card:

#### `c` — Close worktree (with confirm)

1. Read worktree-id from card's metadata.
2. Show a modal `"Close worktree <id>? This deletes the worktree
   directory and removes the registration. (y / N)"`.
3. On `y`: shell out to `orca-cli wt close <id>`. Capture stdout +
   stderr, surface in a result modal. On non-zero exit, show stderr
   in red.
4. Trigger refresh.

#### `o` — Open shell

1. Read worktree path from card.
2. Suspend the TUI (Textual's `app.suspend()`).
3. `subprocess.run(["bash"], cwd=worktree_path)`.
4. When the shell exits, resume the TUI and refresh.

If no `$SHELL` environment variable is set, fall back to `bash`.
If `bash` isn't available, show an error modal with the path so the
operator can `cd` themselves.

#### `e` — Open `$EDITOR`

Same flow as `o` but invokes `$EDITOR <worktree_path>` (or `vi` as
fallback).

#### Confirmation pattern

Use a single `ConfirmModal` ModalScreen for all confirm-then-run
actions. Default action is "no" — Enter / N / Esc all cancel; only
`y` confirms. This is consistent with `git rebase --interactive`
muscle memory.

#### Read-only safety net

A new `OrcaTUI.MUTATIONS_ENABLED` class var (default `True`) gates
every action keybind. `--read-only` CLI flag flips it off so the
v1.2 invariant ("TUI never mutates") is recoverable for users who
want it.

## Components

| File | Phase | Responsibility |
|------|-------|----------------|
| `src/orca/tui/screens.py` | 1 | `ListScreen` + `BoardScreen` Screen subclasses; `b` toggle binding |
| `src/orca/tui/kanban.py` | 1 | `KanbanColumn` enum + `bin_feature(repo_root, feature_id) -> KanbanColumn`; `collect_kanban(repo_root) -> dict[KanbanColumn, list[FeatureCard]]` |
| `src/orca/tui/cards.py` | 1 | `FeatureCard` widget (4-line block); `CardData` dataclass with feature_id, branch, worktree_status, review_summary |
| `src/orca/tui/actions.py` | 2 | `close_worktree(...)`, `open_shell(...)`, `open_editor(...)` — pure shell-out helpers, return `(rc, stdout, stderr)` |
| `src/orca/tui/modals.py` | 2 | `ConfirmModal` (yes/no), `ResultModal` (post-action stdout/stderr) |
| `src/orca/tui/app.py` | 0/1/2 | Mount the screens, wire `b` toggle, `--read-only` flag, action keybinds |
| `src/orca/tui/panes.py` | 0 | Bug fixes: focus, cursor preservation, navigation keys |

## Data Flow

```
filesystem (specs/, .orca/, .git/)
    │
    ▼
flow_state.compute_flow_state(feature_dir)  ── existing
    │                                       │
    │                                       ▼
    │                              kanban.bin_feature() ── new
    │                                       │
    ▼                                       ▼
collect_all() ── existing               collect_kanban() ── new
    │                                       │
    ▼                                       ▼
ListScreen panes                         BoardScreen columns
                                            │
                                            ▼
                                        FeatureCard widgets
                                            │
                                            ▼
                                        actions.* on c/o/e
                                            │
                                            ▼
                                        subprocess (orca-cli wt close
                                                    / bash / $EDITOR)
```

## Error Handling

- Every collector wraps per-feature work in try/except so one bad
  feature directory never zeros the whole board.
- Subprocess actions capture stderr and surface it in a modal; they
  never re-raise.
- The toggle screen swap survives an exception during compose by
  popping back to the previous screen.
- Watcher-fired refresh during a modal action is queued, not
  applied, so the modal doesn't close mid-confirm.

## Testing

- **Phase 0 regression suite:** every existing v1.2 test still
  passes (69 tests). Plus N new tests, one per bug found.
- **Phase 1 kanban tests:**
  - `bin_feature` for each of the 5 columns (5 tests, fixture-driven).
  - `collect_kanban` returns exactly the right cards per column for
    a multi-feature fixture.
  - `BoardScreen` mounts; column count = 5; card count matches
    collector output.
  - Toggle test: `b` pressed twice returns to the same screen.
- **Phase 2 action tests:**
  - `close_worktree` calls `orca-cli wt close` with the right ID
    (subprocess mocked).
  - Confirm-modal default-no: pressing Enter cancels.
  - `--read-only` flag suppresses the action keybinds in the footer.
- **End-to-end Pilot smoke:** open TUI against this repo, navigate
  to a card, press `c`, confirm, observe refresh.

Target: 90+ tests green, no warnings, full smoke at 80×24 and
140×44.

## Production-Readiness Bar

The user said "continue on ralph loop until you think it's
production ready." Concrete bar:

1. Phase 0 complete: every footer-listed keybinding works as
   documented; no flicker; cursor survives refresh.
2. Phase 1 complete: board view renders correctly against this repo
   (≥5 features in flight); toggle is instant; columns scroll
   independently.
3. Phase 2 complete: all three actions work end-to-end against a
   real test worktree; confirm modal is reliable; result modal
   surfaces success and failure.
4. All tests green; smoke-rendered at 80×24 and 140×44; no Pyright
   import errors except known venv-visibility noise.
5. Stack is mergeable: each phase is its own commit; the branch
   rebases cleanly on `main` once the v1.2 stack lands.

## Open Questions (for the implementer)

- Where does worktree state come from — `.orca/worktrees/*.json`
  or matriarch registry? Need to read both and pick whichever the
  current `orca-cli wt list` uses.
- Branch-merged check: `git branch --merged main` is per-current-
  branch. Use `git for-each-ref --merged refs/heads/main` instead
  for stability.
- Does `app.suspend()` work cleanly inside `pilot.run_test()`? If
  not, gate `o`/`e` actions with a "are we under test?" check.
