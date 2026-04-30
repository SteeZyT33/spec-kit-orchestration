# Orca Path-Safety Consolidation — Design

**Date:** 2026-04-30
**Status:** Design (pre-implementation)
**Scope:** Build `orca.core.path_safety` shared module; migrate Class A/C/D path validation at CLI boundaries to use it.
**Out of scope:** Class B (`/shared/`) validation — deferred until perf-lab integration ships. Internal-helper migration — deferred per "validate at boundary" principle.
**References:** `docs/superpowers/contracts/path-safety.md` (the contract this design enforces).

## Goal

The path-safety contract (`docs/superpowers/contracts/path-safety.md`) defines four path classes (A/B/C/D) and six core invariants. Today, validation is implemented ad-hoc across capability code:

- `src/orca/core/reviewers/file_backed.py:40-58` — symlink/exists/size checks for findings-file
- `src/orca/python_cli.py:277-308` `_validate_findings_file_eagerly` — duplicates the above with different error wrapping
- No `--feature-id` validation anywhere; bad identifiers reach `host_layout.resolve_feature_dir()` and produce confusing downstream errors
- No symlink/containment check on `--target` (cross-agent-review) at the CLI boundary

The contract's "Implementation status" section explicitly tracks this consolidation as a follow-up. This design lands the shared module and migrates the CLI boundary.

## Non-goals

- Migrating internal helpers (`session.py`, `context_handoffs.py`, `sdd_adapter.py`, `flow_state.py`, `brainstorm_memory.py`). They operate on already-validated paths per the contract's "internal helpers do not re-validate" clause.
- Class B `/shared/` validation — no `validate_shared_*` function until perf-lab integration ships.
- Extending the `Error` class with top-level `field` / `rule_violated` attrs — structured fields live in `Error.detail`.
- Plugin-side (slash command bash block) validation — slash commands pass arguments to `orca-cli`, which validates. Python-side only.

## Architecture

**New module: `src/orca/core/path_safety.py`** (~150 LOC, single file). Pure functions plus one exception class. No new dependencies (stdlib only: `pathlib`, `re`, `os`).

**Composition.** Capabilities and CLI handlers call helpers at their entry points. Helpers raise `PathSafetyError` on contract violation. Capability boundaries (in `python_cli.py` argparse handlers) catch the exception and convert to `Err(Error(kind=INPUT_INVALID, message=..., detail={...}))`. Internal helpers — paths that already passed through the boundary — do not call path_safety.

**Why exception, not Result.** Validation stops on first violation; you do not accumulate. Returning `Result` from every helper would be noisy and would force every call site to unpack. Exception-shaped is the natural fit, and the capability boundary converts once.

## Module API

```python
# src/orca/core/path_safety.py

class PathSafetyError(Exception):
    """Raised by path_safety helpers on contract violation.

    Carries structured fields suitable for INPUT_INVALID error envelopes.
    Capability boundaries catch this and convert to Err(Error).
    """
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


def validate_repo_file(
    path: str | Path,
    *,
    root: Path,
    field: str,
    must_exist: bool = True,
    max_bytes: int = 10 * 1024 * 1024,
) -> Path:
    """Validate a Class A path that must point at a regular file.

    Resolves to absolute, rejects symlinks, enforces containment in `root`,
    enforces regular-file type if `must_exist`, enforces size cap.
    Returns the resolved Path. Raises PathSafetyError on violation.
    """


def validate_repo_dir(
    path: str | Path,
    *,
    root: Path,
    field: str,
    must_exist: bool = True,
) -> Path:
    """Validate a Class A path that must point at a directory.

    Same containment + symlink rules as validate_repo_file. Returns the
    resolved Path. Raises PathSafetyError on violation.
    """


def validate_findings_file(
    path: str | Path,
    *,
    root: Path,
    field: str,
    max_bytes: int = 10 * 1024 * 1024,
) -> Path:
    """Validate a Class C findings-file path (path-shape only).

    No `must_exist` parameter: findings files are always read-only consumed
    by orca (the host LLM authors them out-of-band before orca runs), so a
    missing file is always a violation. Content-layer validation (JSON parse,
    schema) stays in the calling module — `malformed_findings_file` and
    `not_an_array` are raised by the consumer, not by this helper.

    `root` is typically the feature directory in Phase 4a contexts.
    """


def validate_identifier(
    value: str,
    *,
    field: str,
    max_length: int = 128,
) -> str:
    """Validate a Class D identifier string.

    Matches `^[A-Za-z0-9._-]+$`, rejects `.`, `..`, empty, leading `-`,
    length > max_length. Returns the value unchanged on success.
    """
```

### `rule_violated` enum

Mirrored from the contract; capability code MAY pattern-match on these values:

| Value | Meaning |
|-------|---------|
| `symlink_in_resolved_path` | Any path component traverses a symlink |
| `path_outside_root` | Resolved path is not contained in declared root |
| `not_a_regular_file` | Type-mismatched: regular file expected, got dir/socket/fifo |
| `not_a_directory` | Type-mismatched: directory expected, got file |
| `does_not_exist` | `must_exist=True` and path is absent |
| `size_cap_exceeded` | Regular file larger than `max_bytes` |
| `identifier_format` | Identifier did not match `[A-Za-z0-9._-]+` |
| `identifier_reserved` | Identifier equals `.` or `..` |
| `identifier_too_long` | Identifier length > `max_length` |
| `identifier_empty` | Empty string |

## Migration call-site map

**Migrate now (5 sites):**

1. **`src/orca/python_cli.py` `_validate_findings_file_eagerly`** — replace body with `validate_findings_file(...)`. Catch `PathSafetyError`, build INPUT_INVALID envelope with `detail=exc.to_error_detail()`. Removes ~30 LOC of inline checks.

2. **`src/orca/core/reviewers/file_backed.py` `FileBackedReviewer.review`** — call `validate_findings_file` for path-shape checks before reading. JSON-parse + schema-validate stay inline (content-layer codes `malformed_findings_file`, `not_an_array`). `ReviewerError` wraps `PathSafetyError` for adapter consistency.

3. **`--feature-id` argparse handlers** in `resolve-path`, `cross-agent-review`, `gate`, `cite`, `contradiction-detector` — call `validate_identifier(ns.feature_id, field="--feature-id")` immediately after parsing.

4. **`--target`** (cross-agent-review) — after resolving repo_root, call `validate_repo_file` or `validate_repo_dir` based on `Path.is_dir()` (post-resolve).

5. **`--evidence-path`** (repeatable) — loop, call `validate_repo_file` per entry.

**Not migrated** (per contract's boundary principle):
- `session.py`, `context_handoffs.py`, `sdd_adapter.py`, `flow_state.py`, `brainstorm_memory.py` — paths already passed through CLI/argparse boundaries.
- `host_layout/reference_set.py:30,41` — internal helper, documented as such.

## Error envelope mapping

`_err_envelope` gains an optional `detail: dict | None = None` parameter that flows into `Error(kind=..., message=..., detail=...)`. Existing eight callers pass nothing → no behavior change. New path-safety catch sites pass `detail=exc.to_error_detail()`.

Final envelope on stdout (matches the contract verbatim):

```json
{"ok": false, "capability": "cross-agent-review", "version": "...",
 "error": {"kind": "INPUT_INVALID",
           "message": "symlinks rejected: /home/.../findings.json",
           "detail": {"field": "--claude-findings-file",
                      "rule_violated": "symlink_in_resolved_path",
                      "value_redacted": "/home/.../findings.json"}},
 "duration_ms": 0}
```

`field` / `rule_violated` / `value_redacted` live under `error.detail` rather than as top-level envelope keys. The contract specifies the payload shape but does not pin top-level placement; nesting under `detail` keeps `Error.to_json()` unchanged and avoids a breaking change.

**`value_redacted` policy for v1:** echo `str(resolved_or_input_path)` as-is. The contract permits relativization of `$HOME`-prefixed paths "at the capability author's discretion" — for v1 we do not redact, since orca runs in the operator's own environment and absolute paths in error messages are diagnostic, not sensitive. Future redaction (e.g., for shipping logs to remote telemetry) is additive.

## Testing

**New: `tests/core/test_path_safety.py`** (~25 tests).

Per-function coverage. Each function gets:
- happy path (valid input → returns resolved Path or sanitized string)
- symlink rejection (`tmp_path` symlink → raises with `rule_violated="symlink_in_resolved_path"`)
- root containment violation (path outside root → `rule_violated="path_outside_root"`)
- type mismatch (directory passed to file-only → `rule_violated="not_a_regular_file"`)
- non-existence when `must_exist=True` → `rule_violated="does_not_exist"`
- size cap (file > `max_bytes` → `rule_violated="size_cap_exceeded"`)

`validate_identifier` extras: empty string (`identifier_empty`), `.` / `..` (`identifier_reserved`), leading `-` (`identifier_format`), special chars (`/`, `\0`, `..\foo` → `identifier_format`), length > 128 (`identifier_too_long`), valid edge cases (`feature_001`, `001-foo`, `a.b.c`).

Plus `PathSafetyError` structure tests: carries `field`, `rule_violated`, `value_redacted`; `to_error_detail()` returns the three-key dict.

**Regression tests on migrated sites:**

- `tests/cli/test_resolve_path_cli.py` — bad `--feature-id` (`..`, empty, `foo/bar`) → INPUT_INVALID envelope with `detail.rule_violated="identifier_reserved"` or `"identifier_format"`.
- Cross-agent-review CLI tests — symlinked `--claude-findings-file` → INPUT_INVALID with `detail.rule_violated="symlink_in_resolved_path"`. Symlinked `--target` rejected likewise.
- `tests/core/reviewers/test_file_backed.py` — symlink-reject path still works after delegating to `validate_findings_file`.

**Total:** ~22 new tests + ~5 modified.

## Implementation phases

Single PR, sequential within:

1. **Module + tests:** Build `path_safety.py`, write `test_path_safety.py`, get all 25 tests green. No call-site changes yet.
2. **`_err_envelope` extension:** Add `detail` parameter (default `None`). Existing callers unchanged.
3. **CLI migration (one site at a time):** findings-file → feature-id → target → evidence-path. Run regression suite after each.
4. **`FileBackedReviewer` migration:** delegate path-shape checks; keep content-layer checks inline. Run reviewer tests.
5. **Doctor breadcrumb (optional):** doctor script gets a one-line note that path-safety helpers are in use; not blocking for this PR.

Total estimate: ~200 LOC + tests, ~half day of focused work.

## Risk

Low. The module is additive (no removal until call sites migrate). Each migration is a small, independently-testable swap. The `_err_envelope` extension is backward-compatible. No public API changes; no consumer outside this repo depends on `Error.detail` shape.

The one place to be careful: `FileBackedReviewer` currently raises `ReviewerError` with `underlying="symlink_rejected"`. After migration it raises `ReviewerError` wrapping a `PathSafetyError`. Tests asserting on `underlying=` need to change to assert on the wrapped exception's `rule_violated`. That is the migration plan, not a regression — but it is the one place where assertion shapes change.
