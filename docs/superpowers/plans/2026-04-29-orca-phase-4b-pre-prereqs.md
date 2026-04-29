# Orca Phase 4b Prerequisites — Implementation Plan (orca repo)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land five small prerequisite changes in the orca repo (Phase 4b-pre-1 through pre-5) that the perf-lab spec PR cites as merge gates. Each task is independently shippable.

**Architecture:** Mostly mirrors of Phase 4a's file-backed reviewer pattern, plus one trivial CLI flag, one decision artifact, and two doc deliverables. No new capabilities. No new architecture.

**Tech Stack:** Python 3.11, pytest, existing orca CLI pattern.

**Source spec:** `docs/superpowers/specs/2026-04-28-orca-phase-4b-perf-lab-integration-design.md` § "Orca Repo Prerequisites".

**Target repo:** orca (`/home/taylor/worktrees/spec-kit-orca/orca-phase-3-plugin-formats`, branch `orca-phase-3-plugin-formats`).

**Test runner:** `uv run python -m pytest` (NOT `uv run pytest` — finds global pytest).

**Baseline:** 445 tests passing on PR #70 head.

---

## File Structure

### Files to modify

- `src/orca/python_cli.py` — Pre-1 (contradiction-detector argparse), Pre-2 (`--version` top-level)
- `src/orca/capabilities/contradiction_detector.py` — Pre-1 (accept reviewer dict containing FileBackedReviewer)
- `tests/cli/test_contradiction_detector_cli.py` — Pre-1 tests (NEW or extend existing)
- `tests/cli/test_cli_top_level.py` — Pre-2 tests (NEW or extend existing)
- `tests/cli/test_build_review_prompt_cli.py` — Pre-5 regression test (NEW or extend existing)

### Files to create

- `docs/superpowers/contracts/dispatch-algorithm.md` — Pre-4 algorithm spec
- `docs/superpowers/notes/2026-04-29-pypi-publication-decision.md` — Pre-3 decision artifact

### Files to leave alone

- `src/orca/core/reviewers/file_backed.py` — already exists from Phase 4a, no changes needed; contradiction-detector reuses it as-is
- `src/orca/capabilities/cross_agent_review.py` — already accepts findings-file flags via `_load_reviewers`; no changes
- `plugins/claude-code/commands/*.md` — slash commands already use the pattern; no changes

---

## Task 1: Pre-1 — Add `--claude-findings-file` and `--codex-findings-file` to contradiction-detector

**Files:**
- Modify: `src/orca/python_cli.py:652-717` (`_run_contradiction_detector` function)
- Modify: `src/orca/capabilities/contradiction_detector.py` (verify reviewer dict acceptance)
- Test: `tests/cli/test_contradiction_detector_cli.py`

This mirrors `_run_cross_agent_review`'s existing implementation at `src/orca/python_cli.py:117-225` exactly: add the two flags, run the same `_validate_findings_file_eagerly` preflight, pass through to the existing `_load_reviewers` helper which already supports both flags.

- [ ] **Step 1.1: Write failing test for `--claude-findings-file` happy path**

```python
# tests/cli/test_contradiction_detector_cli.py
import json
import subprocess
import sys
from pathlib import Path


def test_contradict_with_claude_findings_file(tmp_path: Path) -> None:
    """--claude-findings-file routes to FileBackedReviewer; envelope ok=True."""
    new_content = tmp_path / "new.md"
    new_content.write_text("# New synthesis\n\nThe sky is blue.\n")
    prior_evidence = tmp_path / "prior.md"
    prior_evidence.write_text("# Prior\n\nObservation: sky is blue.\n")
    findings_file = tmp_path / "claude-findings.json"
    findings_file.write_text(json.dumps([
        {"id": "c1", "kind": "contradiction", "severity": "high",
         "summary": "no contradictions", "evidence": []}
    ]))

    result = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "contradiction-detector",
         "--new-content", str(new_content),
         "--prior-evidence", str(prior_evidence),
         "--claude-findings-file", str(findings_file),
         "--reviewer", "claude"],
        capture_output=True, text=True,
    )
    assert result.returncode in (0, 1), result.stderr
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is True or envelope.get("partial"), envelope
    assert envelope["capability"] == "contradiction-detector"
```

- [ ] **Step 1.2: Run the test to verify it fails**

```bash
uv run python -m pytest tests/cli/test_contradiction_detector_cli.py::test_contradict_with_claude_findings_file -v
```

Expected: FAIL with `unknown args: ['--claude-findings-file', ...]` (the flag isn't wired yet).

- [ ] **Step 1.3: Add the two flags + preflight + reviewer routing in `_run_contradiction_detector`**

In `src/orca/python_cli.py`, modify `_run_contradiction_detector` (currently lines 652-717). Add the two argparse flags, the file-flag preflight loop, and pass through to `_load_reviewers` exactly the way `_run_cross_agent_review` does.

```python
def _run_contradiction_detector(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="orca-cli contradiction-detector",
        exit_on_error=False,
    )
    parser.add_argument("--new-content", required=True)
    parser.add_argument("--prior-evidence", action="append", required=True, default=[],
                        help="path to prior evidence file (repeatable, at least one required)")
    parser.add_argument("--reviewer", default="cross", choices=["claude", "codex", "cross"])
    parser.add_argument("--claude-findings-file", default=None,
                        help="path to a JSON file with pre-authored claude findings; bypasses SDK")
    parser.add_argument("--codex-findings-file", default=None,
                        help="path to a JSON file with pre-authored codex findings; bypasses SDK")
    parser.add_argument("--pretty", action="store_true",
                        help="emit human-readable summary instead of JSON envelope")

    try:
        ns, unknown = parser.parse_known_args(args)
    except argparse.ArgumentError as exc:
        return _emit_envelope(
            envelope=_err_envelope(
                "contradiction-detector", CONTRADICTION_DETECTOR_VERSION,
                ErrorKind.INPUT_INVALID, f"argv parse error: {exc}",
            ),
            pretty=False,
            exit_code=2,
        )
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        return _emit_envelope(
            envelope=_err_envelope(
                "contradiction-detector", CONTRADICTION_DETECTOR_VERSION,
                ErrorKind.INPUT_INVALID, "argv parse error (missing/invalid arguments)",
            ),
            pretty=False,
            exit_code=2,
        )

    if unknown:
        return _emit_envelope(
            envelope=_err_envelope(
                "contradiction-detector", CONTRADICTION_DETECTOR_VERSION,
                ErrorKind.INPUT_INVALID, f"unknown args: {unknown}",
            ),
            pretty=ns.pretty,
            exit_code=2,
        )

    # Pre-flight validation for findings-file flags (mirrors cross-agent-review).
    for slot, path_str in (
        ("claude-findings-file", ns.claude_findings_file),
        ("codex-findings-file", ns.codex_findings_file),
    ):
        if not path_str:
            continue
        err_msg = _validate_findings_file_eagerly(path_str)
        if err_msg is not None:
            return _emit_envelope(
                envelope=_err_envelope(
                    "contradiction-detector", CONTRADICTION_DETECTOR_VERSION,
                    ErrorKind.INPUT_INVALID, f"{slot}: {err_msg}",
                ),
                pretty=ns.pretty,
                exit_code=1,
            )

    inp = ContradictionDetectorInput(
        new_content=ns.new_content,
        prior_evidence=ns.prior_evidence,
        reviewer=ns.reviewer,
    )

    started = time.monotonic()
    reviewers = _load_reviewers(
        claude_findings_file=ns.claude_findings_file,
        codex_findings_file=ns.codex_findings_file,
    )
    result = contradiction_detector(inp, reviewers=reviewers)
    duration_ms = round((time.monotonic() - started) * 1000, 1)

    envelope = result.to_json(
        capability="contradiction-detector",
        version=CONTRADICTION_DETECTOR_VERSION,
        duration_ms=duration_ms,
    )
    return _emit_envelope(
        envelope=envelope,
        pretty=ns.pretty,
        exit_code=0 if result.ok else 1,
    )
```

- [ ] **Step 1.4: Run the happy-path test to verify it passes**

```bash
uv run python -m pytest tests/cli/test_contradiction_detector_cli.py::test_contradict_with_claude_findings_file -v
```

Expected: PASS.

- [ ] **Step 1.5: Add failure-mode tests (mirror Phase 4a's preflight tests for cross-agent-review)**

For each of these failure modes, write one test asserting `--claude-findings-file <path>` returns `INPUT_INVALID` exit 1 with the expected message slot. Mirror the cases in `tests/cli/test_cross_agent_review_cli.py` (whichever file has the existing preflight tests):

- missing file (`/tmp/does-not-exist.json`) → "missing"
- symlink to a regular file (`os.symlink`) → "symlinks rejected"
- empty file → "empty"
- non-JSON content → "JSON parse failed"
- non-array JSON (e.g., `{"x": 1}`) → "expected JSON array"
- malformed finding shape (missing required keys) → matches preflight error message

```python
def test_contradict_findings_file_missing(tmp_path: Path) -> None:
    new_content = tmp_path / "n.md"
    new_content.write_text("x")
    prior = tmp_path / "p.md"
    prior.write_text("y")

    result = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "contradiction-detector",
         "--new-content", str(new_content),
         "--prior-evidence", str(prior),
         "--claude-findings-file", str(tmp_path / "missing.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False
    assert envelope["error"]["kind"] == "INPUT_INVALID"
    assert "claude-findings-file" in envelope["error"]["message"]
```

(Repeat shape for the other failure modes, using the same fixture pattern as cross-agent-review tests.)

- [ ] **Step 1.6: Run all preflight tests; verify all pass**

```bash
uv run python -m pytest tests/cli/test_contradiction_detector_cli.py -v
```

Expected: all pass.

- [ ] **Step 1.7: Run the full test suite to confirm no regressions**

```bash
uv run python -m pytest
```

Expected: 445 + new tests passing.

- [ ] **Step 1.8: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_contradiction_detector_cli.py
git commit -m "feat(contradiction-detector): add --claude-findings-file / --codex-findings-file (Phase 4b-pre-1)

Mirrors Phase 4a's cross-agent-review file-backed-reviewer wiring:
both flags + INPUT_INVALID preflight + passthrough to _load_reviewers.
Closes Phase 4b-pre-1 prerequisite per Phase 4b spec v2."
```

---

## Task 2: Pre-2 — Add `orca-cli --version` top-level flag

**Files:**
- Modify: `src/orca/python_cli.py` (top-level argv handler, around the `_print_help` area)
- Test: `tests/cli/test_cli_top_level.py` (or extend existing)

- [ ] **Step 2.1: Write failing test**

```python
# tests/cli/test_cli_top_level.py
import re
import subprocess
import sys


def test_orca_cli_version_flag() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "--version"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    # Format: "spec-kit-orca <semver>"
    assert re.match(r"spec-kit-orca \d+\.\d+\.\d+", result.stdout.strip()), result.stdout
```

- [ ] **Step 2.2: Run test; verify FAIL with "unknown capability: --version"**

```bash
uv run python -m pytest tests/cli/test_cli_top_level.py::test_orca_cli_version_flag -v
```

- [ ] **Step 2.3: Find the package version source**

Read `pyproject.toml` to get the package name and version field. Should be:
```bash
grep -E "^name|^version" pyproject.toml
```

Expected: `name = "spec-kit-orca"`, `version = "<x.y.z>"`.

- [ ] **Step 2.4: Add `--version` handling in main()**

In `src/orca/python_cli.py`, locate `main()` (or the top-level argv-handling function) and add a `--version` short-circuit BEFORE the capability dispatch. Use `importlib.metadata.version("spec-kit-orca")` to read the installed package version dynamically.

```python
import importlib.metadata

def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] in ("--version", "-V"):
        try:
            ver = importlib.metadata.version("spec-kit-orca")
        except importlib.metadata.PackageNotFoundError:
            ver = "0.0.0+unknown"
        print(f"spec-kit-orca {ver}")
        return 0

    # ... existing capability dispatch ...
```

(Verify the existing top-level structure matches; adapt the insertion point as needed.)

- [ ] **Step 2.5: Run test; verify PASS**

```bash
uv run python -m pytest tests/cli/test_cli_top_level.py::test_orca_cli_version_flag -v
```

- [ ] **Step 2.6: Run full suite**

```bash
uv run python -m pytest
```

Expected: all green.

- [ ] **Step 2.7: Commit**

```bash
git add src/orca/python_cli.py tests/cli/test_cli_top_level.py
git commit -m "feat(cli): add orca-cli --version (Phase 4b-pre-2)

Reads version from importlib.metadata (no hardcoded constant).
Output: 'spec-kit-orca <semver>' to stdout, exit 0. Required by
Phase 4b's compatibility probe; perf-lab will fail-fast on missing
--version rather than running with an incompatible orca."
```

---

## Task 3: Pre-3 — PyPI publication decision artifact

**Files:**
- Create: `docs/superpowers/notes/2026-04-29-pypi-publication-decision.md`

This task is non-coding. The deliverable is a written decision: do we publish `spec-kit-orca` to PyPI, publish under a different name, or stay un-published and require source bind-mount in Phase 4b's devcontainer?

- [ ] **Step 3.1: Verify current PyPI state**

```bash
curl -sSL https://pypi.org/pypi/spec-kit-orca/json 2>&1 | head -3
```

Expected: 404 or empty (package does not exist on PyPI as of 2026-04-29).

- [ ] **Step 3.2: Verify `pyproject.toml` package name**

```bash
grep "^name" pyproject.toml
```

Expected: `name = "spec-kit-orca"`.

- [ ] **Step 3.3: Write the decision doc**

Create `docs/superpowers/notes/2026-04-29-pypi-publication-decision.md` capturing the chosen path. The three options to evaluate:

- **(a) Publish to PyPI as `spec-kit-orca`.** Requires `__about__.py` or version-source plumbing, PyPI account with 2FA, twine/uv publish workflow. Locks in the name as canonical going forward.
- **(b) Publish under a different name** (e.g., `orca-toolchest`, `orca-cli`). Requires renaming in `pyproject.toml`, breaking existing `uv tool install spec-kit-orca` invocations. Cleaner if "spec-kit-orca" no longer reflects reality (it doesn't — phase 1 removed the spec-kit fork framing).
- **(c) No PyPI publication.** Phase 4b devcontainer uses bind-mount-only (`ENV ORCA_PROJECT=/opt/orca` + `volume mount`). Operator burden: each perf-lab install needs an orca source tree.

Evaluation criteria: maintenance overhead, operator UX in perf-lab v6, alignment with the renamed-repo identity ("spec-kit-orca" or just "orca"?). Document the decision and the next step (publish workflow OR Dockerfile bind-mount instructions).

The doc body should be ~150-300 words. Single source of truth that T0Z11 cites in the perf-lab spec PR.

- [ ] **Step 3.4: Commit**

```bash
git add docs/superpowers/notes/2026-04-29-pypi-publication-decision.md
git commit -m "docs(notes): pypi publication decision for spec-kit-orca (Phase 4b-pre-3)

Captures the chosen path among (a) publish as spec-kit-orca,
(b) publish under different name, (c) no PyPI / bind-mount only.
T0Z11 in perf-lab spec PR cites this decision."
```

---

## Task 4: Pre-4 — Document the host-side dispatch algorithm

**Files:**
- Create: `docs/superpowers/contracts/dispatch-algorithm.md`

The doc specifies the algorithm each consumer (perf-lab bash wrappers, Claude Code slash commands, Codex hosts) implements natively. No shared code crosses repos.

- [ ] **Step 4.1: Write the algorithm spec doc**

Create `docs/superpowers/contracts/dispatch-algorithm.md` with sections:

1. **Purpose** — why subagent dispatch needs an explicit algorithm contract (Symphony §10.6 precedent; Phase 4b prerequisite).
2. **Inputs** — prompt text, harness (claude-code | codex | other), claim/round IDs (for findings-file path), criteria list, target path.
3. **Outputs** — findings file at `/shared/orca/<claim_id>/<round_id>/<kind>-findings-<timestamp>.json` (perf-lab) or `<feature-dir>/.<command>-<reviewer>-findings.json` (in-repo).
4. **Algorithm**:
   - Compute findings-file path via path-safety contract Class C rules.
   - Build prompt via `orca-cli build-review-prompt --kind <kind> --criteria ...`.
   - Dispatch subagent with prompt + target content. Record dispatch start timestamp.
   - Stream subagent events; on each event, update last-event timestamp.
   - If `now - last_event_timestamp > stall_timeout` (default 300s, override via `ORCA_DISPATCH_STALL_TIMEOUT`), kill the subagent and write sentinel: `{"ok": false, "error": {"kind": "DISPATCH_STALL", "elapsed_seconds": N}}`.
   - If `now - dispatch_start > hard_timeout` (default 600s, override via `ORCA_DISPATCH_HARD_TIMEOUT`), kill and write sentinel: `{"ok": false, "error": {"kind": "DISPATCH_TIMEOUT", "elapsed_seconds": N}}`.
   - On normal completion: pipe response through `orca-cli parse-subagent-response` to write the findings file.
   - On parse failure: write sentinel `{"ok": false, "error": {"kind": "PARSE_FAILURE", "raw": "<truncated>"}}`.
5. **Sentinel format** — exact JSON shape consumers detect; what error.kind values are reserved.
6. **Implementation notes** — bash-specific concerns (signal handling, timeout(1) caveats); Claude Code slash command pattern (Agent tool dispatch); Codex pattern (app-server protocol with timeouts).
7. **Cross-references** — Symphony §10.6 origin, path-safety contract for findings-file path, Phase 4a parse-subagent-response.

Target length: 200-400 lines. Be precise on the sentinel format and timeouts; consumers will literally parse these.

- [ ] **Step 4.2: Cross-reference from path-safety contract**

Edit `docs/superpowers/contracts/path-safety.md` — add a "See also: dispatch-algorithm.md" line in the cross-references section so consumers find both contracts together.

- [ ] **Step 4.3: Commit**

```bash
git add docs/superpowers/contracts/dispatch-algorithm.md docs/superpowers/contracts/path-safety.md
git commit -m "docs(contracts): host-side dispatch algorithm (Phase 4b-pre-4)

Specifies the subagent-dispatch loop with stall detection
(300s default) and hard timeout (600s default) per Symphony
SPEC §10.6. Each consumer implements natively; no shared bash
helper crosses repos. Cited by perf-lab spec PR T0Z06."
```

---

## Task 5: Pre-5 — Regression test for `build-review-prompt --kind <arbitrary>`

**Files:**
- Test: `tests/cli/test_build_review_prompt_cli.py` (NEW or extend existing)

The current implementation accepts any `--kind` value without branching (free-text, forward-compat). Codify that as a regression test so future orca versions can't accidentally add kind-validation that breaks Phase 4b's `orca-dispatch-contradict.sh`.

- [ ] **Step 5.1: Write the regression test**

```python
# tests/cli/test_build_review_prompt_cli.py
import subprocess
import sys

import pytest


@pytest.mark.parametrize("kind", [
    "spec",
    "code",
    "pr",
    "diff",
    "contradiction",     # Phase 4b dispatch wrappers use this
    "artifact",
    "experimental-kind-x",
    "snake_case_kind",
    "kind-with-dashes",
])
def test_build_review_prompt_accepts_arbitrary_kind(kind: str) -> None:
    """build-review-prompt MUST accept any non-empty --kind without error.

    v1's documented behavior: 'accepts any --kind without branching'.
    Phase 4b dispatch wrappers depend on --kind contradiction not failing.
    This test prevents regressions that add kind-validation.
    """
    result = subprocess.run(
        [sys.executable, "-m", "orca.python_cli", "build-review-prompt",
         "--kind", kind,
         "--criteria", "factual-accuracy"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"--kind {kind} failed unexpectedly: stderr={result.stderr}"
    )
    assert result.stdout, f"--kind {kind} produced no output"
```

- [ ] **Step 5.2: Run; verify PASS (current behavior already accepts arbitrary kinds)**

```bash
uv run python -m pytest tests/cli/test_build_review_prompt_cli.py -v
```

Expected: all parametrized cases PASS.

- [ ] **Step 5.3: Commit**

```bash
git add tests/cli/test_build_review_prompt_cli.py
git commit -m "test(build-review-prompt): regression for arbitrary --kind (Phase 4b-pre-5)

Locks in v1's documented behavior: build-review-prompt accepts
any --kind value without branching. Phase 4b's dispatch wrappers
depend on --kind contradiction not failing in some future orca
version that adds kind-validation."
```

---

## Task 6: Final verification

- [ ] **Step 6.1: Run the full test suite**

```bash
uv run python -m pytest
```

Expected: baseline 445 + ~10-15 new tests, all green.

- [ ] **Step 6.2: Verify each pre-task is independently shippable**

Each of pre-1 through pre-5 should land on its own commit (per the plan above). Confirm:

```bash
git log --oneline -10
```

Expected: 5 distinct commits with `(Phase 4b-pre-N)` in each subject line.

- [ ] **Step 6.3: Push to remote**

```bash
git push
```

- [ ] **Step 6.4: Open or update PR #70 description**

Add a "Phase 4b prerequisites" section to PR #70's description listing the 5 commits and linking the perf-lab spec PR (when it lands) as the consumer.

---

## Self-Review Checklist

Before marking the plan complete:

1. **Spec coverage:** Each Phase 4b-pre-N (1 through 5) has exactly one task in this plan. ✓
2. **Test coverage:** Pre-1 has happy-path + 5+ failure-mode tests; Pre-2 has version-format test; Pre-5 has parametrized arbitrary-kind test. Pre-3 and Pre-4 are docs (no code tests).
3. **No placeholders:** Each step shows exact commands, exact code, expected output. No "TODO" or "fill in later".
4. **Independence:** Tasks 1-5 do not depend on each other; can ship in any order or in parallel.

## Honest Risk Notes

- Pre-1 is the only task with non-trivial code. ~80 lines added to `python_cli.py` mirroring an existing pattern; ~150 lines of test code. Estimated 1-2 hours of focused work.
- Pre-2 risk: package-name mismatch. If `pyproject.toml` says `name = "orca"` (post-rename) instead of `spec-kit-orca`, the `importlib.metadata.version()` call needs the matching string. Verify before writing the test.
- Pre-3 has no code; the risk is making the wrong decision. Don't overthink — bind-mount-only (option c) is the lowest-cost path and matches the current state. Publishing to PyPI can come later.
- Pre-4 doc is the longest. Resist scope creep — it's an algorithm spec, not a tutorial. Keep examples minimal.
- Pre-5 is trivial; the risk is none.
