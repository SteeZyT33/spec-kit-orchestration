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
from orca.core.reviewers._parse import validate_findings_array
from orca.core.reviewers.base import RawFindings, ReviewerError


MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB cap; findings JSON should never approach
_METADATA_SOURCE = "in-session-subagent"


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
