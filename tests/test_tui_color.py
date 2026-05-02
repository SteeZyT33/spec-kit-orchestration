"""Tests for severity-based cell coloring in the TUI panes."""

from __future__ import annotations

from rich.text import Text


def test_styled_returns_text_with_keyed_style():
    from orca.tui.panes import _styled

    out = _styled("missing", {"missing": "red"})
    assert isinstance(out, Text)
    assert str(out.style) == "red"


def test_styled_returns_unstyled_for_unknown_value():
    from orca.tui.panes import _styled

    out = _styled("whatever", {"missing": "red"})
    assert str(out.style) == ""


def test_review_status_severity_palette():
    """Status tokens map to the right ANSI severity buckets."""
    from orca.tui.panes import _REVIEW_STATUS_STYLES

    # red (blocking)
    assert "red" in _REVIEW_STATUS_STYLES["missing"]
    assert "red" in _REVIEW_STATUS_STYLES["blocked"]
    # yellow (in-progress / needs attention)
    assert "yellow" in _REVIEW_STATUS_STYLES["needs-revision"]
    assert "yellow" in _REVIEW_STATUS_STYLES["in_progress"]
    # dim (waiting / passive)
    assert "dim" in _REVIEW_STATUS_STYLES["not_started"]
    # green (done)
    assert "green" in _REVIEW_STATUS_STYLES["complete"]


def test_event_source_styles():
    from orca.tui.panes import _EVENT_SOURCE_STYLES

    assert _EVENT_SOURCE_STYLES["git"] == "cyan"
    assert _EVENT_SOURCE_STYLES["review"] == "green"


def test_adoption_value_styled_yes_is_green():
    from orca.tui.panes import _adoption_value_styled

    out = _adoption_value_styled("yes  1 file  2026-05-01 15:19")
    assert str(out.style) == "green"


def test_adoption_value_styled_manifest_only_is_yellow():
    from orca.tui.panes import _adoption_value_styled

    out = _adoption_value_styled("manifest only (run: orca-cli apply)")
    assert str(out.style) == "yellow"


def test_adoption_value_styled_not_adopted_is_red():
    from orca.tui.panes import _adoption_value_styled

    out = _adoption_value_styled("not adopted (run: orca-cli adopt)")
    assert str(out.style) == "red"
