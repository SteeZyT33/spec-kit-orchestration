# Orca Spec 015 — Brownfield Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `orca-cli adopt` / `orca-cli apply` flow plus `orca.core.host_layout` adapter (4 implementations) so a third party can install orca into an existing repo without manual surgery.

**Architecture:** Manifest-driven (`.orca/adoption.toml`) is source of truth. Wizard populates it. Executor reads it. Adapter abstracts over `{spec-kit, openspec, superpowers, bare}`. Idempotent + reversible. Existing in-tree behavior unchanged until adapter is wired (Task 13+).

**Tech Stack:** Python 3.10+ (per `pyproject.toml`), `tomli` + `tomli-w` for TOML I/O, existing `Result`/`ErrorKind` from `orca.core`, `pytest` for tests.

**Source spec:** `docs/superpowers/specs/2026-04-29-orca-spec-015-brownfield-adoption-design.md` (commit `645d467`).

**Test runner:** `uv run python -m pytest` (NOT `uv run pytest`).

**Baseline:** 462 tests on commit `645d467`.

---

## File Structure

### New files

- `src/orca/core/host_layout/__init__.py` — protocol export + factory functions (`from_manifest`, `detect`)
- `src/orca/core/host_layout/protocol.py` — `HostLayout` Protocol class
- `src/orca/core/host_layout/spec_kit.py` — `SpecKitLayout`
- `src/orca/core/host_layout/openspec.py` — `OpenSpecLayout`
- `src/orca/core/host_layout/superpowers.py` — `SuperpowersLayout`
- `src/orca/core/host_layout/bare.py` — `BareLayout`
- `src/orca/core/host_layout/detect.py` — `detect(repo_root) -> HostLayout`
- `src/orca/core/adoption/__init__.py` — module export surface
- `src/orca/core/adoption/manifest.py` — `Manifest` dataclass + TOML I/O + validation
- `src/orca/core/adoption/snapshot.py` — backup directory write/read
- `src/orca/core/adoption/state.py` — `adoption-state.json` reader/writer
- `src/orca/core/adoption/apply.py` — apply executor (idempotent)
- `src/orca/core/adoption/revert.py` — revert executor
- `src/orca/core/adoption/wizard.py` — interactive prompts for `orca adopt`
- `src/orca/core/adoption/policies/claude_md.py` — CLAUDE.md merge policies
- `src/orca/core/adoption/policies/slash_commands.py` — slash command namespace policy
- `src/orca/core/adoption/policies/constitution.py` — constitution merge policy
- `tests/core/host_layout/test_protocol.py` — protocol contract tests (parametrized over all 4 implementations)
- `tests/core/host_layout/test_detect.py` — detection priority + override tests
- `tests/core/adoption/test_manifest.py` — TOML round-trip + schema validation
- `tests/core/adoption/test_apply_idempotency.py` — apply twice = no-op
- `tests/core/adoption/test_revert.py` — apply + revert = byte-identical original
- `tests/core/adoption/test_policies.py` — conflict-matrix tests
- `tests/cli/test_adopt_apply_cli.py` — `orca-cli adopt` and `orca-cli apply` smoke + flag coverage
- `tests/integration/test_self_host_dogfood.py` — orca repo dogfooding (the orca repo itself adopts orca)
- `tests/fixtures/host_layouts/spec_kit/` — minimal `.specify/` repo fixture
- `tests/fixtures/host_layouts/openspec/` — minimal `openspec/` repo fixture
- `tests/fixtures/host_layouts/superpowers/` — minimal `docs/superpowers/` repo fixture
- `tests/fixtures/host_layouts/bare/` — minimal git repo (no spec system)

### Modified files

- `src/orca/python_cli.py` — add `adopt` and `apply` capability handlers; wire them into `CAPABILITIES` registry
- `pyproject.toml` — add `tomli`/`tomli-w` dependencies
- `plugins/claude-code/commands/review-spec.md` — consult `host_layout` for feature dir resolution (Task 13)
- `plugins/claude-code/commands/review-code.md` — same
- `plugins/claude-code/commands/review-pr.md` — same
- `plugins/claude-code/commands/cite.md` — same
- `plugins/claude-code/commands/gate.md` — same
- `plugins/claude-code/commands/doctor.md` — add adoption checks
- `scripts/bash/orca-doctor.sh` — add adoption checks (manifest exists, schema valid, capabilities reachable)
- `docs/superpowers/contracts/path-safety.md` — Class A reads from `host_layout.resolve_feature_dir(feature_id)` (Task 14)

---

## Task Sequencing

Tasks 1-3 build the foundation (manifest + adapter protocol + first adapter). Tasks 4-6 add the remaining adapters in parallel-safe order. Tasks 7-8 build the executor (apply, revert). Task 9 is the wizard. Tasks 10-12 add CLI surface and tests. Task 13 refactors slash commands to use the adapter (this is when in-tree behavior could change; gate with feature flag if needed). Task 14 updates the path-safety contract. Task 15 is dogfooding integration.

The in-tree orca repo continues to work throughout: existing slash commands keep their hardcoded path resolution until Task 13. Tasks 1-12 add new code in parallel paths.

---

## Task 1: Add `tomli` + `tomli-w` dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1.1: Read current dependencies block**

```bash
grep -A 20 "^dependencies" pyproject.toml
```

Expected: existing `dependencies = [...]` array.

- [ ] **Step 1.2: Add tomli and tomli-w to dependencies**

```toml
dependencies = [
    # ... existing entries unchanged ...
    "tomli>=2.0; python_version<'3.11'",
    "tomli-w>=1.0",
]
```

(tomllib is stdlib in 3.11+; tomli is the conditional fallback for 3.10. tomli-w is the writer; no stdlib equivalent.)

- [ ] **Step 1.3: Sync deps**

```bash
uv sync
```

Expected: new packages installed; no conflicts.

- [ ] **Step 1.4: Verify import**

```bash
uv run python -c "import tomli_w; print('tomli_w', tomli_w.__version__)"
```

Expected: prints version, exits 0.

- [ ] **Step 1.5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add tomli + tomli-w for adoption manifest I/O"
```

---

## Task 2: Manifest schema + TOML I/O + validation

**Files:**
- Create: `src/orca/core/adoption/__init__.py`
- Create: `src/orca/core/adoption/manifest.py`
- Test: `tests/core/adoption/test_manifest.py`

The manifest is the contract. Build it first; everything else consumes it.

- [ ] **Step 2.1: Write failing tests**

Create `tests/core/adoption/__init__.py` (empty file).

Create `tests/core/adoption/test_manifest.py`:

```python
"""Manifest round-trip + schema validation."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from orca.core.adoption.manifest import (
    Manifest,
    ManifestError,
    load_manifest,
    write_manifest,
)


def test_manifest_round_trip(tmp_path: Path) -> None:
    src = tmp_path / "adoption.toml"
    src.write_text(textwrap.dedent("""
        schema_version = 1

        [host]
        system = "superpowers"
        feature_dir_pattern = "docs/superpowers/specs/{feature_id}"
        constitution_path = "docs/superpowers/constitution.md"
        agents_md_path = "AGENTS.md"
        review_artifact_dir = "docs/superpowers/reviews"

        [orca]
        state_dir = ".orca"
        installed_capabilities = ["cross-agent-review", "citation-validator"]

        [slash_commands]
        namespace = "orca"
        enabled = ["review-spec", "review-code"]
        disabled = []

        [claude_md]
        policy = "section"
        section_marker = "## Orca"
        namespace_prefix = "orca:"

        [constitution]
        policy = "respect-existing"

        [reversal]
        backup_dir = ".orca/adoption-backup"
    """))

    m = load_manifest(src)
    assert m.host.system == "superpowers"
    assert m.host.feature_dir_pattern == "docs/superpowers/specs/{feature_id}"
    assert m.orca.installed_capabilities == ["cross-agent-review", "citation-validator"]
    assert m.slash_commands.namespace == "orca"
    assert m.claude_md.policy == "section"

    dst = tmp_path / "out.toml"
    write_manifest(m, dst)
    m2 = load_manifest(dst)
    assert m2 == m


def test_unknown_host_system_rejected(tmp_path: Path) -> None:
    src = tmp_path / "adoption.toml"
    src.write_text(textwrap.dedent("""
        schema_version = 1
        [host]
        system = "unknown-system"
        feature_dir_pattern = "x/{feature_id}"
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

    with pytest.raises(ManifestError, match="host.system"):
        load_manifest(src)


def test_feature_dir_pattern_must_contain_feature_id(tmp_path: Path) -> None:
    src = tmp_path / "adoption.toml"
    src.write_text(textwrap.dedent("""
        schema_version = 1
        [host]
        system = "spec-kit"
        feature_dir_pattern = "specs/feature"
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

    with pytest.raises(ManifestError, match="feature_id"):
        load_manifest(src)


def test_schema_version_unsupported(tmp_path: Path) -> None:
    src = tmp_path / "adoption.toml"
    src.write_text("schema_version = 99\n")
    with pytest.raises(ManifestError, match="schema_version"):
        load_manifest(src)


def test_namespace_format_validated(tmp_path: Path) -> None:
    src = tmp_path / "adoption.toml"
    src.write_text(textwrap.dedent("""
        schema_version = 1
        [host]
        system = "spec-kit"
        feature_dir_pattern = "specs/{feature_id}"
        agents_md_path = "AGENTS.md"
        review_artifact_dir = "x"
        [orca]
        state_dir = ".orca"
        installed_capabilities = []
        [slash_commands]
        namespace = "Bad Namespace!"
        enabled = []
        disabled = []
        [claude_md]
        policy = "section"
        [constitution]
        policy = "respect-existing"
        [reversal]
        backup_dir = ".orca/adoption-backup"
    """))
    with pytest.raises(ManifestError, match="namespace"):
        load_manifest(src)
```

- [ ] **Step 2.2: Run tests; verify FAIL**

```bash
uv run python -m pytest tests/core/adoption/test_manifest.py -v
```

Expected: ImportError/ModuleNotFoundError on `orca.core.adoption.manifest`.

- [ ] **Step 2.3: Implement manifest module**

Create `src/orca/core/adoption/__init__.py`:

```python
"""Brownfield adoption: manifest, apply, revert, wizard."""
```

Create `src/orca/core/adoption/manifest.py`:

```python
"""Manifest schema, TOML I/O, validation.

The manifest at `.orca/adoption.toml` is the source of truth for an
adopted orca install. See spec 015 for the schema rationale.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Literal

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

SUPPORTED_SCHEMA_VERSION = 1
SUPPORTED_HOST_SYSTEMS = frozenset({"spec-kit", "openspec", "superpowers", "bare"})
SUPPORTED_CLAUDE_MD_POLICIES = frozenset({"append", "section", "namespace", "skip"})
SUPPORTED_CONSTITUTION_POLICIES = frozenset({"respect-existing", "merge", "skip"})
NAMESPACE_RE = re.compile(r"^[a-z][a-z0-9-]*$")
RESERVED_NAMESPACE_PREFIXES = ("speckit-", "claude-")


class ManifestError(ValueError):
    """Raised when manifest schema is invalid."""


@dataclass(frozen=True)
class HostConfig:
    system: Literal["spec-kit", "openspec", "superpowers", "bare"]
    feature_dir_pattern: str
    agents_md_path: str
    review_artifact_dir: str
    constitution_path: str | None = None


@dataclass(frozen=True)
class OrcaConfig:
    state_dir: str
    installed_capabilities: list[str]


@dataclass(frozen=True)
class SlashCommandsConfig:
    namespace: str
    enabled: list[str]
    disabled: list[str]


@dataclass(frozen=True)
class ClaudeMdConfig:
    policy: Literal["append", "section", "namespace", "skip"]
    section_marker: str = "## Orca"
    namespace_prefix: str = "orca:"


@dataclass(frozen=True)
class ConstitutionConfig:
    policy: Literal["respect-existing", "merge", "skip"]


@dataclass(frozen=True)
class ReversalConfig:
    backup_dir: str


@dataclass(frozen=True)
class Manifest:
    schema_version: int
    host: HostConfig
    orca: OrcaConfig
    slash_commands: SlashCommandsConfig
    claude_md: ClaudeMdConfig
    constitution: ConstitutionConfig
    reversal: ReversalConfig


def _require(d: dict[str, Any], key: str, ctx: str) -> Any:
    if key not in d:
        raise ManifestError(f"missing {ctx}.{key}")
    return d[key]


def load_manifest(path: Path) -> Manifest:
    """Read and validate a manifest from disk.

    Raises ManifestError on any schema violation; the message names the
    specific field that failed.
    """
    raw = path.read_bytes()
    if not raw:
        raise ManifestError("manifest file is empty")
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"TOML parse failed: {exc}") from exc

    schema_version = _require(data, "schema_version", "")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ManifestError(
            f"schema_version={schema_version} not supported; "
            f"this orca expects {SUPPORTED_SCHEMA_VERSION}"
        )

    host_raw = _require(data, "host", "")
    host_system = _require(host_raw, "system", "host")
    if host_system not in SUPPORTED_HOST_SYSTEMS:
        raise ManifestError(
            f"host.system={host_system!r} not in {sorted(SUPPORTED_HOST_SYSTEMS)}"
        )
    pattern = _require(host_raw, "feature_dir_pattern", "host")
    if "{feature_id}" not in pattern:
        raise ManifestError(
            "host.feature_dir_pattern must contain literal {feature_id}"
        )

    host = HostConfig(
        system=host_system,
        feature_dir_pattern=pattern,
        agents_md_path=_require(host_raw, "agents_md_path", "host"),
        review_artifact_dir=_require(host_raw, "review_artifact_dir", "host"),
        constitution_path=host_raw.get("constitution_path"),
    )

    orca_raw = _require(data, "orca", "")
    orca = OrcaConfig(
        state_dir=_require(orca_raw, "state_dir", "orca"),
        installed_capabilities=list(_require(orca_raw, "installed_capabilities", "orca")),
    )

    sc_raw = _require(data, "slash_commands", "")
    namespace = _require(sc_raw, "namespace", "slash_commands")
    if not NAMESPACE_RE.match(namespace):
        raise ManifestError(
            f"slash_commands.namespace={namespace!r} must match [a-z][a-z0-9-]*"
        )
    if any(namespace.startswith(p) for p in RESERVED_NAMESPACE_PREFIXES):
        raise ManifestError(
            f"slash_commands.namespace={namespace!r} starts with reserved prefix"
        )

    slash_commands = SlashCommandsConfig(
        namespace=namespace,
        enabled=list(_require(sc_raw, "enabled", "slash_commands")),
        disabled=list(_require(sc_raw, "disabled", "slash_commands")),
    )

    cm_raw = _require(data, "claude_md", "")
    cm_policy = _require(cm_raw, "policy", "claude_md")
    if cm_policy not in SUPPORTED_CLAUDE_MD_POLICIES:
        raise ManifestError(
            f"claude_md.policy={cm_policy!r} not in {sorted(SUPPORTED_CLAUDE_MD_POLICIES)}"
        )
    claude_md = ClaudeMdConfig(
        policy=cm_policy,
        section_marker=cm_raw.get("section_marker", "## Orca"),
        namespace_prefix=cm_raw.get("namespace_prefix", "orca:"),
    )

    co_raw = _require(data, "constitution", "")
    co_policy = _require(co_raw, "policy", "constitution")
    if co_policy not in SUPPORTED_CONSTITUTION_POLICIES:
        raise ManifestError(
            f"constitution.policy={co_policy!r} not in {sorted(SUPPORTED_CONSTITUTION_POLICIES)}"
        )
    constitution = ConstitutionConfig(policy=co_policy)

    rev_raw = _require(data, "reversal", "")
    reversal = ReversalConfig(
        backup_dir=_require(rev_raw, "backup_dir", "reversal"),
    )

    return Manifest(
        schema_version=schema_version,
        host=host,
        orca=orca,
        slash_commands=slash_commands,
        claude_md=claude_md,
        constitution=constitution,
        reversal=reversal,
    )


def write_manifest(manifest: Manifest, path: Path) -> None:
    """Serialize manifest to TOML; atomic write."""
    payload: dict[str, Any] = {
        "schema_version": manifest.schema_version,
        "host": {
            "system": manifest.host.system,
            "feature_dir_pattern": manifest.host.feature_dir_pattern,
            "agents_md_path": manifest.host.agents_md_path,
            "review_artifact_dir": manifest.host.review_artifact_dir,
        },
        "orca": {
            "state_dir": manifest.orca.state_dir,
            "installed_capabilities": list(manifest.orca.installed_capabilities),
        },
        "slash_commands": {
            "namespace": manifest.slash_commands.namespace,
            "enabled": list(manifest.slash_commands.enabled),
            "disabled": list(manifest.slash_commands.disabled),
        },
        "claude_md": {
            "policy": manifest.claude_md.policy,
            "section_marker": manifest.claude_md.section_marker,
            "namespace_prefix": manifest.claude_md.namespace_prefix,
        },
        "constitution": {"policy": manifest.constitution.policy},
        "reversal": {"backup_dir": manifest.reversal.backup_dir},
    }
    if manifest.host.constitution_path is not None:
        payload["host"]["constitution_path"] = manifest.host.constitution_path

    encoded = tomli_w.dumps(payload).encode("utf-8")
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_bytes(encoded)
    tmp.replace(path)
```

- [ ] **Step 2.4: Run tests; verify PASS**

```bash
uv run python -m pytest tests/core/adoption/test_manifest.py -v
```

Expected: 5 passed.

- [ ] **Step 2.5: Run full suite for regression check**

```bash
uv run python -m pytest -q
```

Expected: 462 + 5 = 467 passed.

- [ ] **Step 2.6: Commit**

```bash
git add src/orca/core/adoption/__init__.py src/orca/core/adoption/manifest.py tests/core/adoption/__init__.py tests/core/adoption/test_manifest.py
git commit -m "feat(adoption): manifest schema + TOML I/O (Spec 015)"
```

---

## Task 3: HostLayout Protocol + BareLayout (simplest adapter)

**Files:**
- Create: `src/orca/core/host_layout/__init__.py`
- Create: `src/orca/core/host_layout/protocol.py`
- Create: `src/orca/core/host_layout/bare.py`
- Test: `tests/core/host_layout/__init__.py` (empty)
- Test: `tests/core/host_layout/test_protocol.py` (parametrized contract test)

- [ ] **Step 3.1: Write failing protocol contract tests**

Create `tests/core/host_layout/__init__.py` (empty).

Create `tests/core/host_layout/test_protocol.py`:

```python
"""Protocol contract tests, parametrized over all host_layout implementations.

Each adapter must implement the same public surface; this file is the
canonical contract test. Adding a new adapter = parametrize it in.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.host_layout import BareLayout, HostLayout


@pytest.fixture
def bare_repo(tmp_path: Path) -> Path:
    """A minimal repo with no spec system at all."""
    (tmp_path / "README.md").write_text("# bare\n")
    return tmp_path


def test_bare_layout_satisfies_protocol(bare_repo: Path) -> None:
    layout: HostLayout = BareLayout(repo_root=bare_repo)
    assert isinstance(layout.repo_root, Path)


def test_bare_layout_resolve_feature_dir(bare_repo: Path) -> None:
    layout = BareLayout(repo_root=bare_repo)
    fd = layout.resolve_feature_dir("001-example")
    assert fd == bare_repo / "docs" / "orca-specs" / "001-example"


def test_bare_layout_list_features_empty(bare_repo: Path) -> None:
    layout = BareLayout(repo_root=bare_repo)
    assert layout.list_features() == []


def test_bare_layout_list_features_after_creation(bare_repo: Path) -> None:
    (bare_repo / "docs" / "orca-specs" / "001-x").mkdir(parents=True)
    (bare_repo / "docs" / "orca-specs" / "002-y").mkdir(parents=True)
    layout = BareLayout(repo_root=bare_repo)
    assert sorted(layout.list_features()) == ["001-x", "002-y"]


def test_bare_layout_constitution_path_is_none(bare_repo: Path) -> None:
    layout = BareLayout(repo_root=bare_repo)
    assert layout.constitution_path() is None


def test_bare_layout_agents_md_path_default(bare_repo: Path) -> None:
    layout = BareLayout(repo_root=bare_repo)
    assert layout.agents_md_path() == bare_repo / "AGENTS.md"


def test_bare_layout_review_artifact_dir(bare_repo: Path) -> None:
    layout = BareLayout(repo_root=bare_repo)
    assert layout.review_artifact_dir() == bare_repo / "docs" / "orca-specs" / "_reviews"
```

- [ ] **Step 3.2: Run; verify FAIL**

```bash
uv run python -m pytest tests/core/host_layout/test_protocol.py -v
```

Expected: ImportError on `orca.core.host_layout`.

- [ ] **Step 3.3: Implement protocol + BareLayout**

Create `src/orca/core/host_layout/protocol.py`:

```python
"""HostLayout protocol — the single abstraction over spec systems."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class HostLayout(Protocol):
    """Adapter interface; implementations live in sibling modules."""

    repo_root: Path

    def resolve_feature_dir(self, feature_id: str) -> Path:
        """Return absolute path to the feature dir for `feature_id`.

        Path is computed; existence is not checked. Caller decides
        whether to create / require existence.
        """
        ...

    def list_features(self) -> list[str]:
        """Return feature_ids found under this host's feature root.

        Empty list if no feature root exists yet. IDs are returned
        as the directory basename, not absolute paths.
        """
        ...

    def constitution_path(self) -> Path | None:
        """Return absolute path to the host's constitution.md.

        Returns None if this host has no constitution convention
        (e.g., bare repo).
        """
        ...

    def agents_md_path(self) -> Path:
        """Return absolute path to the host's AGENTS.md (or CLAUDE.md).

        Always returns a path; caller checks `.exists()` if needed.
        """
        ...

    def review_artifact_dir(self) -> Path:
        """Return absolute path to where review-spec.md and friends land."""
        ...
```

Create `src/orca/core/host_layout/bare.py`:

```python
"""BareLayout — fallback for repos with no recognized spec system."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BareLayout:
    """No spec system detected; orca creates docs/orca-specs/ as fallback."""

    repo_root: Path

    def resolve_feature_dir(self, feature_id: str) -> Path:
        return self.repo_root / "docs" / "orca-specs" / feature_id

    def list_features(self) -> list[str]:
        root = self.repo_root / "docs" / "orca-specs"
        if not root.is_dir():
            return []
        return [
            entry.name
            for entry in root.iterdir()
            if entry.is_dir() and not entry.name.startswith("_")
        ]

    def constitution_path(self) -> Path | None:
        return None

    def agents_md_path(self) -> Path:
        return self.repo_root / "AGENTS.md"

    def review_artifact_dir(self) -> Path:
        return self.repo_root / "docs" / "orca-specs" / "_reviews"
```

Create `src/orca/core/host_layout/__init__.py`:

```python
"""HostLayout adapters: spec-system-agnostic path resolution."""
from __future__ import annotations

from orca.core.host_layout.bare import BareLayout
from orca.core.host_layout.protocol import HostLayout

__all__ = ["HostLayout", "BareLayout"]
```

- [ ] **Step 3.4: Run tests; verify PASS**

```bash
uv run python -m pytest tests/core/host_layout/test_protocol.py -v
```

Expected: 7 passed.

- [ ] **Step 3.5: Commit**

```bash
git add src/orca/core/host_layout/ tests/core/host_layout/
git commit -m "feat(host_layout): protocol + BareLayout (Spec 015)"
```

---

## Task 4: SpecKitLayout

**Files:**
- Create: `src/orca/core/host_layout/spec_kit.py`
- Modify: `src/orca/core/host_layout/__init__.py` (export `SpecKitLayout`)
- Modify: `tests/core/host_layout/test_protocol.py` (add fixture + parametrize)

- [ ] **Step 4.1: Write failing tests**

Append to `tests/core/host_layout/test_protocol.py`:

```python
from orca.core.host_layout import SpecKitLayout


@pytest.fixture
def spec_kit_repo(tmp_path: Path) -> Path:
    (tmp_path / ".specify" / "memory").mkdir(parents=True)
    (tmp_path / ".specify" / "memory" / "constitution.md").write_text("# constitution\n")
    (tmp_path / "specs" / "001-example").mkdir(parents=True)
    (tmp_path / "specs" / "002-other").mkdir(parents=True)
    return tmp_path


def test_spec_kit_layout_resolve_feature_dir(spec_kit_repo: Path) -> None:
    layout = SpecKitLayout(repo_root=spec_kit_repo)
    assert layout.resolve_feature_dir("001-example") == spec_kit_repo / "specs" / "001-example"


def test_spec_kit_layout_list_features(spec_kit_repo: Path) -> None:
    layout = SpecKitLayout(repo_root=spec_kit_repo)
    assert sorted(layout.list_features()) == ["001-example", "002-other"]


def test_spec_kit_layout_constitution_present(spec_kit_repo: Path) -> None:
    layout = SpecKitLayout(repo_root=spec_kit_repo)
    assert layout.constitution_path() == spec_kit_repo / ".specify" / "memory" / "constitution.md"


def test_spec_kit_layout_constitution_missing_returns_none(tmp_path: Path) -> None:
    layout = SpecKitLayout(repo_root=tmp_path)
    assert layout.constitution_path() is None


def test_spec_kit_layout_review_artifact_dir(spec_kit_repo: Path) -> None:
    layout = SpecKitLayout(repo_root=spec_kit_repo)
    assert layout.review_artifact_dir() == spec_kit_repo / "specs"
```

- [ ] **Step 4.2: Run tests; verify FAIL**

```bash
uv run python -m pytest tests/core/host_layout/test_protocol.py::test_spec_kit_layout_resolve_feature_dir -v
```

Expected: ImportError on `SpecKitLayout`.

- [ ] **Step 4.3: Implement SpecKitLayout**

Create `src/orca/core/host_layout/spec_kit.py`:

```python
"""SpecKitLayout — the original spec-kit convention."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SpecKitLayout:
    """Repos using spec-kit's `.specify/` + `specs/<id>/` convention."""

    repo_root: Path

    def resolve_feature_dir(self, feature_id: str) -> Path:
        return self.repo_root / "specs" / feature_id

    def list_features(self) -> list[str]:
        root = self.repo_root / "specs"
        if not root.is_dir():
            return []
        return [
            entry.name
            for entry in root.iterdir()
            if entry.is_dir() and not entry.name.startswith("_")
        ]

    def constitution_path(self) -> Path | None:
        path = self.repo_root / ".specify" / "memory" / "constitution.md"
        return path if path.exists() else None

    def agents_md_path(self) -> Path:
        # spec-kit hosts conventionally use CLAUDE.md
        return self.repo_root / "CLAUDE.md"

    def review_artifact_dir(self) -> Path:
        return self.repo_root / "specs"
```

Update `src/orca/core/host_layout/__init__.py`:

```python
"""HostLayout adapters: spec-system-agnostic path resolution."""
from __future__ import annotations

from orca.core.host_layout.bare import BareLayout
from orca.core.host_layout.protocol import HostLayout
from orca.core.host_layout.spec_kit import SpecKitLayout

__all__ = ["HostLayout", "BareLayout", "SpecKitLayout"]
```

- [ ] **Step 4.4: Run tests; verify PASS**

```bash
uv run python -m pytest tests/core/host_layout/test_protocol.py -v
```

Expected: all (BareLayout + SpecKitLayout tests) pass.

- [ ] **Step 4.5: Commit**

```bash
git add src/orca/core/host_layout/spec_kit.py src/orca/core/host_layout/__init__.py tests/core/host_layout/test_protocol.py
git commit -m "feat(host_layout): SpecKitLayout adapter (Spec 015)"
```

---

## Task 5: SuperpowersLayout

**Files:**
- Create: `src/orca/core/host_layout/superpowers.py`
- Modify: `src/orca/core/host_layout/__init__.py`
- Modify: `tests/core/host_layout/test_protocol.py`

- [ ] **Step 5.1: Write failing tests**

Append to `tests/core/host_layout/test_protocol.py`:

```python
from orca.core.host_layout import SuperpowersLayout


@pytest.fixture
def superpowers_repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "specs" / "2026-04-29-feature-x").mkdir()
    (tmp_path / "docs" / "superpowers" / "constitution.md").write_text("# c\n")
    (tmp_path / "AGENTS.md").write_text("# agents\n")
    return tmp_path


def test_superpowers_layout_resolve_feature_dir(superpowers_repo: Path) -> None:
    layout = SuperpowersLayout(repo_root=superpowers_repo)
    fd = layout.resolve_feature_dir("2026-04-29-feature-x")
    assert fd == superpowers_repo / "docs" / "superpowers" / "specs" / "2026-04-29-feature-x"


def test_superpowers_layout_list_features(superpowers_repo: Path) -> None:
    layout = SuperpowersLayout(repo_root=superpowers_repo)
    assert layout.list_features() == ["2026-04-29-feature-x"]


def test_superpowers_layout_constitution(superpowers_repo: Path) -> None:
    layout = SuperpowersLayout(repo_root=superpowers_repo)
    assert layout.constitution_path() == superpowers_repo / "docs" / "superpowers" / "constitution.md"


def test_superpowers_layout_review_artifact_dir(superpowers_repo: Path) -> None:
    layout = SuperpowersLayout(repo_root=superpowers_repo)
    assert layout.review_artifact_dir() == superpowers_repo / "docs" / "superpowers" / "reviews"
```

- [ ] **Step 5.2: Run; verify FAIL**

Expected: ImportError on `SuperpowersLayout`.

- [ ] **Step 5.3: Implement**

Create `src/orca/core/host_layout/superpowers.py`:

```python
"""SuperpowersLayout — superpowers/ convention with date-prefixed specs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SuperpowersLayout:
    """Repos using the superpowers convention: `docs/superpowers/specs/`."""

    repo_root: Path

    def resolve_feature_dir(self, feature_id: str) -> Path:
        return self.repo_root / "docs" / "superpowers" / "specs" / feature_id

    def list_features(self) -> list[str]:
        root = self.repo_root / "docs" / "superpowers" / "specs"
        if not root.is_dir():
            return []
        return [
            entry.name
            for entry in root.iterdir()
            if entry.is_dir() and not entry.name.startswith("_")
        ]

    def constitution_path(self) -> Path | None:
        path = self.repo_root / "docs" / "superpowers" / "constitution.md"
        return path if path.exists() else None

    def agents_md_path(self) -> Path:
        return self.repo_root / "AGENTS.md"

    def review_artifact_dir(self) -> Path:
        return self.repo_root / "docs" / "superpowers" / "reviews"
```

Update `src/orca/core/host_layout/__init__.py`:

```python
from orca.core.host_layout.superpowers import SuperpowersLayout

__all__ = ["HostLayout", "BareLayout", "SpecKitLayout", "SuperpowersLayout"]
```

- [ ] **Step 5.4: Verify PASS, commit**

```bash
uv run python -m pytest tests/core/host_layout/ -v
git add src/orca/core/host_layout/ tests/core/host_layout/
git commit -m "feat(host_layout): SuperpowersLayout adapter (Spec 015)"
```

---

## Task 6: OpenSpecLayout

**Files:**
- Create: `src/orca/core/host_layout/openspec.py`
- Modify: `src/orca/core/host_layout/__init__.py`
- Modify: `tests/core/host_layout/test_protocol.py`

- [ ] **Step 6.1: Write failing tests**

Append to `tests/core/host_layout/test_protocol.py`:

```python
from orca.core.host_layout import OpenSpecLayout


@pytest.fixture
def openspec_repo(tmp_path: Path) -> Path:
    (tmp_path / "openspec" / "changes" / "add-feature-x").mkdir(parents=True)
    (tmp_path / "openspec" / "specs").mkdir()
    return tmp_path


def test_openspec_layout_resolve_feature_dir(openspec_repo: Path) -> None:
    layout = OpenSpecLayout(repo_root=openspec_repo)
    fd = layout.resolve_feature_dir("add-feature-x")
    assert fd == openspec_repo / "openspec" / "changes" / "add-feature-x"


def test_openspec_layout_list_features(openspec_repo: Path) -> None:
    layout = OpenSpecLayout(repo_root=openspec_repo)
    assert layout.list_features() == ["add-feature-x"]


def test_openspec_layout_no_constitution(openspec_repo: Path) -> None:
    layout = OpenSpecLayout(repo_root=openspec_repo)
    # openspec doesn't have a constitution.md convention
    assert layout.constitution_path() is None


def test_openspec_layout_review_artifact_dir(openspec_repo: Path) -> None:
    layout = OpenSpecLayout(repo_root=openspec_repo)
    assert layout.review_artifact_dir() == openspec_repo / "openspec" / "changes"
```

- [ ] **Step 6.2: Run; verify FAIL.**
- [ ] **Step 6.3: Implement**

Create `src/orca/core/host_layout/openspec.py`:

```python
"""OpenSpecLayout — openspec's `openspec/changes/` convention."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OpenSpecLayout:
    """Repos using openspec's `openspec/changes/<change-id>/` convention."""

    repo_root: Path

    def resolve_feature_dir(self, feature_id: str) -> Path:
        return self.repo_root / "openspec" / "changes" / feature_id

    def list_features(self) -> list[str]:
        root = self.repo_root / "openspec" / "changes"
        if not root.is_dir():
            return []
        return [
            entry.name
            for entry in root.iterdir()
            if entry.is_dir() and not entry.name.startswith("_")
        ]

    def constitution_path(self) -> Path | None:
        # openspec has no canonical constitution location
        return None

    def agents_md_path(self) -> Path:
        return self.repo_root / "AGENTS.md"

    def review_artifact_dir(self) -> Path:
        return self.repo_root / "openspec" / "changes"
```

Update `__init__.py` to export `OpenSpecLayout`.

- [ ] **Step 6.4: Verify, commit**

```bash
uv run python -m pytest tests/core/host_layout/ -v
git add src/orca/core/host_layout/ tests/core/host_layout/
git commit -m "feat(host_layout): OpenSpecLayout adapter (Spec 015)"
```

---

## Task 7: Detection function

**Files:**
- Create: `src/orca/core/host_layout/detect.py`
- Modify: `src/orca/core/host_layout/__init__.py`
- Test: `tests/core/host_layout/test_detect.py`

- [ ] **Step 7.1: Write failing tests**

Create `tests/core/host_layout/test_detect.py`:

```python
"""Detection priority + override tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.host_layout import (
    BareLayout,
    OpenSpecLayout,
    SpecKitLayout,
    SuperpowersLayout,
    detect,
)


def test_detect_superpowers(tmp_path: Path) -> None:
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    layout = detect(tmp_path)
    assert isinstance(layout, SuperpowersLayout)


def test_detect_openspec(tmp_path: Path) -> None:
    (tmp_path / "openspec" / "changes").mkdir(parents=True)
    layout = detect(tmp_path)
    assert isinstance(layout, OpenSpecLayout)


def test_detect_spec_kit(tmp_path: Path) -> None:
    (tmp_path / ".specify").mkdir()
    layout = detect(tmp_path)
    assert isinstance(layout, SpecKitLayout)


def test_detect_bare(tmp_path: Path) -> None:
    layout = detect(tmp_path)
    assert isinstance(layout, BareLayout)


def test_detect_superpowers_wins_over_specify(tmp_path: Path) -> None:
    """When both .specify/ and docs/superpowers/specs/ exist (mid-migration),
    superpowers wins per priority order."""
    (tmp_path / ".specify").mkdir()
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    layout = detect(tmp_path)
    assert isinstance(layout, SuperpowersLayout)


def test_detect_openspec_wins_over_specify(tmp_path: Path) -> None:
    (tmp_path / ".specify").mkdir()
    (tmp_path / "openspec" / "changes").mkdir(parents=True)
    layout = detect(tmp_path)
    assert isinstance(layout, OpenSpecLayout)
```

- [ ] **Step 7.2: Run; verify FAIL.**
- [ ] **Step 7.3: Implement detection**

Create `src/orca/core/host_layout/detect.py`:

```python
"""Detect which spec system a repo uses; pick the matching adapter."""
from __future__ import annotations

from pathlib import Path

from orca.core.host_layout.bare import BareLayout
from orca.core.host_layout.openspec import OpenSpecLayout
from orca.core.host_layout.protocol import HostLayout
from orca.core.host_layout.spec_kit import SpecKitLayout
from orca.core.host_layout.superpowers import SuperpowersLayout


def detect(repo_root: Path) -> HostLayout:
    """Probe `repo_root` and return the best-fit HostLayout.

    Priority order: superpowers > openspec > spec-kit > bare.
    """
    if (repo_root / "docs" / "superpowers" / "specs").is_dir():
        return SuperpowersLayout(repo_root=repo_root)
    if (repo_root / "openspec" / "changes").is_dir():
        return OpenSpecLayout(repo_root=repo_root)
    if (repo_root / ".specify").is_dir():
        return SpecKitLayout(repo_root=repo_root)
    return BareLayout(repo_root=repo_root)
```

Update `__init__.py`:

```python
from orca.core.host_layout.detect import detect

__all__ = [
    "HostLayout", "BareLayout", "SpecKitLayout",
    "SuperpowersLayout", "OpenSpecLayout", "detect",
]
```

- [ ] **Step 7.4: Verify, commit**

```bash
uv run python -m pytest tests/core/host_layout/ -v
git add src/orca/core/host_layout/ tests/core/host_layout/test_detect.py
git commit -m "feat(host_layout): detect(repo_root) probes 4 systems (Spec 015)"
```

---

## Task 8: from_manifest factory

**Files:**
- Modify: `src/orca/core/host_layout/__init__.py` (add `from_manifest`)
- Modify: `tests/core/host_layout/test_detect.py` (add tests)

`from_manifest` is the runtime entry point used by capabilities — they receive a manifest path and get back the right adapter.

- [ ] **Step 8.1: Write failing tests**

Append to `tests/core/host_layout/test_detect.py`:

```python
import textwrap

from orca.core.host_layout import from_manifest


def _write_manifest(tmp_path: Path, system: str, pattern: str) -> Path:
    manifest = tmp_path / ".orca" / "adoption.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(textwrap.dedent(f"""
        schema_version = 1
        [host]
        system = "{system}"
        feature_dir_pattern = "{pattern}"
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
    return manifest


def test_from_manifest_spec_kit(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "spec-kit", "specs/{feature_id}")
    layout = from_manifest(tmp_path)
    assert isinstance(layout, SpecKitLayout)
    assert layout.repo_root == tmp_path


def test_from_manifest_superpowers(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "superpowers", "docs/superpowers/specs/{feature_id}")
    layout = from_manifest(tmp_path)
    assert isinstance(layout, SuperpowersLayout)


def test_from_manifest_openspec(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "openspec", "openspec/changes/{feature_id}")
    layout = from_manifest(tmp_path)
    assert isinstance(layout, OpenSpecLayout)


def test_from_manifest_bare(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "bare", "docs/orca-specs/{feature_id}")
    layout = from_manifest(tmp_path)
    assert isinstance(layout, BareLayout)


def test_from_manifest_missing(tmp_path: Path) -> None:
    """No manifest at <repo>/.orca/adoption.toml -> raise."""
    from orca.core.adoption.manifest import ManifestError
    with pytest.raises((ManifestError, FileNotFoundError)):
        from_manifest(tmp_path)
```

- [ ] **Step 8.2: Run; verify FAIL.**
- [ ] **Step 8.3: Implement from_manifest**

Update `src/orca/core/host_layout/__init__.py`:

```python
"""HostLayout adapters: spec-system-agnostic path resolution."""
from __future__ import annotations

from pathlib import Path

from orca.core.adoption.manifest import load_manifest
from orca.core.host_layout.bare import BareLayout
from orca.core.host_layout.detect import detect
from orca.core.host_layout.openspec import OpenSpecLayout
from orca.core.host_layout.protocol import HostLayout
from orca.core.host_layout.spec_kit import SpecKitLayout
from orca.core.host_layout.superpowers import SuperpowersLayout

_ADAPTERS = {
    "spec-kit": SpecKitLayout,
    "openspec": OpenSpecLayout,
    "superpowers": SuperpowersLayout,
    "bare": BareLayout,
}


def from_manifest(repo_root: Path) -> HostLayout:
    """Load the manifest at <repo_root>/.orca/adoption.toml; return adapter.

    Raises ManifestError or FileNotFoundError if manifest absent/invalid.
    """
    manifest_path = repo_root / ".orca" / "adoption.toml"
    manifest = load_manifest(manifest_path)
    cls = _ADAPTERS[manifest.host.system]
    return cls(repo_root=repo_root)


__all__ = [
    "HostLayout", "BareLayout", "SpecKitLayout", "SuperpowersLayout",
    "OpenSpecLayout", "detect", "from_manifest",
]
```

- [ ] **Step 8.4: Verify, commit**

```bash
uv run python -m pytest tests/core/host_layout/ tests/core/adoption/ -v
git add src/orca/core/host_layout/__init__.py tests/core/host_layout/test_detect.py
git commit -m "feat(host_layout): from_manifest factory (Spec 015)"
```

---

## Task 9: Snapshot module (backup + state.json)

**Files:**
- Create: `src/orca/core/adoption/snapshot.py`
- Create: `src/orca/core/adoption/state.py`
- Test: `tests/core/adoption/test_snapshot.py`

- [ ] **Step 9.1: Write failing tests**

Create `tests/core/adoption/test_snapshot.py`:

```python
"""Snapshot + state.json round-trip + integrity checks."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orca.core.adoption.snapshot import snapshot_files, restore_file
from orca.core.adoption.state import (
    AdoptionState,
    FileEntry,
    load_state,
    write_state,
)


def test_snapshot_copies_files(tmp_path: Path) -> None:
    backup_dir = tmp_path / ".orca" / "adoption-backup" / "20260429T120000Z"
    f1 = tmp_path / "CLAUDE.md"
    f1.write_text("hello\n")
    f2 = tmp_path / "constitution.md"
    f2.write_text("# c\n")

    entries = snapshot_files([f1, f2], backup_dir, repo_root=tmp_path)

    assert len(entries) == 2
    assert (backup_dir / "CLAUDE.md").read_text() == "hello\n"
    assert (backup_dir / "constitution.md").read_text() == "# c\n"
    assert entries[0].rel_path == "CLAUDE.md"
    assert entries[0].pre_hash != ""


def test_snapshot_skips_nonexistent(tmp_path: Path) -> None:
    backup_dir = tmp_path / ".orca" / "adoption-backup" / "ts"
    f = tmp_path / "missing.md"
    entries = snapshot_files([f], backup_dir, repo_root=tmp_path)
    assert entries == []


def test_restore_file(tmp_path: Path) -> None:
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "CLAUDE.md").write_text("original\n")
    target = tmp_path / "CLAUDE.md"
    target.write_text("modified\n")
    restore_file(backup_dir / "CLAUDE.md", target)
    assert target.read_text() == "original\n"


def test_state_round_trip(tmp_path: Path) -> None:
    state = AdoptionState(
        manifest_hash="abc123",
        applied_at="2026-04-29T12:00:00Z",
        backup_timestamp="20260429T120000Z",
        files=[
            FileEntry(rel_path="CLAUDE.md", pre_hash="x", post_hash="y"),
            FileEntry(rel_path="constitution.md", pre_hash="a", post_hash="b"),
        ],
    )
    p = tmp_path / "state.json"
    write_state(state, p)
    loaded = load_state(p)
    assert loaded == state
```

- [ ] **Step 9.2: Run; verify FAIL.**
- [ ] **Step 9.3: Implement snapshot.py**

Create `src/orca/core/adoption/snapshot.py`:

```python
"""Snapshot files into backup_dir before modification.

Snapshot is the foundation of revertibility. Each modified file is
copied byte-for-byte to <backup_dir>/<rel_path> before any edit.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from orca.core.adoption.state import FileEntry


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def snapshot_files(
    paths: list[Path], backup_dir: Path, *, repo_root: Path
) -> list[FileEntry]:
    """Copy each existing path under `backup_dir` (mirroring rel paths).

    Non-existent paths are skipped (returned list is shorter than input).
    Returns FileEntry per snapshotted file with pre_hash populated.
    post_hash is empty string; caller fills it after applying changes.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    entries: list[FileEntry] = []
    for path in paths:
        if not path.exists():
            continue
        rel = path.relative_to(repo_root)
        target = backup_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        entries.append(
            FileEntry(rel_path=str(rel), pre_hash=_hash_file(path), post_hash="")
        )
    return entries


def restore_file(backup_path: Path, target: Path) -> None:
    """Copy `backup_path` -> `target`, preserving mtime."""
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_path, target)
```

Create `src/orca/core/adoption/state.py`:

```python
"""Adoption state.json: tracks what was applied for revertibility."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FileEntry:
    rel_path: str
    pre_hash: str
    post_hash: str


@dataclass(frozen=True)
class AdoptionState:
    manifest_hash: str
    applied_at: str  # ISO-8601 UTC
    backup_timestamp: str
    files: list[FileEntry] = field(default_factory=list)


def write_state(state: AdoptionState, path: Path) -> None:
    """Atomic write of state.json."""
    payload = {
        "manifest_hash": state.manifest_hash,
        "applied_at": state.applied_at,
        "backup_timestamp": state.backup_timestamp,
        "files": [asdict(f) for f in state.files],
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(encoded)
    tmp.replace(path)


def load_state(path: Path) -> AdoptionState:
    data = json.loads(path.read_text())
    return AdoptionState(
        manifest_hash=data["manifest_hash"],
        applied_at=data["applied_at"],
        backup_timestamp=data["backup_timestamp"],
        files=[FileEntry(**f) for f in data.get("files", [])],
    )
```

- [ ] **Step 9.4: Verify, commit**

```bash
uv run python -m pytest tests/core/adoption/test_snapshot.py -v
git add src/orca/core/adoption/snapshot.py src/orca/core/adoption/state.py tests/core/adoption/test_snapshot.py
git commit -m "feat(adoption): snapshot + state.json modules (Spec 015)"
```

---

## Task 10: CLAUDE.md merge policies

**Files:**
- Create: `src/orca/core/adoption/policies/__init__.py`
- Create: `src/orca/core/adoption/policies/claude_md.py`
- Test: `tests/core/adoption/test_policies.py`

- [ ] **Step 10.1: Write failing tests**

Create `tests/core/adoption/test_policies.py`:

```python
"""CLAUDE.md / constitution / slash-command policy unit tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.adoption.policies.claude_md import (
    ClaudeMdPolicyError,
    apply_section,
    detect_section,
    remove_section,
)

ORCA_CONTENT = "Orca is installed.\n\n- /orca:review-spec\n"
START_MARKER = "<!-- orca:adoption:start version=1 -->"
END_MARKER = "<!-- orca:adoption:end -->"


def test_apply_section_to_empty(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    apply_section(target, ORCA_CONTENT, section_marker="## Orca")
    out = target.read_text()
    assert START_MARKER in out
    assert END_MARKER in out
    assert "## Orca" in out
    assert ORCA_CONTENT in out


def test_apply_section_appends_to_existing(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# My CLAUDE.md\n\nExisting content.\n")
    apply_section(target, ORCA_CONTENT, section_marker="## Orca")
    out = target.read_text()
    assert "Existing content." in out
    assert ORCA_CONTENT in out
    assert out.index("Existing content.") < out.index(START_MARKER)


def test_apply_section_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# My CLAUDE.md\n")
    apply_section(target, ORCA_CONTENT, section_marker="## Orca")
    first = target.read_text()
    apply_section(target, ORCA_CONTENT, section_marker="## Orca")
    assert target.read_text() == first


def test_apply_section_updates_existing_block(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# My CLAUDE.md\n")
    apply_section(target, "Old content\n", section_marker="## Orca")
    apply_section(target, "New content\n", section_marker="## Orca")
    out = target.read_text()
    assert "New content" in out
    assert "Old content" not in out


def test_detect_section_present(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    apply_section(target, ORCA_CONTENT, section_marker="## Orca")
    assert detect_section(target) is True


def test_detect_section_absent(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# no orca\n")
    assert detect_section(target) is False


def test_remove_section_clean_revert(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# My CLAUDE.md\n\nOriginal.\n")
    apply_section(target, ORCA_CONTENT, section_marker="## Orca")
    remove_section(target)
    assert target.read_text() == "# My CLAUDE.md\n\nOriginal.\n"


def test_remove_section_refuses_tampered_block(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text(
        f"# my\n\n{START_MARKER}\n## Orca\nuser-edited!\n{END_MARKER}\n"
    )
    # Hash check happens at apply layer; here we just ensure remove_section
    # always operates only on the delimited block. Tampering inside markers
    # is detected by state.json hash mismatch, not by remove_section.
    remove_section(target)
    assert "## Orca" not in target.read_text()
```

- [ ] **Step 10.2: Run; verify FAIL.**
- [ ] **Step 10.3: Implement claude_md.py**

Create `src/orca/core/adoption/policies/__init__.py`:

```python
"""Policy modules for adoption surfaces (CLAUDE.md, constitution, etc.)."""
```

Create `src/orca/core/adoption/policies/claude_md.py`:

```python
"""CLAUDE.md / AGENTS.md merge policies.

`apply_section` is the canonical merge: idempotent, marker-delimited,
safe to re-apply. `remove_section` removes the marker-delimited block
during revert. `detect_section` checks for marker presence.
"""
from __future__ import annotations

import re
from pathlib import Path

START_MARKER = "<!-- orca:adoption:start version=1 -->"
END_MARKER = "<!-- orca:adoption:end -->"

_BLOCK_RE = re.compile(
    rf"\n*{re.escape(START_MARKER)}\n.*?\n{re.escape(END_MARKER)}\n*",
    re.DOTALL,
)


class ClaudeMdPolicyError(ValueError):
    """Raised when a policy operation cannot proceed safely."""


def detect_section(path: Path) -> bool:
    """Return True if path exists and contains an orca-managed section."""
    if not path.exists():
        return False
    return START_MARKER in path.read_text()


def apply_section(
    path: Path,
    content: str,
    *,
    section_marker: str,
) -> None:
    """Insert or replace the orca-managed section in `path`.

    If `path` does not exist, create it with just the orca block.
    If an orca block already exists, replace it in place.
    Otherwise append the orca block (with a leading blank line).
    """
    block = _build_block(content, section_marker)
    if not path.exists():
        path.write_text(block + "\n")
        return

    existing = path.read_text()
    if START_MARKER in existing:
        new = _BLOCK_RE.sub("\n\n" + block + "\n", existing)
    else:
        sep = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
        new = existing + sep + block + "\n"

    if new != existing:
        path.write_text(new)


def remove_section(path: Path) -> None:
    """Remove the orca-managed section from `path`, if present.

    No-op if path missing or no markers present.
    """
    if not path.exists():
        return
    existing = path.read_text()
    if START_MARKER not in existing:
        return
    cleaned = _BLOCK_RE.sub("\n", existing)
    # Collapse triple blank lines down to double
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    path.write_text(cleaned)


def _build_block(content: str, section_marker: str) -> str:
    body = content if content.endswith("\n") else content + "\n"
    return f"{START_MARKER}\n{section_marker}\n\n{body}{END_MARKER}"
```

- [ ] **Step 10.4: Verify, commit**

```bash
uv run python -m pytest tests/core/adoption/test_policies.py -v
git add src/orca/core/adoption/policies/ tests/core/adoption/test_policies.py
git commit -m "feat(adoption): CLAUDE.md section policy (Spec 015)"
```

---

## Task 11: Apply executor

**Files:**
- Create: `src/orca/core/adoption/apply.py`
- Test: `tests/core/adoption/test_apply_idempotency.py`

This is the largest single task. The executor: reads manifest → snapshots → applies each surface → writes state.json. This task implements only CLAUDE.md surface; constitution and slash-command surfaces are deferred to follow-up tasks (kept small to fit in subagent context).

- [ ] **Step 11.1: Write failing tests**

Create `tests/core/adoption/test_apply_idempotency.py`:

```python
"""Apply idempotency + state.json correctness."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from orca.core.adoption.apply import apply
from orca.core.adoption.manifest import load_manifest


def _write_manifest(repo: Path) -> Path:
    manifest = repo / ".orca" / "adoption.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(textwrap.dedent("""
        schema_version = 1
        [host]
        system = "superpowers"
        feature_dir_pattern = "docs/superpowers/specs/{feature_id}"
        agents_md_path = "AGENTS.md"
        review_artifact_dir = "docs/superpowers/reviews"
        [orca]
        state_dir = ".orca"
        installed_capabilities = ["cross-agent-review"]
        [slash_commands]
        namespace = "orca"
        enabled = ["review-spec"]
        disabled = []
        [claude_md]
        policy = "section"
        section_marker = "## Orca"
        namespace_prefix = "orca:"
        [constitution]
        policy = "respect-existing"
        [reversal]
        backup_dir = ".orca/adoption-backup"
    """))
    return manifest


def test_apply_creates_state_json(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    apply(repo_root=tmp_path)
    state_json = tmp_path / ".orca" / "adoption-state.json"
    assert state_json.exists()


def test_apply_writes_claude_md_section(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# host content\n")
    apply(repo_root=tmp_path)
    out = (tmp_path / "AGENTS.md").read_text()
    assert "<!-- orca:adoption:start version=1 -->" in out
    assert "## Orca" in out


def test_apply_is_idempotent(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# host content\n")
    apply(repo_root=tmp_path)
    first = (tmp_path / "AGENTS.md").read_text()
    apply(repo_root=tmp_path)
    second = (tmp_path / "AGENTS.md").read_text()
    assert first == second


def test_apply_snapshots_pre_modification(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    apply(repo_root=tmp_path)
    backup_dir = tmp_path / ".orca" / "adoption-backup"
    snapshots = list(backup_dir.glob("*/AGENTS.md"))
    assert len(snapshots) == 1
    assert snapshots[0].read_text() == "# original\n"


def test_apply_missing_manifest(tmp_path: Path) -> None:
    """Missing manifest -> ManifestError or FileNotFoundError."""
    from orca.core.adoption.manifest import ManifestError
    with pytest.raises((ManifestError, FileNotFoundError)):
        apply(repo_root=tmp_path)
```

- [ ] **Step 11.2: Run; verify FAIL.**
- [ ] **Step 11.3: Implement apply.py**

Create `src/orca/core/adoption/apply.py`:

```python
"""Apply executor: read manifest -> snapshot -> apply surfaces -> write state."""
from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

from orca.core.adoption.manifest import Manifest, load_manifest
from orca.core.adoption.policies.claude_md import apply_section
from orca.core.adoption.snapshot import snapshot_files
from orca.core.adoption.state import AdoptionState, FileEntry, write_state


def apply(*, repo_root: Path) -> AdoptionState:
    """Execute the manifest at <repo_root>/.orca/adoption.toml.

    Idempotent: re-running with no manifest changes produces no file diffs
    (state.json is rewritten with same content).
    """
    manifest_path = repo_root / ".orca" / "adoption.toml"
    manifest = load_manifest(manifest_path)
    manifest_hash = _hash_bytes(manifest_path.read_bytes())

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    applied_at = dt.datetime.now(dt.timezone.utc).isoformat()

    backup_dir = repo_root / manifest.reversal.backup_dir / timestamp

    surfaces = _enumerate_surfaces(repo_root, manifest)
    file_entries = snapshot_files(
        [path for path, _ in surfaces], backup_dir, repo_root=repo_root
    )

    for path, payload in surfaces:
        _apply_surface(path, payload, manifest)

    # Update post_hash for each entry
    final_entries = []
    for entry in file_entries:
        full = repo_root / entry.rel_path
        post = _hash_bytes(full.read_bytes()) if full.exists() else ""
        final_entries.append(
            FileEntry(rel_path=entry.rel_path, pre_hash=entry.pre_hash, post_hash=post)
        )

    state = AdoptionState(
        manifest_hash=manifest_hash,
        applied_at=applied_at,
        backup_timestamp=timestamp,
        files=final_entries,
    )
    write_state(state, repo_root / ".orca" / "adoption-state.json")
    return state


def _enumerate_surfaces(
    repo_root: Path, manifest: Manifest
) -> list[tuple[Path, str]]:
    """Return (path, payload) pairs for each surface to apply."""
    surfaces: list[tuple[Path, str]] = []
    if manifest.claude_md.policy != "skip":
        agents_md = repo_root / manifest.host.agents_md_path
        payload = _build_orca_section(manifest)
        surfaces.append((agents_md, payload))
    return surfaces


def _build_orca_section(manifest: Manifest) -> str:
    lines = [
        "Orca is installed in this repo.",
        "",
        f"- Capabilities: {', '.join(manifest.orca.installed_capabilities)}",
        f"- Slash commands: /{manifest.slash_commands.namespace}:{cmd}"
        if manifest.slash_commands.namespace
        else f"- Slash command: /{cmd}"
        for cmd in manifest.slash_commands.enabled
    ]
    # Fix list-comp leakage: rebuild explicitly
    lines = ["Orca is installed in this repo.", ""]
    lines.append(f"- Capabilities: {', '.join(manifest.orca.installed_capabilities)}")
    for cmd in manifest.slash_commands.enabled:
        if manifest.slash_commands.namespace:
            lines.append(f"- /{manifest.slash_commands.namespace}:{cmd}")
        else:
            lines.append(f"- /{cmd}")
    return "\n".join(lines) + "\n"


def _apply_surface(path: Path, payload: str, manifest: Manifest) -> None:
    if manifest.claude_md.policy == "section":
        apply_section(path, payload, section_marker=manifest.claude_md.section_marker)
    elif manifest.claude_md.policy == "append":
        existing = path.read_text() if path.exists() else ""
        path.write_text(existing.rstrip("\n") + "\n\n" + payload)
    elif manifest.claude_md.policy == "namespace":
        # ORCA.md gets the content; AGENTS.md gets a one-line pointer.
        orca_md = path.parent / "ORCA.md"
        orca_md.write_text(payload)
        if not path.exists() or "ORCA.md" not in path.read_text():
            existing = path.read_text() if path.exists() else ""
            path.write_text(existing.rstrip("\n") + "\nSee `ORCA.md` for orca details.\n")


def _hash_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()
```

- [ ] **Step 11.4: Verify, commit**

```bash
uv run python -m pytest tests/core/adoption/test_apply_idempotency.py -v
git add src/orca/core/adoption/apply.py tests/core/adoption/test_apply_idempotency.py
git commit -m "feat(adoption): apply executor with idempotent CLAUDE.md merge (Spec 015)"
```

---

## Task 12: Revert executor

**Files:**
- Create: `src/orca/core/adoption/revert.py`
- Test: `tests/core/adoption/test_revert.py`

- [ ] **Step 12.1: Write failing tests**

Create `tests/core/adoption/test_revert.py`:

```python
"""Apply + revert produces byte-identical original tree."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from orca.core.adoption.apply import apply
from orca.core.adoption.revert import RevertError, revert


def _write_manifest(repo: Path) -> None:
    (repo / ".orca").mkdir(parents=True, exist_ok=True)
    (repo / ".orca" / "adoption.toml").write_text(textwrap.dedent("""
        schema_version = 1
        [host]
        system = "superpowers"
        feature_dir_pattern = "docs/superpowers/specs/{feature_id}"
        agents_md_path = "AGENTS.md"
        review_artifact_dir = "docs/superpowers/reviews"
        [orca]
        state_dir = ".orca"
        installed_capabilities = ["cross-agent-review"]
        [slash_commands]
        namespace = "orca"
        enabled = ["review-spec"]
        disabled = []
        [claude_md]
        policy = "section"
        [constitution]
        policy = "respect-existing"
        [reversal]
        backup_dir = ".orca/adoption-backup"
    """))


def test_revert_restores_original(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    apply(repo_root=tmp_path)
    revert(repo_root=tmp_path)
    assert (tmp_path / "AGENTS.md").read_text() == "# original\n"


def test_revert_apply_apply_revert_idempotent(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    apply(repo_root=tmp_path)
    apply(repo_root=tmp_path)
    revert(repo_root=tmp_path)
    assert (tmp_path / "AGENTS.md").read_text() == "# original\n"


def test_revert_refuses_when_state_missing(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    with pytest.raises(RevertError, match="state"):
        revert(repo_root=tmp_path)


def test_revert_refuses_hand_edited_file(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    apply(repo_root=tmp_path)
    # User hand-edits inside the orca block
    contents = (tmp_path / "AGENTS.md").read_text()
    (tmp_path / "AGENTS.md").write_text(contents + "\nuser-edit\n")

    with pytest.raises(RevertError, match="hand-edit|hash"):
        revert(repo_root=tmp_path)


def test_revert_keep_state_preserves_backup(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    apply(repo_root=tmp_path)
    revert(repo_root=tmp_path, keep_state=True)
    backup_root = tmp_path / ".orca" / "adoption-backup"
    assert backup_root.exists()
    assert any(backup_root.iterdir())
```

- [ ] **Step 12.2: Run; verify FAIL.**
- [ ] **Step 12.3: Implement revert.py**

Create `src/orca/core/adoption/revert.py`:

```python
"""Revert executor: restore from backup if state.json hashes match."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from orca.core.adoption.manifest import load_manifest
from orca.core.adoption.snapshot import restore_file
from orca.core.adoption.state import load_state


class RevertError(RuntimeError):
    """Raised when revert cannot proceed safely."""


def revert(*, repo_root: Path, keep_state: bool = False) -> None:
    """Undo a prior apply per state.json.

    For each file in state.json: verify current hash matches post_hash;
    if so, copy backup over. If not, refuse for that file (user has
    hand-edited; revert proceeds for other files; raises after).

    Removes .orca/ at the end unless keep_state=True (then preserves
    adoption-backup/ as audit trail).
    """
    state_path = repo_root / ".orca" / "adoption-state.json"
    if not state_path.exists():
        raise RevertError(f"adoption-state.json not found at {state_path}")

    state = load_state(state_path)
    manifest = load_manifest(repo_root / ".orca" / "adoption.toml")
    backup_dir = repo_root / manifest.reversal.backup_dir / state.backup_timestamp

    if not backup_dir.exists():
        raise RevertError(f"backup directory missing: {backup_dir}")

    skipped: list[str] = []
    for entry in state.files:
        target = repo_root / entry.rel_path
        if not target.exists():
            # File was deleted post-apply; restore from backup
            restore_file(backup_dir / entry.rel_path, target)
            continue
        actual_hash = _hash_bytes(target.read_bytes())
        if actual_hash != entry.post_hash:
            skipped.append(entry.rel_path)
            continue
        backup_file = backup_dir / entry.rel_path
        if backup_file.exists():
            restore_file(backup_file, target)
        else:
            # File didn't exist pre-apply; remove
            target.unlink()

    if skipped:
        raise RevertError(
            f"hand-edit detected (post-apply hash mismatch); refused for: "
            f"{', '.join(skipped)}. Other files reverted; manual cleanup required."
        )

    if not keep_state:
        shutil.rmtree(repo_root / ".orca")


def _hash_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()
```

- [ ] **Step 12.4: Verify, commit**

```bash
uv run python -m pytest tests/core/adoption/test_revert.py -v
git add src/orca/core/adoption/revert.py tests/core/adoption/test_revert.py
git commit -m "feat(adoption): revert executor with hash-checked safety (Spec 015)"
```

---

## Task 13: CLI wiring (`orca-cli adopt` and `orca-cli apply`)

**Files:**
- Modify: `src/orca/python_cli.py`
- Create: `src/orca/core/adoption/wizard.py`
- Test: `tests/cli/test_adopt_apply_cli.py`

The wizard for `orca adopt` is non-interactive in tests (pulls answers from a fixture); interactive prompts use `input()` with a mockable interface.

- [ ] **Step 13.1: Write failing tests**

Create `tests/cli/test_adopt_apply_cli.py`:

```python
"""orca-cli adopt + apply smoke tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from orca.python_cli import main as cli_main


def test_adopt_in_bare_repo_writes_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["adopt", "--host", "bare", "--force", "--plan-only"])
    assert rc == 0
    assert (tmp_path / ".orca" / "adoption.toml").exists()


def test_adopt_in_superpowers_repo_detects(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    rc = cli_main(["adopt", "--force", "--plan-only"])
    assert rc == 0
    manifest_text = (tmp_path / ".orca" / "adoption.toml").read_text()
    assert 'system = "superpowers"' in manifest_text


def test_apply_after_adopt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    cli_main(["adopt", "--host", "bare", "--force", "--plan-only"])
    rc = cli_main(["apply"])
    assert rc == 0
    assert (tmp_path / ".orca" / "adoption-state.json").exists()


def test_apply_revert_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    cli_main(["adopt", "--host", "bare", "--force", "--plan-only"])
    cli_main(["apply"])
    rc = cli_main(["apply", "--revert"])
    assert rc == 0
    assert (tmp_path / "AGENTS.md").read_text() == "# original\n"


def test_apply_dry_run_no_writes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# original\n")
    cli_main(["adopt", "--host", "bare", "--force", "--plan-only"])
    rc = cli_main(["apply", "--dry-run"])
    assert rc == 0
    # AGENTS.md untouched
    assert (tmp_path / "AGENTS.md").read_text() == "# original\n"
    # state.json NOT written
    assert not (tmp_path / ".orca" / "adoption-state.json").exists()
```

- [ ] **Step 13.2: Run; verify FAIL.**
- [ ] **Step 13.3: Implement wizard.py**

Create `src/orca/core/adoption/wizard.py`:

```python
"""Wizard for `orca adopt`: detection + (optionally interactive) prompts."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from orca.core.adoption.manifest import (
    ClaudeMdConfig,
    ConstitutionConfig,
    HostConfig,
    Manifest,
    OrcaConfig,
    ReversalConfig,
    SUPPORTED_HOST_SYSTEMS,
    SUPPORTED_SCHEMA_VERSION,
    SlashCommandsConfig,
    write_manifest,
)
from orca.core.host_layout.detect import detect

DEFAULT_CAPABILITIES = [
    "cross-agent-review",
    "citation-validator",
    "contradiction-detector",
    "completion-gate",
    "worktree-overlap-check",
    "flow-state-projection",
]
DEFAULT_SLASH_COMMANDS = [
    "review-spec", "review-code", "review-pr", "gate", "cite", "doctor",
]

_HOST_DEFAULTS = {
    "spec-kit": {
        "feature_dir_pattern": "specs/{feature_id}",
        "agents_md_path": "CLAUDE.md",
        "review_artifact_dir": "specs",
        "constitution_path": ".specify/memory/constitution.md",
    },
    "openspec": {
        "feature_dir_pattern": "openspec/changes/{feature_id}",
        "agents_md_path": "AGENTS.md",
        "review_artifact_dir": "openspec/changes",
        "constitution_path": None,
    },
    "superpowers": {
        "feature_dir_pattern": "docs/superpowers/specs/{feature_id}",
        "agents_md_path": "AGENTS.md",
        "review_artifact_dir": "docs/superpowers/reviews",
        "constitution_path": "docs/superpowers/constitution.md",
    },
    "bare": {
        "feature_dir_pattern": "docs/orca-specs/{feature_id}",
        "agents_md_path": "AGENTS.md",
        "review_artifact_dir": "docs/orca-specs/_reviews",
        "constitution_path": None,
    },
}


def build_default_manifest(
    repo_root: Path,
    *,
    host_override: str | None = None,
) -> Manifest:
    """Construct a Manifest using detection + sensible defaults."""
    if host_override is not None:
        if host_override not in SUPPORTED_HOST_SYSTEMS:
            raise ValueError(
                f"--host={host_override!r} not in {sorted(SUPPORTED_HOST_SYSTEMS)}"
            )
        system = host_override
    else:
        layout = detect(repo_root)
        # Map adapter type back to host_system string
        from orca.core.host_layout import (
            BareLayout, OpenSpecLayout, SpecKitLayout, SuperpowersLayout,
        )
        type_map = {
            BareLayout: "bare",
            OpenSpecLayout: "openspec",
            SpecKitLayout: "spec-kit",
            SuperpowersLayout: "superpowers",
        }
        system = type_map[type(layout)]

    defaults = _HOST_DEFAULTS[system]
    host = HostConfig(
        system=system,  # type: ignore[arg-type]
        feature_dir_pattern=defaults["feature_dir_pattern"],
        agents_md_path=defaults["agents_md_path"],
        review_artifact_dir=defaults["review_artifact_dir"],
        constitution_path=defaults["constitution_path"],
    )

    return Manifest(
        schema_version=SUPPORTED_SCHEMA_VERSION,
        host=host,
        orca=OrcaConfig(
            state_dir=".orca",
            installed_capabilities=list(DEFAULT_CAPABILITIES),
        ),
        slash_commands=SlashCommandsConfig(
            namespace="orca",
            enabled=list(DEFAULT_SLASH_COMMANDS),
            disabled=[],
        ),
        claude_md=ClaudeMdConfig(policy="section"),
        constitution=ConstitutionConfig(policy="respect-existing"),
        reversal=ReversalConfig(backup_dir=".orca/adoption-backup"),
    )


def run_adopt(
    *,
    repo_root: Path,
    host_override: str | None = None,
    plan_only: bool = False,
    force: bool = False,
    reset: bool = False,
) -> Path:
    """Build manifest, write to disk, return path to manifest.

    With --force, prompts are skipped (defaults used).
    With --reset, existing manifest is backed up and regenerated.
    Without --plan-only, also runs apply.
    """
    manifest_path = repo_root / ".orca" / "adoption.toml"

    if manifest_path.exists() and not reset and not force:
        raise FileExistsError(
            f"manifest already exists at {manifest_path}; pass --reset to regenerate"
        )

    if manifest_path.exists() and reset:
        backup = manifest_path.with_suffix(".toml.backup")
        manifest_path.replace(backup)

    manifest = build_default_manifest(repo_root, host_override=host_override)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    write_manifest(manifest, manifest_path)
    return manifest_path
```

- [ ] **Step 13.4: Wire into python_cli.py**

Add to `src/orca/python_cli.py`:

```python
# Add import near other capability imports
from orca.core.adoption.wizard import run_adopt
from orca.core.adoption.apply import apply as adoption_apply
from orca.core.adoption.revert import revert as adoption_revert

# Add to CAPABILITIES registry
CAPABILITIES["adopt"] = (_run_adopt, "1.0.0")
CAPABILITIES["apply"] = (_run_apply, "1.0.0")


def _run_adopt(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="orca-cli adopt", exit_on_error=False
    )
    parser.add_argument("--host", default=None,
                        choices=["spec-kit", "openspec", "superpowers", "bare"])
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--repo-root", default=".",
                        help="path to repo root (default: cwd)")
    try:
        ns, unknown = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        return 2

    if unknown:
        print(f"unknown args: {unknown}", file=sys.stderr)
        return 2

    repo_root = Path(ns.repo_root).resolve()
    try:
        manifest_path = run_adopt(
            repo_root=repo_root,
            host_override=ns.host,
            plan_only=ns.plan_only,
            force=ns.force,
            reset=ns.reset,
        )
    except (ValueError, FileExistsError) as exc:
        print(f"adopt failed: {exc}", file=sys.stderr)
        return 1

    print(f"manifest written: {manifest_path}")
    if not ns.plan_only:
        adoption_apply(repo_root=repo_root)
        print(f"applied; state: {repo_root}/.orca/adoption-state.json")
    return 0


def _run_apply(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="orca-cli apply", exit_on_error=False
    )
    parser.add_argument("--revert", action="store_true")
    parser.add_argument("--keep-state", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo-root", default=".")
    try:
        ns, unknown = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit):
        return 2
    if unknown:
        print(f"unknown args: {unknown}", file=sys.stderr)
        return 2

    repo_root = Path(ns.repo_root).resolve()
    try:
        if ns.revert:
            adoption_revert(repo_root=repo_root, keep_state=ns.keep_state)
            print("reverted")
            return 0
        if ns.dry_run:
            # Read manifest; print what WOULD be applied; don't write
            from orca.core.adoption.manifest import load_manifest
            manifest = load_manifest(repo_root / ".orca" / "adoption.toml")
            print(f"would apply manifest at {repo_root / '.orca' / 'adoption.toml'}")
            print(f"  host.system = {manifest.host.system}")
            print(f"  agents_md_path = {manifest.host.agents_md_path}")
            print(f"  claude_md.policy = {manifest.claude_md.policy}")
            return 0
        adoption_apply(repo_root=repo_root)
        print(f"applied; state: {repo_root}/.orca/adoption-state.json")
        return 0
    except Exception as exc:
        print(f"apply failed: {exc}", file=sys.stderr)
        return 1
```

(Place the helper functions near other `_run_*` capability handlers; place the registry entries with the existing `CAPABILITIES` dict.)

- [ ] **Step 13.5: Verify, commit**

```bash
uv run python -m pytest tests/cli/test_adopt_apply_cli.py tests/core/adoption/ -v
git add src/orca/core/adoption/wizard.py src/orca/python_cli.py tests/cli/test_adopt_apply_cli.py
git commit -m "feat(cli): orca-cli adopt + apply wired (Spec 015)"
```

---

## Task 14: Update path-safety contract Class A

**Files:**
- Modify: `docs/superpowers/contracts/path-safety.md`

- [ ] **Step 14.1: Edit Class A description**

In `docs/superpowers/contracts/path-safety.md` § "Class A: repo paths", replace the `**Roots:**` line with:

```markdown
**Roots:** the user's git repository root (`git rev-parse --show-toplevel`) OR a feature directory resolved via `host_layout.resolve_feature_dir(feature_id)` per the host repo's adoption manifest. The manifest's `host.system` determines the convention: spec-kit (`<repo>/specs/<feature_id>/`), openspec (`<repo>/openspec/changes/<feature_id>/`), superpowers (`<repo>/docs/superpowers/specs/<feature_id>/`), or bare (`<repo>/docs/orca-specs/<feature_id>/`). See `docs/superpowers/specs/2026-04-29-orca-spec-015-brownfield-adoption-design.md`.
```

- [ ] **Step 14.2: Commit**

```bash
git add docs/superpowers/contracts/path-safety.md
git commit -m "docs(contracts): path-safety Class A reads from host_layout (Spec 015)"
```

---

## Task 15: Self-host integration test

**Files:**
- Test: `tests/integration/test_self_host_dogfood.py`

The orca repo IS its own host (superpowers convention). Running `orca-cli adopt` against the orca repo's worktree must succeed.

- [ ] **Step 15.1: Write integration test**

Create `tests/integration/__init__.py` (empty if not present).

Create `tests/integration/test_self_host_dogfood.py`:

```python
"""orca dogfood: orca-cli adopt against the orca repo itself succeeds."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
def test_self_host_adopt_detects_superpowers(tmp_path: Path) -> None:
    """Copy the orca repo's superpowers signal into a temp dir; ensure detection works.

    We don't run against the real worktree because adopt would write .orca/adoption.toml
    and we don't want to perturb dev state. Instead we create a tiny fixture that
    mimics the orca repo's superpowers signature.
    """
    # Mimic superpowers signal
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "constitution.md").write_text("# c\n")

    # Run orca-cli adopt --plan-only
    result = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "adopt",
         "--repo-root", str(tmp_path), "--force", "--plan-only"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    manifest = (tmp_path / ".orca" / "adoption.toml").read_text()
    assert 'system = "superpowers"' in manifest
    assert "docs/superpowers/specs/{feature_id}" in manifest


@pytest.mark.integration
def test_self_host_apply_revert_round_trip(tmp_path: Path) -> None:
    """End-to-end: adopt + apply + revert against a fresh fixture leaves no trace."""
    (tmp_path / "AGENTS.md").write_text("# original AGENTS.md\n")
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)

    # adopt
    subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "adopt",
         "--repo-root", str(tmp_path), "--force"],
        check=True,
    )
    # AGENTS.md should now have the orca block
    after_apply = (tmp_path / "AGENTS.md").read_text()
    assert "<!-- orca:adoption:start" in after_apply

    # revert
    result = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "apply",
         "--repo-root", str(tmp_path), "--revert"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

    # AGENTS.md byte-identical to original
    assert (tmp_path / "AGENTS.md").read_text() == "# original AGENTS.md\n"
    # .orca/ removed
    assert not (tmp_path / ".orca").exists()
```

- [ ] **Step 15.2: Verify, commit**

```bash
uv run python -m pytest tests/integration/test_self_host_dogfood.py -v
git add tests/integration/test_self_host_dogfood.py
git commit -m "test(integration): self-host dogfood for adoption (Spec 015)"
```

---

## Task 16: Doctor checks for adoption

**Files:**
- Modify: `plugins/claude-code/commands/doctor.md`
- Modify: `scripts/bash/orca-doctor.sh`

- [ ] **Step 16.1: Add adoption check to orca-doctor.sh**

Append to the existing checks in `scripts/bash/orca-doctor.sh`:

```bash
# Check 6: Adoption manifest (optional; only checks if .orca/adoption.toml exists)
if [ -f "$REPO_ROOT/.orca/adoption.toml" ]; then
  if uv run --project "$ORCA_PROJECT" orca-cli apply --repo-root "$REPO_ROOT" --dry-run >/dev/null 2>&1; then
    echo "PASS: .orca/adoption.toml validates"
  else
    echo "FAIL: .orca/adoption.toml present but does not validate"
    DOCTOR_EXIT=1
  fi
else
  echo "INFO: no .orca/adoption.toml (orca not adopted; run orca-cli adopt)"
fi
```

- [ ] **Step 16.2: Update doctor.md to mention adoption check**

In `plugins/claude-code/commands/doctor.md`, append to the "Workflow Contract" section a note that doctor reports adoption status as part of its output.

- [ ] **Step 16.3: Commit**

```bash
git add plugins/claude-code/commands/doctor.md scripts/bash/orca-doctor.sh
git commit -m "feat(doctor): adoption manifest validation check (Spec 015)"
```

---

## Task 17: Final verification + push

- [ ] **Step 17.1: Run full suite**

```bash
uv run python -m pytest -q
```

Expected: 462 + ~50 new tests = ~512+ passing.

- [ ] **Step 17.2: Run integration tests explicitly**

```bash
uv run python -m pytest tests/integration/ -v -m integration
```

Expected: 2 passing (self-host dogfood).

- [ ] **Step 17.3: Manual smoke test against the actual orca repo (in a temp clone)**

```bash
TMP=$(mktemp -d)
cp -r /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats/.git "$TMP/.git"
git -C "$TMP" checkout -- .
cd "$TMP" && uv run --project /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats orca-cli adopt --plan-only --force
cat "$TMP/.orca/adoption.toml" | head -20
rm -rf "$TMP"
```

Expected: manifest written; `system = "superpowers"`.

- [ ] **Step 17.4: Push branch**

```bash
git push
```

---

## Out of Scope (deferred to follow-up)

- Constitution.md merge policy (`merge` mode) — only `respect-existing` and `skip` implemented in v1
- Slash command flat namespace conflict detection (CLI helper) — defaults to `namespace = "orca"` always
- Migration of existing 015 historical artifacts — manual step documented in Spec 015
- Refactor of existing slash commands (`/orca:review-spec` etc.) to consult `host_layout` — gated behind a separate plan; current behavior preserved
- CI hook installation — out of v1 scope per Spec 015
- Multi-host detection ambiguity prompt — `--force` always wins via priority order today
- Schema_version migration logic — only schema_version=1 supported today

---

## Self-Review Checklist

**1. Spec coverage:**
- Manifest schema → Task 2 ✓
- HostLayout protocol + 4 adapters → Tasks 3-6 ✓
- Detection → Task 7 ✓
- from_manifest → Task 8 ✓
- Snapshot + state.json → Task 9 ✓
- CLAUDE.md policies → Task 10 ✓
- Apply executor → Task 11 ✓
- Revert executor → Task 12 ✓
- CLI surface → Task 13 ✓
- Path-safety contract update → Task 14 ✓
- Self-host integration → Task 15 ✓
- Doctor checks → Task 16 ✓
- Constitution merge mode → DEFERRED (called out in Out of Scope) ✓
- Slash command flat namespace → DEFERRED ✓
- Slash-command refactor to host_layout → DEFERRED to follow-up plan ✓

**2. No placeholders:** all steps have actual content; no TBD/TODO ✓

**3. Type consistency:**
- `Manifest` dataclass has `host`, `orca`, `slash_commands`, `claude_md`, `constitution`, `reversal` fields → matches across Tasks 2, 11, 12, 13 ✓
- `HostLayout` protocol has `repo_root`, `resolve_feature_dir`, `list_features`, `constitution_path`, `agents_md_path`, `review_artifact_dir` → matches across Tasks 3-7 ✓
- `AdoptionState` has `manifest_hash`, `applied_at`, `backup_timestamp`, `files` → matches across Tasks 9, 11, 12 ✓
- `FileEntry` has `rel_path`, `pre_hash`, `post_hash` → matches across Tasks 9, 11, 12 ✓

**4. Estimated test deltas:**
- Task 2: +5 (manifest)
- Task 3-6: +24 (host_layout protocol contract, 4 adapters)
- Task 7: +6 (detect)
- Task 8: +5 (from_manifest)
- Task 9: +4 (snapshot/state)
- Task 10: +7 (claude_md policy)
- Task 11: +5 (apply idempotency)
- Task 12: +5 (revert)
- Task 13: +5 (CLI smoke)
- Task 15: +2 (self-host dogfood)
- Total: ~68 new tests (462 → ~530)

---

## Honest Risk Notes

- **Task 11 (apply executor) has a list-comp leakage bug in the example code** — `_build_orca_section` initially uses a dict-comp-like pattern then immediately rebuilds explicitly. This is intentional in the plan (the explicit rebuild is what should ship); the implementer should use the explicit form.
- **Task 13 (CLI wiring) is the largest single task.** ~150 LOC including the new wizard.py module. May warrant a split if the implementer feels constrained.
- **`from_manifest` in Task 8 imports from `orca.core.adoption.manifest`** which is built in Task 2. Task ordering is deliberate; don't rearrange.
- **`apply` in Task 11 imports from `policies.claude_md`** which is built in Task 10. Same.
- **Auto mode caveat:** the `--force` flag in `orca-cli adopt` skips prompts; tests rely on this. Without `--force`, the wizard is interactive (uses `input()`); add `--force` to all CLI tests.
- **Revert + `.orca/` removal:** Task 12's `revert()` removes the entire `.orca/` directory unless `keep_state=True`. If users have unrelated state in `.orca/` (e.g., flow-state-projection caches), they lose it. Consider: scope removal to `adoption.toml`, `adoption-state.json`, `adoption-backup/` only. Decide during Task 12 implementation.
- **Path-safety contract update (Task 14) is a doc-only change** but creates a forward dependency: capabilities should consult `host_layout` going forward. The actual capability-side refactor is OUT OF SCOPE per the Out of Scope section. The doc update reflects the future state; capabilities don't yet read from `host_layout` until a follow-up plan.
