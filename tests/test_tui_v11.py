"""Tests for 018 TUI v1.1 - drawer views + theme cycling.

Drawer builders are pure functions of repo-root + row input; they do not
import Textual and are unit-tested without a terminal. The DetailDrawer
ModalScreen and theme cycle keybinding are exercised via Textual's Pilot
harness.

TDD discipline: every GREEN has a RED first. See specs/018-orca-tui/v1.1/.
"""

from __future__ import annotations

import asyncio
from pathlib import Path


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_feature(repo_root: Path, feature_id: str) -> Path:
    feat = repo_root / "specs" / feature_id
    feat.mkdir(parents=True, exist_ok=True)
    (feat / "spec.md").write_text(f"# {feature_id} spec\n")
    return feat


# ---------------------------------------------------------------------------
# Phase B - drawer builders (pure functions)
# ---------------------------------------------------------------------------


def test_drawer_content_review_previews_artifact(tmp_path: Path):
    """Review drawer previews the first 40 lines of the artifact when present."""
    from orca.tui.collectors import ReviewRow
    from orca.tui.drawer import build_review_drawer

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
    from orca.tui.collectors import ReviewRow
    from orca.tui.drawer import build_review_drawer

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


def test_enter_on_event_pane_is_noop(tmp_path: Path):
    """Enter on the event-feed pane does not open a drawer."""
    from orca.tui import OrcaTUI
    from orca.tui.drawer import DetailDrawer

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test() as pilot:
            await pilot.press("2")  # focus event pane (binding 2 = events)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert not isinstance(app.screen, DetailDrawer)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Phase D - theme cycle
# ---------------------------------------------------------------------------


def test_theme_cycle_advances_on_t(tmp_path: Path):
    from orca.tui import OrcaTUI

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
    from orca.tui import OrcaTUI

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
    from orca.tui import OrcaTUI, app as app_mod

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
    from orca.tui import OrcaTUI

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


def test_theme_index_does_not_advance_on_setter_failure(tmp_path: Path, monkeypatch):
    """If theme setter raises, _theme_index must not advance (FR-109 stable)."""
    from orca.tui import OrcaTUI

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
