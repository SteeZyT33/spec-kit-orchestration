from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from orca.core.bundle import build_bundle
from orca.core.reviewers.base import ReviewerError
from orca.core.reviewers.codex import CodexReviewer

TESTS_DIR = Path(__file__).resolve().parents[2]
FIXTURE = TESTS_DIR / "fixtures" / "reviewers" / "codex" / "simple_review.json"


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
    with patch("orca.core.reviewers.codex.shutil.which", return_value="/usr/local/bin/codex"), \
         patch("orca.core.reviewers.codex.subprocess.run", return_value=_fake_run(**fixture)):
        reviewer = CodexReviewer(binary="codex")
        raw = reviewer.review(_bundle(tmp_path), prompt="review")
    assert raw.reviewer == "codex"
    assert len(raw.findings) == 1
    assert raw.findings[0]["severity"] == "medium"


def test_codex_reviewer_nonzero_exit(tmp_path):
    with patch("orca.core.reviewers.codex.shutil.which", return_value="/usr/local/bin/codex"), \
         patch(
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


def test_codex_reviewer_timeout(tmp_path):
    import subprocess as _sp
    with patch("orca.core.reviewers.codex.shutil.which", return_value="/usr/local/bin/codex"), \
         patch(
            "orca.core.reviewers.codex.subprocess.run",
            side_effect=_sp.TimeoutExpired(cmd=["codex"], timeout=1),
         ):
        reviewer = CodexReviewer(binary="codex", timeout_s=1)
        with pytest.raises(ReviewerError, match="timeout") as exc_info:
            reviewer.review(_bundle(tmp_path), prompt="review")
        # Local subprocess timeout: bundle-too-big, not transient — non-retryable
        assert exc_info.value.retryable is False
        assert exc_info.value.underlying == "timeout"
