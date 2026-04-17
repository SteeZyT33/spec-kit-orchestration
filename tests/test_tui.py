"""Tests for the Orca TUI (018-orca-tui) - read-only 4-pane view.

Collectors are pure functions of repo-root input; they do not import
Textual. Pane / app tests use Textual's Pilot harness where practical.
Every GREEN has a RED first per repo TDD discipline.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from speckit_orca import matriarch


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_yolo_run(
    repo_root: Path,
    run_id: str,
    feature_id: str,
    outcome: str,
    current_stage: str = "implement",
) -> None:
    from speckit_orca.yolo import Event, EventType, append_event, generate_ulid

    # RUN_STARTED
    started = Event(
        event_id=generate_ulid(),
        run_id=run_id,
        event_type=EventType.RUN_STARTED,
        timestamp="2026-04-16T10:00:00Z",
        lamport_clock=1,
        actor="claude",
        feature_id=feature_id,
        lane_id=None,
        branch=feature_id,
        head_commit_sha="abc1234",
        from_stage=None,
        to_stage="brainstorm",
        reason=None,
        evidence=None,
    )
    append_event(repo_root, run_id, started)

    # STAGE_ENTERED moves to current_stage
    entered = Event(
        event_id=generate_ulid(),
        run_id=run_id,
        event_type=EventType.STAGE_ENTERED,
        timestamp="2026-04-16T10:01:00Z",
        lamport_clock=2,
        actor="claude",
        feature_id=feature_id,
        lane_id=None,
        branch=feature_id,
        head_commit_sha="abc1234",
        from_stage="brainstorm",
        to_stage=current_stage,
        reason=None,
        evidence=None,
    )
    append_event(repo_root, run_id, entered)

    if outcome == "canceled":
        canceled = Event(
            event_id=generate_ulid(),
            run_id=run_id,
            event_type=EventType.TERMINAL,
            timestamp="2026-04-16T10:02:00Z",
            lamport_clock=3,
            actor="claude",
            feature_id=feature_id,
            lane_id=None,
            branch=feature_id,
            head_commit_sha="abc1234",
            from_stage=current_stage,
            to_stage=None,
            reason="canceled",
            evidence=None,
        )
        append_event(repo_root, run_id, canceled)


def _make_feature(repo_root: Path, feature_id: str, with_spec: bool = True) -> Path:
    feat = repo_root / "specs" / feature_id
    feat.mkdir(parents=True, exist_ok=True)
    if with_spec:
        (feat / "spec.md").write_text(f"# {feature_id} spec\n")
    return feat


# ---------------------------------------------------------------------------
# Phase A - skeleton
# ---------------------------------------------------------------------------


def test_app_imports():
    """RED/GREEN: `speckit_orca.tui` exposes `OrcaTUI` and `main`."""
    from speckit_orca.tui import OrcaTUI, main
    assert OrcaTUI is not None
    assert callable(main)


def test_app_constructs_without_repo_work():
    """Instantiating the app should not touch the filesystem."""
    from speckit_orca.tui import OrcaTUI

    app = OrcaTUI(repo_root=Path("/nonexistent/path/that/does/not/exist"))
    assert app.repo_root == Path("/nonexistent/path/that/does/not/exist")


# ---------------------------------------------------------------------------
# Phase B - collectors
# ---------------------------------------------------------------------------


def _init_repo(tmp_path: Path) -> None:
    """Initialize tmp_path as a minimal git repo with one commit.

    017-agent-presence-and-matriarch-gates tightened ``register_lane`` to
    require a resolvable HEAD (LANE_REGISTRATION_HEAD_UNRESOLVED guard),
    so tests that register lanes need real git history.
    """
    import os
    import subprocess

    (tmp_path / ".specify").mkdir(exist_ok=True)
    if (tmp_path / ".git").exists():
        return
    env = {
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "PATH": os.environ.get("PATH", ""),
    }
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(tmp_path)],
        check=True, capture_output=True,
    )
    (tmp_path / ".gitkeep").write_text("")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", ".gitkeep"],
        check=True, capture_output=True, env=env,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-q", "-m", "init"],
        check=True, capture_output=True, env=env,
    )


def test_collect_lanes_empty(tmp_path: Path):
    """No matriarch directory => empty list, no raise."""
    from speckit_orca.tui.collectors import collect_lanes

    _init_repo(tmp_path)
    rows = collect_lanes(tmp_path)
    assert rows == []


def test_collect_lanes_returns_rows(tmp_path: Path):
    """One registered lane => one LaneRow."""
    from speckit_orca.tui.collectors import LaneRow, collect_lanes

    _init_repo(tmp_path)
    # Create a minimal lane via matriarch.register_lane
    matriarch.register_lane(
        spec_id="020-example",
        title="Example",
        branch="020-example",
        worktree_path=str(tmp_path),
        repo_root=tmp_path,
    )
    rows = collect_lanes(tmp_path)
    assert len(rows) == 1
    assert isinstance(rows[0], LaneRow)
    assert rows[0].lane_id == "020-example"
    assert rows[0].effective_state  # non-empty string


def test_collect_yolo_runs_filters_terminal(tmp_path: Path):
    """Runs with outcome in {completed, canceled, failed} excluded."""
    from speckit_orca.tui.collectors import collect_yolo_runs

    (tmp_path / ".git").mkdir()
    _write_yolo_run(tmp_path, "run-active", "020-example", outcome="running")
    _write_yolo_run(tmp_path, "run-done", "021-example", outcome="canceled")
    rows = collect_yolo_runs(tmp_path)
    run_ids = {r.run_id for r in rows}
    assert "run-active" in run_ids
    assert "run-done" not in run_ids


def test_collect_yolo_runs_empty(tmp_path: Path):
    from speckit_orca.tui.collectors import collect_yolo_runs
    (tmp_path / ".git").mkdir()
    assert collect_yolo_runs(tmp_path) == []


def test_collect_reviews_skips_complete(tmp_path: Path):
    """Features without review-spec appear; features with complete reviews do not.

    MVP rule: a review row appears if its flow-state milestone is in a
    non-terminal status ({missing, not_started, stale, needs-revision,
    blocked, phases_partial, invalid, in_progress}).
    """
    from speckit_orca.tui.collectors import collect_reviews

    (tmp_path / ".git").mkdir()
    # Feature with no review artifacts => pending reviews surface
    _make_feature(tmp_path, "022-needs-review")
    rows = collect_reviews(tmp_path)
    feature_ids = {r.feature_id for r in rows}
    assert "022-needs-review" in feature_ids


def test_collect_event_feed_merges_sources(tmp_path: Path):
    """Yolo events + matriarch inbound mailbox messages merged + sorted desc."""
    from speckit_orca.tui.collectors import collect_event_feed

    (tmp_path / ".git").mkdir()
    _write_yolo_run(tmp_path, "run-feed", "020-example", outcome="running")

    entries = collect_event_feed(tmp_path)
    assert len(entries) > 0
    assert any(e.source == "yolo" for e in entries)
    # Truncated to 30 max
    assert len(entries) <= 30


def test_collect_event_feed_empty(tmp_path: Path):
    from speckit_orca.tui.collectors import collect_event_feed
    (tmp_path / ".git").mkdir()
    assert collect_event_feed(tmp_path) == []


def test_collect_all_returns_collector_result(tmp_path: Path):
    from speckit_orca.tui.collectors import CollectorResult, collect_all

    (tmp_path / ".git").mkdir()
    result = collect_all(tmp_path, polling_mode=True)
    assert isinstance(result, CollectorResult)
    assert result.polling_mode is True
    assert result.lanes == []
    assert result.yolo_runs == []
    assert result.reviews == []
    assert result.event_feed == []
    assert result.collected_at  # truthy timestamp string


# ---------------------------------------------------------------------------
# Phase C - watcher
# ---------------------------------------------------------------------------


def test_watcher_falls_back_when_watchdog_missing(tmp_path, monkeypatch):
    """When watchdog can't be imported, Watcher switches to polling mode."""
    import builtins

    real_import = builtins.__import__

    def fail_watchdog(name, *args, **kwargs):
        if name.startswith("watchdog"):
            raise ImportError("watchdog blocked for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_watchdog)

    # Force a fresh import of watcher module so the shim re-evaluates
    import importlib
    import sys
    sys.modules.pop("speckit_orca.tui.watcher", None)
    watcher_mod = importlib.import_module("speckit_orca.tui.watcher")

    (tmp_path / ".git").mkdir()
    events: list[str] = []
    w = watcher_mod.Watcher(tmp_path, on_change=lambda p: events.append(str(p)))
    assert w.polling_mode is True
    w.stop()


def test_watcher_stops_cleanly(tmp_path):
    """watcher.stop() releases resources and is safe to call twice."""
    import importlib
    import sys
    sys.modules.pop("speckit_orca.tui.watcher", None)
    from speckit_orca.tui import watcher as watcher_mod

    (tmp_path / ".git").mkdir()
    w = watcher_mod.Watcher(tmp_path, on_change=lambda p: None)
    w.stop()
    w.stop()  # idempotent


def test_watcher_detects_file_change(tmp_path):
    """With watchdog available, appending to a watched file triggers on_change."""
    import importlib
    import sys
    sys.modules.pop("speckit_orca.tui.watcher", None)
    from speckit_orca.tui import watcher as watcher_mod

    (tmp_path / ".git").mkdir()
    # Create a yolo runs dir so there's something to watch
    runs = tmp_path / ".specify" / "orca" / "yolo" / "runs" / "run-1"
    runs.mkdir(parents=True)
    events_path = runs / "events.jsonl"
    events_path.write_text("")

    triggered: list[str] = []
    w = watcher_mod.Watcher(
        tmp_path,
        on_change=lambda p: triggered.append(str(p)),
        poll_interval=0.2,
    )
    try:
        # Write to the file
        time.sleep(0.1)
        events_path.write_text('{"hi": 1}\n')
        # Wait up to 2s for the callback
        deadline = time.time() + 3.0
        while time.time() < deadline and not triggered:
            time.sleep(0.05)
        assert triggered, "Watcher did not fire on_change within timeout"
    finally:
        w.stop()


# ---------------------------------------------------------------------------
# Phase D - pane widgets via Textual Pilot
# ---------------------------------------------------------------------------


def test_app_mounts_four_panes(tmp_path: Path):
    """Pilot: all four pane IDs exist on mount."""
    import asyncio
    from speckit_orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test():
            assert app.query_one("#lane-pane") is not None
            assert app.query_one("#yolo-pane") is not None
            assert app.query_one("#review-pane") is not None
            assert app.query_one("#event-pane") is not None

    asyncio.run(_run())


def test_app_quits_on_q(tmp_path: Path):
    """Pilot: pressing q exits the app."""
    import asyncio
    from speckit_orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.press("q")
            await pilot.pause()

    asyncio.run(_run())


def test_app_polling_mode_banner(tmp_path: Path):
    """When polling_mode is forced, header indicator surfaces."""
    import asyncio
    from speckit_orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path, force_polling_mode=True)
        async with app.run_test():
            # Read the polling banner off the app-level reactive string
            assert app.polling_mode is True
            header_text = app.render_header_text().lower()
            assert "polling" in header_text

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Phase E - CLI entry
# ---------------------------------------------------------------------------


def test_main_parses_repo_root_flag(tmp_path: Path, monkeypatch):
    """`main(['--repo-root', path, '--no-run'])` parses without running the app."""
    from speckit_orca.tui import main

    (tmp_path / ".git").mkdir()
    rc = main(["--repo-root", str(tmp_path), "--no-run"])
    assert rc == 0


def test_main_defaults_to_cwd(tmp_path: Path, monkeypatch):
    from speckit_orca.tui import main

    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    rc = main(["--no-run"])
    assert rc == 0


# ---------------------------------------------------------------------------
# Phase F - robustness fixes (PR #61 review threads)
# ---------------------------------------------------------------------------


def test_git_branch_probe_times_out_gracefully(tmp_path: Path, monkeypatch):
    """A hung git subprocess must not block the UI; _git_branch returns None."""
    import subprocess as _subprocess

    from speckit_orca.tui import app as app_mod

    def _raise_timeout(*_args, **_kwargs):
        raise _subprocess.TimeoutExpired(cmd="git", timeout=2.0)

    monkeypatch.setattr(app_mod.subprocess, "run", _raise_timeout)
    assert app_mod._git_branch(tmp_path) is None


def test_git_branch_probe_passes_timeout_argument(tmp_path: Path, monkeypatch):
    """The git probe must invoke subprocess.run with a positive `timeout`."""
    from speckit_orca.tui import app as app_mod

    captured: dict[str, object] = {}

    class _FakeCompleted:
        stdout = "main\n"

    def _fake_run(*args, **kwargs):
        captured.update(kwargs)
        return _FakeCompleted()

    monkeypatch.setattr(app_mod.subprocess, "run", _fake_run)
    result = app_mod._git_branch(tmp_path)
    assert result == "main"
    assert "timeout" in captured
    assert isinstance(captured["timeout"], (int, float))
    assert captured["timeout"] > 0


def test_do_refresh_isolates_pane_failures(tmp_path: Path):
    """One pane raising on update_rows must not prevent the others from refreshing."""
    import asyncio

    from speckit_orca.tui import OrcaTUI
    from speckit_orca.tui.panes import LanePane

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test():
            # Sabotage just one pane's update_rows; the other three should
            # still receive a refresh call.
            lane_pane = app.query_one("#lane-pane", LanePane)

            def _boom(_rows):
                raise RuntimeError("lane pane exploded")

            lane_pane.update_rows = _boom  # type: ignore[assignment]

            calls: dict[str, int] = {"yolo": 0, "review": 0, "event": 0}

            from speckit_orca.tui.panes import EventFeedPane, ReviewPane, YoloPane

            yolo = app.query_one("#yolo-pane", YoloPane)
            review = app.query_one("#review-pane", ReviewPane)
            event = app.query_one("#event-pane", EventFeedPane)

            orig_yolo = yolo.update_rows
            orig_review = review.update_rows
            orig_event = event.update_rows

            def _wrap_yolo(rows):
                calls["yolo"] += 1
                return orig_yolo(rows)

            def _wrap_review(rows):
                calls["review"] += 1
                return orig_review(rows)

            def _wrap_event(rows):
                calls["event"] += 1
                return orig_event(rows)

            yolo.update_rows = _wrap_yolo  # type: ignore[assignment]
            review.update_rows = _wrap_review  # type: ignore[assignment]
            event.update_rows = _wrap_event  # type: ignore[assignment]

            # Trigger refresh explicitly; must not raise.
            app._do_refresh()

            assert calls["yolo"] >= 1
            assert calls["review"] >= 1
            assert calls["event"] >= 1

    asyncio.run(_run())


def test_event_feed_survives_corrupt_jsonl(tmp_path: Path):
    """A corrupt events.jsonl line must not abort the feed; valid entries still surface."""
    from speckit_orca.tui.collectors import collect_event_feed

    (tmp_path / ".git").mkdir()

    # One clean run
    _write_yolo_run(tmp_path, "run-clean", "020-example", outcome="running")

    # One corrupt run: overwrite events.jsonl with garbage lines (no valid JSON)
    bad_run = tmp_path / ".specify" / "orca" / "yolo" / "runs" / "run-bad"
    bad_run.mkdir(parents=True, exist_ok=True)
    (bad_run / "events.jsonl").write_text("this is not json\n{broken\n")

    entries = collect_event_feed(tmp_path)
    # Clean run's events still present.
    assert any("run-clea" in e.summary for e in entries if e.source == "yolo")


def test_event_feed_survives_invalid_utf8(tmp_path: Path):
    """Non-UTF-8 bytes in events.jsonl degrade to empty for that file, not whole feed."""
    from speckit_orca.tui.collectors import collect_event_feed

    (tmp_path / ".git").mkdir()

    # Clean run
    _write_yolo_run(tmp_path, "run-utf8ok", "020-example", outcome="running")

    # Run with invalid UTF-8 bytes in its events.jsonl
    bad_run = tmp_path / ".specify" / "orca" / "yolo" / "runs" / "run-utf8bad"
    bad_run.mkdir(parents=True, exist_ok=True)
    (bad_run / "events.jsonl").write_bytes(b"\xff\xfe\xfd not-utf-8 bytes\n")

    # Must not raise; must still return the clean run's entries.
    entries = collect_event_feed(tmp_path)
    assert any(e.source == "yolo" for e in entries)


def test_tail_jsonl_handles_unicode_decode_error(tmp_path: Path):
    """_tail_jsonl swallows UnicodeDecodeError and returns []."""
    from speckit_orca.tui.collectors import _tail_jsonl

    bad = tmp_path / "bad.jsonl"
    bad.write_bytes(b"\xff\xfe\xfd\n")
    assert _tail_jsonl(bad, 10) == []


def test_event_feed_survives_unreadable_directory(tmp_path: Path, monkeypatch):
    """If iterdir() raises OSError mid-refresh, the feed degrades to the other source."""
    from speckit_orca.tui import collectors as coll

    (tmp_path / ".git").mkdir()
    # Make the runs dir exist so the code path is entered.
    runs_dir = tmp_path / ".specify" / "orca" / "yolo" / "runs"
    runs_dir.mkdir(parents=True)

    real_iterdir = Path.iterdir

    def _iterdir(self):
        if self == runs_dir:
            raise OSError("simulated unreadable tree")
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", _iterdir)

    # Must not raise.
    entries = coll.collect_event_feed(tmp_path)
    assert entries == []
