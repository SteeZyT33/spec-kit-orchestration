# Orca Phase 1: Repo Rename + Kill-List Strip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `spec-kit-orca` package to `orca`, strip kill-list code (yolo, matriarch, spec_lite, adoption, onboard, evolve, capability_packs), update surviving code that depended on stripped modules, migrate state path `.specify/orca/` → `.orca/`, and move slash commands to `plugins/claude-code/commands/` with `orca:*` namespace. Tests pass at every milestone.

**Architecture:** Strip first, rename second, restructure third. Strip phase removes dead modules and updates surviving code (TUI drawer, ProjectionSnapshot, flow_state) so the rename phase operates on a smaller clean codebase. Rename phase is mostly mechanical (`git mv` + sed) with test verification. Restructure phase moves slash commands and migrates state path conventions.

**Tech Stack:** Python 3.10+, pytest, hatchling build backend, bash, git.

**Spec:** `docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md`

**Phase 1 of 5.** Phases 2-5 (capability cores + CLI, plugin formats, perf-lab integration shim, test hardening) get separate plans after this lands.

---

## File Structure Changes

### Files to delete

```
src/speckit_orca/yolo.py
src/speckit_orca/matriarch.py
src/speckit_orca/spec_lite.py
src/speckit_orca/adoption.py
src/speckit_orca/onboard.py
src/speckit_orca/evolve.py
src/speckit_orca/capability_packs.py
commands/yolo.md
commands/matriarch.md
commands/spec-lite.md
commands/adopt.md
commands/assign.md
scripts/bash/orca-matriarch.sh
tests/test_yolo.py
tests/test_yolo_supervised.py
tests/test_matriarch.py
tests/test_matriarch_gates.py
tests/test_spec_lite.py
tests/test_adoption.py
tests/test_onboard.py
tests/test_evolve.py
tests/test_capability_packs.py
tests/test_flow_state_yolo.py
tests/test_flow_state_spec_lite.py
tests/test_flow_state_adoption.py
tests/test_tui_matriarch_smoke.py
templates/capability-packs.example.json
```

### Files to modify (strip dependencies on kill-list modules)

```
src/speckit_orca/tui/drawer.py        # remove yolo / matriarch drawer functions
src/speckit_orca/tui/panes.py         # drop yolo and matriarch panes (keep review queue + event feed)
src/speckit_orca/tui/app.py           # drop pane wiring for removed panes
src/speckit_orca/tui/watcher.py       # drop matriarch directory watch
src/speckit_orca/tui/collectors.py    # drop yolo / matriarch collectors
src/speckit_orca/core/projection/snapshots.py  # delete file (joins flow-state + matriarch + yolo)
src/speckit_orca/flow_state.py        # remove list_yolo_runs_for_feature
src/speckit_orca/sdd_adapter/registry.py  # update docstrings
extension.yml                          # remove kill-list commands, update remaining names
```

### Files to rename (directory move + sed)

```
src/speckit_orca/  →  src/orca/
pyproject.toml: name = "spec-kit-orca" → "orca"
pyproject.toml: package paths speckit_orca → orca
pyproject.toml: script speckit-orca → orca
speckit-orca (CLI shim file) → orca
```

### Files to move

```
commands/brainstorm.md    →  plugins/claude-code/commands/brainstorm.md
commands/review-spec.md   →  plugins/claude-code/commands/review-spec.md
commands/review-code.md   →  plugins/claude-code/commands/review-code.md
commands/review-pr.md     →  plugins/claude-code/commands/review-pr.md
commands/tui.md           →  plugins/claude-code/commands/tui.md
```

### State path migration

```
.specify/orca/  →  .orca/   (in code references, scripts, docs)
```

---

## Task 1: Pre-flight Verification

**Files:** none (verification only)

- [ ] **Step 1: Verify clean working tree**

```bash
git status --short
```

Expected: empty output (or only the untracked files we know about: `.a5c/`, `.codex`, `tmp_process_source.js`, `docs/superpowers/`).

If unexpected modifications exist, stop and resolve before proceeding.

- [ ] **Step 2: Verify all tests pass on current main**

```bash
uv run python -m pytest tests/ -x --tb=short 2>&1 | tail -30
```

Expected: all tests pass. If failures exist, document them as pre-existing and confirm they're unrelated to kill-list code before continuing.

- [ ] **Step 3: Snapshot the test count**

```bash
uv run python -m pytest tests/ --collect-only -q 2>&1 | tail -5
```

Record the test count. We'll compare at the end (it should drop by the number of stripped tests, not by anything else).

- [ ] **Step 4: Create a phase-1 working branch**

```bash
git checkout -b orca-phase-1-rename-strip
```

---

## Task 2: Strip yolo Module

**Files:**
- Delete: `src/speckit_orca/yolo.py`
- Delete: `commands/yolo.md`
- Delete: `tests/test_yolo.py`, `tests/test_yolo_supervised.py`, `tests/test_flow_state_yolo.py`
- Modify: `src/speckit_orca/flow_state.py` (remove `list_yolo_runs_for_feature` and related code)
- Modify: `src/speckit_orca/tui/drawer.py` (remove `build_yolo_drawer`, `_yolo_event_tail`)
- Modify: `src/speckit_orca/tui/collectors.py` (remove yolo collector)
- Modify: `src/speckit_orca/tui/panes.py` (remove yolo pane class)
- Modify: `src/speckit_orca/tui/app.py` (remove yolo pane wiring)

- [ ] **Step 1: Identify all yolo references in surviving code**

```bash
grep -rn "yolo\|Yolo\|YOLO" src/speckit_orca/ --include="*.py" \
  | grep -v "^src/speckit_orca/yolo\.py:" \
  | grep -v "^src/speckit_orca/core/projection/snapshots\.py:" \
  > /tmp/yolo-refs-before.txt
cat /tmp/yolo-refs-before.txt
```

Expected: references in `flow_state.py`, `tui/drawer.py`, `tui/panes.py`, `tui/collectors.py`, `tui/app.py`, possibly `tui/watcher.py`. The projection snapshots file is deleted in Task 6.

- [ ] **Step 2: Delete yolo source and test files**

```bash
git rm src/speckit_orca/yolo.py
git rm tests/test_yolo.py tests/test_yolo_supervised.py tests/test_flow_state_yolo.py
git rm commands/yolo.md
```

- [ ] **Step 3: Remove `list_yolo_runs_for_feature` from flow_state.py**

```bash
grep -n "list_yolo_runs_for_feature\|yolo" src/speckit_orca/flow_state.py
```

For each match, inspect and remove the function definition and any callers within `flow_state.py`. The function and its callers form a self-contained yolo-awareness slice. Use Edit to remove the function definition block and any imports / calls within `flow_state.py` that no longer have a target.

- [ ] **Step 4: Remove yolo functions from tui/drawer.py**

Use Edit to delete:
- `build_yolo_drawer` function
- `_yolo_event_tail` function
- Any imports of `speckit_orca.yolo` or references to `YoloRow`

```bash
grep -n "yolo\|Yolo" src/speckit_orca/tui/drawer.py
```

After edits this should return zero matches.

- [ ] **Step 5: Remove yolo collector from tui/collectors.py**

```bash
grep -n "yolo\|Yolo" src/speckit_orca/tui/collectors.py
```

Use Edit to remove the yolo collector function and any imports. Reference the spec at `specs/018-orca-tui/spec.md` for which collectors exist; the yolo collector is the one that calls `yolo.list_runs` per FR-005.

- [ ] **Step 6: Remove yolo pane from tui/panes.py and tui/app.py**

T2 reduces the TUI from 4 panes to 3 (lane + review queue + event feed); yolo is removed here, lane is removed in T3, ending Phase 1 at 2 panes. Adjust grid layout accordingly (e.g., `1 3` vertical stack as an interim).

Use Edit to:
- Remove the yolo pane class from `panes.py`
- Remove yolo pane instantiation and wiring from `app.py`

```bash
grep -n "yolo\|Yolo" src/speckit_orca/tui/panes.py src/speckit_orca/tui/app.py
```

After edits this should return zero matches.

- [ ] **Step 7: Run tests to verify yolo strip is consistent**

```bash
uv run python -m pytest tests/ -x --tb=short --ignore=tests/test_projection_snapshots.py --ignore=tests/test_sub_phase_d_total.py 2>&1 | tail -20
```

We ignore `test_projection_snapshots.py` and `test_sub_phase_d_total.py` because they exercise the ProjectionSnapshot module which is deleted in Task 7. Other tests should pass.

If TUI tests fail (`test_tui.py`, `test_tui_v11.py`), fix them by removing yolo-related assertions.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: strip yolo module and dependencies

Removes yolo CLI runner (1432 lines) and surviving-code dependencies:
- src/speckit_orca/yolo.py
- commands/yolo.md
- tests/test_yolo.py, test_yolo_supervised.py, test_flow_state_yolo.py
- list_yolo_runs_for_feature from flow_state.py
- build_yolo_drawer, _yolo_event_tail from tui/drawer.py
- yolo collector and pane from TUI

TUI now shows 2 panes (review queue, event feed) instead of 4.
Lane pane removed in matriarch strip; yolo pane removed here."
```

---

## Task 3: Strip matriarch Module

**Files:**
- Delete: `src/speckit_orca/matriarch.py`
- Delete: `commands/matriarch.md`
- Delete: `scripts/bash/orca-matriarch.sh`
- Delete: `tests/test_matriarch.py`, `tests/test_matriarch_gates.py`, `tests/test_tui_matriarch_smoke.py`
- Modify: `src/speckit_orca/tui/drawer.py` (remove `build_lane_drawer`)
- Modify: `src/speckit_orca/tui/collectors.py` (remove lane collector)
- Modify: `src/speckit_orca/tui/panes.py` (remove lane pane class)
- Modify: `src/speckit_orca/tui/app.py` (remove lane pane wiring)
- Modify: `src/speckit_orca/tui/watcher.py` (drop matriarch dir watch)
- Modify: `src/speckit_orca/sdd_adapter/registry.py` (update docstrings)

- [ ] **Step 1: Delete matriarch source, scripts, and tests**

```bash
git rm src/speckit_orca/matriarch.py
git rm scripts/bash/orca-matriarch.sh
git rm commands/matriarch.md
git rm tests/test_matriarch.py tests/test_matriarch_gates.py tests/test_tui_matriarch_smoke.py
```

- [ ] **Step 2: Remove lane functions from tui/drawer.py**

Use Edit to delete:
- `build_lane_drawer` function
- Any imports of `speckit_orca.matriarch` or `MatriarchError`
- `matriarch_sync_failed` field rendering in any remaining drawer functions

```bash
grep -n "matriarch\|Matriarch\|lane" src/speckit_orca/tui/drawer.py
```

After edits this should return zero matches.

- [ ] **Step 3: Remove lane collector from tui/collectors.py**

```bash
grep -n "matriarch\|Matriarch\|lane\|list_lanes" src/speckit_orca/tui/collectors.py
```

Use Edit to remove the lane collector function (calls `matriarch.list_lanes` per FR-004) and any imports.

- [ ] **Step 4: Remove lane pane from tui/panes.py and tui/app.py**

Use Edit to:
- Remove lane pane class from `panes.py`
- Remove lane pane instantiation and wiring from `app.py`

```bash
grep -n "matriarch\|lane" src/speckit_orca/tui/panes.py src/speckit_orca/tui/app.py
```

After edits this should return zero matches.

- [ ] **Step 5: Update tui/watcher.py to drop matriarch directory watch**

```bash
grep -n "matriarch\|\.specify/orca/matriarch" src/speckit_orca/tui/watcher.py
```

Use Edit to remove the matriarch directory from watched paths and from any comment that lists watched directories.

- [ ] **Step 6: Update sdd_adapter/registry.py docstrings**

```bash
grep -n "yolo\|matriarch" src/speckit_orca/sdd_adapter/registry.py
```

Use Edit to update docstrings — replace `"yolo, matriarch"` examples with `"flow_state, completion_gate"` or similar surviving callers. These are documentation-only; no behavior change.

- [ ] **Step 7: Run tests to verify matriarch strip is consistent**

```bash
uv run python -m pytest tests/ -x --tb=short --ignore=tests/test_projection_snapshots.py --ignore=tests/test_sub_phase_d_total.py 2>&1 | tail -20
```

Fix any remaining TUI test failures by removing matriarch-related assertions (`test_tui.py`, `test_tui_v11.py`).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: strip matriarch module and dependencies

Removes matriarch supervisor and surviving-code dependencies:
- src/speckit_orca/matriarch.py
- scripts/bash/orca-matriarch.sh
- commands/matriarch.md
- tests/test_matriarch.py, test_matriarch_gates.py, test_tui_matriarch_smoke.py
- build_lane_drawer from tui/drawer.py
- lane collector and pane from TUI
- matriarch directory from tui/watcher.py
- yolo/matriarch references from sdd_adapter/registry.py docstrings"
```

---

## Task 4: Strip spec_lite Module

**Files:**
- Delete: `src/speckit_orca/spec_lite.py`
- Delete: `commands/spec-lite.md`
- Delete: `tests/test_spec_lite.py`, `tests/test_flow_state_spec_lite.py`
- Modify: `src/speckit_orca/flow_state.py` (remove spec-lite awareness if any)

- [ ] **Step 1: Identify spec_lite references in surviving code**

```bash
grep -rn "spec_lite\|SpecLite\|spec-lite" src/speckit_orca/ --include="*.py" \
  | grep -v "^src/speckit_orca/spec_lite\.py:"
```

- [ ] **Step 2: Delete spec_lite source and tests**

```bash
git rm src/speckit_orca/spec_lite.py
git rm commands/spec-lite.md
git rm tests/test_spec_lite.py tests/test_flow_state_spec_lite.py
```

- [ ] **Step 3: Remove spec_lite references from flow_state.py and any other surviving code**

For each file with a remaining reference, use Edit to remove the reference. Spec-lite was a "lightweight intake" feature; flow_state may have rendered SL-* records as a feature kind. Remove that handling.

```bash
grep -rn "spec_lite\|SpecLite\|spec-lite\|SL-" src/speckit_orca/ --include="*.py"
```

After edits this should return zero matches in source code (test fixtures and historic specs may still mention it).

- [ ] **Step 4: Run tests**

```bash
uv run python -m pytest tests/ -x --tb=short --ignore=tests/test_projection_snapshots.py --ignore=tests/test_sub_phase_d_total.py 2>&1 | tail -20
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: strip spec_lite module

Removes spec-lite lightweight intake feature:
- src/speckit_orca/spec_lite.py
- commands/spec-lite.md
- tests/test_spec_lite.py, test_flow_state_spec_lite.py
- spec-lite awareness from flow_state.py"
```

---

## Task 5: Strip adoption / onboard / evolve / capability_packs

**Files:**
- Delete: `src/speckit_orca/adoption.py`, `onboard.py`, `evolve.py`, `capability_packs.py`
- Delete: `commands/adopt.md`, `commands/assign.md`
- Delete: `tests/test_adoption.py`, `test_onboard.py`, `test_evolve.py`, `test_capability_packs.py`, `test_flow_state_adoption.py`
- Delete: `templates/capability-packs.example.json`
- Modify: `src/speckit_orca/flow_state.py` (remove adoption awareness if any)

- [ ] **Step 1: Identify references in surviving code**

```bash
grep -rn "adoption\|Adoption\|adopt\|onboard\|evolve\|capability_pack\|CapabilityPack\|AR-" \
  src/speckit_orca/ --include="*.py" \
  | grep -v "^src/speckit_orca/\(adoption\|onboard\|evolve\|capability_packs\)\.py:"
```

- [ ] **Step 2: Delete source files**

```bash
git rm src/speckit_orca/adoption.py
git rm src/speckit_orca/onboard.py
git rm src/speckit_orca/evolve.py
git rm src/speckit_orca/capability_packs.py
git rm commands/adopt.md commands/assign.md
git rm templates/capability-packs.example.json
git rm tests/test_adoption.py tests/test_onboard.py tests/test_evolve.py tests/test_capability_packs.py
git rm tests/test_flow_state_adoption.py
```

- [ ] **Step 3: Remove references from flow_state.py and other surviving code**

```bash
grep -rn "adoption\|adopt\|onboard\|evolve\|capability_pack\|AR-" src/speckit_orca/ --include="*.py"
```

For each match, use Edit to remove. Adoption was the "brownfield intake" feature with AR-* records; flow_state may have a feature-kind dispatch that handles them. Remove it.

After edits this should return zero matches in source.

- [ ] **Step 4: Remove pyproject.toml capability_packs reference**

```bash
grep -n "capability-packs" pyproject.toml
```

Use Edit to remove the `templates/capability-packs.example.json` entry from `[tool.hatch.build.targets.sdist.force-include]` and `[tool.hatch.build.targets.wheel.force-include]`.

- [ ] **Step 5: Run tests**

```bash
uv run python -m pytest tests/ -x --tb=short --ignore=tests/test_projection_snapshots.py --ignore=tests/test_sub_phase_d_total.py 2>&1 | tail -20
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: strip adoption, onboard, evolve, capability_packs

Removes brownfield intake, onboarding, evolution, and capability-pack
features that did not earn keep against actual use:
- src/speckit_orca/adoption.py, onboard.py, evolve.py, capability_packs.py
- commands/adopt.md, assign.md
- templates/capability-packs.example.json
- corresponding tests
- pyproject.toml capability_packs build references
- adoption/AR-* awareness from flow_state.py"
```

---

## Task 6: Delete ProjectionSnapshot Module

**Files:**
- Delete: `src/speckit_orca/core/projection/snapshots.py`
- Delete: `tests/test_projection_snapshots.py`, `tests/test_sub_phase_d_total.py`
- Modify: `src/speckit_orca/core/projection/__init__.py` (if it exposes ProjectionSnapshot)

ProjectionSnapshot joined flow-state + matriarch + yolo runs. With matriarch and yolo stripped, it has no purpose.

- [ ] **Step 1: Inspect what depends on ProjectionSnapshot**

```bash
grep -rn "ProjectionSnapshot\|core.projection\|projection.snapshots" src/speckit_orca/ tests/ --include="*.py"
```

Expected: only the snapshots.py file itself, the two test files, and possibly an `__init__.py` that re-exports. Nothing else should depend on it (it's recent — commit 35a216c).

- [ ] **Step 2: Delete files**

```bash
git rm src/speckit_orca/core/projection/snapshots.py
git rm tests/test_projection_snapshots.py tests/test_sub_phase_d_total.py
```

- [ ] **Step 3: Update core/projection/__init__.py**

```bash
cat src/speckit_orca/core/projection/__init__.py
```

If it re-exports anything from `snapshots.py`, use Edit to remove those exports. If it only contains `from .snapshots import ProjectionSnapshot`, the file becomes empty — leave a comment placeholder so the package remains valid:

```python
"""Projection module. Currently empty; reserved for future projections."""
```

If the directory becomes pointless (only an empty __init__.py), keep it for now — it'll be cleaned up in Phase 2 if not used.

- [ ] **Step 4: Run full test suite (no more --ignore flags needed)**

```bash
uv run python -m pytest tests/ -x --tb=short 2>&1 | tail -20
```

Expected: all remaining tests pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: delete ProjectionSnapshot module

ProjectionSnapshot joined flow-state + matriarch lane + yolo runs.
With matriarch and yolo stripped, it has no purpose.

- src/speckit_orca/core/projection/snapshots.py
- tests/test_projection_snapshots.py
- tests/test_sub_phase_d_total.py"
```

---

## Task 7: Verify Strip is Clean

**Files:** none (verification only)

- [ ] **Step 1: Confirm zero kill-list references in source**

```bash
grep -rn "speckit_orca\.\(yolo\|matriarch\|spec_lite\|adoption\|onboard\|evolve\|capability_packs\)" \
  src/speckit_orca/ --include="*.py" 2>&1
```

Expected: no matches.

- [ ] **Step 2: Confirm zero kill-list test files**

```bash
ls tests/test_{yolo,matriarch,spec_lite,adoption,onboard,evolve,capability_packs,flow_state_yolo,flow_state_spec_lite,flow_state_adoption,tui_matriarch_smoke,projection_snapshots,sub_phase_d_total}* 2>&1
```

Expected: `ls: cannot access ... No such file or directory` for all.

- [ ] **Step 3: Run full test suite**

```bash
uv run python -m pytest tests/ --tb=short 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 4: Run lint / type check if configured**

```bash
ls Makefile 2>/dev/null && make lint 2>&1 | tail -20 || echo "no Makefile lint target"
```

If a lint target exists, run it. Fix any errors introduced by stripping (typically unused imports).

---

## Task 8: Rename Python Package (Directory + pyproject)

**Files:**
- Modify: `pyproject.toml` (package name, paths, script name, force-includes)
- Move: `src/speckit_orca/` → `src/orca/` (entire directory)
- Move: `speckit-orca` (executable shim) → `orca`

- [ ] **Step 1: Inspect pyproject.toml current state**

```bash
cat pyproject.toml
```

Note all references to `speckit_orca` and `speckit-orca`.

- [ ] **Step 2: Move the source directory**

```bash
git mv src/speckit_orca src/orca
```

- [ ] **Step 3: Move the CLI shim file**

```bash
git mv speckit-orca orca
```

- [ ] **Step 4: Update pyproject.toml**

Use Edit to make the following changes:

1. `name = "spec-kit-orca"` → `name = "orca"`
2. `description = "Installer and updater for Spec Kit Orca orchestration extensions"` → `description = "Cross-agent review and SDD-aware quality gates"`
3. `speckit-orca = "speckit_orca.cli:main"` → `orca = "orca.cli:main"`
4. `packages = ["src/speckit_orca"]` → `packages = ["src/orca"]`
5. In `[tool.hatch.build.targets.sdist.force-include]`:
   - `"src/speckit_orca/assets/speckit-orca.sh"` → `"src/orca/assets/orca.sh"` (note: file rename happens in step 6)
   - `"src/speckit_orca/assets/speckit-orca-main.sh"` → `"src/orca/assets/orca-main.sh"`
   - `"speckit-orca"` → `"orca"`
6. In `[tool.hatch.build.targets.wheel.force-include]`:
   - `"src/speckit_orca/assets/speckit-orca.sh" = "speckit_orca/assets/speckit-orca.sh"` → `"src/orca/assets/orca.sh" = "orca/assets/orca.sh"`
   - same for `speckit-orca-main.sh`

- [ ] **Step 5: Rename asset shell scripts**

```bash
git mv src/orca/assets/speckit-orca.sh src/orca/assets/orca.sh
git mv src/orca/assets/speckit-orca-main.sh src/orca/assets/orca-main.sh
```

- [ ] **Step 6: Update all internal Python imports**

```bash
grep -rln "speckit_orca" src/orca/ tests/ --include="*.py" | wc -l
```

Note the count for verification.

```bash
grep -rln "speckit_orca" src/orca/ tests/ --include="*.py" \
  | xargs sed -i 's/speckit_orca/orca/g'
```

Verify:

```bash
grep -rn "speckit_orca" src/orca/ tests/ --include="*.py" 2>&1 | head -10
```

Expected: no matches.

- [ ] **Step 7: Update bash scripts that invoke the module**

```bash
grep -rln "speckit_orca\|speckit-orca" scripts/ --include="*.sh" --include="*.py"
```

For each match, use Edit (not sed — these scripts are smaller and want individual review) to update:
- `python -m speckit_orca.X` → `python -m orca.X`
- `speckit_orca` references in CLI argument parsing or path resolution → `orca`

- [ ] **Step 8: Update internal asset shell scripts**

```bash
grep -n "speckit_orca\|speckit-orca" src/orca/assets/*.sh
```

Use Edit to update references inside the asset shell scripts to use `orca` paths and module names.

- [ ] **Step 9: Update Makefile if it references the old name**

```bash
grep -n "speckit_orca\|speckit-orca" Makefile 2>/dev/null
```

Use Edit to update.

- [ ] **Step 10: Reinstall the package in dev mode**

```bash
uv sync 2>&1 | tail -10
```

Expected: clean install. The package now installs as `orca`, not `spec-kit-orca`.

- [ ] **Step 11: Run full test suite**

```bash
uv run python -m pytest tests/ -x --tb=short 2>&1 | tail -20
```

Expected: all tests pass with the new module name.

- [ ] **Step 12: Verify CLI entry point works**

```bash
uv run orca --help 2>&1 | head -10
```

Expected: orca CLI help text displays. If the entry point script `speckit-orca` is referenced anywhere as a binary, also verify the renamed `orca` binary works.

- [ ] **Step 13: Commit**

```bash
git add -A
git commit -m "feat: rename package speckit_orca → orca

Atomic rename:
- pyproject.toml: name = \"spec-kit-orca\" → \"orca\"
- src/speckit_orca/ → src/orca/
- src/orca/assets/speckit-orca*.sh → src/orca/assets/orca*.sh
- speckit-orca CLI shim → orca
- Python imports updated via sed
- bash scripts and Makefile updated to invoke orca module
- Project script entry: orca = \"orca.cli:main\"

Also unblocks the CodeQL rename-cache failure on PRs #62/#63/#64
(pyproject name = \"spec-kit-orca\" collided with renamed repo)."
```

---

## Task 9: Migrate State Path .specify/orca/ → .orca/

**Files:**
- Modify: any file under `src/orca/`, `scripts/`, `commands/` that references `.specify/orca/`

- [ ] **Step 1: Find all references**

```bash
grep -rln "\.specify/orca" src/orca/ scripts/ commands/ --include="*.py" --include="*.md" --include="*.sh" 2>/dev/null
```

Expected: a list of files. Per pre-flight check, ~20 files.

- [ ] **Step 2: Bulk rewrite via sed**

```bash
grep -rln "\.specify/orca" src/orca/ scripts/ commands/ --include="*.py" --include="*.md" --include="*.sh" \
  | xargs sed -i 's|\.specify/orca|.orca|g'
```

- [ ] **Step 3: Verify**

```bash
grep -rn "\.specify/orca" src/orca/ scripts/ commands/ --include="*.py" --include="*.md" --include="*.sh" 2>&1 | head -10
```

Expected: no matches.

- [ ] **Step 4: Update tests that wrote to or read from `.specify/orca/`**

```bash
grep -rln "\.specify/orca\|specify_orca_dir\|orca_state_dir" tests/ --include="*.py"
```

For each match, use Edit to update path conventions to `.orca/`. Tests likely have helper functions or fixtures that build the state directory path; update them.

- [ ] **Step 5: Run full test suite**

```bash
uv run python -m pytest tests/ -x --tb=short 2>&1 | tail -20
```

Expected: all tests pass with new state path.

- [ ] **Step 6: Update README.md and MIGRATION.md if they reference the old path**

```bash
grep -n "\.specify/orca" README.md MIGRATION.md CHANGELOG.md 2>/dev/null
```

For each match, use Edit to update — but preserve historical references in CHANGELOG (those describe what was true at the time).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: migrate state path .specify/orca/ → .orca/

Per the orca-as-control-plane reframing (commit ac82b49) and the
state-namespace docs commit (2b1763e), code now writes to .orca/
instead of .specify/orca/.

- Source code path references updated via sed
- Tests updated to use new path
- README and MIGRATION.md updated; CHANGELOG preserves history"
```

---

## Task 10: Move Slash Commands to Plugin Structure

**Files:**
- Create: `plugins/claude-code/commands/` (directory)
- Move: `commands/brainstorm.md`, `review-spec.md`, `review-code.md`, `review-pr.md`, `tui.md` → `plugins/claude-code/commands/`
- Delete: `commands/` directory (after move)

- [ ] **Step 1: Create plugin directory structure**

```bash
mkdir -p plugins/claude-code/commands
mkdir -p plugins/claude-code/skills
```

- [ ] **Step 2: Move surviving slash command files**

```bash
git mv commands/brainstorm.md plugins/claude-code/commands/
git mv commands/review-spec.md plugins/claude-code/commands/
git mv commands/review-code.md plugins/claude-code/commands/
git mv commands/review-pr.md plugins/claude-code/commands/
git mv commands/tui.md plugins/claude-code/commands/
```

- [ ] **Step 3: Verify the old commands directory is now empty**

```bash
ls commands/ 2>&1
```

Expected: empty directory (or `ls: cannot access...` if git removed it). If empty, remove it:

```bash
rmdir commands 2>/dev/null || true
```

- [ ] **Step 4: Update slash command file contents to use orca: namespace**

For each of the moved slash command files, the frontmatter or body may reference command names like `speckit.orca.review-code`. These must update to `orca:review-code`.

```bash
grep -n "speckit\.orca\." plugins/claude-code/commands/*.md
```

Use Edit for each match to replace `speckit.orca.` with `orca:` (preserving the rest of the command name). Examples:
- `speckit.orca.review-spec` → `orca:review-spec`
- `speckit.orca.review-code` → `orca:review-code`
- `speckit.orca.brainstorm` → `orca:brainstorm`
- `speckit.orca.tui` → `orca:tui`
- `speckit.orca.review-pr` → `orca:review-pr`

- [ ] **Step 5: Update any internal references in source code to slash command names**

```bash
grep -rn "speckit\.orca\." src/orca/ scripts/ --include="*.py" --include="*.sh" --include="*.md"
```

For each match, replace `speckit.orca.X` with `orca:X` using Edit.

- [ ] **Step 6: Run tests to verify nothing broke**

```bash
uv run python -m pytest tests/ -x --tb=short 2>&1 | tail -20
```

Expected: pass. Slash command name references in tests should already be updated (most tests don't reference command names by string).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: move slash commands to plugins/claude-code/commands/

Moves surviving slash commands (brainstorm, review-spec, review-code,
review-pr, tui) into Claude Code plugin structure and updates the
namespace from speckit.orca.* to orca:*.

- plugins/claude-code/commands/ now holds active slash commands
- plugins/claude-code/skills/ created (empty; populated in Phase 3)
- commands/ removed (was containing only stripped/moved files)
- Internal references updated speckit.orca.X → orca:X"
```

---

## Task 11: Update extension.yml

**Files:**
- Modify: `extension.yml`

The extension.yml currently lists 9 commands; after strip + move, only 5 survive. The extension manifest needs to reflect the new state.

- [ ] **Step 1: Inspect current extension.yml**

```bash
cat extension.yml
```

Note the structure: `extension`, `requires`, `provides.commands`, `provides.config`, `hooks`.

- [ ] **Step 2: Rewrite extension.yml for the new structure**

Use Edit (or Write to fully replace) to produce:

```yaml
schema_version: "1.0"

extension:
  id: "orca"
  name: "Orca — Cross-Agent Review and SDD-Aware Quality Gates"
  version: "2.0.2"
  description: "Cross-agent review broker, SDD completion gates, flow-state projection, and worktree conflict detection. Integrates with spec-kit and openspec; provides personal slash commands and per-host integration shims."
  author: "SteeZyT33"
  repository: "https://github.com/SteeZyT33/orca"
  license: "MIT"
  homepage: "https://github.com/SteeZyT33/orca"

requires:
  speckit_version: ">=0.5.0"

provides:
  commands:
    - name: "orca:brainstorm"
      file: "plugins/claude-code/commands/brainstorm.md"
      description: "Structured pre-spec ideation that captures options, constraints, and recommendation without dropping into implementation."

    - name: "orca:review-spec"
      file: "plugins/claude-code/commands/review-spec.md"
      description: "Cross-agent adversarial review of a clarified spec. Covers cross-spec consistency, feasibility, security, dependencies, and industry patterns."

    - name: "orca:review-code"
      file: "plugins/claude-code/commands/review-code.md"
      description: "Self+cross review per user-story phase. Self-pass by the author, cross-pass by a different agent. Append-only across rounds."

    - name: "orca:review-pr"
      file: "plugins/claude-code/commands/review-pr.md"
      description: "PR comment disposition and process retrospective. Tracks external reviewer comments, records retro note, and final merge verdict."

    - name: "orca:tui"
      file: "plugins/claude-code/commands/tui.md"
      description: "Live awareness pane showing review queue and event feed."

  config:
    - name: "orca-config.yml"
      template: "config-template.yml"
      description: "Review and cross-pass routing configuration"
      required: false

hooks:
  after_implement:
    command: "orca:review-code"
    optional: true
    prompt: "Run post-implementation review-code (self+cross)?"
    description: "Optionally start self+cross review after implementation completes"

  after_review:
    command: "orca:review-pr"
    optional: true
    prompt: "Run review-pr to handle PR comments and retro?"
    description: "Optionally process PR comments and write retro note after review-code completes"

  before_pr:
    command: "coderabbit-review"
    optional: true
    prompt: "Run CodeRabbit local review before opening the PR?"
    description: "Line-level pre-PR review via CodeRabbit CLI."
    invocation: "bash scripts/bash/orca-coderabbit-pre-pr.sh"
```

- [ ] **Step 3: Run tests**

```bash
uv run python -m pytest tests/ -x --tb=short 2>&1 | tail -20
```

Expected: pass. Extension.yml is metadata; no test should fail.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: update extension.yml for orca v1 surface

- Strip yolo, matriarch, spec-lite, adopt, assign command entries
- Rename remaining commands from speckit.orca.* to orca:*
- Update file paths to plugins/claude-code/commands/
- Update extension id, name, description, repository URL
- Update hook command references"
```

---

## Task 12: Update README and Top-Level Docs

**Files:**
- Modify: `README.md`, `MIGRATION.md`, `CHANGELOG.md`, `AGENTS.md`

- [ ] **Step 1: Inventory references in top-level docs**

```bash
grep -n "speckit_orca\|speckit-orca\|speckit\.orca\." README.md MIGRATION.md CHANGELOG.md AGENTS.md 2>/dev/null
```

- [ ] **Step 2: Update README.md**

Use Edit to replace:
- `spec-kit-orca` → `orca` (project name references in narrative)
- `speckit_orca` → `orca` (module name references in code blocks)
- `speckit.orca.*` → `orca:*` (slash command references)
- Update install instructions if they reference the old package name
- Update repository URL if shown
- Update the "What is orca" framing to match the new design (cross-agent review wedge, six capabilities, three audiences) — but keep the README change conservative; deeper rewriting belongs in Phase 5 if needed

If README has a feature list that includes yolo/matriarch/spec-lite/adopt/assign, remove those entries.

- [ ] **Step 3: Append a v2.1.0 section to CHANGELOG.md**

Use Edit to add a new section at the top (preserving prior history):

```markdown
## v2.1.0 (2026-04-26)

### Renamed

- Package `spec-kit-orca` → `orca`
- Python module `speckit_orca` → `orca`
- State path `.specify/orca/` → `.orca/`
- Slash commands `speckit.orca.*` → `orca:*`

### Removed (kill list)

- `yolo` — single-lane execution runner (1432 lines). Did not earn keep against actual use.
- `matriarch` — multi-lane supervisor. Failed in practice as an "AI middle manager."
- `spec-lite` — lightweight intake. Was a loophole around discipline rather than a real lane.
- `adopt` — brownfield intake. Out of scope for the new wedge.
- `assign` — agent assignment. Out of scope.
- `onboard`, `evolve`, `capability_packs` — supporting modules for stripped features.
- `ProjectionSnapshot` — joined flow-state + matriarch + yolo. No purpose without matriarch and yolo.

### Restructured

- Slash commands moved to `plugins/claude-code/commands/`
- TUI reduced from 4 panes to 2 (review queue + event feed); lane and yolo panes removed.

### Pending (Phase 2-5)

- Six v1 capabilities with documented JSON contracts (cross-agent-review, completion-gate, worktree-overlap-check, flow-state-projection, citation-validator, contradiction-detector)
- Codex plugin (AGENTS.md fragments + prompts)
- Codex reviewer backend
- Perf-lab integration shim
- Test coverage hardening per design doc Section 5
```

- [ ] **Step 4: Update MIGRATION.md**

```bash
cat MIGRATION.md
```

Append a section describing the v2.0 → v2.1 rename:

```markdown
## Migrating from v2.0 (spec-kit-orca) to v2.1 (orca)

### Required changes for downstream callers

- Package name: `pip install spec-kit-orca` → `pip install orca`
- Python imports: `from speckit_orca import X` → `from orca import X`
- CLI: `speckit-orca <args>` → `orca <args>` (or `python -m orca.cli <args>`)
- State directory: `.specify/orca/` → `.orca/`
- Slash commands in scripts: `/speckit.orca.review-code` → `/orca:review-code`

### Removed surfaces (no replacement)

- `speckit.orca.yolo`, `.matriarch`, `.spec-lite`, `.adopt`, `.assign` — these commands no longer exist. See CHANGELOG v2.1.0 for removal rationale.
```

- [ ] **Step 5: Update AGENTS.md if it references the old name**

```bash
grep -n "speckit_orca\|speckit-orca\|speckit\.orca\." AGENTS.md 2>/dev/null
```

For each match, use Edit to update.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "docs: update README, CHANGELOG, MIGRATION, AGENTS for orca rename

- README narrative and code blocks reference 'orca' (not spec-kit-orca)
- CHANGELOG v2.1.0 documents rename, kill-list, restructure, and pending phases
- MIGRATION.md adds v2.0 → v2.1 migration steps for downstream callers
- AGENTS.md updated for new module name"
```

---

## Task 13: Final Verification

**Files:** none (verification only)

- [ ] **Step 1: Confirm zero old-name references in production code**

```bash
grep -rn "speckit_orca\|speckit-orca\|speckit\.orca\." \
  src/ tests/ scripts/ plugins/ extension.yml pyproject.toml \
  --include="*.py" --include="*.md" --include="*.sh" --include="*.yml" --include="*.toml" 2>&1 | head -10
```

Expected: no matches. Historical references are acceptable in `specs/` (those are historical specs) and `CHANGELOG.md` (intentional history).

- [ ] **Step 2: Confirm zero kill-list source files**

```bash
ls src/orca/{yolo,matriarch,spec_lite,adoption,onboard,evolve,capability_packs}.py 2>&1
```

Expected: `ls: cannot access ... No such file or directory` for each.

- [ ] **Step 3: Run full test suite**

```bash
uv run python -m pytest tests/ --tb=short 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 4: Compare test count to pre-flight snapshot**

```bash
uv run python -m pytest tests/ --collect-only -q 2>&1 | tail -5
```

Expected: count is `pre-flight count - (number of stripped tests)`. Do the math from Task 1's pre-flight count to verify nothing else dropped silently.

- [ ] **Step 5: Verify the orca CLI works end-to-end**

```bash
uv run orca --help 2>&1 | head -20
```

Expected: orca's CLI help displays and reflects the surviving subcommands (no yolo, matriarch, spec-lite, adopt, assign).

- [ ] **Step 6: Verify the TUI still launches (smoke test)**

```bash
timeout 3 uv run python -m orca.tui --help 2>&1 | head -10
```

Expected: TUI launches help text successfully (or non-error exit on timeout). Manual smoke: actual TUI rendering is verified by `uv run python -m orca.tui` and pressing `q` to quit, but that's manual.

- [ ] **Step 7: Verify the package builds**

```bash
uv build 2>&1 | tail -10
```

Expected: clean wheel + sdist build with the new name `orca-2.1.0` (or whatever version is set).

- [ ] **Step 8: Final commit if anything was missed**

If steps 1-7 surfaced any inconsistencies, fix and commit:

```bash
git status --short
```

If clean, no commit needed.

- [ ] **Step 9: Push the branch and open a PR**

```bash
git push -u origin orca-phase-1-rename-strip
gh pr create --title "orca v1 phase 1: rename + kill-list strip" \
  --body "$(cat <<'EOF'
## Summary
- Renames package `spec-kit-orca` → `orca` (Python module, CLI, state path)
- Strips kill-list code: yolo, matriarch, spec-lite, adopt, assign, onboard, evolve, capability-packs
- Updates surviving code (TUI, ProjectionSnapshot deletion, flow_state) for stripped dependencies
- Moves slash commands to `plugins/claude-code/commands/` with `orca:*` namespace
- Migrates state path `.specify/orca/` → `.orca/`
- Updates README, CHANGELOG, MIGRATION, extension.yml

Phase 1 of 5. Phases 2-5 (capability cores + CLI, plugin formats, perf-lab integration shim, test hardening) follow in separate plans.

Spec: `docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md`
Plan: `docs/superpowers/plans/2026-04-26-orca-phase-1-rename-and-strip.md`

Also unblocks the CodeQL rename-cache failure on PRs #62/#63/#64
(pyproject `name = "spec-kit-orca"` collided with the renamed repo).

## Test plan
- [x] Strip phase: tests pass after each module's strip + dependency cleanup
- [x] Rename phase: full test suite passes after directory move + sed
- [x] State path migration: tests pass with new `.orca/` paths
- [x] Slash command move: extension.yml + command file references updated
- [x] Docs: README, CHANGELOG, MIGRATION, AGENTS reflect new naming
- [x] Final: full test suite, CLI smoke, TUI smoke, package build all pass
EOF
)"
```

---

## Self-Review

After writing this plan, checking against the spec at `docs/superpowers/specs/2026-04-26-orca-toolchest-v1-design.md`:

**Spec coverage (Phase 1 portion):**
- ✓ Repo Migration section item 1 (`pyproject.toml` rename) — Task 8
- ✓ item 2 (`src/speckit_orca/` → `src/orca/`) — Task 8
- ✓ item 3 (state path migration) — Task 9
- ✓ item 4 (CLI invocation rename) — Task 8 (Python imports) + Task 7 step 5 (bash scripts)
- ✓ item 5 (slash command namespace) — Task 10
- ✓ item 6 (kill-list strip — yolo, matriarch, spec_lite, adoption, onboard, evolve, capability_packs, adopt, assign) — Tasks 2-5
- ✓ item 7 (slash commands to `plugins/claude-code/commands/`) — Task 10
- ✓ item 8 (`plugins/claude-code/skills/` directory) — Task 10 step 1 creates empty dir
- ✓ item 9 (`plugins/codex/` with AGENTS.md) — DEFERRED to Phase 3 (see plan note below)
- ✓ item 10 (`integrations/perf_lab/` shim) — DEFERRED to Phase 4
- ✓ item 11 (JSON contracts in `docs/capabilities/`) — DEFERRED to Phase 2
- ✓ "TUI continues to function post-rename" note — Task 2 step 6 + Task 3 step 4 explicitly reduce TUI to 2 panes; explicit functional verification in Task 13 step 6

**Items not covered by Phase 1 plan (intentionally deferred):**
- Six v1 capabilities (`cross-agent-review`, `completion-gate`, `worktree-overlap-check`, `flow-state-projection`, `citation-validator`, `contradiction-detector`) — Phase 2 plan
- Plugin format implementation (skill files, codex AGENTS.md fragments) — Phase 3 plan
- Perf-lab integration shim — Phase 4 plan
- Test coverage hardening (VCR, JSON schema CI) — Phase 5 plan

**Placeholder scan:** No "TBD" or vague steps. All steps include exact commands or precise instructions. Edits use Edit-tool semantics with exact paths.

**Type / name consistency:** Slash command namespace is `orca:` consistently across Tasks 10, 11, and 12. Module name is `orca` consistently. State path is `.orca/` consistently.

**Honest scope estimate for Phase 1:** ~3-5 days of focused work. The plan is intentionally granular because rename/strip work is mostly mechanical but has many failure modes (forgotten import, wrong sed pattern, leftover reference in a doc). The granularity protects against silent regressions.

---

## Open Questions for User Confirmation Before Execution

1. **Migration commit boundaries.** I structured this as ~12 commits (one per task). Some teams prefer fewer, larger commits. Push back if you want me to consolidate.

2. **Branch strategy.** Plan assumes a `orca-phase-1-rename-strip` feature branch off `main`. The current branch `019-openspec-adapter` has the design doc commit on it; we should rebase the design doc onto `main` first or branch from current HEAD. Confirm preference.

3. **Tests that may need rewriting (not just deletion).** `tests/test_cross_pass_routing.py`, `tests/test_openspec_adapter.py`, `tests/test_sdd_adapter.py`, `tests/test_stub_adapter.py`, `tests/test_flow_state_anti_leak.py` reference matriarch / yolo per the pre-flight grep. The plan assumes they still pass after the strip (matriarch / yolo references are likely incidental, not load-bearing). If they fail, sub-tasks may be needed to remove specific assertions. Confirm I should handle inline during execution rather than splitting into separate tasks.
