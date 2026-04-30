# Orca: `resolve-path` CLI + Slash Command Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `orca-cli resolve-path` subcommand and refactor 5 slash commands to use it; closes the Spec 015 gap where the `host_layout` adapter is built but unused at runtime.

**Architecture:** New CLI subcommand reads `.orca/adoption.toml` via `from_manifest` OR runs `host_layout.detect()` if no manifest. Returns resolved path(s) on stdout. Slash commands replace hardcoded `specs/<id>/` with `$(orca-cli resolve-path --kind feature-dir --feature-id "$ID")`. Detection fallback preserves in-tree orca behavior.

**Tech Stack:** Python 3.10+, existing orca CLI patterns (`_register`, `_emit_envelope`, argparse), pytest.

**Source spec:** `docs/superpowers/specs/2026-04-29-orca-resolve-path-slash-command-refactor-design.md` (commit `6528a4c`).

**Test runner:** `uv run python -m pytest`.

**Baseline:** 527 tests passing on `e1e7be4`.

---

## File Structure

### New files

- `src/orca/core/host_layout/reference_set.py` — auto-discovery of feature-dir SDD artifacts (extracted from cite.md bash)
- `tests/core/host_layout/test_reference_set.py` — discovery tests
- `tests/cli/test_resolve_path_cli.py` — CLI smoke + per-kind tests
- `tests/cli/test_slash_commands_call_resolve_path.py` — bash-grep regression test

### Modified files

- `src/orca/python_cli.py` — add `_run_resolve_path` handler + `_register("resolve-path", ...)` call
- `plugins/claude-code/commands/review-spec.md` — bash-block refactor
- `plugins/claude-code/commands/review-code.md` — bash-block refactor
- `plugins/claude-code/commands/review-pr.md` — bash-block refactor
- `plugins/claude-code/commands/gate.md` — bash-block refactor
- `plugins/claude-code/commands/cite.md` — bash-block refactor + reference-set delegation
- `plugins/codex/AGENTS.md` — add `resolve-path` row to Utility Subcommands table

---

## Task 1: Reference-set auto-discovery module

**Files:**
- Create: `src/orca/core/host_layout/reference_set.py`
- Test: `tests/core/host_layout/test_reference_set.py`

The reference-set discovery currently lives in `cite.md` bash. Extract to a single Python function so `resolve-path --kind reference-set` can return the same list.

- [ ] **Step 1.1: Write failing tests**

Create `tests/core/host_layout/test_reference_set.py`:

```python
"""Reference-set auto-discovery for citation-validator default --reference-set."""
from __future__ import annotations

from pathlib import Path

from orca.core.host_layout.reference_set import discover


def test_discover_finds_canonical_artifacts(tmp_path: Path) -> None:
    fd = tmp_path / "001-feature"
    fd.mkdir()
    for name in ("plan.md", "data-model.md", "research.md", "quickstart.md", "tasks.md"):
        (fd / name).write_text("# stub\n")
    paths = discover(fd)
    assert sorted(p.name for p in paths) == sorted([
        "data-model.md", "plan.md", "quickstart.md", "research.md", "tasks.md",
    ])


def test_discover_skips_missing_artifacts(tmp_path: Path) -> None:
    fd = tmp_path / "001-feature"
    fd.mkdir()
    (fd / "plan.md").write_text("# stub\n")
    paths = discover(fd)
    assert [p.name for p in paths] == ["plan.md"]


def test_discover_includes_contracts(tmp_path: Path) -> None:
    fd = tmp_path / "001-feature"
    (fd / "contracts").mkdir(parents=True)
    (fd / "plan.md").write_text("# p\n")
    (fd / "contracts" / "api.md").write_text("# c\n")
    (fd / "contracts" / "events.md").write_text("# e\n")
    paths = discover(fd)
    names = [p.name for p in paths]
    assert "plan.md" in names
    assert "api.md" in names
    assert "events.md" in names


def test_discover_returns_absolute_paths(tmp_path: Path) -> None:
    fd = tmp_path / "001-feature"
    fd.mkdir()
    (fd / "plan.md").write_text("# p\n")
    paths = discover(fd)
    assert all(p.is_absolute() for p in paths)


def test_discover_empty_when_feature_dir_missing(tmp_path: Path) -> None:
    paths = discover(tmp_path / "nonexistent")
    assert paths == []


def test_discover_canonical_order(tmp_path: Path) -> None:
    """Canonical artifacts come before contracts, in a stable order."""
    fd = tmp_path / "001-feature"
    (fd / "contracts").mkdir(parents=True)
    for name in ("tasks.md", "plan.md", "data-model.md"):
        (fd / name).write_text("# s\n")
    (fd / "contracts" / "z.md").write_text("# z\n")
    (fd / "contracts" / "a.md").write_text("# a\n")

    paths = discover(fd)
    # Canonical order: plan, data-model, research, quickstart, tasks (existing first)
    # Then contracts/ in sorted order
    names = [p.name for p in paths]
    canonical = [n for n in ("plan.md", "data-model.md", "research.md", "quickstart.md", "tasks.md") if n in names]
    contract_names = sorted(["a.md", "z.md"])

    assert names[:len(canonical)] == canonical
    assert names[len(canonical):] == contract_names
```

- [ ] **Step 1.2: Run; verify FAIL** (`ImportError: orca.core.host_layout.reference_set`)

```bash
uv run python -m pytest tests/core/host_layout/test_reference_set.py -v
```

- [ ] **Step 1.3: Implement reference_set.py**

Create `src/orca/core/host_layout/reference_set.py`:

```python
"""Auto-discovery of canonical SDD artifacts under a feature directory.

Replaces the `cite.md` bash loop that hardcoded the same logic.
Returns absolute paths in canonical order: plan.md, data-model.md,
research.md, quickstart.md, tasks.md, then contracts/**/*.md (sorted).
"""
from __future__ import annotations

from pathlib import Path

CANONICAL_ARTIFACTS: tuple[str, ...] = (
    "plan.md",
    "data-model.md",
    "research.md",
    "quickstart.md",
    "tasks.md",
)


def discover(feature_dir: Path) -> list[Path]:
    """Return absolute paths of existing SDD artifacts under feature_dir.

    Order: canonical artifacts first (in CANONICAL_ARTIFACTS order, only
    those that exist), then contracts/**/*.md sorted alphabetically by
    relative path. Empty list if feature_dir doesn't exist.
    """
    if not feature_dir.is_dir():
        return []

    feature_dir = feature_dir.resolve()
    paths: list[Path] = []

    for name in CANONICAL_ARTIFACTS:
        candidate = feature_dir / name
        if candidate.is_file():
            paths.append(candidate)

    contracts_dir = feature_dir / "contracts"
    if contracts_dir.is_dir():
        contracts = sorted(
            p.resolve()
            for p in contracts_dir.rglob("*.md")
            if p.is_file()
        )
        paths.extend(contracts)

    return paths
```

- [ ] **Step 1.4: Run; verify PASS**

```bash
uv run python -m pytest tests/core/host_layout/test_reference_set.py -v
```

Expected: 6 passed.

- [ ] **Step 1.5: Commit**

```bash
git add src/orca/core/host_layout/reference_set.py tests/core/host_layout/test_reference_set.py
git commit -m "feat(host_layout): reference-set auto-discovery module"
```

---

## Task 2: `orca-cli resolve-path` CLI subcommand

**Files:**
- Modify: `src/orca/python_cli.py` (add `_run_resolve_path` + register)
- Test: `tests/cli/test_resolve_path_cli.py`

This is the load-bearing task. ~80 LOC of CLI handler + 12-15 tests.

- [ ] **Step 2.1: Write failing tests**

Create `tests/cli/test_resolve_path_cli.py`:

```python
"""orca-cli resolve-path: per-kind dispatch + manifest/detection fallback."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from orca.python_cli import main as cli_main


def _write_manifest(repo: Path, system: str = "superpowers") -> None:
    pattern_map = {
        "spec-kit": "specs/{feature_id}",
        "openspec": "openspec/changes/{feature_id}",
        "superpowers": "docs/superpowers/specs/{feature_id}",
        "bare": "docs/orca-specs/{feature_id}",
    }
    (repo / ".orca").mkdir(parents=True, exist_ok=True)
    (repo / ".orca" / "adoption.toml").write_text(textwrap.dedent(f"""
        schema_version = 1
        [host]
        system = "{system}"
        feature_dir_pattern = "{pattern_map[system]}"
        agents_md_path = "AGENTS.md"
        review_artifact_dir = "x"
        [orca]
        state_dir = ".orca"
        installed_capabilities = []
        [slash_commands]
        namespace = "orca"
        enabled = []
        disabled = []
        [claude_md]
        policy = "section"
        [constitution]
        policy = "respect-existing"
        [reversal]
        backup_dir = ".orca/adoption-backup"
    """))


def test_resolve_feature_dir_via_manifest(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_manifest(tmp_path, system="superpowers")
    rc = cli_main(["resolve-path", "--kind", "feature-dir",
                    "--feature-id", "001-x"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.endswith("docs/superpowers/specs/001-x")
    assert Path(out).is_absolute()


def test_resolve_feature_dir_via_detection_no_manifest(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "openspec" / "changes").mkdir(parents=True)
    rc = cli_main(["resolve-path", "--kind", "feature-dir",
                    "--feature-id", "add-x"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.endswith("openspec/changes/add-x")


def test_resolve_feature_dir_bare_fallback(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "feature-dir",
                    "--feature-id", "001-x"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.endswith("docs/orca-specs/001-x")


def test_resolve_constitution_present(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "constitution.md").write_text("# c\n")
    rc = cli_main(["resolve-path", "--kind", "constitution"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.endswith("docs/superpowers/constitution.md")


def test_resolve_constitution_absent_returns_empty(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "openspec" / "changes").mkdir(parents=True)
    rc = cli_main(["resolve-path", "--kind", "constitution"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out == "" or out == "\n"


def test_resolve_agents_md(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "agents-md"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.endswith("AGENTS.md")


def test_resolve_reviews_dir(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    rc = cli_main(["resolve-path", "--kind", "reviews-dir"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.endswith("docs/superpowers/reviews")


def test_resolve_reference_set(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fd = tmp_path / "docs" / "superpowers" / "specs" / "001-x"
    fd.mkdir(parents=True)
    (fd / "plan.md").write_text("# p\n")
    (fd / "tasks.md").write_text("# t\n")
    rc = cli_main(["resolve-path", "--kind", "reference-set",
                    "--feature-id", "001-x"])
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.strip()]
    assert rc == 0
    assert len(lines) == 2
    assert any(l.endswith("plan.md") for l in lines)
    assert any(l.endswith("tasks.md") for l in lines)


def test_resolve_path_invalid_kind(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "bogus"])
    assert rc == 2  # argv parse error


def test_resolve_feature_dir_missing_feature_id(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "feature-dir"])
    assert rc == 1
    out = capsys.readouterr().out
    import json
    env = json.loads(out)
    assert env["ok"] is False
    assert env["error"]["kind"] == "input_invalid"


def test_resolve_constitution_rejects_feature_id(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "constitution",
                    "--feature-id", "x"])
    assert rc == 1


def test_resolve_feature_id_with_dotdot_rejected(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "feature-dir",
                    "--feature-id", ".."])
    assert rc == 1


def test_resolve_feature_id_with_slash_rejected(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["resolve-path", "--kind", "feature-dir",
                    "--feature-id", "../etc/passwd"])
    assert rc == 1
```

- [ ] **Step 2.2: Run; verify FAIL** (resolve-path not registered yet)

```bash
uv run python -m pytest tests/cli/test_resolve_path_cli.py -v
```

Expected: most tests fail with `unknown capability: resolve-path` or similar.

- [ ] **Step 2.3: Implement `_run_resolve_path` handler in `python_cli.py`**

Open `src/orca/python_cli.py`. Near the other capability handlers (`_run_cross_agent_review`, `_run_contradiction_detector`, etc.), add:

```python
def _run_resolve_path(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="orca-cli resolve-path",
        exit_on_error=False,
    )
    parser.add_argument("--kind", required=True,
                        choices=["feature-dir", "constitution", "agents-md",
                                 "reviews-dir", "reference-set"])
    parser.add_argument("--feature-id", default=None)
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--pretty", action="store_true")

    try:
        ns, unknown = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        if isinstance(exc, SystemExit) and exc.code == 0:
            return 0
        return 2

    if unknown:
        return 2

    repo_root = Path(ns.repo_root).resolve() if ns.repo_root else Path.cwd().resolve()

    # Validate flag combinations
    requires_feature_id = ns.kind in ("feature-dir", "reference-set")
    if requires_feature_id and not ns.feature_id:
        return _emit_envelope(
            envelope=_err_envelope(
                "resolve-path", "1.0.0",
                ErrorKind.INPUT_INVALID,
                f"--feature-id is required when --kind={ns.kind}",
            ),
            pretty=ns.pretty,
            exit_code=1,
        )
    if not requires_feature_id and ns.feature_id is not None:
        return _emit_envelope(
            envelope=_err_envelope(
                "resolve-path", "1.0.0",
                ErrorKind.INPUT_INVALID,
                f"--feature-id not accepted when --kind={ns.kind}",
            ),
            pretty=ns.pretty,
            exit_code=1,
        )

    # Validate feature_id against path-safety contract Class D
    if ns.feature_id is not None:
        err = _validate_feature_id(ns.feature_id)
        if err is not None:
            return _emit_envelope(
                envelope=_err_envelope(
                    "resolve-path", "1.0.0",
                    ErrorKind.INPUT_INVALID, err,
                ),
                pretty=ns.pretty,
                exit_code=1,
            )

    # Pick adapter: manifest-driven OR detection-driven
    from orca.core.adoption.manifest import ManifestError
    from orca.core.host_layout import detect, from_manifest
    try:
        layout = from_manifest(repo_root)
    except (FileNotFoundError, ManifestError):
        layout = detect(repo_root)

    # Dispatch
    paths: list[Path] = []
    if ns.kind == "feature-dir":
        paths = [layout.resolve_feature_dir(ns.feature_id)]
    elif ns.kind == "constitution":
        cp = layout.constitution_path()
        if cp is not None:
            paths = [cp]
    elif ns.kind == "agents-md":
        paths = [layout.agents_md_path()]
    elif ns.kind == "reviews-dir":
        paths = [layout.review_artifact_dir()]
    elif ns.kind == "reference-set":
        from orca.core.host_layout.reference_set import discover
        feature_dir = layout.resolve_feature_dir(ns.feature_id)
        paths = discover(feature_dir)

    if ns.pretty:
        adapter_name = type(layout).__name__
        print(f"kind: {ns.kind}")
        print(f"adapter: {adapter_name}")
        for p in paths:
            print(p)
    else:
        for p in paths:
            print(p)

    return 0


_FEATURE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_feature_id(value: str) -> str | None:
    """Per path-safety contract Class D. Returns error message or None."""
    if not value:
        return "--feature-id is empty"
    if value in (".", ".."):
        return f"--feature-id={value!r} not allowed"
    if value.startswith("-"):
        return f"--feature-id={value!r} cannot start with '-'"
    if len(value) > 128:
        return "--feature-id exceeds 128 chars"
    if not _FEATURE_ID_RE.match(value):
        return f"--feature-id={value!r} must match [A-Za-z0-9._-]+"
    return None
```

(If `re` isn't already imported at top of file, add it.)

Then near the bottom where other `_register` calls live, add:

```python
_register("resolve-path", _run_resolve_path, "1.0.0")
```

- [ ] **Step 2.4: Update `plugins/codex/AGENTS.md`**

The doc-drift guard test (`tests/cli/test_codex_agents_md.py::test_codex_agents_md_lists_every_capability`) requires every `CAPABILITIES` entry appears in `plugins/codex/AGENTS.md`. Find the Utility Subcommands table; add a row:

```markdown
| `resolve-path` | Resolve host-aware paths (feature-dir, constitution, agents-md, reviews-dir, reference-set) per `.orca/adoption.toml` or detection fallback. |
```

- [ ] **Step 2.5: Run all tests; verify PASS**

```bash
uv run python -m pytest tests/cli/test_resolve_path_cli.py -v
```

Expected: 13 passed.

```bash
uv run python -m pytest -q
```

Expected: 527 baseline + 6 (Task 1) + 13 (Task 2) = 546 passing.

- [ ] **Step 2.6: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_resolve_path_cli.py plugins/codex/AGENTS.md
git commit -m "feat(cli): orca-cli resolve-path host-aware path resolution"
```

---

## Task 3: Refactor `review-spec.md`

**Files:**
- Modify: `plugins/claude-code/commands/review-spec.md`

The command currently says "Resolve `<feature-dir>` from user input or current branch (e.g., `specs/001-foo/`)." Replace with `orca-cli resolve-path` invocation.

- [ ] **Step 3.1: Identify the bash block to update**

Read `plugins/claude-code/commands/review-spec.md` and find the section that resolves `<feature-dir>`. It's currently a numbered list item like:

> 1. Resolve `<feature-dir>` from user input or current branch (e.g., `specs/001-foo/`).
> 2. Resolve `<feature-id>` (basename of feature dir, e.g., `001-foo`).

- [ ] **Step 3.2: Replace with explicit `orca-cli resolve-path` invocation**

Edit the section to:

```markdown
1. Resolve `<feature-id>` from user input or current branch.
   - If user passed `--feature <id>`, use that.
   - Else infer from branch name (e.g., `001-foo` from branch `001-foo`).
2. Resolve `<feature-dir>` via host-aware adapter:

   ```bash
   FEATURE_DIR="$(orca-cli resolve-path --kind feature-dir --feature-id "$FEATURE_ID")"
   ```

   This honors `.orca/adoption.toml` if present; otherwise auto-detects
   the host's spec system (spec-kit, openspec, superpowers, or bare).
   For host repos that haven't run `orca-cli adopt`, this still works.
```

- [ ] **Step 3.3: Commit**

```bash
git add plugins/claude-code/commands/review-spec.md
git commit -m "refactor(review-spec): use orca-cli resolve-path for feature-dir"
```

---

## Task 4: Refactor `review-code.md` and `review-pr.md`

**Files:**
- Modify: `plugins/claude-code/commands/review-code.md`
- Modify: `plugins/claude-code/commands/review-pr.md`

Both currently use `{SCRIPT}` to set `$FEATURE_DIR`. After: `{SCRIPT}` returns `feature_id`; bash resolves `$FEATURE_DIR` via `resolve-path`.

- [ ] **Step 4.1: Update review-code.md**

Find the section in `review-code.md` that says "Run `{SCRIPT}` from repo root and parse `FEATURE_DIR` and `AVAILABLE_DOCS`." Replace with:

```markdown
1. Run `{SCRIPT}` from repo root to obtain `FEATURE_ID` (and optionally
   `AVAILABLE_DOCS`). The script's job is only to identify the feature;
   path resolution happens in step 2.
2. Resolve `<feature-dir>` via host-aware adapter:

   ```bash
   FEATURE_DIR="$(orca-cli resolve-path --kind feature-dir --feature-id "$FEATURE_ID")"
   ```
```

(Preserve the rest of the workflow that uses `$FEATURE_DIR`.)

- [ ] **Step 4.2: Update review-pr.md**

Same pattern. Find the `{SCRIPT}` line and add the `resolve-path` invocation immediately after.

- [ ] **Step 4.3: Commit**

```bash
git add plugins/claude-code/commands/review-code.md plugins/claude-code/commands/review-pr.md
git commit -m "refactor(review-code,review-pr): use orca-cli resolve-path"
```

---

## Task 5: Refactor `gate.md`

**Files:**
- Modify: `plugins/claude-code/commands/gate.md`

- [ ] **Step 5.1: Update gate.md**

Find the bash block that sets `FEATURE_DIR` from user input or current branch. Replace the resolution with `orca-cli resolve-path`:

```markdown
1. Resolve `<feature-id>` from user input or current branch.
2. Resolve `<feature-dir>`:

   ```bash
   FEATURE_DIR="$(orca-cli resolve-path --kind feature-dir --feature-id "$FEATURE_ID")"
   ```
3. (Existing gate.md flow continues using $FEATURE_DIR)
```

- [ ] **Step 5.2: Commit**

```bash
git add plugins/claude-code/commands/gate.md
git commit -m "refactor(gate): use orca-cli resolve-path for feature-dir"
```

---

## Task 6: Refactor `cite.md`

**Files:**
- Modify: `plugins/claude-code/commands/cite.md`

`cite.md` has TWO things to update: feature-dir resolution, and the auto-discovered reference-set bash loop (which `resolve-path --kind reference-set` now produces).

- [ ] **Step 6.1: Replace the reference-set discovery block**

In `cite.md`, find the bash example showing the `for f in plan.md ...` loop. Replace with:

```markdown
2. Resolve `--reference-set` paths. If the operator passed any
   `--reference-set` flag(s), use those. Otherwise auto-discover via
   `orca-cli resolve-path`:

   ```bash
   REFS=()
   while IFS= read -r ref; do
     [ -n "$ref" ] && REFS+=("--reference-set" "$ref")
   done < <(orca-cli resolve-path --kind reference-set --feature-id "$FEATURE_ID" 2>/dev/null)
   ```

   If `REFS` is empty (no SDD artifacts present), fall back to whatever
   the operator explicitly passes; the capability runs against an empty
   reference set and reports broken refs accordingly.
```

- [ ] **Step 6.2: Add explicit feature-dir resolution**

Earlier in `cite.md` where `$FEATURE_DIR` is implied or assumed, add an explicit resolution step:

```markdown
1a. Resolve `<feature-dir>`:

   ```bash
   FEATURE_DIR="$(orca-cli resolve-path --kind feature-dir --feature-id "$FEATURE_ID")"
   ```
```

- [ ] **Step 6.3: Commit**

```bash
git add plugins/claude-code/commands/cite.md
git commit -m "refactor(cite): use orca-cli resolve-path for refs + feature-dir"
```

---

## Task 7: Slash-command regression test

**Files:**
- Create: `tests/cli/test_slash_commands_call_resolve_path.py`

Bash regression: greps each modified slash command for the `orca-cli resolve-path` invocation pattern. Prevents future drift where someone "fixes" a slash command and quietly drops the host-aware resolution.

- [ ] **Step 7.1: Write tests**

Create `tests/cli/test_slash_commands_call_resolve_path.py`:

```python
"""Regression: slash commands MUST consult orca-cli resolve-path.

These tests grep each refactored command for the canonical invocation
pattern. Drift from `orca-cli resolve-path --kind feature-dir` back to
hardcoded `specs/<id>/` would break adoption for non-spec-kit hosts.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "plugins" / "claude-code" / "commands"

# Commands that resolve --feature-id to a feature-dir
HOST_AWARE_COMMANDS = [
    "review-spec.md",
    "review-code.md",
    "review-pr.md",
    "gate.md",
    "cite.md",
]


@pytest.mark.parametrize("filename", HOST_AWARE_COMMANDS)
def test_command_invokes_resolve_path_feature_dir(filename: str) -> None:
    text = (COMMANDS_DIR / filename).read_text()
    assert "orca-cli resolve-path --kind feature-dir" in text, (
        f"{filename} must call `orca-cli resolve-path --kind feature-dir`"
    )


def test_cite_uses_reference_set_discovery() -> None:
    """cite.md MUST use `--kind reference-set` for auto-discovery (not the
    legacy bash `for f in plan.md...` loop)."""
    text = (COMMANDS_DIR / "cite.md").read_text()
    assert "orca-cli resolve-path --kind reference-set" in text, (
        "cite.md must call orca-cli resolve-path --kind reference-set"
    )
```

- [ ] **Step 7.2: Run; verify PASS** (assuming Tasks 3-6 landed correctly)

```bash
uv run python -m pytest tests/cli/test_slash_commands_call_resolve_path.py -v
```

Expected: 6 passing (5 parametrized + 1 cite-specific).

- [ ] **Step 7.3: Commit**

```bash
git add tests/cli/test_slash_commands_call_resolve_path.py
git commit -m "test: regression guard for slash commands using resolve-path"
```

---

## Task 8: Final verification + push

- [ ] **Step 8.1: Run full suite**

```bash
uv run python -m pytest -q
```

Expected: 527 + ~28 = ~555 passing (6 reference-set + 13 resolve-path CLI + 6 slash-command regression + 3 cushion for any other tests touched).

- [ ] **Step 8.2: Manual smoke test**

```bash
cd /tmp && rm -rf orca-resolve-test && mkdir orca-resolve-test && cd orca-resolve-test
mkdir -p docs/superpowers/specs/001-test
echo "# plan" > docs/superpowers/specs/001-test/plan.md

uv run --project /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats orca-cli resolve-path --kind feature-dir --feature-id 001-test
# Expected: <abs>/docs/superpowers/specs/001-test (via detection)

uv run --project /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats orca-cli resolve-path --kind reference-set --feature-id 001-test
# Expected: <abs>/docs/superpowers/specs/001-test/plan.md
```

- [ ] **Step 8.3: Verify the orca repo dogfood case still works**

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
uv run orca-cli resolve-path --kind feature-dir --feature-id 015-brownfield-adoption
# Expected: <abs>/specs/015-brownfield-adoption (or .../docs/superpowers/specs/...)
# depending on which detection path orca repo lands on
uv run orca-cli resolve-path --pretty --kind agents-md
# Expected: kind: agents-md / adapter: <name> / <path>
```

- [ ] **Step 8.4: Push**

```bash
git push
```

---

## Self-Review Checklist

**1. Spec coverage:**
- `orca-cli resolve-path` CLI subcommand → Task 2 ✓
- 5 supported `--kind` values (feature-dir, constitution, agents-md, reviews-dir, reference-set) → Task 2 ✓
- Detection fallback when no manifest → Task 2 ✓
- Reference-set discovery centralized → Task 1 ✓
- 5 slash command refactors → Tasks 3-6 ✓
- path-safety contract Class D feature_id validation → Task 2 ✓
- Backwards compat (in-tree orca repo) → Task 8 step 8.3 ✓
- Regression guard against drift → Task 7 ✓

**2. No placeholders:** all steps have actual content.

**3. Type consistency:**
- `discover(feature_dir: Path) -> list[Path]` consistent across Tasks 1-2 ✓
- `_run_resolve_path(args: list[str]) -> int` matches `_run_*` pattern in `python_cli.py` ✓
- CLI flag spellings (`--kind`, `--feature-id`, `--repo-root`, `--pretty`) consistent ✓

## Honest Risk Notes

- **Task 2 has the only non-trivial code.** The other tasks are mostly markdown edits. Estimated 60-80 LOC for the handler + 150 LOC of tests. The bulk of the half-day budget.
- **`{SCRIPT}` semantics.** The slash commands invoke a template `{SCRIPT}` which gets substituted by the host harness (Claude Code) to a real script (e.g., `.specify/scripts/bash/setup-review-spec.sh`). This plan refactors the command MARKDOWN; whatever script gets substituted should still output `feature_id` somewhere parseable. If the existing scripts ONLY output a feature_dir (already-resolved), Task 4's "{SCRIPT} returns feature_id" framing may need adjustment — the implementer can keep the script's output and just re-parse to extract feature_id (basename of feature_dir).
- **`re` import in python_cli.py.** Step 2.3 assumes `re` is already imported. If not, add `import re` at the top.
- **Codex AGENTS.md update.** Step 2.4 is required for the doc-drift test to pass; Spec 015 hit the same gotcha during Task 13.
- **Subject lines under 72 chars.** Commitlint enforces. All suggested subjects in this plan are well under the limit.
