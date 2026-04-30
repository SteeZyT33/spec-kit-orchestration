# Orca Phase 4a: In-Session Claude Reviewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the "Claude reviews itself via API" identity collapse with subagent-driven review when the host is Claude Code, using a file-backed reviewer adapter and orca-cli-side findings validation.

**Architecture:** Add `FileBackedReviewer` (loads pre-validated findings JSON from disk), two new orca-cli subcommands (`parse-subagent-response` for stdin-to-validated-JSON pipe, `build-review-prompt` for assembling the canonical review prompt), and `--claude-findings-file` / `--codex-findings-file` flags on `cross-agent-review`. The slash command dispatches a Claude Code subagent via the `Agent` tool, pipes the response through `parse-subagent-response`, then calls `cross-agent-review` with the file flag. orca-cli stays focused on capability dispatch + validation; subagent dispatch is the host LLM's responsibility.

**Tech Stack:** Python 3.11+ (existing orca toolchain), pytest, no new runtime deps. Validator reuses `parse_findings_array` from `src/orca/core/reviewers/_parse.py`.

**Worktree:** This plan should be executed on `orca-phase-3-plugin-formats` branch (stacked on PR #70). After Phase 3 merges to main, rebase onto main; expect possible rebase conflicts on the slash command markdown files.

**Spec:** `docs/superpowers/specs/2026-04-28-orca-phase-4a-in-session-reviewer-design.md` (commit `79ade18`).

---

## File Structure

**New files:**
- `src/orca/core/reviewers/file_backed.py` - `FileBackedReviewer` adapter (~50 lines)
- `tests/core/reviewers/test_file_backed.py` - 6 unit tests

**Modified files:**
- `src/orca/python_cli.py` - `_run_cross_agent_review` (new flags), `_load_reviewers` / `_build_reviewer` (file-flag precedence), new `_run_parse_subagent_response`, new `_run_build_review_prompt`, register both subcommands
- `tests/cli/test_python_cli.py` - extensions for the 3 surfaces (~12 tests added)
- `plugins/claude-code/commands/review-spec.md` - subagent dispatch step in Outline
- `plugins/claude-code/commands/review-code.md` - subagent dispatch step in step 8
- `plugins/claude-code/commands/review-pr.md` - subagent dispatch step in Cross-Pass Review section
- `plugins/codex/AGENTS.md` - document new subcommands + flags

**Why this layout:**
- `file_backed.py` is one focused module: read JSON file, validate, return RawFindings. No mixing with SDK adapter logic.
- Subcommand dispatcher functions (`_run_parse_subagent_response`, `_run_build_review_prompt`) live alongside other `_run_*` functions in `python_cli.py` matching established patterns.
- Tests split: `test_file_backed.py` for adapter unit tests, `test_python_cli.py` extensions for CLI surface tests.

---

## Task 1: FileBackedReviewer adapter

**Why first:** Smallest concrete change. Other tasks consume this. Pure unit-test-driven.

**Files:**
- Create: `src/orca/core/reviewers/file_backed.py`
- Create: `tests/core/reviewers/test_file_backed.py`

- [ ] **Step 1: Write failing test for happy path**

Create `tests/core/reviewers/test_file_backed.py`:

```python
"""Unit tests for FileBackedReviewer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orca.core.bundle import ReviewBundle
from orca.core.reviewers.base import ReviewerError
from orca.core.reviewers.file_backed import FileBackedReviewer


def _make_findings_file(tmp_path: Path, findings: list[dict]) -> Path:
    p = tmp_path / "claude-findings.json"
    p.write_text(json.dumps(findings), encoding="utf-8")
    return p


def _bundle() -> ReviewBundle:
    return ReviewBundle(kind="diff", subject="dummy")


def test_file_backed_reviewer_reads_valid_findings(tmp_path: Path) -> None:
    findings = [{
        "id": "abc1234567890def",
        "category": "correctness",
        "severity": "high",
        "confidence": "high",
        "summary": "test claim",
        "detail": "details",
        "evidence": ["src/foo.py:1"],
        "suggestion": "fix it",
        "reviewer": "claude",
    }]
    path = _make_findings_file(tmp_path, findings)
    reviewer = FileBackedReviewer(name="claude", findings_path=path)
    result = reviewer.review(_bundle(), prompt="ignored")
    assert result.reviewer == "claude"
    assert result.findings == findings
    assert result.metadata["source"] == "in-session-subagent"
    assert result.metadata["findings_path"] == str(path)
```

- [ ] **Step 2: Verify failure**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest tests/core/reviewers/test_file_backed.py -v`
Expected: ImportError or ModuleNotFoundError on `orca.core.reviewers.file_backed`.

- [ ] **Step 3: Create the module with minimal happy-path implementation**

Create `src/orca/core/reviewers/file_backed.py`:

```python
"""FileBackedReviewer: loads pre-validated findings from a JSON file.

Used when the host harness has authored the review out-of-band (typically via
subagent dispatch). orca-cli's `parse-subagent-response` subcommand is the
recommended way to produce these files.

The file MUST be a top-level JSON array of finding dicts. Schema validation
reuses `parse_findings_array` so the per-finding contract matches what the
SDK adapter produces today.
"""
from __future__ import annotations

import json
from pathlib import Path

from orca.core.bundle import ReviewBundle
from orca.core.reviewers._parse import parse_findings_array
from orca.core.reviewers.base import RawFindings, ReviewerError


_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB cap; findings JSON should never approach


class FileBackedReviewer:
    """Reviewer adapter that reads pre-authored findings from a JSON file."""

    name: str
    findings_path: Path

    def __init__(self, *, name: str, findings_path: Path) -> None:
        self.name = name
        self.findings_path = findings_path

    def review(self, bundle: ReviewBundle, prompt: str) -> RawFindings:
        # bundle and prompt are part of the adapter interface; ignored here
        # because findings are pre-authored. Caller is responsible for using
        # a matching prompt + subject when authoring the file.
        path = self.findings_path
        if not path.exists():
            raise ReviewerError(
                f"file-backed reviewer: file not found: {path}",
                retryable=False,
                underlying="file_not_found",
            )
        if path.is_symlink():
            raise ReviewerError(
                f"file-backed reviewer: symlinks rejected: {path}",
                retryable=False,
                underlying="symlink_rejected",
            )
        size = path.stat().st_size
        if size > _MAX_FILE_BYTES:
            raise ReviewerError(
                f"file-backed reviewer: file exceeds {_MAX_FILE_BYTES} byte cap: {size} bytes",
                retryable=False,
                underlying="file_too_large",
            )
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
            )
        # Reuse parse_findings_array's per-finding validator for schema parity.
        # We pass the JSON-encoded array text so its regex-extract-then-validate
        # path runs as the SDK adapter does. Source label distinguishes errors.
        findings = parse_findings_array(json.dumps(data), source=f"file-backed:{self.name}")
        return RawFindings(
            reviewer=self.name,
            findings=findings,
            metadata={
                "source": "in-session-subagent",
                "findings_path": str(path),
            },
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest tests/core/reviewers/test_file_backed.py::test_file_backed_reviewer_reads_valid_findings -v`
Expected: PASS

- [ ] **Step 5: Add error-path tests**

Append to `tests/core/reviewers/test_file_backed.py`:

```python
def test_file_backed_reviewer_missing_file(tmp_path: Path) -> None:
    reviewer = FileBackedReviewer(name="claude", findings_path=tmp_path / "missing.json")
    with pytest.raises(ReviewerError, match="file not found"):
        reviewer.review(_bundle(), prompt="ignored")


def test_file_backed_reviewer_rejects_symlink(tmp_path: Path) -> None:
    real = _make_findings_file(tmp_path, [])
    link = tmp_path / "link.json"
    link.symlink_to(real)
    reviewer = FileBackedReviewer(name="claude", findings_path=link)
    with pytest.raises(ReviewerError, match="symlinks rejected"):
        reviewer.review(_bundle(), prompt="ignored")


def test_file_backed_reviewer_rejects_oversize(tmp_path: Path) -> None:
    p = tmp_path / "big.json"
    # 11 MB of valid-ish JSON to exceed the 10 MB cap
    p.write_bytes(b"[" + b'"x",' * (11 * 1024 * 1024 // 4) + b'"x"]')
    reviewer = FileBackedReviewer(name="claude", findings_path=p)
    with pytest.raises(ReviewerError, match="exceeds"):
        reviewer.review(_bundle(), prompt="ignored")


def test_file_backed_reviewer_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{not json at all", encoding="utf-8")
    reviewer = FileBackedReviewer(name="claude", findings_path=p)
    with pytest.raises(ReviewerError, match="invalid JSON"):
        reviewer.review(_bundle(), prompt="ignored")


def test_file_backed_reviewer_not_an_array(tmp_path: Path) -> None:
    p = tmp_path / "obj.json"
    p.write_text('{"findings": []}', encoding="utf-8")
    reviewer = FileBackedReviewer(name="claude", findings_path=p)
    with pytest.raises(ReviewerError, match="expected JSON array"):
        reviewer.review(_bundle(), prompt="ignored")


def test_file_backed_reviewer_per_finding_validation(tmp_path: Path) -> None:
    # Non-dict element triggers parse_findings_array's _validate_findings_array.
    p = _make_findings_file(tmp_path, ["not a dict"])  # type: ignore[list-item]
    reviewer = FileBackedReviewer(name="claude", findings_path=p)
    with pytest.raises(ReviewerError, match="non-dict"):
        reviewer.review(_bundle(), prompt="ignored")
```

- [ ] **Step 6: Run all FileBackedReviewer tests**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest tests/core/reviewers/test_file_backed.py -v`
Expected: 6 PASS

- [ ] **Step 7: Run full suite to verify no regressions**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest -q`
Expected: 420 + 6 = 426 PASS (or higher if intermediate work added tests)

- [ ] **Step 8: Commit**

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
git add src/orca/core/reviewers/file_backed.py tests/core/reviewers/test_file_backed.py
git commit -m "feat(reviewers): FileBackedReviewer for pre-authored findings"
```

---

## Task 2: cross-agent-review file-flag wiring

**Why second:** FileBackedReviewer exists; now expose it through the dispatcher.

**Files:**
- Modify: `src/orca/python_cli.py` (around lines 113-220 for `_run_cross_agent_review` + `_load_reviewers` + `_build_reviewer`)
- Test: `tests/cli/test_python_cli.py`

- [ ] **Step 1: Write failing test for --claude-findings-file flag**

Append to `tests/cli/test_python_cli.py`:

```python
def test_cross_agent_review_claude_findings_file(tmp_path: Path, capsys) -> None:
    """--claude-findings-file uses FileBackedReviewer instead of SDK."""
    from orca.python_cli import main

    findings = [{
        "id": "abc1234567890def",
        "category": "correctness",
        "severity": "high",
        "confidence": "high",
        "summary": "from file",
        "detail": "",
        "evidence": [],
        "suggestion": "",
        "reviewer": "claude",
    }]
    findings_file = tmp_path / "claude-findings.json"
    findings_file.write_text(json.dumps(findings), encoding="utf-8")

    target = tmp_path / "subject.txt"
    target.write_text("anything", encoding="utf-8")

    # Codex side via fixture so we don't need ORCA_LIVE.
    codex_fixture = tmp_path / "codex-fixture.json"
    codex_fixture.write_text(json.dumps({
        "scenario": "ok",
        "findings": [],
    }), encoding="utf-8")

    rc = main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "cross",
        "--claude-findings-file", str(findings_file),
    ], env={"ORCA_FIXTURE_REVIEWER_CODEX": str(codex_fixture)})

    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is True
    # Claude findings were sourced from the file
    assert "from file" in json.dumps(envelope["result"])
    assert rc == 0
```

NOTE: this test pattern depends on `main([...], env=...)` accepting an env override, OR you set the env var via monkeypatch. Adjust to match how existing tests in this file invoke `main` (likely via monkeypatch on os.environ). Read the existing test file structure first to match conventions.

- [ ] **Step 2: Verify failure**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest tests/cli/test_python_cli.py::test_cross_agent_review_claude_findings_file -v`
Expected: FAIL - argparse rejects `--claude-findings-file` as unknown.

- [ ] **Step 3: Add the flag and wire into reviewer-selection**

In `src/orca/python_cli.py`, locate `_run_cross_agent_review` (around line 113). After the `--prompt` argument (around line 124), add:

```python
    parser.add_argument("--claude-findings-file", default=None,
                        help="path to a JSON file with pre-authored claude findings; bypasses SDK")
    parser.add_argument("--codex-findings-file", default=None,
                        help="path to a JSON file with pre-authored codex findings; bypasses SDK")
```

Locate `_load_reviewers()` (around line 194) and change its signature:

```python
def _load_reviewers(
    *,
    claude_findings_file: str | None = None,
    codex_findings_file: str | None = None,
) -> dict:
    """Pick reviewer backends from CLI flags or env vars.

    Precedence per reviewer slot:
      1. --<name>-findings-file flag -> FileBackedReviewer
      2. ORCA_FIXTURE_REVIEWER_<NAME> env var -> FixtureReviewer
      3. ORCA_LIVE=1 -> live SDK/CLI factory
      4. None (capability surfaces missing-reviewer as Err(INPUT_INVALID))
    """
    reviewers: dict = {}
    file_flags = {
        "claude": claude_findings_file,
        "codex": codex_findings_file,
    }
    for name, live_factory in (
        ("claude", _live_claude),
        ("codex", _live_codex),
    ):
        reviewer = _build_reviewer(name, live_factory, findings_file=file_flags[name])
        if reviewer is not None:
            reviewers[name] = reviewer
    return reviewers
```

Locate `_build_reviewer` (around line 212) and change:

```python
def _build_reviewer(name: str, live_factory, *, findings_file: str | None = None):
    """Construct a single reviewer for `name` per precedence in _load_reviewers."""
    if findings_file is not None:
        from orca.core.reviewers.file_backed import FileBackedReviewer
        return FileBackedReviewer(name=name, findings_path=Path(findings_file))
    fixture = os.environ.get(f"ORCA_FIXTURE_REVIEWER_{name.upper()}")
    if fixture:
        return FixtureReviewer(scenario=Path(fixture), name=name)
    if os.environ.get("ORCA_LIVE") == "1":
        return live_factory()
    return None
```

Locate the `_load_reviewers()` call in `_run_cross_agent_review` (around line 181) and change to:

```python
    reviewers = _load_reviewers(
        claude_findings_file=ns.claude_findings_file,
        codex_findings_file=ns.codex_findings_file,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest tests/cli/test_python_cli.py::test_cross_agent_review_claude_findings_file -v`
Expected: PASS

- [ ] **Step 5: Add codex symmetry test**

Append to `tests/cli/test_python_cli.py`:

```python
def test_cross_agent_review_codex_findings_file(tmp_path: Path, capsys, monkeypatch) -> None:
    """--codex-findings-file uses FileBackedReviewer for codex slot."""
    from orca.python_cli import main

    codex_findings = [{
        "id": "fed4321098765432",
        "category": "security",
        "severity": "medium",
        "confidence": "high",
        "summary": "from codex file",
        "detail": "",
        "evidence": [],
        "suggestion": "",
        "reviewer": "codex",
    }]
    codex_file = tmp_path / "codex-findings.json"
    codex_file.write_text(json.dumps(codex_findings), encoding="utf-8")

    claude_findings: list = []
    claude_file = tmp_path / "claude-findings.json"
    claude_file.write_text(json.dumps(claude_findings), encoding="utf-8")

    target = tmp_path / "subject.txt"
    target.write_text("anything", encoding="utf-8")

    rc = main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "cross",
        "--claude-findings-file", str(claude_file),
        "--codex-findings-file", str(codex_file),
    ])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is True
    assert "from codex file" in json.dumps(envelope["result"])
    assert rc == 0
```

- [ ] **Step 6: Add file-flag-wins-over-fixture-env precedence test**

Append:

```python
def test_cross_agent_review_file_flag_wins_over_fixture(tmp_path: Path, capsys, monkeypatch) -> None:
    """When both --claude-findings-file and ORCA_FIXTURE_REVIEWER_CLAUDE are set,
    file flag takes precedence."""
    from orca.python_cli import main

    file_findings = [{
        "id": "abc1234567890def",
        "category": "correctness", "severity": "high", "confidence": "high",
        "summary": "from file flag", "detail": "", "evidence": [], "suggestion": "",
        "reviewer": "claude",
    }]
    file_path = tmp_path / "file-findings.json"
    file_path.write_text(json.dumps(file_findings), encoding="utf-8")

    fixture_findings = [{
        "id": "9876543210abcdef",
        "category": "correctness", "severity": "high", "confidence": "high",
        "summary": "from fixture", "detail": "", "evidence": [], "suggestion": "",
        "reviewer": "claude",
    }]
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps({"scenario": "ok", "findings": fixture_findings}), encoding="utf-8")

    target = tmp_path / "subject.txt"
    target.write_text("anything", encoding="utf-8")

    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CLAUDE", str(fixture_path))
    monkeypatch.setenv("ORCA_FIXTURE_REVIEWER_CODEX", str(fixture_path))  # any non-empty so codex slot fills

    rc = main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "claude",  # single reviewer for cleaner test
        "--claude-findings-file", str(file_path),
    ])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is True
    assert "from file flag" in json.dumps(envelope["result"])
    assert "from fixture" not in json.dumps(envelope["result"])
    assert rc == 0
```

- [ ] **Step 7: Add missing-file error path test**

```python
def test_cross_agent_review_claude_findings_file_missing(tmp_path: Path, capsys) -> None:
    """Missing --claude-findings-file path returns Err envelope, exit 1."""
    from orca.python_cli import main

    target = tmp_path / "subject.txt"
    target.write_text("anything", encoding="utf-8")

    rc = main([
        "cross-agent-review",
        "--kind", "diff",
        "--target", str(target),
        "--reviewer", "claude",
        "--claude-findings-file", str(tmp_path / "does-not-exist.json"),
    ])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is False
    assert "file not found" in envelope["error"]["message"].lower() or "missing" in envelope["error"]["message"].lower()
    assert rc == 1
```

- [ ] **Step 8: Run all flag tests**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest tests/cli/test_python_cli.py -v -k "claude_findings_file or codex_findings_file or file_flag_wins"`
Expected: 4 PASS

- [ ] **Step 9: Run full suite**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest -q`
Expected: existing + 4 new = 430 PASS

- [ ] **Step 10: Commit**

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
git add src/orca/python_cli.py tests/cli/test_python_cli.py
git commit -m "feat(cli): cross-agent-review --claude-findings-file / --codex-findings-file"
```

---

## Task 3: parse-subagent-response subcommand

**Why third:** Slash commands need this primitive before they can pipe subagent output. orca-cli owns the JSON-extraction validation.

**Files:**
- Modify: `src/orca/python_cli.py` (new function `_run_parse_subagent_response`, register subcommand)
- Test: `tests/cli/test_python_cli.py`

- [ ] **Step 1: Write failing test for happy path (bare JSON array)**

Append to `tests/cli/test_python_cli.py`:

```python
def test_parse_subagent_response_bare_json_array(capsys, monkeypatch) -> None:
    """Bare JSON array on stdin emits same array on stdout."""
    from orca.python_cli import main
    import io

    findings = [{
        "id": "abc1234567890def",
        "category": "correctness",
        "severity": "high",
        "confidence": "high",
        "summary": "test",
        "detail": "",
        "evidence": [],
        "suggestion": "",
        "reviewer": "claude",
    }]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(findings)))
    rc = main(["parse-subagent-response"])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed == findings
    assert rc == 0
```

- [ ] **Step 2: Verify failure**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest tests/cli/test_python_cli.py::test_parse_subagent_response_bare_json_array -v`
Expected: FAIL - unknown subcommand `parse-subagent-response`.

- [ ] **Step 3: Add the subcommand**

In `src/orca/python_cli.py`, find the section near the bottom where capability subcommands are registered with `_register(...)` calls (around line 750). Above the `_register` calls, add the new dispatcher:

```python
def _run_parse_subagent_response(args: list[str]) -> int:
    """Validate raw subagent text on stdin, emit findings JSON on stdout.

    Reuses parse_findings_array from the SDK adapter pipeline so schema
    validation matches what the SDK adapter emits today. Failure path is
    Err(INPUT_INVALID) with a specific message.
    """
    parser = argparse.ArgumentParser(
        prog="orca-cli parse-subagent-response",
        description="Extract + validate findings JSON from raw subagent text",
        exit_on_error=False,
    )
    parser.add_argument("--pretty", action="store_true",
                        help="emit human-readable summary; default emits findings JSON")
    try:
        ns, unknown = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "parse-subagent-response", "0.1.0",
                ErrorKind.INPUT_INVALID, f"argv parse error: {exc}",
            ),
            pretty=False,
            exit_code=2,
        )
    if unknown:
        return _emit_envelope(
            envelope=_err_envelope(
                "parse-subagent-response", "0.1.0",
                ErrorKind.INPUT_INVALID, f"unknown args: {unknown}",
            ),
            pretty=ns.pretty,
            exit_code=2,
        )

    text = sys.stdin.read()
    try:
        findings = parse_findings_array(text, source="subagent-response")
    except ReviewerError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "parse-subagent-response", "0.1.0",
                ErrorKind.INPUT_INVALID, f"parse-subagent-response: {exc}",
            ),
            pretty=ns.pretty,
            exit_code=1,
        )

    print(json.dumps(findings))
    return 0
```

Add the import for `parse_findings_array` and `ReviewerError` at the top of `python_cli.py` if not already present:

```python
from orca.core.reviewers._parse import parse_findings_array
from orca.core.reviewers.base import ReviewerError
```

(Check existing imports first; `ReviewerError` may already be imported via another path.)

Register the subcommand in the `_register` block:

```python
_register("parse-subagent-response", _run_parse_subagent_response, "0.1.0")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest tests/cli/test_python_cli.py::test_parse_subagent_response_bare_json_array -v`
Expected: PASS

- [ ] **Step 5: Add markdown-fenced JSON test**

```python
def test_parse_subagent_response_markdown_fenced(capsys, monkeypatch) -> None:
    """JSON wrapped in markdown code fence is extracted."""
    from orca.python_cli import main
    import io

    findings = [{
        "id": "abc1234567890def",
        "category": "correctness",
        "severity": "high",
        "confidence": "high",
        "summary": "test",
        "detail": "",
        "evidence": [],
        "suggestion": "",
        "reviewer": "claude",
    }]
    raw = f"Here are my findings:\n\n```json\n{json.dumps(findings)}\n```\n\nLet me know if you need more."
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))
    rc = main(["parse-subagent-response"])
    out = capsys.readouterr().out
    parsed = json.loads(out)
    assert parsed == findings
    assert rc == 0
```

- [ ] **Step 6: Add prose-only failure test**

```python
def test_parse_subagent_response_prose_only_fails(capsys, monkeypatch) -> None:
    """Pure prose with no JSON array exits 1 with specific error."""
    from orca.python_cli import main
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("I reviewed the diff and found no issues."))
    rc = main(["parse-subagent-response"])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is False
    assert envelope["error"]["kind"] == "input_invalid"
    assert "could not parse" in envelope["error"]["message"].lower() or "parse-subagent" in envelope["error"]["message"].lower()
    assert rc == 1
```

- [ ] **Step 7: Add invalid-JSON failure test**

```python
def test_parse_subagent_response_invalid_json_fails(capsys, monkeypatch) -> None:
    """Malformed JSON-looking content exits 1."""
    from orca.python_cli import main
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("[{not: 'valid json'}]"))
    rc = main(["parse-subagent-response"])
    out = capsys.readouterr().out
    envelope = json.loads(out)
    assert envelope["ok"] is False
    assert rc == 1
```

- [ ] **Step 8: Run all parse-subagent-response tests**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest tests/cli/test_python_cli.py -v -k parse_subagent_response`
Expected: 4 PASS

- [ ] **Step 9: Run full suite**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest -q`
Expected: existing + 4 new = 434 PASS

- [ ] **Step 10: Commit**

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
git add src/orca/python_cli.py tests/cli/test_python_cli.py
git commit -m "feat(cli): parse-subagent-response subcommand"
```

---

## Task 4: build-review-prompt subcommand

**Why fourth:** Last orca-cli surface change. Slash commands consume this in Tasks 5-7.

**Files:**
- Modify: `src/orca/python_cli.py` (new function `_run_build_review_prompt`, register subcommand)
- Test: `tests/cli/test_python_cli.py`

- [ ] **Step 1: Write failing test for default prompt**

```python
def test_build_review_prompt_default(capsys) -> None:
    """No criteria: emits DEFAULT_REVIEW_PROMPT verbatim, no extra sections."""
    from orca.python_cli import main
    from orca.capabilities.cross_agent_review import DEFAULT_REVIEW_PROMPT

    rc = main(["build-review-prompt", "--kind", "diff"])
    out = capsys.readouterr().out
    assert out.strip() == DEFAULT_REVIEW_PROMPT.strip()
    assert rc == 0
```

- [ ] **Step 2: Verify failure**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest tests/cli/test_python_cli.py::test_build_review_prompt_default -v`
Expected: FAIL - unknown subcommand `build-review-prompt`.

- [ ] **Step 3: Add the subcommand**

In `src/orca/python_cli.py`, add another `_run_*` dispatcher near `_run_parse_subagent_response`:

```python
def _run_build_review_prompt(args: list[str]) -> int:
    """Emit the canonical review prompt on stdout (plain text, no envelope).

    v1: DEFAULT_REVIEW_PROMPT plus optional bullet-list of criteria. Per-kind
    branching is accepted via --kind for forward-compat but does not branch
    in v1 (per Phase 4a spec; per-kind opinionation deferred).
    """
    parser = argparse.ArgumentParser(
        prog="orca-cli build-review-prompt",
        description="Emit canonical review prompt for subagent dispatch",
        exit_on_error=False,
    )
    parser.add_argument("--kind", default="diff",
                        help="review subject kind; accepted for forward-compat (v1 does not branch)")
    parser.add_argument("--criteria", action="append", default=[],
                        help="review criterion (repeatable)")
    parser.add_argument("--context", action="append", default=[],
                        help="review context line (repeatable)")
    try:
        ns, unknown = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "build-review-prompt", "0.1.0",
                ErrorKind.INPUT_INVALID, f"argv parse error: {exc}",
            ),
            pretty=False,
            exit_code=2,
        )
    if unknown:
        return _emit_envelope(
            envelope=_err_envelope(
                "build-review-prompt", "0.1.0",
                ErrorKind.INPUT_INVALID, f"unknown args: {unknown}",
            ),
            pretty=False,
            exit_code=2,
        )

    parts: list[str] = [DEFAULT_REVIEW_PROMPT.strip()]
    if ns.criteria:
        parts.append("")
        parts.append("Criteria:")
        for c in ns.criteria:
            parts.append(f"- {c}")
    if ns.context:
        parts.append("")
        parts.append("Context:")
        for c in ns.context:
            parts.append(f"- {c}")
    print("\n".join(parts))
    return 0
```

Verify `DEFAULT_REVIEW_PROMPT` is imported at the top of `python_cli.py` (it should already be present per the existing cross_agent_review import line; if not, add `DEFAULT_REVIEW_PROMPT` to the import).

Register the subcommand in the `_register` block:

```python
_register("build-review-prompt", _run_build_review_prompt, "0.1.0")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest tests/cli/test_python_cli.py::test_build_review_prompt_default -v`
Expected: PASS

- [ ] **Step 5: Add criteria-bullets test**

```python
def test_build_review_prompt_criteria_bullets(capsys) -> None:
    """--criteria flags become bullet-list under 'Criteria:' header."""
    from orca.python_cli import main

    rc = main([
        "build-review-prompt",
        "--kind", "diff",
        "--criteria", "correctness",
        "--criteria", "security",
    ])
    out = capsys.readouterr().out
    assert "Criteria:" in out
    assert "- correctness" in out
    assert "- security" in out
    assert rc == 0


def test_build_review_prompt_kind_does_not_branch(capsys) -> None:
    """v1: --kind is accepted but does not change output."""
    from orca.python_cli import main

    rc1 = main(["build-review-prompt", "--kind", "diff"])
    out1 = capsys.readouterr().out
    rc2 = main(["build-review-prompt", "--kind", "spec"])
    out2 = capsys.readouterr().out
    assert out1 == out2
    assert rc1 == 0 and rc2 == 0
```

- [ ] **Step 6: Run all build-review-prompt tests**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest tests/cli/test_python_cli.py -v -k build_review_prompt`
Expected: 3 PASS

- [ ] **Step 7: Run full suite**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest -q`
Expected: 437 PASS

- [ ] **Step 8: Smoke test the new subcommand**

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
uv run orca-cli build-review-prompt --kind diff --criteria correctness --criteria security
```

Expected output:
```
Review the following content. Return a JSON array of findings.

Criteria:
- correctness
- security
```

- [ ] **Step 9: Commit**

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
git add src/orca/python_cli.py tests/cli/test_python_cli.py
git commit -m "feat(cli): build-review-prompt subcommand"
```

---

## Task 5: Update review-spec slash command

**Why now:** orca-cli surfaces are in place; slash commands can consume them.

**Files:**
- Modify: `plugins/claude-code/commands/review-spec.md` (insert subagent dispatch step in Outline)

- [ ] **Step 1: Read the current file structure**

Run: `grep -n "^## \|^[0-9]\+\. " plugins/claude-code/commands/review-spec.md | head -20`

Identify the line number of step 4 in the Outline ("Invoke `orca-cli cross-agent-review` against the spec:"). The new subagent dispatch step is inserted as step 4a, BEFORE step 4.

- [ ] **Step 2: Insert the subagent dispatch step**

In `plugins/claude-code/commands/review-spec.md`, find the exact text:

```
4. Invoke `orca-cli cross-agent-review` against the spec:
```

and replace with:

```
4. Build the cross-pass review prompt and dispatch the in-session claude reviewer (Claude Code only):

   ```bash
   ORCA_PROMPT=$(uv run orca-cli build-review-prompt \
     --kind spec \
     --criteria cross-spec-consistency \
     --criteria feasibility \
     --criteria security \
     --criteria dependencies \
     --criteria industry-patterns)
   ```

   Dispatch a `Code Reviewer` subagent via the Agent tool with:
   - description: `Cross-pass review of <feature-id> spec.md`
   - prompt: `$ORCA_PROMPT` followed by the full text of `<feature-dir>/spec.md`

   Capture the subagent's response into `$SUBAGENT_RESPONSE`. Then validate:

   ```bash
   echo "$SUBAGENT_RESPONSE" | uv run orca-cli parse-subagent-response \
     > "$FEATURE_DIR/.review-spec-claude-findings.json"
   ```

   If `parse-subagent-response` exits non-zero, append a `### Round N - FAILED` block to `<feature-dir>/review-spec.md` describing the parse failure and STOP.

5. Invoke `orca-cli cross-agent-review` against the spec, providing the file-backed claude findings:
```

(Note: this also renumbers the subsequent steps. Find the next numbered list items and renumber them: original 5 -> new 6, original 6 -> new 7, etc.)

- [ ] **Step 3: Update the cross-agent-review bash block to use the file flag**

In the same file, find the existing `uv run orca-cli cross-agent-review \` block (which was step 4 in the original numbering, now within step 5). Add the `--claude-findings-file` argument:

```bash
   uv run orca-cli cross-agent-review \
     --kind spec \
     --target "<feature-dir>/spec.md" \
     --feature-id "<feature-id>" \
     --reviewer cross \
     --claude-findings-file "$FEATURE_DIR/.review-spec-claude-findings.json" \
     --criteria "cross-spec-consistency" \
     --criteria "feasibility" \
     --criteria "security" \
     --criteria "dependencies" \
     --criteria "industry-patterns" \
     > "$FEATURE_DIR/.review-spec-envelope.json"
```

- [ ] **Step 4: Verify the file is still valid markdown**

Run: `head -80 plugins/claude-code/commands/review-spec.md`
Expected: frontmatter intact, Purpose / Workflow Contract / Prerequisites / Outline structure intact, new step 4 present.

Run: `grep -nE "—" plugins/claude-code/commands/review-spec.md`
Expected: only the legacy `### Round N — ` documentation occurrences (per Phase 3.1 backward-compat note); no new em-dashes introduced.

- [ ] **Step 5: Commit**

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
git add plugins/claude-code/commands/review-spec.md
git commit -m "feat(slash): review-spec subagent dispatch via Code Reviewer"
```

---

## Task 6: Update review-code slash command

**Files:**
- Modify: `plugins/claude-code/commands/review-code.md` (subagent dispatch within step 8)

- [ ] **Step 1: Locate step 8**

Run: `grep -n "^8\. \*\*MANDATORY" plugins/claude-code/commands/review-code.md`
Identify the line number; step 8 is the cross-pass step rewired in Phase 3.

- [ ] **Step 2: Insert subagent dispatch as substep 8c**

In `plugins/claude-code/commands/review-code.md`, find the existing substep that says (paraphrased): "Invoke `orca-cli cross-agent-review` against the diff. Both reviewers run by default..." with a bash block.

INSERT a new substep BEFORE that block:

```markdown
   c. Build the cross-pass prompt and dispatch the in-session claude reviewer (Claude Code only):

      ```bash
      ORCA_PROMPT=$(uv run orca-cli build-review-prompt \
        --kind diff \
        --criteria correctness \
        --criteria security \
        --criteria maintainability)
      ```

      Dispatch a `Code Reviewer` subagent via the Agent tool with:
      - description: `Cross-pass review of $(basename "$FEATURE_DIR") diff`
      - prompt: `$ORCA_PROMPT` followed by the full content of `"$FEATURE_DIR/.cross-pass-patch"`

      Capture the subagent's response into `$SUBAGENT_RESPONSE`. Then validate:

      ```bash
      echo "$SUBAGENT_RESPONSE" | uv run orca-cli parse-subagent-response \
        > "$FEATURE_DIR/.review-code-claude-findings.json"
      ```

      If `parse-subagent-response` exits non-zero, append a `### Round N - FAILED` block to `$FEATURE_DIR/review-code.md` and STOP.
```

(The existing substeps b, c, d, etc., need to be renumbered: original c -> d, original d -> e, etc.)

- [ ] **Step 3: Update the cross-agent-review bash block to use the file flag**

In the renumbered substep that invokes orca-cli, add the `--claude-findings-file` argument:

```bash
      uv run orca-cli cross-agent-review \
        --kind diff \
        --target "$FEATURE_DIR/.cross-pass-patch" \
        --feature-id "$(basename "$FEATURE_DIR")" \
        --reviewer cross \
        --claude-findings-file "$FEATURE_DIR/.review-code-claude-findings.json" \
        --criteria "correctness" \
        --criteria "security" \
        --criteria "maintainability" \
        > "$FEATURE_DIR/.review-code-envelope.json"
```

- [ ] **Step 4: Verify markdown integrity**

Run: `grep -nE "—" plugins/claude-code/commands/review-code.md`
Expected: only the legacy `### Round N — ` doc occurrences.

Run: `head -100 plugins/claude-code/commands/review-code.md`
Expected: structure intact, no broken markdown.

- [ ] **Step 5: Commit**

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
git add plugins/claude-code/commands/review-code.md
git commit -m "feat(slash): review-code subagent dispatch via Code Reviewer"
```

---

## Task 7: Update review-pr slash command

**Files:**
- Modify: `plugins/claude-code/commands/review-pr.md` (subagent dispatch in Cross-Pass Review section)

- [ ] **Step 1: Locate the Cross-Pass Review section**

Run: `grep -n "^## Cross-Pass Review" plugins/claude-code/commands/review-pr.md`
The section is a `## Cross-Pass Review` heading with numbered substeps; the subagent dispatch goes between step 2 (Determine round number) and step 3 (Invoke orca-cli).

- [ ] **Step 2: Insert subagent dispatch as step 3, renumbering subsequent steps**

In the Cross-Pass Review section, between step 2 ("Determine the next round number...") and the existing step 3 ("Invoke `orca-cli cross-agent-review`..."), INSERT:

```markdown
3. Build the cross-pass prompt and dispatch the in-session claude reviewer (Claude Code only):

   ```bash
   ORCA_PROMPT=$(uv run orca-cli build-review-prompt \
     --kind pr \
     --criteria comment-disposition \
     --criteria regression-risk)
   ```

   Dispatch a `Code Reviewer` subagent via the Agent tool with:
   - description: `Cross-pass review of PR diff`
   - prompt: `$ORCA_PROMPT` followed by the content of `"$FEATURE_DIR/.pr-pass-patch"`

   Capture the subagent's response into `$SUBAGENT_RESPONSE`. Then:

   ```bash
   echo "$SUBAGENT_RESPONSE" | uv run orca-cli parse-subagent-response \
     > "$FEATURE_DIR/.review-pr-claude-findings.json"
   ```

   If `parse-subagent-response` exits non-zero, append a `### Round N - FAILED` row to the disposition table and STOP.

4. Invoke `orca-cli cross-agent-review`:
```

(Original step 3 becomes step 4, original step 4 becomes 5, original step 5 becomes 6.)

- [ ] **Step 3: Update orca-cli cross-agent-review block**

In the renumbered step 4, add `--claude-findings-file` to the bash block:

```bash
   uv run orca-cli cross-agent-review \
     --kind pr \
     --target "$FEATURE_DIR/.pr-pass-patch" \
     --feature-id "$(basename "$FEATURE_DIR")" \
     --reviewer cross \
     --claude-findings-file "$FEATURE_DIR/.review-pr-claude-findings.json" \
     --criteria "comment-disposition" \
     --criteria "regression-risk" \
     > "$FEATURE_DIR/.review-pr-envelope.json"
```

- [ ] **Step 4: Verify markdown integrity**

Run: `grep -nE "—" plugins/claude-code/commands/review-pr.md`
Expected: only legacy `### Round N — ` references.

- [ ] **Step 5: Commit**

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
git add plugins/claude-code/commands/review-pr.md
git commit -m "feat(slash): review-pr subagent dispatch via Code Reviewer"
```

---

## Task 8: AGENTS.md update

**Files:**
- Modify: `plugins/codex/AGENTS.md`

- [ ] **Step 1: Locate insertion point**

Run: `grep -n "^### " plugins/codex/AGENTS.md | head`
Find the "Live Backend Prerequisites" section (added in Phase 3 disposition Round 2).

- [ ] **Step 2: Add documentation for new subcommands and flags**

In `plugins/codex/AGENTS.md`, after the "Live Backend Prerequisites" section but before the next major heading, add:

```markdown
### In-Session Reviewer (Claude Code hosts)

When the host harness is Claude Code, the cross-agent-review can use a
file-backed reviewer instead of the Anthropic SDK. This avoids the API
roundtrip and lets the host's subagent author the claude findings.

Two helper subcommands support the flow:

- `orca-cli build-review-prompt --kind <k> [--criteria ...]` emits the
  canonical review prompt on stdout (no envelope, plain text). Slash
  commands feed this to the dispatched subagent.

- `orca-cli parse-subagent-response < <raw-text>` validates the subagent's
  free-form response, extracts the JSON findings array, and emits valid
  findings JSON on stdout. Failure: `Err(INPUT_INVALID)` envelope on stdout,
  exit 1. Use this to materialize the findings file before calling
  cross-agent-review.

Two new cross-agent-review flags:

- `--claude-findings-file <path>`: claude reviewer slot reads from this
  file instead of calling the SDK. File MUST be a top-level JSON array of
  finding dicts. Symlinks rejected, file size capped at 10 MB.
- `--codex-findings-file <path>`: symmetric. Operator-supplied; not tied
  to any specific producer (Phase 4a v1 does not provide a codex-host
  subagent dispatch).

Reviewer-source precedence (per slot):
1. `--<name>-findings-file` flag -> FileBackedReviewer
2. `ORCA_FIXTURE_REVIEWER_<NAME>` env var -> FixtureReviewer
3. `ORCA_LIVE=1` -> live SDK/CLI factory
4. None -> `Err(INPUT_INVALID)` "no reviewer source configured for <name>"

Mixed mode (file-backed claude + SDK codex when `ORCA_LIVE=1`) is valid
but bypasses cross-reviewer dedupe (subagent-authored findings produce
distinct IDs from SDK-authored findings for the same logical issue).
```

- [ ] **Step 3: Verify AGENTS.md drift test still passes**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest tests/cli/test_codex_agents_md.py -v`
Expected: 6 PASS (the drift test asserts capability names appear in AGENTS.md; new subcommands are not capabilities, no new assertions needed).

- [ ] **Step 4: Run full suite**

Run: `cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats && uv run python -m pytest -q`
Expected: 437 PASS

- [ ] **Step 5: Commit**

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
git add plugins/codex/AGENTS.md
git commit -m "docs(codex): document in-session reviewer + new orca-cli subcommands"
```

---

## Task 9: End-to-end smoke + finalization

**Why last:** All surfaces in place. Verify the integration works against a real diff via subagent dispatch.

**Files:** none modified; verification only.

- [ ] **Step 1: Reinstall to spec-kit-orca with new files**

```bash
/tmp/install-phase3-orca.sh /home/taylor/spec-kit-orca
```

Expected: 7 SKILL.md files regenerated (including doctor + the updated review-* commands).

- [ ] **Step 2: Smoke build-review-prompt + parse-subagent-response loop**

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
ORCA_PROMPT=$(uv run orca-cli build-review-prompt --kind diff --criteria correctness --criteria security)
echo "$ORCA_PROMPT"
```

Expected output: `Review the following content. Return a JSON array of findings.\n\nCriteria:\n- correctness\n- security`.

Then validate a hand-crafted subagent response:

```bash
echo '```json
[{"id":"abc1234567890def","category":"correctness","severity":"high","confidence":"high","summary":"test","detail":"","evidence":[],"suggestion":"","reviewer":"claude"}]
```' | uv run orca-cli parse-subagent-response
```

Expected: `[{"id":"abc1234567890def",...}]` (the array, validated).

- [ ] **Step 3: Smoke a file-backed cross-agent-review run**

```bash
mkdir -p /tmp/orca-phase4a-smoke && cd /tmp/orca-phase4a-smoke

cat > claude-findings.json <<'EOF'
[{"id":"abc1234567890def","category":"correctness","severity":"high","confidence":"high","summary":"smoke claim","detail":"","evidence":["src/foo.py:1"],"suggestion":"","reviewer":"claude"}]
EOF

cat > codex-findings.json <<'EOF'
[]
EOF

echo "subject content" > subject.txt

cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
uv run orca-cli cross-agent-review \
  --kind diff \
  --target /tmp/orca-phase4a-smoke/subject.txt \
  --feature-id smoke \
  --reviewer cross \
  --claude-findings-file /tmp/orca-phase4a-smoke/claude-findings.json \
  --codex-findings-file /tmp/orca-phase4a-smoke/codex-findings.json \
  | python3 -m json.tool | head -30
```

Expected: envelope with `"ok": true`, `"result"` containing `"findings"` array including the "smoke claim" entry, `"reviewer_metadata"` with `"source": "in-session-subagent"`.

- [ ] **Step 4: Run the full test suite one more time**

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
uv run python -m pytest -q
```

Expected: 437 PASS (or whatever final count after all task additions; verify no regressions).

- [ ] **Step 5: Push the branch**

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
git push
```

Expected: pushes Phase 4a commits on top of Phase 3 head.

- [ ] **Step 6: Update review-pr disposition table on PR #70**

PR #70 is review-stable; Phase 4a commits land on the same branch. Either:
- Open a follow-up PR after Phase 3 merges, OR
- Note in PR #70 that Phase 4a commits are stacked and will be reviewed jointly.

For this plan, leave the decision to the operator. No commit required.

- [ ] **Step 7: Mark Phase 3.2 backlog item 9 as DONE**

Edit `docs/superpowers/notes/2026-04-27-phase-3-2-backlog.md` to update item 9 from `DEFERRED-TO-PHASE-4` to `DONE` with the resolution note: "shipped in Phase 4a; commits ..." (with the actual commit SHAs).

```bash
cd /home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats
git add docs/superpowers/notes/2026-04-27-phase-3-2-backlog.md
git commit -m "docs(phase-3.2): mark item 9 (in-session reviewer) DONE via phase 4a"
git push
```

---

## Self-Review Checklist (run before declaring DONE)

1. **Spec coverage:**
   - [x] FileBackedReviewer (Task 1)
   - [x] --claude-findings-file / --codex-findings-file flags (Task 2)
   - [x] parse-subagent-response (Task 3)
   - [x] build-review-prompt (Task 4)
   - [x] review-spec subagent dispatch (Task 5)
   - [x] review-code subagent dispatch (Task 6)
   - [x] review-pr subagent dispatch (Task 7)
   - [x] AGENTS.md docs (Task 8)
   - [x] End-to-end smoke (Task 9)

2. **No placeholders:** Every code step has real code; every test step has real assertions; every commit step has real message text.

3. **Type consistency:** `FileBackedReviewer.findings_path` is `Path` everywhere; `_load_reviewers(claude_findings_file=, codex_findings_file=)` keyword args match `_run_cross_agent_review`'s `ns.claude_findings_file` / `ns.codex_findings_file` argparse-attribute names; subcommand version strings consistent at `"0.1.0"`.

4. **Test count math:** Phase 3 baseline 420 + 6 (Task 1) + 4 (Task 2) + 4 (Task 3) + 3 (Task 4) = 437. Verify on first full-suite run.

5. **Em-dash hygiene:** All new code and docs are em-dash-free per project rule. Verify after each markdown edit.

---

## Honest Risk Notes

- **Task 9 is the long pole.** The end-to-end smoke is the first time the slash commands' subagent dispatch wording meets a live host. If the markdown wording confuses the host LLM (e.g., it skips dispatch and calls orca-cli directly), iterate on the slash command prose. Budget 1-2 days for this iteration.

- **Tasks 5-7 ARE doing the same edit three times.** This is intentional duplication per Phase 3 review-pr finding #6 ("cross-pass invocation duplicated nearly verbatim across three slash commands"). The duplication is a known scope-protective defer; do not refactor the three files into a shared snippet during Phase 4a.

- **Task 2's `_load_reviewers` signature change** is a non-cosmetic refactor. Existing callers (other tests, possibly external) MUST update. Run `grep -nr "_load_reviewers" src/ tests/` before the commit to find all call sites; update each.

- **Stack rebase risk:** if PR #69 (Phase 2) merges before this plan executes, rebase the worktree onto main. If PR #70 (Phase 3) changes during this plan's execution (e.g., human review feedback amends review-{spec,code,pr}.md), rebase Phase 4a's edits on top.
