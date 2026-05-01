# Path-Safety Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `orca.core.path_safety` shared module enforcing the path-safety contract; migrate Class A/C/D path validation at CLI boundaries to use it.

**Architecture:** New stdlib-only module exposes `PathSafetyError` exception + four pure validate functions. Capability boundaries (`python_cli.py` argparse handlers, `FileBackedReviewer`) catch `PathSafetyError` and convert to `Err(Error(kind=INPUT_INVALID, detail={field, rule_violated, value_redacted}))`. Internal helpers — paths already passed through the boundary — do not re-validate.

**Tech Stack:** Python 3.10+, pytest. Stdlib only (`pathlib`, `re`, `os`).

**Spec:** `docs/superpowers/specs/2026-04-30-orca-path-safety-consolidation-design.md` (commit `8da1fd8`).

**Worktree:** `/home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats`. Branch: `orca-phase-3-plugin-formats`.

**Test runner:** `uv run python -m pytest`.

---

## File map

**Create:**
- `src/orca/core/path_safety.py` — module
- `tests/core/test_path_safety.py` — tests

**Modify:**
- `src/orca/python_cli.py` — extend `_err_envelope`; replace `_validate_findings_file_eagerly`; delete `_validate_feature_id`; add `--target`, `--feature-dir`, `--prior-evidence`, missing `--feature-id` validation
- `src/orca/core/reviewers/file_backed.py` — delegate path-shape checks to `validate_findings_file`
- `tests/core/reviewers/test_file_backed.py` — update assertion shape (still matches "symlinks rejected" but exception is now wrapped)

**Note on flag inventory:**

The spec listed `--evidence-path` as a Class A migration site. That flag does not exist in current orca CLI — `contradiction-detector` uses `--prior-evidence` (repeatable) and `completion-gate` uses `--feature-dir`. This plan migrates the actual flags. The spec's migration count of "5 sites" is preserved; one entry shifts from `--evidence-path` to `--prior-evidence` / `--feature-dir`.

---

## Task 1: Module skeleton + `PathSafetyError`

**Files:**
- Create: `src/orca/core/path_safety.py`
- Create: `tests/core/test_path_safety.py`

- [ ] **Step 1: Write the failing test for `PathSafetyError` shape**

`tests/core/test_path_safety.py`:

```python
"""Tests for orca.core.path_safety — enforces docs/superpowers/contracts/path-safety.md."""
from __future__ import annotations

import pytest

from orca.core.path_safety import PathSafetyError


def test_path_safety_error_carries_structured_fields():
    err = PathSafetyError(
        "symlinks rejected: /tmp/x",
        field="--claude-findings-file",
        rule_violated="symlink_in_resolved_path",
        value_redacted="/tmp/x",
    )
    assert str(err) == "symlinks rejected: /tmp/x"
    assert err.field == "--claude-findings-file"
    assert err.rule_violated == "symlink_in_resolved_path"
    assert err.value_redacted == "/tmp/x"


def test_path_safety_error_to_error_detail_returns_three_keys():
    err = PathSafetyError(
        "msg", field="--feature-id", rule_violated="identifier_format",
        value_redacted="bad/value",
    )
    assert err.to_error_detail() == {
        "field": "--feature-id",
        "rule_violated": "identifier_format",
        "value_redacted": "bad/value",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/core/test_path_safety.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'orca.core.path_safety'`

- [ ] **Step 3: Implement minimal module**

`src/orca/core/path_safety.py`:

```python
"""Path-safety validation helpers.

Enforces docs/superpowers/contracts/path-safety.md at CLI boundaries.

Design:
- Pure stdlib (pathlib, re, os).
- Each validator raises PathSafetyError on contract violation, returns the
  resolved Path (or sanitized string for identifiers) on success.
- Exception carries field/rule_violated/value_redacted suitable for
  INPUT_INVALID error envelopes via to_error_detail().
"""
from __future__ import annotations


class PathSafetyError(Exception):
    """Raised by path_safety helpers on contract violation."""

    def __init__(
        self,
        message: str,
        *,
        field: str,
        rule_violated: str,
        value_redacted: str,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.rule_violated = rule_violated
        self.value_redacted = value_redacted

    def to_error_detail(self) -> dict:
        return {
            "field": self.field,
            "rule_violated": self.rule_violated,
            "value_redacted": self.value_redacted,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/core/test_path_safety.py -v`
Expected: PASS, 2 tests.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/path_safety.py tests/core/test_path_safety.py
git commit -m "feat(core): add path_safety module skeleton with PathSafetyError"
```

---

## Task 2: `validate_identifier` (Class D)

**Files:**
- Modify: `src/orca/core/path_safety.py`
- Modify: `tests/core/test_path_safety.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/core/test_path_safety.py`:

```python
from orca.core.path_safety import validate_identifier


class TestValidateIdentifier:
    def test_valid_alphanumeric(self):
        assert validate_identifier("feature_001", field="--feature-id") == "feature_001"

    def test_valid_with_dots_dashes_underscores(self):
        assert validate_identifier("001-foo.bar_baz", field="--feature-id") == "001-foo.bar_baz"

    def test_rejects_empty_string(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_empty"
        assert exc_info.value.field == "--feature-id"

    def test_rejects_dot(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier(".", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_reserved"

    def test_rejects_double_dot(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("..", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_reserved"

    def test_rejects_leading_dash(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("-foo", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_format"

    def test_rejects_slash(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("foo/bar", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_format"

    def test_rejects_null_byte(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("foo\0bar", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_format"

    def test_rejects_traversal_attempt(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("..\\foo", field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_format"

    def test_rejects_too_long(self):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_identifier("a" * 129, field="--feature-id")
        assert exc_info.value.rule_violated == "identifier_too_long"

    def test_max_length_default_is_128(self):
        # Exactly 128 chars: valid
        assert validate_identifier("a" * 128, field="--feature-id") == "a" * 128
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/core/test_path_safety.py::TestValidateIdentifier -v`
Expected: FAIL with `ImportError: cannot import name 'validate_identifier'`.

- [ ] **Step 3: Implement `validate_identifier`**

Append to `src/orca/core/path_safety.py`:

```python
import re

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_identifier(
    value: str,
    *,
    field: str,
    max_length: int = 128,
) -> str:
    """Validate a Class D identifier string.

    Returns the value unchanged on success. Raises PathSafetyError otherwise.
    Rules per contract: regex [A-Za-z0-9._-]+, not '.' or '..', not empty,
    no leading '-', length <= max_length.
    """
    if value == "":
        raise PathSafetyError(
            f"{field} is empty",
            field=field, rule_violated="identifier_empty", value_redacted="",
        )
    if value in (".", ".."):
        raise PathSafetyError(
            f"{field}={value!r} not allowed (reserved path component)",
            field=field, rule_violated="identifier_reserved", value_redacted=value,
        )
    if len(value) > max_length:
        raise PathSafetyError(
            f"{field} exceeds {max_length} chars (got {len(value)})",
            field=field, rule_violated="identifier_too_long", value_redacted=value,
        )
    if value.startswith("-"):
        raise PathSafetyError(
            f"{field}={value!r} cannot start with '-'",
            field=field, rule_violated="identifier_format", value_redacted=value,
        )
    if not _IDENTIFIER_RE.match(value):
        raise PathSafetyError(
            f"{field}={value!r} must match [A-Za-z0-9._-]+",
            field=field, rule_violated="identifier_format", value_redacted=value,
        )
    return value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/core/test_path_safety.py -v`
Expected: PASS, 13 tests total.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/path_safety.py tests/core/test_path_safety.py
git commit -m "feat(core/path_safety): add validate_identifier for Class D"
```

---

## Task 3: `validate_repo_file` (Class A file)

**Files:**
- Modify: `src/orca/core/path_safety.py`
- Modify: `tests/core/test_path_safety.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/core/test_path_safety.py`:

```python
from pathlib import Path

from orca.core.path_safety import validate_repo_file


class TestValidateRepoFile:
    def test_happy_path_returns_resolved(self, tmp_path: Path):
        f = tmp_path / "spec.md"
        f.write_text("hello", encoding="utf-8")
        result = validate_repo_file(f, root=tmp_path, field="--target")
        assert result == f.resolve()

    def test_accepts_string_path(self, tmp_path: Path):
        f = tmp_path / "spec.md"
        f.write_text("hello")
        result = validate_repo_file(str(f), root=tmp_path, field="--target")
        assert result == f.resolve()

    def test_rejects_symlink(self, tmp_path: Path):
        real = tmp_path / "real.md"
        real.write_text("hi")
        link = tmp_path / "link.md"
        link.symlink_to(real)
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_file(link, root=tmp_path, field="--target")
        assert exc_info.value.rule_violated == "symlink_in_resolved_path"

    def test_rejects_path_outside_root(self, tmp_path: Path):
        outside = tmp_path.parent / "outside.md"
        outside.write_text("escape")
        try:
            with pytest.raises(PathSafetyError) as exc_info:
                validate_repo_file(outside, root=tmp_path, field="--target")
            assert exc_info.value.rule_violated == "path_outside_root"
        finally:
            outside.unlink(missing_ok=True)

    def test_rejects_directory(self, tmp_path: Path):
        d = tmp_path / "subdir"
        d.mkdir()
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_file(d, root=tmp_path, field="--target")
        assert exc_info.value.rule_violated == "not_a_regular_file"

    def test_rejects_missing_when_must_exist(self, tmp_path: Path):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_file(tmp_path / "missing.md", root=tmp_path, field="--target")
        assert exc_info.value.rule_violated == "does_not_exist"

    def test_rejects_oversized(self, tmp_path: Path):
        f = tmp_path / "big.md"
        f.write_bytes(b"x" * 1024)
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_file(f, root=tmp_path, field="--target", max_bytes=512)
        assert exc_info.value.rule_violated == "size_cap_exceeded"

    def test_must_exist_false_allows_missing(self, tmp_path: Path):
        # must_exist=False is for forward-looking writes; size/type checks skipped
        result = validate_repo_file(
            tmp_path / "future.md", root=tmp_path, field="--target", must_exist=False
        )
        assert result == (tmp_path / "future.md").resolve()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/core/test_path_safety.py::TestValidateRepoFile -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `validate_repo_file` and shared helpers**

Append to `src/orca/core/path_safety.py`:

```python
import os
from pathlib import Path


def _resolve_and_check_symlink(path: Path, *, field: str) -> Path:
    """Resolve to absolute. Reject if any component traverses a symlink.

    Uses os.path.realpath vs os.path.abspath to detect component-level
    symlinks (Path.is_symlink only checks the leaf). Raises on mismatch.
    Returns the resolved Path (which equals abspath when no symlinks).
    """
    raw = str(path)
    abs_path = os.path.abspath(raw)
    real_path = os.path.realpath(raw)
    if abs_path != real_path:
        raise PathSafetyError(
            f"symlinks rejected in resolved path: {raw}",
            field=field,
            rule_violated="symlink_in_resolved_path",
            value_redacted=raw,
        )
    return Path(abs_path)


def _check_root_containment(resolved: Path, root: Path, *, field: str) -> None:
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        raise PathSafetyError(
            f"path outside root: {resolved} not under {root_resolved}",
            field=field,
            rule_violated="path_outside_root",
            value_redacted=str(resolved),
        )


def validate_repo_file(
    path: "str | Path",
    *,
    root: Path,
    field: str,
    must_exist: bool = True,
    max_bytes: int = 10 * 1024 * 1024,
) -> Path:
    """Validate a Class A path that must point at a regular file.

    Resolves to absolute, rejects symlinks, enforces containment in root,
    enforces regular-file type if must_exist, enforces size cap.
    Returns the resolved Path. Raises PathSafetyError on violation.
    """
    resolved = _resolve_and_check_symlink(Path(path), field=field)
    _check_root_containment(resolved, root, field=field)

    if not must_exist:
        return resolved

    if not resolved.exists():
        raise PathSafetyError(
            f"path does not exist: {resolved}",
            field=field,
            rule_violated="does_not_exist",
            value_redacted=str(resolved),
        )
    if not resolved.is_file():
        raise PathSafetyError(
            f"not a regular file: {resolved}",
            field=field,
            rule_violated="not_a_regular_file",
            value_redacted=str(resolved),
        )
    size = resolved.stat().st_size
    if size > max_bytes:
        raise PathSafetyError(
            f"file exceeds {max_bytes} byte cap ({size} bytes): {resolved}",
            field=field,
            rule_violated="size_cap_exceeded",
            value_redacted=str(resolved),
        )
    return resolved
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/core/test_path_safety.py -v`
Expected: PASS, 21 tests total.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/path_safety.py tests/core/test_path_safety.py
git commit -m "feat(core/path_safety): add validate_repo_file for Class A files"
```

---

## Task 4: `validate_repo_dir` (Class A dir)

**Files:**
- Modify: `src/orca/core/path_safety.py`
- Modify: `tests/core/test_path_safety.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/core/test_path_safety.py`:

```python
from orca.core.path_safety import validate_repo_dir


class TestValidateRepoDir:
    def test_happy_path_returns_resolved(self, tmp_path: Path):
        d = tmp_path / "feature-001"
        d.mkdir()
        result = validate_repo_dir(d, root=tmp_path, field="--feature-dir")
        assert result == d.resolve()

    def test_rejects_symlink(self, tmp_path: Path):
        real = tmp_path / "real-dir"
        real.mkdir()
        link = tmp_path / "link-dir"
        link.symlink_to(real, target_is_directory=True)
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_dir(link, root=tmp_path, field="--feature-dir")
        assert exc_info.value.rule_violated == "symlink_in_resolved_path"

    def test_rejects_path_outside_root(self, tmp_path: Path):
        outside = tmp_path.parent / "outside-dir"
        outside.mkdir()
        try:
            with pytest.raises(PathSafetyError) as exc_info:
                validate_repo_dir(outside, root=tmp_path, field="--feature-dir")
            assert exc_info.value.rule_violated == "path_outside_root"
        finally:
            outside.rmdir()

    def test_rejects_regular_file(self, tmp_path: Path):
        f = tmp_path / "file.md"
        f.write_text("hi")
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_dir(f, root=tmp_path, field="--feature-dir")
        assert exc_info.value.rule_violated == "not_a_directory"

    def test_rejects_missing_when_must_exist(self, tmp_path: Path):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_repo_dir(tmp_path / "missing", root=tmp_path, field="--feature-dir")
        assert exc_info.value.rule_violated == "does_not_exist"

    def test_must_exist_false_allows_missing(self, tmp_path: Path):
        result = validate_repo_dir(
            tmp_path / "future-dir", root=tmp_path,
            field="--feature-dir", must_exist=False,
        )
        assert result == (tmp_path / "future-dir").resolve()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/core/test_path_safety.py::TestValidateRepoDir -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `validate_repo_dir`**

Append to `src/orca/core/path_safety.py`:

```python
def validate_repo_dir(
    path: "str | Path",
    *,
    root: Path,
    field: str,
    must_exist: bool = True,
) -> Path:
    """Validate a Class A path that must point at a directory.

    Same containment + symlink rules as validate_repo_file. No size cap
    (directories don't have meaningful sizes for this contract). Returns
    the resolved Path. Raises PathSafetyError on violation.
    """
    resolved = _resolve_and_check_symlink(Path(path), field=field)
    _check_root_containment(resolved, root, field=field)

    if not must_exist:
        return resolved

    if not resolved.exists():
        raise PathSafetyError(
            f"path does not exist: {resolved}",
            field=field,
            rule_violated="does_not_exist",
            value_redacted=str(resolved),
        )
    if not resolved.is_dir():
        raise PathSafetyError(
            f"not a directory: {resolved}",
            field=field,
            rule_violated="not_a_directory",
            value_redacted=str(resolved),
        )
    return resolved
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/core/test_path_safety.py -v`
Expected: PASS, 27 tests total.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/path_safety.py tests/core/test_path_safety.py
git commit -m "feat(core/path_safety): add validate_repo_dir for Class A dirs"
```

---

## Task 5: `validate_findings_file` (Class C)

**Files:**
- Modify: `src/orca/core/path_safety.py`
- Modify: `tests/core/test_path_safety.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/core/test_path_safety.py`:

```python
from orca.core.path_safety import validate_findings_file


class TestValidateFindingsFile:
    def test_happy_path_returns_resolved(self, tmp_path: Path):
        f = tmp_path / "findings.json"
        f.write_text("[]")
        result = validate_findings_file(f, root=tmp_path, field="--claude-findings-file")
        assert result == f.resolve()

    def test_rejects_symlink(self, tmp_path: Path):
        real = tmp_path / "real.json"
        real.write_text("[]")
        link = tmp_path / "link.json"
        link.symlink_to(real)
        with pytest.raises(PathSafetyError) as exc_info:
            validate_findings_file(link, root=tmp_path, field="--claude-findings-file")
        assert exc_info.value.rule_violated == "symlink_in_resolved_path"

    def test_rejects_dangling_symlink(self, tmp_path: Path):
        link = tmp_path / "dangling.json"
        link.symlink_to(tmp_path / "missing.json")
        with pytest.raises(PathSafetyError) as exc_info:
            validate_findings_file(link, root=tmp_path, field="--claude-findings-file")
        assert exc_info.value.rule_violated == "symlink_in_resolved_path"

    def test_rejects_missing(self, tmp_path: Path):
        with pytest.raises(PathSafetyError) as exc_info:
            validate_findings_file(
                tmp_path / "missing.json", root=tmp_path, field="--claude-findings-file"
            )
        assert exc_info.value.rule_violated == "does_not_exist"

    def test_rejects_directory(self, tmp_path: Path):
        d = tmp_path / "subdir"
        d.mkdir()
        with pytest.raises(PathSafetyError) as exc_info:
            validate_findings_file(d, root=tmp_path, field="--claude-findings-file")
        assert exc_info.value.rule_violated == "not_a_regular_file"

    def test_rejects_oversized(self, tmp_path: Path):
        f = tmp_path / "big.json"
        f.write_bytes(b"x" * 1024)
        with pytest.raises(PathSafetyError) as exc_info:
            validate_findings_file(
                f, root=tmp_path, field="--claude-findings-file", max_bytes=512
            )
        assert exc_info.value.rule_violated == "size_cap_exceeded"

    def test_rejects_path_outside_root(self, tmp_path: Path):
        outside = tmp_path.parent / "escape.json"
        outside.write_text("[]")
        try:
            with pytest.raises(PathSafetyError) as exc_info:
                validate_findings_file(
                    outside, root=tmp_path, field="--claude-findings-file"
                )
            assert exc_info.value.rule_violated == "path_outside_root"
        finally:
            outside.unlink(missing_ok=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/core/test_path_safety.py::TestValidateFindingsFile -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `validate_findings_file`**

Append to `src/orca/core/path_safety.py`:

```python
def validate_findings_file(
    path: "str | Path",
    *,
    root: Path,
    field: str,
    max_bytes: int = 10 * 1024 * 1024,
) -> Path:
    """Validate a Class C findings-file path (path-shape only).

    No must_exist parameter: findings files are always read-only consumed
    by orca (the host LLM authors them out-of-band before orca runs), so
    a missing file is always a violation. Content-layer validation (JSON
    parse, schema) stays in the calling module.
    """
    return validate_repo_file(
        path, root=root, field=field, must_exist=True, max_bytes=max_bytes,
    )
```

(The Class C contract has the same path-shape rules as Class A files. Sharing the implementation keeps the surface honest. The behavioral distinction lives in the *consumer*, which raises `malformed_findings_file` after content parsing.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/core/test_path_safety.py -v`
Expected: PASS, 34 tests total.

- [ ] **Step 5: Commit**

```bash
git add src/orca/core/path_safety.py tests/core/test_path_safety.py
git commit -m "feat(core/path_safety): add validate_findings_file for Class C"
```

---

## Task 6: Extend `_err_envelope` with `detail` parameter

**Files:**
- Modify: `src/orca/python_cli.py:323-334`
- Test: `tests/cli/test_python_cli_err_envelope.py` (new)

- [ ] **Step 1: Write failing test**

Create `tests/cli/test_python_cli_err_envelope.py`:

```python
"""Tests for _err_envelope detail-passthrough.

Verifies that path-safety failures can attach structured detail
(field/rule_violated/value_redacted) to the INPUT_INVALID envelope.
"""
from __future__ import annotations

from orca.core.errors import ErrorKind
from orca.python_cli import _err_envelope


def test_err_envelope_without_detail_omits_detail_key():
    env = _err_envelope("cap", "1.0.0", ErrorKind.INPUT_INVALID, "boom")
    assert env["error"]["kind"] == "input_invalid"
    assert env["error"]["message"] == "boom"
    assert "detail" not in env["error"]


def test_err_envelope_with_detail_includes_detail_dict():
    env = _err_envelope(
        "cap", "1.0.0", ErrorKind.INPUT_INVALID, "boom",
        detail={"field": "--feature-id", "rule_violated": "identifier_format",
                "value_redacted": "bad/value"},
    )
    assert env["error"]["detail"] == {
        "field": "--feature-id",
        "rule_violated": "identifier_format",
        "value_redacted": "bad/value",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/cli/test_python_cli_err_envelope.py -v`
Expected: FAIL — `_err_envelope` rejects `detail` kwarg.

- [ ] **Step 3: Modify `_err_envelope`**

In `src/orca/python_cli.py`, replace the `_err_envelope` function (around line 323) with:

```python
def _err_envelope(
    capability: str,
    version: str,
    kind: ErrorKind,
    message: str,
    *,
    detail: dict | None = None,
) -> dict:
    """Build a CLI-side error envelope (e.g., for argparse failures).

    Routes through Err(Error).to_json so envelope shape stays consistent
    with capability-returned envelopes. duration_ms is 0 for CLI-side errors
    since no capability ran. Optional `detail` carries structured fields
    for path-safety violations (field/rule_violated/value_redacted).
    """
    return Err(Error(kind=kind, message=message, detail=detail)).to_json(
        capability=capability,
        version=version,
        duration_ms=0,
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run python -m pytest tests/cli/test_python_cli_err_envelope.py tests/cli/ -v`
Expected: PASS for new tests; existing CLI tests unaffected (existing 18+ callers don't pass `detail`).

- [ ] **Step 5: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_python_cli_err_envelope.py
git commit -m "feat(cli): _err_envelope accepts optional detail dict"
```

---

## Task 7: Migrate `_validate_findings_file_eagerly`

**Files:**
- Modify: `src/orca/python_cli.py:193-208` (cross-agent-review caller)
- Modify: `src/orca/python_cli.py:277-308` (replace `_validate_findings_file_eagerly`)
- Modify: `src/orca/python_cli.py:720-740` (contradiction-detector caller)
- Test: `tests/cli/test_cross_agent_review_findings_path_safety.py` (new)

- [ ] **Step 1: Write failing test for new envelope shape**

Create `tests/cli/test_cross_agent_review_findings_path_safety.py`:

```python
"""Path-safety regression tests for cross-agent-review findings-file flag."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_cli(args: list[str], cwd: Path) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", *args],
        cwd=str(cwd), capture_output=True, text=True,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, payload


def test_symlinked_findings_file_rejected_with_structured_detail(tmp_path: Path):
    feature_dir = tmp_path / "specs" / "001-foo"
    feature_dir.mkdir(parents=True)
    spec = feature_dir / "spec.md"
    spec.write_text("# spec\n", encoding="utf-8")

    real = feature_dir / "real-findings.json"
    real.write_text("[]", encoding="utf-8")
    link = feature_dir / "linked-findings.json"
    link.symlink_to(real)

    rc, payload = _run_cli(
        [
            "cross-agent-review",
            "--kind", "spec",
            "--target", str(spec),
            "--reviewer", "claude",
            "--feature-id", "001-foo",
            "--claude-findings-file", str(link),
            "--criteria", "feasibility",
        ],
        cwd=tmp_path,
    )
    assert rc != 0
    assert payload["ok"] is False
    err = payload["error"]
    assert err["kind"] == "input_invalid"
    assert err["detail"]["field"] == "--claude-findings-file"
    assert err["detail"]["rule_violated"] == "symlink_in_resolved_path"
    assert "linked-findings.json" in err["detail"]["value_redacted"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/cli/test_cross_agent_review_findings_path_safety.py -v`
Expected: FAIL — current envelope has no `detail.rule_violated`.

- [ ] **Step 3: Replace `_validate_findings_file_eagerly`**

In `src/orca/python_cli.py`, replace the function at line 277-308 with:

```python
def _validate_findings_file_eagerly(
    path_str: str, *, root: Path, field: str,
) -> tuple[str | None, dict | None]:
    """Pre-flight validation for --*-findings-file paths.

    Path-shape checks delegate to orca.core.path_safety.validate_findings_file.
    Content-layer checks (JSON parse, array shape, finding schema) stay here
    because they emit distinct rule_violated values.

    Returns (error_message, detail_dict_or_None) — None on success.
    """
    from orca.core.path_safety import PathSafetyError, validate_findings_file

    try:
        path = validate_findings_file(path_str, root=root, field=field)
    except PathSafetyError as exc:
        return str(exc), exc.to_error_detail()

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"read error ({exc}): {path}", {
            "field": field, "rule_violated": "missing_findings_file",
            "value_redacted": str(path),
        }
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"invalid JSON ({exc}): {path}", {
            "field": field, "rule_violated": "malformed_findings_file",
            "value_redacted": str(path),
        }
    if not isinstance(data, list):
        return f"expected JSON array, got {type(data).__name__}: {path}", {
            "field": field, "rule_violated": "malformed_findings_file",
            "value_redacted": str(path),
        }
    try:
        validate_findings_array(data, source="cli-preflight")
    except Exception as exc:
        return f"finding validation failed ({exc}): {path}", {
            "field": field, "rule_violated": "malformed_findings_file",
            "value_redacted": str(path),
        }
    return None, None
```

- [ ] **Step 4: Update both callers to pass `root` and consume detail**

In `src/orca/python_cli.py`, find the cross-agent-review caller (~line 193) and replace:

```python
    # Pre-flight validation for findings-file flags. Per the Phase 4a spec
    # error-handling table, every file-flag failure mode (missing, symlink,
    # oversized, malformed JSON, non-array, bad finding shape) MUST surface
    # as Err(INPUT_INVALID, "<slot>: <reason>") with exit 1.
    findings_root = Path.cwd().resolve()
    for slot, path_str in (
        ("--claude-findings-file", ns.claude_findings_file),
        ("--codex-findings-file", ns.codex_findings_file),
    ):
        if not path_str:
            continue
        err_msg, detail = _validate_findings_file_eagerly(
            path_str, root=findings_root, field=slot,
        )
        if err_msg is not None:
            return _emit_envelope(
                envelope=_err_envelope(
                    "cross-agent-review", CROSS_AGENT_REVIEW_VERSION,
                    ErrorKind.INPUT_INVALID, f"{slot}: {err_msg}",
                    detail=detail,
                ),
                pretty=ns.pretty,
                exit_code=1,
            )
```

In the contradiction-detector caller (~line 720), apply the same pattern:

```python
    findings_root = Path.cwd().resolve()
    for slot, path_str in (
        ("--claude-findings-file", ns.claude_findings_file),
        ("--codex-findings-file", ns.codex_findings_file),
    ):
        if not path_str:
            continue
        err_msg, detail = _validate_findings_file_eagerly(
            path_str, root=findings_root, field=slot,
        )
        if err_msg is not None:
            return _emit_envelope(
                envelope=_err_envelope(
                    "contradiction-detector", CONTRADICTION_DETECTOR_VERSION,
                    ErrorKind.INPUT_INVALID, f"{slot}: {err_msg}",
                    detail=detail,
                ),
                pretty=ns.pretty,
                exit_code=1,
            )
```

- [ ] **Step 5: Run tests**

Run: `uv run python -m pytest tests/cli/ -v`
Expected: new test PASSES; pre-existing CLI tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_cross_agent_review_findings_path_safety.py
git commit -m "refactor(cli): findings-file pre-flight uses path_safety helpers"
```

---

## Task 8: Migrate `_validate_feature_id` → `validate_identifier`

**Files:**
- Modify: `src/orca/python_cli.py:1158-1170` (resolve-path caller)
- Modify: `src/orca/python_cli.py:1222-1237` (delete `_validate_feature_id` and `_FEATURE_ID_RE`)
- Test: `tests/cli/test_resolve_path_cli.py` (extend)

- [ ] **Step 1: Write failing test**

Append to `tests/cli/test_resolve_path_cli.py`:

```python
def test_resolve_path_rejects_traversal_feature_id(tmp_path: Path, run_cli):
    rc, payload = run_cli(["resolve-path", "--kind", "feature-dir", "--feature-id", ".."], cwd=tmp_path)
    assert rc != 0
    err = payload["error"]
    assert err["kind"] == "input_invalid"
    assert err["detail"]["rule_violated"] == "identifier_reserved"
    assert err["detail"]["field"] == "--feature-id"


def test_resolve_path_rejects_slash_in_feature_id(tmp_path: Path, run_cli):
    rc, payload = run_cli(
        ["resolve-path", "--kind", "feature-dir", "--feature-id", "foo/bar"], cwd=tmp_path,
    )
    assert rc != 0
    err = payload["error"]
    assert err["detail"]["rule_violated"] == "identifier_format"
```

(If `tests/cli/test_resolve_path_cli.py` does not yet have a `run_cli` fixture, add one inline using the same `subprocess.run([sys.executable, "-m", "orca.python_cli", ...])` pattern as Task 7.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/cli/test_resolve_path_cli.py -v -k "traversal_feature_id or slash_in_feature_id"`
Expected: FAIL — current envelope has plain message string, no `detail`.

- [ ] **Step 3: Migrate the caller in `_run_resolve_path`**

In `src/orca/python_cli.py` around line 1159-1170 (the `if ns.feature_id is not None:` block), replace with:

```python
    if ns.feature_id is not None:
        from orca.core.path_safety import PathSafetyError, validate_identifier
        try:
            validate_identifier(ns.feature_id, field="--feature-id")
        except PathSafetyError as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "resolve-path", "1.0.0",
                    ErrorKind.INPUT_INVALID, str(exc),
                    detail=exc.to_error_detail(),
                ),
                pretty=ns.pretty,
                exit_code=1,
            )
```

- [ ] **Step 4: Delete `_validate_feature_id` and `_FEATURE_ID_RE`**

In `src/orca/python_cli.py`, delete the entire block at lines 1222-1237:

```python
_FEATURE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_feature_id(value: str) -> str | None:
    """Per path-safety contract Class D. Returns error message or None."""
    if not value:
        return "--feature-id is empty"
    ...
    return None
```

If `re` is unused after this deletion, remove its import as well.

- [ ] **Step 5: Run tests**

Run: `uv run python -m pytest tests/cli/test_resolve_path_cli.py -v`
Expected: all tests PASS, including new ones.

- [ ] **Step 6: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_resolve_path_cli.py
git commit -m "refactor(cli): resolve-path uses validate_identifier; drop local validator"
```

---

## Task 9: Add `--feature-id` validation to cross-agent-review and flow-state-projection

**Files:**
- Modify: `src/orca/python_cli.py:_run_cross_agent_review` (~line 184, after argparse parses)
- Modify: `src/orca/python_cli.py:_run_flow_state_projection` (~line 470, after argparse parses)
- Test: `tests/cli/test_cross_agent_review_findings_path_safety.py` (extend)

- [ ] **Step 1: Write failing test**

Append to `tests/cli/test_cross_agent_review_findings_path_safety.py`:

```python
def test_cross_agent_review_rejects_traversal_feature_id(tmp_path: Path):
    spec = tmp_path / "spec.md"
    spec.write_text("# spec\n")
    rc, payload = _run_cli(
        [
            "cross-agent-review",
            "--kind", "spec",
            "--target", str(spec),
            "--reviewer", "claude",
            "--feature-id", "..",
            "--criteria", "feasibility",
        ],
        cwd=tmp_path,
    )
    assert rc != 0
    err = payload["error"]
    assert err["detail"]["field"] == "--feature-id"
    assert err["detail"]["rule_violated"] == "identifier_reserved"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/cli/test_cross_agent_review_findings_path_safety.py::test_cross_agent_review_rejects_traversal_feature_id -v`
Expected: FAIL — currently no validation; the `..` reaches downstream code.

- [ ] **Step 3: Add validation after argparse in `_run_cross_agent_review`**

In `src/orca/python_cli.py` inside `_run_cross_agent_review`, immediately after the `if unknown:` argparse-error block (before the findings-file pre-flight, ~line 185), add:

```python
    if ns.feature_id is not None:
        from orca.core.path_safety import PathSafetyError, validate_identifier
        try:
            validate_identifier(ns.feature_id, field="--feature-id")
        except PathSafetyError as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "cross-agent-review", CROSS_AGENT_REVIEW_VERSION,
                    ErrorKind.INPUT_INVALID, str(exc),
                    detail=exc.to_error_detail(),
                ),
                pretty=ns.pretty,
                exit_code=1,
            )
```

- [ ] **Step 4: Add same block to `_run_flow_state_projection`**

In `src/orca/python_cli.py` inside `_run_flow_state_projection`, immediately after the `if unknown:` argparse-error block:

```python
    if ns.feature_id is not None:
        from orca.core.path_safety import PathSafetyError, validate_identifier
        try:
            validate_identifier(ns.feature_id, field="--feature-id")
        except PathSafetyError as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "flow-state-projection", FLOW_STATE_PROJECTION_VERSION,
                    ErrorKind.INPUT_INVALID, str(exc),
                    detail=exc.to_error_detail(),
                ),
                pretty=ns.pretty,
                exit_code=1,
            )
```

(If a similar `if ns.feature_id is not None` already exists in flow-state, replace it; otherwise add it.)

- [ ] **Step 5: Run tests**

Run: `uv run python -m pytest tests/cli/ -v`
Expected: new test PASSES; pre-existing cross-agent-review and flow-state tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_cross_agent_review_findings_path_safety.py
git commit -m "feat(cli): validate --feature-id in cross-agent-review and flow-state"
```

---

## Task 10: Validate `--target` (cross-agent-review)

**Files:**
- Modify: `src/orca/python_cli.py:_run_cross_agent_review` (after feature-id validation)
- Test: `tests/cli/test_cross_agent_review_findings_path_safety.py` (extend)

- [ ] **Step 1: Write failing tests**

Append to `tests/cli/test_cross_agent_review_findings_path_safety.py`:

```python
def test_cross_agent_review_rejects_symlinked_target(tmp_path: Path):
    real = tmp_path / "real-spec.md"
    real.write_text("# spec\n")
    link = tmp_path / "link-spec.md"
    link.symlink_to(real)

    rc, payload = _run_cli(
        [
            "cross-agent-review",
            "--kind", "spec",
            "--target", str(link),
            "--reviewer", "claude",
            "--criteria", "feasibility",
        ],
        cwd=tmp_path,
    )
    assert rc != 0
    err = payload["error"]
    assert err["detail"]["field"] == "--target"
    assert err["detail"]["rule_violated"] == "symlink_in_resolved_path"


def test_cross_agent_review_rejects_target_outside_repo(tmp_path: Path):
    # Target outside the cwd-rooted tree
    outside = tmp_path.parent / "escape.md"
    outside.write_text("# escape\n")
    inside_repo = tmp_path / "repo"
    inside_repo.mkdir()
    try:
        rc, payload = _run_cli(
            [
                "cross-agent-review",
                "--kind", "spec",
                "--target", str(outside),
                "--reviewer", "claude",
                "--criteria", "feasibility",
            ],
            cwd=inside_repo,
        )
        assert rc != 0
        assert payload["error"]["detail"]["rule_violated"] == "path_outside_root"
    finally:
        outside.unlink(missing_ok=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/cli/test_cross_agent_review_findings_path_safety.py -v -k target`
Expected: FAIL — currently `--target` skips path-safety at the CLI boundary.

- [ ] **Step 3: Add target validation in `_run_cross_agent_review`**

After the `--feature-id` validation block from Task 9, add:

```python
    target_root = Path.cwd().resolve()
    from orca.core.path_safety import (
        PathSafetyError, validate_repo_dir, validate_repo_file,
    )
    for t in ns.target:
        try:
            t_path = Path(t).resolve()
            if t_path.is_dir():
                validate_repo_dir(t, root=target_root, field="--target")
            else:
                validate_repo_file(t, root=target_root, field="--target")
        except PathSafetyError as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "cross-agent-review", CROSS_AGENT_REVIEW_VERSION,
                    ErrorKind.INPUT_INVALID, str(exc),
                    detail=exc.to_error_detail(),
                ),
                pretty=ns.pretty,
                exit_code=1,
            )
```

(The `t_path.is_dir()` post-resolve dispatch picks the right validator.
The validator then re-resolves the input — this is intentional defense
in depth, not a redundancy.)

- [ ] **Step 4: Run tests**

Run: `uv run python -m pytest tests/cli/ -v`
Expected: new tests PASS; pre-existing PASS.

- [ ] **Step 5: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_cross_agent_review_findings_path_safety.py
git commit -m "feat(cli): validate --target paths in cross-agent-review"
```

---

## Task 11: Validate `--prior-evidence` (contradiction-detector) and `--feature-dir` (completion-gate)

**Files:**
- Modify: `src/orca/python_cli.py:_run_contradiction_detector` (after argparse)
- Modify: `src/orca/python_cli.py:_run_completion_gate` (after argparse)
- Test: `tests/cli/test_cli_path_safety_misc.py` (new)

- [ ] **Step 1: Write failing tests**

Create `tests/cli/test_cli_path_safety_misc.py`:

```python
"""Path-safety regression tests for misc CLI flags."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_cli(args: list[str], cwd: Path) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", *args],
        cwd=str(cwd), capture_output=True, text=True,
    )
    payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, payload


def test_contradiction_detector_rejects_symlinked_prior_evidence(tmp_path: Path):
    new = tmp_path / "new.md"
    new.write_text("# new")
    real = tmp_path / "real.md"
    real.write_text("# real")
    link = tmp_path / "link.md"
    link.symlink_to(real)

    rc, payload = _run_cli(
        [
            "contradiction-detector",
            "--new-content", str(new),
            "--prior-evidence", str(link),
            "--reviewer", "claude",
        ],
        cwd=tmp_path,
    )
    assert rc != 0
    err = payload["error"]
    assert err["detail"]["field"] == "--prior-evidence"
    assert err["detail"]["rule_violated"] == "symlink_in_resolved_path"


def test_completion_gate_rejects_symlinked_feature_dir(tmp_path: Path):
    real = tmp_path / "real-feature"
    real.mkdir()
    link = tmp_path / "link-feature"
    link.symlink_to(real, target_is_directory=True)

    rc, payload = _run_cli(
        [
            "completion-gate",
            "--feature-dir", str(link),
            "--target-stage", "spec",
        ],
        cwd=tmp_path,
    )
    assert rc != 0
    err = payload["error"]
    assert err["detail"]["field"] == "--feature-dir"
    assert err["detail"]["rule_violated"] == "symlink_in_resolved_path"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/cli/test_cli_path_safety_misc.py -v`
Expected: FAIL — neither flag validates symlinks today.

- [ ] **Step 3: Add `--prior-evidence` validation in `_run_contradiction_detector`**

After the `if unknown:` block in `_run_contradiction_detector`, add:

```python
    evidence_root = Path.cwd().resolve()
    from orca.core.path_safety import PathSafetyError, validate_repo_file
    for ev in ns.prior_evidence:
        try:
            validate_repo_file(ev, root=evidence_root, field="--prior-evidence")
        except PathSafetyError as exc:
            return _emit_envelope(
                envelope=_err_envelope(
                    "contradiction-detector", CONTRADICTION_DETECTOR_VERSION,
                    ErrorKind.INPUT_INVALID, str(exc),
                    detail=exc.to_error_detail(),
                ),
                pretty=ns.pretty,
                exit_code=1,
            )
```

- [ ] **Step 4: Add `--feature-dir` validation in `_run_completion_gate`**

After the `if unknown:` block in `_run_completion_gate`, add:

```python
    feature_root = Path.cwd().resolve()
    from orca.core.path_safety import PathSafetyError, validate_repo_dir
    try:
        validate_repo_dir(ns.feature_dir, root=feature_root, field="--feature-dir")
    except PathSafetyError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "completion-gate", COMPLETION_GATE_VERSION,
                ErrorKind.INPUT_INVALID, str(exc),
                detail=exc.to_error_detail(),
            ),
            pretty=ns.pretty,
            exit_code=1,
        )
```

- [ ] **Step 5: Run tests**

Run: `uv run python -m pytest tests/cli/ -v`
Expected: new tests PASS; pre-existing tests for contradiction-detector and completion-gate still PASS.

- [ ] **Step 6: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_cli_path_safety_misc.py
git commit -m "feat(cli): validate --prior-evidence and --feature-dir paths"
```

---

## Task 12: Migrate `FileBackedReviewer` to `validate_findings_file`

**Files:**
- Modify: `src/orca/core/reviewers/file_backed.py:25-83`
- Modify: `tests/core/reviewers/test_file_backed.py` (verify assertions still match)

- [ ] **Step 1: Read existing test assertions to ensure compat**

Run: `uv run python -m pytest tests/core/reviewers/test_file_backed.py -v`
Expected: all current tests PASS at baseline (this is just to verify starting state).

- [ ] **Step 2: Modify `FileBackedReviewer.review`**

In `src/orca/core/reviewers/file_backed.py`, replace lines 39-58 (the path-shape checks) with a delegation to `validate_findings_file`:

```python
    def review(self, bundle: ReviewBundle, prompt: str) -> RawFindings:
        # bundle and prompt are part of the adapter interface; ignored here
        # because findings are pre-authored. Caller is responsible for using
        # a matching prompt + subject when authoring the file.
        from orca.core.path_safety import (
            PathSafetyError, validate_findings_file,
        )
        path = self.findings_path
        try:
            path = validate_findings_file(
                path,
                root=path.parent.resolve() if path.is_absolute() else Path.cwd().resolve(),
                field="findings_path",
                max_bytes=MAX_FILE_BYTES,
            )
        except PathSafetyError as exc:
            # Map rule_violated to underlying for adapter consistency.
            underlying_map = {
                "symlink_in_resolved_path": "symlink_rejected",
                "does_not_exist": "file_not_found",
                "size_cap_exceeded": "file_too_large",
                "not_a_regular_file": "not_a_regular_file",
                "path_outside_root": "path_outside_root",
            }
            raise ReviewerError(
                f"file-backed reviewer: {exc}",
                retryable=False,
                underlying=underlying_map.get(exc.rule_violated, "input_invalid"),
            ) from exc

        text = path.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ReviewerError(
                f"file-backed reviewer: invalid JSON in {path}: {exc}",
                retryable=False,
                underlying="invalid_json",
            ) from exc
        if not isinstance(data, list):
            raise ReviewerError(
                f"file-backed reviewer: expected JSON array, got {type(data).__name__}",
                retryable=False,
                underlying="not_an_array",
            ) from None
        findings = validate_findings_array(data, source=f"file-backed:{self.name}")
        return RawFindings(
            reviewer=self.name,
            findings=findings,
            metadata={
                "source": _METADATA_SOURCE,
                "findings_path": str(path),
            },
        )
```

(`root=path.parent.resolve()` is the lowest-blast-radius default for this internal adapter — the host harness has already chosen the directory to write into, so requiring containment in that same directory enforces the contract without breaking existing call sites that pass arbitrary feature-dir locations. The CLI pre-flight in Task 7 enforces a stricter `root=cwd` boundary at the entry point.)

- [ ] **Step 3: Run tests**

Run: `uv run python -m pytest tests/core/reviewers/test_file_backed.py -v`
Expected: all tests PASS. The existing `with pytest.raises(ReviewerError, match="symlinks rejected")` assertion still matches because the wrapping `ReviewerError` message contains the original `PathSafetyError` string.

- [ ] **Step 4: If any assertion fails on string match, update**

If `test_file_backed_reviewer_rejects_symlink` or `test_file_backed_reviewer_rejects_dangling_symlink` fails, change the regex:

```python
with pytest.raises(ReviewerError, match="symlinks rejected"):
```

to:

```python
with pytest.raises(ReviewerError, match="symlink"):
```

This stays compatible with both the old wording (`"symlinks rejected: <path>"`) and the new wrapped wording (`"file-backed reviewer: symlinks rejected in resolved path: <path>"`).

- [ ] **Step 5: Run full test suite**

Run: `uv run python -m pytest -x`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/orca/core/reviewers/file_backed.py tests/core/reviewers/test_file_backed.py
git commit -m "refactor(reviewers): FileBackedReviewer delegates to path_safety"
```

---

## Task 13: Final regression sweep + contract reference

**Files:**
- Modify: `docs/superpowers/contracts/path-safety.md` (update implementation status)

- [ ] **Step 1: Run full test suite**

Run: `uv run python -m pytest`
Expected: all tests PASS (baseline 462 + ~22 new = ~484+).

- [ ] **Step 2: Run `uv run python -m orca.python_cli --help` smoke test**

Expected: no import errors, all subcommands listed.

- [ ] **Step 3: Update implementation status in the contract doc**

In `docs/superpowers/contracts/path-safety.md`, replace the "Implementation status (as of 2026-04-29)" section with:

```markdown
## Implementation status (as of 2026-04-30)

- **Shared module `orca.core.path_safety`** ships `PathSafetyError` and four validators (`validate_repo_file`, `validate_repo_dir`, `validate_findings_file`, `validate_identifier`). All Class A/C/D path validation at the orca CLI boundary delegates to this module.
- **Class B (`/shared/`) validation**: not yet implemented. Will land alongside perf-lab integration when that work resumes.
- **Internal helpers** (`session.py`, `context_handoffs.py`, `sdd_adapter.py`, `flow_state.py`, `brainstorm_memory.py`) operate on already-validated paths per the "validate at boundary" principle and do not re-validate.
- **`_err_envelope`** in `python_cli.py` accepts an optional `detail` dict; path-safety failures populate it with `{field, rule_violated, value_redacted}` per this contract.
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/contracts/path-safety.md
git commit -m "docs(contracts): path-safety implementation status reflects consolidation"
```

---

## Self-review checklist

After all tasks ship, verify:

1. **Spec coverage:**
   - Module API ✅ (Tasks 1-5)
   - `_err_envelope` extension ✅ (Task 6)
   - 5 migration sites — adapted to current flag inventory ✅ (Tasks 7, 8, 9, 10, 11, 12 = 6 sites; counts findings-file as one site with two callers)
   - Tests ~22 new + ~5 modified ✅
   - Out-of-scope items (Class B, internal helpers, doctor warning) intentionally omitted ✅

2. **Type/signature consistency:**
   - `validate_repo_file(path, *, root, field, must_exist=True, max_bytes=...)` consistent across Tasks 3, 5, 7, 10, 11, 12.
   - `validate_repo_dir(path, *, root, field, must_exist=True)` consistent across Tasks 4, 10, 11.
   - `validate_identifier(value, *, field, max_length=128)` consistent across Tasks 2, 8, 9.
   - `_err_envelope(..., *, detail=None)` consistent across all migration callers.
   - `PathSafetyError(message, *, field, rule_violated, value_redacted).to_error_detail()` consistent.

3. **No placeholders:** all code blocks complete; all commands explicit.
