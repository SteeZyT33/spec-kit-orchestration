"""Tests for 018 TUI v1.1 - drawer views + theme cycling.

Drawer builders are pure functions of repo-root + row input; they do not
import Textual and are unit-tested without a terminal. The DetailDrawer
ModalScreen and theme cycle keybinding are exercised via Textual's Pilot
harness.

TDD discipline: every GREEN has a RED first. See specs/018-orca-tui/v1.1/.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from speckit_orca import matriarch


# ---------------------------------------------------------------------------
# Fixture helpers (mirror the v1 test_tui.py helpers so v1.1 stays isolated)
# ---------------------------------------------------------------------------


def _init_repo(tmp_path: Path) -> None:
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


def _write_yolo_run(
    repo_root: Path,
    run_id: str,
    feature_id: str,
    outcome: str = "running",
    current_stage: str = "implement",
) -> None:
    from speckit_orca.yolo import Event, EventType, append_event, generate_ulid

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


def _make_feature(repo_root: Path, feature_id: str) -> Path:
    feat = repo_root / "specs" / feature_id
    feat.mkdir(parents=True, exist_ok=True)
    (feat / "spec.md").write_text(f"# {feature_id} spec\n")
    return feat


# ---------------------------------------------------------------------------
# Phase B - drawer builders (pure functions)
# ---------------------------------------------------------------------------


def test_drawer_content_lane_builds_from_row(tmp_path: Path):
    """build_lane_drawer returns a DrawerContent with expected labels."""
    from speckit_orca.tui.collectors import LaneRow
    from speckit_orca.tui.drawer import DrawerContent, build_lane_drawer

    _init_repo(tmp_path)
    matriarch.register_lane(
        spec_id="020-example",
        title="Example lane",
        branch="020-example",
        worktree_path=str(tmp_path),
        repo_root=tmp_path,
    )
    row = LaneRow(
        lane_id="020-example",
        effective_state="registered",
        owner_id=None,
        status_reason="",
    )
    content = build_lane_drawer(tmp_path, row)
    assert isinstance(content, DrawerContent)
    assert "020-example" in content.title
    labels = [label for (label, _value) in content.body]
    assert "lane_id" in labels
    assert "effective_state" in labels
    assert "mailbox_counts" in labels
    assert "dependencies" in labels


def test_drawer_content_lane_degrades_on_missing_lane(tmp_path: Path):
    """A lane_id with no record returns a placeholder DrawerContent, no raise."""
    from speckit_orca.tui.collectors import LaneRow
    from speckit_orca.tui.drawer import build_lane_drawer

    _init_repo(tmp_path)
    row = LaneRow(
        lane_id="999-missing",
        effective_state="error",
        owner_id=None,
        status_reason="",
    )
    content = build_lane_drawer(tmp_path, row)
    joined = " ".join(value for (_label, value) in content.body).lower()
    assert "error" in joined or "missing" in joined or "unavailable" in joined


def test_drawer_content_yolo_includes_runstate_fields(tmp_path: Path):
    """Yolo drawer surfaces RunState fields that the pane does not show."""
    from speckit_orca.tui.collectors import YoloRow
    from speckit_orca.tui.drawer import build_yolo_drawer

    (tmp_path / ".git").mkdir()
    _write_yolo_run(tmp_path, "run-drawer", "020-example")
    row = YoloRow(
        run_id="run-drawer",
        feature_id="020-example",
        current_stage="implement",
        outcome="running",
        matriarch_sync_failed=False,
    )
    content = build_yolo_drawer(tmp_path, row)
    labels = [label for (label, _value) in content.body]
    # RunState fields that are NOT in the v1 pane
    assert "mode" in labels
    assert "retry_counts" in labels
    assert "last_event_timestamp" in labels
    # tail should be a list of event summaries
    assert isinstance(content.tail, list)
    assert len(content.tail) > 0


def test_drawer_content_yolo_degrades_on_read_failure(tmp_path: Path):
    """Yolo drawer for unknown run returns placeholder, no raise."""
    from speckit_orca.tui.collectors import YoloRow
    from speckit_orca.tui.drawer import build_yolo_drawer

    (tmp_path / ".git").mkdir()
    row = YoloRow(
        run_id="never-existed",
        feature_id="020-example",
        current_stage="?",
        outcome="?",
        matriarch_sync_failed=False,
    )
    content = build_yolo_drawer(tmp_path, row)
    # must not raise; tail is an empty / placeholder list
    assert isinstance(content.tail, list)
    joined = " ".join(value for (_label, value) in content.body).lower()
    assert "error" in joined or "unavailable" in joined or "no events" in joined or content.tail == []


def test_drawer_content_review_previews_artifact(tmp_path: Path):
    """Review drawer previews the first 40 lines of the artifact when present."""
    from speckit_orca.tui.collectors import ReviewRow
    from speckit_orca.tui.drawer import build_review_drawer

    (tmp_path / ".git").mkdir()
    feat = _make_feature(tmp_path, "022-needs-review")
    artifact = feat / "review-spec.md"
    artifact.write_text("# review\n" + "\n".join(f"line {i}" for i in range(60)))

    row = ReviewRow(
        feature_id="022-needs-review",
        review_type="review-spec",
        status="missing",
    )
    content = build_review_drawer(tmp_path, row)
    assert content.tail  # preview block populated
    assert len(content.tail) <= 40
    assert any("line" in ln or "review" in ln for ln in content.tail)


def test_drawer_content_review_missing_artifact(tmp_path: Path):
    """Review drawer renders placeholder when artifact file absent."""
    from speckit_orca.tui.collectors import ReviewRow
    from speckit_orca.tui.drawer import build_review_drawer

    (tmp_path / ".git").mkdir()
    _make_feature(tmp_path, "022-needs-review")  # feature dir only, no review
    row = ReviewRow(
        feature_id="022-needs-review",
        review_type="review-spec",
        status="missing",
    )
    content = build_review_drawer(tmp_path, row)
    joined_tail = " ".join(content.tail).lower()
    joined_body = " ".join(v for (_l, v) in content.body).lower()
    assert (
        "not yet written" in joined_tail
        or "not yet written" in joined_body
        or "artifact" in joined_tail + joined_body
    )


# ---------------------------------------------------------------------------
# Phase C - Enter / Escape drawer dispatch via Pilot
# ---------------------------------------------------------------------------


def test_enter_on_lane_pushes_drawer(tmp_path: Path):
    """Pressing Enter on the focused lane pane opens DetailDrawer."""
    from speckit_orca.tui import OrcaTUI
    from speckit_orca.tui.drawer import DetailDrawer

    _init_repo(tmp_path)
    matriarch.register_lane(
        spec_id="020-example",
        title="Example",
        branch="020-example",
        worktree_path=str(tmp_path),
        repo_root=tmp_path,
    )

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            # Ensure lane pane is focused and refresh has populated rows.
            app._do_refresh()
            await pilot.pause()
            await pilot.press("1")  # focus lane pane
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, DetailDrawer)

    asyncio.run(_run())


def test_escape_closes_drawer(tmp_path: Path):
    """Escape with the drawer open pops the screen."""
    from speckit_orca.tui import OrcaTUI
    from speckit_orca.tui.drawer import DetailDrawer

    _init_repo(tmp_path)
    matriarch.register_lane(
        spec_id="020-example",
        title="Example",
        branch="020-example",
        worktree_path=str(tmp_path),
        repo_root=tmp_path,
    )

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            app._do_refresh()
            await pilot.pause()
            await pilot.press("1")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, DetailDrawer)
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, DetailDrawer)

    asyncio.run(_run())


def test_enter_toggles_drawer_closed(tmp_path: Path):
    """Enter while the drawer is open also closes it (toggle semantics)."""
    from speckit_orca.tui import OrcaTUI
    from speckit_orca.tui.drawer import DetailDrawer

    _init_repo(tmp_path)
    matriarch.register_lane(
        spec_id="020-example",
        title="Example",
        branch="020-example",
        worktree_path=str(tmp_path),
        repo_root=tmp_path,
    )

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            app._do_refresh()
            await pilot.pause()
            await pilot.press("1")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, DetailDrawer)
            await pilot.press("enter")
            await pilot.pause()
            assert not isinstance(app.screen, DetailDrawer)

    asyncio.run(_run())


def test_enter_on_event_pane_is_noop(tmp_path: Path):
    """Enter on the event-feed pane does not open a drawer."""
    from speckit_orca.tui import OrcaTUI
    from speckit_orca.tui.drawer import DetailDrawer

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.press("4")  # focus event pane
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert not isinstance(app.screen, DetailDrawer)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Phase D - theme cycle
# ---------------------------------------------------------------------------


def test_theme_cycle_advances_on_t(tmp_path: Path):
    from speckit_orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            before = app.theme
            await pilot.press("t")
            await pilot.pause()
            after = app.theme
            # Theme must change (assuming >=2 themes available, which
            # Textual guarantees with its built-ins).
            assert after != before

    asyncio.run(_run())


def test_theme_cycle_wraps_around(tmp_path: Path):
    from speckit_orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            start = app.theme
            # Press t enough times to wrap the cycle (len of cycle + 1).
            cycle_len = len(app._theme_cycle)
            assert cycle_len >= 1
            for _ in range(cycle_len):
                await pilot.press("t")
                await pilot.pause()
            # After a full cycle we should be back at the start.
            assert app.theme == start

    asyncio.run(_run())


def test_theme_cycle_filters_unavailable(tmp_path: Path, monkeypatch):
    """Themes not in available_themes are dropped from the cycle at mount."""
    from speckit_orca.tui import OrcaTUI, app as app_mod

    (tmp_path / ".git").mkdir()

    # Pretend the configured cycle has an unavailable theme.
    monkeypatch.setattr(
        app_mod, "CONFIGURED_THEMES",
        ["textual-dark", "does-not-exist", "monokai"],
    )

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test():
            assert "does-not-exist" not in app._theme_cycle
            # The real ones still made it in.
            assert "textual-dark" in app._theme_cycle or "monokai" in app._theme_cycle

    asyncio.run(_run())


def test_theme_persists_across_refresh(tmp_path: Path):
    """Theme selection survives a forced refresh."""
    from speckit_orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.press("t")
            await pilot.pause()
            chosen = app.theme
            app._do_refresh()
            await pilot.pause()
            assert app.theme == chosen

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Phase F - codex review findings (post-review hardening)
# ---------------------------------------------------------------------------


def test_lane_drawer_renders_deployment_kind_key(tmp_path: Path, monkeypatch):
    """summarize_lane emits `deployment_kind`, not `kind`. FR-104 correctness."""
    from speckit_orca.tui.collectors import LaneRow
    from speckit_orca.tui import drawer as drawer_mod

    def _fake_summarize(lane_id, *, repo_root=None):
        return {
            "lane_id": lane_id,
            "spec_id": "020-x",
            "title": "deployed lane",
            "branch": "020-x",
            "worktree_path": "/tmp/020",
            "effective_state": "active",
            "status_reason": "",
            "owner_type": "codex",
            "owner_id": "ag-1",
            "dependencies": [],
            "mailbox_counts": {"inbound": 1, "outbound": 0, "reports": 2},
            "delegated_work": [],
            "assignment_history": [],
            "deployment": {
                "deployment_kind": "tmux",
                "launched_by": "ag-1",
                "session_name": "orca:020",
            },
            "registry_revision": 3,
            "mailbox_path": ".specify/orca/matriarch/mailbox/020-x",
        }

    from speckit_orca import matriarch as _matriarch
    monkeypatch.setattr(_matriarch, "summarize_lane", _fake_summarize)

    row = LaneRow(
        lane_id="020-x", effective_state="active",
        owner_id="ag-1", status_reason="",
    )
    content = drawer_mod.build_lane_drawer(tmp_path, row)
    dep_value = dict(content.body).get("deployment", "")
    assert "tmux" in dep_value
    assert "ag-1" in dep_value
    assert "?" not in dep_value


def test_lane_drawer_degrades_on_malformed_payload(tmp_path: Path, monkeypatch):
    """A non-dict / partial summarize_lane return must not crash the drawer."""
    from speckit_orca.tui.collectors import LaneRow
    from speckit_orca.tui import drawer as drawer_mod

    def _bad_summarize(lane_id, *, repo_root=None):
        return "this is not a dict"  # malformed payload

    from speckit_orca import matriarch as _matriarch
    monkeypatch.setattr(_matriarch, "summarize_lane", _bad_summarize)

    row = LaneRow(
        lane_id="020-x", effective_state="active",
        owner_id=None, status_reason="",
    )
    # Must not raise.
    content = drawer_mod.build_lane_drawer(tmp_path, row)
    joined = " ".join(v for (_l, v) in content.body).lower()
    assert "020-x" in joined or "error" in joined or "malformed" in joined


def test_yolo_drawer_degrades_on_partial_runstate(tmp_path: Path, monkeypatch):
    """A RunState missing expected attributes must render via getattr fallback."""
    from speckit_orca.tui.collectors import YoloRow
    from speckit_orca.tui import drawer as drawer_mod

    class _Partial:
        run_id = "r-1"
        feature_id = "020"
        # Intentionally missing most fields.

    from speckit_orca import yolo as _yolo
    monkeypatch.setattr(_yolo, "run_status", lambda repo, rid: _Partial())

    row = YoloRow(
        run_id="r-1", feature_id="020", current_stage="implement",
        outcome="running", matriarch_sync_failed=False,
    )
    content = drawer_mod.build_yolo_drawer(tmp_path, row)
    labels = [label for (label, _value) in content.body]
    # Rendering did not raise; required labels are present with fallbacks.
    assert "run_id" in labels
    assert "mode" in labels
    assert "retry_counts" in labels


def test_theme_index_does_not_advance_on_setter_failure(tmp_path: Path, monkeypatch):
    """If theme setter raises, _theme_index must not advance (FR-109 stable)."""
    from speckit_orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            start_idx = app._theme_index
            # Force the theme setter to raise for the next call.
            type(app).theme = property(
                lambda self: getattr(self, "_forced_theme", "textual-dark"),
                lambda self, v: (_ for _ in ()).throw(RuntimeError("boom")),
            )
            try:
                await pilot.press("t")
                await pilot.pause()
            finally:
                # Unbind the forced property so teardown doesn't blow up.
                del type(app).theme
            assert app._theme_index == start_idx

    asyncio.run(_run())


def test_drawer_close_restores_focus_to_origin_pane(tmp_path: Path):
    """Escape after drill on lane pane leaves the lane pane focused."""
    from speckit_orca.tui import OrcaTUI
    from speckit_orca.tui.panes import LanePane

    _init_repo(tmp_path)
    matriarch.register_lane(
        spec_id="020-focus",
        title="focus",
        branch="020-focus",
        worktree_path=str(tmp_path),
        repo_root=tmp_path,
    )

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            app._do_refresh()
            await pilot.pause()
            await pilot.press("1")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            # The originating pane (or a descendant of it) should hold focus.
            pane = app.query_one("#lane-pane", LanePane)
            focused = app.focused
            assert focused is not None
            node = focused
            found = False
            while node is not None:
                if node is pane:
                    found = True
                    break
                node = getattr(node, "parent", None)
            assert found, f"focus not restored to lane pane; focused={focused!r}"

    asyncio.run(_run())
