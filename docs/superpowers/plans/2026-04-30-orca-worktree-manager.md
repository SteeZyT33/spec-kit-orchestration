# Orca Worktree Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `orca-cli wt new/start/cd/ls/merge/rm/init/config/version/doctor` — opinionated tmux-mediated worktree manager with cmux-parity command surface, host-aware auto-symlinks, TOFU hook trust ledger, and lifecycle observability.

**Architecture:** New `src/orca/core/worktrees/` package (8 files, decoupled). CLI verbs registered as `_run_wt_*` in `python_cli.py`. Persistence: `.orca/worktrees/registry.json` (schema v2) + per-lane sidecars + append-only `events.jsonl`. tmux acts as substrate via `subprocess` (one session per repo, one window per lane). Trust ledger at `~/.config/orca/worktree-trust.json` keyed by remote URL. Cross-platform: Linux/macOS/WSL full; Windows native via `--no-tmux`.

**Tech Stack:** Python 3.10+, pytest, `pathlib`, `fcntl` (POSIX) / `msvcrt` (Windows), `subprocess`, `tomli`/`tomli_w`, `tomllib` on 3.11+. tmux ≥ 1.7. git ≥ 2.5 (worktree support).

**Spec:** `docs/superpowers/specs/2026-04-30-orca-worktree-manager-design.md` (commit `a216e14`, v3 post-round-2-review).

**Worktree:** `/home/taylor/worktrees/spec-kit-orca/orca-worktree-manager`. Branch: `orca-worktree-manager`.

**Test runner:** `uv run python -m pytest`.

**Hard prerequisite (already met):** `src/orca/core/path_safety.py` exists (verified in Task 0). The plan uses `validate_identifier` and `validate_repo_dir` directly.

---

## File map

### New files (worktree manager core)

| Path | Responsibility |
|---|---|
| `src/orca/core/worktrees/__init__.py` | Public exports |
| `src/orca/core/worktrees/protocol.py` | `WorktreeManager` Protocol |
| `src/orca/core/worktrees/identifiers.py` | Lane-id derivation, repo-key sanitization |
| `src/orca/core/worktrees/config.py` | TOML load/merge for worktrees.toml + worktrees.local.toml |
| `src/orca/core/worktrees/layout.py` | Base path resolution, lane-id mode dispatch |
| `src/orca/core/worktrees/registry.py` | Sidecar + registry.json + events.jsonl + locking + migrator |
| `src/orca/core/worktrees/symlinks.py` | Atomic-rename symlink layer (Stage 1 auto-symlink) |
| `src/orca/core/worktrees/trust.py` | TOFU ledger load/store + prompt flow |
| `src/orca/core/worktrees/hooks.py` | Stage 2/3/4 hook execution + env contract |
| `src/orca/core/worktrees/tmux.py` | tmux subprocess wrapper + {repo} sanitization |
| `src/orca/core/worktrees/agent_launch.py` | Prompt-file + launcher-script pattern |
| `src/orca/core/worktrees/manager.py` | Orchestrator: create/remove/list against state cube |
| `src/orca/core/worktrees/init_script.py` | Ecosystem detection + after_create generation |

### New CLI handlers

| Path | Lines added | Responsibility |
|---|---|---|
| `src/orca/python_cli.py` | ~600 LOC | `_run_wt_new`, `_run_wt_start`, `_run_wt_cd`, `_run_wt_ls`, `_run_wt_rm`, `_run_wt_merge`, `_run_wt_init`, `_run_wt_config`, `_run_wt_version`, `_run_wt_doctor` + dispatch from `_run_wt` |

### Modified files

| Path | Lines changed | Why |
|---|---|---|
| `src/orca/sdd_adapter.py:799-845` | ~15 LOC | Defensive normalize for v1+v2 registry shapes; mixed-entry tolerance |
| `src/orca/python_cli.py` | top-level | Register `wt` capability |
| `src/orca/core/adoption/wizard.py` | ~10 LOC | `[orca] enabled_features = ["worktrees"]` default |
| `src/orca/core/adoption/apply.py` | ~20 LOC | Run `wt init` non-interactive when worktrees enabled |
| `scripts/bash/orca-doctor.sh` | ~15 LOC | Warn on missing worktrees.toml when feature enabled |
| `plugins/codex/AGENTS.md` | ~3 LOC | Add `wt` row to utility-subcommand table |
| `README.md` | ~30 LOC | Worktree manager section |

### New tests

| Path | Test count |
|---|---|
| `tests/core/worktrees/test_identifiers.py` | 12 |
| `tests/core/worktrees/test_config.py` | 8 |
| `tests/core/worktrees/test_layout.py` | 6 |
| `tests/core/worktrees/test_registry.py` | 14 |
| `tests/core/worktrees/test_symlinks.py` | 8 |
| `tests/core/worktrees/test_trust.py` | 10 |
| `tests/core/worktrees/test_hooks.py` | 6 |
| `tests/core/worktrees/test_tmux.py` | 8 |
| `tests/core/worktrees/test_agent_launch.py` | 6 |
| `tests/core/worktrees/test_manager.py` | 14 (state cube) |
| `tests/core/worktrees/test_init_script.py` | 6 |
| `tests/cli/test_wt_cli.py` | 18 |
| `tests/integration/test_wt_dogfood.py` | 5 (gated `-m integration`) |
| `tests/integration/test_wt_concurrent_writes.py` | 3 (gated `-m integration`) |

---

## Task 0: Verify prerequisites + create scaffolding

**Files:**
- Create: `src/orca/core/worktrees/__init__.py`
- Create: `tests/core/worktrees/__init__.py`

- [ ] **Step 1: Verify path_safety prerequisite**

Run: `uv run python -c "from orca.core.path_safety import validate_identifier, validate_repo_dir, PathSafetyError; print('ok')"`

Expected: `ok`. If this fails, STOP and complete the path-safety consolidation plan first.

- [ ] **Step 2: Verify tmux availability for integration tests**

Run: `tmux -V`

Expected: `tmux 1.7` or higher. Document the version in your worklog.

- [ ] **Step 3: Create empty package files**

```python
# src/orca/core/worktrees/__init__.py
"""Orca worktree manager: opinionated git worktree + tmux + lifecycle hooks.

See docs/superpowers/specs/2026-04-30-orca-worktree-manager-design.md.
"""
```

```python
# tests/core/worktrees/__init__.py
```

- [ ] **Step 4: Verify imports work**

Run: `uv run python -c "import orca.core.worktrees"`

Expected: no output (success).

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/__init__.py tests/core/worktrees/__init__.py
git commit -m "feat(worktrees): scaffold core.worktrees package"
```

---

## Task 1: Identifiers module — lane-id derivation + repo-key sanitization

**Files:**
- Create: `src/orca/core/worktrees/identifiers.py`
- Test: `tests/core/worktrees/test_identifiers.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/worktrees/test_identifiers.py
import pytest
from orca.core.worktrees.identifiers import (
    derive_lane_id,
    sanitize_repo_name,
    LaneIdMode,
)
from orca.core.path_safety import PathSafetyError


class TestDeriveLaneIdBranchMode:
    def test_simple_branch_passes_through(self):
        assert derive_lane_id(branch="feature-foo", mode="branch") == "feature-foo"

    def test_slashes_replaced_with_hyphens(self):
        assert derive_lane_id(branch="feature/foo", mode="branch") == "feature-foo"

    def test_special_chars_replaced_with_underscore(self):
        assert derive_lane_id(branch="feat@2.0!", mode="branch") == "feat_2.0_"

    def test_max_length_128_enforced(self):
        long = "a" * 200
        with pytest.raises(PathSafetyError):
            derive_lane_id(branch=long, mode="branch")


class TestDeriveLaneIdLaneMode:
    def test_feature_lane_combines(self):
        assert derive_lane_id(branch="feature/015-wizard",
                              mode="lane",
                              feature="015",
                              lane="wizard") == "015-wizard"

    def test_lane_mode_requires_feature_and_lane(self):
        with pytest.raises(ValueError, match="lane mode requires"):
            derive_lane_id(branch="x", mode="lane")


class TestDeriveLaneIdAuto:
    def test_auto_with_feature_and_lane_uses_lane_mode(self):
        assert derive_lane_id(branch="x", mode="auto",
                              feature="015", lane="wiz") == "015-wiz"

    def test_auto_without_feature_uses_branch_mode(self):
        assert derive_lane_id(branch="x/y", mode="auto") == "x-y"


class TestSanitizeRepoName:
    def test_clean_name_passes(self):
        assert sanitize_repo_name("orca") == "orca"

    def test_dot_replaced(self):
        # tmux target syntax uses : and .; both replaced
        assert sanitize_repo_name("my.repo") == "my_repo"

    def test_colon_replaced(self):
        assert sanitize_repo_name("repo:branch") == "repo_branch"

    def test_truncated_to_64(self):
        assert len(sanitize_repo_name("a" * 100)) == 64
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_identifiers.py -v`
Expected: ImportError (module not yet created).

- [ ] **Step 3: Implement**

```python
# src/orca/core/worktrees/identifiers.py
"""Lane-id derivation + repo-key sanitization for worktree manager."""
from __future__ import annotations

import re
from typing import Literal

from orca.core.path_safety import validate_identifier

LaneIdMode = Literal["branch", "lane", "auto"]

_BRANCH_SLASH_RE = re.compile(r"/")
_BRANCH_OTHER_RE = re.compile(r"[^A-Za-z0-9._-]")
_REPO_RE = re.compile(r"[^A-Za-z0-9_-]")  # NOTE: . and : both excluded
_REPO_MAX = 64


def _sanitize_branch(branch: str) -> str:
    s = _BRANCH_SLASH_RE.sub("-", branch)
    s = _BRANCH_OTHER_RE.sub("_", s)
    return s


def derive_lane_id(
    *,
    branch: str,
    mode: LaneIdMode,
    feature: str | None = None,
    lane: str | None = None,
) -> str:
    """Derive a lane-id per the configured mode. Validates against path-safety
    Class D (`[A-Za-z0-9._-]+`, max 128, not `.` / `..`)."""
    if mode == "lane":
        if not feature or not lane:
            raise ValueError(
                "lane mode requires both feature and lane arguments"
            )
        candidate = f"{feature}-{lane}"
    elif mode == "auto":
        if feature and lane:
            candidate = f"{feature}-{lane}"
        else:
            candidate = _sanitize_branch(branch)
    else:  # "branch"
        candidate = _sanitize_branch(branch)

    return validate_identifier(candidate, field="lane_id", max_length=128)


def sanitize_repo_name(name: str) -> str:
    """Sanitize a repo basename for safe tmux session-name templating.

    More restrictive than lane-id sanitization: also replaces `.` and `:`
    (tmux target syntax). Truncated to 64 chars.
    """
    s = _REPO_RE.sub("_", name)
    return s[:_REPO_MAX]
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_identifiers.py -v`
Expected: all 12 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/identifiers.py tests/core/worktrees/test_identifiers.py
git commit -m "feat(worktrees): lane-id derivation + repo-key sanitization"
```

---

## Task 2: Config module — worktrees.toml + local override merge

**Files:**
- Create: `src/orca/core/worktrees/config.py`
- Test: `tests/core/worktrees/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/worktrees/test_config.py
import pytest
from pathlib import Path
import textwrap

from orca.core.worktrees.config import (
    WorktreesConfig,
    load_config,
    write_default_config,
    ConfigError,
)


def _make_repo(tmp_path: Path, committed: str = "", local: str = "") -> Path:
    (tmp_path / ".orca").mkdir()
    if committed:
        (tmp_path / ".orca" / "worktrees.toml").write_text(committed)
    if local:
        (tmp_path / ".orca" / "worktrees.local.toml").write_text(local)
    return tmp_path


class TestLoadConfig:
    def test_missing_files_returns_defaults(self, tmp_path):
        repo = _make_repo(tmp_path)
        cfg = load_config(repo)
        assert cfg.base == ".orca/worktrees"
        assert cfg.lane_id_mode == "auto"
        assert cfg.tmux_session == "orca"
        assert cfg.default_agent == "claude"

    def test_committed_overrides_defaults(self, tmp_path):
        committed = textwrap.dedent("""
            [worktrees]
            schema_version = 1
            base = ".worktrees"
            lane_id_mode = "branch"
        """)
        repo = _make_repo(tmp_path, committed=committed)
        cfg = load_config(repo)
        assert cfg.base == ".worktrees"
        assert cfg.lane_id_mode == "branch"

    def test_local_overrides_committed(self, tmp_path):
        committed = '[worktrees]\nschema_version = 1\nbase = ".worktrees"\n'
        local = '[worktrees]\nbase = "/tmp/wt"\n'
        repo = _make_repo(tmp_path, committed=committed, local=local)
        cfg = load_config(repo)
        assert cfg.base == "/tmp/wt"

    def test_invalid_schema_version_raises(self, tmp_path):
        committed = '[worktrees]\nschema_version = 99\n'
        repo = _make_repo(tmp_path, committed=committed)
        with pytest.raises(ConfigError, match="schema_version"):
            load_config(repo)

    def test_scalar_where_list_expected_raises(self, tmp_path):
        committed = '[worktrees]\nschema_version = 1\nsymlink_paths = "specs"\n'
        repo = _make_repo(tmp_path, committed=committed)
        with pytest.raises(ConfigError, match="symlink_paths"):
            load_config(repo)

    def test_agent_command_template_loaded(self, tmp_path):
        committed = textwrap.dedent("""
            [worktrees]
            schema_version = 1
            [worktrees.agents]
            claude = "claude --custom-flag"
            codex = "codex --yolo"
        """)
        repo = _make_repo(tmp_path, committed=committed)
        cfg = load_config(repo)
        assert cfg.agents["claude"] == "claude --custom-flag"
        assert cfg.agents["codex"] == "codex --yolo"


class TestWriteDefaultConfig:
    def test_writes_committed_only_when_missing(self, tmp_path):
        repo = _make_repo(tmp_path)
        write_default_config(repo)
        assert (repo / ".orca" / "worktrees.toml").exists()
        # local is gitignored; not auto-written
        assert not (repo / ".orca" / "worktrees.local.toml").exists()

    def test_idempotent_does_not_overwrite_existing(self, tmp_path):
        committed = '[worktrees]\nschema_version = 1\nbase = "/custom"\n'
        repo = _make_repo(tmp_path, committed=committed)
        write_default_config(repo)
        # Existing committed file preserved
        assert "/custom" in (repo / ".orca" / "worktrees.toml").read_text()
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_config.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/orca/core/worktrees/config.py
"""worktrees.toml + worktrees.local.toml loader with deep-merge.

worktrees.toml: committed (set-once team policy).
worktrees.local.toml: gitignored (per-machine overrides).
Local overrides committed via TOML deep-merge, last-writer-wins per key.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

SUPPORTED_SCHEMA_VERSION = 1

_DEFAULT_AGENTS = {
    "claude": "claude --dangerously-skip-permissions",
    "codex": "codex --yolo",
}


class ConfigError(ValueError):
    """Raised when worktrees.toml schema is invalid."""


@dataclass(frozen=True)
class WorktreesConfig:
    schema_version: int = 1
    base: str = ".orca/worktrees"
    lane_id_mode: Literal["branch", "lane", "auto"] = "auto"
    symlink_paths: list[str] = field(default_factory=list)
    symlink_files: list[str] = field(
        default_factory=lambda: [".env", ".env.local", ".env.secrets"]
    )
    after_create_hook: str = "after_create"
    before_run_hook: str = "before_run"
    before_remove_hook: str = "before_remove"
    tmux_session: str = "orca"
    default_agent: Literal["claude", "codex", "none"] = "claude"
    agents: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_AGENTS))


def _require_list(d: dict[str, Any], key: str) -> list[Any]:
    if key not in d:
        return []
    value = d[key]
    if not isinstance(value, list):
        raise ConfigError(
            f"worktrees.{key} must be a list, got {type(value).__name__}"
        )
    return list(value)


def _merge(committed: dict, local: dict) -> dict:
    """Deep-merge: local overrides committed, last-writer-wins per leaf key."""
    out = dict(committed)
    for key, val in local.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], val)
        else:
            out[key] = val
    return out


def load_config(repo_root: Path) -> WorktreesConfig:
    """Load + merge worktrees.toml and worktrees.local.toml. Returns defaults
    if both are missing."""
    committed_path = repo_root / ".orca" / "worktrees.toml"
    local_path = repo_root / ".orca" / "worktrees.local.toml"

    committed: dict[str, Any] = {}
    local: dict[str, Any] = {}
    if committed_path.exists():
        committed = tomllib.loads(committed_path.read_text(encoding="utf-8"))
    if local_path.exists():
        local = tomllib.loads(local_path.read_text(encoding="utf-8"))

    merged = _merge(committed, local)
    section = merged.get("worktrees", {})
    if not section:
        return WorktreesConfig()

    schema_version = section.get("schema_version", SUPPORTED_SCHEMA_VERSION)
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ConfigError(
            f"worktrees.schema_version={schema_version} not supported; "
            f"expected {SUPPORTED_SCHEMA_VERSION}"
        )

    return WorktreesConfig(
        schema_version=schema_version,
        base=section.get("base", ".orca/worktrees"),
        lane_id_mode=section.get("lane_id_mode", "auto"),
        symlink_paths=_require_list(section, "symlink_paths"),
        symlink_files=_require_list(section, "symlink_files") or list(WorktreesConfig().symlink_files),
        after_create_hook=section.get("after_create_hook", "after_create"),
        before_run_hook=section.get("before_run_hook", "before_run"),
        before_remove_hook=section.get("before_remove_hook", "before_remove"),
        tmux_session=section.get("tmux_session", "orca"),
        default_agent=section.get("default_agent", "claude"),
        agents={**_DEFAULT_AGENTS, **section.get("agents", {})},
    )


def write_default_config(repo_root: Path) -> Path:
    """Write a default worktrees.toml if missing. Returns the path."""
    path = repo_root / ".orca" / "worktrees.toml"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "worktrees": {
            "schema_version": SUPPORTED_SCHEMA_VERSION,
            "base": ".orca/worktrees",
            "lane_id_mode": "auto",
            "tmux_session": "orca",
            "default_agent": "claude",
            "agents": dict(_DEFAULT_AGENTS),
        }
    }
    encoded = tomli_w.dumps(payload).encode("utf-8")
    tmp = path.with_suffix(".toml.partial")
    tmp.write_bytes(encoded)
    tmp.replace(path)
    return path
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_config.py -v`
Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/config.py tests/core/worktrees/test_config.py
git commit -m "feat(worktrees): TOML config loader with local override merge"
```

---

## Task 3: Layout module — base path + lane-id mode dispatch

**Files:**
- Create: `src/orca/core/worktrees/layout.py`
- Test: `tests/core/worktrees/test_layout.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/worktrees/test_layout.py
from pathlib import Path

from orca.core.worktrees.config import WorktreesConfig
from orca.core.worktrees.layout import resolve_worktree_path, resolve_base_dir


class TestResolveBaseDir:
    def test_default_relative_to_repo(self, tmp_path):
        cfg = WorktreesConfig()
        assert resolve_base_dir(tmp_path, cfg) == tmp_path / ".orca" / "worktrees"

    def test_absolute_passes_through(self, tmp_path):
        cfg = WorktreesConfig(base="/abs/path/wt")
        assert resolve_base_dir(tmp_path, cfg) == Path("/abs/path/wt")

    def test_relative_resolved_against_repo(self, tmp_path):
        cfg = WorktreesConfig(base=".worktrees")
        assert resolve_base_dir(tmp_path, cfg) == tmp_path / ".worktrees"


class TestResolveWorktreePath:
    def test_combines_base_and_lane_id(self, tmp_path):
        cfg = WorktreesConfig()
        path = resolve_worktree_path(tmp_path, cfg, lane_id="015-wizard")
        assert path == tmp_path / ".orca" / "worktrees" / "015-wizard"

    def test_with_custom_base(self, tmp_path):
        cfg = WorktreesConfig(base=".worktrees")
        path = resolve_worktree_path(tmp_path, cfg, lane_id="feature-foo")
        assert path == tmp_path / ".worktrees" / "feature-foo"

    def test_with_absolute_base(self, tmp_path):
        cfg = WorktreesConfig(base="/scratch")
        path = resolve_worktree_path(tmp_path, cfg, lane_id="x")
        assert path == Path("/scratch") / "x"
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_layout.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/orca/core/worktrees/layout.py
"""Base path resolution + worktree path layout."""
from __future__ import annotations

from pathlib import Path

from orca.core.worktrees.config import WorktreesConfig


def resolve_base_dir(repo_root: Path, cfg: WorktreesConfig) -> Path:
    """Resolve the base directory that holds worktrees.

    Absolute paths in cfg.base pass through; relative paths are resolved
    against the repo root.
    """
    base = Path(cfg.base)
    if base.is_absolute():
        return base
    return repo_root / base


def resolve_worktree_path(
    repo_root: Path, cfg: WorktreesConfig, *, lane_id: str
) -> Path:
    """Resolve the absolute worktree path for a given lane-id."""
    return resolve_base_dir(repo_root, cfg) / lane_id
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_layout.py -v`
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/layout.py tests/core/worktrees/test_layout.py
git commit -m "feat(worktrees): layout — base + worktree path resolution"
```

---

## Task 4: Sidecar dataclass + atomic write/read

**Files:**
- Create: `src/orca/core/worktrees/registry.py` (sidecar half only; registry-list functions added Task 5)
- Test: `tests/core/worktrees/test_registry.py` (sidecar tests only this task)

- [ ] **Step 1: Write failing tests**

```python
# tests/core/worktrees/test_registry.py
import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

from orca.core.worktrees.registry import (
    Sidecar,
    write_sidecar,
    read_sidecar,
    sidecar_path,
)


def _sample_sidecar() -> Sidecar:
    return Sidecar(
        schema_version=2,
        lane_id="015-wizard",
        lane_mode="lane",
        feature_id="015",
        lane_name="wizard",
        branch="feature/015-wizard",
        base_branch="main",
        worktree_path="/abs/path",
        created_at="2026-04-30T22:55:00Z",
        tmux_session="orca",
        tmux_window="015-wizard",
        agent="claude",
        setup_version="abc123",
        last_attached_at="2026-04-30T23:10:00Z",
        host_system="superpowers",
    )


class TestSidecarRoundTrip:
    def test_write_then_read(self, tmp_path):
        sc = _sample_sidecar()
        write_sidecar(tmp_path, sc)
        loaded = read_sidecar(sidecar_path(tmp_path, sc.lane_id))
        assert loaded == sc

    def test_dual_emit_legacy_fields(self, tmp_path):
        sc = _sample_sidecar()
        write_sidecar(tmp_path, sc)
        raw = json.loads(sidecar_path(tmp_path, sc.lane_id).read_text())
        # New-style fields
        assert raw["lane_id"] == "015-wizard"
        assert raw["feature_id"] == "015"
        assert raw["worktree_path"] == "/abs/path"
        # Legacy fields (for sdd_adapter._load_worktree_lanes compat)
        assert raw["id"] == "015-wizard"
        assert raw["feature"] == "015"
        assert raw["path"] == "/abs/path"
        assert raw["status"] == "active"
        assert raw["task_scope"] == []

    def test_atomic_write_no_partial_on_failure(self, tmp_path, monkeypatch):
        sc = _sample_sidecar()
        # write + ensure no .partial file lingers
        write_sidecar(tmp_path, sc)
        partials = list(tmp_path.glob("**/*.partial"))
        assert partials == []


class TestReadSidecar:
    def test_missing_file_returns_none(self, tmp_path):
        assert read_sidecar(tmp_path / "nonexistent.json") is None

    def test_corrupt_json_returns_none(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json {")
        assert read_sidecar(bad) is None
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_registry.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement (sidecar half)**

```python
# src/orca/core/worktrees/registry.py
"""Registry + sidecar persistence with atomic writes and dual-emit legacy fields.

Layout under <repo>/.orca/worktrees/:
  registry.json         schema_version 2; lanes = [{lane_id, branch, ...}]
  registry.lock         lock file for fcntl/msvcrt protection
  <lane_id>.json        per-lane sidecar; emits both v2 and legacy keys
  events.jsonl          append-only lifecycle event log
  registry.v1.bak.json  one-shot backup written by the v1->v2 migrator
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 2


@dataclass(frozen=True)
class Sidecar:
    schema_version: int
    lane_id: str
    lane_mode: str  # "branch" | "lane"
    feature_id: Optional[str]
    lane_name: Optional[str]
    branch: str
    base_branch: str
    worktree_path: str
    created_at: str  # ISO-8601 UTC
    tmux_session: str
    tmux_window: str
    agent: str  # "claude" | "codex" | "none"
    setup_version: str
    last_attached_at: Optional[str]
    host_system: str
    status: str = "active"
    task_scope: list[str] = field(default_factory=list)


def sidecar_path(worktree_root: Path, lane_id: str) -> Path:
    return worktree_root / f"{lane_id}.json"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    tmp = path.with_suffix(path.suffix + ".partial")
    try:
        tmp.write_bytes(encoded)
        tmp.replace(path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def write_sidecar(worktree_root: Path, sc: Sidecar) -> None:
    """Atomic write with dual-emit legacy fields for sdd_adapter compat."""
    payload = asdict(sc)
    # Dual-emit: legacy field names alongside v2 names. Read-side compat
    # for src/orca/sdd_adapter.py:799-845.
    payload["id"] = sc.lane_id
    payload["feature"] = sc.feature_id
    payload["path"] = sc.worktree_path
    _atomic_write_json(sidecar_path(worktree_root, sc.lane_id), payload)


def read_sidecar(path: Path) -> Sidecar | None:
    """Read a sidecar; return None if missing or corrupt."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    try:
        return Sidecar(
            schema_version=data["schema_version"],
            lane_id=data["lane_id"],
            lane_mode=data["lane_mode"],
            feature_id=data.get("feature_id"),
            lane_name=data.get("lane_name"),
            branch=data["branch"],
            base_branch=data["base_branch"],
            worktree_path=data["worktree_path"],
            created_at=data["created_at"],
            tmux_session=data["tmux_session"],
            tmux_window=data["tmux_window"],
            agent=data["agent"],
            setup_version=data["setup_version"],
            last_attached_at=data.get("last_attached_at"),
            host_system=data["host_system"],
            status=data.get("status", "active"),
            task_scope=data.get("task_scope", []),
        )
    except KeyError:
        return None
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_registry.py -v`
Expected: 5 tests pass (others added in Task 5).

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/registry.py tests/core/worktrees/test_registry.py
git commit -m "feat(worktrees): sidecar dataclass + atomic write with dual-emit fields"
```

---

## Task 5: Registry list (lanes) + atomic-rename writer

**Files:**
- Modify: `src/orca/core/worktrees/registry.py` (add registry-list functions)
- Modify: `tests/core/worktrees/test_registry.py` (add registry tests)

- [ ] **Step 1: Add failing tests**

Append to `tests/core/worktrees/test_registry.py`:

```python
from orca.core.worktrees.registry import (
    LaneRow, RegistryView, read_registry, write_registry, registry_path,
)


class TestRegistryRoundTrip:
    def test_write_then_read_v2(self, tmp_path):
        rows = [
            LaneRow(lane_id="015-wiz", branch="feature/015-wiz",
                    worktree_path=str(tmp_path / "015-wiz"), feature_id="015"),
            LaneRow(lane_id="016-tst", branch="feature/016-tst",
                    worktree_path=str(tmp_path / "016-tst"), feature_id="016"),
        ]
        write_registry(tmp_path, rows)
        view = read_registry(tmp_path)
        assert view.schema_version == 2
        assert len(view.lanes) == 2
        assert view.lanes[0].lane_id == "015-wiz"

    def test_read_missing_returns_empty_v2_view(self, tmp_path):
        view = read_registry(tmp_path)
        assert view.schema_version == 2
        assert view.lanes == []

    def test_atomic_rename_no_partial_artifact(self, tmp_path):
        write_registry(tmp_path, [])
        partials = list(tmp_path.glob("*.partial"))
        assert partials == []
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_registry.py -v`
Expected: 3 new tests fail with ImportError on `LaneRow`.

- [ ] **Step 3: Add to `src/orca/core/worktrees/registry.py`**

```python
@dataclass(frozen=True)
class LaneRow:
    lane_id: str
    branch: str
    worktree_path: str
    feature_id: Optional[str] = None


@dataclass(frozen=True)
class RegistryView:
    schema_version: int
    lanes: list[LaneRow]


def registry_path(worktree_root: Path) -> Path:
    return worktree_root / "registry.json"


def write_registry(worktree_root: Path, lanes: list[LaneRow]) -> None:
    """Atomic write of v2 registry. Caller must hold the registry lock."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "lanes": [asdict(row) for row in lanes],
    }
    _atomic_write_json(registry_path(worktree_root), payload)


def read_registry(worktree_root: Path) -> RegistryView:
    """Read v2 registry. Returns empty view if missing or corrupt.

    Tolerates v1 (string lanes) by normalizing on read; full migration is
    handled by `migrate_v1_to_v2` (Task 8). This function is read-only and
    does NOT mutate the registry on disk.
    """
    path = registry_path(worktree_root)
    if not path.exists():
        return RegistryView(schema_version=SCHEMA_VERSION, lanes=[])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return RegistryView(schema_version=SCHEMA_VERSION, lanes=[])

    raw_lanes = data.get("lanes", [])
    rows: list[LaneRow] = []
    for entry in raw_lanes:
        if isinstance(entry, str):
            # v1 shape: string lane-id only. Hydrate from sidecar if present.
            sc = read_sidecar(sidecar_path(worktree_root, entry))
            if sc is not None:
                rows.append(LaneRow(
                    lane_id=sc.lane_id,
                    branch=sc.branch,
                    worktree_path=sc.worktree_path,
                    feature_id=sc.feature_id,
                ))
        elif isinstance(entry, dict):
            try:
                rows.append(LaneRow(
                    lane_id=entry["lane_id"],
                    branch=entry["branch"],
                    worktree_path=entry["worktree_path"],
                    feature_id=entry.get("feature_id"),
                ))
            except KeyError:
                continue
        # Other types: skip silently
    return RegistryView(
        schema_version=data.get("schema_version", 1),
        lanes=rows,
    )
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_registry.py -v`
Expected: 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/registry.py tests/core/worktrees/test_registry.py
git commit -m "feat(worktrees): v2 registry read/write with v1 string-lane tolerance"
```

---

## Task 6: Concurrent-write locking — POSIX fcntl

**Files:**
- Modify: `src/orca/core/worktrees/registry.py`
- Modify: `tests/core/worktrees/test_registry.py`

- [ ] **Step 1: Add failing test**

```python
# Append to tests/core/worktrees/test_registry.py
import multiprocessing as mp
import sys
import pytest

from orca.core.worktrees.registry import (
    acquire_registry_lock, LockTimeout, write_registry, LaneRow,
)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX fcntl path")
class TestRegistryLockingPosix:
    def test_lock_acquire_release(self, tmp_path):
        with acquire_registry_lock(tmp_path, timeout_s=1.0):
            pass  # acquired and released without raising

    def test_lock_timeout_when_held(self, tmp_path):
        # Hold the lock and try to acquire from another thread; should timeout.
        import threading
        held = threading.Event()
        release = threading.Event()
        def holder():
            with acquire_registry_lock(tmp_path, timeout_s=5.0):
                held.set()
                release.wait()
        t = threading.Thread(target=holder)
        t.start()
        held.wait(timeout=2.0)
        with pytest.raises(LockTimeout):
            with acquire_registry_lock(tmp_path, timeout_s=0.2):
                pass
        release.set()
        t.join()
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_registry.py::TestRegistryLockingPosix -v`
Expected: ImportError on `acquire_registry_lock`.

- [ ] **Step 3: Add to `src/orca/core/worktrees/registry.py`**

```python
import contextlib
import errno
import os
import sys
import time

# At module top, near SCHEMA_VERSION
LOCK_FILENAME = "registry.lock"
DEFAULT_LOCK_TIMEOUT_S = 30.0


class LockTimeout(RuntimeError):
    """Raised when registry lock cannot be acquired within the timeout."""


def _lock_path(worktree_root: Path) -> Path:
    return worktree_root / LOCK_FILENAME


def _ensure_lock_file(path: Path) -> None:
    """Create the lock file with a 1-byte sentinel if missing.

    Windows msvcrt.locking on a 0-byte file returns EINVAL; the sentinel
    ensures byte 0 exists for both POSIX (where it's harmless) and Windows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with open(path, "wb") as f:
            f.write(b"\0")


@contextlib.contextmanager
def acquire_registry_lock(
    worktree_root: Path,
    *,
    timeout_s: float | None = None,
):
    """Acquire an exclusive lock on registry.lock for the duration of the
    `with` block. Cross-platform: fcntl on POSIX, msvcrt on Windows.

    Raises LockTimeout if the lock cannot be acquired within timeout_s.
    """
    timeout = timeout_s if timeout_s is not None else float(
        os.environ.get("ORCA_WT_LOCK_TIMEOUT", DEFAULT_LOCK_TIMEOUT_S)
    )
    path = _lock_path(worktree_root)
    _ensure_lock_file(path)

    if sys.platform == "win32":
        ctx = _windows_lock(path, timeout)
    else:
        ctx = _posix_lock(path, timeout)

    with ctx:
        yield


@contextlib.contextmanager
def _posix_lock(path: Path, timeout: float):
    import fcntl
    fd = os.open(str(path), os.O_RDWR)
    deadline = time.monotonic() + timeout
    attempt = 0
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as e:
                if e.errno not in (errno.EAGAIN, errno.EACCES):
                    raise
                if time.monotonic() >= deadline:
                    raise LockTimeout(
                        f"could not acquire {path} within {timeout}s"
                    ) from e
                time.sleep(min(0.05 * (2 ** attempt), 0.5))
                attempt += 1
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_registry.py -v`
Expected: 10 tests pass (POSIX-only locking tests run; Windows skipped).

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/registry.py tests/core/worktrees/test_registry.py
git commit -m "feat(worktrees): POSIX fcntl registry lock with backoff"
```

---

## Task 7: Concurrent-write locking — Windows msvcrt path (gated)

**Files:**
- Modify: `src/orca/core/worktrees/registry.py`
- Modify: `tests/core/worktrees/test_registry.py`

- [ ] **Step 1: Add failing tests (Windows-gated)**

```python
# Append to tests/core/worktrees/test_registry.py
@pytest.mark.skipif(sys.platform != "win32", reason="Windows msvcrt path")
@pytest.mark.windows
class TestRegistryLockingWindows:
    def test_lock_acquire_release(self, tmp_path):
        with acquire_registry_lock(tmp_path, timeout_s=1.0):
            pass

    def test_lock_timeout_when_held(self, tmp_path):
        import threading
        held = threading.Event()
        release = threading.Event()
        def holder():
            with acquire_registry_lock(tmp_path, timeout_s=5.0):
                held.set()
                release.wait()
        t = threading.Thread(target=holder)
        t.start()
        held.wait(timeout=2.0)
        with pytest.raises(LockTimeout):
            with acquire_registry_lock(tmp_path, timeout_s=0.2):
                pass
        release.set()
        t.join()
```

- [ ] **Step 2: Register windows marker**

Add to `pyproject.toml` under `[tool.pytest.ini_options].markers`:
```toml
"windows: tests requiring Windows host"
```

- [ ] **Step 3: Run on POSIX (Windows tests skipped)**

Run: `uv run python -m pytest tests/core/worktrees/test_registry.py -v`
Expected: Windows tests show as `skipped` on POSIX; POSIX tests pass.

- [ ] **Step 4: Add Windows lock implementation to `src/orca/core/worktrees/registry.py`**

```python
@contextlib.contextmanager
def _windows_lock(path: Path, timeout: float):
    """Windows msvcrt mandatory byte-range lock on byte 0, length 1.

    Uses LK_NBLCK (non-blocking) + retry loop. Avoids LK_LOCK because
    Windows blocking locks can deadlock when the holder is itself blocked.
    """
    import msvcrt  # type: ignore[import-not-found]
    fd = os.open(str(path), os.O_RDWR)
    deadline = time.monotonic() + timeout
    attempt = 0
    locked = False
    try:
        while True:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                locked = True
                break
            except OSError as e:
                if e.errno not in (errno.EACCES, errno.EDEADLK):
                    raise
                if time.monotonic() >= deadline:
                    raise LockTimeout(
                        f"could not acquire {path} within {timeout}s"
                    ) from e
                time.sleep(min(0.1 * (2 ** attempt), 1.0))
                attempt += 1
        yield
    finally:
        if locked:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        os.close(fd)
```

- [ ] **Step 5: Verify lint passes**

Run: `uv run python -m pytest tests/core/worktrees/test_registry.py -v`
Expected: same as before (Windows tests still skipped on POSIX).

- [ ] **Step 6: Commit**

```bash
git add src/orca/core/worktrees/registry.py tests/core/worktrees/test_registry.py pyproject.toml
git commit -m "feat(worktrees): Windows msvcrt LK_NBLCK lock with backoff"
```

---

## Task 8: Schema v1 → v2 migrator

**Files:**
- Modify: `src/orca/core/worktrees/registry.py`
- Modify: `tests/core/worktrees/test_registry.py`

- [ ] **Step 1: Add failing tests**

```python
# Append to tests/core/worktrees/test_registry.py
from orca.core.worktrees.registry import migrate_v1_to_v2


class TestMigrator:
    def _write_v1(self, tmp_path: Path, lane_ids: list[str]) -> None:
        registry = {"lanes": lane_ids}  # NO schema_version (v1)
        registry_path(tmp_path).write_text(json.dumps(registry))

    def test_migrate_string_lanes_to_objects(self, tmp_path):
        # Arrange: v1 registry + matching sidecars
        self._write_v1(tmp_path, ["015-wiz"])
        sc = _sample_sidecar()
        write_sidecar(tmp_path, sc)

        # Act
        migrated = migrate_v1_to_v2(tmp_path)

        # Assert
        assert migrated is True
        view = read_registry(tmp_path)
        assert view.schema_version == 2
        assert len(view.lanes) == 1
        assert view.lanes[0].lane_id == "015-wiz"
        # v1 backup was preserved
        assert (tmp_path / "registry.v1.bak.json").exists()

    def test_migrate_idempotent_on_v2(self, tmp_path):
        write_registry(tmp_path, [
            LaneRow("x", "feature/x", "/p", None),
        ])
        # Already v2; migrator returns False (no change)
        assert migrate_v1_to_v2(tmp_path) is False
        # No backup written
        assert not (tmp_path / "registry.v1.bak.json").exists()

    def test_migrate_skips_when_registry_missing(self, tmp_path):
        assert migrate_v1_to_v2(tmp_path) is False
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_registry.py::TestMigrator -v`
Expected: ImportError.

- [ ] **Step 3: Add to `src/orca/core/worktrees/registry.py`**

```python
def migrate_v1_to_v2(worktree_root: Path) -> bool:
    """Migrate a v1 (string-lane) registry to v2 (object-lane) shape.

    Returns True if migration was performed, False if no-op (already v2 or
    no registry). Backs up the v1 file as registry.v1.bak.json before write.
    Caller should hold the registry lock when invoking this.
    """
    path = registry_path(worktree_root)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    if data.get("schema_version") == SCHEMA_VERSION:
        return False  # already v2

    raw_lanes = data.get("lanes", [])
    rows: list[LaneRow] = []
    for entry in raw_lanes:
        if isinstance(entry, str):
            sc = read_sidecar(sidecar_path(worktree_root, entry))
            if sc is not None:
                rows.append(LaneRow(
                    lane_id=sc.lane_id,
                    branch=sc.branch,
                    worktree_path=sc.worktree_path,
                    feature_id=sc.feature_id,
                ))
        elif isinstance(entry, dict) and "lane_id" in entry:
            rows.append(LaneRow(
                lane_id=entry["lane_id"],
                branch=entry["branch"],
                worktree_path=entry["worktree_path"],
                feature_id=entry.get("feature_id"),
            ))

    backup = worktree_root / "registry.v1.bak.json"
    backup.write_bytes(path.read_bytes())
    write_registry(worktree_root, rows)
    return True
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_registry.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/registry.py tests/core/worktrees/test_registry.py
git commit -m "feat(worktrees): one-shot v1 -> v2 registry migrator"
```

---

## Task 9: sdd_adapter._load_worktree_lanes defensive normalize

**Files:**
- Modify: `src/orca/sdd_adapter.py:799-845`
- Test: `tests/test_sdd_adapter_worktree_lanes.py` (existing or new)

- [ ] **Step 1: Locate existing tests**

Run: `grep -rn "load_worktree_lanes\|_load_worktree_lanes" tests/ | head -5`

- [ ] **Step 2: Write failing test for v2 reader compatibility**

Create or extend with:

```python
# tests/test_sdd_adapter_worktree_lanes.py (append)
import json
from pathlib import Path

from orca.sdd_adapter import OrcaAdapter


def test_reader_handles_v2_object_lanes(tmp_path):
    repo = tmp_path
    wt_root = repo / ".orca" / "worktrees"
    wt_root.mkdir(parents=True)

    # v2 registry: list of objects
    (wt_root / "registry.json").write_text(json.dumps({
        "schema_version": 2,
        "lanes": [
            {"lane_id": "015-wiz", "branch": "feature/015-wiz",
             "worktree_path": str(wt_root / "015-wiz"), "feature_id": "015"},
        ],
    }))
    # Sidecar with both v2 and legacy field names
    (wt_root / "015-wiz.json").write_text(json.dumps({
        "id": "015-wiz",        # legacy
        "feature": "015",        # legacy (matches feature_id arg)
        "branch": "feature/015-wiz",
        "path": str(wt_root / "015-wiz"),  # legacy
        "status": "active",
        "task_scope": [],
    }))

    lanes = OrcaAdapter._load_worktree_lanes(repo, "015")
    assert len(lanes) == 1
    assert lanes[0].lane_id == "015-wiz"


def test_reader_skips_unknown_lane_entry_types(tmp_path):
    repo = tmp_path
    wt_root = repo / ".orca" / "worktrees"
    wt_root.mkdir(parents=True)
    # Mixed: one object, one string (v1 stragglers), one bogus number
    (wt_root / "registry.json").write_text(json.dumps({
        "schema_version": 2,
        "lanes": [
            {"lane_id": "a", "branch": "b", "worktree_path": "/p", "feature_id": "X"},
            "string-lane",
            42,
        ],
    }))
    # Sidecars
    (wt_root / "a.json").write_text(json.dumps({
        "id": "a", "feature": "X", "branch": "b", "path": "/p",
        "status": "active", "task_scope": [],
    }))
    (wt_root / "string-lane.json").write_text(json.dumps({
        "id": "string-lane", "feature": "X", "branch": "z", "path": "/q",
        "status": "active", "task_scope": [],
    }))

    lanes = OrcaAdapter._load_worktree_lanes(repo, "X")
    # The numeric entry is skipped silently; the other two normalize.
    lane_ids = sorted(l.lane_id for l in lanes)
    assert lane_ids == ["a", "string-lane"]
```

- [ ] **Step 3: Run failing**

Run: `uv run python -m pytest tests/test_sdd_adapter_worktree_lanes.py -v`
Expected: failure (current reader builds `Path / dict`).

- [ ] **Step 4: Update `src/orca/sdd_adapter.py:799-845`**

Replace the loop body in `_load_worktree_lanes`:

```python
        lane_ids_raw = registry.get("lanes", [])
        if not isinstance(lane_ids_raw, list):
            return []

        # Normalize defensively: v1 emits strings, v2 emits objects.
        # Mixed lists (partial migration) are tolerated; unknown entry
        # types are logged-and-skipped via the silent continue.
        normalized_ids: list[str] = []
        for entry in lane_ids_raw:
            if isinstance(entry, str):
                normalized_ids.append(entry)
            elif isinstance(entry, dict) and isinstance(entry.get("lane_id"), str):
                normalized_ids.append(entry["lane_id"])
            else:
                # Unknown shape; skip rather than raise — preserves
                # older-orca behavior of returning [] on malformed data.
                continue

        lanes: list[NormalizedWorktreeLane] = []
        for lane_id in normalized_ids:
            lane_path = worktree_root / f"{lane_id}.json"
            if not lane_path.exists():
                continue
            try:
                lane = json.loads(lane_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue

            if (
                lane.get("feature") != feature_id
                and lane.get("id") != feature_id
            ):
                continue

            task_scope = lane.get("task_scope", [])
            lanes.append(
                NormalizedWorktreeLane(
                    lane_id=lane.get("id", lane_id),
                    branch=lane.get("branch"),
                    status=lane.get("status"),
                    path=lane.get("path"),
                    task_scope=task_scope if isinstance(task_scope, list) else [],
                )
            )
        return lanes
```

- [ ] **Step 5: Run passing**

Run: `uv run python -m pytest tests/test_sdd_adapter_worktree_lanes.py tests/test_sdd_adapter.py -v`
Expected: all tests pass; existing v1 tests unbroken.

- [ ] **Step 6: Commit**

```bash
git add src/orca/sdd_adapter.py tests/test_sdd_adapter_worktree_lanes.py
git commit -m "fix(sdd_adapter): defensive normalize for v1+v2 worktree registry"
```

---

## Task 10: Lifecycle event log (events.jsonl)

**Files:**
- Create: `src/orca/core/worktrees/events.py`
- Test: `tests/core/worktrees/test_events.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/worktrees/test_events.py
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from orca.core.worktrees.events import emit_event, read_events, EVENT_VOCAB


class TestEmitEvent:
    def test_appends_jsonl_line(self, tmp_path):
        emit_event(tmp_path, event="lane.created",
                   lane_id="015-wiz", branch="feature/015-wiz")
        log = (tmp_path / "events.jsonl").read_text()
        line = json.loads(log.strip())
        assert line["event"] == "lane.created"
        assert line["lane_id"] == "015-wiz"
        assert "ts" in line  # ISO-8601 timestamp injected

    def test_appends_not_overwrites(self, tmp_path):
        emit_event(tmp_path, event="lane.created", lane_id="a")
        emit_event(tmp_path, event="lane.removed", lane_id="a")
        lines = [json.loads(l) for l in
                 (tmp_path / "events.jsonl").read_text().splitlines()]
        assert len(lines) == 2
        assert lines[0]["event"] == "lane.created"
        assert lines[1]["event"] == "lane.removed"

    def test_unknown_event_raises(self, tmp_path):
        with pytest.raises(ValueError, match="not in event vocabulary"):
            emit_event(tmp_path, event="lane.exploded", lane_id="x")

    def test_extra_fields_pass_through(self, tmp_path):
        emit_event(tmp_path, event="setup.after_create.completed",
                   lane_id="x", duration_ms=2340, exit_code=0)
        line = json.loads((tmp_path / "events.jsonl").read_text())
        assert line["duration_ms"] == 2340
        assert line["exit_code"] == 0


class TestReadEvents:
    def test_empty_log_returns_empty(self, tmp_path):
        assert read_events(tmp_path) == []

    def test_skips_corrupt_lines(self, tmp_path):
        log = tmp_path / "events.jsonl"
        log.write_text(
            json.dumps({"ts": "x", "event": "lane.created", "lane_id": "a"}) +
            "\n{not json\n" +
            json.dumps({"ts": "y", "event": "lane.removed", "lane_id": "a"}) +
            "\n"
        )
        events = read_events(tmp_path)
        assert len(events) == 2
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_events.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/orca/core/worktrees/events.py
"""Append-only lifecycle event log at .orca/worktrees/events.jsonl.

Closed event vocabulary: new events require contract bump.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVENT_VOCAB = frozenset({
    "lane.created", "lane.attached", "lane.removed",
    "setup.after_create.started", "setup.after_create.completed",
    "setup.after_create.failed",
    "setup.before_run.started", "setup.before_run.completed",
    "setup.before_run.failed",
    "setup.before_remove.started", "setup.before_remove.completed",
    "setup.before_remove.failed",
    "tmux.window.created", "tmux.window.killed",
    "tmux.session.created", "tmux.session.killed",
    "agent.launched", "agent.exited",
})

EVENTS_FILENAME = "events.jsonl"


def emit_event(
    worktree_root: Path,
    *,
    event: str,
    lane_id: str,
    **fields: Any,
) -> None:
    """Append one event line to events.jsonl."""
    if event not in EVENT_VOCAB:
        raise ValueError(
            f"event {event!r} not in event vocabulary "
            f"(see EVENT_VOCAB; contract bump required to add)"
        )
    worktree_root.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        "lane_id": lane_id,
    }
    payload.update(fields)
    line = json.dumps(payload, sort_keys=True)
    with open(worktree_root / EVENTS_FILENAME, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_events(worktree_root: Path) -> list[dict[str, Any]]:
    """Read all events; skips corrupt lines."""
    path = worktree_root / EVENTS_FILENAME
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_events.py -v`
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/events.py tests/core/worktrees/test_events.py
git commit -m "feat(worktrees): lifecycle event log with closed vocabulary"
```

---

## Task 11: Atomic-rename symlink helper (POSIX + Windows fallback)

**Files:**
- Create: `src/orca/core/worktrees/symlinks.py`
- Test: `tests/core/worktrees/test_symlinks.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/worktrees/test_symlinks.py
import os
import sys
from pathlib import Path

import pytest

from orca.core.worktrees.symlinks import (
    safe_symlink, SymlinkConflict,
)


@pytest.fixture
def primary_target(tmp_path: Path) -> Path:
    target = tmp_path / "primary" / ".specify"
    target.mkdir(parents=True)
    (target / "marker").write_text("hi")
    return target


class TestSafeSymlink:
    def test_creates_new_symlink(self, tmp_path, primary_target):
        link = tmp_path / "wt" / ".specify"
        link.parent.mkdir()
        safe_symlink(target=primary_target, link=link)
        assert link.is_symlink()
        assert (link / "marker").read_text() == "hi"

    def test_idempotent_when_pointing_at_correct_target(self, tmp_path, primary_target):
        link = tmp_path / "wt" / ".specify"
        link.parent.mkdir()
        safe_symlink(target=primary_target, link=link)
        # Re-call: no error, link unchanged
        safe_symlink(target=primary_target, link=link)
        assert link.is_symlink()

    def test_replaces_wrong_symlink(self, tmp_path, primary_target):
        wrong = tmp_path / "wrong"
        wrong.mkdir()
        link = tmp_path / "wt" / ".specify"
        link.parent.mkdir()
        link.symlink_to(wrong)
        safe_symlink(target=primary_target, link=link)
        # Now points at primary_target
        assert link.resolve() == primary_target.resolve()

    def test_refuses_real_directory(self, tmp_path, primary_target):
        link = tmp_path / "wt" / ".specify"
        link.parent.mkdir()
        link.mkdir()  # Real directory blocks the symlink
        with pytest.raises(SymlinkConflict, match="won't clobber"):
            safe_symlink(target=primary_target, link=link)

    def test_refuses_real_file(self, tmp_path, primary_target):
        link = tmp_path / "wt" / "marker"
        link.parent.mkdir()
        link.write_text("real")
        with pytest.raises(SymlinkConflict, match="won't clobber"):
            safe_symlink(target=primary_target, link=link)

    def test_no_partial_artifact_on_success(self, tmp_path, primary_target):
        link = tmp_path / "wt" / ".specify"
        link.parent.mkdir()
        safe_symlink(target=primary_target, link=link)
        partials = list(link.parent.glob(".specify.tmp-*"))
        assert partials == []
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_symlinks.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/orca/core/worktrees/symlinks.py
"""TOCTOU-safe symlink helper using atomic-rename pattern.

Algorithm:
  1. lstat the final path (does NOT follow symlinks)
  2. If it's a real file or directory: refuse with SymlinkConflict
  3. If it's a symlink already pointing at target: no-op
  4. Otherwise: create symlink at <final>.tmp-<pid>-<rand>, then os.replace
     to final path (atomic, immune to concurrent-replace race)

On Windows where developer-mode is unavailable, falls back to mklink /J
(directory junction) for paths; file symlinks emit a warning and skip.
"""
from __future__ import annotations

import logging
import os
import secrets
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class SymlinkConflict(RuntimeError):
    """Raised when a real file or directory blocks the desired symlink path."""


def _link_targets_match(link: Path, target: Path) -> bool:
    try:
        readlink = os.readlink(str(link))
    except OSError:
        return False
    return Path(readlink) == target or Path(readlink).resolve() == target.resolve()


def _atomic_symlink(target: Path, link: Path) -> None:
    tmp_name = f"{link.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}"
    tmp_path = link.parent / tmp_name
    try:
        os.symlink(str(target), str(tmp_path))
        os.replace(str(tmp_path), str(link))
    except OSError:
        if tmp_path.exists() or tmp_path.is_symlink():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def _windows_junction(target: Path, link: Path) -> None:
    """Windows fallback: mklink /J via cmd; only valid for directories."""
    import subprocess
    if not target.is_dir():
        logger.warning(
            "windows file-symlink unavailable for %s -> %s; skipping",
            link, target,
        )
        return
    tmp_name = f"{link.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}"
    tmp_path = link.parent / tmp_name
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(tmp_path), str(target)],
        check=True, capture_output=True,
    )
    os.replace(str(tmp_path), str(link))


def safe_symlink(*, target: Path, link: Path) -> None:
    """Create or replace a symlink at `link` pointing at `target`.

    Idempotent: existing-and-correct symlinks are no-op. Existing real
    files or directories raise SymlinkConflict (refuse to clobber).
    Atomic via tmp-rename to avoid TOCTOU.
    """
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        if _link_targets_match(link, target):
            return  # idempotent no-op
        # Wrong symlink target: replace via atomic rename
        if sys.platform == "win32":
            _windows_junction(target, link)
        else:
            _atomic_symlink(target, link)
        return
    # Not a symlink — could be a real file/dir, or absent
    if link.exists():
        raise SymlinkConflict(
            f"won't clobber unmanaged content at {link}"
        )
    if sys.platform == "win32":
        _windows_junction(target, link)
    else:
        _atomic_symlink(target, link)
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_symlinks.py -v`
Expected: 6 tests pass on POSIX (Windows tests skip naturally because the suite runs on POSIX in CI; manual Windows verification deferred).

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/symlinks.py tests/core/worktrees/test_symlinks.py
git commit -m "feat(worktrees): TOCTOU-safe atomic-rename symlink helper"
```

---

## Task 12: Stage 1 auto-symlink — host-aware derivation + execute

**Files:**
- Create: `src/orca/core/worktrees/auto_symlink.py`
- Test: `tests/core/worktrees/test_auto_symlink.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/worktrees/test_auto_symlink.py
from pathlib import Path

import pytest

from orca.core.worktrees.config import WorktreesConfig
from orca.core.worktrees.auto_symlink import (
    derive_host_paths, run_stage1,
)


class TestDeriveHostPaths:
    def test_spec_kit_paths(self):
        paths = derive_host_paths("spec-kit")
        assert ".specify" in paths
        assert "specs" in paths

    def test_superpowers_paths(self):
        paths = derive_host_paths("superpowers")
        assert "docs/superpowers" in paths

    def test_openspec_paths(self):
        paths = derive_host_paths("openspec")
        assert "openspec" in paths

    def test_bare_paths(self):
        paths = derive_host_paths("bare")
        assert "docs/orca-specs" in paths


class TestRunStage1:
    def _setup_repo(self, tmp_path: Path, host: str) -> tuple[Path, Path]:
        primary = tmp_path / "primary"
        primary.mkdir()
        (primary / ".env").write_text("FOO=1")
        (primary / ".specify").mkdir()
        (primary / "specs").mkdir()
        wt = tmp_path / "wt"
        wt.mkdir()
        return primary, wt

    def test_creates_host_symlinks(self, tmp_path):
        primary, wt = self._setup_repo(tmp_path, "spec-kit")
        cfg = WorktreesConfig()
        run_stage1(primary_root=primary, worktree_dir=wt,
                   cfg=cfg, host_system="spec-kit")
        assert (wt / ".specify").is_symlink()
        assert (wt / "specs").is_symlink()
        assert (wt / ".env").is_symlink()

    def test_explicit_symlink_paths_override_host_defaults(self, tmp_path):
        primary, wt = self._setup_repo(tmp_path, "spec-kit")
        (primary / "custom").mkdir()
        cfg = WorktreesConfig(symlink_paths=["custom"])
        run_stage1(primary_root=primary, worktree_dir=wt,
                   cfg=cfg, host_system="spec-kit")
        # Explicit list override: only "custom" symlinked, not .specify
        assert (wt / "custom").is_symlink()
        assert not (wt / ".specify").is_symlink()

    def test_skips_files_missing_in_primary(self, tmp_path):
        primary, wt = self._setup_repo(tmp_path, "spec-kit")
        # .env.local does not exist in primary
        cfg = WorktreesConfig()
        run_stage1(primary_root=primary, worktree_dir=wt,
                   cfg=cfg, host_system="spec-kit")
        assert not (wt / ".env.local").exists()
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_auto_symlink.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/orca/core/worktrees/auto_symlink.py
"""Stage 1 host-aware auto-symlink: build the symlink list from manifest
host_system + cfg, then create symlinks via the safe atomic-rename helper.
"""
from __future__ import annotations

from pathlib import Path

from orca.core.worktrees.config import WorktreesConfig
from orca.core.worktrees.symlinks import safe_symlink

_HOST_DEFAULTS: dict[str, list[str]] = {
    "spec-kit": [".specify", "specs"],
    "superpowers": ["docs/superpowers"],
    "openspec": ["openspec"],
    "bare": ["docs/orca-specs"],
}


def derive_host_paths(host_system: str) -> list[str]:
    """Return the auto-derived symlink paths for a host system."""
    return list(_HOST_DEFAULTS.get(host_system, []))


def run_stage1(
    *,
    primary_root: Path,
    worktree_dir: Path,
    cfg: WorktreesConfig,
    host_system: str,
) -> list[Path]:
    """Create auto-symlinks. Returns the list of links created/verified.

    Symlink list precedence:
      - cfg.symlink_paths (if non-empty) overrides host defaults
      - else: host defaults from `derive_host_paths`
      - cfg.symlink_files (env-style files) always layered in addition
    """
    explicit = list(cfg.symlink_paths)
    paths = explicit if explicit else derive_host_paths(host_system)

    created: list[Path] = []
    for rel in paths:
        target = primary_root / rel
        if not target.exists():
            continue
        link = worktree_dir / rel
        safe_symlink(target=target, link=link)
        created.append(link)

    for rel in cfg.symlink_files:
        target = primary_root / rel
        if not target.exists():
            continue
        link = worktree_dir / rel
        safe_symlink(target=target, link=link)
        created.append(link)

    return created
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_auto_symlink.py -v`
Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/auto_symlink.py tests/core/worktrees/test_auto_symlink.py
git commit -m "feat(worktrees): Stage 1 host-aware auto-symlink layer"
```

---

## Task 13: TOFU trust ledger — load/store + repo-key resolution

**Files:**
- Create: `src/orca/core/worktrees/trust.py`
- Test: `tests/core/worktrees/test_trust.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/worktrees/test_trust.py
import json
import os
from pathlib import Path

import pytest

from orca.core.worktrees.trust import (
    TrustLedger, resolve_repo_key, ledger_path,
)


class TestResolveRepoKey:
    def test_uses_remote_origin_when_present(self, tmp_path, monkeypatch):
        # Set up a fake repo with a remote
        import subprocess
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        subprocess.run(["git", "-C", str(tmp_path), "remote", "add",
                        "origin", "git@github.com:o/r.git"], check=True)
        assert resolve_repo_key(tmp_path) == "git@github.com:o/r.git"

    def test_falls_back_to_realpath_when_no_remote(self, tmp_path):
        import subprocess
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        key = resolve_repo_key(tmp_path)
        # Falls back to the realpath of the repo
        assert Path(key).resolve() == tmp_path.resolve()


class TestLedgerPath:
    def test_default_xdg(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.delenv("ORCA_TRUST_LEDGER", raising=False)
        path = ledger_path()
        assert path == tmp_path / "orca" / "worktree-trust.json"

    def test_explicit_env_overrides(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "custom.json"))
        assert ledger_path() == tmp_path / "custom.json"


class TestTrustLedger:
    def test_load_missing_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "missing.json"))
        ledger = TrustLedger.load()
        assert ledger.is_trusted("k", "/p/setup", "abc") is False

    def test_record_then_check(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        ledger = TrustLedger.load()
        ledger.record(repo_key="k", script_path="/p/setup", sha="abc")
        ledger.save()

        # Reload from disk
        reloaded = TrustLedger.load()
        assert reloaded.is_trusted("k", "/p/setup", "abc") is True
        # Different SHA -> not trusted (script changed)
        assert reloaded.is_trusted("k", "/p/setup", "xyz") is False
        # Different repo -> not trusted
        assert reloaded.is_trusted("other", "/p/setup", "abc") is False

    def test_atomic_write(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        ledger = TrustLedger.load()
        ledger.record(repo_key="k", script_path="s", sha="a")
        ledger.save()
        partials = list(tmp_path.glob("*.partial"))
        assert partials == []
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_trust.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/orca/core/worktrees/trust.py
"""TOFU (trust-on-first-use) hook ledger.

Hook scripts run with operator's full privileges. The ledger records
which (repo_key, script_path, sha256) triples the operator has approved.
First run prompts; subsequent runs match against the ledger.

Storage: ${ORCA_TRUST_LEDGER:-${XDG_CONFIG_HOME:-$HOME/.config}/orca/worktree-trust.json}.
Locking: same fcntl/msvcrt strategy as the registry, on a sibling .lock file.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LEDGER_FILENAME = "worktree-trust.json"


def ledger_path() -> Path:
    """Resolve ledger path per env precedence."""
    explicit = os.environ.get("ORCA_TRUST_LEDGER")
    if explicit:
        return Path(explicit)
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "orca" / LEDGER_FILENAME


def resolve_repo_key(repo_root: Path) -> str:
    """Return remote.origin.url if available; else realpath of the repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, check=False,
        )
        url = result.stdout.strip()
        if url:
            return url
    except (FileNotFoundError, OSError):
        pass
    return str(repo_root.resolve())


@dataclass
class _Entry:
    repo_key: str
    script_path: str
    sha: str


@dataclass
class TrustLedger:
    """In-memory ledger snapshot. Use .load()/.save() for I/O."""
    entries: list[_Entry] = field(default_factory=list)

    @classmethod
    def load(cls) -> "TrustLedger":
        path = ledger_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        entries = [
            _Entry(
                repo_key=e["repo_key"],
                script_path=e["script_path"],
                sha=e["sha"],
            )
            for e in data.get("entries", [])
            if isinstance(e, dict) and "repo_key" in e
        ]
        return cls(entries=entries)

    def is_trusted(self, repo_key: str, script_path: str, sha: str) -> bool:
        return any(
            e.repo_key == repo_key and e.script_path == script_path and e.sha == sha
            for e in self.entries
        )

    def record(self, *, repo_key: str, script_path: str, sha: str) -> None:
        # Replace any prior entry for the same (repo_key, script_path)
        self.entries = [
            e for e in self.entries
            if not (e.repo_key == repo_key and e.script_path == script_path)
        ]
        self.entries.append(_Entry(repo_key, script_path, sha))

    def save(self) -> None:
        path = ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "schema_version": 1,
            "entries": [
                {"repo_key": e.repo_key, "script_path": e.script_path, "sha": e.sha}
                for e in self.entries
            ],
        }
        encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        tmp = path.with_suffix(path.suffix + ".partial")
        tmp.write_bytes(encoded)
        tmp.replace(path)
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_trust.py -v`
Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/trust.py tests/core/worktrees/test_trust.py
git commit -m "feat(worktrees): TOFU ledger with repo-key + atomic save"
```

---

## Task 14: Trust prompt flow + --trust-hooks + --record + non-interactive guard

**Files:**
- Modify: `src/orca/core/worktrees/trust.py` (add `check_or_prompt`)
- Modify: `tests/core/worktrees/test_trust.py`

- [ ] **Step 1: Write failing tests**

```python
# Append to tests/core/worktrees/test_trust.py
import io
import sys
from unittest.mock import patch

from orca.core.worktrees.trust import (
    check_or_prompt, TrustOutcome, TrustDecision,
)


class TestCheckOrPrompt:
    def test_already_trusted_returns_trusted(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        ledger = TrustLedger.load()
        ledger.record(repo_key="k", script_path="s", sha="abc")
        ledger.save()

        out = check_or_prompt(repo_key="k", script_path="s", sha="abc",
                              script_text="echo hi",
                              decision=TrustDecision(trust_hooks=False, record=False),
                              interactive=True)
        assert out == TrustOutcome.TRUSTED

    def test_trust_hooks_bypass_without_record(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        out = check_or_prompt(repo_key="k", script_path="s", sha="abc",
                              script_text="echo hi",
                              decision=TrustDecision(trust_hooks=True, record=False),
                              interactive=False)
        assert out == TrustOutcome.BYPASSED
        # Ledger unchanged
        ledger = TrustLedger.load()
        assert not ledger.is_trusted("k", "s", "abc")

    def test_trust_hooks_with_record_persists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        out = check_or_prompt(repo_key="k", script_path="s", sha="abc",
                              script_text="echo hi",
                              decision=TrustDecision(trust_hooks=True, record=True),
                              interactive=False)
        assert out == TrustOutcome.RECORDED
        ledger = TrustLedger.load()
        assert ledger.is_trusted("k", "s", "abc")

    def test_non_interactive_unknown_refuses(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        out = check_or_prompt(repo_key="k", script_path="s", sha="abc",
                              script_text="echo hi",
                              decision=TrustDecision(trust_hooks=False, record=False),
                              interactive=False)
        assert out == TrustOutcome.REFUSED_NONINTERACTIVE

    def test_interactive_yes_records_and_returns_recorded(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        with patch("sys.stdin", io.StringIO("y\n")):
            out = check_or_prompt(repo_key="k", script_path="s", sha="abc",
                                  script_text="echo hi",
                                  decision=TrustDecision(trust_hooks=False, record=False),
                                  interactive=True)
        assert out == TrustOutcome.RECORDED

    def test_interactive_no_returns_declined(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCA_TRUST_LEDGER", str(tmp_path / "l.json"))
        with patch("sys.stdin", io.StringIO("n\n")):
            out = check_or_prompt(repo_key="k", script_path="s", sha="abc",
                                  script_text="echo hi",
                                  decision=TrustDecision(trust_hooks=False, record=False),
                                  interactive=True)
        assert out == TrustOutcome.DECLINED
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_trust.py -v`
Expected: ImportError on TrustOutcome.

- [ ] **Step 3: Add to `src/orca/core/worktrees/trust.py`**

```python
import enum
import sys
from dataclasses import dataclass


class TrustOutcome(enum.Enum):
    """Outcome of a trust check.

    TRUSTED: matched an existing ledger entry; no prompt shown.
    RECORDED: bypass + record (--trust-hooks --record) OR interactive yes.
    BYPASSED: --trust-hooks without --record; one-shot bypass.
    DECLINED: interactive prompt answered 'no'.
    REFUSED_NONINTERACTIVE: stdin not a tty AND no --trust-hooks AND not in
        ledger; CLI handler should exit INPUT_INVALID with hint.
    """
    TRUSTED = "trusted"
    RECORDED = "recorded"
    BYPASSED = "bypassed"
    DECLINED = "declined"
    REFUSED_NONINTERACTIVE = "refused_noninteractive"


@dataclass(frozen=True)
class TrustDecision:
    trust_hooks: bool  # --trust-hooks or ORCA_TRUST_HOOKS=1
    record: bool       # --record subflag


def check_or_prompt(
    *,
    repo_key: str,
    script_path: str,
    sha: str,
    script_text: str,
    decision: TrustDecision,
    interactive: bool,
) -> TrustOutcome:
    """Resolve trust for a hook script.

    Logic:
      1. If already in ledger: TRUSTED
      2. Else if decision.trust_hooks and decision.record: record + RECORDED
      3. Else if decision.trust_hooks: BYPASSED (no record)
      4. Else if not interactive: REFUSED_NONINTERACTIVE
      5. Else: prompt; on 'y' -> record + RECORDED; on 'n' -> DECLINED
    """
    ledger = TrustLedger.load()
    if ledger.is_trusted(repo_key, script_path, sha):
        return TrustOutcome.TRUSTED

    if decision.trust_hooks:
        if decision.record:
            ledger.record(repo_key=repo_key, script_path=script_path, sha=sha)
            ledger.save()
            return TrustOutcome.RECORDED
        return TrustOutcome.BYPASSED

    if not interactive:
        return TrustOutcome.REFUSED_NONINTERACTIVE

    print(f"\nHook script: {script_path}")
    print(f"SHA-256: {sha}")
    print("--- script content ---")
    print(script_text)
    print("--- end script ---")
    print(f"Trust this script for repo {repo_key}? [y/N]: ", end="", flush=True)
    answer = sys.stdin.readline().strip().lower()
    if answer == "y":
        ledger.record(repo_key=repo_key, script_path=script_path, sha=sha)
        ledger.save()
        return TrustOutcome.RECORDED
    return TrustOutcome.DECLINED
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_trust.py -v`
Expected: all 13 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/trust.py tests/core/worktrees/test_trust.py
git commit -m "feat(worktrees): trust prompt flow with --trust-hooks/--record"
```

---

## Task 15: Hook env contract + execution helper

**Files:**
- Create: `src/orca/core/worktrees/hooks.py`
- Test: `tests/core/worktrees/test_hooks.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/worktrees/test_hooks.py
import os
import stat
from pathlib import Path

import pytest

from orca.core.worktrees.hooks import (
    HookEnv, run_hook, HookOutcome, hook_sha,
)


def _make_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


class TestRunHook:
    def test_missing_hook_returns_skipped(self, tmp_path):
        env = HookEnv(repo_root=tmp_path, worktree_dir=tmp_path / "wt",
                      branch="x", lane_id="x", lane_mode="branch",
                      feature_id=None, host_system="bare")
        outcome = run_hook(script_path=tmp_path / "missing.sh", env=env)
        assert outcome.status == "skipped"

    def test_successful_hook_completes_zero(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        hook = tmp_path / "after_create"
        _make_executable(hook, '#!/usr/bin/env bash\nexit 0\n')

        env = HookEnv(repo_root=tmp_path, worktree_dir=wt, branch="x",
                      lane_id="x", lane_mode="branch", feature_id=None,
                      host_system="bare")
        outcome = run_hook(script_path=hook, env=env)
        assert outcome.status == "completed"
        assert outcome.exit_code == 0

    def test_failing_hook_returns_failed(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        hook = tmp_path / "after_create"
        _make_executable(hook, '#!/usr/bin/env bash\nexit 7\n')

        env = HookEnv(repo_root=tmp_path, worktree_dir=wt, branch="x",
                      lane_id="x", lane_mode="branch", feature_id=None,
                      host_system="bare")
        outcome = run_hook(script_path=hook, env=env)
        assert outcome.status == "failed"
        assert outcome.exit_code == 7

    def test_env_contract_injected(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        out = tmp_path / "out.txt"
        hook = tmp_path / "after_create"
        _make_executable(hook,
            '#!/usr/bin/env bash\n'
            f'echo "$ORCA_LANE_ID:$ORCA_BRANCH:$ORCA_HOST_SYSTEM" > "{out}"\n')

        env = HookEnv(repo_root=tmp_path, worktree_dir=wt, branch="feat",
                      lane_id="L1", lane_mode="branch", feature_id=None,
                      host_system="superpowers")
        outcome = run_hook(script_path=hook, env=env)
        assert outcome.status == "completed"
        assert out.read_text().strip() == "L1:feat:superpowers"

    def test_cwd_is_worktree_dir(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        out = tmp_path / "cwd.txt"
        hook = tmp_path / "after_create"
        _make_executable(hook,
            '#!/usr/bin/env bash\n'
            f'pwd > "{out}"\n')

        env = HookEnv(repo_root=tmp_path, worktree_dir=wt, branch="x",
                      lane_id="x", lane_mode="branch", feature_id=None,
                      host_system="bare")
        run_hook(script_path=hook, env=env)
        assert out.read_text().strip() == str(wt.resolve())


class TestHookSha:
    def test_returns_sha256_hex(self, tmp_path):
        h = tmp_path / "after_create"
        h.write_text("#!/usr/bin/env bash\necho hi\n")
        sha = hook_sha(h)
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_hooks.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/orca/core/worktrees/hooks.py
"""Hook execution with the env contract documented in the spec.

Stage 2 (after_create), Stage 3 (before_run), Stage 4 (before_remove).
This module is purely about running ONE hook script with the right env;
trust verification is a separate concern (trust.py).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class HookEnv:
    repo_root: Path
    worktree_dir: Path
    branch: str
    lane_id: str
    lane_mode: Literal["branch", "lane"]
    feature_id: str | None
    host_system: str


@dataclass(frozen=True)
class HookOutcome:
    status: Literal["skipped", "completed", "failed"]
    exit_code: int
    duration_ms: int
    stdout: str = ""
    stderr: str = ""


def hook_sha(script_path: Path) -> str:
    """SHA-256 hex of the script content. Used by the trust ledger."""
    h = hashlib.sha256()
    h.update(script_path.read_bytes())
    return h.hexdigest()


def _build_env(env: HookEnv) -> dict[str, str]:
    out = dict(os.environ)
    out["ORCA_REPO_ROOT"] = str(env.repo_root.resolve())
    out["ORCA_WORKTREE_DIR"] = str(env.worktree_dir.resolve())
    out["ORCA_BRANCH"] = env.branch
    out["ORCA_LANE_ID"] = env.lane_id
    out["ORCA_LANE_MODE"] = env.lane_mode
    if env.feature_id is not None:
        out["ORCA_FEATURE_ID"] = env.feature_id
    out["ORCA_HOST_SYSTEM"] = env.host_system
    return out


def run_hook(*, script_path: Path, env: HookEnv) -> HookOutcome:
    """Execute one hook script.

    Returns HookOutcome with status:
      - "skipped"  if script doesn't exist
      - "completed" if exit 0
      - "failed"   if non-zero
    """
    if not script_path.exists():
        return HookOutcome(status="skipped", exit_code=0, duration_ms=0)

    started = time.monotonic()
    proc = subprocess.run(
        [str(script_path)],
        cwd=str(env.worktree_dir),
        env=_build_env(env),
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = int((time.monotonic() - started) * 1000)
    status = "completed" if proc.returncode == 0 else "failed"
    return HookOutcome(
        status=status,
        exit_code=proc.returncode,
        duration_ms=elapsed,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_hooks.py -v`
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/hooks.py tests/core/worktrees/test_hooks.py
git commit -m "feat(worktrees): hook executor with env contract + sha helper"
```

---

## Task 16: tmux helper module

**Files:**
- Create: `src/orca/core/worktrees/tmux.py`
- Test: `tests/core/worktrees/test_tmux.py`

- [ ] **Step 1: Write failing tests** (mocked tmux subprocess)

```python
# tests/core/worktrees/test_tmux.py
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from orca.core.worktrees.tmux import (
    has_session, has_window, ensure_session, new_window,
    kill_window, kill_session_if_empty, list_windows,
    send_keys, resolve_session_name,
)


class TestResolveSessionName:
    def test_literal_passes_through(self):
        assert resolve_session_name("orca", repo_root=Path("/x/foo")) == "orca"

    def test_template_substitutes_sanitized_repo(self):
        assert resolve_session_name("orca-{repo}",
                                     repo_root=Path("/x/my.repo")) == "orca-my_repo"

    def test_template_truncates_long_repo_name(self):
        long_name = "a" * 200
        result = resolve_session_name("{repo}",
                                       repo_root=Path(f"/x/{long_name}"))
        assert len(result) <= 64


class TestHasSession:
    def test_returns_true_when_tmux_succeeds(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            assert has_session("orca") is True

    def test_returns_false_when_tmux_fails(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=1)
            assert has_session("orca") is False


class TestEnsureSession:
    def test_no_op_when_session_exists(self):
        with patch("orca.core.worktrees.tmux.has_session", return_value=True), \
             patch("subprocess.run") as run:
            ensure_session("orca", cwd=Path("/x"))
            assert run.call_count == 0

    def test_creates_when_missing(self):
        with patch("orca.core.worktrees.tmux.has_session", return_value=False), \
             patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            ensure_session("orca", cwd=Path("/x"))
            assert run.called
            args = run.call_args[0][0]
            assert args[:4] == ["tmux", "new-session", "-d", "-s"]


class TestNewWindow:
    def test_invokes_tmux_new_window(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            new_window(session="orca", window="015-wiz", cwd=Path("/x"))
            assert run.called
            args = run.call_args[0][0]
            assert "new-window" in args
            assert "015-wiz" in args


class TestSendKeys:
    def test_sends_string_then_enter(self):
        with patch("subprocess.run") as run:
            run.return_value = MagicMock(returncode=0)
            send_keys(session="orca", window="x", keys="bash run.sh")
            # First call types the string, second sends Enter
            assert run.call_count == 2
            first_args = run.call_args_list[0][0][0]
            assert "send-keys" in first_args
            assert "bash run.sh" in first_args
            second_args = run.call_args_list[1][0][0]
            assert "Enter" in second_args
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_tmux.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/orca/core/worktrees/tmux.py
"""tmux subprocess wrapper.

All operations use args lists; never shell strings. send_keys uses
two-call pattern (text then Enter) so the keys arg never gets shell-parsed
by tmux's command parser.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from orca.core.worktrees.identifiers import sanitize_repo_name

TMUX_WINDOW_NAME_MAX = 32


def resolve_session_name(template: str, *, repo_root: Path) -> str:
    """Substitute {repo} with sanitized repo basename. Other template
    tokens are reserved for future use."""
    if "{repo}" in template:
        repo_name = sanitize_repo_name(repo_root.name)
        return template.replace("{repo}", repo_name)
    return template


def truncate_window_name(name: str) -> str:
    return name[:TMUX_WINDOW_NAME_MAX]


def has_session(session: str) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        capture_output=True, check=False,
    )
    return result.returncode == 0


def has_window(session: str, window: str) -> bool:
    result = subprocess.run(
        ["tmux", "list-windows", "-t", session, "-F", "#{window_name}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return False
    return window in result.stdout.splitlines()


def list_windows(session: str) -> list[str]:
    """Return list of window names in the session, or empty if missing."""
    result = subprocess.run(
        ["tmux", "list-windows", "-t", session, "-F", "#{window_name}"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()


def ensure_session(session: str, *, cwd: Path) -> None:
    if has_session(session):
        return
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session, "-c", str(cwd)],
        check=True,
    )


def new_window(*, session: str, window: str, cwd: Path) -> None:
    name = truncate_window_name(window)
    subprocess.run(
        ["tmux", "new-window", "-t", session, "-n", name, "-c", str(cwd)],
        check=True,
    )


def kill_window(*, session: str, window: str) -> None:
    name = truncate_window_name(window)
    subprocess.run(
        ["tmux", "kill-window", "-t", f"{session}:{name}"],
        capture_output=True, check=False,
    )


def kill_session_if_empty(session: str) -> None:
    if not list_windows(session):
        subprocess.run(
            ["tmux", "kill-session", "-t", session],
            capture_output=True, check=False,
        )


def send_keys(*, session: str, window: str, keys: str) -> None:
    """Send a literal string then Enter. Two subprocess calls so tmux
    doesn't parse `keys` as a tmux command sequence."""
    name = truncate_window_name(window)
    subprocess.run(
        ["tmux", "send-keys", "-t", f"{session}:{name}", keys],
        check=True,
    )
    subprocess.run(
        ["tmux", "send-keys", "-t", f"{session}:{name}", "Enter"],
        check=True,
    )
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_tmux.py -v`
Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/tmux.py tests/core/worktrees/test_tmux.py
git commit -m "feat(worktrees): tmux subprocess wrapper + {repo} sanitization"
```

---

## Task 17: Agent launcher (prompt-file + launcher script)

**Files:**
- Create: `src/orca/core/worktrees/agent_launch.py`
- Test: `tests/core/worktrees/test_agent_launch.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/worktrees/test_agent_launch.py
import os
import stat
from pathlib import Path

import pytest

from orca.core.worktrees.agent_launch import (
    write_launcher, prompt_path, launcher_path,
)


class TestWriteLauncher:
    def test_creates_launcher_and_prompt(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        write_launcher(
            worktree_dir=wt,
            lane_id="015-wiz",
            agent_cmd="claude --dangerously-skip-permissions",
            prompt="Build the thing",
            extra_args=[],
        )
        ldir = wt / ".orca"
        assert ldir.exists()
        # Launcher script
        launcher = ldir / ".run-015-wiz.sh"
        assert launcher.exists()
        mode = launcher.stat().st_mode & 0o777
        assert mode == 0o700
        # Prompt file
        pfile = ldir / ".run-015-wiz.prompt"
        assert pfile.exists()
        pmode = pfile.stat().st_mode & 0o777
        assert pmode == 0o600
        assert pfile.read_text() == "Build the thing"

    def test_no_prompt_skips_prompt_file(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        write_launcher(
            worktree_dir=wt,
            lane_id="x",
            agent_cmd="claude",
            prompt=None,
            extra_args=[],
        )
        assert (wt / ".orca" / ".run-x.sh").exists()
        assert not (wt / ".orca" / ".run-x.prompt").exists()

    def test_extra_args_quoted_safely(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        write_launcher(
            worktree_dir=wt,
            lane_id="x",
            agent_cmd="claude",
            prompt=None,
            extra_args=["--model", "opus", "weird arg with 'quotes'"],
        )
        script = (wt / ".orca" / ".run-x.sh").read_text()
        # shlex.quote ensures the dangerous arg is wrapped safely
        assert "'weird arg with '\"'\"'quotes'\"'\"''" in script

    def test_launcher_invokes_via_exec_after_reading_prompt(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        write_launcher(
            worktree_dir=wt,
            lane_id="x",
            agent_cmd="claude --dangerously-skip-permissions",
            prompt="hello",
            extra_args=[],
        )
        script = (wt / ".orca" / ".run-x.sh").read_text()
        # Prompt is read from the prompt file then deleted before exec
        assert 'PROMPT_FILE=".orca/.run-x.prompt"' in script
        assert "rm -f" in script
        assert "exec claude" in script


class TestPromptFileSecrecy:
    def test_prompt_file_mode_0600(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        write_launcher(
            worktree_dir=wt,
            lane_id="x",
            agent_cmd="claude",
            prompt="secret",
            extra_args=[],
        )
        pfile = wt / ".orca" / ".run-x.prompt"
        assert (pfile.stat().st_mode & 0o077) == 0  # No group/other access
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_agent_launch.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/orca/core/worktrees/agent_launch.py
"""Agent launcher: prompt-file + launcher-script pattern.

Per spec §"Agent-launch quoting via prompt-file + launcher-script", the
prompt is written to a separate mode-0600 file that the launcher reads
and deletes (one-shot). The launcher script itself is mode-0700 and
persists for the lane lifetime (removed by `wt rm`). No tmux
set-environment is used, so the prompt does not leak across panes.
"""
from __future__ import annotations

import os
import shlex
import stat
from pathlib import Path

LAUNCHER_DIR = ".orca"


def launcher_path(worktree_dir: Path, lane_id: str) -> Path:
    return worktree_dir / LAUNCHER_DIR / f".run-{lane_id}.sh"


def prompt_path(worktree_dir: Path, lane_id: str) -> Path:
    return worktree_dir / LAUNCHER_DIR / f".run-{lane_id}.prompt"


def write_launcher(
    *,
    worktree_dir: Path,
    lane_id: str,
    agent_cmd: str,
    prompt: str | None,
    extra_args: list[str],
) -> Path:
    """Write the launcher script (and prompt file if a prompt is supplied).

    Returns the launcher path. Caller is responsible for invoking it via
    tmux send_keys; this function does not touch tmux.
    """
    ldir = worktree_dir / LAUNCHER_DIR
    ldir.mkdir(parents=True, exist_ok=True)

    pf = prompt_path(worktree_dir, lane_id)
    if prompt is not None:
        pf.write_text(prompt, encoding="utf-8")
        os.chmod(pf, 0o600)

    quoted_extra = " ".join(shlex.quote(a) for a in extra_args)
    rel_prompt = f"{LAUNCHER_DIR}/.run-{lane_id}.prompt"
    if prompt is not None:
        body = f'''#!/usr/bin/env bash
set -e
PROMPT_FILE="{rel_prompt}"
if [[ -f "$PROMPT_FILE" ]]; then
  PROMPT="$(cat "$PROMPT_FILE")"
  rm -f "$PROMPT_FILE"
else
  PROMPT=""
fi
exec {agent_cmd}{(" " + quoted_extra) if quoted_extra else ""} --prompt "$PROMPT"
'''
    else:
        body = f'''#!/usr/bin/env bash
set -e
exec {agent_cmd}{(" " + quoted_extra) if quoted_extra else ""}
'''

    lpath = launcher_path(worktree_dir, lane_id)
    lpath.write_text(body, encoding="utf-8")
    os.chmod(lpath, 0o700)
    return lpath
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_agent_launch.py -v`
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/agent_launch.py tests/core/worktrees/test_agent_launch.py
git commit -m "feat(worktrees): agent launcher with prompt-file + launcher-script"
```

---

## Task 18: WorktreeManager protocol + create() happy path (state-cube row 1)

**Files:**
- Create: `src/orca/core/worktrees/protocol.py`
- Create: `src/orca/core/worktrees/manager.py`
- Test: `tests/core/worktrees/test_manager.py`

- [ ] **Step 1: Write failing test for happy-path create**

```python
# tests/core/worktrees/test_manager.py
import json
import subprocess
from pathlib import Path

import pytest

from orca.core.worktrees.config import WorktreesConfig
from orca.core.worktrees.manager import WorktreeManager, CreateRequest, CreateResult


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "--allow-empty",
                    "-m", "init"], check=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                        **__import__("os").environ})
    return tmp_path


@pytest.fixture
def repo(tmp_path):
    return _init_repo(tmp_path)


class TestCreateHappyPath:
    def test_creates_worktree_branch_sidecar_registry(self, repo):
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        result = mgr.create(req)
        assert isinstance(result, CreateResult)
        assert result.lane_id == "feature-foo"
        # Worktree directory exists
        assert (repo / ".orca" / "worktrees" / "feature-foo").is_dir()
        # Sidecar exists
        assert (repo / ".orca" / "worktrees" / "feature-foo.json").exists()
        # Registry entry exists
        reg = json.loads((repo / ".orca" / "worktrees" / "registry.json").read_text())
        assert reg["schema_version"] == 2
        assert reg["lanes"][0]["lane_id"] == "feature-foo"
        # Branch was created
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "feature-foo"],
            capture_output=True, check=True,
        )
        assert result.returncode == 0
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_manager.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement protocol + manager (happy path only)**

```python
# src/orca/core/worktrees/protocol.py
"""WorktreeManager Protocol — the public surface used by CLI handlers."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CreateRequest:
    branch: str
    from_branch: str | None
    feature: str | None
    lane: str | None
    agent: str  # "claude" | "codex" | "none"
    prompt: str | None
    extra_args: list[str]
    reuse_branch: bool = False
    recreate_branch: bool = False
    no_setup: bool = False
    trust_hooks: bool = False
    record_trust: bool = False


@dataclass(frozen=True)
class CreateResult:
    lane_id: str
    worktree_path: Path
    branch: str
    tmux_session: str | None
    tmux_window: str | None
    setup_outcomes: list[str] = field(default_factory=list)


class WorktreeManagerProtocol(Protocol):
    def create(self, req: CreateRequest) -> CreateResult: ...
```

```python
# src/orca/core/worktrees/manager.py
"""WorktreeManager: orchestrates create/remove against the state cube.

This task implements only the happy path (state-cube row 1: nothing
exists yet). Subsequent tasks layer in the other 7 rows.
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from orca.core.worktrees.config import WorktreesConfig
from orca.core.worktrees.events import emit_event
from orca.core.worktrees.identifiers import derive_lane_id
from orca.core.worktrees.layout import resolve_worktree_path
from orca.core.worktrees.protocol import CreateRequest, CreateResult
from orca.core.worktrees.registry import (
    LaneRow, Sidecar, acquire_registry_lock, read_registry, write_registry,
    write_sidecar, registry_path,
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_branch(repo_root: Path) -> str:
    """Try origin HEAD, then main, then master, then current branch."""
    for cmd in (
        ["git", "-C", str(repo_root), "symbolic-ref", "refs/remotes/origin/HEAD"],
    ):
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return result.stdout.strip().split("/")[-1]
    for branch in ("main", "master"):
        check = subprocess.run(
            ["git", "-C", str(repo_root), "show-ref", "--verify", "--quiet",
             f"refs/heads/{branch}"],
            check=False,
        )
        if check.returncode == 0:
            return branch
    # Fall back to current
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


class WorktreeManager:
    def __init__(
        self,
        *,
        repo_root: Path,
        cfg: WorktreesConfig,
        host_system: str,
        run_tmux: bool = True,
        run_setup: bool = True,
    ) -> None:
        self.repo_root = repo_root
        self.cfg = cfg
        self.host_system = host_system
        self.run_tmux = run_tmux
        self.run_setup = run_setup
        self.worktree_root = repo_root / ".orca" / "worktrees"

    def create(self, req: CreateRequest) -> CreateResult:
        lane_id = derive_lane_id(
            branch=req.branch, mode=self.cfg.lane_id_mode,
            feature=req.feature, lane=req.lane,
        )
        wt_path = resolve_worktree_path(self.repo_root, self.cfg, lane_id=lane_id)
        from_branch = req.from_branch or _default_branch(self.repo_root)

        with acquire_registry_lock(self.worktree_root):
            self.worktree_root.mkdir(parents=True, exist_ok=True)
            # State-cube row 1 only this task: assume nothing exists.
            # Later tasks will branch on the 8-row table here.

            # git worktree add -b <branch> <path> <from>
            subprocess.run(
                ["git", "-C", str(self.repo_root), "worktree", "add",
                 "-b", req.branch, str(wt_path), from_branch],
                check=True, capture_output=True,
            )

            sidecar = Sidecar(
                schema_version=2,
                lane_id=lane_id,
                lane_mode="lane" if (req.feature and req.lane) else "branch",
                feature_id=req.feature,
                lane_name=req.lane,
                branch=req.branch,
                base_branch=from_branch,
                worktree_path=str(wt_path),
                created_at=_now_utc(),
                tmux_session=self.cfg.tmux_session,
                tmux_window=lane_id[:32],
                agent=req.agent,
                setup_version="",
                last_attached_at=None,
                host_system=self.host_system,
            )
            write_sidecar(self.worktree_root, sidecar)

            # Append to registry
            view = read_registry(self.worktree_root)
            new_lanes = list(view.lanes) + [LaneRow(
                lane_id=lane_id, branch=req.branch,
                worktree_path=str(wt_path), feature_id=req.feature,
            )]
            write_registry(self.worktree_root, new_lanes)

            emit_event(self.worktree_root, event="lane.created",
                       lane_id=lane_id, branch=req.branch)

        return CreateResult(
            lane_id=lane_id,
            worktree_path=wt_path,
            branch=req.branch,
            tmux_session=None,
            tmux_window=None,
        )
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_manager.py -v`
Expected: 1 happy-path test passes.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/protocol.py src/orca/core/worktrees/manager.py tests/core/worktrees/test_manager.py
git commit -m "feat(worktrees): WorktreeManager.create() happy path (row 1)"
```

---

## Task 19: WorktreeManager.create() — state-cube rows 2-8 (idempotency)

**Files:**
- Modify: `src/orca/core/worktrees/manager.py`
- Modify: `tests/core/worktrees/test_manager.py`

- [ ] **Step 1: Write failing tests for each row**

Each test sets up the (branch, worktree, sidecar, registry) state then asserts behavior per the spec's 8-row table.

```python
# Append to tests/core/worktrees/test_manager.py
import os
import shutil

from orca.core.worktrees.manager import IdempotencyError


def _existing_lane(repo: Path, branch: str) -> tuple[str, Path]:
    """Helper: bring a lane into the (yes, yes, yes, yes) state."""
    cfg = WorktreesConfig()
    mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                          run_tmux=False, run_setup=False)
    req = CreateRequest(branch=branch, from_branch=None, feature=None, lane=None,
                        agent="none", prompt=None, extra_args=[])
    result = mgr.create(req)
    return result.lane_id, result.worktree_path


class TestStateCubeRows:
    # Row 2: branch yes, no worktree, no sidecar, no registry
    def test_branch_exists_no_worktree_refuses_without_reuse(self, repo):
        subprocess.run(["git", "-C", str(repo), "branch", "preexisting"], check=True)
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="preexisting", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        with pytest.raises(IdempotencyError, match="branch exists"):
            mgr.create(req)

    def test_branch_exists_no_worktree_succeeds_with_reuse(self, repo):
        subprocess.run(["git", "-C", str(repo), "branch", "preexisting"], check=True)
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="preexisting", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[], reuse_branch=True)
        result = mgr.create(req)
        assert result.lane_id == "preexisting"

    # Row 5: fully registered → idempotent attach
    def test_fully_registered_attaches_idempotent(self, repo):
        lane_id, wt = _existing_lane(repo, "feature-foo")
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        result = mgr.create(req)
        assert result.lane_id == lane_id
        # Worktree wasn't recreated
        assert wt.exists()

    # Row 6: branch yes, sidecar yes, no worktree → refuse without --reuse-branch
    def test_branch_yes_sidecar_yes_no_worktree_refuses(self, repo):
        lane_id, wt = _existing_lane(repo, "feature-foo")
        # Force-remove the worktree leaving sidecar+registry+branch behind
        shutil.rmtree(wt)
        subprocess.run(["git", "-C", str(repo), "worktree", "prune"], check=True)
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        with pytest.raises(IdempotencyError, match="stale"):
            mgr.create(req)

    # Row 7: no branch, sidecar/registry yes → auto-clean; refuse without --recreate
    def test_no_branch_orphan_sidecar_refuses_without_recreate(self, repo):
        lane_id, wt = _existing_lane(repo, "feature-foo")
        # Delete branch + worktree externally
        shutil.rmtree(wt)
        subprocess.run(["git", "-C", str(repo), "worktree", "prune"], check=True)
        subprocess.run(["git", "-C", str(repo), "branch", "-D", "feature-foo"],
                       check=True)
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[])
        with pytest.raises(IdempotencyError, match="recreate"):
            mgr.create(req)

    def test_no_branch_orphan_sidecar_succeeds_with_recreate(self, repo):
        lane_id, wt = _existing_lane(repo, "feature-foo")
        shutil.rmtree(wt)
        subprocess.run(["git", "-C", str(repo), "worktree", "prune"], check=True)
        subprocess.run(["git", "-C", str(repo), "branch", "-D", "feature-foo"],
                       check=True)
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[], recreate_branch=True)
        result = mgr.create(req)
        assert result.lane_id == lane_id
        assert wt.exists()
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_manager.py -v`
Expected: ImportError on IdempotencyError, then state-cube failures.

- [ ] **Step 3: Implement state-cube logic**

Replace the body of `WorktreeManager.create()` in `src/orca/core/worktrees/manager.py`:

```python
class IdempotencyError(RuntimeError):
    """Raised when wt new encounters a state-cube row that requires an
    explicit flag (--reuse-branch or --recreate-branch)."""


def _branch_exists(repo_root: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show-ref", "--verify", "--quiet",
         f"refs/heads/{branch}"],
        check=False,
    )
    return result.returncode == 0


def _worktree_for_branch(repo_root: Path, branch: str) -> Path | None:
    """Return the worktree path for a branch, or None if not checked out."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return None
    current_path: Path | None = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line[len("worktree "):].strip())
        elif line.startswith("branch "):
            ref = line[len("branch "):].strip()
            if ref == f"refs/heads/{branch}":
                return current_path
    return None
```

Replace `create` body:

```python
    def create(self, req: CreateRequest) -> CreateResult:
        from orca.core.worktrees.registry import sidecar_path, read_sidecar
        lane_id = derive_lane_id(
            branch=req.branch, mode=self.cfg.lane_id_mode,
            feature=req.feature, lane=req.lane,
        )
        wt_path = resolve_worktree_path(self.repo_root, self.cfg, lane_id=lane_id)
        from_branch = req.from_branch or _default_branch(self.repo_root)

        with acquire_registry_lock(self.worktree_root):
            self.worktree_root.mkdir(parents=True, exist_ok=True)

            branch_exists = _branch_exists(self.repo_root, req.branch)
            existing_wt = _worktree_for_branch(self.repo_root, req.branch)
            worktree_exists = existing_wt is not None and existing_wt.exists()
            scp = sidecar_path(self.worktree_root, lane_id)
            sidecar_exists = scp.exists()
            view = read_registry(self.worktree_root)
            registry_exists = any(l.lane_id == lane_id for l in view.lanes)

            # Fully-registered attach (row 5 + sidecar branch matches)
            if (worktree_exists and sidecar_exists and registry_exists
                    and existing_wt == wt_path):
                emit_event(self.worktree_root, event="lane.attached",
                           lane_id=lane_id)
                return CreateResult(
                    lane_id=lane_id, worktree_path=wt_path, branch=req.branch,
                    tmux_session=None, tmux_window=None,
                )

            # Row 4 — worktree at non-canonical path
            if worktree_exists and existing_wt != wt_path:
                raise IdempotencyError(
                    f"worktree for {req.branch} exists at unexpected path "
                    f"{existing_wt}; expected {wt_path}. Run `wt rm` first."
                )

            # Row 6 — sidecar/registry stale, branch exists, no worktree
            if branch_exists and not worktree_exists and (sidecar_exists or registry_exists):
                if not req.reuse_branch:
                    raise IdempotencyError(
                        f"sidecar+registry stale for {lane_id}; branch "
                        f"{req.branch} still exists. Pass --reuse-branch "
                        f"to attach a fresh worktree."
                    )
                # Clean stale, then proceed
                if scp.exists():
                    scp.unlink()
                view = read_registry(self.worktree_root)
                view_lanes = [l for l in view.lanes if l.lane_id != lane_id]
                write_registry(self.worktree_root, view_lanes)

            # Row 7 — no branch, sidecar/registry orphan
            if not branch_exists and (sidecar_exists or registry_exists):
                if not req.recreate_branch:
                    # Auto-clean stale entries first, then refuse
                    if scp.exists():
                        scp.unlink()
                    view2 = read_registry(self.worktree_root)
                    write_registry(self.worktree_root,
                                   [l for l in view2.lanes if l.lane_id != lane_id])
                    raise IdempotencyError(
                        f"orphan sidecar/registry for {lane_id} cleaned. "
                        f"Pass --recreate-branch to recreate {req.branch}."
                    )
                # Clean + recreate
                if scp.exists():
                    scp.unlink()
                view3 = read_registry(self.worktree_root)
                write_registry(self.worktree_root,
                               [l for l in view3.lanes if l.lane_id != lane_id])

            # Row 2 — branch exists locally but no worktree, no sidecar
            if branch_exists and not worktree_exists and not sidecar_exists and not req.reuse_branch:
                raise IdempotencyError(
                    f"branch {req.branch} exists but has no worktree. "
                    f"Pass --reuse-branch to adopt it into a new worktree."
                )

            # Row 3 — worktree at expected path, no sidecar (operator created
            # via `git worktree add` directly): adopt it.
            adopting_existing = worktree_exists and existing_wt == wt_path and not sidecar_exists

            # Now create or adopt
            if not worktree_exists:
                if branch_exists:
                    # --reuse-branch path: adopt existing branch
                    subprocess.run(
                        ["git", "-C", str(self.repo_root), "worktree", "add",
                         str(wt_path), req.branch],
                        check=True, capture_output=True,
                    )
                else:
                    subprocess.run(
                        ["git", "-C", str(self.repo_root), "worktree", "add",
                         "-b", req.branch, str(wt_path), from_branch],
                        check=True, capture_output=True,
                    )

            sidecar = Sidecar(
                schema_version=2,
                lane_id=lane_id,
                lane_mode="lane" if (req.feature and req.lane) else "branch",
                feature_id=req.feature,
                lane_name=req.lane,
                branch=req.branch,
                base_branch=from_branch,
                worktree_path=str(wt_path),
                created_at=_now_utc(),
                tmux_session=self.cfg.tmux_session,
                tmux_window=lane_id[:32],
                agent=req.agent,
                setup_version="",
                last_attached_at=None,
                host_system=self.host_system,
            )
            write_sidecar(self.worktree_root, sidecar)

            view4 = read_registry(self.worktree_root)
            new_lanes = [l for l in view4.lanes if l.lane_id != lane_id]
            new_lanes.append(LaneRow(
                lane_id=lane_id, branch=req.branch,
                worktree_path=str(wt_path), feature_id=req.feature,
            ))
            write_registry(self.worktree_root, new_lanes)

            event = "lane.attached" if adopting_existing else "lane.created"
            emit_event(self.worktree_root, event=event,
                       lane_id=lane_id, branch=req.branch)

        return CreateResult(
            lane_id=lane_id, worktree_path=wt_path, branch=req.branch,
            tmux_session=None, tmux_window=None,
        )
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_manager.py -v`
Expected: 7 state-cube tests + happy-path test pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/manager.py tests/core/worktrees/test_manager.py
git commit -m "feat(worktrees): create() handles 8-row idempotency state cube"
```

---

## Task 20: WorktreeManager.remove() with state-aware short-circuits

**Files:**
- Modify: `src/orca/core/worktrees/manager.py`
- Modify: `src/orca/core/worktrees/protocol.py`
- Modify: `tests/core/worktrees/test_manager.py`

- [ ] **Step 1: Write failing tests**

```python
# Append to tests/core/worktrees/test_manager.py
from orca.core.worktrees.manager import RemoveRequest


class TestRemove:
    def test_removes_worktree_branch_sidecar_registry(self, repo):
        lane_id, wt = _existing_lane(repo, "feature-foo")
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        mgr.remove(RemoveRequest(branch="feature-foo", force=False,
                                 keep_branch=False, all_lanes=False))
        # Worktree gone
        assert not wt.exists()
        # Sidecar gone
        assert not (repo / ".orca" / "worktrees" / f"{lane_id}.json").exists()
        # Branch gone
        result = subprocess.run(
            ["git", "-C", str(repo), "show-ref", "--verify", "--quiet",
             "refs/heads/feature-foo"],
            check=False,
        )
        assert result.returncode != 0

    def test_keep_branch_preserves_branch(self, repo):
        lane_id, wt = _existing_lane(repo, "feature-foo")
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        mgr.remove(RemoveRequest(branch="feature-foo", force=False,
                                 keep_branch=True, all_lanes=False))
        result = subprocess.run(
            ["git", "-C", str(repo), "show-ref", "--verify", "--quiet",
             "refs/heads/feature-foo"],
            check=False,
        )
        assert result.returncode == 0  # branch still exists

    def test_no_op_when_lane_not_registered(self, repo):
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        # Should not raise
        mgr.remove(RemoveRequest(branch="never-existed", force=False,
                                 keep_branch=False, all_lanes=False))

    def test_external_worktree_refuses_without_force(self, repo):
        # Create worktree externally with no orca state
        external = repo / "external-wt"
        subprocess.run(["git", "-C", str(repo), "worktree", "add",
                        str(external), "-b", "outside"], check=True,
                       capture_output=True)
        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=False)
        with pytest.raises(IdempotencyError, match="external"):
            mgr.remove(RemoveRequest(branch="outside", force=False,
                                     keep_branch=False, all_lanes=False))
```

- [ ] **Step 2: Add to `src/orca/core/worktrees/protocol.py`**

```python
@dataclass(frozen=True)
class RemoveRequest:
    branch: str
    force: bool
    keep_branch: bool
    all_lanes: bool
```

- [ ] **Step 3: Add to `src/orca/core/worktrees/manager.py`**

```python
from orca.core.worktrees.protocol import RemoveRequest


    def remove(self, req: RemoveRequest) -> None:
        from orca.core.worktrees.registry import sidecar_path, read_sidecar
        with acquire_registry_lock(self.worktree_root):
            view = read_registry(self.worktree_root)
            # Find lane by branch
            target_row = next(
                (l for l in view.lanes if l.branch == req.branch), None,
            )

            existing_wt = _worktree_for_branch(self.repo_root, req.branch)
            sidecar_exists = (
                target_row is not None
                and sidecar_path(self.worktree_root, target_row.lane_id).exists()
            )

            # No-op short-circuit
            if target_row is None and not sidecar_exists and existing_wt is None:
                return

            # External worktree refusal
            if existing_wt is not None and target_row is None and not req.force:
                raise IdempotencyError(
                    f"external worktree at {existing_wt} not registered with "
                    f"orca; pass --force to remove anyway."
                )

            lane_id = target_row.lane_id if target_row else None

            # Remove worktree (if present)
            if existing_wt is not None:
                subprocess.run(
                    ["git", "-C", str(self.repo_root), "worktree", "remove",
                     "--force", str(existing_wt)],
                    check=False, capture_output=True,
                )

            # Remove branch (unless --keep-branch)
            if not req.keep_branch:
                subprocess.run(
                    ["git", "-C", str(self.repo_root), "branch", "-D", req.branch],
                    check=False, capture_output=True,
                )

            # Clean sidecar + registry
            if lane_id is not None:
                scp = sidecar_path(self.worktree_root, lane_id)
                if scp.exists():
                    scp.unlink()
                new_lanes = [l for l in view.lanes if l.lane_id != lane_id]
                write_registry(self.worktree_root, new_lanes)
                emit_event(self.worktree_root, event="lane.removed",
                           lane_id=lane_id, branch_kept=req.keep_branch)
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_manager.py -v`
Expected: all 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/manager.py src/orca/core/worktrees/protocol.py tests/core/worktrees/test_manager.py
git commit -m "feat(worktrees): WorktreeManager.remove() with state-aware short-circuits"
```

---

## Task 21: tmux integration in manager (create + remove)

**Files:**
- Modify: `src/orca/core/worktrees/manager.py`
- Modify: `tests/core/worktrees/test_manager.py`

- [ ] **Step 1: Write failing test (mocked tmux)**

```python
# Append to tests/core/worktrees/test_manager.py
from unittest.mock import patch


class TestTmuxIntegration:
    def test_create_with_tmux_calls_ensure_session_and_new_window(self, repo):
        cfg = WorktreesConfig()
        with patch("orca.core.worktrees.manager.tmux") as tm:
            tm.resolve_session_name.return_value = "orca"
            tm.ensure_session.return_value = None
            tm.new_window.return_value = None
            mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                                  run_tmux=True, run_setup=False)
            req = CreateRequest(branch="feature-foo", from_branch=None,
                                feature=None, lane=None, agent="none",
                                prompt=None, extra_args=[])
            mgr.create(req)
            tm.ensure_session.assert_called_once()
            tm.new_window.assert_called_once()

    def test_remove_with_tmux_kills_window(self, repo):
        cfg = WorktreesConfig()
        # Create with tmux mocked
        with patch("orca.core.worktrees.manager.tmux") as tm:
            tm.resolve_session_name.return_value = "orca"
            mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                                  run_tmux=True, run_setup=False)
            req = CreateRequest(branch="feature-foo", from_branch=None,
                                feature=None, lane=None, agent="none",
                                prompt=None, extra_args=[])
            mgr.create(req)
            mgr.remove(RemoveRequest(branch="feature-foo", force=False,
                                     keep_branch=False, all_lanes=False))
            tm.kill_window.assert_called_once()
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_manager.py::TestTmuxIntegration -v`
Expected: failure (manager doesn't reference tmux yet).

- [ ] **Step 3: Wire tmux into manager**

In `src/orca/core/worktrees/manager.py`:

```python
from orca.core.worktrees import tmux  # at module top

# In create(), after sidecar+registry written, add:
            if self.run_tmux:
                session = tmux.resolve_session_name(
                    self.cfg.tmux_session, repo_root=self.repo_root,
                )
                tmux.ensure_session(session, cwd=wt_path)
                window = lane_id[:32]
                if not tmux.has_window(session, window):
                    tmux.new_window(session=session, window=window, cwd=wt_path)
                    emit_event(self.worktree_root, event="tmux.window.created",
                               lane_id=lane_id, session=session, window=window)

# In remove(), after worktree removed, before branch delete:
            if lane_id is not None:
                session = tmux.resolve_session_name(
                    self.cfg.tmux_session, repo_root=self.repo_root,
                )
                window = lane_id[:32]
                tmux.kill_window(session=session, window=window)
                tmux.kill_session_if_empty(session)
                emit_event(self.worktree_root, event="tmux.window.killed",
                           lane_id=lane_id)
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_manager.py -v`
Expected: all manager tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/manager.py tests/core/worktrees/test_manager.py
git commit -m "feat(worktrees): tmux session/window lifecycle in manager"
```

---

## Task 22: wt init script generation (ecosystem detection)

**Files:**
- Create: `src/orca/core/worktrees/init_script.py`
- Test: `tests/core/worktrees/test_init_script.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/worktrees/test_init_script.py
from pathlib import Path

import pytest

from orca.core.worktrees.init_script import (
    detect_ecosystems, generate_after_create, EcosystemHit,
)


class TestDetectEcosystems:
    def test_detects_uv(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        (tmp_path / "uv.lock").write_text("")
        hits = detect_ecosystems(tmp_path)
        assert any(h.name == "uv" for h in hits)

    def test_detects_bun(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "bun.lockb").write_bytes(b"\x00")
        hits = detect_ecosystems(tmp_path)
        assert any(h.name == "bun" for h in hits)

    def test_detects_pip_with_requirements(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("requests\n")
        hits = detect_ecosystems(tmp_path)
        assert any(h.name == "pip" for h in hits)

    def test_warns_on_monorepo_signals(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "apps").mkdir()
        (tmp_path / "apps" / "web").mkdir()
        (tmp_path / "apps" / "web" / "package.json").write_text("{}")
        hits = detect_ecosystems(tmp_path)
        # Warning attached as a separate hit
        assert any(h.name == "monorepo_warning" for h in hits)


class TestGenerateAfterCreate:
    def test_generates_executable_script(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        (tmp_path / "uv.lock").write_text("")
        out = generate_after_create(tmp_path)
        assert out.exists()
        # Contains uv sync line
        body = out.read_text()
        assert "uv sync" in body
        # Executable bit set
        import os, stat
        assert out.stat().st_mode & stat.S_IXUSR

    def test_refuses_overwrite_without_replace(self, tmp_path):
        (tmp_path / ".orca" / "worktrees").mkdir(parents=True)
        existing = tmp_path / ".orca" / "worktrees" / "after_create"
        existing.write_text("# existing\n")
        with pytest.raises(FileExistsError):
            generate_after_create(tmp_path, replace=False)
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_init_script.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/orca/core/worktrees/init_script.py
"""Ecosystem detection + after_create script generation for `wt init`.

v1: top-level signal files only. Subdirectory monorepos emit a warning.
"""
from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EcosystemHit:
    name: str
    install_line: str | None  # None for warnings


_RULES: list[tuple[str, str, list[str]]] = [
    # (signal_file, ecosystem_name, install_command_words)
    ("uv.lock", "uv", ["uv", "sync"]),
    ("bun.lockb", "bun", ["bun", "install"]),
    ("pnpm-lock.yaml", "pnpm", ["pnpm", "install"]),
    ("yarn.lock", "yarn", ["yarn", "install"]),
    ("Cargo.toml", "cargo", ["cargo", "fetch"]),
    ("go.mod", "go", ["go", "mod", "download"]),
    ("Gemfile", "bundler", ["bundle", "install"]),
]


def detect_ecosystems(repo_root: Path) -> list[EcosystemHit]:
    """Top-level signal-file detection. Returns a list of EcosystemHit."""
    hits: list[EcosystemHit] = []
    seen_top_npm = (repo_root / "package.json").exists()

    for signal, name, install in _RULES:
        if (repo_root / signal).exists():
            hits.append(EcosystemHit(name=name, install_line=" ".join(install)))

    # node fallback: package.json + no specific lockfile -> npm install
    if seen_top_npm and not any(h.name in {"bun", "pnpm", "yarn"} for h in hits):
        hits.append(EcosystemHit(name="npm", install_line="npm install"))

    # pip via requirements*.txt (no pyproject)
    if not any(h.name == "uv" for h in hits):
        for req in sorted(repo_root.glob("requirements*.txt")):
            hits.append(EcosystemHit(name="pip",
                                     install_line=f"pip install -r {req.name}"))
            break  # one is enough; comment in script suggests editing

    # Monorepo warning
    for parent in ("apps", "packages", "crates"):
        if (repo_root / parent).is_dir():
            for child in (repo_root / parent).iterdir():
                if not child.is_dir():
                    continue
                if any((child / s).exists() for s, _, _ in _RULES) or \
                   (child / "package.json").exists():
                    hits.append(EcosystemHit(
                        name="monorepo_warning",
                        install_line=None,
                    ))
                    break

    return hits


def generate_after_create(
    repo_root: Path, *, replace: bool = False,
) -> Path:
    """Write a default after_create script. Refuses to overwrite unless
    `replace=True`. Returns the path."""
    out_dir = repo_root / ".orca" / "worktrees"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "after_create"
    if out_path.exists() and not replace:
        raise FileExistsError(f"{out_path} exists; pass replace=True to overwrite")

    hits = detect_ecosystems(repo_root)
    install_lines = [h.install_line for h in hits if h.install_line]
    has_warning = any(h.name == "monorepo_warning" for h in hits)

    body_parts = [
        "#!/usr/bin/env bash",
        "set -e",
        "",
        "# Generated by `orca-cli wt init`. Edit freely.",
        f"# Ecosystem detection found: "
        f"{', '.join(h.name for h in hits if h.install_line) or '(none)'}",
    ]
    if has_warning:
        body_parts.append(
            "# WARNING: monorepo signals detected in apps/, packages/, "
            "or crates/. Edit per-package install lines if needed."
        )
    body_parts.append("")
    if not install_lines:
        body_parts.append("# No ecosystems detected; this hook is a no-op.")
        body_parts.append("exit 0")
    else:
        for line in install_lines:
            body_parts.append(line)

    out_path.write_text("\n".join(body_parts) + "\n", encoding="utf-8")
    os.chmod(out_path, out_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return out_path
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_init_script.py -v`
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/init_script.py tests/core/worktrees/test_init_script.py
git commit -m "feat(worktrees): wt init ecosystem detection + after_create generator"
```

---

## Task 23: Hook integration in manager.create() (Stage 1 + 2 + 3)

**Files:**
- Modify: `src/orca/core/worktrees/manager.py`
- Modify: `src/orca/core/worktrees/protocol.py` (add lane_setup_version)
- Modify: `tests/core/worktrees/test_manager.py`

- [ ] **Step 1: Write failing test**

```python
# Append to tests/core/worktrees/test_manager.py
class TestSetupHooks:
    def test_after_create_runs_when_setup_enabled(self, repo):
        out = repo / "out.txt"
        ldir = repo / ".orca" / "worktrees"
        ldir.mkdir(parents=True)
        ac = ldir / "after_create"
        ac.write_text(f'#!/usr/bin/env bash\necho "ran" > "{out}"\n')
        ac.chmod(0o755)

        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=True)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[],
                            trust_hooks=True, record_trust=False)
        mgr.create(req)
        assert out.read_text().strip() == "ran"

    def test_after_create_failure_aborts_and_reverts(self, repo):
        ldir = repo / ".orca" / "worktrees"
        ldir.mkdir(parents=True)
        ac = ldir / "after_create"
        ac.write_text('#!/usr/bin/env bash\nexit 7\n')
        ac.chmod(0o755)

        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=True)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[],
                            trust_hooks=True, record_trust=False)
        with pytest.raises(RuntimeError, match="after_create failed"):
            mgr.create(req)
        # Worktree was reverted
        wt = repo / ".orca" / "worktrees" / "feature-foo"
        assert not wt.exists()
        # Branch was deleted
        result = subprocess.run(
            ["git", "-C", str(repo), "show-ref", "--verify", "--quiet",
             "refs/heads/feature-foo"],
            check=False,
        )
        assert result.returncode != 0
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/core/worktrees/test_manager.py::TestSetupHooks -v`
Expected: setup not yet wired.

- [ ] **Step 3: Wire hooks into create()**

In `src/orca/core/worktrees/manager.py`, after `git worktree add` and before sidecar write:

```python
from orca.core.worktrees.auto_symlink import run_stage1
from orca.core.worktrees.hooks import HookEnv, hook_sha, run_hook
from orca.core.worktrees.trust import (
    TrustDecision, TrustOutcome, check_or_prompt, resolve_repo_key,
)


    def _run_setup_stages(self, *, lane_id: str, wt_path: Path,
                          req: CreateRequest, base_branch: str) -> str:
        """Run Stage 1 (auto-symlink) + Stage 2 (after_create) + Stage 3
        (before_run). Returns the after_create SHA (used for setup_version)
        or '' if no after_create hook ran. Raises on Stage 2 failure."""
        # Stage 1
        run_stage1(
            primary_root=self.repo_root, worktree_dir=wt_path,
            cfg=self.cfg, host_system=self.host_system,
        )

        env = HookEnv(
            repo_root=self.repo_root, worktree_dir=wt_path,
            branch=req.branch, lane_id=lane_id,
            lane_mode="lane" if (req.feature and req.lane) else "branch",
            feature_id=req.feature, host_system=self.host_system,
        )

        ac_path = self.worktree_root / self.cfg.after_create_hook
        setup_sha = ""
        if req.no_setup:
            return ""
        if ac_path.exists():
            sha = hook_sha(ac_path)
            decision = TrustDecision(
                trust_hooks=req.trust_hooks, record=req.record_trust,
            )
            outcome = check_or_prompt(
                repo_key=resolve_repo_key(self.repo_root),
                script_path=str(ac_path),
                sha=sha,
                script_text=ac_path.read_text(encoding="utf-8"),
                decision=decision,
                interactive=os.isatty(0),
            )
            if outcome in (TrustOutcome.DECLINED,
                           TrustOutcome.REFUSED_NONINTERACTIVE):
                raise RuntimeError(
                    f"after_create hook untrusted "
                    f"(outcome={outcome.value}). Use --no-setup to skip "
                    f"or --trust-hooks to bypass."
                )

            emit_event(self.worktree_root,
                       event="setup.after_create.started",
                       lane_id=lane_id)
            result = run_hook(script_path=ac_path, env=env)
            event = ("setup.after_create.completed"
                     if result.status == "completed"
                     else "setup.after_create.failed")
            emit_event(self.worktree_root, event=event,
                       lane_id=lane_id, exit_code=result.exit_code,
                       duration_ms=result.duration_ms)
            if result.status == "failed":
                raise RuntimeError(
                    f"after_create failed (exit {result.exit_code})"
                )
            setup_sha = sha

        # Stage 3: before_run (failures log but don't abort)
        br_path = self.worktree_root / self.cfg.before_run_hook
        if br_path.exists():
            emit_event(self.worktree_root,
                       event="setup.before_run.started", lane_id=lane_id)
            result = run_hook(script_path=br_path, env=env)
            event = ("setup.before_run.completed"
                     if result.status == "completed"
                     else "setup.before_run.failed")
            emit_event(self.worktree_root, event=event,
                       lane_id=lane_id, exit_code=result.exit_code,
                       duration_ms=result.duration_ms)
            # Note: before_run failures are non-fatal per spec

        return setup_sha
```

In `create()`, after `git worktree add` succeeds and before `write_sidecar`:

```python
            if self.run_setup:
                try:
                    setup_sha = self._run_setup_stages(
                        lane_id=lane_id, wt_path=wt_path, req=req,
                        base_branch=from_branch,
                    )
                except Exception:
                    # Revert: remove worktree and (newly created) branch
                    subprocess.run(
                        ["git", "-C", str(self.repo_root), "worktree", "remove",
                         "--force", str(wt_path)],
                        check=False, capture_output=True,
                    )
                    if not branch_exists:
                        subprocess.run(
                            ["git", "-C", str(self.repo_root), "branch", "-D",
                             req.branch],
                            check=False, capture_output=True,
                        )
                    raise
            else:
                setup_sha = ""
```

Use `setup_sha` when constructing the `Sidecar`.

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_manager.py -v`
Expected: all manager tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/worktrees/manager.py tests/core/worktrees/test_manager.py
git commit -m "feat(worktrees): wire stage 1/2/3 hooks + revert-on-failure into create()"
```

---

## Task 24: Hook integration in manager.remove() (Stage 4 + agent launch in create)

**Files:**
- Modify: `src/orca/core/worktrees/manager.py`
- Modify: `tests/core/worktrees/test_manager.py`

- [ ] **Step 1: Write failing test**

```python
# Append to tests/core/worktrees/test_manager.py
class TestBeforeRemove:
    def test_before_remove_runs_before_deletion(self, repo):
        out = repo / "before_remove_ran.txt"
        ldir = repo / ".orca" / "worktrees"
        ldir.mkdir(parents=True)
        br = ldir / "before_remove"
        br.write_text(f'#!/usr/bin/env bash\necho "ran" > "{out}"\n')
        br.chmod(0o755)

        cfg = WorktreesConfig()
        mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                              run_tmux=False, run_setup=True)
        req = CreateRequest(branch="feature-foo", from_branch=None,
                            feature=None, lane=None, agent="none",
                            prompt=None, extra_args=[],
                            trust_hooks=True, record_trust=False)
        mgr.create(req)
        mgr.remove(RemoveRequest(branch="feature-foo", force=False,
                                 keep_branch=False, all_lanes=False))
        assert out.read_text().strip() == "ran"


class TestAgentLaunch:
    def test_creates_launcher_when_agent_set(self, repo):
        cfg = WorktreesConfig()
        with patch("orca.core.worktrees.manager.tmux") as tm:
            tm.resolve_session_name.return_value = "orca"
            mgr = WorktreeManager(repo_root=repo, cfg=cfg, host_system="bare",
                                  run_tmux=True, run_setup=False)
            req = CreateRequest(branch="feature-foo", from_branch=None,
                                feature=None, lane=None, agent="claude",
                                prompt="hello", extra_args=[])
            mgr.create(req)
            wt = repo / ".orca" / "worktrees" / "feature-foo"
            assert (wt / ".orca" / ".run-feature-foo.sh").exists()
            tm.send_keys.assert_called()
```

- [ ] **Step 2: Add agent-launch + before_remove to manager**

```python
from orca.core.worktrees.agent_launch import write_launcher

# In create(), after tmux window created:
            if self.run_tmux and req.agent != "none":
                cmd = self.cfg.agents.get(req.agent)
                if cmd:
                    write_launcher(
                        worktree_dir=wt_path, lane_id=lane_id,
                        agent_cmd=cmd, prompt=req.prompt,
                        extra_args=list(req.extra_args),
                    )
                    tmux.send_keys(
                        session=session, window=window,
                        keys=f"bash .orca/.run-{lane_id}.sh",
                    )
                    emit_event(self.worktree_root, event="agent.launched",
                               lane_id=lane_id, agent=req.agent)

# In remove(), before worktree-remove:
            br_path = self.worktree_root / self.cfg.before_remove_hook
            if lane_id is not None and br_path.exists() and existing_wt is not None:
                env = HookEnv(
                    repo_root=self.repo_root, worktree_dir=existing_wt,
                    branch=req.branch, lane_id=lane_id, lane_mode="branch",
                    feature_id=None, host_system=self.host_system,
                )
                emit_event(self.worktree_root,
                           event="setup.before_remove.started", lane_id=lane_id)
                result = run_hook(script_path=br_path, env=env)
                emit_event(self.worktree_root,
                           event=(f"setup.before_remove."
                                  f"{'completed' if result.status == 'completed' else 'failed'}"),
                           lane_id=lane_id, exit_code=result.exit_code,
                           duration_ms=result.duration_ms)
```

- [ ] **Step 3: Run passing**

Run: `uv run python -m pytest tests/core/worktrees/test_manager.py -v`
Expected: all 14 manager tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/orca/core/worktrees/manager.py tests/core/worktrees/test_manager.py
git commit -m "feat(worktrees): before_remove hook + agent-launch in create()"
```

---

## Task 25: CLI dispatch table + `wt new` handler

**Files:**
- Modify: `src/orca/python_cli.py`
- Test: `tests/cli/test_wt_cli.py`

- [ ] **Step 1: Write failing CLI test**

```python
# tests/cli/test_wt_cli.py
import json
import subprocess
import sys
from pathlib import Path

import pytest


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           **__import__("os").environ}
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-m", "init"],
        check=True, env=env,
    )
    return tmp_path


@pytest.fixture
def repo(tmp_path):
    return _init_repo(tmp_path)


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "wt", *args,
         "--no-tmux", "--no-setup"],
        cwd=str(repo),
        capture_output=True, text=True, check=False,
    )


class TestWtNew:
    def test_creates_worktree_via_cli(self, repo):
        result = _run(repo, "new", "feature-foo")
        assert result.returncode == 0, result.stderr
        # Worktree path printed on stdout
        path = result.stdout.strip()
        assert Path(path).is_dir()
        assert path.endswith("feature-foo")

    def test_emits_json_envelope_on_failure(self, repo):
        # Bad branch name (path-safety rejects)
        result = _run(repo, "new", "..")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["ok"] is False
        assert envelope["error"]["kind"] == "input_invalid"

    def test_unknown_subverb_returns_input_invalid(self, repo):
        result = subprocess.run(
            [sys.executable, "-m", "orca.python_cli", "wt", "exterminate"],
            cwd=str(repo), capture_output=True, text=True, check=False,
        )
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["error"]["kind"] == "input_invalid"
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/cli/test_wt_cli.py -v`
Expected: `wt` capability not registered.

- [ ] **Step 3: Add CLI dispatch + new handler in `src/orca/python_cli.py`**

Near the bottom of the file (where other capabilities are registered):

```python
def _run_wt(args: list[str]) -> int:
    """Top-level wt dispatcher. Routes wt <verb> to _run_wt_<verb>."""
    if not args:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0",
                ErrorKind.INPUT_INVALID,
                "wt requires a subverb (new|start|cd|ls|merge|rm|init|"
                "config|version|doctor)",
            ),
            pretty=False,
            exit_code=2,
        )
    verb = args[0]
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
    }
    handler = handlers.get(verb)
    if handler is None:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0",
                ErrorKind.INPUT_INVALID,
                f"unknown wt verb: {verb}",
            ),
            pretty=False,
            exit_code=2,
        )
    return handler(args[1:])


def _detect_host_system(repo_root: Path) -> str:
    """Detect host system; falls back to 'bare' if no manifest or marker."""
    manifest = repo_root / ".orca" / "adoption.toml"
    if manifest.exists():
        try:
            from orca.core.adoption.manifest import load_manifest
            m = load_manifest(manifest)
            return m.host.system
        except Exception:
            pass
    # Detection fallback
    if (repo_root / ".specify").is_dir():
        return "spec-kit"
    if (repo_root / "openspec" / "changes").is_dir():
        return "openspec"
    if (repo_root / "docs" / "superpowers").is_dir():
        return "superpowers"
    return "bare"


def _run_wt_new(args: list[str]) -> int:
    import argparse
    from orca.core.path_safety import PathSafetyError
    from orca.core.worktrees.config import load_config
    from orca.core.worktrees.manager import (
        WorktreeManager, IdempotencyError,
    )
    from orca.core.worktrees.protocol import CreateRequest

    parser = argparse.ArgumentParser(prog="orca-cli wt new", exit_on_error=False)
    parser.add_argument("branch")
    parser.add_argument("--from", dest="from_branch", default=None)
    parser.add_argument("--feature", default=None)
    parser.add_argument("--lane", default=None)
    parser.add_argument("--agent", choices=["claude", "codex", "none"], default=None)
    parser.add_argument("--no-tmux", dest="no_tmux", action="store_true")
    parser.add_argument("--no-setup", dest="no_setup", action="store_true")
    parser.add_argument("--reuse-branch", dest="reuse_branch", action="store_true")
    parser.add_argument("--recreate-branch", dest="recreate_branch", action="store_true")
    parser.add_argument("--trust-hooks", dest="trust_hooks", action="store_true")
    parser.add_argument("--record", dest="record_trust", action="store_true")
    parser.add_argument("-p", dest="prompt", default=None)

    try:
        ns, extra = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0", ErrorKind.INPUT_INVALID,
                f"argv parse error: {exc}",
            ),
            pretty=False, exit_code=2,
        )

    # Pop out '--' separator if present; trailing args are agent extras
    extra_args: list[str] = []
    if "--" in extra:
        sep = extra.index("--")
        extra_args = extra[sep + 1:]
        extra = extra[:sep]
    if extra:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0", ErrorKind.INPUT_INVALID,
                f"unknown args: {extra}",
            ),
            pretty=False, exit_code=2,
        )

    repo_root = Path.cwd().resolve()
    cfg = load_config(repo_root)
    host = _detect_host_system(repo_root)
    agent = ns.agent or cfg.default_agent

    mgr = WorktreeManager(
        repo_root=repo_root, cfg=cfg, host_system=host,
        run_tmux=not ns.no_tmux, run_setup=not ns.no_setup,
    )
    req = CreateRequest(
        branch=ns.branch, from_branch=ns.from_branch,
        feature=ns.feature, lane=ns.lane,
        agent=agent, prompt=ns.prompt, extra_args=extra_args,
        reuse_branch=ns.reuse_branch, recreate_branch=ns.recreate_branch,
        no_setup=ns.no_setup,
        trust_hooks=ns.trust_hooks, record_trust=ns.record_trust,
    )
    try:
        result = mgr.create(req)
    except (IdempotencyError, PathSafetyError) as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0", ErrorKind.INPUT_INVALID, str(exc),
            ),
            pretty=False, exit_code=1,
        )
    except RuntimeError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "wt", "1.0.0", ErrorKind.BACKEND_FAILURE, str(exc),
            ),
            pretty=False, exit_code=1,
        )

    print(str(result.worktree_path))
    return 0


# Stub the other verbs (filled in next tasks)
def _run_wt_start(args): return _stub_unimplemented("start")
def _run_wt_cd(args): return _stub_unimplemented("cd")
def _run_wt_ls(args): return _stub_unimplemented("ls")
def _run_wt_rm(args): return _stub_unimplemented("rm")
def _run_wt_merge(args): return _stub_unimplemented("merge")
def _run_wt_init(args): return _stub_unimplemented("init")
def _run_wt_config(args): return _stub_unimplemented("config")
def _run_wt_version(args): return _stub_unimplemented("version")
def _run_wt_doctor(args): return _stub_unimplemented("doctor")


def _stub_unimplemented(verb: str) -> int:
    return _emit_envelope(
        envelope=_err_envelope(
            "wt", "1.0.0", ErrorKind.INPUT_INVALID,
            f"wt {verb} not yet implemented",
        ),
        pretty=False, exit_code=2,
    )


_register("wt", _run_wt, "1.0.0")
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/cli/test_wt_cli.py::TestWtNew -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_wt_cli.py
git commit -m "feat(cli): wt dispatcher + wt new handler"
```

---

## Task 26: `wt rm` + `wt cd`

**Files:**
- Modify: `src/orca/python_cli.py`
- Modify: `tests/cli/test_wt_cli.py`

- [ ] **Step 1: Add failing tests**

```python
# Append to tests/cli/test_wt_cli.py
class TestWtRm:
    def test_removes_lane(self, repo):
        result = _run(repo, "new", "feat-rm")
        assert result.returncode == 0
        wt_path = Path(result.stdout.strip())

        result = _run(repo, "rm", "feat-rm")
        assert result.returncode == 0, result.stderr
        assert not wt_path.exists()

    def test_no_op_when_lane_missing(self, repo):
        result = _run(repo, "rm", "never-existed")
        assert result.returncode == 0


class TestWtCd:
    def test_no_arg_prints_repo_root(self, repo):
        result = _run(repo, "cd")
        assert result.returncode == 0
        assert Path(result.stdout.strip()).resolve() == repo.resolve()

    def test_branch_arg_prints_worktree_path(self, repo):
        _run(repo, "new", "feat-cd")
        result = _run(repo, "cd", "feat-cd")
        assert result.returncode == 0
        assert result.stdout.strip().endswith("feat-cd")

    def test_lane_id_arg_resolves(self, repo):
        _run(repo, "new", "feature/123-xyz")  # lane-id "feature-123-xyz"
        result = _run(repo, "cd", "feature-123-xyz")
        assert result.returncode == 0
        assert result.stdout.strip().endswith("feature-123-xyz")
```

- [ ] **Step 2: Run failing**

Run: `uv run python -m pytest tests/cli/test_wt_cli.py::TestWtRm tests/cli/test_wt_cli.py::TestWtCd -v`
Expected: stub error.

- [ ] **Step 3: Implement `_run_wt_rm` and `_run_wt_cd`**

Replace stubs in `src/orca/python_cli.py`:

```python
def _run_wt_rm(args: list[str]) -> int:
    import argparse
    from orca.core.worktrees.config import load_config
    from orca.core.worktrees.manager import (
        WorktreeManager, IdempotencyError,
    )
    from orca.core.worktrees.protocol import RemoveRequest

    parser = argparse.ArgumentParser(prog="orca-cli wt rm", exit_on_error=False)
    parser.add_argument("branch", nargs="?", default=None)
    parser.add_argument("--all", dest="all_lanes", action="store_true")
    parser.add_argument("-f", "--force", action="store_true")
    parser.add_argument("--keep-branch", dest="keep_branch", action="store_true")
    parser.add_argument("--no-tmux", dest="no_tmux", action="store_true")
    parser.add_argument("--no-setup", dest="no_setup", action="store_true")

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
    if not ns.branch and not ns.all_lanes:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    "wt rm requires <branch> or --all"),
            pretty=False, exit_code=2,
        )

    repo_root = Path.cwd().resolve()
    cfg = load_config(repo_root)
    host = _detect_host_system(repo_root)
    mgr = WorktreeManager(
        repo_root=repo_root, cfg=cfg, host_system=host,
        run_tmux=not ns.no_tmux, run_setup=not ns.no_setup,
    )
    try:
        if ns.all_lanes:
            from orca.core.worktrees.registry import read_registry
            view = read_registry(repo_root / ".orca" / "worktrees")
            for lane in view.lanes:
                mgr.remove(RemoveRequest(branch=lane.branch, force=ns.force,
                                         keep_branch=ns.keep_branch,
                                         all_lanes=False))
        else:
            mgr.remove(RemoveRequest(branch=ns.branch, force=ns.force,
                                     keep_branch=ns.keep_branch,
                                     all_lanes=False))
    except IdempotencyError as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID, str(exc)),
            pretty=False, exit_code=1,
        )
    return 0


def _run_wt_cd(args: list[str]) -> int:
    """Print worktree path (or repo root). Operator wraps in $(...)."""
    import argparse
    from orca.core.worktrees.registry import read_registry, sidecar_path, read_sidecar

    parser = argparse.ArgumentParser(prog="orca-cli wt cd", exit_on_error=False)
    parser.add_argument("target", nargs="?", default=None)
    try:
        ns, _ = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit):
        ns = parser.parse_args([])

    repo_root = Path.cwd().resolve()
    if not ns.target:
        print(str(repo_root))
        return 0

    wt_root = repo_root / ".orca" / "worktrees"
    # Try lane-id first
    sc = read_sidecar(sidecar_path(wt_root, ns.target))
    if sc is not None:
        print(sc.worktree_path)
        return 0
    # Fall back to branch lookup
    view = read_registry(wt_root)
    for row in view.lanes:
        if row.branch == ns.target:
            print(row.worktree_path)
            return 0

    return _emit_envelope(
        envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                f"no worktree for {ns.target!r}"),
        pretty=False, exit_code=1,
    )
```

- [ ] **Step 4: Run passing**

Run: `uv run python -m pytest tests/cli/test_wt_cli.py -v`
Expected: rm + cd tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_wt_cli.py
git commit -m "feat(cli): wt rm + wt cd"
```

---

## Task 27: `wt ls` with JSON shape + tmux liveness probe

**Files:**
- Modify: `src/orca/python_cli.py`
- Modify: `tests/cli/test_wt_cli.py`

- [ ] **Step 1: Add failing tests**

```python
# Append to tests/cli/test_wt_cli.py
class TestWtLs:
    def test_human_table(self, repo):
        _run(repo, "new", "feat-a")
        _run(repo, "new", "feat-b")
        result = _run(repo, "ls")
        assert result.returncode == 0
        assert "feat-a" in result.stdout
        assert "feat-b" in result.stdout

    def test_json_shape(self, repo):
        _run(repo, "new", "feat-x")
        result = _run(repo, "ls", "--json")
        assert result.returncode == 0
        envelope = json.loads(result.stdout)
        assert envelope["schema_version"] == 1
        lanes = envelope["lanes"]
        assert len(lanes) == 1
        # Required keys per spec
        for key in ("lane_id", "branch", "worktree_path", "feature_id",
                    "tmux_state", "agent", "last_attached_at",
                    "setup_version"):
            assert key in lanes[0]
```

- [ ] **Step 2: Implement**

Replace `_run_wt_ls` stub:

```python
def _run_wt_ls(args: list[str]) -> int:
    import argparse
    from orca.core.worktrees.registry import (
        read_registry, sidecar_path, read_sidecar,
    )
    from orca.core.worktrees.tmux import (
        list_windows, resolve_session_name,
    )
    from orca.core.worktrees.config import load_config

    parser = argparse.ArgumentParser(prog="orca-cli wt ls", exit_on_error=False)
    parser.add_argument("--json", dest="as_json", action="store_true")
    parser.add_argument("--all", dest="show_all", action="store_true")
    try:
        ns, _ = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit):
        ns = parser.parse_args([])

    repo_root = Path.cwd().resolve()
    cfg = load_config(repo_root)
    wt_root = repo_root / ".orca" / "worktrees"
    view = read_registry(wt_root)
    session = resolve_session_name(cfg.tmux_session, repo_root=repo_root)
    live_windows = set(list_windows(session))

    rows = []
    for lane in view.lanes:
        sc = read_sidecar(sidecar_path(wt_root, lane.lane_id))
        window = lane.lane_id[:32]
        if not live_windows:
            tmux_state = "session-missing"
        elif window in live_windows:
            tmux_state = "attached"
        else:
            tmux_state = "stale"
        rows.append({
            "lane_id": lane.lane_id,
            "branch": lane.branch,
            "worktree_path": lane.worktree_path,
            "feature_id": lane.feature_id,
            "tmux_state": tmux_state,
            "agent": (sc.agent if sc else "none"),
            "last_attached_at": (sc.last_attached_at if sc else None),
            "setup_version": (sc.setup_version if sc else None),
        })

    if ns.as_json:
        print(json.dumps({"schema_version": 1, "lanes": rows},
                         indent=2, sort_keys=True))
        return 0

    # Human table
    if not rows:
        print("(no lanes)")
        return 0
    headers = ["LANE_ID", "BRANCH", "TMUX", "AGENT", "PATH"]
    widths = [max(len(h), max((len(str(r[k])) for r in rows), default=0))
              for h, k in zip(headers,
                              ["lane_id", "branch", "tmux_state", "agent",
                               "worktree_path"])]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    for r in rows:
        print(fmt.format(r["lane_id"], r["branch"], r["tmux_state"],
                          r["agent"] or "none", r["worktree_path"]))
    return 0
```

- [ ] **Step 3: Run passing**

Run: `uv run python -m pytest tests/cli/test_wt_cli.py::TestWtLs -v`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_wt_cli.py
git commit -m "feat(cli): wt ls with tmux liveness probe + JSON shape"
```

---

## Task 28: `wt start` + `wt config` + `wt version`

**Files:**
- Modify: `src/orca/python_cli.py`
- Modify: `tests/cli/test_wt_cli.py`

- [ ] **Step 1: Add failing tests**

```python
# Append to tests/cli/test_wt_cli.py
class TestWtStartConfigVersion:
    def test_start_refuses_when_no_lane(self, repo):
        result = _run(repo, "start", "missing")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert envelope["error"]["kind"] == "input_invalid"

    def test_start_runs_before_run_hook(self, repo):
        _run(repo, "new", "feat-s")
        out = repo / "ran.txt"
        ldir = repo / ".orca" / "worktrees"
        br = ldir / "before_run"
        br.write_text(f'#!/usr/bin/env bash\necho "x" > "{out}"\n')
        br.chmod(0o755)
        result = _run(repo, "start", "feat-s", "--trust-hooks")
        assert result.returncode == 0
        assert out.read_text().strip() == "x"

    def test_config_json_shape(self, repo):
        result = _run(repo, "config", "--json")
        assert result.returncode == 0
        envelope = json.loads(result.stdout)
        assert envelope["schema_version"] == 1
        assert "effective" in envelope
        assert "sources" in envelope

    def test_version(self, repo):
        result = _run(repo, "version")
        assert result.returncode == 0
        # Format: "<orca version> wt-schema=<version>"
        assert "wt-schema=" in result.stdout
```

- [ ] **Step 2: Implement**

Replace stubs:

```python
def _run_wt_start(args: list[str]) -> int:
    import argparse
    from orca.core.worktrees.config import load_config
    from orca.core.worktrees.registry import (
        read_registry, read_sidecar, sidecar_path, write_sidecar, Sidecar,
        acquire_registry_lock,
    )
    from orca.core.worktrees.events import emit_event
    from orca.core.worktrees.hooks import HookEnv, hook_sha, run_hook
    from orca.core.worktrees.tmux import (
        ensure_session, has_window, new_window, send_keys,
        resolve_session_name,
    )

    parser = argparse.ArgumentParser(prog="orca-cli wt start", exit_on_error=False)
    parser.add_argument("branch")
    parser.add_argument("--agent", choices=["claude", "codex", "none"], default=None)
    parser.add_argument("-p", dest="prompt", default=None)
    parser.add_argument("--rerun-setup", dest="rerun_setup", action="store_true")
    parser.add_argument("--no-tmux", dest="no_tmux", action="store_true")
    parser.add_argument("--trust-hooks", dest="trust_hooks", action="store_true")
    try:
        ns, _ = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"argv parse error: {exc}"),
            pretty=False, exit_code=2,
        )

    repo_root = Path.cwd().resolve()
    cfg = load_config(repo_root)
    wt_root = repo_root / ".orca" / "worktrees"

    view = read_registry(wt_root)
    row = next((l for l in view.lanes if l.branch == ns.branch), None)
    if row is None:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"no lane for branch {ns.branch!r}; "
                                    f"run wt new first"),
            pretty=False, exit_code=1,
        )

    sc = read_sidecar(sidecar_path(wt_root, row.lane_id))
    wt_path = Path(row.worktree_path)

    if not ns.no_tmux:
        session = resolve_session_name(cfg.tmux_session, repo_root=repo_root)
        ensure_session(session, cwd=wt_path)
        window = row.lane_id[:32]
        if not has_window(session, window):
            new_window(session=session, window=window, cwd=wt_path)

    # Stage 3 (before_run)
    br = wt_root / cfg.before_run_hook
    if br.exists():
        env = HookEnv(
            repo_root=repo_root, worktree_dir=wt_path, branch=ns.branch,
            lane_id=row.lane_id,
            lane_mode=("lane" if (sc and sc.feature_id and sc.lane_name)
                       else "branch"),
            feature_id=(sc.feature_id if sc else None),
            host_system=(sc.host_system if sc else "bare"),
        )
        emit_event(wt_root, event="setup.before_run.started", lane_id=row.lane_id)
        result = run_hook(script_path=br, env=env)
        emit_event(wt_root,
                   event=("setup.before_run.completed" if result.status == "completed"
                          else "setup.before_run.failed"),
                   lane_id=row.lane_id, exit_code=result.exit_code,
                   duration_ms=result.duration_ms)

    # Update last_attached_at + emit lane.attached
    if sc is not None:
        from datetime import datetime, timezone
        new_sc = Sidecar(
            **{**sc.__dict__,
               "last_attached_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        )
        with acquire_registry_lock(wt_root):
            write_sidecar(wt_root, new_sc)
    emit_event(wt_root, event="lane.attached", lane_id=row.lane_id)
    print(str(wt_path))
    return 0


def _run_wt_config(args: list[str]) -> int:
    import argparse
    from orca.core.worktrees.config import load_config
    from dataclasses import asdict

    parser = argparse.ArgumentParser(prog="orca-cli wt config", exit_on_error=False)
    parser.add_argument("--json", dest="as_json", action="store_true")
    try:
        ns, _ = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit):
        ns = parser.parse_args([])

    repo_root = Path.cwd().resolve()
    cfg = load_config(repo_root)
    payload = {
        "schema_version": 1,
        "effective": asdict(cfg),
        "sources": {
            "committed": ".orca/worktrees.toml",
            "local": ".orca/worktrees.local.toml",
        },
    }
    if ns.as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"base               {cfg.base}")
    print(f"lane_id_mode       {cfg.lane_id_mode}")
    print(f"tmux_session       {cfg.tmux_session}")
    print(f"default_agent      {cfg.default_agent}")
    return 0


def _run_wt_version(args: list[str]) -> int:
    from orca.core.worktrees.registry import SCHEMA_VERSION
    print(f"orca {_pkg_version('orca')} wt-schema={SCHEMA_VERSION}")
    return 0
```

- [ ] **Step 3: Run passing**

Run: `uv run python -m pytest tests/cli/test_wt_cli.py::TestWtStartConfigVersion -v`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_wt_cli.py
git commit -m "feat(cli): wt start + wt config + wt version"
```

---

## Task 29: `wt init` + `wt merge`

**Files:**
- Modify: `src/orca/python_cli.py`
- Modify: `tests/cli/test_wt_cli.py`

- [ ] **Step 1: Add failing tests**

```python
# Append to tests/cli/test_wt_cli.py
class TestWtInitMerge:
    def test_init_writes_after_create(self, repo):
        (repo / "pyproject.toml").write_text("[project]\nname='x'\n")
        (repo / "uv.lock").write_text("")
        result = _run(repo, "init")
        assert result.returncode == 0, result.stderr
        ac = repo / ".orca" / "worktrees" / "after_create"
        assert ac.exists()
        assert "uv sync" in ac.read_text()

    def test_init_refuses_overwrite_without_replace(self, repo):
        ldir = repo / ".orca" / "worktrees"
        ldir.mkdir(parents=True)
        (ldir / "after_create").write_text("# existing\n")
        result = _run(repo, "init")
        assert result.returncode != 0
        envelope = json.loads(result.stdout)
        assert "exists" in envelope["error"]["message"].lower()

    def test_merge_invokes_git_merge(self, repo):
        # Create + commit on a feature branch
        _run(repo, "new", "feat-merge")
        wt_path = repo / ".orca" / "worktrees" / "feat-merge"
        (wt_path / "f.txt").write_text("x")
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
               **__import__("os").environ}
        subprocess.run(["git", "-C", str(wt_path), "add", "f.txt"], check=True, env=env)
        subprocess.run(["git", "-C", str(wt_path), "commit", "-m", "x"],
                       check=True, env=env)

        result = _run(repo, "merge", "feat-merge")
        assert result.returncode == 0, result.stderr
        # File now in primary main
        assert (repo / "f.txt").exists()
```

- [ ] **Step 2: Implement**

Replace stubs:

```python
def _run_wt_init(args: list[str]) -> int:
    import argparse
    from orca.core.worktrees.config import write_default_config
    from orca.core.worktrees.init_script import generate_after_create

    parser = argparse.ArgumentParser(prog="orca-cli wt init", exit_on_error=False)
    parser.add_argument("--replace", action="store_true")
    try:
        ns, _ = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit):
        ns = parser.parse_args([])

    repo_root = Path.cwd().resolve()
    write_default_config(repo_root)
    try:
        generate_after_create(repo_root, replace=ns.replace)
    except FileExistsError as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID, str(exc)),
            pretty=False, exit_code=1,
        )

    print(f"wrote .orca/worktrees.toml and .orca/worktrees/after_create")
    if (repo_root / "worktrees").is_dir():
        print("note: orca worktrees live at .orca/worktrees/; "
              "this is unrelated to the existing worktrees/ directory in your repo")
    return 0


def _run_wt_merge(args: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="orca-cli wt merge", exit_on_error=False)
    parser.add_argument("branch")
    parser.add_argument("--into", dest="into", default=None)
    try:
        ns, extra = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.INPUT_INVALID,
                                    f"argv parse error: {exc}"),
            pretty=False, exit_code=2,
        )
    repo_root = Path.cwd().resolve()
    target = ns.into
    if target is None:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "symbolic-ref",
             "--short", "refs/remotes/origin/HEAD"],
            capture_output=True, text=True, check=False,
        )
        target = (result.stdout.strip().split("/")[-1] if result.returncode == 0
                  else "main")
    # Switch to target then merge
    sw = subprocess.run(
        ["git", "-C", str(repo_root), "switch", target],
        capture_output=True, text=True, check=False,
    )
    if sw.returncode != 0:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.BACKEND_FAILURE,
                                    f"git switch failed: {sw.stderr}"),
            pretty=False, exit_code=1,
        )
    cmd = ["git", "-C", str(repo_root), "merge", *extra, ns.branch]
    mr = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if mr.returncode != 0:
        return _emit_envelope(
            envelope=_err_envelope("wt", "1.0.0", ErrorKind.BACKEND_FAILURE,
                                    f"git merge failed: {mr.stderr}"),
            pretty=False, exit_code=1,
        )
    print(mr.stdout)
    return 0
```

- [ ] **Step 3: Run passing**

Run: `uv run python -m pytest tests/cli/test_wt_cli.py::TestWtInitMerge -v`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_wt_cli.py
git commit -m "feat(cli): wt init + wt merge"
```

---

## Task 30: `wt doctor` (read-only) + `--reap`

**Files:**
- Modify: `src/orca/python_cli.py`
- Modify: `tests/cli/test_wt_cli.py`

- [ ] **Step 1: Add failing tests**

```python
# Append to tests/cli/test_wt_cli.py
class TestWtDoctor:
    def test_clean_state_reports_ok(self, repo):
        _run(repo, "new", "feat-d")
        result = _run(repo, "doctor")
        assert result.returncode == 0
        assert "ok" in result.stdout.lower() or "clean" in result.stdout.lower()

    def test_orphan_sidecar_detected(self, repo):
        _run(repo, "new", "feat-d")
        # Force-remove the worktree, leaving sidecar
        wt = repo / ".orca" / "worktrees" / "feat-d"
        import shutil; shutil.rmtree(wt)
        subprocess.run(["git", "-C", str(repo), "worktree", "prune"],
                       check=True, capture_output=True)
        result = _run(repo, "doctor")
        # Doctor exit 0 with warnings; or non-zero on orphan?
        # Spec: doctor surfaces issues and exits non-zero when issues present
        assert result.returncode != 0
        assert "feat-d" in result.stdout or "feat-d" in result.stderr
```

- [ ] **Step 2: Implement**

Replace stub:

```python
def _run_wt_doctor(args: list[str]) -> int:
    import argparse
    from orca.core.worktrees.config import load_config
    from orca.core.worktrees.registry import (
        read_registry, sidecar_path, read_sidecar,
    )
    from orca.core.worktrees.tmux import (
        list_windows, resolve_session_name,
    )

    parser = argparse.ArgumentParser(prog="orca-cli wt doctor", exit_on_error=False)
    parser.add_argument("--reap", action="store_true")
    parser.add_argument("-y", dest="assume_yes", action="store_true")
    try:
        ns, _ = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit):
        ns = parser.parse_args([])

    repo_root = Path.cwd().resolve()
    cfg = load_config(repo_root)
    wt_root = repo_root / ".orca" / "worktrees"
    view = read_registry(wt_root)
    issues: list[str] = []

    # Check git worktrees vs registry
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, check=True,
        )
        git_paths = []
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                git_paths.append(line[len("worktree "):].strip())
    except subprocess.CalledProcessError:
        git_paths = []

    registered_paths = {l.worktree_path for l in view.lanes}
    for gp in git_paths:
        if gp != str(repo_root) and gp not in registered_paths and \
           Path(gp).is_relative_to(wt_root) if Path(gp).is_absolute() else False:
            issues.append(f"orphan-git: worktree {gp} not in registry")

    for lane in view.lanes:
        if not Path(lane.worktree_path).exists():
            issues.append(f"orphan-sidecar: worktree {lane.worktree_path} missing on disk for {lane.lane_id}")

    # Sidecar without registry
    if wt_root.exists():
        for sc_file in wt_root.glob("*.json"):
            if sc_file.name == "registry.json":
                continue
            sc = read_sidecar(sc_file)
            if sc is None:
                continue
            if not any(l.lane_id == sc.lane_id for l in view.lanes):
                issues.append(f"orphan-sidecar: {sc.lane_id} has sidecar but no registry entry")

    # tmux liveness
    session = resolve_session_name(cfg.tmux_session, repo_root=repo_root)
    live = set(list_windows(session))
    for lane in view.lanes:
        window = lane.lane_id[:32]
        if live and window not in live:
            issues.append(f"tmux-stale: lane {lane.lane_id} has no live tmux window")

    if not issues:
        print("ok: no issues detected")
        return 0

    for issue in issues:
        print(issue)

    if ns.reap:
        # v1: only handle orphan-sidecar (no git worktree on disk)
        for lane in view.lanes:
            if not Path(lane.worktree_path).exists():
                if not ns.assume_yes:
                    print(f"reap orphan {lane.lane_id}? [y/N]: ", end="", flush=True)
                    answer = sys.stdin.readline().strip().lower()
                    if answer != "y":
                        continue
                # Clean
                scp = sidecar_path(wt_root, lane.lane_id)
                if scp.exists():
                    scp.unlink()
                from orca.core.worktrees.registry import (
                    write_registry, acquire_registry_lock,
                )
                with acquire_registry_lock(wt_root):
                    new_view = read_registry(wt_root)
                    write_registry(wt_root, [
                        l for l in new_view.lanes if l.lane_id != lane.lane_id
                    ])
                print(f"reaped {lane.lane_id}")

    return 1
```

- [ ] **Step 3: Run passing**

Run: `uv run python -m pytest tests/cli/test_wt_cli.py -v`
Expected: all CLI tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_wt_cli.py
git commit -m "feat(cli): wt doctor + --reap"
```

---

## Task 31: Adoption-flow integration — apply runs `wt init`

**Files:**
- Modify: `src/orca/core/adoption/wizard.py` (default `enabled_features = ["worktrees"]`)
- Modify: `src/orca/core/adoption/apply.py` (run `wt init` non-interactive)
- Modify: `tests/core/adoption/test_apply.py` (add test)

- [ ] **Step 1: Add failing test**

```python
# tests/core/adoption/test_apply.py (append)
def test_apply_runs_wt_init_when_worktrees_enabled(tmp_path):
    # Set up a minimal adopted repo with worktrees feature enabled
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)

    from orca.core.adoption.wizard import build_default_manifest
    from orca.core.adoption.manifest import write_manifest
    from orca.core.adoption.apply import apply

    manifest = build_default_manifest(tmp_path, host_override="bare")
    # Force enabled_features to include worktrees
    # (current default once Task 31 lands)
    write_manifest(manifest, tmp_path / ".orca" / "adoption.toml")

    apply(repo_root=tmp_path)
    # worktrees.toml + after_create should exist
    assert (tmp_path / ".orca" / "worktrees.toml").exists()
```

- [ ] **Step 2: Wire it up**

In `src/orca/core/adoption/apply.py`, near the end of `apply`:

```python
    # If worktrees feature enabled, run wt init non-interactively
    from orca.core.adoption.manifest import load_manifest
    m = load_manifest(repo_root / ".orca" / "adoption.toml")
    if "worktrees" in (getattr(m.orca, "enabled_features", None) or ["worktrees"]):
        from orca.core.worktrees.config import write_default_config
        from orca.core.worktrees.init_script import generate_after_create
        write_default_config(repo_root)
        try:
            generate_after_create(repo_root, replace=False)
        except FileExistsError:
            pass  # operator already initialized
```

NOTE: `OrcaConfig.enabled_features` doesn't exist yet — this is a forward-compatible read. The manifest schema bump to add `enabled_features` is tracked separately; for v1 the default-on path is unconditional.

Simplify to unconditional for v1:

```python
    # Worktree manager is default-on per spec; future schema bump will gate
    # this on `[orca] enabled_features`. For v1 we always seed the config.
    from orca.core.worktrees.config import write_default_config
    write_default_config(repo_root)
```

- [ ] **Step 3: Run passing**

Run: `uv run python -m pytest tests/core/adoption/test_apply.py -v`
Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/orca/core/adoption/apply.py tests/core/adoption/test_apply.py
git commit -m "feat(adoption): seed worktrees.toml during orca-cli apply"
```

---

## Task 32: Doctor warning for missing worktrees.toml + AGENTS.md row + README

**Files:**
- Modify: `scripts/bash/orca-doctor.sh`
- Modify: `plugins/codex/AGENTS.md`
- Modify: `README.md`

- [ ] **Step 1: Locate doctor script and pattern**

Run: `grep -n "function\|check_" scripts/bash/orca-doctor.sh | head -20`

- [ ] **Step 2: Add worktree-check to doctor**

Add a check function that warns when adoption manifest exists but `.orca/worktrees.toml` is missing:

```bash
# scripts/bash/orca-doctor.sh — add near the end of checks:
check_worktree_config() {
  local repo_root="$1"
  if [[ -f "$repo_root/.orca/adoption.toml" && ! -f "$repo_root/.orca/worktrees.toml" ]]; then
    warn "missing .orca/worktrees.toml; run 'orca-cli wt init' to seed it"
    return 1
  fi
  return 0
}

# Call it where other checks run
check_worktree_config "$REPO_ROOT" || true
```

- [ ] **Step 3: Add AGENTS.md row**

In `plugins/codex/AGENTS.md`, append a row to the utility-subcommands table:

```markdown
| `wt` | Opinionated worktree + tmux manager. Subverbs: `new`, `start`, `cd`, `ls`, `merge`, `rm`, `init`, `config`, `version`, `doctor`. See `docs/superpowers/specs/2026-04-30-orca-worktree-manager-design.md`. | `src/orca/python_cli.py` `_run_wt` |
```

- [ ] **Step 4: Add README section**

Append to `README.md`:

```markdown
## Worktree Manager (orca-cli wt)

Opinionated tmux-mediated worktree manager with cmux-parity command surface.
Run `orca-cli wt init` to seed `.orca/worktrees.toml` and a default
`after_create` hook based on detected ecosystems (uv, bun, npm, cargo, etc.).
Then:

- `orca-cli wt new <branch> [-p <prompt>]` — creates worktree, runs hooks,
  spawns tmux window, optionally launches an agent
- `orca-cli wt ls [--json]` — list lanes with tmux liveness state
- `orca-cli wt rm <branch> [-f] [--keep-branch]` — tear down
- `orca-cli wt doctor [--reap]` — find orphans and optionally clean

Hooks at `.orca/worktrees/{after_create,before_run,before_remove}` run
with the operator's full privileges; first-run prompts for trust.
Pass `--trust-hooks` for one-off CI bypass, or `--trust-hooks --record`
to remember the script SHA for future runs.

Cross-platform: Linux/macOS/WSL full; Windows native uses `--no-tmux`.

Spec: `docs/superpowers/specs/2026-04-30-orca-worktree-manager-design.md`.
```

- [ ] **Step 5: Commit**

```bash
git add scripts/bash/orca-doctor.sh plugins/codex/AGENTS.md README.md
git commit -m "docs: worktree manager — doctor warning + AGENTS row + README"
```

---

## Task 33: Concurrent-write integration test

**Files:**
- Create: `tests/integration/test_wt_concurrent_writes.py`

- [ ] **Step 1: Write integration test**

```python
# tests/integration/test_wt_concurrent_writes.py
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


def _init_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           **os.environ}
    subprocess.run(["git", "-C", str(tmp_path), "commit", "--allow-empty",
                    "-m", "init"], check=True, env=env)
    return tmp_path


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX fcntl")
def test_two_writers_both_lanes_land(tmp_path):
    """Two concurrent wt new processes both get their lanes registered."""
    repo = _init_repo(tmp_path)
    errors: list[str] = []

    def run_one(branch: str) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "orca.python_cli", "wt", "new",
             branch, "--no-tmux", "--no-setup"],
            cwd=str(repo), capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            errors.append(f"{branch}: {result.stderr}")

    t1 = threading.Thread(target=run_one, args=("feat-a",))
    t2 = threading.Thread(target=run_one, args=("feat-b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert errors == []
    reg = json.loads((repo / ".orca" / "worktrees" / "registry.json").read_text())
    lane_ids = sorted(l["lane_id"] for l in reg["lanes"])
    assert lane_ids == ["feat-a", "feat-b"]
```

- [ ] **Step 2: Run**

Run: `uv run python -m pytest tests/integration/test_wt_concurrent_writes.py -v -m integration`
Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_wt_concurrent_writes.py
git commit -m "test(worktrees): concurrent wt new integration test"
```

---

## Task 34: Dogfood test — orca repo creates a real lane via wt new

**Files:**
- Create: `tests/integration/test_wt_dogfood.py`

- [ ] **Step 1: Write dogfood test**

```python
# tests/integration/test_wt_dogfood.py
"""Dogfood: orca uses its own wt manager against a temp clone of itself."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _make_repo_with_history(tmp_path: Path) -> Path:
    """Set up a repo with a couple of commits to exercise wt new + wt rm."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           **os.environ}
    (tmp_path / "README.md").write_text("# Test")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, env=env)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"],
                   check=True, env=env)
    return tmp_path


def _run_wt(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "wt", *args,
         "--no-tmux", "--no-setup"],
        cwd=str(repo), capture_output=True, text=True, check=False,
    )


def test_full_lifecycle(tmp_path):
    repo = _make_repo_with_history(tmp_path)

    # 1. wt new
    r = _run_wt(repo, "new", "demo")
    assert r.returncode == 0, r.stderr
    wt = Path(r.stdout.strip())
    assert wt.is_dir()

    # 2. wt ls includes the lane
    r = _run_wt(repo, "ls", "--json")
    assert r.returncode == 0
    rows = json.loads(r.stdout)["lanes"]
    assert any(l["lane_id"] == "demo" for l in rows)

    # 3. wt cd resolves to the worktree
    r = _run_wt(repo, "cd", "demo")
    assert r.returncode == 0
    assert Path(r.stdout.strip()) == wt

    # 4. wt doctor reports clean
    r = _run_wt(repo, "doctor")
    assert r.returncode == 0

    # 5. wt rm cleans up
    r = _run_wt(repo, "rm", "demo")
    assert r.returncode == 0
    assert not wt.exists()
```

- [ ] **Step 2: Run**

Run: `uv run python -m pytest tests/integration/test_wt_dogfood.py -v -m integration`
Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_wt_dogfood.py
git commit -m "test(worktrees): full-lifecycle dogfood integration test"
```

---

## Task 35: Final test sweep + plan verification

**Files:** none (verification only)

- [ ] **Step 1: Run full unit test suite**

Run: `uv run python -m pytest tests/core/worktrees/ tests/cli/test_wt_cli.py tests/test_sdd_adapter_worktree_lanes.py -v`
Expected: all unit tests pass.

- [ ] **Step 2: Run full integration suite (gated)**

Run: `uv run python -m pytest tests/integration/test_wt_dogfood.py tests/integration/test_wt_concurrent_writes.py -v -m integration`
Expected: pass.

- [ ] **Step 3: Run the full test suite to verify no regressions elsewhere**

Run: `uv run python -m pytest`
Expected: all existing tests still pass; new tests join the green count.

- [ ] **Step 4: Self-review checklist (manual)**

Verify against the spec:
- [ ] All 10 verbs implemented (new/start/cd/ls/merge/rm/init/config/version/doctor)
- [ ] Schema v2 sidecar dual-emits legacy fields
- [ ] sdd_adapter._load_worktree_lanes handles v1+v2 + mixed gracefully
- [ ] Idempotency state cube covers all 8 rows (manager tests)
- [ ] TOFU ledger exists at ledger_path() with --trust-hooks/--record
- [ ] Concurrent-write locking via fcntl (POSIX) + msvcrt (Windows path)
- [ ] Atomic-rename symlink layer prevents TOCTOU
- [ ] Agent-launch uses prompt-file pattern, no tmux set-environment
- [ ] tmux {repo} sanitization
- [ ] Lifecycle events.jsonl emitted from manager
- [ ] wt init detects top-level ecosystems + monorepo warning
- [ ] Adoption flow seeds .orca/worktrees.toml
- [ ] Doctor warns on missing config

- [ ] **Step 5: Commit verification doc (optional worklog)**

```bash
git status  # should be clean
```

---

## Self-review notes (writing-plans skill)

**Spec coverage:** Each spec section maps to a task:
- §Architecture → Task 0 (scaffold) + Tasks 1-24 (modules)
- §CLI verb surface → Tasks 25-30
- §Configuration schema → Task 2
- §Idempotency state machine → Task 19
- §Hook lifecycle (4 stages) → Tasks 11, 12, 15, 23, 24
- §Hook trust model → Tasks 13, 14
- §Lane-id and sidecar → Tasks 1, 4
- §Concurrent-write semantics → Tasks 6, 7
- §Schema v1→v2 migrator → Task 8
- §sdd_adapter reader update → Task 9
- §JSON output shapes → Tasks 27, 28
- §tmux integration → Tasks 16, 17, 21
- §Lifecycle events → Task 10
- §Doctor + reap → Task 30
- §wt init ecosystem detection → Task 22
- §Adoption-flow integration → Task 31
- §Doctor warning for missing worktrees.toml → Task 32
- §Cross-platform → Task 7 (Windows lock), Task 11 (Windows symlink fallback)
- §Testing strategy → Tasks 33, 34, 35

**Type consistency:** `Sidecar`, `LaneRow`, `WorktreesConfig`, `CreateRequest`, `RemoveRequest`, `HookEnv`, `HookOutcome`, `TrustOutcome`, `TrustDecision`, `IdempotencyError` — all defined in their introducing tasks and used consistently downstream.

**Placeholder scan:** No "TBD" / "implement later" anywhere. Every code step contains the actual code.
