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


def test_relative_symlink_idempotent_from_different_cwd(tmp_path, monkeypatch):
    """Re-running safe_symlink with a relative-style target should be no-op,
    regardless of process CWD at call time."""
    target = tmp_path / "primary" / ".env"
    target.parent.mkdir(parents=True)
    target.write_text("ok")
    link = tmp_path / "wt" / ".env"
    link.parent.mkdir()
    safe_symlink(target=target, link=link)
    # cd to a totally different dir, then re-call. Idempotent should hold.
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    safe_symlink(target=target, link=link)
    assert link.is_symlink()
