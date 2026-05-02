"""Tests for visual fixes seen by actually rendering the TUI:

- Event-feed timestamps must be compact relative-time strings (≤8 chars)
  so the summary column fits on an 80-col terminal.
- Default Textual footer bindings (palette etc.) must not surface.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_format_age_seconds():
    from orca.tui.timefmt import format_age

    now = datetime.now(timezone.utc)
    assert format_age(_iso(now), now=now) == "now"
    assert format_age(_iso(now - timedelta(seconds=30)), now=now) == "30s"


def test_format_age_minutes_hours_days():
    from orca.tui.timefmt import format_age

    now = datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc)
    assert format_age(_iso(now - timedelta(minutes=5)), now=now) == "5m"
    assert format_age(_iso(now - timedelta(hours=3)), now=now) == "3h"
    assert format_age(_iso(now - timedelta(days=2)), now=now) == "2d"


def test_format_age_old_falls_back_to_date():
    from orca.tui.timefmt import format_age

    now = datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc)
    old = _iso(now - timedelta(days=10))
    out = format_age(old, now=now)
    # 10+ days falls back to a short calendar date.
    assert out.startswith("Apr") or out.startswith("Apr ")
    assert len(out) <= 8


def test_format_age_handles_garbage():
    """Unparseable timestamp returns the original string truncated."""
    from orca.tui.timefmt import format_age

    out = format_age("not-a-timestamp")
    # Must not raise, returns short fallback.
    assert isinstance(out, str)
    assert len(out) <= 8


def test_event_pane_renders_relative_age(tmp_path: Path):
    """The 'when' column shows a short relative-age string, not the ISO timestamp."""
    from orca.tui import OrcaTUI
    from orca.tui.collectors import EventFeedEntry
    from orca.tui.panes import EventFeedPane

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test():
            pane = app.query_one("#event-pane", EventFeedPane)
            now = datetime.now(timezone.utc)
            entries = [
                EventFeedEntry(timestamp=_iso(now - timedelta(minutes=2)),
                               source="git", summary="abc1234 recent"),
                EventFeedEntry(timestamp=_iso(now - timedelta(hours=5)),
                               source="git", summary="def5678 older"),
            ]
            pane.update_rows(entries)
            from textual.widgets import DataTable
            table = app.query_one("#event-log", DataTable)
            row_keys = list(table.rows)
            first = list(table.get_row(row_keys[0]))
            second = list(table.get_row(row_keys[1]))
            # First column ("when") should now be short relative form.
            assert first[0] in ("2m", "1m", "now", "3m")  # tolerate +/-1 minute
            assert second[0] == "5h"

    asyncio.run(_run())


def test_short_review_kind_strips_prefix():
    """ReviewPane abbreviates 'review-spec' -> 'spec' for display."""
    from orca.tui.panes import ReviewPane
    assert ReviewPane._short_review_kind("review-spec") == "spec"
    assert ReviewPane._short_review_kind("review-code") == "code"
    assert ReviewPane._short_review_kind("review-pr") == "pr"
    # Non-prefixed values pass through.
    assert ReviewPane._short_review_kind("custom") == "custom"


def test_format_applied_at_drops_microseconds():
    """`_format_applied_at` returns YYYY-MM-DD HH:MM (no microseconds)."""
    from orca.tui.adoption import _format_applied_at
    out = _format_applied_at("2026-05-01T15:19:31.063608+00:00")
    assert out == "2026-05-01 15:19"
    # Z-suffix variant
    assert _format_applied_at("2026-05-01T15:19:31Z") == "2026-05-01 15:19"
    # Empty input
    assert _format_applied_at("") == ""
    # Garbage in: returned as-is rather than raise.
    assert _format_applied_at("nonsense") == "nonsense"


def test_adoption_applied_row_uses_short_format(tmp_path: Path):
    """The adoption pane 'applied' row formats applied_at compactly."""
    from orca.tui.adoption import AdoptionInfo, render_rows

    info = AdoptionInfo(
        present=True,
        applied=True,
        applied_files=2,
        applied_at="2026-05-01T15:19:31+00:00",
    )
    rows = render_rows(info)
    applied_row = next(r for r in rows if r.label == "applied")
    assert "2026-05-01 15:19" in applied_row.value
    assert "files" in applied_row.value  # plural with 2
    assert "063608" not in applied_row.value


def test_footer_drops_default_palette_binding(tmp_path: Path):
    """The footer should not surface Textual's default ctrl+p palette binding."""
    from orca.tui import OrcaTUI

    (tmp_path / ".git").mkdir()

    async def _run():
        app = OrcaTUI(repo_root=tmp_path)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            from textual.widgets._footer import FooterKey
            keys = [(fk.key, fk.description) for fk in app.query(FooterKey)]
            descriptions = {d.lower() for _, d in keys}
            assert "palette" not in descriptions, (
                f"unexpected palette binding still in footer: {keys}"
            )

    asyncio.run(_run())
