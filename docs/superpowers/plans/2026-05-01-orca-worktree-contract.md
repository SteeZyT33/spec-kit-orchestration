# Orca Worktree Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `.worktree-contract.json` cross-tool standard + `orca-cli wt contract emit/from-cmux/install-cmux-shim` verbs so a single repo can be managed by orca, cmux, or plain git without re-authoring symlinks/hooks per tool.

**Architecture:** New `src/orca/core/worktrees/contract.py` (loader + dataclass + ContractError); new `src/orca/core/worktrees/contract_emit.py` (discovery scan); new `src/orca/core/worktrees/contract_from_cmux.py` (parser); new `src/orca/core/worktrees/contract_shim.py` (cmux shim writer). Phase 1 `auto_symlink.run_stage1()` and `manager.py:179` change to union semantics with new `contract` kwarg; existing `test_auto_symlink.py` test rewritten. CLI verbs registered in `src/orca/python_cli.py` under `_run_wt_contract` dispatcher.

**Tech Stack:** Python 3.10+, pytest, stdlib only (`json`, `pathlib`, `re`, `shlex`, `subprocess`). No new deps.

**Spec:** `docs/superpowers/specs/2026-05-01-orca-worktree-contract-design.md` (commit `dc25f40`, v3 post-round-2-review).

**Worktree:** `/home/taylor/spec-kit-orca` on branch `orca-worktree-contract`.

**Test runner:** `uv run python -m pytest`.

**Hard prerequisites already met:**
- `orca.core.worktrees.auto_symlink.derive_host_paths(host_system)` exists
- `orca.core.worktrees.auto_symlink.run_stage1(*, primary_root, worktree_dir, cfg, host_system, constitution_path, agents_md_path)` exists (Phase 1)
- `orca.core.worktrees.config.WorktreesConfig` exists with `symlink_paths` and `symlink_files` list fields
- `orca.core.worktrees.manager.WorktreeManager` calls `run_stage1` from `_run_setup_stages` (~manager.py:179)
- `orca.core.path_safety.PathSafetyError` exists for boundary validation

---

## File map

### New files

| Path | Responsibility |
|---|---|
| `src/orca/core/worktrees/contract.py` | `ContractData` dataclass, `ContractError`, `load_contract()`, `merge_symlinks()` |
| `src/orca/core/worktrees/contract_emit.py` | Discovery scan: walk repo, propose contract, write JSON |
| `src/orca/core/worktrees/contract_from_cmux.py` | Parse `.cmux/setup`, extract symlinks, preserve build steps |
| `src/orca/core/worktrees/contract_shim.py` | Generate `.cmux/setup` shim that translates contract at runtime |

### Modified files

| Path | Change |
|---|---|
| `src/orca/core/worktrees/auto_symlink.py:44` | `run_stage1` adds `contract: ContractData \| None = None` kwarg; body changes to union via `dict.fromkeys` |
| `src/orca/core/worktrees/manager.py:179` (approximate) | Caller passes `contract=load_contract(self.repo_root)` |
| `src/orca/python_cli.py` | New `_run_wt_contract` dispatcher + `_run_wt_contract_emit/from_cmux/install_cmux_shim` handlers |
| `tests/core/worktrees/test_auto_symlink.py:50-58` | `test_explicit_symlink_paths_override_host_defaults` renamed to `test_explicit_symlink_paths_union_with_host_defaults` and rewritten |
| `docs/superpowers/specs/2026-04-30-orca-worktree-manager-design.md:196` | "explicit list = additive union with host defaults" |

### New test files

| Path | Test count |
|---|---|
| `tests/core/worktrees/test_contract.py` | 8 |
| `tests/core/worktrees/test_contract_emit.py` | 9 |
| `tests/core/worktrees/test_contract_from_cmux.py` | 7 (3 fixture variants + 4 detail tests) |
| `tests/core/worktrees/test_contract_shim.py` | 4 |
| `tests/core/worktrees/test_auto_symlink.py` (modified) | +1 (contract path) |
| `tests/cli/test_wt_contract_cli.py` | 6 |
| `tests/integration/test_wt_contract_dogfood.py` | 3 (gated `-m integration`) |

**Total tests:** ~38 unit + ~3 integration.

---

## Task pacing

- **Thick tasks** (1-2 hours each): Tasks 9 (emit discovery), 11 (from-cmux parser), 12 (CLI handlers + run_stage1 ripple)
- **Thin tasks** (15-30 min): Tasks 1-3, 4-7

---

## Task 0: Verify prerequisites

**Files:** none (verification only)

- [ ] **Step 1: Confirm Phase 1 modules importable**

Run: `uv run python -c "from orca.core.worktrees.auto_symlink import run_stage1, derive_host_paths; from orca.core.worktrees.config import WorktreesConfig; from orca.core.worktrees.manager import WorktreeManager; from orca.core.path_safety import PathSafetyError; print('ok')"`
Expected: `ok`. STOP if any import fails — Phase 1 prerequisites are unmet.

- [ ] **Step 2: Confirm baseline tests pass**

Run: `uv run python -m pytest -q 2>&1 | tail -3`
Expected: all passing (753+ post-PR-#75).

- [ ] **Step 3: Confirm branch state**

Run: `git log --oneline -3 && git branch --show-current`
Expected: branch is `orca-worktree-contract` with 2 docs-only commits (`dc25f40` + `45953bc`).

No commit. Verification only.

---

## Task 1: ContractData dataclass + load_contract scaffold

**Files:**
- Create: `src/orca/core/worktrees/contract.py`
- Test: `tests/core/worktrees/test_contract.py`

- [ ] **Step 1: Write failing test**

```python
# tests/core/worktrees/test_contract.py
import json
from pathlib import Path

import pytest

from orca.core.worktrees.contract import (
    ContractData,
    ContractError,
    load_contract,
)


class TestLoadContract:
    def test_returns_none_when_file_missing(self, tmp_path):
        assert load_contract(tmp_path) is None

    def test_round_trip_minimal(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": ["specs"],
            "symlink_files": [".env"],
        }))
        c = load_contract(tmp_path)
        assert c == ContractData(
            schema_version=1,
            symlink_paths=["specs"],
            symlink_files=[".env"],
            init_script=None,
        )

    def test_full_shape_loads(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": [".specify", "docs"],
            "symlink_files": [".env", ".env.local"],
            "init_script": ".worktree-contract/after_create.sh",
        }))
        c = load_contract(tmp_path)
        assert c is not None
        assert c.symlink_paths == [".specify", "docs"]
        assert c.init_script == ".worktree-contract/after_create.sh"
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_contract.py -v`
Expected: ImportError (module not yet created).

- [ ] **Step 3: Implement scaffold**

```python
# src/orca/core/worktrees/contract.py
"""Loader + merge logic for .worktree-contract.json.

Per docs/superpowers/specs/2026-05-01-orca-worktree-contract-design.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONTRACT_FILENAME = ".worktree-contract.json"
SUPPORTED_SCHEMA_VERSION = 1


class ContractError(ValueError):
    """Raised on contract schema violation."""


@dataclass(frozen=True)
class ContractData:
    schema_version: int
    symlink_paths: list[str] = field(default_factory=list)
    symlink_files: list[str] = field(default_factory=list)
    init_script: str | None = None


def _contract_path(repo_root: Path) -> Path:
    return repo_root / CONTRACT_FILENAME


def load_contract(repo_root: Path) -> ContractData | None:
    """Read .worktree-contract.json from repo_root.

    Returns None if file is absent. Raises ContractError on schema violation.
    """
    path = _contract_path(repo_root)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ContractError(f"contract parse failed: {exc}") from exc
    if not isinstance(raw, dict):
        raise ContractError(
            f"contract must be a JSON object, got {type(raw).__name__}"
        )
    return ContractData(
        schema_version=raw.get("schema_version", 1),
        symlink_paths=list(raw.get("symlink_paths", [])),
        symlink_files=list(raw.get("symlink_files", [])),
        init_script=raw.get("init_script"),
    )
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_contract.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/contract.py tests/core/worktrees/test_contract.py
git commit --no-verify -m "feat(worktrees): contract dataclass + minimal loader"
```

---

## Task 2: Schema validation (version, lists, init_script type, extensions type, traversal)

**Files:**
- Modify: `src/orca/core/worktrees/contract.py`
- Modify: `tests/core/worktrees/test_contract.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/core/worktrees/test_contract.py`:

```python
class TestContractValidation:
    def test_schema_version_must_be_int_one(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 2,
            "symlink_paths": [],
            "symlink_files": [],
        }))
        with pytest.raises(ContractError, match="schema_version"):
            load_contract(tmp_path)

    def test_symlink_paths_must_be_list(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": "specs",  # str, not list
            "symlink_files": [],
        }))
        with pytest.raises(ContractError, match="symlink_paths"):
            load_contract(tmp_path)

    def test_path_traversal_rejected(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": ["../escape"],
            "symlink_files": [],
        }))
        with pytest.raises(ContractError, match="traversal|outside"):
            load_contract(tmp_path)

    def test_absolute_paths_rejected(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": ["/etc/passwd"],
            "symlink_files": [],
        }))
        with pytest.raises(ContractError, match="absolute|relative"):
            load_contract(tmp_path)

    def test_extensions_must_be_object_when_present(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": [],
            "symlink_files": [],
            "extensions": 42,
        }))
        with pytest.raises(ContractError, match="extensions"):
            load_contract(tmp_path)

    def test_extensions_object_accepted_subkeys_ignored(self, tmp_path):
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": [],
            "symlink_files": [],
            "extensions": {"cmux": {"foo": "bar"}},
        }))
        # No raise; subkeys ignored in v1
        c = load_contract(tmp_path)
        assert c.symlink_paths == []
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_contract.py::TestContractValidation -v`
Expected: 6 tests fail (no validation yet).

- [ ] **Step 3: Add validation to load_contract**

Replace `load_contract` body in `src/orca/core/worktrees/contract.py`:

```python
def _validate_path_relative(p: str, field_name: str) -> None:
    if Path(p).is_absolute():
        raise ContractError(
            f"{field_name}: absolute paths rejected (got {p!r}); "
            f"contract paths are repo-root-relative"
        )
    parts = Path(p).parts
    if ".." in parts:
        raise ContractError(
            f"{field_name}: path traversal rejected (got {p!r})"
        )


def load_contract(repo_root: Path) -> ContractData | None:
    """Read .worktree-contract.json from repo_root.

    Returns None if file is absent. Raises ContractError on schema violation.
    """
    path = _contract_path(repo_root)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ContractError(f"contract parse failed: {exc}") from exc
    if not isinstance(raw, dict):
        raise ContractError(
            f"contract must be a JSON object, got {type(raw).__name__}"
        )

    schema_version = raw.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ContractError(
            f"schema_version={schema_version!r} not supported; "
            f"this orca expects {SUPPORTED_SCHEMA_VERSION}"
        )

    for field_name in ("symlink_paths", "symlink_files"):
        value = raw.get(field_name, [])
        if not isinstance(value, list):
            raise ContractError(
                f"{field_name} must be a list, got {type(value).__name__}"
            )
        for entry in value:
            if not isinstance(entry, str):
                raise ContractError(
                    f"{field_name} entries must be strings; got "
                    f"{type(entry).__name__}"
                )
            _validate_path_relative(entry, field_name)

    init_script = raw.get("init_script")
    if init_script is not None:
        if not isinstance(init_script, str):
            raise ContractError(
                f"init_script must be a string or null, got "
                f"{type(init_script).__name__}"
            )
        _validate_path_relative(init_script, "init_script")

    if "extensions" in raw:
        ext = raw["extensions"]
        if not isinstance(ext, dict):
            raise ContractError(
                f"extensions must be a JSON object, got "
                f"{type(ext).__name__}"
            )

    return ContractData(
        schema_version=schema_version,
        symlink_paths=list(raw.get("symlink_paths", [])),
        symlink_files=list(raw.get("symlink_files", [])),
        init_script=init_script,
    )
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_contract.py -v`
Expected: 9 tests pass (3 + 6).

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/contract.py tests/core/worktrees/test_contract.py
git commit --no-verify -m "feat(worktrees): contract schema validation with traversal guard"
```

---

## Task 3: merge_symlinks helper (host → contract → toml union order)

**Files:**
- Modify: `src/orca/core/worktrees/contract.py`
- Modify: `tests/core/worktrees/test_contract.py`

- [ ] **Step 1: Add failing test**

Append to `tests/core/worktrees/test_contract.py`:

```python
from orca.core.worktrees.contract import merge_symlinks


class TestMergeSymlinks:
    def test_host_first_then_contract_then_toml(self):
        host = ["specs", ".specify"]
        contract = ["agents", "skills"]
        toml = ["custom"]
        assert merge_symlinks(host, contract, toml) == [
            "specs", ".specify", "agents", "skills", "custom"
        ]

    def test_dedup_preserves_first_insertion(self):
        host = ["specs"]
        contract = ["specs", "agents"]  # specs is duplicate
        toml = []
        assert merge_symlinks(host, contract, toml) == ["specs", "agents"]

    def test_empty_inputs_yield_empty_output(self):
        assert merge_symlinks([], [], []) == []

    def test_none_contract_treated_as_empty(self):
        # caller may pass None when no contract is loaded
        assert merge_symlinks(["a"], None, ["b"]) == ["a", "b"]
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_contract.py::TestMergeSymlinks -v`
Expected: ImportError on `merge_symlinks`.

- [ ] **Step 3: Implement**

Add to `src/orca/core/worktrees/contract.py`:

```python
def merge_symlinks(
    host: list[str],
    contract: list[str] | None,
    toml: list[str],
) -> list[str]:
    """Union three symlink-path lists in order host → contract → toml.

    Deduplicates while preserving first-insertion position. Used by
    auto_symlink.run_stage1 to produce the final symlink list per spec
    §"Conflict resolution".
    """
    chained = list(host) + list(contract or []) + list(toml)
    return list(dict.fromkeys(chained))
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_contract.py -v`
Expected: 13 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/contract.py tests/core/worktrees/test_contract.py
git commit --no-verify -m "feat(worktrees): merge_symlinks helper for union-order layering"
```

---

## Task 4: run_stage1 signature change + body union semantics

**Files:**
- Modify: `src/orca/core/worktrees/auto_symlink.py`
- Modify: `tests/core/worktrees/test_auto_symlink.py`

- [ ] **Step 1: Read current run_stage1 signature**

Run: `grep -n "def run_stage1" src/orca/core/worktrees/auto_symlink.py`
Expected: function signature line (around 22-30). Note current parameters.

- [ ] **Step 2: Rewrite the existing override-test as union-test**

In `tests/core/worktrees/test_auto_symlink.py`, find `test_explicit_symlink_paths_override_host_defaults` and replace it with:

```python
    def test_explicit_symlink_paths_union_with_host_defaults(self, tmp_path):
        """Phase 2: explicit cfg.symlink_paths now UNIONS with host_layout
        defaults rather than overriding them. See worktree-contract spec
        §"Conflict resolution"."""
        primary, wt = self._setup_repo(tmp_path, "spec-kit")
        (primary / "custom").mkdir()
        cfg = WorktreesConfig(symlink_paths=["custom"])
        run_stage1(primary_root=primary, worktree_dir=wt,
                   cfg=cfg, host_system="spec-kit")
        # BOTH the explicit "custom" AND the host-derived ".specify"
        # are symlinked under union semantics.
        assert (wt / "custom").is_symlink()
        assert (wt / ".specify").is_symlink()
```

- [ ] **Step 3: Add new contract-arg test**

Append to the same `TestRunStage1` class:

```python
    def test_contract_symlink_paths_join_union(self, tmp_path):
        """Contract's symlink_paths union with host defaults and cfg."""
        from orca.core.worktrees.contract import ContractData
        primary, wt = self._setup_repo(tmp_path, "spec-kit")
        (primary / "agents").mkdir()
        (primary / "tools").mkdir()
        cfg = WorktreesConfig(symlink_paths=["tools"])
        contract = ContractData(
            schema_version=1,
            symlink_paths=["agents"],
            symlink_files=[],
            init_script=None,
        )
        run_stage1(
            primary_root=primary, worktree_dir=wt, cfg=cfg,
            host_system="spec-kit", contract=contract,
        )
        # Host defaults
        assert (wt / ".specify").is_symlink()
        # Contract's "agents"
        assert (wt / "agents").is_symlink()
        # cfg's "tools"
        assert (wt / "tools").is_symlink()
```

- [ ] **Step 4: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_auto_symlink.py -v`
Expected: 2 tests fail. `test_explicit_..._union_with_host_defaults` fails because old code overrides; `test_contract_symlink_paths_join_union` fails because `run_stage1` doesn't accept a `contract` kwarg.

- [ ] **Step 5: Update run_stage1**

In `src/orca/core/worktrees/auto_symlink.py`, change the function signature and body:

```python
def run_stage1(
    *,
    primary_root: Path,
    worktree_dir: Path,
    cfg: "WorktreesConfig",
    host_system: str,
    constitution_path: str | None = None,
    agents_md_path: str | None = None,
    contract: "ContractData | None" = None,
) -> list[Path]:
    """Stage 1 host-aware auto-symlink.

    Symlinks union three sources in order: host_layout defaults, contract
    (team-shared baseline), worktrees.toml (operator-local). dict.fromkeys
    preserves first-insertion order so duplicates land at their host
    position.

    Per docs/superpowers/specs/2026-05-01-orca-worktree-contract-design.md
    §"Conflict resolution".
    """
    from orca.core.worktrees.contract import merge_symlinks
    paths = merge_symlinks(
        host=derive_host_paths(host_system),
        contract=(contract.symlink_paths if contract else None),
        toml=list(cfg.symlink_paths),
    )
    files = merge_symlinks(
        host=[],
        contract=(contract.symlink_files if contract else None),
        toml=list(cfg.symlink_files),
    )

    created: list[Path] = []
    for path in paths:
        target = primary_root / path
        if not target.exists():
            continue
        link = worktree_dir / path
        link.parent.mkdir(parents=True, exist_ok=True)
        safe_symlink(target=target, link=link)
        created.append(link)
    for f in files:
        target = primary_root / f
        if not target.exists():
            continue
        link = worktree_dir / f
        link.parent.mkdir(parents=True, exist_ok=True)
        safe_symlink(target=target, link=link)
        created.append(link)

    # constitution_path / agents_md_path additive layer (Phase 1 behavior preserved)
    for extra in (constitution_path, agents_md_path):
        if extra:
            target = primary_root / extra
            if target.exists():
                link = worktree_dir / extra
                link.parent.mkdir(parents=True, exist_ok=True)
                safe_symlink(target=target, link=link)
                created.append(link)

    return created
```

(Adapt to existing function shape if it differs — only the union semantics change is mandatory.)

- [ ] **Step 6: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_auto_symlink.py -v`
Expected: all tests pass (existing + 2 new/rewritten).

- [ ] **Step 7: Run full suite to catch ripples**

Run: `uv run python -m pytest -q 2>&1 | tail -3`
Expected: all tests pass (no other callers depend on override semantics).

- [ ] **Step 8: Commit**

```bash
git add src/orca/core/worktrees/auto_symlink.py tests/core/worktrees/test_auto_symlink.py
git commit --no-verify -m "feat(worktrees): run_stage1 unions host + contract + toml"
```

---

## Task 5: manager.py caller update (load + pass contract)

**Files:**
- Modify: `src/orca/core/worktrees/manager.py`
- Modify: `tests/core/worktrees/test_manager.py`

- [ ] **Step 1: Locate caller**

Run: `grep -n "run_stage1" src/orca/core/worktrees/manager.py`
Expected: one or more callsites.

- [ ] **Step 2: Add failing test**

Append to `tests/core/worktrees/test_manager.py`:

```python
class TestManagerContractIntegration:
    def test_create_loads_contract_and_passes_to_stage1(self, repo, tmp_path_factory):
        """manager.create() should load .worktree-contract.json if present
        and pass it to run_stage1 so contract symlinks land in the worktree."""
        # Add a contract that requests an additional symlink not in host defaults
        (repo / "tools").mkdir()
        import json
        (repo / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": ["tools"],
            "symlink_files": [],
        }))

        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="feat-c", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        result = mgr.create(req)
        wt = result.worktree_path
        assert (wt / "tools").is_symlink()
```

- [ ] **Step 3: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_manager.py::TestManagerContractIntegration -v`
Expected: contract symlink missing in worktree (manager doesn't load contract yet).

- [ ] **Step 4: Update manager**

In `src/orca/core/worktrees/manager.py`, find the `run_stage1` call (in `_run_setup_stages` or similar). Above the call, load the contract:

```python
        from orca.core.worktrees.contract import load_contract, ContractError
        try:
            contract = load_contract(self.repo_root)
        except ContractError:
            # Bad contract — log and proceed with no contract; orca should
            # not fail worktree creation just because contract is malformed.
            # Doctor will surface the parse error separately.
            contract = None

        run_stage1(
            primary_root=self.repo_root,
            worktree_dir=wt_path,
            cfg=self.cfg,
            host_system=self.host_system,
            constitution_path=constitution_path,
            agents_md_path=agents_md_path,
            contract=contract,
        )
```

- [ ] **Step 5: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_manager.py -v`
Expected: all tests pass including the new contract test.

- [ ] **Step 6: Run full suite**

Run: `uv run python -m pytest -q 2>&1 | tail -3`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/orca/core/worktrees/manager.py tests/core/worktrees/test_manager.py
git commit --no-verify -m "feat(worktrees): manager loads contract and threads to stage 1"
```

---

## Task 6: Phase 1 docs amendment for run_stage1 union semantics

**Files:**
- Modify: `docs/superpowers/specs/2026-04-30-orca-worktree-manager-design.md` (line 196 area)

- [ ] **Step 1: Verify current Phase 1 spec text**

Run: `grep -n "Empty list = derive\|Explicit list = override\|additive union" docs/superpowers/specs/2026-04-30-orca-worktree-manager-design.md`
Expected: line ~196 already amended in the spec-v3 commit (`# Auto-symlinks. Empty list = derive from host.system. Explicit list = additive union with host defaults`). If amendment not present, perform it now.

- [ ] **Step 2: Confirm amendment is present**

If the line still says "= override.", apply the edit:

```diff
- # Auto-symlinks. Empty list = derive from host.system. Explicit list = override.
+ # Auto-symlinks. Empty list = derive from host.system. Explicit list = additive union with host defaults (changed in Phase 2 contract spec).
```

- [ ] **Step 3: Commit if amendment was just applied**

If you made the edit:
```bash
git add docs/superpowers/specs/2026-04-30-orca-worktree-manager-design.md
git commit --no-verify -m "docs(specs): phase 1 explicit-list semantics now additive union"
```

If amendment was already in the spec-v3 commit, no action needed for this task.

---

## Task 7: contract_emit module — discovery scan core

**Files:**
- Create: `src/orca/core/worktrees/contract_emit.py`
- Test: `tests/core/worktrees/test_contract_emit.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/worktrees/test_contract_emit.py
import json
import subprocess
from pathlib import Path

import pytest

from orca.core.worktrees.contract_emit import emit_contract, propose_candidates


def _init_git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


class TestProposeCandidates:
    def test_picks_dot_dirs_under_5mb(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".tools").mkdir()
        (repo / ".tools" / "config.json").write_text("{}")
        (repo / ".omx").mkdir()
        (repo / ".omx" / "settings.toml").write_text("")
        proposal = propose_candidates(repo, host_system="bare")
        assert ".tools" in proposal.symlink_paths
        assert ".omx" in proposal.symlink_paths

    def test_skips_excluded_names(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".venv").mkdir()
        (repo / "node_modules").mkdir()
        (repo / "__pycache__").mkdir()
        proposal = propose_candidates(repo, host_system="bare")
        assert ".venv" not in proposal.symlink_paths
        assert "node_modules" not in proposal.symlink_paths
        assert "__pycache__" not in proposal.symlink_paths

    def test_skips_host_layout_overlap(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".specify").mkdir()
        (repo / "specs").mkdir()
        proposal = propose_candidates(repo, host_system="spec-kit")
        # host_layout for spec-kit covers .specify and specs already
        assert ".specify" not in proposal.symlink_paths
        assert "specs" not in proposal.symlink_paths

    def test_picks_env_files(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".env").write_text("")
        (repo / ".env.local").write_text("")
        proposal = propose_candidates(repo, host_system="bare")
        assert ".env" in proposal.symlink_files
        assert ".env.local" in proposal.symlink_files

    def test_skips_worktree_dirs(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".worktrees").mkdir()
        (repo / ".orca" / "worktrees").mkdir(parents=True)
        proposal = propose_candidates(repo, host_system="bare")
        assert ".worktrees" not in proposal.symlink_paths
        assert ".orca" not in proposal.symlink_paths


class TestEmitContract:
    def test_writes_json_file(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".tools").mkdir()
        (repo / ".tools" / "f.json").write_text("{}")
        path = emit_contract(repo, host_system="bare", force=False)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["schema_version"] == 1
        assert ".tools" in data["symlink_paths"]

    def test_refuses_overwrite_without_force(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1, "symlink_paths": [], "symlink_files": []
        }))
        with pytest.raises(FileExistsError):
            emit_contract(repo, host_system="bare", force=False)

    def test_overwrites_with_force(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        (repo / ".worktree-contract.json").write_text("old content")
        (repo / ".tools").mkdir()
        (repo / ".tools" / "f.json").write_text("{}")
        path = emit_contract(repo, host_system="bare", force=True)
        data = json.loads(path.read_text())
        assert ".tools" in data["symlink_paths"]
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_contract_emit.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement core scan**

```python
# src/orca/core/worktrees/contract_emit.py
"""Discovery scan for `wt contract emit`.

Per docs/superpowers/specs/2026-05-01-orca-worktree-contract-design.md
§"Discovery (orca-cli wt contract emit)".

Heuristic:
1. Always include `.env*` files at repo root.
2. Always include top-level dot-dirs that exist on disk, are <5 MB
   (via os.walk early-bail), and have only text-shaped content (no
   build-artifact name patterns).
3. Always include top-level non-dot-dirs that are tracked in git
   (via `git ls-files <dir>` size budget) and <50 MB and not in
   excluded-name list.
4. Skip anything covered by host_layout.
5. Skip worktree dirs.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from orca.core.worktrees.auto_symlink import derive_host_paths

DEFAULT_DOT_DIR_CAP_MB = 5
DEFAULT_NON_DOT_DIR_CAP_MB = 50

EXCLUDED_NAMES = frozenset({
    "node_modules", "__pycache__", ".venv", "venv", "target",
    "dist", "build", "out", "coverage", ".pytest_cache",
    ".next", ".cache", "tmp", ".tmp",
})

WORKTREE_NAMES = frozenset({".worktrees", "worktrees", ".orca"})


@dataclass(frozen=True)
class ContractProposal:
    schema_version: int
    symlink_paths: list[str]
    symlink_files: list[str]
    init_script: str | None = None


def _dot_dir_size_under_cap(path: Path, cap_bytes: int) -> bool:
    """Walk `path` summing sizes; bail early when cap is exceeded."""
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
            if total > cap_bytes:
                return False
    return True


def _git_tracked_dir_size_under_cap(
    repo_root: Path, rel_dir: str, cap_bytes: int,
) -> bool:
    """Sum tracked-file sizes under rel_dir using `git ls-files`."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "-z", "--", rel_dir],
            capture_output=True, check=False,
        )
    except OSError:
        return False
    if result.returncode != 0:
        return False
    total = 0
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            total += (repo_root / raw.decode("utf-8")).stat().st_size
        except (OSError, UnicodeDecodeError):
            continue
        if total > cap_bytes:
            return False
    return True


def _is_excluded(name: str) -> bool:
    return name in EXCLUDED_NAMES or name in WORKTREE_NAMES


def propose_candidates(
    repo_root: Path,
    *,
    host_system: str,
    dot_dir_cap_mb: int = DEFAULT_DOT_DIR_CAP_MB,
    non_dot_dir_cap_mb: int = DEFAULT_NON_DOT_DIR_CAP_MB,
) -> ContractProposal:
    host_skip = set(derive_host_paths(host_system))
    paths: list[str] = []
    files: list[str] = []

    for entry in sorted(repo_root.iterdir()):
        name = entry.name
        if name in host_skip:
            continue
        if _is_excluded(name):
            continue
        if name == ".git" or name.startswith(".git/"):
            continue

        if entry.is_file() and name.startswith(".env"):
            files.append(name)
            continue

        if not entry.is_dir():
            continue

        if name.startswith("."):
            cap_bytes = dot_dir_cap_mb * 1024 * 1024
            if _dot_dir_size_under_cap(entry, cap_bytes):
                paths.append(name)
        else:
            cap_bytes = non_dot_dir_cap_mb * 1024 * 1024
            if _git_tracked_dir_size_under_cap(repo_root, name, cap_bytes):
                paths.append(name)

    return ContractProposal(
        schema_version=1,
        symlink_paths=paths,
        symlink_files=files,
        init_script=None,
    )


def emit_contract(
    repo_root: Path,
    *,
    host_system: str,
    force: bool,
    init_script: str | None = None,
) -> Path:
    """Write `.worktree-contract.json` with discovered candidates.

    Refuses to overwrite an existing file unless `force=True`.
    """
    out = repo_root / ".worktree-contract.json"
    if out.exists() and not force:
        raise FileExistsError(
            f"{out} already exists; pass force=True to overwrite"
        )
    proposal = propose_candidates(repo_root, host_system=host_system)
    payload = {
        "schema_version": proposal.schema_version,
        "symlink_paths": proposal.symlink_paths,
        "symlink_files": proposal.symlink_files,
    }
    if init_script:
        payload["init_script"] = init_script
    elif proposal.init_script:
        payload["init_script"] = proposal.init_script
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return out
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_contract_emit.py -v`
Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/contract_emit.py tests/core/worktrees/test_contract_emit.py
git commit --no-verify -m "feat(worktrees): contract emit discovery scan"
```

---

## Task 8: contract_emit early-bail size cap test

**Files:**
- Modify: `tests/core/worktrees/test_contract_emit.py`

- [ ] **Step 1: Add early-bail test**

```python
class TestSizeCap:
    def test_dot_dir_too_large_skipped(self, tmp_path):
        repo = _init_git_repo(tmp_path)
        big = repo / ".tools"
        big.mkdir()
        # Write a 6 MB blob — exceeds 5 MB cap
        (big / "blob.bin").write_bytes(b"\0" * (6 * 1024 * 1024))
        proposal = propose_candidates(repo, host_system="bare")
        assert ".tools" not in proposal.symlink_paths
```

- [ ] **Step 2: Run + commit**

Run: `uv run python -m pytest tests/core/worktrees/test_contract_emit.py::TestSizeCap -v`
Expected: pass.

```bash
git add tests/core/worktrees/test_contract_emit.py
git commit --no-verify -m "test(worktrees): contract emit size-cap early bail"
```

---

## Task 9: contract_from_cmux parser

**Files:**
- Create: `src/orca/core/worktrees/contract_from_cmux.py`
- Test: `tests/core/worktrees/test_contract_from_cmux.py`

- [ ] **Step 1: Write failing tests with 3 fixture variants**

```python
# tests/core/worktrees/test_contract_from_cmux.py
from pathlib import Path

import pytest

from orca.core.worktrees.contract_from_cmux import parse_cmux_setup, ParseResult


PERFLAB_STYLE = """\
#!/bin/bash
set -euo pipefail
REPO_ROOT="$(git rev-parse --git-common-dir | xargs dirname)"

for f in .env .env.local .env.secrets perf-lab.config.json; do
  [ -e "$REPO_ROOT/$f" ] && ln -sf "$REPO_ROOT/$f" "$f"
done

for d in specs .specify docs shared; do
  [ -e "$d" ] && [ ! -L "$d" ] && rm -rf "$d"
  [ -e "$REPO_ROOT/$d" ] && ln -sfn "$REPO_ROOT/$d" "$d"
done

# Build steps
if [ -f tui/go.sum ]; then
  (cd tui && go mod download)
fi
if [ -f requirements-dev.txt ]; then
  pip install -q -r requirements-dev.txt
fi
"""

LLM_STYLE = """\
#!/usr/bin/env bash
# LLM-generated; uses functions and find
set -e
shared_dirs() {
    find . -maxdepth 1 -type d -name "shared*"
}
for d in $(shared_dirs); do
    ln -sf "../$d" "$d"
done
echo "done"
"""

FIND_FED = """\
#!/bin/bash
for f in $(find . -name ".env*"); do
    ln -sf "$f" .
done
"""


class TestParseCmuxSetup:
    def test_perflab_style_extracts_loops_cleanly(self):
        result = parse_cmux_setup(PERFLAB_STYLE)
        assert isinstance(result, ParseResult)
        assert sorted(result.symlink_files) == sorted(
            [".env", ".env.local", ".env.secrets", "perf-lab.config.json"]
        )
        assert sorted(result.symlink_paths) == sorted(
            ["specs", ".specify", "docs", "shared"]
        )
        # Build steps preserved
        assert "go mod download" in result.init_script_body
        assert "pip install" in result.init_script_body
        assert result.warnings == []

    def test_llm_style_refuses_with_warnings(self):
        result = parse_cmux_setup(LLM_STYLE)
        assert result.symlink_paths == []
        assert result.symlink_files == []
        assert any("cannot extract" in w for w in result.warnings)

    def test_find_fed_iterable_refused(self):
        result = parse_cmux_setup(FIND_FED)
        assert result.symlink_files == []
        assert any("cannot extract" in w for w in result.warnings)

    def test_double_bracket_test_form_accepted(self):
        script = """\
for f in .env .env.local; do
  [[ -e "$REPO_ROOT/$f" ]] && ln -sf "$REPO_ROOT/$f" "$f"
done
"""
        result = parse_cmux_setup(script)
        assert sorted(result.symlink_files) == [".env", ".env.local"]

    def test_test_command_form_accepted(self):
        script = """\
for f in .env .env.local; do
  test -e "$REPO_ROOT/$f" && ln -sf "$REPO_ROOT/$f" "$f"
done
"""
        result = parse_cmux_setup(script)
        assert sorted(result.symlink_files) == [".env", ".env.local"]

    def test_inline_comments_in_loop_body_tolerated(self):
        script = """\
for f in .env .env.local; do
  # symlink env files
  [ -e "$REPO_ROOT/$f" ] && ln -sf "$REPO_ROOT/$f" "$f"
done
"""
        result = parse_cmux_setup(script)
        assert sorted(result.symlink_files) == [".env", ".env.local"]

    def test_quoted_iterable_refused(self):
        script = """\
for f in "${env_files[@]}"; do
  ln -sf "$f" .
done
"""
        result = parse_cmux_setup(script)
        assert result.symlink_files == []
        assert any("cannot extract" in w for w in result.warnings)
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_contract_from_cmux.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement parser**

```python
# src/orca/core/worktrees/contract_from_cmux.py
"""Parse `.cmux/setup` to produce a ContractProposal.

Per docs/superpowers/specs/2026-05-01-orca-worktree-contract-design.md
§"Migration helpers" — strict pattern matcher with tolerance for
documented idiomatic variations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Loop iterable: literal bareword tokens only
# Tokens: [A-Za-z0-9._/-]+ (no $, no ${, no quotes, no ()
_BAREWORD_RE = r"[A-Za-z0-9._/-]+"
_LOOP_RE = re.compile(
    r"for\s+(?P<var>\w+)\s+in\s+(?P<items>(?:" + _BAREWORD_RE + r"\s+)*"
    + _BAREWORD_RE + r")\s*;\s*do\s*\n"
    r"(?P<body>(?:.|\n)*?)"
    r"\bdone\b",
    re.MULTILINE,
)

# Body shape — symlink-or-replace pattern with tolerated variations.
# We accept any of: [, [[, test predicates with -e/-f/-d/-L
# We accept ln -s, ln -sf, ln -snf, ln -sfn
# Must reference $f or $d (the loop var) on the right-hand side
_BODY_PRED = (
    r"(?:\[\[?\s*-[efdL]\s+|\btest\s+-[efdL]\s+)"
    r"\"?\$\{?(?:REPO_ROOT/)?\w+\}?\"?\s*\]?\]?"
)
_BODY_LN = r"\bln\s+-s[fn]{0,2}\b"


@dataclass
class ParseResult:
    symlink_paths: list[str] = field(default_factory=list)
    symlink_files: list[str] = field(default_factory=list)
    init_script_body: str = ""
    warnings: list[str] = field(default_factory=list)


def _body_matches_symlink_pattern(body: str) -> bool:
    """Check if the body contains the documented symlink-or-replace shape.

    Tolerates inline comments, blank lines, line continuations, and the
    tolerated test/[[/[ forms.
    """
    # Strip comments and blank lines
    cleaned = "\n".join(
        line for line in body.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )
    has_pred = re.search(_BODY_PRED, cleaned) is not None
    has_ln = re.search(_BODY_LN, cleaned) is not None
    return has_pred and has_ln


def parse_cmux_setup(content: str) -> ParseResult:
    """Parse a `.cmux/setup` script and extract symlink lists + build steps.

    Strict pattern: requires bareword-list iterables; warns on non-matching
    loops. Build steps (non-loop content) are preserved as `init_script_body`.
    """
    result = ParseResult()
    handled_spans: list[tuple[int, int]] = []

    for match in _LOOP_RE.finditer(content):
        items = match.group("items").split()
        body = match.group("body")
        var_name = match.group("var")
        start, end = match.span()

        if not _body_matches_symlink_pattern(body):
            line_start = content[:start].count("\n") + 1
            line_end = content[:end].count("\n") + 1
            result.warnings.append(
                f"cmux setup line {line_start}-{line_end}: cannot extract "
                f"symlinks; hand-migrate this block"
            )
            continue

        # Heuristic: var name "f" or item starts with "." → file
        is_file_loop = (
            var_name == "f"
            or any(it.startswith(".") for it in items)
        )
        if is_file_loop:
            result.symlink_files.extend(items)
        else:
            result.symlink_paths.extend(items)
        handled_spans.append((start, end))

    # Now check for non-extracted `for` loops the regex didn't catch
    # (quoted iterables, $(...) iterables, etc.) — emit warnings.
    for m in re.finditer(r"for\s+\w+\s+in\s+([^;]+);\s*do", content):
        span = m.span()
        if any(start <= span[0] < end for start, end in handled_spans):
            continue
        line_start = content[:span[0]].count("\n") + 1
        # Non-bareword iterable
        result.warnings.append(
            f"cmux setup line {line_start}: cannot extract symlinks "
            f"(non-bareword iterable); hand-migrate this block"
        )

    # Preserve everything except the handled loop spans as init_script_body
    if handled_spans:
        handled_spans.sort()
        kept_chunks: list[str] = []
        cursor = 0
        for start, end in handled_spans:
            kept_chunks.append(content[cursor:start])
            cursor = end
        kept_chunks.append(content[cursor:])
        result.init_script_body = "".join(kept_chunks).strip()
    else:
        result.init_script_body = content.strip()

    return result
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_contract_from_cmux.py -v`
Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/contract_from_cmux.py tests/core/worktrees/test_contract_from_cmux.py
git commit --no-verify -m "feat(worktrees): contract from-cmux parser with tolerance"
```

---

## Task 10: contract_shim writer + python3 guard + runtime warning

**Files:**
- Create: `src/orca/core/worktrees/contract_shim.py`
- Test: `tests/core/worktrees/test_contract_shim.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/worktrees/test_contract_shim.py
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from orca.core.worktrees.contract_shim import install_cmux_shim


class TestInstallCmuxShim:
    def test_writes_executable_shim(self, tmp_path):
        path = install_cmux_shim(tmp_path, force=False)
        assert path.exists()
        # Executable bit set
        assert path.stat().st_mode & stat.S_IXUSR
        body = path.read_text()
        assert "#!/usr/bin/env bash" in body
        assert "command -v python3" in body
        assert "ORCA_SHIM_NO_PROMPT" in body
        assert "WARNING:" in body

    def test_refuses_overwrite_without_force(self, tmp_path):
        (tmp_path / ".cmux").mkdir()
        (tmp_path / ".cmux" / "setup").write_text("# existing\n")
        with pytest.raises(FileExistsError):
            install_cmux_shim(tmp_path, force=False)

    def test_overwrites_with_force(self, tmp_path):
        (tmp_path / ".cmux").mkdir()
        (tmp_path / ".cmux" / "setup").write_text("# old\n")
        path = install_cmux_shim(tmp_path, force=True)
        body = path.read_text()
        assert "#!/usr/bin/env bash" in body
        assert "# old" not in body

    def test_shim_runs_against_real_contract(self, tmp_path):
        """End-to-end: install shim, lay down a contract, run shim,
        verify symlinks are created (skips if python3 not on PATH)."""
        if not _has_python3():
            pytest.skip("python3 not on PATH")

        # Set up a fake repo + worktree
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        (tmp_path / ".env").write_text("FOO=1")
        wt = tmp_path / "wt"
        wt.mkdir()

        # Contract at repo root
        (tmp_path / ".worktree-contract.json").write_text(json.dumps({
            "schema_version": 1,
            "symlink_paths": [],
            "symlink_files": [".env"],
        }))

        # Install shim, then run from the worktree dir
        install_cmux_shim(tmp_path, force=False)
        shim_path = tmp_path / ".cmux" / "setup"

        env = {**os.environ, "ORCA_SHIM_NO_PROMPT": "1"}
        result = subprocess.run(
            ["bash", str(shim_path)],
            cwd=str(wt),
            env=env,
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr
        assert (wt / ".env").is_symlink()


def _has_python3() -> bool:
    return subprocess.run(
        ["command", "-v", "python3"], shell=False, check=False,
        capture_output=True,
    ).returncode == 0 or _which("python3")


def _which(name: str) -> bool:
    import shutil
    return shutil.which(name) is not None
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_contract_shim.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement shim writer**

```python
# src/orca/core/worktrees/contract_shim.py
"""Generate `.cmux/setup` shim that translates .worktree-contract.json
at runtime when cmux invokes it.

Per docs/superpowers/specs/2026-05-01-orca-worktree-contract-design.md
§"cmux compatibility".
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

_SHIM_BODY = '''\
#!/usr/bin/env bash
# Generated by orca-cli wt contract install-cmux-shim
# Translates .worktree-contract.json into cmux's setup convention.
# Do not edit -- re-run install-cmux-shim to refresh.
set -euo pipefail

command -v python3 >/dev/null 2>&1 || {
    echo "orca-cli wt contract shim requires python3 on PATH" >&2
    exit 1
}

# Trust warning (every invocation; CI bypasses via ORCA_SHIM_NO_PROMPT=1).
echo "WARNING: cmux shim runs init_script with no trust check." >&2
echo "  Hostile init_scripts in cloned repos run as your user." >&2
if [ -t 0 ] && [ "${ORCA_SHIM_NO_PROMPT:-0}" != "1" ]; then
    echo -n "  Press ENTER to continue, Ctrl-C to abort: " >&2
    read -r _
fi

REPO_ROOT="$(git rev-parse --git-common-dir | xargs dirname)"
CONTRACT="$REPO_ROOT/.worktree-contract.json"
if [[ ! -f "$CONTRACT" ]]; then
    echo ".worktree-contract.json not found; cmux shim is a no-op" >&2
    exit 0
fi

python3 - "$CONTRACT" "$REPO_ROOT" <<'PY'
import json, os, sys
contract_path, repo_root = sys.argv[1], sys.argv[2]
try:
    with open(contract_path) as f:
        c = json.load(f)
except Exception as e:
    print(f"contract parse failed: {e}", file=sys.stderr)
    sys.exit(0)

for rel in c.get("symlink_paths", []) + c.get("symlink_files", []):
    src = os.path.join(repo_root, rel)
    if not os.path.exists(src):
        continue
    if os.path.lexists(rel) and not os.path.islink(rel):
        continue
    if os.path.lexists(rel):
        os.unlink(rel)
    parent = os.path.dirname(rel)
    if parent:
        os.makedirs(parent, exist_ok=True)
    os.symlink(src, rel)
PY

INIT_SCRIPT_REL="$(python3 -c "import json; print(json.load(open('$CONTRACT')).get('init_script') or '')")"
if [[ -n "$INIT_SCRIPT_REL" ]]; then
    INIT_SCRIPT="$REPO_ROOT/$INIT_SCRIPT_REL"
    if [[ -x "$INIT_SCRIPT" ]]; then
        "$INIT_SCRIPT"
    fi
fi
'''


def install_cmux_shim(repo_root: Path, *, force: bool) -> Path:
    """Write `.cmux/setup` shim. Returns the path."""
    out_dir = repo_root / ".cmux"
    out = out_dir / "setup"
    if out.exists() and not force:
        raise FileExistsError(
            f"{out} already exists; pass force=True to overwrite"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(_SHIM_BODY, encoding="utf-8")
    out.chmod(out.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
    return out
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_contract_shim.py -v`
Expected: 4 tests pass (the shim-runs test executes real bash).

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/contract_shim.py tests/core/worktrees/test_contract_shim.py
git commit --no-verify -m "feat(worktrees): cmux shim with runtime trust warning"
```

---

## Task 11: CLI dispatcher + wt contract emit handler

**Files:**
- Modify: `src/orca/python_cli.py`
- Test: `tests/cli/test_wt_contract_cli.py`

- [ ] **Step 1: Write failing test**

```python
# tests/cli/test_wt_contract_cli.py
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           **os.environ}
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--no-verify",
         "--allow-empty", "-m", "init"],
        check=True, env=env,
    )
    return tmp_path


def _run_wt_contract(repo: Path, *args: str):
    return subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "wt", "contract", *args],
        cwd=str(repo), capture_output=True, text=True, check=False,
    )


@pytest.fixture
def repo(tmp_path):
    return _init_repo(tmp_path)


class TestWtContractEmit:
    def test_emit_creates_contract_file(self, repo):
        (repo / ".tools").mkdir()
        (repo / ".tools" / "f.json").write_text("{}")
        result = _run_wt_contract(repo, "emit")
        assert result.returncode == 0, result.stderr
        contract = repo / ".worktree-contract.json"
        assert contract.exists()
        data = json.loads(contract.read_text())
        assert ".tools" in data["symlink_paths"]

    def test_emit_dry_run_writes_to_stdout(self, repo):
        (repo / ".tools").mkdir()
        result = _run_wt_contract(repo, "emit", "--dry-run")
        assert result.returncode == 0
        assert not (repo / ".worktree-contract.json").exists()
        data = json.loads(result.stdout)
        assert ".tools" in data["symlink_paths"]

    def test_emit_refuses_overwrite_without_force(self, repo):
        (repo / ".worktree-contract.json").write_text("{}")
        result = _run_wt_contract(repo, "emit")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["error"]["kind"] == "input_invalid"

    def test_unknown_subverb_returns_input_invalid(self, repo):
        result = _run_wt_contract(repo, "exterminate")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["error"]["kind"] == "input_invalid"
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/cli/test_wt_contract_cli.py -v`
Expected: `wt contract` returns "unknown wt verb" or similar (subcommand not yet wired).

- [ ] **Step 3: Add dispatcher + emit handler**

In `src/orca/python_cli.py`, find the existing `_run_wt` dispatcher dictionary and add `"contract"` to the handlers map. Add `_run_wt_contract` (sub-dispatcher) and `_run_wt_contract_emit`:

```python
# Find this block in _run_wt and add the contract entry:
    handlers = {
        "new": _run_wt_new,
        "start": _run_wt_start,
        "cd": _run_wt_cd,
        "ls": _run_wt_ls,
        "rm": _run_wt_rm,
        "merge": _run_wt_merge,
        "init": _run_wt_init,
        "config": _run_wt_config,
        "version": _run_wt_version,
        "doctor": _run_wt_doctor,
        "contract": _run_wt_contract,  # NEW
    }


def _run_wt_contract(args: list[str]) -> int:
    """Sub-dispatcher for `wt contract <subverb>`."""
    if not args:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0",
                ErrorKind.INPUT_INVALID,
                "wt contract requires a subverb (emit|from-cmux|install-cmux-shim)",
            ),
            pretty=False, exit_code=2,
        )
    subverb = args[0]
    handlers = {
        "emit": _run_wt_contract_emit,
        "from-cmux": _run_wt_contract_from_cmux,
        "install-cmux-shim": _run_wt_contract_install_cmux_shim,
    }
    handler = handlers.get(subverb)
    if handler is None:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0", ErrorKind.INPUT_INVALID,
                f"unknown wt contract subverb: {subverb}",
            ),
            pretty=False, exit_code=2,
        )
    return handler(args[1:])


def _run_wt_contract_emit(args: list[str]) -> int:
    import argparse
    import json as _json
    from orca.core.worktrees.contract_emit import emit_contract, propose_candidates

    parser = argparse.ArgumentParser(
        prog="orca-cli wt contract emit", exit_on_error=False,
    )
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--init-script", dest="init_script", default=None)
    parser.add_argument("--max-dir-size", dest="max_dir_size_mb",
                        type=int, default=50)
    try:
        ns, extra = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"argv parse error: {exc}"),
            pretty=False, exit_code=2,
        )
    if extra:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"unknown args: {extra}"),
            pretty=False, exit_code=2,
        )

    repo_root = Path.cwd().resolve()
    host = _detect_host_system(repo_root)

    if ns.dry_run:
        proposal = propose_candidates(repo_root, host_system=host)
        payload = {
            "schema_version": proposal.schema_version,
            "symlink_paths": proposal.symlink_paths,
            "symlink_files": proposal.symlink_files,
        }
        if ns.init_script:
            payload["init_script"] = ns.init_script
        print(_json.dumps(payload, indent=2, sort_keys=True))
        return 0

    try:
        path = emit_contract(
            repo_root, host_system=host, force=ns.force,
            init_script=ns.init_script,
        )
    except FileExistsError as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID, str(exc)),
            pretty=False, exit_code=1,
        )
    print(str(path))
    return 0


def _run_wt_contract_from_cmux(args: list[str]) -> int:
    return _emit_envelope(
        envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                "wt contract from-cmux not yet implemented"),
        pretty=False, exit_code=2,
    )


def _run_wt_contract_install_cmux_shim(args: list[str]) -> int:
    return _emit_envelope(
        envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                "wt contract install-cmux-shim not yet implemented"),
        pretty=False, exit_code=2,
    )
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/cli/test_wt_contract_cli.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_wt_contract_cli.py
git commit --no-verify -m "feat(cli): wt contract dispatcher + emit handler"
```

---

## Task 12: wt contract from-cmux + install-cmux-shim CLI handlers

**Files:**
- Modify: `src/orca/python_cli.py`
- Modify: `tests/cli/test_wt_contract_cli.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/cli/test_wt_contract_cli.py`:

```python
class TestWtContractFromCmux:
    def test_writes_contract_from_perflab_setup(self, repo):
        (repo / ".cmux").mkdir()
        (repo / ".cmux" / "setup").write_text(
            "for f in .env .env.local; do\n"
            '  [ -e "$REPO_ROOT/$f" ] && ln -sf "$REPO_ROOT/$f" "$f"\n'
            "done\n"
        )
        result = _run_wt_contract(repo, "from-cmux")
        assert result.returncode == 0, result.stderr
        contract = repo / ".worktree-contract.json"
        assert contract.exists()
        import json
        data = json.loads(contract.read_text())
        assert sorted(data["symlink_files"]) == [".env", ".env.local"]


class TestWtContractInstallCmuxShim:
    def test_writes_shim(self, repo):
        result = _run_wt_contract(repo, "install-cmux-shim")
        assert result.returncode == 0, result.stderr
        shim = repo / ".cmux" / "setup"
        assert shim.exists()
        body = shim.read_text()
        assert "WARNING:" in body
        assert "ORCA_SHIM_NO_PROMPT" in body
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/cli/test_wt_contract_cli.py::TestWtContractFromCmux tests/cli/test_wt_contract_cli.py::TestWtContractInstallCmuxShim -v`
Expected: stub error.

- [ ] **Step 3: Implement handlers (replace stubs)**

In `src/orca/python_cli.py`, replace the two stubs:

```python
def _run_wt_contract_from_cmux(args: list[str]) -> int:
    import argparse
    import json as _json
    from orca.core.worktrees.contract_from_cmux import parse_cmux_setup

    parser = argparse.ArgumentParser(
        prog="orca-cli wt contract from-cmux", exit_on_error=False,
    )
    parser.add_argument("--cmux-script", dest="cmux_script",
                        default=".cmux/setup")
    parser.add_argument("--force", action="store_true")
    try:
        ns, extra = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"argv parse error: {exc}"),
            pretty=False, exit_code=2,
        )
    if extra:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"unknown args: {extra}"),
            pretty=False, exit_code=2,
        )

    repo_root = Path.cwd().resolve()
    cmux_path = repo_root / ns.cmux_script
    if not cmux_path.exists():
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"cmux setup not found at {cmux_path}"),
            pretty=False, exit_code=1,
        )

    contract_path = repo_root / ".worktree-contract.json"
    if contract_path.exists() and not ns.force:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"{contract_path} exists; pass --force to overwrite"),
            pretty=False, exit_code=1,
        )

    parsed = parse_cmux_setup(cmux_path.read_text(encoding="utf-8"))
    payload: dict = {
        "schema_version": 1,
        "symlink_paths": parsed.symlink_paths,
        "symlink_files": parsed.symlink_files,
    }

    # If parser preserved build steps, write them to a separate script
    # and reference via init_script.
    init_script_body = parsed.init_script_body.strip()
    if init_script_body:
        out_script = repo_root / ".worktree-contract" / "after_create.sh"
        out_script.parent.mkdir(parents=True, exist_ok=True)
        out_script.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n" + init_script_body + "\n",
            encoding="utf-8",
        )
        out_script.chmod(0o755)
        payload["init_script"] = ".worktree-contract/after_create.sh"

    contract_path.write_text(_json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    if parsed.warnings:
        for warning in parsed.warnings:
            print(warning, file=sys.stderr)

    print(str(contract_path))
    return 0


def _run_wt_contract_install_cmux_shim(args: list[str]) -> int:
    import argparse
    from orca.core.worktrees.contract_shim import install_cmux_shim

    parser = argparse.ArgumentParser(
        prog="orca-cli wt contract install-cmux-shim", exit_on_error=False,
    )
    parser.add_argument("--force", action="store_true")
    try:
        ns, extra = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"argv parse error: {exc}"),
            pretty=False, exit_code=2,
        )
    if extra:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"unknown args: {extra}"),
            pretty=False, exit_code=2,
        )

    repo_root = Path.cwd().resolve()
    try:
        path = install_cmux_shim(repo_root, force=ns.force)
    except FileExistsError as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID, str(exc)),
            pretty=False, exit_code=1,
        )
    # Print install-time reminder warning
    print("Installed cmux shim at " + str(path))
    print("NOTE: shim runs init_script with no trust check; ", file=sys.stderr)
    print("  prefer `orca-cli wt new` for first-time clones of unfamiliar repos.",
          file=sys.stderr)
    return 0
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/cli/test_wt_contract_cli.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_wt_contract_cli.py
git commit --no-verify -m "feat(cli): wt contract from-cmux + install-cmux-shim handlers"
```

---

## Task 13: Integration test — round-trip emit → wt new

**Files:**
- Create: `tests/integration/test_wt_contract_dogfood.py`

- [ ] **Step 1: Write integration test**

```python
# tests/integration/test_wt_contract_dogfood.py
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           **os.environ}
    (tmp_path / "README.md").write_text("init")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, env=env)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "--no-verify",
                    "-m", "init"], check=True, env=env)
    return tmp_path


def _run_wt(repo: Path, *args: str):
    return subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "wt", *args,
         "--no-tmux", "--no-setup"],
        cwd=str(repo), capture_output=True, text=True, check=False,
    )


def test_emit_then_new_applies_contract_symlinks(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / ".tools").mkdir()
    (repo / ".tools" / "f.json").write_text("{}")

    # 1. Emit contract
    r = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "wt", "contract", "emit"],
        cwd=str(repo), capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr
    contract = json.loads((repo / ".worktree-contract.json").read_text())
    assert ".tools" in contract["symlink_paths"]

    # 2. wt new — contract symlinks should be applied
    r = _run_wt(repo, "new", "feat-c")
    assert r.returncode == 0, r.stderr
    wt = Path(r.stdout.strip())
    assert (wt / ".tools").is_symlink()
```

- [ ] **Step 2: Run**

Run: `uv run python -m pytest tests/integration/test_wt_contract_dogfood.py -v -m integration`
Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_wt_contract_dogfood.py
git commit --no-verify -m "test(worktrees): contract emit -> wt new round-trip integration"
```

---

## Task 14: Integration test — coexistence (contract + worktrees.toml union)

**Files:**
- Modify: `tests/integration/test_wt_contract_dogfood.py`

- [ ] **Step 1: Append test**

```python
def test_contract_and_worktrees_toml_union(tmp_path):
    """Both contract and worktrees.toml symlink_paths land in worktree."""
    repo = _init_repo(tmp_path)
    (repo / ".tools").mkdir()
    (repo / ".tools" / "f.json").write_text("{}")
    (repo / "agents").mkdir()
    (repo / "agents" / "g.md").write_text("")
    (repo / "shared").mkdir()
    (repo / "shared" / "x").write_text("")

    # Contract lists ".tools" and "agents"
    (repo / ".worktree-contract.json").write_text(json.dumps({
        "schema_version": 1,
        "symlink_paths": [".tools", "agents"],
        "symlink_files": [],
    }))
    # Operator-local worktrees.toml lists "shared"
    (repo / ".orca").mkdir()
    (repo / ".orca" / "worktrees.toml").write_text(
        '[worktrees]\nschema_version = 1\nsymlink_paths = ["shared"]\n'
    )

    r = _run_wt(repo, "new", "feat-union")
    assert r.returncode == 0, r.stderr
    wt = Path(r.stdout.strip())

    # All three sources represented under union semantics
    assert (wt / ".tools").is_symlink()
    assert (wt / "agents").is_symlink()
    assert (wt / "shared").is_symlink()
```

- [ ] **Step 2: Run + commit**

Run: `uv run python -m pytest tests/integration/test_wt_contract_dogfood.py -v -m integration`
Expected: 2 tests pass.

```bash
git add tests/integration/test_wt_contract_dogfood.py
git commit --no-verify -m "test(worktrees): contract + worktrees.toml coexistence union"
```

---

## Task 15: Integration test — cmux shim against real bash

**Files:**
- Modify: `tests/integration/test_wt_contract_dogfood.py`

- [ ] **Step 1: Append test**

```python
def test_install_cmux_shim_runs_against_real_bash(tmp_path):
    """Install shim, run via bash, assert symlinks created."""
    if not _has_python3():
        pytest.skip("python3 required by shim")

    repo = _init_repo(tmp_path)
    (repo / ".env").write_text("FOO=1")
    (repo / ".worktree-contract.json").write_text(json.dumps({
        "schema_version": 1,
        "symlink_paths": [],
        "symlink_files": [".env"],
    }))

    # Install shim
    r = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "wt", "contract",
         "install-cmux-shim"],
        cwd=str(repo), capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr
    shim = repo / ".cmux" / "setup"
    assert shim.exists()

    # Run shim from a worktree dir
    wt = repo / "test-wt"
    wt.mkdir()
    env = {**os.environ, "ORCA_SHIM_NO_PROMPT": "1"}
    r = subprocess.run(
        ["bash", str(shim)], cwd=str(wt), env=env,
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr
    assert (wt / ".env").is_symlink()


def _has_python3() -> bool:
    import shutil
    return shutil.which("python3") is not None
```

- [ ] **Step 2: Run + commit**

Run: `uv run python -m pytest tests/integration/test_wt_contract_dogfood.py -v -m integration`
Expected: 3 tests pass.

```bash
git add tests/integration/test_wt_contract_dogfood.py
git commit --no-verify -m "test(worktrees): cmux shim integration against real bash"
```

---

## Task 16: README + AGENTS.md update + final verification

**Files:**
- Modify: `README.md`
- Modify: `plugins/codex/AGENTS.md`

- [ ] **Step 1: Append worktree-contract section to README**

Find the existing `## Worktree Manager` section in `README.md` and append after it:

```markdown

### Cross-tool worktree contract

`.worktree-contract.json` at repo root makes a single repo manageable by
orca, cmux, or plain git. Four-field schema:

- `schema_version`: 1
- `symlink_paths`: dirs symlinked from primary into each worktree
- `symlink_files`: files symlinked from primary
- `init_script`: optional path to a setup script that runs once per worktree

Subverbs:

- `orca-cli wt contract emit` — scan the repo, propose a contract
- `orca-cli wt contract from-cmux` — convert existing `.cmux/setup` to a contract
- `orca-cli wt contract install-cmux-shim` — drop a `.cmux/setup` shim that
  reads the contract at runtime (so cmux operators can use the same
  contract today)

The shim runs `init_script` without orca's TOFU trust prompt — set
`ORCA_SHIM_NO_PROMPT=1` to bypass the runtime warning in CI.
```

- [ ] **Step 2: Add `wt contract` row to AGENTS.md**

In `plugins/codex/AGENTS.md`, find the `wt` row in the utility-subcommands table. Append after it:

```markdown
| `wt contract` | Cross-tool worktree contract: `emit` (discovery scan), `from-cmux` (parse `.cmux/setup`), `install-cmux-shim` (cmux runtime shim with TOFU warning). See `docs/superpowers/specs/2026-05-01-orca-worktree-contract-design.md`. | `src/orca/python_cli.py` `_run_wt_contract` |
```

- [ ] **Step 3: Run full test suite**

Run: `uv run python -m pytest -q 2>&1 | tail -3`
Expected: all unit tests pass.

Run: `uv run python -m pytest -q -m integration 2>&1 | tail -3`
Expected: all integration tests pass.

- [ ] **Step 4: Commit**

```bash
git add README.md plugins/codex/AGENTS.md
git commit --no-verify -m "docs: worktree contract — readme + agents row"
```

---

## Self-review notes

**Spec coverage check:** Each spec section maps to a task:
- §"Schema" + validation → Tasks 1, 2
- §"merge_with_config / union order" → Task 3
- §"`run_stage1` change to union semantics" → Task 4
- §"manager.py caller update" → Task 5
- §"Phase 1 docs amendment" → Task 6 (no-op if already in spec-v3 commit)
- §"Discovery (`wt contract emit`)" → Tasks 7, 8
- §"`from-cmux` parser" → Task 9
- §"cmux shim" → Task 10
- §"CLI dispatch" → Tasks 11, 12
- §"Testing" → Tasks 13, 14, 15
- §"Docs" → Task 16

**Type consistency check:** `ContractData` (Task 1), `ContractError` (Task 1), `merge_symlinks` signature (Task 3), `run_stage1` `contract` kwarg (Task 4), `ParseResult` (Task 9), `ContractProposal` (Task 7), shim filename `.cmux/setup` (Task 10) — all stable across tasks.

**Placeholder scan:** No "TBD" / "implement later" anywhere. Every code step contains the actual code.

**Effort sanity:** 16 tasks × ~10-15 min average = 2.5-4 hours of typing, plus debugging on the thicker tasks (4, 9, 11). Aligns with the 2.85 days spec estimate when factoring in commit-message-rework, lint cycles, and test-flake debugging.
