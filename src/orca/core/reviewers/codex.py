from __future__ import annotations

import shutil
import subprocess

from orca.core.bundle import ReviewBundle
from orca.core.reviewers._parse import parse_findings_array
from orca.core.reviewers.base import RawFindings, ReviewerError


class CodexReviewer:
    """Reviewer adapter that shells out to the `codex` CLI.

    codex >= 0.124.0 supports `codex exec --sandbox read-only` as a
    non-interactive invocation. We pipe the prompt+bundle on stdin and
    parse the JSON-array of findings from stdout.

    Codex stdout includes session chrome (model, sandbox, session-id,
    echoed prompt, tokens-used). Rather than use `--output-last-message
    <file>` (cleaner but requires temp-file management) or
    `--output-schema` (requires strict OpenAI structured-output schema
    with additionalProperties:false on every object), we rely on the
    shared `parse_findings_array` helper, which falls back to a
    balanced-bracket scan picking the last list-of-dicts when the
    greedy regex match fails. This survives chrome reliably for the
    current codex output shape; revisit if chrome layout changes.

    The binary path can be overridden via the `binary` constructor arg
    so tests can swap in a fixture; it must resolve via `shutil.which`
    or `review()` raises ReviewerError immediately.
    """

    name = "codex"

    def __init__(self, *, binary: str = "codex", timeout_s: int = 120):
        self.binary = binary
        self.timeout_s = timeout_s

    def review(self, bundle: ReviewBundle, prompt: str) -> RawFindings:
        codex_path = shutil.which(self.binary)
        if codex_path is None:
            raise ReviewerError(
                f"codex binary not found: {self.binary}",
                retryable=False,
                underlying="binary_missing",
            )

        user_text = f"{prompt}\n\n{bundle.render_text()}"
        try:
            completed = subprocess.run(
                [codex_path, "exec", "--sandbox", "read-only"],
                input=user_text,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ReviewerError(
                f"codex timeout after {self.timeout_s}s; "
                "reduce bundle size or raise timeout_s",
                retryable=False,
                underlying="timeout",
            ) from exc

        if completed.returncode != 0:
            raise ReviewerError(
                f"codex exit {completed.returncode}: {completed.stderr.strip()}",
                retryable=False,
                underlying="nonzero_exit",
            )

        findings = parse_findings_array(completed.stdout, source="codex output")
        # Capture stderr truncated for diagnostics (deprecation warnings,
        # sandbox notices, model fallbacks). Bound the size so a chatty CLI
        # doesn't bloat the metadata payload.
        stderr_capture = completed.stderr[:2048] if completed.stderr else ""
        return RawFindings(
            reviewer=self.name,
            findings=findings,
            metadata={
                "binary": self.binary,
                "stderr": stderr_capture,
            },
        )
