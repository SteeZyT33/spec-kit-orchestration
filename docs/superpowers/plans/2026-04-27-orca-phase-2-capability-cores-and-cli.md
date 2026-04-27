# Orca Phase 2: Capability Cores + CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the orca v1 capability cores and canonical CLI, starting with `cross-agent-review` end-to-end as the wedge, then layering the remaining 5 capabilities on the proven shape.

**Architecture:** Python library at `src/orca/` with `core/` (Result type, errors, findings schema, bundle builder, reviewer abstractions) and `capabilities/` (six capability modules). CLI at `src/orca/cli.py` exposes one subcommand per capability; canonical I/O is JSON to stdout. Reviewer backends (`ClaudeReviewer`, `CodexReviewer`, `CrossReviewer`) implement a single `review(bundle, prompt) -> RawFindings` interface; LLM tests use recorded fixtures with `ORCA_LIVE=1` escape hatch for live runs.

**Tech Stack:** Python 3.11+, uv, pytest, jsonschema, Anthropic SDK (claude reviewer), OpenAI SDK or Codex CLI shellout (codex reviewer). No external Result library — small in-repo discriminated union. Pre-existing libraries (`flow_state.py`) reused via API stabilization, not rewrite.

**Starting state:** Phase 1 has landed (PR #68). Repo is renamed to `orca`, `src/orca/` exists, kill-list stripped, state path is `.orca/`, slash commands under `plugins/claude-code/commands/orca:*`. Pre-existing modules: `flow_state.py`, `sdd_adapter/`, `context_handoffs.py`, `brainstorm_memory.py`, `tui/`, `session.py`, `banner_anim.py`. `cli.py` currently shells to a bash launcher — Phase 2 introduces a real Python CLI alongside (Bash launcher remains for opinion-layer compatibility; new Python CLI is the canonical capability surface).

---

## File Structure

### New files (Phase 2a — wedge: cross-agent-review)

- `src/orca/core/__init__.py` — re-exports `Result`, `Ok`, `Err`, `Error`, `ErrorKind`
- `src/orca/core/result.py` — `Result[T, E]` discriminated union, `Ok`/`Err` constructors, `to_json()`/`from_json()`
- `src/orca/core/errors.py` — `Error`, `ErrorKind` enum (`input_invalid`, `backend_failure`, `timeout`, `internal`)
- `src/orca/core/capability.py` — `Capability` protocol, `CapabilityMetadata`, JSON envelope helpers
- `src/orca/core/findings.py` — `Finding` dataclass, `Findings` collection, stable `dedupe_id()`, severity/confidence enums
- `src/orca/core/bundle.py` — `ReviewBundle` dataclass (target paths, kind, feature_id, criteria, context); `build_bundle()` from CLI args
- `src/orca/core/reviewers/__init__.py` — re-exports `Reviewer` protocol + concrete reviewers
- `src/orca/core/reviewers/base.py` — `Reviewer` protocol, `RawFindings` type, `ReviewerError`
- `src/orca/core/reviewers/claude.py` — `ClaudeReviewer` (Anthropic SDK)
- `src/orca/core/reviewers/codex.py` — `CodexReviewer` (Codex CLI shellout)
- `src/orca/core/reviewers/cross.py` — `CrossReviewer` (runs both, merges with dedupe, handles partial)
- `src/orca/core/reviewers/fixtures.py` — `FixtureReviewer` for tests (replays recorded JSON)
- `src/orca/capabilities/__init__.py` — capability registry
- `src/orca/capabilities/cross_agent_review.py` — `cross_agent_review(input) -> Result[Findings, Error]`
- `src/orca/capabilities/_cli_helpers.py` — shared CLI input parsing, JSON output, exit code mapping
- `src/orca/python_cli.py` — new Python CLI entry (avoids collision with existing bash-shim `cli.py`)
- `tests/core/test_result.py`, `tests/core/test_findings.py`, `tests/core/test_bundle.py`
- `tests/core/reviewers/test_base.py` (contract test parameterized across reviewers), `tests/core/reviewers/test_claude.py`, `tests/core/reviewers/test_codex.py`, `tests/core/reviewers/test_cross.py`
- `tests/capabilities/test_cross_agent_review.py`
- `tests/cli/test_python_cli.py`
- `tests/fixtures/reviewers/claude/<scenario>.json`, `tests/fixtures/reviewers/codex/<scenario>.json` — recorded responses
- `docs/capabilities/cross-agent-review/schema/input.json`
- `docs/capabilities/cross-agent-review/schema/output.json`
- `docs/capabilities/cross-agent-review/README.md`

### New files (Phase 2b — remaining capabilities)

- `src/orca/capabilities/worktree_overlap_check.py`
- `src/orca/capabilities/flow_state_projection.py` — thin wrapper over existing `flow_state.py`
- `src/orca/capabilities/completion_gate.py`
- `src/orca/capabilities/citation_validator.py`
- `src/orca/capabilities/contradiction_detector.py`
- `tests/capabilities/test_worktree_overlap_check.py`
- `tests/capabilities/test_flow_state_projection.py`
- `tests/capabilities/test_completion_gate.py`
- `tests/capabilities/test_citation_validator.py`
- `tests/capabilities/test_contradiction_detector.py`
- `docs/capabilities/<capability>/schema/{input,output}.json` × 5
- `docs/capabilities/<capability>/README.md` × 5
- `tests/fixtures/capabilities/<capability>/...` per capability

### Modified files

- `pyproject.toml` — add `[project.scripts]` `orca-cli = "orca.python_cli:main"`; declare deps `anthropic>=0.40`, `jsonschema>=4`
- `src/orca/cli.py` — leave as-is (bash shim for opinion layer); document the split
- `.github/workflows/ci.yml` — add JSON schema validation step; add `pytest -m fixtures` and `pytest -m mocked` matrix entries

### Why this layout

- `core/` holds primitives reused by every capability. Capabilities depend on `core`, never vice versa.
- Reviewers split per backend: a new reviewer = one file with one class implementing one protocol.
- Capabilities are flat modules (no per-capability subpackages) because each is one file's worth of logic. Cross-agent-review's reviewers live in `core/reviewers/` because they're shared infra, not capability-private.
- `python_cli.py` separates from `cli.py` (bash shim) to avoid touching the existing opinion-layer entry. After Phase 3, we can collapse if desired.
- Test layout mirrors source layout for reliable navigation.

---

## Phase 2a: Foundation + cross-agent-review wedge

### Task 1: Result type and Error type

**Why first:** every capability returns `Result`. Building it once correctly avoids retroactive refactors.

**Files:**
- Create: `src/orca/core/__init__.py`
- Create: `src/orca/core/result.py`
- Create: `src/orca/core/errors.py`
- Create: `tests/core/test_result.py`
- Create: `tests/core/__init__.py`

- [ ] **Step 1: Write the failing tests for Result**

```python
# tests/core/test_result.py
from __future__ import annotations

import pytest

from orca.core.result import Err, Ok, Result
from orca.core.errors import Error, ErrorKind


def test_ok_carries_value():
    r: Result[int, Error] = Ok(42)
    assert r.ok is True
    assert r.value == 42


def test_err_carries_error():
    e = Error(kind=ErrorKind.INPUT_INVALID, message="bad input")
    r: Result[int, Error] = Err(e)
    assert r.ok is False
    assert r.error.kind == ErrorKind.INPUT_INVALID
    assert r.error.message == "bad input"


def test_ok_to_json():
    r: Result[dict, Error] = Ok({"foo": "bar"})
    payload = r.to_json(capability="test", version="0.1.0", duration_ms=12)
    assert payload["ok"] is True
    assert payload["result"] == {"foo": "bar"}
    assert payload["metadata"] == {"capability": "test", "version": "0.1.0", "duration_ms": 12}
    assert "error" not in payload


def test_err_to_json():
    e = Error(kind=ErrorKind.TIMEOUT, message="slow", detail={"after_s": 30})
    r: Result[dict, Error] = Err(e)
    payload = r.to_json(capability="test", version="0.1.0", duration_ms=30000)
    assert payload["ok"] is False
    assert payload["error"] == {
        "kind": "timeout",
        "message": "slow",
        "detail": {"after_s": 30},
    }
    assert "result" not in payload


def test_error_kind_round_trip():
    for kind in ErrorKind:
        assert ErrorKind(kind.value) is kind


def test_error_default_detail_is_none():
    e = Error(kind=ErrorKind.INTERNAL, message="boom")
    payload = Err(e).to_json(capability="x", version="0", duration_ms=0)
    assert "detail" not in payload["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/core/test_result.py -v`
Expected: ImportError / ModuleNotFoundError on `orca.core.result`.

- [ ] **Step 3: Implement Error and ErrorKind**

```python
# src/orca/core/errors.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorKind(str, Enum):
    INPUT_INVALID = "input_invalid"
    BACKEND_FAILURE = "backend_failure"
    TIMEOUT = "timeout"
    INTERNAL = "internal"


@dataclass(frozen=True)
class Error:
    kind: ErrorKind
    message: str
    detail: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": self.kind.value, "message": self.message}
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload
```

- [ ] **Step 4: Implement Result, Ok, Err**

```python
# src/orca/core/result.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar, Union

from orca.core.errors import Error

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T
    ok: bool = True

    def to_json(self, *, capability: str, version: str, duration_ms: int) -> dict[str, Any]:
        return {
            "ok": True,
            "result": _to_json_safe(self.value),
            "metadata": {
                "capability": capability,
                "version": version,
                "duration_ms": duration_ms,
            },
        }


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E
    ok: bool = False

    def to_json(self, *, capability: str, version: str, duration_ms: int) -> dict[str, Any]:
        err_payload = self.error.to_json() if hasattr(self.error, "to_json") else {"message": str(self.error)}
        return {
            "ok": False,
            "error": err_payload,
            "metadata": {
                "capability": capability,
                "version": version,
                "duration_ms": duration_ms,
            },
        }


Result = Union[Ok[T], Err[E]]


def _to_json_safe(value: Any) -> Any:
    if hasattr(value, "to_json") and callable(value.to_json):
        return value.to_json()
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(v) for v in value]
    return value
```

- [ ] **Step 5: Add core package exports**

```python
# src/orca/core/__init__.py
from __future__ import annotations

from orca.core.errors import Error, ErrorKind
from orca.core.result import Err, Ok, Result

__all__ = ["Error", "ErrorKind", "Err", "Ok", "Result"]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run python -m pytest tests/core/test_result.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/orca/core/__init__.py src/orca/core/result.py src/orca/core/errors.py tests/core/__init__.py tests/core/test_result.py
git commit -m "feat(core): add Result/Ok/Err and Error/ErrorKind"
```

---

### Task 2: Findings schema and stable dedupe ID

**Why:** every reviewer-backed capability emits findings. Stable dedupe IDs are the wedge — they're what makes cross-mode merging reliable.

**Files:**
- Create: `src/orca/core/findings.py`
- Create: `tests/core/test_findings.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_findings.py
from __future__ import annotations

from orca.core.findings import Finding, Findings, Severity, Confidence


def test_finding_to_json_minimal():
    f = Finding(
        category="correctness",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        summary="Off-by-one in loop",
        detail="The range should be range(n+1) not range(n).",
        evidence=["src/foo.py:42"],
        suggestion="Use range(n+1)",
        reviewer="claude",
    )
    out = f.to_json()
    assert out["category"] == "correctness"
    assert out["severity"] == "high"
    assert out["confidence"] == "high"
    assert out["evidence"] == ["src/foo.py:42"]
    assert out["reviewer"] == "claude"
    assert "id" in out and len(out["id"]) == 16


def test_dedupe_id_stable_across_calls():
    base = dict(
        category="correctness",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        summary="Off-by-one in loop",
        detail="The range should be range(n+1) not range(n).",
        evidence=["src/foo.py:42"],
        suggestion="Use range(n+1)",
        reviewer="claude",
    )
    f1 = Finding(**base)
    f2 = Finding(**base)
    assert f1.dedupe_id() == f2.dedupe_id()


def test_dedupe_id_ignores_reviewer_and_confidence():
    base = dict(
        category="correctness",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        summary="Off-by-one in loop",
        detail="Detail text",
        evidence=["src/foo.py:42"],
        suggestion="Use range(n+1)",
    )
    f_claude = Finding(reviewer="claude", **base)
    f_codex = Finding(reviewer="codex", **{**base, "confidence": Confidence.MEDIUM})
    assert f_claude.dedupe_id() == f_codex.dedupe_id()


def test_dedupe_id_changes_with_evidence():
    base = dict(
        category="correctness",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        summary="x",
        detail="y",
        suggestion="z",
        reviewer="claude",
    )
    f1 = Finding(evidence=["a.py:1"], **base)
    f2 = Finding(evidence=["b.py:1"], **base)
    assert f1.dedupe_id() != f2.dedupe_id()


def test_findings_merge_dedupes_across_reviewers():
    a = Finding(
        category="correctness",
        severity=Severity.HIGH,
        confidence=Confidence.HIGH,
        summary="Off-by-one",
        detail="d",
        evidence=["x.py:1"],
        suggestion="s",
        reviewer="claude",
    )
    b = Finding(
        category="correctness",
        severity=Severity.HIGH,
        confidence=Confidence.MEDIUM,
        summary="Off-by-one",
        detail="d",
        evidence=["x.py:1"],
        suggestion="s",
        reviewer="codex",
    )
    merged = Findings.merge([a], [b])
    assert len(merged) == 1
    assert set(merged[0].reviewers) == {"claude", "codex"}


def test_findings_merge_keeps_distinct():
    a = Finding(
        category="correctness", severity=Severity.HIGH, confidence=Confidence.HIGH,
        summary="A", detail="d", evidence=["x.py:1"], suggestion="s", reviewer="claude",
    )
    b = Finding(
        category="security", severity=Severity.MEDIUM, confidence=Confidence.HIGH,
        summary="B", detail="d", evidence=["y.py:2"], suggestion="s", reviewer="codex",
    )
    merged = Findings.merge([a], [b])
    assert len(merged) == 2
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `uv run python -m pytest tests/core/test_findings.py -v`
Expected: ImportError on `orca.core.findings`.

- [ ] **Step 3: Implement Finding, Severity, Confidence**

```python
# src/orca/core/findings.py
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class Severity(str, Enum):
    BLOCKER = "blocker"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NIT = "nit"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class Finding:
    category: str
    severity: Severity
    confidence: Confidence
    summary: str
    detail: str
    evidence: list[str]
    suggestion: str
    reviewer: str
    reviewers: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if not self.reviewers:
            object.__setattr__(self, "reviewers", (self.reviewer,))

    def dedupe_id(self) -> str:
        payload = {
            "category": self.category,
            "severity": self.severity.value,
            "summary": self.summary.strip().lower(),
            "evidence": sorted(self.evidence),
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return digest[:16]

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.dedupe_id(),
            "category": self.category,
            "severity": self.severity.value,
            "confidence": self.confidence.value,
            "summary": self.summary,
            "detail": self.detail,
            "evidence": list(self.evidence),
            "suggestion": self.suggestion,
            "reviewer": self.reviewer,
            "reviewers": list(self.reviewers),
        }


class Findings(list):
    @staticmethod
    def merge(*groups: Iterable[Finding]) -> "Findings":
        by_id: dict[str, Finding] = {}
        for group in groups:
            for f in group:
                key = f.dedupe_id()
                if key in by_id:
                    existing = by_id[key]
                    combined = tuple(sorted(set(existing.reviewers) | set(f.reviewers)))
                    by_id[key] = Finding(
                        category=existing.category,
                        severity=existing.severity,
                        confidence=existing.confidence,
                        summary=existing.summary,
                        detail=existing.detail,
                        evidence=existing.evidence,
                        suggestion=existing.suggestion,
                        reviewer=existing.reviewer,
                        reviewers=combined,
                    )
                else:
                    by_id[key] = f
        return Findings(by_id.values())

    def to_json(self) -> list[dict[str, Any]]:
        return [f.to_json() for f in self]
```

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run python -m pytest tests/core/test_findings.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/findings.py tests/core/test_findings.py
git commit -m "feat(core): add Finding/Findings with stable dedupe id"
```

---

### Task 3: ReviewBundle dataclass

**Why:** every reviewer takes a bundle. Capability core builds it from CLI args; reviewers consume it.

**Files:**
- Create: `src/orca/core/bundle.py`
- Create: `tests/core/test_bundle.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_bundle.py
from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.bundle import ReviewBundle, BundleError, build_bundle


def test_build_bundle_from_paths(tmp_path: Path):
    f1 = tmp_path / "a.py"
    f1.write_text("print('a')\n")
    f2 = tmp_path / "b.py"
    f2.write_text("print('b')\n")

    bundle = build_bundle(
        kind="diff",
        target=[str(f1), str(f2)],
        feature_id="001-foo",
        criteria=["correctness"],
        context=[],
    )
    assert bundle.kind == "diff"
    assert bundle.feature_id == "001-foo"
    assert len(bundle.target_paths) == 2
    assert bundle.criteria == ("correctness",)


def test_build_bundle_rejects_unknown_kind(tmp_path: Path):
    with pytest.raises(BundleError, match="unknown kind"):
        build_bundle(kind="banana", target=[], feature_id=None, criteria=[], context=[])


def test_build_bundle_rejects_missing_path(tmp_path: Path):
    with pytest.raises(BundleError, match="not found"):
        build_bundle(
            kind="spec",
            target=[str(tmp_path / "nope.md")],
            feature_id=None,
            criteria=[],
            context=[],
        )


def test_bundle_hash_stable_across_calls(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("print('a')\n")
    b1 = build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])
    b2 = build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])
    assert b1.bundle_hash == b2.bundle_hash


def test_bundle_hash_changes_with_content(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("v1\n")
    b1 = build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])
    f.write_text("v2\n")
    b2 = build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])
    assert b1.bundle_hash != b2.bundle_hash
```

- [ ] **Step 2: Run tests, verify fail**

Run: `uv run python -m pytest tests/core/test_bundle.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement bundle**

```python
# src/orca/core/bundle.py
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


VALID_KINDS = {"spec", "diff", "pr", "claim-output"}


class BundleError(Exception):
    pass


@dataclass(frozen=True)
class ReviewBundle:
    kind: str
    target_paths: tuple[Path, ...]
    feature_id: str | None
    criteria: tuple[str, ...]
    context_paths: tuple[Path, ...]
    bundle_hash: str

    def render_text(self) -> str:
        chunks: list[str] = []
        for p in self.target_paths:
            chunks.append(f"### {p}\n{p.read_text()}")
        return "\n\n".join(chunks)


def build_bundle(
    *,
    kind: str,
    target: Iterable[str],
    feature_id: str | None,
    criteria: Iterable[str],
    context: Iterable[str],
) -> ReviewBundle:
    if kind not in VALID_KINDS:
        raise BundleError(f"unknown kind: {kind}; expected one of {sorted(VALID_KINDS)}")

    target_paths = tuple(Path(p) for p in target)
    for p in target_paths:
        if not p.exists():
            raise BundleError(f"target not found: {p}")

    context_paths = tuple(Path(p) for p in context)
    for p in context_paths:
        if not p.exists():
            raise BundleError(f"context not found: {p}")

    h = hashlib.sha256()
    h.update(kind.encode())
    h.update(b"|")
    h.update((feature_id or "").encode())
    h.update(b"|")
    for p in target_paths:
        h.update(str(p).encode())
        h.update(b":")
        h.update(p.read_bytes())
        h.update(b"|")
    for p in context_paths:
        h.update(str(p).encode())
        h.update(b":")
        h.update(p.read_bytes())
        h.update(b"|")
    for c in criteria:
        h.update(c.encode())
        h.update(b"|")
    bundle_hash = h.hexdigest()[:32]

    return ReviewBundle(
        kind=kind,
        target_paths=target_paths,
        feature_id=feature_id,
        criteria=tuple(criteria),
        context_paths=context_paths,
        bundle_hash=bundle_hash,
    )
```

- [ ] **Step 4: Run tests, verify pass**

Run: `uv run python -m pytest tests/core/test_bundle.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/bundle.py tests/core/test_bundle.py
git commit -m "feat(core): add ReviewBundle and build_bundle helper"
```

---

### Task 4: Reviewer protocol + FixtureReviewer

**Why:** every reviewer is interchangeable. Defining the protocol + a fixture-backed reviewer lets us test downstream code (cross combiner, capability) without LLM calls.

**Files:**
- Create: `src/orca/core/reviewers/__init__.py`
- Create: `src/orca/core/reviewers/base.py`
- Create: `src/orca/core/reviewers/fixtures.py`
- Create: `tests/core/reviewers/__init__.py`
- Create: `tests/core/reviewers/test_fixture_reviewer.py`
- Create: `tests/fixtures/reviewers/scenarios/simple_diff.json`

- [ ] **Step 1: Write fixture file**

```json
// tests/fixtures/reviewers/scenarios/simple_diff.json
{
  "reviewer": "claude",
  "raw_findings": [
    {
      "category": "correctness",
      "severity": "high",
      "confidence": "high",
      "summary": "Off-by-one in loop",
      "detail": "range(n) skips the last element when iterating inclusively.",
      "evidence": ["src/foo.py:42"],
      "suggestion": "Use range(n+1)"
    }
  ]
}
```

- [ ] **Step 2: Write failing tests**

```python
# tests/core/reviewers/test_fixture_reviewer.py
from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.bundle import build_bundle
from orca.core.reviewers.base import ReviewerError
from orca.core.reviewers.fixtures import FixtureReviewer


FIXTURE_ROOT = Path(__file__).parent.parent.parent / "fixtures" / "reviewers" / "scenarios"


def _bundle(tmp_path: Path):
    f = tmp_path / "foo.py"
    f.write_text("for i in range(n): pass\n")
    return build_bundle(
        kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[],
    )


def test_fixture_reviewer_replays_recorded_findings(tmp_path):
    reviewer = FixtureReviewer(scenario=FIXTURE_ROOT / "simple_diff.json")
    raw = reviewer.review(_bundle(tmp_path), prompt="any")
    assert raw.reviewer == "claude"
    assert len(raw.findings) == 1
    assert raw.findings[0]["summary"] == "Off-by-one in loop"


def test_fixture_reviewer_missing_file_errors(tmp_path):
    reviewer = FixtureReviewer(scenario=tmp_path / "missing.json")
    with pytest.raises(ReviewerError, match="fixture not found"):
        reviewer.review(_bundle(tmp_path), prompt="any")


def test_fixture_reviewer_name_property(tmp_path):
    reviewer = FixtureReviewer(scenario=FIXTURE_ROOT / "simple_diff.json", name="claude")
    assert reviewer.name == "claude"
```

- [ ] **Step 3: Run, verify fail**

Run: `uv run python -m pytest tests/core/reviewers/test_fixture_reviewer.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement base + fixture reviewer**

```python
# src/orca/core/reviewers/base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from orca.core.bundle import ReviewBundle


class ReviewerError(Exception):
    """Raised by a reviewer when its backend fails. Caller wraps in Result."""

    def __init__(self, message: str, *, retryable: bool = False, underlying: str | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.underlying = underlying


@dataclass(frozen=True)
class RawFindings:
    reviewer: str
    findings: list[dict[str, Any]]
    metadata: dict[str, Any]


class Reviewer(Protocol):
    name: str

    def review(self, bundle: ReviewBundle, prompt: str) -> RawFindings: ...
```

```python
# src/orca/core/reviewers/fixtures.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orca.core.bundle import ReviewBundle
from orca.core.reviewers.base import RawFindings, Reviewer, ReviewerError


class FixtureReviewer(Reviewer):
    def __init__(self, *, scenario: Path, name: str | None = None):
        self.scenario = Path(scenario)
        self._explicit_name = name

    @property
    def name(self) -> str:
        if self._explicit_name is not None:
            return self._explicit_name
        return self._load().get("reviewer", "fixture")

    def _load(self) -> dict[str, Any]:
        if not self.scenario.exists():
            raise ReviewerError(f"fixture not found: {self.scenario}")
        return json.loads(self.scenario.read_text())

    def review(self, bundle: ReviewBundle, prompt: str) -> RawFindings:
        data = self._load()
        return RawFindings(
            reviewer=data.get("reviewer", "fixture"),
            findings=list(data.get("raw_findings", [])),
            metadata={"fixture": str(self.scenario), "bundle_hash": bundle.bundle_hash},
        )
```

```python
# src/orca/core/reviewers/__init__.py
from __future__ import annotations

from orca.core.reviewers.base import RawFindings, Reviewer, ReviewerError
from orca.core.reviewers.fixtures import FixtureReviewer

__all__ = ["RawFindings", "Reviewer", "ReviewerError", "FixtureReviewer"]
```

- [ ] **Step 5: Run, verify pass**

Run: `uv run python -m pytest tests/core/reviewers/test_fixture_reviewer.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/orca/core/reviewers/ tests/core/reviewers/__init__.py tests/core/reviewers/test_fixture_reviewer.py tests/fixtures/reviewers/scenarios/simple_diff.json
git commit -m "feat(core/reviewers): add Reviewer protocol and FixtureReviewer"
```

---

### Task 5: ClaudeReviewer (Anthropic SDK)

**Why:** the wedge needs a real reviewer. ClaudeReviewer is first because Anthropic SDK is already a project consideration. Tests use cassettes (recorded JSON), not live calls.

**Files:**
- Modify: `pyproject.toml` (add `anthropic>=0.40.0` dep)
- Create: `src/orca/core/reviewers/claude.py`
- Create: `tests/core/reviewers/test_claude.py`
- Create: `tests/fixtures/reviewers/claude/simple_review.json`

- [ ] **Step 1: Add anthropic dependency**

Edit `pyproject.toml`. Find the `[project] dependencies` array and append `"anthropic>=0.40.0"` and `"jsonschema>=4.0"`.

Run: `uv sync`
Expected: lock updates, install succeeds.

- [ ] **Step 2: Write recorded fixture**

```json
// tests/fixtures/reviewers/claude/simple_review.json
{
  "stop_reason": "end_turn",
  "content_text": "[{\"category\":\"correctness\",\"severity\":\"high\",\"confidence\":\"high\",\"summary\":\"Off-by-one in loop\",\"detail\":\"range(n) skips the last element.\",\"evidence\":[\"src/foo.py:42\"],\"suggestion\":\"Use range(n+1)\"}]",
  "usage": {"input_tokens": 120, "output_tokens": 80}
}
```

- [ ] **Step 3: Write failing tests**

```python
# tests/core/reviewers/test_claude.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from orca.core.bundle import build_bundle
from orca.core.reviewers.base import ReviewerError
from orca.core.reviewers.claude import ClaudeReviewer

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "reviewers" / "claude" / "simple_review.json"


def _bundle(tmp_path):
    f = tmp_path / "foo.py"
    f.write_text("for i in range(n): pass\n")
    return build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])


def _fake_response_from_fixture():
    data = json.loads(FIXTURE.read_text())
    block = MagicMock()
    block.type = "text"
    block.text = data["content_text"]
    response = MagicMock()
    response.content = [block]
    response.stop_reason = data["stop_reason"]
    response.usage = MagicMock(input_tokens=data["usage"]["input_tokens"], output_tokens=data["usage"]["output_tokens"])
    return response


def test_claude_reviewer_parses_findings(tmp_path):
    client = MagicMock()
    client.messages.create.return_value = _fake_response_from_fixture()
    reviewer = ClaudeReviewer(client=client, model="claude-sonnet-4-6")
    raw = reviewer.review(_bundle(tmp_path), prompt="Review this diff.")
    assert raw.reviewer == "claude"
    assert len(raw.findings) == 1
    assert raw.findings[0]["summary"] == "Off-by-one in loop"
    assert raw.metadata["model"] == "claude-sonnet-4-6"
    assert raw.metadata["stop_reason"] == "end_turn"


def test_claude_reviewer_invalid_json_response(tmp_path):
    client = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = "not json at all"
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "end_turn"
    response.usage = MagicMock(input_tokens=1, output_tokens=1)
    client.messages.create.return_value = response

    reviewer = ClaudeReviewer(client=client, model="claude-sonnet-4-6")
    with pytest.raises(ReviewerError, match="parse"):
        reviewer.review(_bundle(tmp_path), prompt="any")


def test_claude_reviewer_api_error_wrapped(tmp_path):
    client = MagicMock()
    client.messages.create.side_effect = RuntimeError("rate limited")

    reviewer = ClaudeReviewer(client=client, model="claude-sonnet-4-6")
    with pytest.raises(ReviewerError, match="rate limited"):
        reviewer.review(_bundle(tmp_path), prompt="any")


def test_claude_reviewer_name_default(tmp_path):
    reviewer = ClaudeReviewer(client=MagicMock(), model="claude-sonnet-4-6")
    assert reviewer.name == "claude"
```

- [ ] **Step 4: Run, verify fail**

Run: `uv run python -m pytest tests/core/reviewers/test_claude.py -v`
Expected: ImportError.

- [ ] **Step 5: Implement ClaudeReviewer**

```python
# src/orca/core/reviewers/claude.py
from __future__ import annotations

import json
import re
from typing import Any

from orca.core.bundle import ReviewBundle
from orca.core.reviewers.base import RawFindings, Reviewer, ReviewerError


_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)


class ClaudeReviewer(Reviewer):
    name = "claude"

    def __init__(self, *, client: Any, model: str = "claude-sonnet-4-6", max_tokens: int = 4096):
        self.client = client
        self.model = model
        self.max_tokens = max_tokens

    def review(self, bundle: ReviewBundle, prompt: str) -> RawFindings:
        user_text = f"{prompt}\n\n{bundle.render_text()}"
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": user_text}],
            )
        except Exception as exc:  # SDK raises various subclasses; treat all as backend failure
            raise ReviewerError(str(exc), retryable=True, underlying=type(exc).__name__) from exc

        text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
        findings = _parse_findings(text)
        return RawFindings(
            reviewer=self.name,
            findings=findings,
            metadata={
                "model": self.model,
                "stop_reason": response.stop_reason,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )


def _parse_findings(text: str) -> list[dict[str, Any]]:
    match = _JSON_ARRAY.search(text)
    if not match:
        raise ReviewerError(f"could not parse JSON array from response: {text[:200]}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ReviewerError(f"could not parse JSON: {exc}") from exc
    if not isinstance(data, list):
        raise ReviewerError("expected JSON array of findings")
    return data
```

- [ ] **Step 6: Run, verify pass**

Run: `uv run python -m pytest tests/core/reviewers/test_claude.py -v`
Expected: 4 PASS.

- [ ] **Step 7: Commit**

```bash
git add src/orca/core/reviewers/claude.py tests/core/reviewers/test_claude.py tests/fixtures/reviewers/claude/simple_review.json pyproject.toml uv.lock
git commit -m "feat(core/reviewers): add ClaudeReviewer with parse + error wrapping"
```

---

### Task 6: CodexReviewer (Codex CLI shellout)

**Why:** the cross-agent claim depends on the second backend existing. Codex CLI is the project's other agent; shelling out keeps orca decoupled from any specific Codex Python SDK.

**Files:**
- Create: `src/orca/core/reviewers/codex.py`
- Create: `tests/core/reviewers/test_codex.py`
- Create: `tests/fixtures/reviewers/codex/simple_review.json`

- [ ] **Step 1: Write fixture**

```json
// tests/fixtures/reviewers/codex/simple_review.json
{
  "stdout": "[{\"category\":\"correctness\",\"severity\":\"medium\",\"confidence\":\"high\",\"summary\":\"Off-by-one in loop\",\"detail\":\"Use range(n+1).\",\"evidence\":[\"src/foo.py:42\"],\"suggestion\":\"range(n+1)\"}]",
  "stderr": "",
  "returncode": 0
}
```

- [ ] **Step 2: Write failing tests**

```python
# tests/core/reviewers/test_codex.py
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from orca.core.bundle import build_bundle
from orca.core.reviewers.base import ReviewerError
from orca.core.reviewers.codex import CodexReviewer

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "reviewers" / "codex" / "simple_review.json"


def _bundle(tmp_path):
    f = tmp_path / "foo.py"
    f.write_text("for i in range(n): pass\n")
    return build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])


def _fake_run(*, stdout: str, stderr: str = "", returncode: int = 0):
    completed = MagicMock()
    completed.stdout = stdout
    completed.stderr = stderr
    completed.returncode = returncode
    return completed


def test_codex_reviewer_parses_stdout(tmp_path):
    fixture = json.loads(FIXTURE.read_text())
    with patch("orca.core.reviewers.codex.subprocess.run", return_value=_fake_run(**fixture)):
        reviewer = CodexReviewer(binary="codex")
        raw = reviewer.review(_bundle(tmp_path), prompt="review")
    assert raw.reviewer == "codex"
    assert len(raw.findings) == 1
    assert raw.findings[0]["severity"] == "medium"


def test_codex_reviewer_nonzero_exit(tmp_path):
    with patch(
        "orca.core.reviewers.codex.subprocess.run",
        return_value=_fake_run(stdout="", stderr="boom", returncode=2),
    ):
        reviewer = CodexReviewer(binary="codex")
        with pytest.raises(ReviewerError, match="exit 2"):
            reviewer.review(_bundle(tmp_path), prompt="review")


def test_codex_reviewer_binary_missing(tmp_path):
    with patch("orca.core.reviewers.codex.shutil.which", return_value=None):
        reviewer = CodexReviewer(binary="not-real-bin")
        with pytest.raises(ReviewerError, match="not found"):
            reviewer.review(_bundle(tmp_path), prompt="review")
```

- [ ] **Step 3: Run, verify fail**

Run: `uv run python -m pytest tests/core/reviewers/test_codex.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement CodexReviewer**

```python
# src/orca/core/reviewers/codex.py
from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any

from orca.core.bundle import ReviewBundle
from orca.core.reviewers.base import RawFindings, Reviewer, ReviewerError


_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)


class CodexReviewer(Reviewer):
    name = "codex"

    def __init__(self, *, binary: str = "codex", timeout_s: int = 120):
        self.binary = binary
        self.timeout_s = timeout_s

    def review(self, bundle: ReviewBundle, prompt: str) -> RawFindings:
        if shutil.which(self.binary) is None:
            raise ReviewerError(f"codex binary not found: {self.binary}")

        user_text = f"{prompt}\n\n{bundle.render_text()}"
        try:
            completed = subprocess.run(
                [self.binary, "exec", "--json", "--quiet"],
                input=user_text,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise ReviewerError(f"codex timeout after {self.timeout_s}s", retryable=True) from exc

        if completed.returncode != 0:
            raise ReviewerError(
                f"codex exit {completed.returncode}: {completed.stderr.strip()}",
                retryable=False,
                underlying="nonzero_exit",
            )

        findings = _parse_findings(completed.stdout)
        return RawFindings(
            reviewer=self.name,
            findings=findings,
            metadata={"binary": self.binary, "stderr_len": len(completed.stderr)},
        )


def _parse_findings(text: str) -> list[dict[str, Any]]:
    match = _JSON_ARRAY.search(text)
    if not match:
        raise ReviewerError(f"could not parse JSON array from codex output: {text[:200]}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ReviewerError(f"could not parse codex JSON: {exc}") from exc
    if not isinstance(data, list):
        raise ReviewerError("expected JSON array from codex")
    return data
```

- [ ] **Step 5: Run, verify pass**

Run: `uv run python -m pytest tests/core/reviewers/test_codex.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Wire into reviewers package**

Edit `src/orca/core/reviewers/__init__.py`:

```python
from __future__ import annotations

from orca.core.reviewers.base import RawFindings, Reviewer, ReviewerError
from orca.core.reviewers.claude import ClaudeReviewer
from orca.core.reviewers.codex import CodexReviewer
from orca.core.reviewers.fixtures import FixtureReviewer

__all__ = [
    "RawFindings", "Reviewer", "ReviewerError",
    "ClaudeReviewer", "CodexReviewer", "FixtureReviewer",
]
```

- [ ] **Step 7: Commit**

```bash
git add src/orca/core/reviewers/codex.py src/orca/core/reviewers/__init__.py tests/core/reviewers/test_codex.py tests/fixtures/reviewers/codex/simple_review.json
git commit -m "feat(core/reviewers): add CodexReviewer with subprocess shellout"
```

---

### Task 7: CrossReviewer combiner with partial-success semantics

**Why:** the cross-mode claim — `reviewer=cross` returns merged findings even if one backend fails. Stable dedupe across reviewers is what makes this useful.

**Files:**
- Create: `src/orca/core/reviewers/cross.py`
- Create: `tests/core/reviewers/test_cross.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/reviewers/test_cross.py
from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.bundle import build_bundle
from orca.core.reviewers.base import RawFindings, ReviewerError
from orca.core.reviewers.cross import CrossReviewer, CrossResult


class _StubReviewer:
    def __init__(self, name: str, *, raise_error: bool = False, findings: list[dict] | None = None):
        self.name = name
        self._raise = raise_error
        self._findings = findings if findings is not None else []

    def review(self, bundle, prompt):
        if self._raise:
            raise ReviewerError(f"{self.name} failed", retryable=True)
        return RawFindings(reviewer=self.name, findings=self._findings, metadata={})


def _bundle(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("pass\n")
    return build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])


def test_cross_both_succeed_merges_findings(tmp_path):
    a_finding = {
        "category": "correctness", "severity": "high", "confidence": "high",
        "summary": "Off-by-one", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s",
    }
    b_finding = {
        "category": "security", "severity": "medium", "confidence": "high",
        "summary": "Unsafe eval", "detail": "d", "evidence": ["y.py:2"], "suggestion": "s",
    }
    cross = CrossReviewer(reviewers=[_StubReviewer("claude", findings=[a_finding]),
                                      _StubReviewer("codex", findings=[b_finding])])
    result = cross.review(_bundle(tmp_path), prompt="x")
    assert result.partial is False
    assert result.missing_reviewer is None
    assert len(result.findings) == 2
    assert {f.reviewer for f in result.findings} == {"claude", "codex"}


def test_cross_dedupes_overlap(tmp_path):
    same = {
        "category": "correctness", "severity": "high", "confidence": "high",
        "summary": "Off-by-one", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s",
    }
    cross = CrossReviewer(reviewers=[_StubReviewer("claude", findings=[same]),
                                      _StubReviewer("codex", findings=[same])])
    result = cross.review(_bundle(tmp_path), prompt="x")
    assert len(result.findings) == 1
    assert set(result.findings[0].reviewers) == {"claude", "codex"}


def test_cross_partial_when_one_fails(tmp_path):
    f = {"category": "c", "severity": "high", "confidence": "high",
         "summary": "Z", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s"}
    cross = CrossReviewer(reviewers=[_StubReviewer("claude", findings=[f]),
                                      _StubReviewer("codex", raise_error=True)])
    result = cross.review(_bundle(tmp_path), prompt="x")
    assert result.partial is True
    assert result.missing_reviewer == "codex"
    assert len(result.findings) == 1


def test_cross_all_fail_raises(tmp_path):
    cross = CrossReviewer(reviewers=[_StubReviewer("claude", raise_error=True),
                                      _StubReviewer("codex", raise_error=True)])
    with pytest.raises(ReviewerError, match="all reviewers failed"):
        cross.review(_bundle(tmp_path), prompt="x")
```

- [ ] **Step 2: Run, verify fail**

Run: `uv run python -m pytest tests/core/reviewers/test_cross.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement CrossReviewer**

```python
# src/orca/core/reviewers/cross.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from orca.core.bundle import ReviewBundle
from orca.core.findings import Confidence, Finding, Findings, Severity
from orca.core.reviewers.base import Reviewer, ReviewerError


@dataclass(frozen=True)
class CrossResult:
    findings: Findings
    partial: bool
    missing_reviewer: str | None
    reviewer_metadata: dict


class CrossReviewer:
    name = "cross"

    def __init__(self, *, reviewers: Sequence[Reviewer]):
        if len(reviewers) < 2:
            raise ValueError("CrossReviewer requires at least 2 reviewers")
        self.reviewers = list(reviewers)

    def review(self, bundle: ReviewBundle, prompt: str) -> CrossResult:
        results: list[Finding] = []
        per_reviewer_findings: list[list[Finding]] = []
        failures: list[tuple[str, ReviewerError]] = []
        metadata: dict[str, dict] = {}

        for reviewer in self.reviewers:
            try:
                raw = reviewer.review(bundle, prompt)
            except ReviewerError as exc:
                failures.append((reviewer.name, exc))
                continue
            metadata[reviewer.name] = raw.metadata
            findings = [_to_finding(f, reviewer.name) for f in raw.findings]
            per_reviewer_findings.append(findings)

        if not per_reviewer_findings:
            messages = "; ".join(f"{name}: {err}" for name, err in failures)
            raise ReviewerError(f"all reviewers failed: {messages}")

        merged = Findings.merge(*per_reviewer_findings)
        partial = len(failures) > 0
        missing = failures[0][0] if partial else None

        return CrossResult(
            findings=merged,
            partial=partial,
            missing_reviewer=missing,
            reviewer_metadata=metadata,
        )


def _to_finding(raw: dict, reviewer_name: str) -> Finding:
    return Finding(
        category=raw["category"],
        severity=Severity(raw["severity"]),
        confidence=Confidence(raw["confidence"]),
        summary=raw["summary"],
        detail=raw["detail"],
        evidence=list(raw.get("evidence", [])),
        suggestion=raw.get("suggestion", ""),
        reviewer=reviewer_name,
    )
```

- [ ] **Step 4: Run, verify pass**

Run: `uv run python -m pytest tests/core/reviewers/test_cross.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/reviewers/cross.py tests/core/reviewers/test_cross.py
git commit -m "feat(core/reviewers): add CrossReviewer with partial-success merge"
```

---

### Task 8: cross_agent_review capability

**Why:** the wedge. Wires bundle + reviewer + findings into a single capability function returning `Result[CrossAgentReviewResult, Error]`.

**Files:**
- Create: `src/orca/capabilities/__init__.py`
- Create: `src/orca/capabilities/cross_agent_review.py`
- Create: `tests/capabilities/__init__.py`
- Create: `tests/capabilities/test_cross_agent_review.py`
- Create: `docs/capabilities/cross-agent-review/schema/input.json`
- Create: `docs/capabilities/cross-agent-review/schema/output.json`
- Create: `docs/capabilities/cross-agent-review/README.md`

- [ ] **Step 1: Write input schema**

```json
// docs/capabilities/cross-agent-review/schema/input.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "cross-agent-review input",
  "type": "object",
  "required": ["kind", "target", "reviewer"],
  "properties": {
    "kind": {"enum": ["spec", "diff", "pr", "claim-output"]},
    "target": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "feature_id": {"type": ["string", "null"]},
    "reviewer": {"enum": ["claude", "codex", "cross"]},
    "criteria": {"type": "array", "items": {"type": "string"}},
    "context": {"type": "array", "items": {"type": "string"}}
  },
  "additionalProperties": false
}
```

- [ ] **Step 2: Write output schema**

```json
// docs/capabilities/cross-agent-review/schema/output.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "cross-agent-review output",
  "type": "object",
  "required": ["findings", "partial", "reviewer_metadata"],
  "properties": {
    "findings": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "category", "severity", "confidence", "summary", "detail", "evidence", "suggestion", "reviewer", "reviewers"],
        "properties": {
          "id": {"type": "string", "minLength": 16, "maxLength": 16},
          "category": {"type": "string"},
          "severity": {"enum": ["blocker", "high", "medium", "low", "nit"]},
          "confidence": {"enum": ["high", "medium", "low"]},
          "summary": {"type": "string"},
          "detail": {"type": "string"},
          "evidence": {"type": "array", "items": {"type": "string"}},
          "suggestion": {"type": "string"},
          "reviewer": {"type": "string"},
          "reviewers": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "partial": {"type": "boolean"},
    "missing_reviewer": {"type": ["string", "null"]},
    "reviewer_metadata": {"type": "object"}
  }
}
```

- [ ] **Step 3: Write README**

```markdown
// docs/capabilities/cross-agent-review/README.md
# cross-agent-review

Bundles a review subject (spec, diff, pr, or claim-output), dispatches to one or more reviewer backends (claude, codex, or cross), and returns structured findings with stable dedupe IDs.

## Input
See `schema/input.json`.

## Output
See `schema/output.json`. Findings have stable 16-char `id` derived from `category`, `severity`, normalized `summary`, and sorted `evidence`. Identical findings from multiple reviewers merge by `id` with combined `reviewers[]`.

## CLI
`orca-cli cross-agent-review --kind diff --target src/foo.py --reviewer cross --feature-id 001-foo`

## Library
`from orca.capabilities.cross_agent_review import cross_agent_review, CrossAgentReviewInput`
```

- [ ] **Step 4: Write failing tests**

```python
# tests/capabilities/test_cross_agent_review.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orca.core.bundle import build_bundle
from orca.core.errors import ErrorKind
from orca.core.reviewers.base import RawFindings, ReviewerError
from orca.capabilities.cross_agent_review import (
    CrossAgentReviewInput,
    cross_agent_review,
)


class _StubReviewer:
    def __init__(self, name: str, *, findings=None, raise_error: bool = False):
        self.name = name
        self._findings = findings or []
        self._raise = raise_error

    def review(self, bundle, prompt):
        if self._raise:
            raise ReviewerError(f"{self.name} failed")
        return RawFindings(reviewer=self.name, findings=self._findings, metadata={})


def _input(tmp_path, **overrides):
    f = tmp_path / "x.py"
    f.write_text("pass\n")
    base = dict(
        kind="diff", target=[str(f)], feature_id=None,
        reviewer="cross", criteria=[], context=[], prompt="review",
    )
    base.update(overrides)
    return CrossAgentReviewInput(**base)


def test_cross_agent_review_returns_ok(tmp_path):
    finding = {
        "category": "correctness", "severity": "high", "confidence": "high",
        "summary": "Off-by-one", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s",
    }
    result = cross_agent_review(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", findings=[finding]),
                   "codex": _StubReviewer("codex", findings=[finding])},
    )
    assert result.ok
    assert len(result.value["findings"]) == 1
    assert result.value["partial"] is False


def test_cross_agent_review_partial_when_one_fails(tmp_path):
    finding = {
        "category": "c", "severity": "high", "confidence": "high",
        "summary": "Z", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s",
    }
    result = cross_agent_review(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", findings=[finding]),
                   "codex": _StubReviewer("codex", raise_error=True)},
    )
    assert result.ok
    assert result.value["partial"] is True
    assert result.value["missing_reviewer"] == "codex"


def test_cross_agent_review_all_fail_returns_backend_failure(tmp_path):
    result = cross_agent_review(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", raise_error=True),
                   "codex": _StubReviewer("codex", raise_error=True)},
    )
    assert not result.ok
    assert result.error.kind == ErrorKind.BACKEND_FAILURE


def test_cross_agent_review_invalid_kind(tmp_path):
    inp = _input(tmp_path, kind="bogus")
    result = cross_agent_review(inp, reviewers={"claude": _StubReviewer("claude")})
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_cross_agent_review_single_reviewer_mode(tmp_path):
    finding = {
        "category": "c", "severity": "high", "confidence": "high",
        "summary": "Z", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s",
    }
    inp = _input(tmp_path, reviewer="claude")
    result = cross_agent_review(
        inp, reviewers={"claude": _StubReviewer("claude", findings=[finding])},
    )
    assert result.ok
    assert result.value["partial"] is False
    assert len(result.value["findings"]) == 1


def test_cross_agent_review_output_validates_against_schema(tmp_path):
    pytest.importorskip("jsonschema")
    import jsonschema

    schema_path = Path(__file__).parent.parent.parent / "docs" / "capabilities" / "cross-agent-review" / "schema" / "output.json"
    schema = json.loads(schema_path.read_text())

    finding = {
        "category": "c", "severity": "high", "confidence": "high",
        "summary": "Z", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s",
    }
    result = cross_agent_review(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", findings=[finding]),
                   "codex": _StubReviewer("codex", findings=[finding])},
    )
    assert result.ok
    jsonschema.validate(result.value, schema)
```

- [ ] **Step 5: Run, verify fail**

Run: `uv run python -m pytest tests/capabilities/test_cross_agent_review.py -v`
Expected: ImportError.

- [ ] **Step 6: Implement capability**

```python
# src/orca/capabilities/__init__.py
"""Orca v1 capability catalog. Each capability is a pure function returning Result."""
```

```python
# src/orca/capabilities/cross_agent_review.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from orca.core.bundle import BundleError, build_bundle
from orca.core.errors import Error, ErrorKind
from orca.core.findings import Confidence, Finding, Findings, Severity
from orca.core.result import Err, Ok, Result
from orca.core.reviewers.base import RawFindings, Reviewer, ReviewerError
from orca.core.reviewers.cross import CrossReviewer

VERSION = "0.1.0"

_VALID_REVIEWERS = {"claude", "codex", "cross"}


@dataclass(frozen=True)
class CrossAgentReviewInput:
    kind: str
    target: list[str]
    reviewer: str
    feature_id: str | None = None
    criteria: list[str] = field(default_factory=list)
    context: list[str] = field(default_factory=list)
    prompt: str = "Review the following content. Return a JSON array of findings."


def cross_agent_review(
    inp: CrossAgentReviewInput,
    *,
    reviewers: Mapping[str, Reviewer],
) -> Result[dict, Error]:
    if inp.reviewer not in _VALID_REVIEWERS:
        return Err(Error(kind=ErrorKind.INPUT_INVALID, message=f"unknown reviewer: {inp.reviewer}"))

    try:
        bundle = build_bundle(
            kind=inp.kind,
            target=inp.target,
            feature_id=inp.feature_id,
            criteria=inp.criteria,
            context=inp.context,
        )
    except BundleError as exc:
        return Err(Error(kind=ErrorKind.INPUT_INVALID, message=str(exc)))

    if inp.reviewer == "cross":
        try:
            cross = CrossReviewer(reviewers=[reviewers["claude"], reviewers["codex"]])
        except KeyError as exc:
            return Err(Error(kind=ErrorKind.INPUT_INVALID, message=f"missing reviewer for cross mode: {exc}"))
        try:
            cross_result = cross.review(bundle, inp.prompt)
        except ReviewerError as exc:
            return Err(Error(kind=ErrorKind.BACKEND_FAILURE, message=str(exc)))
        return Ok(_render_cross(cross_result))

    if inp.reviewer not in reviewers:
        return Err(Error(kind=ErrorKind.INPUT_INVALID, message=f"reviewer not configured: {inp.reviewer}"))

    try:
        raw = reviewers[inp.reviewer].review(bundle, inp.prompt)
    except ReviewerError as exc:
        return Err(Error(kind=ErrorKind.BACKEND_FAILURE, message=str(exc)))

    findings = Findings([_finding_from_raw(f, raw.reviewer) for f in raw.findings])
    return Ok({
        "findings": findings.to_json(),
        "partial": False,
        "missing_reviewer": None,
        "reviewer_metadata": {raw.reviewer: raw.metadata},
    })


def _render_cross(result) -> dict:
    return {
        "findings": result.findings.to_json(),
        "partial": result.partial,
        "missing_reviewer": result.missing_reviewer,
        "reviewer_metadata": result.reviewer_metadata,
    }


def _finding_from_raw(raw: dict, reviewer_name: str) -> Finding:
    return Finding(
        category=raw["category"],
        severity=Severity(raw["severity"]),
        confidence=Confidence(raw["confidence"]),
        summary=raw["summary"],
        detail=raw["detail"],
        evidence=list(raw.get("evidence", [])),
        suggestion=raw.get("suggestion", ""),
        reviewer=reviewer_name,
    )
```

- [ ] **Step 7: Run, verify pass**

Run: `uv run python -m pytest tests/capabilities/test_cross_agent_review.py -v`
Expected: 6 PASS.

- [ ] **Step 8: Commit**

```bash
git add src/orca/capabilities/__init__.py src/orca/capabilities/cross_agent_review.py tests/capabilities/__init__.py tests/capabilities/test_cross_agent_review.py docs/capabilities/cross-agent-review/
git commit -m "feat(capabilities): add cross-agent-review with schema and tests"
```

---

### Task 9: Python CLI with cross-agent-review subcommand

**Why:** the canonical surface. CLI parses JSON-or-args input, calls the capability, prints the Result envelope as JSON, exits with the right code.

**Files:**
- Create: `src/orca/python_cli.py`
- Modify: `pyproject.toml` (add `[project.scripts] orca-cli`)
- Create: `tests/cli/__init__.py`
- Create: `tests/cli/test_python_cli.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/cli/test_python_cli.py
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from orca.python_cli import main as cli_main


def test_cli_lists_capabilities(capsys):
    rc = cli_main(["--list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "cross-agent-review" in out


def test_cli_unknown_capability_exits_3(capsys):
    rc = cli_main(["banana"])
    assert rc == 3


def test_cli_no_args_prints_help(capsys):
    rc = cli_main([])
    out = capsys.readouterr().out
    assert rc == 0 or rc == 2
    assert "orca-cli" in out or "usage" in out.lower()


def test_cli_cross_agent_review_with_fixture_reviewer(tmp_path, capsys, monkeypatch):
    target = tmp_path / "x.py"
    target.write_text("pass\n")

    fixture = tmp_path / "scenario.json"
    fixture.write_text(json.dumps({
        "reviewer": "claude",
        "raw_findings": [
            {"category": "c", "severity": "high", "confidence": "high",
             "summary": "S", "detail": "d", "evidence": ["x.py:1"], "suggestion": "s"}
        ],
    }))

    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CLAUDE", str(fixture))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CODEX", str(fixture))

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "claude",
        "--json",
    ])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["metadata"]["capability"] == "cross-agent-review"
    assert len(payload["result"]["findings"]) == 1


def test_cli_invalid_input_exits_1_with_error_json(tmp_path, capsys, monkeypatch):
    fixture = tmp_path / "scenario.json"
    fixture.write_text(json.dumps({"reviewer": "claude", "raw_findings": []}))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CLAUDE", str(fixture))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CODEX", str(fixture))

    rc = cli_main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(tmp_path / "missing.py"),
        "--reviewer", "claude",
        "--json",
    ])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 1
    assert payload["ok"] is False
    assert payload["error"]["kind"] == "input_invalid"
```

- [ ] **Step 2: Run, verify fail**

Run: `uv run python -m pytest tests/cli/test_python_cli.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement CLI**

```python
# src/orca/python_cli.py
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Sequence

from orca.capabilities.cross_agent_review import (
    VERSION as CROSS_AGENT_REVIEW_VERSION,
    CrossAgentReviewInput,
    cross_agent_review,
)
from orca.core.errors import Error, ErrorKind
from orca.core.reviewers.claude import ClaudeReviewer
from orca.core.reviewers.codex import CodexReviewer
from orca.core.reviewers.fixtures import FixtureReviewer

CAPABILITIES = {
    "cross-agent-review": ("cross_agent_review", CROSS_AGENT_REVIEW_VERSION),
}


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]

    if not argv:
        _print_help()
        return 0

    if argv[0] in ("--list", "-l"):
        for name in CAPABILITIES:
            print(name)
        return 0

    if argv[0] in ("-h", "--help"):
        _print_help()
        return 0

    capability = argv[0]
    if capability not in CAPABILITIES:
        print(f"unknown capability: {capability}", file=sys.stderr)
        print(f"available: {', '.join(CAPABILITIES)}", file=sys.stderr)
        return 3

    if capability == "cross-agent-review":
        return _run_cross_agent_review(argv[1:])

    return 3


def _print_help() -> None:
    print("orca-cli — orca capability runner")
    print()
    print("Usage: orca-cli <capability> [options]")
    print()
    print("Capabilities:")
    for name in CAPABILITIES:
        print(f"  {name}")


def _run_cross_agent_review(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="orca-cli cross-agent-review")
    parser.add_argument("--kind", required=True)
    parser.add_argument("--target", action="append", required=True, default=[])
    parser.add_argument("--reviewer", default="cross")
    parser.add_argument("--feature-id", default=None)
    parser.add_argument("--criteria", action="append", default=[])
    parser.add_argument("--context", action="append", default=[])
    parser.add_argument("--prompt", default="Review the following content. Return a JSON array of findings.")
    parser.add_argument("--json", action="store_true", help="emit JSON envelope to stdout (default)")
    parser.add_argument("--pretty", action="store_true", help="emit human-readable summary instead of JSON")
    ns, unknown = parser.parse_known_args(args)

    if unknown:
        return _emit_envelope(
            envelope=_err_envelope("cross-agent-review", CROSS_AGENT_REVIEW_VERSION,
                                    ErrorKind.INPUT_INVALID, f"unknown args: {unknown}"),
            pretty=ns.pretty,
            exit_code=1,
        )

    inp = CrossAgentReviewInput(
        kind=ns.kind,
        target=ns.target,
        feature_id=ns.feature_id,
        reviewer=ns.reviewer,
        criteria=ns.criteria,
        context=ns.context,
        prompt=ns.prompt,
    )

    started = time.monotonic()
    reviewers = _load_reviewers()
    result = cross_agent_review(inp, reviewers=reviewers)
    duration_ms = int((time.monotonic() - started) * 1000)

    envelope = result.to_json(
        capability="cross-agent-review",
        version=CROSS_AGENT_REVIEW_VERSION,
        duration_ms=duration_ms,
    )
    exit_code = 0 if result.ok else 1
    return _emit_envelope(envelope=envelope, pretty=ns.pretty, exit_code=exit_code)


def _load_reviewers() -> dict:
    """Pick reviewer backends from env vars. Fixture overrides win for tests."""
    reviewers: dict = {}

    claude_fixture = os.environ.get("ORCA_FIXTURE_REVIEWER_CLAUDE")
    if claude_fixture:
        reviewers["claude"] = FixtureReviewer(scenario=Path(claude_fixture), name="claude")
    elif os.environ.get("ORCA_LIVE") == "1":
        try:
            import anthropic  # type: ignore
            reviewers["claude"] = ClaudeReviewer(client=anthropic.Anthropic())
        except ImportError:
            pass

    codex_fixture = os.environ.get("ORCA_FIXTURE_REVIEWER_CODEX")
    if codex_fixture:
        reviewers["codex"] = FixtureReviewer(scenario=Path(codex_fixture), name="codex")
    elif os.environ.get("ORCA_LIVE") == "1":
        reviewers["codex"] = CodexReviewer()

    return reviewers


def _err_envelope(capability: str, version: str, kind: ErrorKind, message: str) -> dict:
    return {
        "ok": False,
        "error": {"kind": kind.value, "message": message},
        "metadata": {"capability": capability, "version": version, "duration_ms": 0},
    }


def _emit_envelope(*, envelope: dict, pretty: bool, exit_code: int) -> int:
    if pretty:
        if envelope["ok"]:
            findings = envelope["result"].get("findings", [])
            print(f"OK ({len(findings)} findings)")
            for f in findings:
                print(f"  [{f['severity']}] {f['summary']} — {','.join(f['evidence'])}")
        else:
            print(f"ERROR ({envelope['error']['kind']}): {envelope['error']['message']}")
    else:
        print(json.dumps(envelope, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Wire script entry**

Edit `pyproject.toml`. Find the `[project.scripts]` table; add:

```toml
orca-cli = "orca.python_cli:main"
```

Run: `uv sync`
Expected: lock updates.

- [ ] **Step 5: Run tests, verify pass**

Run: `uv run python -m pytest tests/cli/test_python_cli.py -v`
Expected: 5 PASS.

- [ ] **Step 6: Smoke-test the script entry**

Run: `uv run orca-cli --list`
Expected output: `cross-agent-review` on stdout.

- [ ] **Step 7: Commit**

```bash
git add src/orca/python_cli.py tests/cli/__init__.py tests/cli/test_python_cli.py pyproject.toml uv.lock
git commit -m "feat(cli): add Python CLI with cross-agent-review subcommand"
```

---

### Task 9.5: Phase 2a verification gate

**Why:** Phase 2a wedge is complete. Run all Phase 2 tests, verify integration, before unlocking 2b.

- [ ] **Step 1: Full test pass**

Run: `uv run python -m pytest tests/core/ tests/capabilities/ tests/cli/ -v`
Expected: all green. Record count in commit message.

- [ ] **Step 2: Schema validation smoke**

```bash
uv run python -c "
import json, jsonschema
schema = json.load(open('docs/capabilities/cross-agent-review/schema/output.json'))
print('schema parses ok')
jsonschema.Draft7Validator.check_schema(schema)
print('schema is valid Draft 7')
"
```

Expected: both lines print.

- [ ] **Step 3: Fixture round-trip smoke via CLI**

```bash
mkdir -p /tmp/orca-smoke && echo "pass" > /tmp/orca-smoke/x.py
cat > /tmp/orca-smoke/fix.json <<'EOF'
{"reviewer":"claude","raw_findings":[{"category":"c","severity":"high","confidence":"high","summary":"S","detail":"d","evidence":["x.py:1"],"suggestion":"s"}]}
EOF
ORCA_FIXTURE_REVIEWER_CLAUDE=/tmp/orca-smoke/fix.json \
ORCA_FIXTURE_REVIEWER_CODEX=/tmp/orca-smoke/fix.json \
uv run orca-cli cross-agent-review --kind diff --target /tmp/orca-smoke/x.py --reviewer cross
```

Expected: JSON envelope with `"ok": true` and one finding.

- [ ] **Step 4: Tag the wedge**

```bash
git tag orca-v0.2.0a-wedge
```

(No push; this is a local milestone marker. Push only if user asks.)

---

## Phase 2b: Remaining 5 capabilities

### Task 10: worktree-overlap-check capability

**Why:** the easy win. Pure Python, no LLM. Validates the framework on a deterministic capability before LLM-heavy ones pile in.

**Files:**
- Create: `src/orca/capabilities/worktree_overlap_check.py`
- Create: `tests/capabilities/test_worktree_overlap_check.py`
- Create: `docs/capabilities/worktree-overlap-check/schema/input.json`
- Create: `docs/capabilities/worktree-overlap-check/schema/output.json`
- Create: `docs/capabilities/worktree-overlap-check/README.md`
- Modify: `src/orca/python_cli.py` (add subcommand routing)

- [ ] **Step 1: Write input schema**

```json
// docs/capabilities/worktree-overlap-check/schema/input.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["worktrees"],
  "properties": {
    "worktrees": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path"],
        "properties": {
          "path": {"type": "string"},
          "branch": {"type": "string"},
          "feature_id": {"type": "string"},
          "claimed_paths": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "proposed_writes": {"type": "array", "items": {"type": "string"}},
    "repo_root": {"type": "string"}
  }
}
```

- [ ] **Step 2: Write output schema**

```json
// docs/capabilities/worktree-overlap-check/schema/output.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["safe", "conflicts", "proposed_overlaps"],
  "properties": {
    "safe": {"type": "boolean"},
    "conflicts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "worktrees"],
        "properties": {
          "path": {"type": "string"},
          "worktrees": {"type": "array", "items": {"type": "string"}, "minItems": 2}
        }
      }
    },
    "proposed_overlaps": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "blocked_by"],
        "properties": {
          "path": {"type": "string"},
          "blocked_by": {"type": "string"}
        }
      }
    }
  }
}
```

- [ ] **Step 3: Write README**

```markdown
// docs/capabilities/worktree-overlap-check/README.md
# worktree-overlap-check

Detects path conflicts between active worktrees and against proposed writes. Pure Python; no git invocation, no LLM. Caller passes pre-collected worktree info.

## Use case
Perf-lab's `lease.sh` shells out here instead of reimplementing overlap detection. Returns `safe=false` when any two worktrees claim the same path, or when a `proposed_writes` entry is already claimed.

## Path matching
Exact-path equality or directory-prefix containment. `src/foo/` claims `src/foo/bar.py`.
```

- [ ] **Step 4: Write failing tests**

```python
# tests/capabilities/test_worktree_overlap_check.py
from __future__ import annotations

from orca.core.errors import ErrorKind
from orca.capabilities.worktree_overlap_check import (
    WorktreeOverlapInput,
    WorktreeInfo,
    worktree_overlap_check,
)


def _wt(path: str, *, claimed: list[str], branch: str = "feat", feature_id: str = "f") -> WorktreeInfo:
    return WorktreeInfo(path=path, branch=branch, feature_id=feature_id, claimed_paths=claimed)


def test_no_conflicts_safe_true():
    inp = WorktreeOverlapInput(worktrees=[
        _wt("/a", claimed=["src/foo/"]),
        _wt("/b", claimed=["src/bar/"]),
    ])
    result = worktree_overlap_check(inp)
    assert result.ok
    assert result.value["safe"] is True
    assert result.value["conflicts"] == []


def test_exact_path_conflict_detected():
    inp = WorktreeOverlapInput(worktrees=[
        _wt("/a", claimed=["src/foo.py"]),
        _wt("/b", claimed=["src/foo.py"]),
    ])
    result = worktree_overlap_check(inp)
    assert result.ok
    assert result.value["safe"] is False
    assert len(result.value["conflicts"]) == 1
    assert set(result.value["conflicts"][0]["worktrees"]) == {"/a", "/b"}


def test_directory_prefix_conflict_detected():
    inp = WorktreeOverlapInput(worktrees=[
        _wt("/a", claimed=["src/foo/"]),
        _wt("/b", claimed=["src/foo/bar.py"]),
    ])
    result = worktree_overlap_check(inp)
    assert result.ok
    assert result.value["safe"] is False
    assert len(result.value["conflicts"]) == 1


def test_proposed_overlap_detected():
    inp = WorktreeOverlapInput(
        worktrees=[_wt("/a", claimed=["src/foo/"])],
        proposed_writes=["src/foo/bar.py"],
    )
    result = worktree_overlap_check(inp)
    assert result.ok
    assert result.value["safe"] is False
    assert len(result.value["proposed_overlaps"]) == 1
    assert result.value["proposed_overlaps"][0]["blocked_by"] == "/a"


def test_empty_worktrees_safe():
    inp = WorktreeOverlapInput(worktrees=[])
    result = worktree_overlap_check(inp)
    assert result.ok
    assert result.value["safe"] is True


def test_invalid_path_in_claimed_returns_input_invalid():
    inp = WorktreeOverlapInput(worktrees=[_wt("/a", claimed=[""])])
    result = worktree_overlap_check(inp)
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID
```

- [ ] **Step 5: Run, verify fail**

Run: `uv run python -m pytest tests/capabilities/test_worktree_overlap_check.py -v`
Expected: ImportError.

- [ ] **Step 6: Implement capability**

```python
# src/orca/capabilities/worktree_overlap_check.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from orca.core.errors import Error, ErrorKind
from orca.core.result import Err, Ok, Result

VERSION = "0.1.0"


@dataclass(frozen=True)
class WorktreeInfo:
    path: str
    branch: str
    feature_id: str
    claimed_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorktreeOverlapInput:
    worktrees: list[WorktreeInfo]
    proposed_writes: list[str] = field(default_factory=list)
    repo_root: str | None = None


def worktree_overlap_check(inp: WorktreeOverlapInput) -> Result[dict, Error]:
    for wt in inp.worktrees:
        for p in wt.claimed_paths:
            if not p:
                return Err(Error(
                    kind=ErrorKind.INPUT_INVALID,
                    message=f"empty claimed path on worktree {wt.path}",
                ))

    conflicts: list[dict] = []
    for i, wt_a in enumerate(inp.worktrees):
        for wt_b in inp.worktrees[i + 1:]:
            for shared in _overlapping_paths(wt_a.claimed_paths, wt_b.claimed_paths):
                conflicts.append({"path": shared, "worktrees": [wt_a.path, wt_b.path]})

    proposed_overlaps: list[dict] = []
    for proposed in inp.proposed_writes:
        for wt in inp.worktrees:
            if _path_overlaps(proposed, wt.claimed_paths):
                proposed_overlaps.append({"path": proposed, "blocked_by": wt.path})
                break

    return Ok({
        "safe": not conflicts and not proposed_overlaps,
        "conflicts": conflicts,
        "proposed_overlaps": proposed_overlaps,
    })


def _overlapping_paths(a: list[str], b: list[str]) -> list[str]:
    out: list[str] = []
    for pa in a:
        for pb in b:
            if _paths_overlap(pa, pb):
                out.append(pa if len(pa) <= len(pb) else pb)
    return out


def _path_overlaps(target: str, claims: list[str]) -> bool:
    return any(_paths_overlap(target, c) for c in claims)


def _paths_overlap(a: str, b: str) -> bool:
    pa = PurePosixPath(a.rstrip("/"))
    pb = PurePosixPath(b.rstrip("/"))
    if pa == pb:
        return True
    try:
        pa.relative_to(pb)
        return True
    except ValueError:
        pass
    try:
        pb.relative_to(pa)
        return True
    except ValueError:
        pass
    return False
```

- [ ] **Step 7: Run, verify pass**

Run: `uv run python -m pytest tests/capabilities/test_worktree_overlap_check.py -v`
Expected: 6 PASS.

- [ ] **Step 8: Wire CLI subcommand**

Edit `src/orca/python_cli.py`. Add to `CAPABILITIES`:

```python
from orca.capabilities.worktree_overlap_check import (
    VERSION as WORKTREE_OVERLAP_VERSION,
    WorktreeOverlapInput,
    WorktreeInfo,
    worktree_overlap_check,
)

CAPABILITIES = {
    "cross-agent-review": ("cross_agent_review", CROSS_AGENT_REVIEW_VERSION),
    "worktree-overlap-check": ("worktree_overlap_check", WORKTREE_OVERLAP_VERSION),
}
```

In `main()`, route the new subcommand:

```python
    if capability == "cross-agent-review":
        return _run_cross_agent_review(argv[1:])
    if capability == "worktree-overlap-check":
        return _run_worktree_overlap_check(argv[1:])
    return 3
```

Add the runner. This capability takes JSON input from stdin (worktree lists are awkward as flat CLI flags):

```python
def _run_worktree_overlap_check(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="orca-cli worktree-overlap-check")
    parser.add_argument("--input", default="-", help="path to JSON input or '-' for stdin")
    parser.add_argument("--pretty", action="store_true")
    ns = parser.parse_args(args)

    started = time.monotonic()
    try:
        if ns.input == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(ns.input).read_text()
        data = json.loads(raw)
        inp = WorktreeOverlapInput(
            worktrees=[WorktreeInfo(**wt) for wt in data.get("worktrees", [])],
            proposed_writes=data.get("proposed_writes", []),
            repo_root=data.get("repo_root"),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        envelope = _err_envelope("worktree-overlap-check", WORKTREE_OVERLAP_VERSION,
                                  ErrorKind.INPUT_INVALID, f"input parse error: {exc}")
        return _emit_envelope(envelope=envelope, pretty=ns.pretty, exit_code=1)

    result = worktree_overlap_check(inp)
    duration_ms = int((time.monotonic() - started) * 1000)
    envelope = result.to_json(
        capability="worktree-overlap-check",
        version=WORKTREE_OVERLAP_VERSION,
        duration_ms=duration_ms,
    )
    return _emit_envelope(envelope=envelope, pretty=ns.pretty, exit_code=0 if result.ok else 1)
```

- [ ] **Step 9: Add CLI test for worktree-overlap-check**

Append to `tests/cli/test_python_cli.py`:

```python
def test_cli_worktree_overlap_check_via_stdin(monkeypatch, capsys):
    payload = json.dumps({
        "worktrees": [
            {"path": "/a", "branch": "f1", "feature_id": "001", "claimed_paths": ["src/foo.py"]},
            {"path": "/b", "branch": "f2", "feature_id": "002", "claimed_paths": ["src/foo.py"]},
        ],
        "proposed_writes": [],
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    rc = cli_main(["worktree-overlap-check"])
    out = capsys.readouterr().out
    env = json.loads(out)
    assert rc == 0
    assert env["ok"] is True
    assert env["result"]["safe"] is False
    assert len(env["result"]["conflicts"]) == 1
```

Add `import io` at the top of the test file (alongside existing imports).

- [ ] **Step 10: Run all CLI tests**

Run: `uv run python -m pytest tests/cli/ tests/capabilities/test_worktree_overlap_check.py -v`
Expected: all PASS (6 unit + 1 new CLI test).

- [ ] **Step 11: Commit**

```bash
git add src/orca/capabilities/worktree_overlap_check.py src/orca/python_cli.py tests/capabilities/test_worktree_overlap_check.py tests/cli/test_python_cli.py docs/capabilities/worktree-overlap-check/
git commit -m "feat(capabilities): add worktree-overlap-check capability and CLI"
```

---

### Task 11: flow-state-projection capability

**Why:** mostly exists in `src/orca/flow_state.py`. v1 work is API stabilization + JSON contract. New capability module is a thin adapter.

**Files:**
- Create: `src/orca/capabilities/flow_state_projection.py`
- Create: `tests/capabilities/test_flow_state_projection.py`
- Create: `docs/capabilities/flow-state-projection/schema/input.json`
- Create: `docs/capabilities/flow-state-projection/schema/output.json`
- Create: `docs/capabilities/flow-state-projection/README.md`
- Modify: `src/orca/python_cli.py`

- [ ] **Step 1: Inspect existing flow_state API**

Run: `uv run python -c "import orca.flow_state as f; print([n for n in dir(f) if not n.startswith('_')])"`
Record names of exported functions and dataclasses for the adapter to call.

- [ ] **Step 2: Write input schema**

```json
// docs/capabilities/flow-state-projection/schema/input.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "feature_id": {"type": "string"},
    "feature_dir": {"type": "string"},
    "sdd_kind": {"enum": ["spec-kit", "openspec", "auto"], "default": "auto"},
    "repo_root": {"type": "string"}
  },
  "anyOf": [
    {"required": ["feature_id"]},
    {"required": ["feature_dir"]}
  ]
}
```

- [ ] **Step 3: Write output schema**

```json
// docs/capabilities/flow-state-projection/schema/output.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["feature_id", "current_stage", "artifacts", "review_status", "next_recommended_action"],
  "properties": {
    "feature_id": {"type": "string"},
    "current_stage": {"type": "string"},
    "artifacts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "path", "exists"],
        "properties": {
          "name": {"type": "string"},
          "path": {"type": "string"},
          "exists": {"type": "boolean"},
          "stale": {"type": "boolean"}
        }
      }
    },
    "review_status": {"type": "object"},
    "next_recommended_action": {"type": "string"}
  }
}
```

- [ ] **Step 4: Write README**

```markdown
// docs/capabilities/flow-state-projection/README.md
# flow-state-projection

Reports SDD stage, artifact statuses, review statuses, and next recommended action for a feature directory. Wraps `orca.flow_state` for stable JSON output.

## Input
Either `feature_id` (resolved against `repo_root`) or absolute `feature_dir`.

## SDD support
`spec-kit` and `openspec` both supported via `sdd_adapter`. Pass `sdd_kind=auto` to auto-detect.
```

- [ ] **Step 5: Write failing tests**

```python
# tests/capabilities/test_flow_state_projection.py
from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.errors import ErrorKind
from orca.capabilities.flow_state_projection import (
    FlowStateProjectionInput,
    flow_state_projection,
)


@pytest.fixture
def speckit_feature(tmp_path: Path) -> Path:
    feat = tmp_path / "specs" / "001-example"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("# Example\n")
    (feat / "plan.md").write_text("# Plan\n")
    return feat


def test_flow_state_projection_returns_state(speckit_feature):
    result = flow_state_projection(FlowStateProjectionInput(
        feature_dir=str(speckit_feature),
        sdd_kind="spec-kit",
    ))
    assert result.ok
    assert "current_stage" in result.value
    assert "artifacts" in result.value
    names = [a["name"] for a in result.value["artifacts"]]
    assert "spec" in names
    assert "plan" in names


def test_flow_state_projection_missing_dir():
    result = flow_state_projection(FlowStateProjectionInput(
        feature_dir="/nonexistent",
        sdd_kind="spec-kit",
    ))
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_flow_state_projection_no_id_or_dir():
    result = flow_state_projection(FlowStateProjectionInput())
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID
```

- [ ] **Step 6: Run, verify fail**

Run: `uv run python -m pytest tests/capabilities/test_flow_state_projection.py -v`
Expected: ImportError.

- [ ] **Step 7: Implement capability adapter**

```python
# src/orca/capabilities/flow_state_projection.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orca.core.errors import Error, ErrorKind
from orca.core.result import Err, Ok, Result
from orca import flow_state as _flow_state
from orca import sdd_adapter

VERSION = "0.1.0"


@dataclass(frozen=True)
class FlowStateProjectionInput:
    feature_id: str | None = None
    feature_dir: str | None = None
    sdd_kind: str = "auto"
    repo_root: str | None = None


def flow_state_projection(inp: FlowStateProjectionInput) -> Result[dict, Error]:
    if inp.feature_id is None and inp.feature_dir is None:
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message="must provide feature_id or feature_dir",
        ))

    feat_dir = _resolve_feature_dir(inp)
    if feat_dir is None or not feat_dir.exists():
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message=f"feature directory not found: {inp.feature_dir or inp.feature_id}",
        ))

    try:
        state = _flow_state.compute_flow_state(feat_dir)
    except Exception as exc:  # pragma: no cover (unexpected path)
        return Err(Error(kind=ErrorKind.INTERNAL, message=str(exc)))

    artifacts = _project_artifacts(state, feat_dir)
    return Ok({
        "feature_id": getattr(state, "feature_id", feat_dir.name),
        "current_stage": getattr(state, "current_stage", "unknown"),
        "artifacts": artifacts,
        "review_status": getattr(state, "review_status", {}),
        "next_recommended_action": getattr(state, "next_recommended_action", ""),
    })


def _resolve_feature_dir(inp: FlowStateProjectionInput) -> Path | None:
    if inp.feature_dir:
        return Path(inp.feature_dir)
    if inp.feature_id and inp.repo_root:
        return Path(inp.repo_root) / "specs" / inp.feature_id
    return None


def _project_artifacts(state, feat_dir: Path) -> list[dict]:
    """Map the in-memory flow_state object to a stable JSON shape.

    Reads .md artifacts known to SDD: spec, plan, tasks, brainstorm.
    """
    out = []
    for name in ("spec", "plan", "tasks", "brainstorm"):
        path = feat_dir / f"{name}.md"
        out.append({
            "name": name,
            "path": str(path),
            "exists": path.exists(),
            "stale": False,  # v1: staleness derives from review state; default False if not computed
        })
    return out
```

> **NOTE for implementer:** `flow_state.compute_flow_state` may not exist with that exact name. After Step 1, replace `_flow_state.compute_flow_state(feat_dir)` with whatever the actual API is. If `flow_state.py` exposes a builder class, instantiate and read from it. The adapter's job is to glue the existing API to a stable JSON shape.

- [ ] **Step 8: Run, verify pass**

Run: `uv run python -m pytest tests/capabilities/test_flow_state_projection.py -v`
Expected: 3 PASS. If not, adjust adapter to existing `flow_state` API.

- [ ] **Step 9: Wire CLI**

Edit `src/orca/python_cli.py`. Add to `CAPABILITIES`, add the runner mirroring worktree-overlap-check (stdin or `--feature-dir`/`--feature-id` args).

- [ ] **Step 10: Commit**

```bash
git add src/orca/capabilities/flow_state_projection.py tests/capabilities/test_flow_state_projection.py src/orca/python_cli.py docs/capabilities/flow-state-projection/
git commit -m "feat(capabilities): add flow-state-projection adapter and CLI"
```

---

### Task 12: completion-gate capability

**Why:** SDD R→P→I gate transitions. Decides whether a feature has cleared `plan-ready`, `implement-ready`, `pr-ready`, `merge-ready` based on artifact + review state.

**Files:**
- Create: `src/orca/capabilities/completion_gate.py`
- Create: `tests/capabilities/test_completion_gate.py`
- Create: `docs/capabilities/completion-gate/schema/{input,output}.json`
- Create: `docs/capabilities/completion-gate/README.md`
- Modify: `src/orca/python_cli.py`

- [ ] **Step 1: Write input schema**

```json
// docs/capabilities/completion-gate/schema/input.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["feature_dir", "target_stage"],
  "properties": {
    "feature_dir": {"type": "string"},
    "target_stage": {"enum": ["plan-ready", "implement-ready", "pr-ready", "merge-ready"]},
    "evidence": {"type": "object"}
  }
}
```

- [ ] **Step 2: Write output schema**

```json
// docs/capabilities/completion-gate/schema/output.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["status", "gates_evaluated", "blockers", "stale_artifacts"],
  "properties": {
    "status": {"enum": ["pass", "blocked", "stale"]},
    "gates_evaluated": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["gate", "passed"],
        "properties": {
          "gate": {"type": "string"},
          "passed": {"type": "boolean"},
          "reason": {"type": "string"}
        }
      }
    },
    "blockers": {"type": "array", "items": {"type": "string"}},
    "stale_artifacts": {"type": "array", "items": {"type": "string"}}
  }
}
```

- [ ] **Step 3: Write README**

```markdown
// docs/capabilities/completion-gate/README.md
# completion-gate

Decides whether an SDD-managed feature has cleared gates for a target stage. Revision-aware: detects stale artifacts when a prior review's bundle hash no longer matches the current artifact.

## Stages
- `plan-ready` — spec.md exists, has no `[NEEDS CLARIFICATION]`, has been reviewed.
- `implement-ready` — plan.md exists, has been reviewed; spec review still current.
- `pr-ready` — implementation complete, code review fresh.
- `merge-ready` — pr-ready + CI green, no unresolved review threads.

## Status
- `pass` — all gates for target stage are green
- `blocked` — at least one gate failed; `blockers[]` lists gate names
- `stale` — at least one prior review references a bundle hash that no longer matches; `stale_artifacts[]` lists which
```

- [ ] **Step 4: Write failing tests**

```python
# tests/capabilities/test_completion_gate.py
from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.errors import ErrorKind
from orca.capabilities.completion_gate import (
    CompletionGateInput,
    completion_gate,
)


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    d = tmp_path / "specs" / "001"
    d.mkdir(parents=True)
    return d


def test_plan_ready_pass(feature_dir):
    (feature_dir / "spec.md").write_text("# Example\n\nNo unclarified items.\n")
    result = completion_gate(CompletionGateInput(
        feature_dir=str(feature_dir),
        target_stage="plan-ready",
    ))
    assert result.ok
    assert result.value["status"] == "pass"
    assert result.value["blockers"] == []


def test_plan_ready_blocked_when_spec_missing(feature_dir):
    result = completion_gate(CompletionGateInput(
        feature_dir=str(feature_dir),
        target_stage="plan-ready",
    ))
    assert result.ok
    assert result.value["status"] == "blocked"
    assert "spec_exists" in result.value["blockers"]


def test_plan_ready_blocked_on_unclarified(feature_dir):
    (feature_dir / "spec.md").write_text("# Example\n\n[NEEDS CLARIFICATION] should we...\n")
    result = completion_gate(CompletionGateInput(
        feature_dir=str(feature_dir),
        target_stage="plan-ready",
    ))
    assert result.ok
    assert result.value["status"] == "blocked"
    assert "no_unclarified" in result.value["blockers"]


def test_implement_ready_blocked_without_plan(feature_dir):
    (feature_dir / "spec.md").write_text("# Example\n")
    result = completion_gate(CompletionGateInput(
        feature_dir=str(feature_dir),
        target_stage="implement-ready",
    ))
    assert result.ok
    assert result.value["status"] == "blocked"
    assert "plan_exists" in result.value["blockers"]


def test_invalid_target_stage(feature_dir):
    result = completion_gate(CompletionGateInput(
        feature_dir=str(feature_dir),
        target_stage="bogus",
    ))
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_missing_feature_dir():
    result = completion_gate(CompletionGateInput(
        feature_dir="/nonexistent",
        target_stage="plan-ready",
    ))
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID
```

- [ ] **Step 5: Run, verify fail**

Run: `uv run python -m pytest tests/capabilities/test_completion_gate.py -v`
Expected: ImportError.

- [ ] **Step 6: Implement capability**

```python
# src/orca/capabilities/completion_gate.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from orca.core.errors import Error, ErrorKind
from orca.core.result import Err, Ok, Result

VERSION = "0.1.0"

VALID_STAGES = {"plan-ready", "implement-ready", "pr-ready", "merge-ready"}


@dataclass(frozen=True)
class CompletionGateInput:
    feature_dir: str
    target_stage: str
    evidence: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GateOutcome:
    gate: str
    passed: bool
    reason: str = ""


def completion_gate(inp: CompletionGateInput) -> Result[dict, Error]:
    if inp.target_stage not in VALID_STAGES:
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message=f"invalid target_stage: {inp.target_stage}; expected one of {sorted(VALID_STAGES)}",
        ))

    feat = Path(inp.feature_dir)
    if not feat.exists():
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message=f"feature_dir does not exist: {feat}",
        ))

    gates = _gates_for_stage(inp.target_stage)
    outcomes = [g(feat, inp.evidence) for g in gates]

    blockers = [o.gate for o in outcomes if not o.passed]
    stale = list(inp.evidence.get("stale_artifacts", []))
    if stale:
        status = "stale"
    elif blockers:
        status = "blocked"
    else:
        status = "pass"

    return Ok({
        "status": status,
        "gates_evaluated": [{"gate": o.gate, "passed": o.passed, "reason": o.reason} for o in outcomes],
        "blockers": blockers,
        "stale_artifacts": stale,
    })


def _gates_for_stage(stage: str) -> list[Callable[[Path, dict], GateOutcome]]:
    plan_ready = [_gate_spec_exists, _gate_no_unclarified]
    implement_ready = plan_ready + [_gate_plan_exists]
    pr_ready = implement_ready + [_gate_tasks_exists]
    merge_ready = pr_ready + [_gate_evidence_ci_green]
    return {
        "plan-ready": plan_ready,
        "implement-ready": implement_ready,
        "pr-ready": pr_ready,
        "merge-ready": merge_ready,
    }[stage]


def _gate_spec_exists(feat: Path, _evidence: dict) -> GateOutcome:
    p = feat / "spec.md"
    return GateOutcome(gate="spec_exists", passed=p.exists())


def _gate_no_unclarified(feat: Path, _evidence: dict) -> GateOutcome:
    p = feat / "spec.md"
    if not p.exists():
        return GateOutcome(gate="no_unclarified", passed=False, reason="spec.md missing")
    text = p.read_text()
    if "[NEEDS CLARIFICATION]" in text:
        return GateOutcome(gate="no_unclarified", passed=False, reason="spec contains [NEEDS CLARIFICATION]")
    return GateOutcome(gate="no_unclarified", passed=True)


def _gate_plan_exists(feat: Path, _evidence: dict) -> GateOutcome:
    p = feat / "plan.md"
    return GateOutcome(gate="plan_exists", passed=p.exists())


def _gate_tasks_exists(feat: Path, _evidence: dict) -> GateOutcome:
    p = feat / "tasks.md"
    return GateOutcome(gate="tasks_exists", passed=p.exists())


def _gate_evidence_ci_green(_feat: Path, evidence: dict) -> GateOutcome:
    val = bool(evidence.get("ci_green"))
    return GateOutcome(
        gate="ci_green",
        passed=val,
        reason="evidence.ci_green=true required" if not val else "",
    )
```

- [ ] **Step 7: Run, verify pass**

Run: `uv run python -m pytest tests/capabilities/test_completion_gate.py -v`
Expected: 6 PASS.

- [ ] **Step 8: Wire CLI**

In `src/orca/python_cli.py`, add subcommand following the worktree-overlap-check pattern. Reads JSON from stdin or `--feature-dir`/`--target-stage` flags.

- [ ] **Step 9: Commit**

```bash
git add src/orca/capabilities/completion_gate.py tests/capabilities/test_completion_gate.py src/orca/python_cli.py docs/capabilities/completion-gate/
git commit -m "feat(capabilities): add completion-gate with stage-based gate evaluation"
```

---

### Task 13: citation-validator capability (rule-based)

**Why:** detects uncited claims and broken refs in synthesis text. v1 is rule-based — assertion-shaped sentence regex + ref existence check. No LLM.

**Files:**
- Create: `src/orca/capabilities/citation_validator.py`
- Create: `tests/capabilities/test_citation_validator.py`
- Create: `docs/capabilities/citation-validator/schema/{input,output}.json`
- Create: `docs/capabilities/citation-validator/README.md`
- Modify: `src/orca/python_cli.py`

- [ ] **Step 1: Write input schema**

```json
// docs/capabilities/citation-validator/schema/input.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["reference_set"],
  "oneOf": [
    {"required": ["content_path"]},
    {"required": ["content_text"]}
  ],
  "properties": {
    "content_path": {"type": "string"},
    "content_text": {"type": "string"},
    "reference_set": {"type": "array", "items": {"type": "string"}},
    "mode": {"enum": ["strict", "lenient"], "default": "strict"}
  }
}
```

- [ ] **Step 2: Write output schema**

```json
// docs/capabilities/citation-validator/schema/output.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["uncited_claims", "broken_refs", "citation_coverage"],
  "properties": {
    "uncited_claims": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["text", "line"],
        "properties": {"text": {"type": "string"}, "line": {"type": "integer"}}
      }
    },
    "broken_refs": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["ref", "line"],
        "properties": {"ref": {"type": "string"}, "line": {"type": "integer"}}
      }
    },
    "well_supported_claims": {"type": "array"},
    "citation_coverage": {"type": "number", "minimum": 0, "maximum": 1}
  }
}
```

- [ ] **Step 3: Write README**

```markdown
// docs/capabilities/citation-validator/README.md
# citation-validator

Detects uncited claims and broken refs in synthesis text using rule-based heuristics. v1 is regex + filesystem; no LLM.

## Heuristics
- **Assertion-shaped sentence:** sentences containing words like "shows", "demonstrates", "proves", "confirms", "indicates", or numerical claims, without a trailing `[ref]` or `(source)` citation.
- **Broken ref:** any `[ref]` or `[file:line]` that doesn't resolve in the `reference_set` paths.

## Modes
- `strict` — every assertion-shaped sentence requires a citation
- `lenient` — only sentences with numbers or strong-claim verbs require citation

## Limitations (v1)
Rule-based misses semantic claims that aren't surface-syntactic. v2 may add LLM mode.
```

- [ ] **Step 4: Write failing tests**

```python
# tests/capabilities/test_citation_validator.py
from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.errors import ErrorKind
from orca.capabilities.citation_validator import (
    CitationValidatorInput,
    citation_validator,
)


def test_well_cited_text_passes(tmp_path):
    ref = tmp_path / "evidence.md"
    ref.write_text("# Evidence\n")
    text = "Results show 42% improvement [evidence]."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    assert result.value["uncited_claims"] == []
    assert result.value["broken_refs"] == []
    assert result.value["citation_coverage"] == 1.0


def test_uncited_claim_detected(tmp_path):
    ref = tmp_path / "evidence.md"
    ref.write_text("# Evidence\n")
    text = "Results show 42% improvement."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    assert len(result.value["uncited_claims"]) == 1
    assert result.value["citation_coverage"] < 1.0


def test_broken_ref_detected(tmp_path):
    ref = tmp_path / "evidence.md"
    ref.write_text("# Evidence\n")
    text = "Results show 42% improvement [missing-ref]."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    assert len(result.value["broken_refs"]) == 1
    assert result.value["broken_refs"][0]["ref"] == "missing-ref"


def test_lenient_mode_skips_non_numerical(tmp_path):
    ref = tmp_path / "evidence.md"
    ref.write_text("x")
    text = "The system shows good performance."
    result = citation_validator(CitationValidatorInput(
        content_text=text,
        reference_set=[str(ref)],
        mode="lenient",
    ))
    assert result.ok
    assert result.value["uncited_claims"] == []


def test_content_path_loads_file(tmp_path):
    ref = tmp_path / "evidence.md"
    ref.write_text("x")
    content = tmp_path / "synthesis.md"
    content.write_text("Results show 42% improvement [evidence].")
    result = citation_validator(CitationValidatorInput(
        content_path=str(content),
        reference_set=[str(ref)],
        mode="strict",
    ))
    assert result.ok
    assert result.value["citation_coverage"] == 1.0


def test_neither_content_nor_path_invalid():
    result = citation_validator(CitationValidatorInput(
        content_text=None,
        content_path=None,
        reference_set=[],
    ))
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID
```

- [ ] **Step 5: Run, verify fail**

Run: `uv run python -m pytest tests/capabilities/test_citation_validator.py -v`
Expected: ImportError.

- [ ] **Step 6: Implement**

```python
# src/orca/capabilities/citation_validator.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from orca.core.errors import Error, ErrorKind
from orca.core.result import Err, Ok, Result

VERSION = "0.1.0"

# Sentence with assertion verbs OR numerical claims
_ASSERTION_VERBS = re.compile(r"\b(shows?|demonstrates?|proves?|confirms?|indicates?|establishes?)\b", re.IGNORECASE)
_NUMERIC_CLAIM = re.compile(r"\b\d+(\.\d+)?\s*%|\b\d{2,}\b")
_REF_PATTERN = re.compile(r"\[([^\[\]]+?)\]")


@dataclass(frozen=True)
class CitationValidatorInput:
    content_text: str | None = None
    content_path: str | None = None
    reference_set: list[str] = field(default_factory=list)
    mode: str = "strict"


def citation_validator(inp: CitationValidatorInput) -> Result[dict, Error]:
    if inp.content_text is None and inp.content_path is None:
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message="must provide content_text or content_path",
        ))

    if inp.mode not in ("strict", "lenient"):
        return Err(Error(
            kind=ErrorKind.INPUT_INVALID,
            message=f"mode must be 'strict' or 'lenient', got {inp.mode!r}",
        ))

    if inp.content_path:
        path = Path(inp.content_path)
        if not path.exists():
            return Err(Error(
                kind=ErrorKind.INPUT_INVALID,
                message=f"content_path does not exist: {path}",
            ))
        text = path.read_text()
    else:
        text = inp.content_text or ""

    available_refs = _index_refs(inp.reference_set)

    uncited: list[dict] = []
    broken: list[dict] = []
    well_supported: list[dict] = []
    total_assertions = 0

    for line_num, line in enumerate(text.splitlines(), start=1):
        for sentence in _split_sentences(line):
            if not _is_assertion(sentence, mode=inp.mode):
                continue
            total_assertions += 1
            refs = _REF_PATTERN.findall(sentence)
            if not refs:
                uncited.append({"text": sentence.strip(), "line": line_num})
                continue
            sentence_well_supported = True
            for ref in refs:
                if not _ref_resolves(ref, available_refs):
                    broken.append({"ref": ref, "line": line_num})
                    sentence_well_supported = False
            if sentence_well_supported:
                well_supported.append({"text": sentence.strip(), "line": line_num})

    coverage = 1.0 if total_assertions == 0 else (total_assertions - len(uncited)) / total_assertions
    return Ok({
        "uncited_claims": uncited,
        "broken_refs": broken,
        "well_supported_claims": well_supported,
        "citation_coverage": round(coverage, 3),
    })


def _index_refs(reference_set: list[str]) -> set[str]:
    """Index reference paths and their stems for lookup."""
    out: set[str] = set()
    for ref in reference_set:
        p = Path(ref)
        out.add(p.name)
        out.add(p.stem)
        out.add(str(p))
    return out


def _split_sentences(line: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", line) if s]


def _is_assertion(sentence: str, *, mode: str) -> bool:
    if mode == "lenient":
        return bool(_NUMERIC_CLAIM.search(sentence))
    return bool(_ASSERTION_VERBS.search(sentence) or _NUMERIC_CLAIM.search(sentence))


def _ref_resolves(ref: str, available: set[str]) -> bool:
    candidate = ref.strip()
    return (
        candidate in available
        or Path(candidate).name in available
        or Path(candidate).stem in available
    )
```

- [ ] **Step 7: Run, verify pass**

Run: `uv run python -m pytest tests/capabilities/test_citation_validator.py -v`
Expected: 6 PASS.

- [ ] **Step 8: Wire CLI** (mirror earlier capabilities)

- [ ] **Step 9: Commit**

```bash
git add src/orca/capabilities/citation_validator.py tests/capabilities/test_citation_validator.py src/orca/python_cli.py docs/capabilities/citation-validator/
git commit -m "feat(capabilities): add rule-based citation-validator"
```

---

### Task 14: contradiction-detector capability

**Why:** detects when new synthesis contradicts existing evidence. v1 = `cross-agent-review` with fixed contradiction criteria + structured output schema. Reuses cross-agent-review reviewer infrastructure.

**Files:**
- Create: `src/orca/capabilities/contradiction_detector.py`
- Create: `tests/capabilities/test_contradiction_detector.py`
- Create: `docs/capabilities/contradiction-detector/schema/{input,output}.json`
- Create: `docs/capabilities/contradiction-detector/README.md`
- Modify: `src/orca/python_cli.py`

- [ ] **Step 1: Write input schema**

```json
// docs/capabilities/contradiction-detector/schema/input.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["new_content", "prior_evidence"],
  "properties": {
    "new_content": {"type": "string", "description": "path to new synthesis or theory"},
    "prior_evidence": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "reviewer": {"enum": ["claude", "codex", "cross"], "default": "cross"}
  }
}
```

- [ ] **Step 2: Write output schema**

```json
// docs/capabilities/contradiction-detector/schema/output.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["contradictions", "partial", "reviewer_metadata"],
  "properties": {
    "contradictions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["new_claim", "conflicting_evidence_ref", "confidence"],
        "properties": {
          "new_claim": {"type": "string"},
          "conflicting_evidence_ref": {"type": "string"},
          "confidence": {"enum": ["high", "medium", "low"]},
          "suggested_resolution": {"type": "string"},
          "reviewer": {"type": "string"}
        }
      }
    },
    "partial": {"type": "boolean"},
    "missing_reviewer": {"type": ["string", "null"]},
    "reviewer_metadata": {"type": "object"}
  }
}
```

- [ ] **Step 3: Write README**

```markdown
// docs/capabilities/contradiction-detector/README.md
# contradiction-detector

Detects when new synthesis or theory contradicts existing raw evidence or prior synthesis. Effectively `cross-agent-review` with fixed contradiction criteria and a structured output schema.

## How it works
Bundles `new_content` + `prior_evidence` paths, sends to reviewer(s) with a contradiction-focused prompt, parses findings into a contradiction-shaped output. v2 may collapse this into a `cross-agent-review` preset.

## Confidence
Reviewer-reported confidence preserved. Hosts decide thresholds for blocking vs. warning.
```

- [ ] **Step 4: Write failing tests**

```python
# tests/capabilities/test_contradiction_detector.py
from __future__ import annotations

from pathlib import Path

import pytest

from orca.core.errors import ErrorKind
from orca.core.reviewers.base import RawFindings, ReviewerError
from orca.capabilities.contradiction_detector import (
    ContradictionDetectorInput,
    contradiction_detector,
)


class _StubReviewer:
    def __init__(self, name: str, *, contradictions: list[dict] | None = None, raise_error: bool = False):
        self.name = name
        self._contradictions = contradictions or []
        self._raise = raise_error

    def review(self, bundle, prompt):
        if self._raise:
            raise ReviewerError(f"{self.name} failed")
        # Map contradiction shape into raw_findings shape (capability normalizes)
        raw_findings = [{
            "category": "contradiction",
            "severity": "high",
            "confidence": c.get("confidence", "high"),
            "summary": c["new_claim"],
            "detail": f"conflicts with {c['conflicting_evidence_ref']}",
            "evidence": [c["conflicting_evidence_ref"]],
            "suggestion": c.get("suggested_resolution", ""),
        } for c in self._contradictions]
        return RawFindings(reviewer=self.name, findings=raw_findings, metadata={})


def _input(tmp_path, **overrides):
    new = tmp_path / "synthesis.md"
    new.write_text("New claim X.")
    prior = tmp_path / "evidence.md"
    prior.write_text("Old claim Y.")
    base = dict(
        new_content=str(new),
        prior_evidence=[str(prior)],
        reviewer="cross",
    )
    base.update(overrides)
    return ContradictionDetectorInput(**base)


def test_contradiction_detector_returns_contradictions(tmp_path):
    contradictions = [{
        "new_claim": "X is fast",
        "conflicting_evidence_ref": "evidence.md",
        "confidence": "high",
        "suggested_resolution": "re-measure",
    }]
    result = contradiction_detector(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", contradictions=contradictions),
                   "codex": _StubReviewer("codex", contradictions=contradictions)},
    )
    assert result.ok
    assert len(result.value["contradictions"]) == 1
    assert result.value["contradictions"][0]["new_claim"] == "X is fast"


def test_contradiction_detector_no_contradictions_returns_empty(tmp_path):
    result = contradiction_detector(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude"), "codex": _StubReviewer("codex")},
    )
    assert result.ok
    assert result.value["contradictions"] == []


def test_contradiction_detector_partial_when_one_fails(tmp_path):
    contradictions = [{
        "new_claim": "X", "conflicting_evidence_ref": "e", "confidence": "high",
    }]
    result = contradiction_detector(
        _input(tmp_path),
        reviewers={"claude": _StubReviewer("claude", contradictions=contradictions),
                   "codex": _StubReviewer("codex", raise_error=True)},
    )
    assert result.ok
    assert result.value["partial"] is True
    assert result.value["missing_reviewer"] == "codex"


def test_contradiction_detector_invalid_reviewer(tmp_path):
    inp = _input(tmp_path, reviewer="bogus")
    result = contradiction_detector(inp, reviewers={})
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID


def test_contradiction_detector_missing_new_content(tmp_path):
    inp = _input(tmp_path)
    inp_bad = ContradictionDetectorInput(
        new_content=str(tmp_path / "nope.md"),
        prior_evidence=inp.prior_evidence,
        reviewer="cross",
    )
    result = contradiction_detector(
        inp_bad,
        reviewers={"claude": _StubReviewer("claude"), "codex": _StubReviewer("codex")},
    )
    assert not result.ok
    assert result.error.kind == ErrorKind.INPUT_INVALID
```

- [ ] **Step 5: Run, verify fail**

Run: `uv run python -m pytest tests/capabilities/test_contradiction_detector.py -v`
Expected: ImportError.

- [ ] **Step 6: Implement**

```python
# src/orca/capabilities/contradiction_detector.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from orca.core.bundle import BundleError, build_bundle
from orca.core.errors import Error, ErrorKind
from orca.core.result import Err, Ok, Result
from orca.core.reviewers.base import Reviewer, ReviewerError
from orca.core.reviewers.cross import CrossReviewer

VERSION = "0.1.0"

_PROMPT = (
    "Compare the new content against the prior evidence. "
    "Return a JSON array of findings where each finding represents a CONTRADICTION between "
    "a claim in the new content and the prior evidence. Each finding MUST include: "
    "category='contradiction', severity, confidence, summary (the new claim), detail (why it conflicts), "
    "evidence (refs to prior evidence files/lines that conflict), suggestion (how to resolve)."
)

_VALID_REVIEWERS = {"claude", "codex", "cross"}


@dataclass(frozen=True)
class ContradictionDetectorInput:
    new_content: str
    prior_evidence: list[str]
    reviewer: str = "cross"


def contradiction_detector(
    inp: ContradictionDetectorInput,
    *,
    reviewers: Mapping[str, Reviewer],
) -> Result[dict, Error]:
    if inp.reviewer not in _VALID_REVIEWERS:
        return Err(Error(kind=ErrorKind.INPUT_INVALID, message=f"unknown reviewer: {inp.reviewer}"))

    try:
        bundle = build_bundle(
            kind="claim-output",
            target=[inp.new_content],
            feature_id=None,
            criteria=["contradiction"],
            context=inp.prior_evidence,
        )
    except BundleError as exc:
        return Err(Error(kind=ErrorKind.INPUT_INVALID, message=str(exc)))

    if inp.reviewer == "cross":
        try:
            cross = CrossReviewer(reviewers=[reviewers["claude"], reviewers["codex"]])
        except KeyError as exc:
            return Err(Error(kind=ErrorKind.INPUT_INVALID, message=f"missing reviewer for cross: {exc}"))
        try:
            cross_result = cross.review(bundle, _PROMPT)
        except ReviewerError as exc:
            return Err(Error(kind=ErrorKind.BACKEND_FAILURE, message=str(exc)))

        contradictions = [_to_contradiction(f.to_json()) for f in cross_result.findings]
        return Ok({
            "contradictions": contradictions,
            "partial": cross_result.partial,
            "missing_reviewer": cross_result.missing_reviewer,
            "reviewer_metadata": cross_result.reviewer_metadata,
        })

    if inp.reviewer not in reviewers:
        return Err(Error(kind=ErrorKind.INPUT_INVALID, message=f"reviewer not configured: {inp.reviewer}"))

    try:
        raw = reviewers[inp.reviewer].review(bundle, _PROMPT)
    except ReviewerError as exc:
        return Err(Error(kind=ErrorKind.BACKEND_FAILURE, message=str(exc)))

    contradictions = [_to_contradiction({**f, "reviewer": raw.reviewer, "reviewers": [raw.reviewer]}) for f in raw.findings]
    return Ok({
        "contradictions": contradictions,
        "partial": False,
        "missing_reviewer": None,
        "reviewer_metadata": {raw.reviewer: raw.metadata},
    })


def _to_contradiction(finding: dict) -> dict:
    evidence = finding.get("evidence", [])
    return {
        "new_claim": finding.get("summary", ""),
        "conflicting_evidence_ref": evidence[0] if evidence else "",
        "confidence": finding.get("confidence", "low"),
        "suggested_resolution": finding.get("suggestion", ""),
        "reviewer": finding.get("reviewer", ""),
    }
```

- [ ] **Step 7: Run, verify pass**

Run: `uv run python -m pytest tests/capabilities/test_contradiction_detector.py -v`
Expected: 5 PASS.

- [ ] **Step 8: Wire CLI**

- [ ] **Step 9: Commit**

```bash
git add src/orca/capabilities/contradiction_detector.py tests/capabilities/test_contradiction_detector.py src/orca/python_cli.py docs/capabilities/contradiction-detector/
git commit -m "feat(capabilities): add contradiction-detector via cross-agent-review"
```

---

### Task 15: Reviewer-adapter contract test

**Why:** the design's swap-cleanly claim. Every reviewer is parameterized through the same test that asserts against the findings schema.

**Files:**
- Create: `tests/core/reviewers/test_adapter_contract.py`

- [ ] **Step 1: Write parameterized contract test**

```python
# tests/core/reviewers/test_adapter_contract.py
"""Adapter contract: every reviewer's RawFindings round-trips into Finding objects.

Adding a new reviewer? Add it to the parametrize list. If your reviewer can't pass this,
it doesn't ship.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from orca.core.bundle import build_bundle
from orca.core.findings import Confidence, Finding, Severity
from orca.core.reviewers.claude import ClaudeReviewer
from orca.core.reviewers.codex import CodexReviewer
from orca.core.reviewers.fixtures import FixtureReviewer

FIXTURE_ROOT = Path(__file__).parent.parent.parent / "fixtures" / "reviewers"


def _fake_anthropic_response(text: str):
    block = MagicMock(); block.type = "text"; block.text = text
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "end_turn"
    response.usage = MagicMock(input_tokens=10, output_tokens=20)
    return response


def _bundle(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("pass\n")
    return build_bundle(kind="diff", target=[str(f)], feature_id=None, criteria=[], context=[])


CANONICAL = json.dumps([{
    "category": "correctness",
    "severity": "high",
    "confidence": "high",
    "summary": "Off-by-one in loop",
    "detail": "range(n) skips the last element.",
    "evidence": ["src/foo.py:42"],
    "suggestion": "Use range(n+1)",
}])


def _make_claude():
    client = MagicMock()
    client.messages.create.return_value = _fake_anthropic_response(CANONICAL)
    return ClaudeReviewer(client=client)


def _make_codex():
    fixture = FIXTURE_ROOT / "codex" / "simple_review.json"
    return FixtureReviewer(scenario=fixture, name="codex")


def _make_fixture_claude():
    fixture = FIXTURE_ROOT / "scenarios" / "simple_diff.json"
    return FixtureReviewer(scenario=fixture, name="claude")


@pytest.mark.parametrize("make_reviewer,expected_name", [
    (_make_claude, "claude"),
    (_make_codex, "codex"),
    (_make_fixture_claude, "claude"),
])
def test_reviewer_returns_findings_that_round_trip(make_reviewer, expected_name, tmp_path):
    reviewer = make_reviewer()
    raw = reviewer.review(_bundle(tmp_path), prompt="review")

    assert raw.reviewer == expected_name
    for f in raw.findings:
        finding = Finding(
            category=f["category"],
            severity=Severity(f["severity"]),
            confidence=Confidence(f["confidence"]),
            summary=f["summary"],
            detail=f["detail"],
            evidence=list(f.get("evidence", [])),
            suggestion=f.get("suggestion", ""),
            reviewer=raw.reviewer,
        )
        json_form = finding.to_json()
        assert len(json_form["id"]) == 16
        assert json_form["severity"] in {"blocker", "high", "medium", "low", "nit"}
        assert json_form["confidence"] in {"high", "medium", "low"}
```

- [ ] **Step 2: Run, verify pass**

Run: `uv run python -m pytest tests/core/reviewers/test_adapter_contract.py -v`
Expected: 3 PASS (one per parametrize entry).

- [ ] **Step 3: Commit**

```bash
git add tests/core/reviewers/test_adapter_contract.py
git commit -m "test(core/reviewers): add cross-reviewer adapter contract test"
```

---

### Task 16: JSON schema validation in CI

**Why:** the design's "schema drift is a build break" claim. Every capability output validates against its schema.

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `tests/cli/test_schema_validation.py`

- [ ] **Step 1: Write tests that validate every capability's output against its schema**

```python
# tests/cli/test_schema_validation.py
"""Every capability's output JSON must validate against its declared output schema."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs" / "capabilities"


@pytest.mark.parametrize("capability", [
    "cross-agent-review",
    "worktree-overlap-check",
    "flow-state-projection",
    "completion-gate",
    "citation-validator",
    "contradiction-detector",
])
def test_schemas_are_valid_draft7(capability):
    schema_dir = DOCS / capability / "schema"
    for name in ("input.json", "output.json"):
        schema = json.loads((schema_dir / name).read_text())
        jsonschema.Draft7Validator.check_schema(schema)


def test_cross_agent_review_sample_output_validates(tmp_path):
    schema = json.loads((DOCS / "cross-agent-review" / "schema" / "output.json").read_text())
    sample = {
        "findings": [{
            "id": "0123456789abcdef",
            "category": "correctness", "severity": "high", "confidence": "high",
            "summary": "S", "detail": "d", "evidence": ["x:1"], "suggestion": "s",
            "reviewer": "claude", "reviewers": ["claude"],
        }],
        "partial": False,
        "missing_reviewer": None,
        "reviewer_metadata": {"claude": {}},
    }
    jsonschema.validate(sample, schema)


def test_worktree_overlap_sample_output_validates():
    schema = json.loads((DOCS / "worktree-overlap-check" / "schema" / "output.json").read_text())
    sample = {"safe": True, "conflicts": [], "proposed_overlaps": []}
    jsonschema.validate(sample, schema)


def test_completion_gate_sample_output_validates():
    schema = json.loads((DOCS / "completion-gate" / "schema" / "output.json").read_text())
    sample = {
        "status": "pass",
        "gates_evaluated": [{"gate": "spec_exists", "passed": True}],
        "blockers": [],
        "stale_artifacts": [],
    }
    jsonschema.validate(sample, schema)


def test_citation_validator_sample_output_validates():
    schema = json.loads((DOCS / "citation-validator" / "schema" / "output.json").read_text())
    sample = {
        "uncited_claims": [], "broken_refs": [], "well_supported_claims": [],
        "citation_coverage": 1.0,
    }
    jsonschema.validate(sample, schema)


def test_contradiction_detector_sample_output_validates():
    schema = json.loads((DOCS / "contradiction-detector" / "schema" / "output.json").read_text())
    sample = {
        "contradictions": [{
            "new_claim": "X", "conflicting_evidence_ref": "e", "confidence": "high",
        }],
        "partial": False,
        "missing_reviewer": None,
        "reviewer_metadata": {},
    }
    jsonschema.validate(sample, schema)
```

- [ ] **Step 2: Run, verify pass**

Run: `uv run python -m pytest tests/cli/test_schema_validation.py -v`
Expected: 11 PASS (6 schema-valid + 5 sample validations).

- [ ] **Step 3: Update CI matrix**

Open `.github/workflows/ci.yml`. Find the existing pytest invocation. Add a new step (or extend the existing one) so the CI also runs the schema validation tests. Concretely, the test step should already pick them up via `pytest tests/`, but add an explicit named step for clarity:

```yaml
      - name: Validate capability schemas
        run: uv run python -m pytest tests/cli/test_schema_validation.py -v
```

Place this step before the broader test step or alongside it.

- [ ] **Step 4: Commit**

```bash
git add tests/cli/test_schema_validation.py .github/workflows/ci.yml
git commit -m "test(cli): add schema validation per capability + CI step"
```

---

### Task 17: Phase 2 final verification

**Why:** confirm the whole Phase 2 deliverable runs green before handoff.

- [ ] **Step 1: Full test suite**

Run: `uv run python -m pytest tests/ -v`
Expected: all green. Take note of total count for the commit message.

- [ ] **Step 2: Verify all CLI subcommands list**

Run: `uv run orca-cli --list`
Expected output (one per line):
```
cross-agent-review
worktree-overlap-check
flow-state-projection
completion-gate
citation-validator
contradiction-detector
```

- [ ] **Step 3: Smoke each capability with a fixture or trivial input**

```bash
# cross-agent-review
mkdir -p /tmp/orca-smoke && echo "pass" > /tmp/orca-smoke/x.py
echo '{"reviewer":"claude","raw_findings":[]}' > /tmp/orca-smoke/empty.json
ORCA_FIXTURE_REVIEWER_CLAUDE=/tmp/orca-smoke/empty.json \
ORCA_FIXTURE_REVIEWER_CODEX=/tmp/orca-smoke/empty.json \
uv run orca-cli cross-agent-review --kind diff --target /tmp/orca-smoke/x.py --reviewer cross | jq .ok

# worktree-overlap-check
echo '{"worktrees":[]}' | uv run orca-cli worktree-overlap-check | jq .ok

# completion-gate
mkdir -p /tmp/orca-smoke/feat && echo "# spec" > /tmp/orca-smoke/feat/spec.md
echo "{\"feature_dir\":\"/tmp/orca-smoke/feat\",\"target_stage\":\"plan-ready\"}" \
  | uv run orca-cli completion-gate | jq .ok

# citation-validator
echo "Results show 42% improvement [evidence]." > /tmp/orca-smoke/syn.md
echo "{\"content_path\":\"/tmp/orca-smoke/syn.md\",\"reference_set\":[\"/tmp/orca-smoke/syn.md\"]}" \
  | uv run orca-cli citation-validator | jq .ok
```

Expected: each prints `true`.

- [ ] **Step 4: Tag Phase 2 completion**

```bash
git tag orca-v0.2.0
```

(Local tag; push only on user instruction.)

- [ ] **Step 5: Open PR**

```bash
git push -u origin orca-phase-2-capability-cores
gh pr create --base main --title "feat: orca v1 phase 2 — capability cores and CLI" --body "$(cat <<'EOF'
## Summary

Phase 2 of orca v1: implements all 6 capability cores plus the canonical Python CLI.

- Phase 2a: cross-agent-review wedge (Result type, Findings, Bundle, Reviewer protocol, ClaudeReviewer, CodexReviewer, CrossReviewer, capability, CLI)
- Phase 2b: worktree-overlap-check, flow-state-projection, completion-gate, citation-validator, contradiction-detector
- Adapter contract test parameterized across reviewers
- JSON schema per capability + CI validation step
- `orca-cli` script entry alongside existing bash launcher

## Test plan

- [ ] `uv run python -m pytest` — full suite passes
- [ ] `uv run orca-cli --list` shows all 6 capabilities
- [ ] CI green
- [ ] Schema validation step passes

## Out of scope (Phases 3-5)

- Plugin formats (Claude Code skills + Codex AGENTS.md fragments)
- Perf-lab integration shim
- Personal SDD opinion-layer slash commands beyond what already exists
- Caching, MCP wrapper
EOF
)"
```

(Skip this step if user prefers to push and PR manually.)

---

## Self-Review

### Spec coverage

| Spec section | Tasks |
|---|---|
| 6 v1 capabilities | Tasks 8 (cross-agent-review), 10 (worktree-overlap-check), 11 (flow-state-projection), 12 (completion-gate), 13 (citation-validator), 14 (contradiction-detector) |
| CLI + Python library | Task 9 (cross-agent-review subcommand), 10/11/12/13/14 add other subcommands |
| Result-typed Python API | Task 1 |
| Reviewer backend abstraction (Claude/Codex/cross) | Tasks 4 (protocol + fixture), 5 (Claude), 6 (Codex), 7 (Cross) |
| Stable dedupe ID for findings | Task 2 |
| Per-capability JSON contract | Tasks 8/10/11/12/13/14 each include schema + README |
| Test coverage strategy | Tasks 4-15 (unit + adapter contract + CLI + schema validation) |
| Reviewer adapter contract test | Task 15 |
| JSON schema validation in CI | Task 16 |
| Recorded fixtures + ORCA_LIVE | Tasks 5/6 fixtures, Task 9 CLI reads `ORCA_FIXTURE_REVIEWER_*` env vars |
| Universal Result envelope | Task 1 (`Result.to_json`) |
| Per-capability error surface | Tasks 8/10/11/12/13/14 enforce `ErrorKind` use; pure-logic capabilities only emit `input_invalid`/`internal` |
| Cross-mode partial success | Tasks 7 (CrossReviewer.partial), 8 (capability propagates), 14 (contradiction-detector propagates) |

**Deferred to later phases (out of Phase 2 scope per design):**
- Plugin formats (Claude Code skills, Codex AGENTS.md fragments) → Phase 3
- Perf-lab integration shim → Phase 4
- E2E personal SDD test (slash command → findings markdown) → Phase 3
- E2E perf-lab test (fixture mission → critique event) → Phase 4
- Live LLM nightly run → Phase 5 hardening
- Caching, MCP wrapper → deferred per design

### Placeholder scan

No placeholders, TBDs, or "implement later" found. Every code step has complete code. Every test step has the actual test. The one note in Task 11 ("`flow_state.compute_flow_state` may not exist with that exact name") is explicitly flagged for the implementer with instructions on what to do — not a placeholder.

### Type consistency

- `Result.ok` is a bool field on `Ok`/`Err`; tests check `.ok`, capability bodies return `Ok(...)`/`Err(...)`. Consistent.
- `Finding.evidence: list[str]`, `Finding.reviewers: tuple[str, ...]` — used consistently in `dedupe_id()`, `to_json()`, `Findings.merge()`.
- `Reviewer.review(bundle, prompt) -> RawFindings` — same signature in `ClaudeReviewer`, `CodexReviewer`, `FixtureReviewer`, stub reviewers in tests.
- `ErrorKind` values: `input_invalid`, `backend_failure`, `timeout`, `internal` — referenced consistently across capabilities.
- `CrossReviewer.review(...) -> CrossResult` (not `RawFindings`) — capability code unwraps via `_render_cross`. Verified consistent.
- CLI `_emit_envelope` signature consistent across runners; `_err_envelope` builder consistent.

### Scope check

This is one phase, one repo. Phase 2a (foundation + wedge) and Phase 2b (5 remaining caps) sequence cleanly because Phase 2b depends entirely on `core/` from Phase 2a. The plan stays in scope; deferred items are explicitly listed.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-27-orca-phase-2-capability-cores-and-cli.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Same flow that worked for Phase 1.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
