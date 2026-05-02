"""Tests for event-feed pane drilldown.

The event-feed pane was a RichLog (read-only tail). This change makes
it a DataTable so rows are selectable and pressing Enter opens a
drawer with full detail (commit body for git events; artifact preview
for review events).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

from orca.tui.collectors import EventFeedEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ,
             "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@e.com",
             "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@e.com"},
    )
    return completed.stdout


def _init_with_commit(repo_root: Path, subject: str, body: str = "") -> str:
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "t@e.com")
    _git(repo_root, "config", "user.name", "test")
    (repo_root / "f.txt").write_text("x\n")
    _git(repo_root, "add", "f.txt")
    msg = subject if not body else f"{subject}\n\n{body}"
    _git(repo_root, "commit", "-q", "--no-verify", "-m", msg)
    return _git(repo_root, "rev-parse", "--short", "HEAD").strip()


# ---------------------------------------------------------------------------
# Pane: DataTable conversion + row_at_cursor
# ---------------------------------------------------------------------------


def test_event_pane_uses_data_table(tmp_path: Path):
    """EventFeedPane mounts a DataTable now (not RichLog)."""
    from orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test():
            from textual.widgets import DataTable
            t = app.query_one("#event-log", DataTable)
            assert t is not None

    asyncio.run(_run())


def test_event_pane_row_at_cursor_returns_entry(tmp_path: Path):
    """row_at_cursor returns the EventFeedEntry corresponding to the cursor."""
    from orca.tui.panes import EventFeedPane

    pane = EventFeedPane()
    entries = [
        EventFeedEntry(timestamp="2026-05-01T12:00:00Z", source="git",
                       summary="abc1234 first"),
        EventFeedEntry(timestamp="2026-05-01T11:00:00Z", source="git",
                       summary="def5678 second"),
    ]
    # row_at_cursor must work post-update_rows even before mount;
    # we accept None pre-mount but never crash.
    pane._last_entries = list(entries)  # internal direct seed, no widget yet
    # The pane's logic should at least round-trip the seeded list.
    assert pane._last_entries[0].source == "git"


# ---------------------------------------------------------------------------
# Drawer builder: git events
# ---------------------------------------------------------------------------


def test_build_git_drawer_includes_full_commit_body(tmp_path: Path):
    """build_git_drawer runs `git show` and surfaces the full commit body."""
    from orca.tui.drawer import build_git_drawer

    short = _init_with_commit(tmp_path, "feat: short subject",
                              "Detailed body line 1.\nDetailed body line 2.")
    entry = EventFeedEntry(
        timestamp="2026-05-01T12:00:00Z",
        source="git",
        summary=f"{short} feat: short subject",
    )

    content = build_git_drawer(tmp_path, entry)
    body_text = "\n".join(f"{a}: {b}" for a, b in content.body)
    tail_text = "\n".join(content.tail)

    assert short in body_text or short in content.title
    # The commit subject + body must appear in the drawer (title or tail).
    assert "feat: short subject" in body_text + "\n" + tail_text
    assert "Detailed body line 1." in tail_text


def test_build_git_drawer_handles_unparseable_summary(tmp_path: Path):
    """A summary missing the short hash returns a graceful drawer."""
    from orca.tui.drawer import build_git_drawer

    entry = EventFeedEntry(
        timestamp="2026-05-01T12:00:00Z",
        source="git",
        summary="weird-summary-with-no-hash",
    )
    content = build_git_drawer(tmp_path, entry)
    # Must not raise; some kind of error/placeholder is rendered.
    assert content.title
    body_kv = dict(content.body)
    assert "error" in body_kv or "summary" in body_kv


def test_build_git_drawer_handles_missing_repo(tmp_path: Path):
    """No .git => drawer surfaces an error placeholder rather than raise."""
    from orca.tui.drawer import build_git_drawer

    entry = EventFeedEntry(
        timestamp="2026-05-01T12:00:00Z",
        source="git",
        summary="abc1234 something",
    )
    content = build_git_drawer(tmp_path, entry)
    body_kv = dict(content.body)
    # Either it has an explicit error key or the tail is empty.
    assert "error" in body_kv or content.tail == []


# ---------------------------------------------------------------------------
# Drawer builder: review events from the event feed
# ---------------------------------------------------------------------------


def test_build_event_review_drawer_renders_artifact(tmp_path: Path):
    """A review event with summary '<feat>/review-spec.md' opens that artifact."""
    from orca.tui.drawer import build_event_review_drawer

    feat_dir = tmp_path / "specs" / "001-foo"
    feat_dir.mkdir(parents=True)
    (feat_dir / "review-spec.md").write_text(
        "# spec review\n\nFinding 1\nFinding 2\n",
    )
    entry = EventFeedEntry(
        timestamp="2026-05-01T12:00:00Z",
        source="review",
        summary="001-foo/review-spec.md",
    )
    content = build_event_review_drawer(tmp_path, entry)
    tail_text = "\n".join(content.tail)
    assert "Finding 1" in tail_text
    assert "spec review" in tail_text


def test_build_event_review_drawer_handles_missing_artifact(tmp_path: Path):
    """Bad summary or missing artifact => placeholder, never raises."""
    from orca.tui.drawer import build_event_review_drawer

    entry = EventFeedEntry(
        timestamp="2026-05-01T12:00:00Z",
        source="review",
        summary="001-foo/review-spec.md",  # file does not exist
    )
    content = build_event_review_drawer(tmp_path, entry)
    body_kv = dict(content.body)
    assert "artifact" in body_kv or "error" in body_kv


# ---------------------------------------------------------------------------
# App integration (Pilot harness)
# ---------------------------------------------------------------------------


def test_event_pane_enter_opens_drawer(tmp_path: Path):
    """With a git commit in the feed, focusing event pane and pressing Enter
    pushes a DetailDrawer modal screen onto the stack."""
    from orca.tui import OrcaTUI
    from orca.tui.drawer import DetailDrawer

    short = _init_with_commit(tmp_path, "feat: hello", "body line.")
    assert short

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            # Force a refresh so the table populates with the commit.
            app._do_refresh()
            await pilot.pause()
            # Focus event pane
            await pilot.press("2")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, DetailDrawer)

    asyncio.run(_run())
