"""Tests for FeatureCard widget render."""
from __future__ import annotations


def test_feature_card_renders_two_compact_lines():
    """Card is 2 lines: feature_id (bold) and branch · status (dim)."""
    from orca.tui.kanban import CardData, KanbanColumn
    from orca.tui.cards import FeatureCard

    data = CardData(
        feature_id="001-orca-worktree-runtime",
        column=KanbanColumn.PLAN,
        branch="001-orca-worktree-runtime",
        worktree_path="/tmp/wt",
        worktree_status="clean",
        review_summary="spec missing",
    )
    card = FeatureCard(data)
    lines = card._content_lines()
    assert len(lines) == 2
    # Feature_id may be ellipsized to fit narrow columns; the prefix
    # is preserved.
    assert lines[0].startswith("001-orca-worktree-")
    # Line 2 has branch + worktree status separated by a middle dot.
    assert "·" in lines[1]
    assert "clean" in lines[1]


def test_feature_card_renders_no_worktree_placeholder():
    from orca.tui.kanban import CardData, KanbanColumn
    from orca.tui.cards import FeatureCard

    data = CardData(feature_id="001-foo", column=KanbanColumn.SPEC)
    card = FeatureCard(data)
    text = card._content_lines()
    body = "\n".join(text)
    assert "(no worktree)" in body


def test_feature_card_truncates_long_feature_id():
    """Cards keep height fixed; long ids truncate with ellipsis."""
    from orca.tui.kanban import CardData, KanbanColumn
    from orca.tui.cards import FeatureCard

    long_id = "2026-05-01-this-is-a-very-long-feature-id-that-should-be-truncated"
    data = CardData(feature_id=long_id, column=KanbanColumn.SPEC)
    card = FeatureCard(data)
    line1 = card._content_lines()[0]
    assert line1.endswith("…")
    assert len(line1) <= 30
