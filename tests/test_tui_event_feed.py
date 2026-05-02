"""Tests for the re-sourced event feed collector.

The TUI event feed surfaces two signal sources:

1. Review-artifact filesystem activity (writes to review-spec.md /
   review-code.md / review-pr.md across every feature directory).
2. Recent git commits (last N entries from `git log`).

Sorted descending by timestamp, capped at EVENT_FEED_MAX_ENTRIES.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path


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


def _init_git_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "t@e.com")
    _git(repo_root, "config", "user.name", "test")


def _make_feature(repo_root: Path, feature_id: str) -> Path:
    feat = repo_root / "specs" / feature_id
    feat.mkdir(parents=True, exist_ok=True)
    (feat / "spec.md").write_text(f"# {feature_id} spec\n")
    return feat


# ---------------------------------------------------------------------------
# Empty-state contract (must remain green for empty repos)
# ---------------------------------------------------------------------------


def test_event_feed_empty_when_no_signals(tmp_path: Path):
    """Empty repo (no specs/, no commits) returns []."""
    from orca.tui.collectors import collect_event_feed
    assert collect_event_feed(tmp_path) == []


# ---------------------------------------------------------------------------
# Review artifact source
# ---------------------------------------------------------------------------


def test_event_feed_surfaces_review_artifact_writes(tmp_path: Path):
    """A review-spec.md / review-code.md / review-pr.md write surfaces in the feed."""
    from orca.tui.collectors import collect_event_feed

    feat = _make_feature(tmp_path, "001-foo")
    (feat / "review-spec.md").write_text("# review-spec\n")
    (feat / "review-code.md").write_text("# review-code\n")

    entries = collect_event_feed(tmp_path)
    sources = {e.source for e in entries}
    summaries = " ".join(e.summary for e in entries)

    assert "review" in sources
    assert "001-foo/review-spec.md" in summaries
    assert "001-foo/review-code.md" in summaries


def test_event_feed_ignores_non_review_artifacts(tmp_path: Path):
    """spec.md / plan.md / tasks.md are not review artifacts; the feed skips them."""
    from orca.tui.collectors import collect_event_feed

    feat = _make_feature(tmp_path, "001-foo")
    (feat / "plan.md").write_text("# plan\n")
    (feat / "tasks.md").write_text("# tasks\n")
    # No review-*.md files written.

    entries = collect_event_feed(tmp_path)
    summaries = " ".join(e.summary for e in entries)
    assert "plan.md" not in summaries
    assert "tasks.md" not in summaries
    # spec.md created by _make_feature also must not surface.
    assert "spec.md" not in summaries


# ---------------------------------------------------------------------------
# Git commit source
# ---------------------------------------------------------------------------


def test_event_feed_surfaces_recent_git_commits(tmp_path: Path):
    """Recent commits appear in the feed with source='git'."""
    from orca.tui.collectors import collect_event_feed

    _init_git_repo(tmp_path)
    (tmp_path / "README.md").write_text("hello\n")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-q", "--no-verify", "-m", "initial commit")

    entries = collect_event_feed(tmp_path)
    sources = {e.source for e in entries}
    summaries = " ".join(e.summary for e in entries)

    assert "git" in sources
    assert "initial commit" in summaries


def test_event_feed_handles_repo_without_git(tmp_path: Path):
    """No .git directory means no git commits, but other sources still work."""
    from orca.tui.collectors import collect_event_feed

    feat = _make_feature(tmp_path, "001-foo")
    (feat / "review-spec.md").write_text("# review\n")

    entries = collect_event_feed(tmp_path)
    sources = {e.source for e in entries}
    assert "review" in sources
    assert "git" not in sources


# ---------------------------------------------------------------------------
# Sort order + cap
# ---------------------------------------------------------------------------


def test_event_feed_sorted_descending_by_timestamp(tmp_path: Path):
    """Newer entries appear before older entries."""
    from orca.tui.collectors import collect_event_feed

    feat = _make_feature(tmp_path, "001-foo")
    older = feat / "review-spec.md"
    newer = feat / "review-code.md"
    older.write_text("# older\n")
    time.sleep(0.05)
    newer.write_text("# newer\n")

    entries = collect_event_feed(tmp_path)
    timestamps = [e.timestamp for e in entries]
    assert timestamps == sorted(timestamps, reverse=True)


def test_event_feed_caps_at_max_entries(tmp_path: Path):
    """The feed never returns more than EVENT_FEED_MAX_ENTRIES rows."""
    from orca.tui.collectors import EVENT_FEED_MAX_ENTRIES, collect_event_feed

    # Create 5 features, each with all 3 review artifacts -> 15 review events.
    # Add 25 git commits -> 25 git events. Total raw = 40 > 30.
    _init_git_repo(tmp_path)
    for i in range(5):
        feat = _make_feature(tmp_path, f"feat-{i:02d}")
        (feat / "review-spec.md").write_text(f"# review-spec {i}\n")
        (feat / "review-code.md").write_text(f"# review-code {i}\n")
        (feat / "review-pr.md").write_text(f"# review-pr {i}\n")

    for i in range(25):
        f = tmp_path / f"file-{i:02d}.txt"
        f.write_text(f"{i}\n")
        _git(tmp_path, "add", f.name)
        _git(tmp_path, "commit", "-q", "--no-verify", "-m", f"commit {i}")

    entries = collect_event_feed(tmp_path)
    assert len(entries) <= EVENT_FEED_MAX_ENTRIES


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_event_feed_no_crash_on_unreadable_specs(tmp_path: Path, monkeypatch):
    """A specs/ directory that can't be enumerated must not crash the feed."""
    from orca.tui import collectors as collectors_mod

    def _boom(_repo_root):
        raise OSError("simulated read failure")

    monkeypatch.setattr(collectors_mod, "_collect_review_events", _boom)
    # Should still return without raising; git source may still produce entries.
    entries = collectors_mod.collect_event_feed(tmp_path)
    assert isinstance(entries, list)


def test_collect_all_includes_event_feed(tmp_path: Path):
    """collect_all bundles the new event-feed output."""
    from orca.tui.collectors import collect_all

    feat = _make_feature(tmp_path, "001-foo")
    (feat / "review-spec.md").write_text("# review\n")

    result = collect_all(tmp_path)
    assert any(e.source == "review" for e in result.event_feed)
